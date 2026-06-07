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


def sync_contacts_from_shopify_orders() -> dict:
    # Aggregate stats and latest-order details per buyer email.
    # Used by both the INSERT and the UPDATE below.
    _STATS_CTE = """
        order_stats AS (
            SELECT
                lower(email)                              AS email,
                COUNT(*)                                  AS orders_count,
                SUM(total_price)                          AS total_spent,
                SUM(total_price) / NULLIF(COUNT(*), 0)   AS ticket_medio,
                MAX(created_at)::date                     AS last_purchase
            FROM shopify_orders
            WHERE email IS NOT NULL
              AND email <> ''
              AND cancelled_at IS NULL
              AND financial_status NOT IN ('voided', 'refunded')
            GROUP BY lower(email)
        ),
        latest_order AS (
            SELECT DISTINCT ON (lower(email))
                lower(email)                                              AS email,
                TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS name,
                shipping_city,
                shipping_province,
                COALESCE((raw->>'buyer_accepts_marketing')::boolean, false) AS accepts_marketing
            FROM shopify_orders
            WHERE email IS NOT NULL
              AND cancelled_at IS NULL
            ORDER BY lower(email), created_at DESC
        )
    """

    insert_sql = text(f"""
        WITH {_STATS_CTE}
        INSERT INTO contacts (
            email, name,
            orders_count, total_spent, ticket_medio, last_purchase,
            shipping_city, shipping_province,
            opted_in, accepts_marketing,
            origin_utm,
            created_at, updated_at
        )
        SELECT
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
        JOIN latest_order lo ON lo.email = os.email
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
            updated_at        = NOW()
        FROM order_stats os
        JOIN latest_order lo ON lo.email = os.email
        WHERE lower(c.email) = os.email
          AND (
              c.last_purchase   IS DISTINCT FROM os.last_purchase
              OR c.orders_count IS DISTINCT FROM os.orders_count
          )
        RETURNING c.id
    """)

    with engine.connect() as conn:
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
