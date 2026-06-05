"""
Recibe webhooks de Shopify y dispara automatizaciones de email.

Triggers cubiertos (espejo de Klaviyo):
  Desde Shopify:
    checkout_started       checkouts/create
    abandoned_cart         checkouts/create (sin orden tras X horas)
    placed_order           orders/create
    ordered_product        orders/create (por cada line_item)
    fulfilled_order        orders/fulfilled
    fulfilled_partial_order orders/partially_fulfilled
    confirmed_shipment     orders/fulfilled con tracking_number
    delivered_shipment     orders/updated con fulfillment status=delivered
    cancelled_order        orders/cancelled
    refunded_order         refunds/create
    added_to_cart          carts/create / carts/update

  Internos (no-webhook):
    subscribed_to_email_marketing  → welcome flow
    subscribed_to_list             → added to segment
    unsubscribed_from_email_marketing → opt-out
    coupon_assigned                → coupon_sends insert
    coupon_used                    → orders/create con discount_codes

  Tracking web (JS pixel → /api/track):
    viewed_product         POST /api/track {event: viewed_product}
    active_on_site         POST /api/track {event: active_on_site}
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.config import settings
from app.models.contact import Contact

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_shopify(body: bytes, hmac_header: str) -> bool:
    secret = getattr(settings, "SHOPIFY_WEBHOOK_SECRET", "")
    if not secret:
        return True
    import base64
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), hmac_header)


def _log_event(cur, topic: str, shopify_id: str, email: str, payload: dict, now: datetime, trigger: str = None):
    cur.execute("""
        INSERT INTO shopify_events (topic, shopify_id, email, payload, automation_triggered, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (topic, shopify_id, email or None, json.dumps(payload), trigger, now))


