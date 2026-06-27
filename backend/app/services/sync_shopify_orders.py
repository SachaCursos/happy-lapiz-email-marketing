"""
Keeps contacts in sync with the shopify_orders table.
Called from the background scheduler every minute.
- Creates a contact for every new Shopify buyer not yet in contacts.
- Updates order stats (orders_count, total_spent, last_purchase, etc.)
  for contacts that already exist whenever newer orders arrive.
- Backfills shopify_events for recent orders that were never delivered via webhook.
  This makes placed_order / ordered_product automations resilient to webhook failures.
"""
import logging
from sqlalchemy import text
from app.database import engine

logger = logging.getLogger(__name__)


def _backfill_missing_order_events(conn) -> int:
    """Insert shopify_events rows for orders from the last 72 hours that have no webhook event.

    Uses shopify_id = str(order.id) so the automation engine can deduplicate against
    both webhook-created events and manually-created retroactive enrollments.
    """
    result = conn.execute(text("""
        INSERT INTO shopify_events (topic, shopify_id, email, payload, processed, created_at)
        SELECT
            'orders/create',
            so.id::text,
            LOWER(so.email),
            COALESCE(so.raw, '{}'::jsonb),
            FALSE,
            NOW()
        FROM shopify_orders so
        WHERE so.created_at >= NOW() - INTERVAL '72 hours'
          AND so.email IS NOT NULL AND so.email <> ''
          AND so.cancelled_at IS NULL
          AND so.financial_status NOT IN ('voided', 'refunded')
          AND NOT EXISTS (
              SELECT 1 FROM shopify_events se
              WHERE se.shopify_id = so.id::text
                AND se.topic = 'orders/create'
          )
    """))
    return result.rowcount


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
        backfilled = _backfill_missing_order_events(conn)
        conn.commit()

    created = len(ins.fetchall())
    updated = len(upd.fetchall())

    if created or updated or backfilled:
        logger.info(
            "sync_shopify_orders: %d contact(s) created, %d updated, %d order event(s) backfilled",
            created, updated, backfilled,
        )
    return {"created": created, "updated": updated, "events_backfilled": backfilled}
