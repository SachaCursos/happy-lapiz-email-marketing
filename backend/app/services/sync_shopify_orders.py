"""
Keeps contacts in sync with the shopify_orders table.
Called from the background scheduler every minute.
- Creates a contact for every new Shopify buyer not yet in contacts.
- Updates order stats (orders_count, total_spent, last_purchase, etc.)
  for contacts that already exist whenever newer orders arrive.
"""
import logging
from sqlalchemy import text
from app.database import engine

logger = logging.getLogger(__name__)

# shopify_orders is owned by the separate ETL pipeline (happylapiz-etl), not this
# app — on an environment where that pipeline hasn't run yet (e.g. a fresh staging
# DB), the table can exist with only a subset of its normal columns. Check before
# querying so a schema that isn't ready yet logs one short line instead of the
# scheduler dumping a full traceback every 60s.
_REQUIRED_COLUMNS = {
    "email", "total_price", "financial_status", "cancelled_at", "created_at",
    "first_name", "last_name", "raw", "shipping_city", "shipping_province", "shop_id",
}

# Set once the "schema not ready" warning has been logged, so it prints a single
# time per process instead of every scheduler tick (every 60s) until the ETL
# pipeline adds the missing column(s).
_schema_warning_logged = False


def _shopify_orders_schema_ready(conn) -> bool:
    global _schema_warning_logged
    existing = {
        row[0] for row in conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'shopify_orders'"
        ))
    }
    missing = _REQUIRED_COLUMNS - existing
    if missing:
        if not _schema_warning_logged:
            logger.warning(
                "sync_contacts_from_shopify_orders: shopify_orders le faltan columnas %s — salteando hasta que el ETL las cree (este warning no se repite)",
                sorted(missing),
            )
            _schema_warning_logged = True
        return False
    return True


def sync_contacts_from_shopify_orders() -> dict:
    # Aggregate stats and latest-order details per buyer email.
    # Used by both the INSERT and the UPDATE below.
    # shop_id IS NOT NULL on both CTEs: shopify_orders is populated by the separate
    # ETL pipeline, which doesn't tag rows with shop_id yet. Guessing a shop_id here
    # (e.g. defaulting to "the" shop) would either mis-assign orders once a second
    # shop exists, or keep inserting shop_id-NULL contacts forever and block the
    # eventual NOT NULL tightening (0004_tighten_shop_id_constraints). Skipping
    # untagged orders is a no-op today (single shop, ETL not yet updated) and
    # self-heals once the ETL starts writing shop_id.
    _STATS_CTE = """
        order_stats AS (
            SELECT
                lower(email)                              AS email,
                shop_id                                   AS shop_id,
                COUNT(*)                                  AS orders_count,
                SUM(total_price)                          AS total_spent,
                SUM(total_price) / NULLIF(COUNT(*), 0)   AS ticket_medio,
                MAX(created_at)::date                     AS last_purchase
            FROM shopify_orders
            WHERE email IS NOT NULL
              AND email <> ''
              AND cancelled_at IS NULL
              AND financial_status NOT IN ('voided', 'refunded')
              AND shop_id IS NOT NULL
            GROUP BY lower(email), shop_id
        ),
        latest_order AS (
            SELECT DISTINCT ON (lower(email), shop_id)
                lower(email)                                              AS email,
                shop_id                                                   AS shop_id,
                TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS name,
                shipping_city,
                shipping_province,
                COALESCE((raw->>'buyer_accepts_marketing')::boolean, false) AS accepts_marketing
            FROM shopify_orders
            WHERE email IS NOT NULL
              AND cancelled_at IS NULL
              AND shop_id IS NOT NULL
            ORDER BY lower(email), shop_id, created_at DESC
        )
    """

    insert_sql = text(f"""
        WITH {_STATS_CTE}
        INSERT INTO contacts (
            shop_id, email, name,
            orders_count, total_spent, ticket_medio, last_purchase,
            shipping_city, shipping_province,
            opted_in, accepts_marketing,
            origin_utm,
            created_at, updated_at
        )
        SELECT
            os.shop_id,
            os.email,
            lo.name,
            os.orders_count,
            os.total_spent,
            os.ticket_medio,
            os.last_purchase,
            lo.shipping_city,
            lo.shipping_province,
            true,
            lo.accepts_marketing,
            'shopify',
            NOW(), NOW()
        FROM order_stats os
        JOIN latest_order lo ON lo.email = os.email AND lo.shop_id = os.shop_id
        WHERE NOT EXISTS (
            SELECT 1 FROM contacts c WHERE lower(c.email) = os.email
        )
        RETURNING id
    """)

    update_sql = text(f"""
        WITH {_STATS_CTE}
        UPDATE contacts c
        SET
            orders_count      = os.orders_count,
            total_spent       = os.total_spent,
            ticket_medio      = os.ticket_medio,
            last_purchase     = os.last_purchase,
            shipping_city     = COALESCE(lo.shipping_city,    c.shipping_city),
            shipping_province = COALESCE(lo.shipping_province, c.shipping_province),
            shop_id           = COALESCE(c.shop_id, os.shop_id),
            updated_at        = NOW()
        FROM order_stats os
        JOIN latest_order lo ON lo.email = os.email AND lo.shop_id = os.shop_id
        WHERE lower(c.email) = os.email
          AND (
              c.last_purchase   IS DISTINCT FROM os.last_purchase
              OR c.orders_count IS DISTINCT FROM os.orders_count
          )
        RETURNING c.id
    """)

    with engine.connect() as conn:
        if not _shopify_orders_schema_ready(conn):
            return {"created": 0, "updated": 0, "skipped": "shopify_orders schema not ready"}
        ins = conn.execute(insert_sql)
        upd = conn.execute(update_sql)
        conn.commit()

    created = len(ins.fetchall())
    updated = len(upd.fetchall())

    if created or updated:
        logger.info(
            "sync_shopify_orders: %d contact(s) created, %d updated",
            created, updated,
        )
    return {"created": created, "updated": updated}
