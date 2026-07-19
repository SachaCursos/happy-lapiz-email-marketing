"""
Poll Shopify abandoned checkouts into carritos_abandonados.

Webhooks for checkouts/carts can disappear or stop firing; this sync keeps
abandoned-cart automations fed. Runs on a staggered scheduler interval.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text

from app.core.config import settings
from app.database import engine

logger = logging.getLogger(__name__)

_API_VERSION = "2024-10"
_GID_RE = re.compile(r"AbandonedCheckout/(\d+)")
_URL_TOKEN_RE = re.compile(r"/checkouts/ac/([^/?]+)")

_GQL = """
query($cursor: String, $q: String!) {
  abandonedCheckouts(first: 50, reverse: true, after: $cursor, query: $q) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      name
      createdAt
      updatedAt
      completedAt
      abandonedCheckoutUrl
      totalPriceSet { shopMoney { amount currencyCode } }
      subtotalPriceSet { shopMoney { amount } }
      totalDiscountSet { shopMoney { amount } }
      customer { email firstName lastName phone }
      billingAddress { firstName lastName phone city province country }
      shippingAddress { firstName lastName phone city province country }
      lineItems(first: 25) {
        nodes {
          title
          quantity
          variant { id sku }
        }
      }
    }
  }
}
"""


def _checkout_token(node: dict) -> str | None:
    """Stable token for carritos_abandonados.checkout_token UNIQUE."""
    url = node.get("abandonedCheckoutUrl") or ""
    m = _URL_TOKEN_RE.search(url)
    if m:
        return m.group(1)
    gid = node.get("id") or ""
    m = _GID_RE.search(gid)
    if m:
        return m.group(1)
    return None


def _money(node: dict, key: str) -> float:
    try:
        return float(((node.get(key) or {}).get("shopMoney") or {}).get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def _fetch_abandoned_checkouts(token: str, domain: str, since: datetime, limit: int = 150) -> list[dict]:
    """Fetch open, not-recovered abandoned checkouts created since `since`."""
    since_s = since.strftime("%Y-%m-%d")
    query_filter = f"created_at:>={since_s} status:open recovery_state:not_recovered"

    url = f"https://{domain}/admin/api/{_API_VERSION}/graphql.json"
    headers = {"X-Shopify-Access-Token": token, "Content-Type": "application/json"}
    out: list[dict] = []
    cursor = None
    with httpx.Client(timeout=45) as client:
        while len(out) < limit:
            r = client.post(
                url,
                headers=headers,
                json={"query": _GQL, "variables": {"cursor": cursor, "q": query_filter}},
            )
            r.raise_for_status()
            payload = r.json()
            if payload.get("errors"):
                raise RuntimeError(str(payload["errors"])[:400])
            conn = (payload.get("data") or {}).get("abandonedCheckouts") or {}
            nodes = conn.get("nodes") or []
            out.extend(nodes)
            page = conn.get("pageInfo") or {}
            if not page.get("hasNextPage") or not page.get("endCursor"):
                break
            cursor = page["endCursor"]
    return out[:limit]


def _upsert_cart(conn, node: dict) -> str | None:
    """Insert/update one abandoned checkout. Returns 'inserted'|'updated'|None."""
    token = _checkout_token(node)
    if not token:
        return None

    customer = node.get("customer") or {}
    bill = node.get("billingAddress") or {}
    ship = node.get("shippingAddress") or {}
    email = (customer.get("email") or "").lower().strip()
    if not email:
        return None

    first_name = customer.get("firstName") or bill.get("firstName") or ship.get("firstName") or ""
    last_name = customer.get("lastName") or bill.get("lastName") or ship.get("lastName") or ""
    phone = customer.get("phone") or bill.get("phone") or ship.get("phone") or ""

    line_items = []
    for li in (node.get("lineItems") or {}).get("nodes") or []:
        variant = li.get("variant") or {}
        line_items.append({
            "title": li.get("title") or "",
            "quantity": li.get("quantity") or 1,
            "variant_id": str(variant.get("id") or ""),
            "sku": variant.get("sku") or "",
        })

    currency = ((node.get("totalPriceSet") or {}).get("shopMoney") or {}).get("currencyCode") or "CLP"
    completed = bool(node.get("completedAt"))
    checkout_url = node.get("abandonedCheckoutUrl") or "https://happylapiz.cl/cart"

    result = conn.execute(text("""
        INSERT INTO carritos_abandonados (
            checkout_token, email, first_name, last_name, phone,
            subtotal_price, total_price, total_discounts, currency,
            line_items,
            shipping_city, shipping_province, shipping_country,
            checkout_url, recovered, abandoned_email_sent,
            shopify_created_at, shopify_updated_at,
            created_at, updated_at
        ) VALUES (
            :token, :email, :first_name, :last_name, :phone,
            :subtotal, :total, :discounts, :currency,
            CAST(:line_items AS jsonb),
            :city, :province, :country,
            :checkout_url, :recovered, FALSE,
            :shopify_created, :shopify_updated,
            COALESCE(CAST(:shopify_created AS timestamptz), NOW()), NOW()
        )
        ON CONFLICT (checkout_token) DO UPDATE SET
            email              = COALESCE(EXCLUDED.email, carritos_abandonados.email),
            first_name         = COALESCE(NULLIF(EXCLUDED.first_name,''), carritos_abandonados.first_name),
            last_name          = COALESCE(NULLIF(EXCLUDED.last_name,''),  carritos_abandonados.last_name),
            phone              = COALESCE(NULLIF(EXCLUDED.phone,''),      carritos_abandonados.phone),
            subtotal_price     = EXCLUDED.subtotal_price,
            total_price        = EXCLUDED.total_price,
            total_discounts    = EXCLUDED.total_discounts,
            currency           = COALESCE(EXCLUDED.currency, carritos_abandonados.currency),
            line_items         = EXCLUDED.line_items,
            shipping_city      = COALESCE(NULLIF(EXCLUDED.shipping_city,''),     carritos_abandonados.shipping_city),
            shipping_province  = COALESCE(NULLIF(EXCLUDED.shipping_province,''), carritos_abandonados.shipping_province),
            shipping_country   = COALESCE(NULLIF(EXCLUDED.shipping_country,''),  carritos_abandonados.shipping_country),
            checkout_url       = COALESCE(EXCLUDED.checkout_url, carritos_abandonados.checkout_url),
            recovered          = carritos_abandonados.recovered OR EXCLUDED.recovered,
            shopify_updated_at = EXCLUDED.shopify_updated_at,
            updated_at         = NOW()
        RETURNING (xmax = 0) AS inserted
    """), {
        "token": token,
        "email": email,
        "first_name": first_name or "",
        "last_name": last_name or "",
        "phone": phone or "",
        "subtotal": _money(node, "subtotalPriceSet"),
        "total": _money(node, "totalPriceSet"),
        "discounts": _money(node, "totalDiscountSet"),
        "currency": currency,
        "line_items": json.dumps(line_items),
        "city": ship.get("city"),
        "province": ship.get("province"),
        "country": ship.get("country"),
        "checkout_url": checkout_url,
        "recovered": completed,
        "shopify_created": node.get("createdAt"),
        "shopify_updated": node.get("updatedAt"),
    })
    row = result.fetchone()
    return "inserted" if row and row[0] else "updated"


def _mark_recovered_from_orders(conn) -> int:
    """Mark carts recovered when the email has an order after the cart was created."""
    result = conn.execute(text("""
        UPDATE carritos_abandonados c
        SET recovered = TRUE,
            recovered_at = COALESCE(c.recovered_at, NOW()),
            updated_at = NOW()
        WHERE c.recovered = FALSE
          AND c.email IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM shopify_orders o
              WHERE LOWER(o.email) = LOWER(c.email)
                AND o.cancelled_at IS NULL
                AND o.created_at >= c.created_at - INTERVAL '1 hour'
          )
    """))
    return result.rowcount or 0


def sync_abandoned_checkouts(lookback_hours: float = 72) -> dict:
    """Pull recent abandoned checkouts from Shopify into carritos_abandonados."""
    token = settings.SHOPIFY_ACCESS_TOKEN
    domain = settings.SHOPIFY_DOMAIN
    if not token:
        logger.error("sync_abandoned_checkouts: SHOPIFY_ACCESS_TOKEN missing")
        return {"ok": False, "error": "SHOPIFY_ACCESS_TOKEN missing"}

    since = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    try:
        nodes = _fetch_abandoned_checkouts(token, domain, since)
    except Exception as exc:
        logger.exception("sync_abandoned_checkouts fetch failed: %s", exc)
        return {"ok": False, "error": str(exc)[:300]}

    inserted = updated = skipped = 0
    with engine.begin() as conn:
        for node in nodes:
            try:
                action = _upsert_cart(conn, node)
            except Exception as exc:
                logger.warning("upsert abandoned checkout failed: %s", exc)
                skipped += 1
                continue
            if action == "inserted":
                inserted += 1
            elif action == "updated":
                updated += 1
            else:
                skipped += 1
        recovered = _mark_recovered_from_orders(conn)

    summary = {
        "ok": True,
        "fetched": len(nodes),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "marked_recovered": recovered,
        "lookback_hours": lookback_hours,
    }
    logger.info("sync_abandoned_checkouts: %s", summary)
    return summary
