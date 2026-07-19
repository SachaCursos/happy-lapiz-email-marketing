"""
Keeps contacts in sync with the shopify_orders table.
Called from the background scheduler every 10 minutes.
- Pulls recent orders from Shopify Admin API (webhook fallback).
- Creates/updates contacts from those orders.
- Backfills shopify_events so placed_order / ordered_product / fulfilled /
  cancelled automations keep working when webhooks drop.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.database import engine

logger = logging.getLogger(__name__)

_API_VERSION = "2024-10"


def _parse_shopify_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _upsert_order_from_payload(conn, order: dict) -> bool:
    """Insert shopify_orders + line items from a Shopify REST order. Returns True if new."""
    order_id = str(order.get("id") or "")
    if not order_id:
        return False
    email = (order.get("email") or "").lower().strip() or None
    customer = order.get("customer") or {}
    bill = order.get("billing_address") or {}
    ship = order.get("shipping_address") or {}
    items = order.get("line_items") or []
    created = _parse_shopify_dt(order.get("created_at")) or datetime.now(timezone.utc)
    cancelled = _parse_shopify_dt(order.get("cancelled_at"))
    now = datetime.now(timezone.utc)

    gateways = order.get("payment_gateway_names")
    payment_gateway = gateways[0] if isinstance(gateways, list) and gateways else order.get("gateway")

    result = conn.execute(text("""
        INSERT INTO shopify_orders (
            id, order_number, email, phone, financial_status, fulfillment_status,
            total_price, subtotal_price, total_tax, total_discounts, currency, created_at,
            customer_id, raw, synced_at, first_name, last_name, order_name, payment_gateway,
            line_items_json, cancelled_at, cancel_reason, tags, shipping_city, shipping_province
        ) VALUES (
            :id, :order_number, :email, :phone, :financial_status, :fulfillment_status,
            :total_price, :subtotal_price, :total_tax, :total_discounts, :currency, :created_at,
            :customer_id, CAST(:raw AS jsonb), :synced_at, :first_name, :last_name, :order_name,
            :payment_gateway, CAST(:line_items_json AS jsonb), :cancelled_at, :cancel_reason,
            :tags, :shipping_city, :shipping_province
        )
        ON CONFLICT (id) DO UPDATE SET
            email = COALESCE(EXCLUDED.email, shopify_orders.email),
            financial_status = COALESCE(EXCLUDED.financial_status, shopify_orders.financial_status),
            fulfillment_status = COALESCE(EXCLUDED.fulfillment_status, shopify_orders.fulfillment_status),
            total_price = EXCLUDED.total_price,
            cancelled_at = COALESCE(EXCLUDED.cancelled_at, shopify_orders.cancelled_at),
            raw = EXCLUDED.raw,
            synced_at = EXCLUDED.synced_at,
            line_items_json = EXCLUDED.line_items_json,
            updated_at = NOW()
        RETURNING (xmax = 0) AS inserted
    """), {
        "id": order_id,
        "order_number": order.get("order_number"),
        "email": email,
        "phone": order.get("phone") or customer.get("phone"),
        "financial_status": order.get("financial_status"),
        "fulfillment_status": order.get("fulfillment_status"),
        "total_price": float(order.get("total_price") or 0),
        "subtotal_price": float(order.get("subtotal_price") or 0),
        "total_tax": float(order.get("total_tax") or 0),
        "total_discounts": float(order.get("total_discounts") or 0),
        "currency": order.get("currency") or "CLP",
        "created_at": created,
        "customer_id": str(customer.get("id") or "") or None,
        "raw": json.dumps(order),
        "synced_at": now,
        "first_name": bill.get("first_name") or customer.get("first_name"),
        "last_name": bill.get("last_name") or customer.get("last_name"),
        "order_name": order.get("name"),
        "payment_gateway": payment_gateway,
        "line_items_json": json.dumps(items),
        "cancelled_at": cancelled,
        "cancel_reason": order.get("cancel_reason"),
        "tags": order.get("tags"),
        "shipping_city": ship.get("city"),
        "shipping_province": ship.get("province"),
    })
    row = result.fetchone()
    inserted = bool(row and row[0])

    for item in items:
        item_id = str(item.get("id") or "")
        if not item_id:
            continue
        conn.execute(text("""
            INSERT INTO shopify_order_line_items (
                id, order_id, order_number, product_id, variant_id,
                title, variant_title, sku, quantity, price, total_discount, synced_at
            ) VALUES (
                :id, :order_id, :order_number, :product_id, :variant_id,
                :title, :variant_title, :sku, :quantity, :price, :total_discount, :synced_at
            )
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": item_id,
            "order_id": order_id,
            "order_number": order.get("order_number"),
            "product_id": str(item.get("product_id") or ""),
            "variant_id": str(item.get("variant_id") or ""),
            "title": item.get("title") or "",
            "variant_title": item.get("variant_title") or "",
            "sku": item.get("sku") or "",
            "quantity": item.get("quantity") or 1,
            "price": float(item.get("price") or 0),
            "total_discount": float(item.get("total_discount") or 0),
            "synced_at": now,
        })
    return inserted