@router.post("/webhooks")
async def shopify_webhook(
    request: Request,
    x_shopify_topic: str = Header(default="", alias="x-shopify-topic"),
    x_shopify_hmac_sha256: str = Header(default="", alias="x-shopify-hmac-sha256"),
):
    body = await request.body()
    if not _verify_shopify(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="HMAC inválido")
    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    topic = x_shopify_topic
    logger.info("Shopify webhook: %s", topic)

    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    email = (
        payload.get("email") or
        payload.get("customer", {}).get("email") or
        payload.get("contact_email") or ""
    ).lower().strip()

    # ── Cart events → Added to Cart ──────────────────────────────────────────
    if topic in ("carts/create", "carts/update"):
        cart_id = str(payload.get("id", payload.get("token", "")))
        _log_event(cur, topic, cart_id, email, payload, now, "added_to_cart")

    # ── Checkout → Checkout Started + future Abandoned Cart ──────────────────
    elif topic in ("checkouts/create", "checkouts/update"):
        token = str(payload.get("token") or payload.get("id") or "")
        total = float(payload.get("total_price") or payload.get("subtotal_price") or 0)
        items = payload.get("line_items", [])
        completed = bool(payload.get("completed_at") or payload.get("order_id"))

        cur.execute("""
            INSERT INTO shopify_checkouts (checkout_token, email, cart_total, line_items, recovered, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (checkout_token) DO UPDATE SET
                email = EXCLUDED.email, cart_total = EXCLUDED.cart_total,
                line_items = EXCLUDED.line_items,
                recovered = shopify_checkouts.recovered OR %s,
                updated_at = EXCLUDED.updated_at
        """, (token, email or None, total, json.dumps(items), completed, now, completed))

        _log_event(cur, topic, token, email, payload, now, "checkout_started")

    # ── Order created → Placed Order + Ordered Product + Coupon Used ─────────
    elif topic == "orders/create":
        order_id = str(payload.get("id", ""))
        total = float(payload.get("total_price", 0))
        items = payload.get("line_items", [])
        discount_codes = payload.get("discount_codes", [])

        # Mark checkout as recovered
        if email:
            cur.execute("""
                UPDATE shopify_checkouts SET recovered = TRUE, updated_at = %s
                WHERE email = %s AND recovered = FALSE
            """, (now, email))

        # Update contact stats
        if email:
            cur.execute("""
                UPDATE contacts SET
                    orders_count = orders_count + 1,
                    total_spent = COALESCE(total_spent, 0) + %s,
                    last_purchase = %s,
                    ticket_medio = (COALESCE(total_spent, 0) + %s) / NULLIF(orders_count + 1, 0),
                    updated_at = %s
                WHERE email = %s
            """, (total, now.date(), total, now, email))

        # placed_order trigger
        _log_event(cur, topic, order_id, email, payload, now, "placed_order")

        # ordered_product: one event per line item
        for item in items:
            _log_event(cur, "ordered_product", order_id,
                       email, {**payload, "_item": item}, now, "ordered_product")

        # coupon_used: if discount codes present
        for dc in discount_codes:
            code = dc.get("code", "")
            if code:
                # Mark coupon as used in our system
                cur.execute("""
                    UPDATE coupon_sends SET used = TRUE WHERE code = %s
                """, (code,))
                _log_event(cur, "coupon_used", order_id, email,
                           {**payload, "_coupon": code}, now, "coupon_used")

    # ── Order fulfilled ───────────────────────────────────────────────────────
    elif topic == "orders/fulfilled":
        order_id = str(payload.get("id", ""))
        fulfillments = payload.get("fulfillments", [])
        has_tracking = any(f.get("tracking_number") for f in fulfillments)
        _log_event(cur, topic, order_id, email, payload, now, "fulfilled_order")
        if has_tracking:
            _log_event(cur, "confirmed_shipment", order_id, email, payload, now, "confirmed_shipment")

    # ── Partial fulfillment ───────────────────────────────────────────────────
    elif topic == "orders/partially_fulfilled":
        order_id = str(payload.get("id", ""))
        _log_event(cur, topic, order_id, email, payload, now, "fulfilled_partial_order")

    # ── Order updated → check for delivered shipment ──────────────────────────
    elif topic == "orders/updated":
        order_id = str(payload.get("id", ""))
        for f in payload.get("fulfillments", []):
            if f.get("shipment_status") == "delivered":
                _log_event(cur, "delivered_shipment", order_id, email, payload, now, "delivered_shipment")
                break
        # marked_out_for_delivery
        for f in payload.get("fulfillments", []):
            if f.get("shipment_status") in ("out_for_delivery", "in_transit"):
                _log_event(cur, "marked_out_for_delivery", order_id, email, payload, now, "marked_out_for_delivery")
                break

    # ── Order cancelled ───────────────────────────────────────────────────────
    elif topic == "orders/cancelled":
        order_id = str(payload.get("id", ""))
        _log_event(cur, topic, order_id, email, payload, now, "cancelled_order")

    # ── Refund ────────────────────────────────────────────────────────────────
    elif topic == "refunds/create":
        order_id = str(payload.get("order_id", ""))
        _log_event(cur, topic, order_id, email, payload, now, "refunded_order")

    cur.close()
    conn.close()
    return {"ok": True, "topic": topic}


# ── Web tracking pixel ────────────────────────────────────────────────────────
class TrackEvent(BaseModel):
    event: str           # viewed_product | active_on_site | added_to_cart
    email: str = ""
    product_id: str = ""
    product_title: str = ""
    url: str = ""
    extra: dict = {}


@router.post("/track")
async def track_event(body: TrackEvent):
    """Recibe eventos de tracking desde el JS pixel en happylapiz.cl."""
    allowed = {"viewed_product", "active_on_site", "added_to_cart", "subscribed_to_back_in_stock"}
    if body.event not in allowed:
        raise HTTPException(status_code=400, detail=f"Evento no permitido: {body.event}")

    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    email = body.email.lower().strip() if body.email else ""

    # Update last_event_date if contact exists
    if email and body.event == "active_on_site":
        cur.execute("""
            UPDATE contacts SET ultima_visita_web = %s, updated_at = %s WHERE email = %s
        """, (now, now, email))

    _log_event(cur, body.event, body.product_id or "web", email,
               {"url": body.url, "product_title": body.product_title, **body.extra}, now, body.event)

    cur.close()
    conn.close()
    return {"ok": True}