def pull_recent_orders_from_shopify(lookback_hours: float = 72) -> dict:
    """Pull recent Shopify orders into shopify_orders (webhook fallback)."""
    token = settings.SHOPIFY_ACCESS_TOKEN
    domain = settings.SHOPIFY_DOMAIN
    if not token:
        logger.error("pull_recent_orders_from_shopify: SHOPIFY_ACCESS_TOKEN missing")
        return {"ok": False, "error": "SHOPIFY_ACCESS_TOKEN missing", "fetched": 0, "inserted": 0}

    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    created_min = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"X-Shopify-Access-Token": token}
    url = f"https://{domain}/admin/api/{_API_VERSION}/orders.json"
    params: dict | None = {
        "status": "any",
        "limit": 250,
        "created_at_min": created_min,
        "order": "created_at asc",
    }

    fetched = inserted = 0
    try:
        with httpx.Client(timeout=60) as client:
            while True:
                r = client.get(url, headers=headers, params=params)
                if r.status_code != 200:
                    logger.error("Shopify orders pull failed: %s %s", r.status_code, r.text[:200])
                    return {
                        "ok": False,
                        "error": f"Shopify API {r.status_code}",
                        "fetched": fetched,
                        "inserted": inserted,
                    }
                orders = r.json().get("orders") or []
                if not orders:
                    break
                with engine.begin() as conn:
                    for order in orders:
                        fetched += 1
                        if _upsert_order_from_payload(conn, order):
                            inserted += 1
                link = r.headers.get("Link") or r.headers.get("link") or ""
                next_url = None
                for part in link.split(","):
                    if 'rel="next"' in part:
                        next_url = part[part.find("<") + 1:part.find(">")]
                        break
                if not next_url:
                    break
                url = next_url
                params = None
    except Exception as exc:
        logger.exception("pull_recent_orders_from_shopify failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300], "fetched": fetched, "inserted": inserted}

    summary = {"ok": True, "fetched": fetched, "inserted": inserted, "lookback_hours": lookback_hours}
    if fetched:
        logger.info("pull_recent_orders_from_shopify: %s", summary)
    return summary


def _backfill_missing_order_events(conn) -> int:
    """Insert shopify_events for recent orders missing webhook delivery."""
    result = conn.execute(text("""
        INSERT INTO shopify_events (topic, shopify_id, email, payload, processed, created_at)
        SELECT
            'orders/create',
            so.id::text,
            LOWER(so.email),
            COALESCE(so.raw, '{}'::jsonb),
            FALSE,
            COALESCE(so.created_at, NOW())
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
    create_count = result.rowcount or 0

    fulfilled = conn.execute(text("""
        INSERT INTO shopify_events (topic, shopify_id, email, payload, processed, created_at)
        SELECT
            'orders/fulfilled',
            so.id::text,
            LOWER(so.email),
            COALESCE(so.raw, '{}'::jsonb),
            FALSE,
            COALESCE(so.updated_at_shopify, so.updated_at, so.created_at, NOW())
        FROM shopify_orders so
        WHERE so.created_at >= NOW() - INTERVAL '14 days'
          AND so.email IS NOT NULL AND so.email <> ''
          AND so.fulfillment_status = 'fulfilled'
          AND NOT EXISTS (
              SELECT 1 FROM shopify_events se
              WHERE se.shopify_id = so.id::text
                AND se.topic = 'orders/fulfilled'
          )
    """))
    cancelled = conn.execute(text("""
        INSERT INTO shopify_events (topic, shopify_id, email, payload, processed, created_at)
        SELECT
            'orders/cancelled',
            so.id::text,
            LOWER(so.email),
            COALESCE(so.raw, '{}'::jsonb),
            FALSE,
            COALESCE(so.cancelled_at, NOW())
        FROM shopify_orders so
        WHERE so.cancelled_at IS NOT NULL
          AND so.cancelled_at >= NOW() - INTERVAL '14 days'
          AND so.email IS NOT NULL AND so.email <> ''
          AND NOT EXISTS (
              SELECT 1 FROM shopify_events se
              WHERE se.shopify_id = so.id::text
                AND se.topic = 'orders/cancelled'
          )
    """))
    return create_count + (fulfilled.rowcount or 0) + (cancelled.rowcount or 0)


def sync_contacts_from_shopify_orders() -> dict:
    pull = pull_recent_orders_from_shopify(lookback_hours=72)

    _RECENT = "AND created_at >= NOW() - INTERVAL '72 hours'"

    _STATS_CTE = f"""
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
              {_RECENT}
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
              {_RECENT}
            ORDER BY lower(email), created_at DESC
        )
    """

    insert_sql = text(f"""
        WITH {_STATS_CTE},
        new_buyers AS (
            SELECT DISTINCT ON (lower(so.email))
                lower(so.email) AS email,
                TRIM(COALESCE(so.first_name, '') || ' ' || COALESCE(so.last_name, '')) AS name,
                so.shipping_city,
                so.shipping_province,
                COALESCE((so.raw->>'buyer_accepts_marketing')::boolean, false) AS accepts_marketing,
                so.created_at
            FROM shopify_orders so
            WHERE so.email IS NOT NULL AND so.email <> ''
              AND so.cancelled_at IS NULL
              AND so.created_at >= NOW() - INTERVAL '30 days'
            ORDER BY lower(so.email), so.created_at DESC
        )
        INSERT INTO contacts (
            email, name,
            orders_count, total_spent, ticket_medio, last_purchase,
            shipping_city, shipping_province,
            opted_in, accepts_marketing,
            origin_utm,
            created_at, updated_at
        )
        SELECT
            nb.email,
            nb.name,
            1, 0, 0, nb.created_at::date,
            nb.shipping_city,
            nb.shipping_province,
            true,
            nb.accepts_marketing,
            'shopify',
            NOW(), NOW()
        FROM new_buyers nb
        WHERE NOT EXISTS (
            SELECT 1 FROM contacts c WHERE lower(c.email) = nb.email
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

    if created or updated or backfilled or pull.get("inserted"):
        logger.info(
            "sync_shopify_orders: pull=%s, %d contact(s) created, %d updated, %d order event(s) backfilled",
            pull, created, updated, backfilled,
        )
    return {
        "created": created,
        "updated": updated,
        "events_backfilled": backfilled,
        "orders_pulled": pull,
    }
