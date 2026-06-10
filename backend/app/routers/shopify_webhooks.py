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

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.contact import Contact
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Shopify Products (for template editor product picker) ─────────────────────
@router.get("/products")
async def list_shopify_products(_: User = Depends(get_current_user)):
    """Devuelve los productos activos de Shopify para el editor de plantillas."""
    token = settings.SHOPIFY_ACCESS_TOKEN
    domain = settings.SHOPIFY_DOMAIN
    if not token:
        raise HTTPException(status_code=400, detail="SHOPIFY_ACCESS_TOKEN no configurado")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://{domain}/admin/api/2024-01/products.json",
            params={"status": "active", "limit": 250, "fields": "id,title,handle,images,variants"},
            headers={"X-Shopify-Access-Token": token},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Shopify API error: {resp.status_code}")

    products = resp.json().get("products", [])
    result = []
    for p in products:
        variant = p["variants"][0] if p.get("variants") else {}
        result.append({
            "id": str(p["id"]),
            "title": p["title"],
            "handle": p.get("handle", ""),
            "url": f"https://www.happylapiz.cl/products/{p.get('handle', '')}",
            "image_url": p["images"][0]["src"] if p.get("images") else "",
            "price": variant.get("price", ""),
            "compare_at_price": variant.get("compare_at_price") or "",
        })
    return result


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

        # Legacy table (used by automation engine)
        cur.execute("""
            INSERT INTO shopify_checkouts (checkout_token, email, cart_total, line_items, recovered, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (checkout_token) DO UPDATE SET
                email = EXCLUDED.email, cart_total = EXCLUDED.cart_total,
                line_items = EXCLUDED.line_items,
                recovered = shopify_checkouts.recovered OR %s,
                updated_at = EXCLUDED.updated_at
        """, (token, email or None, total, json.dumps(items), completed, now, completed))

        # Full abandoned cart table
        customer   = payload.get("customer") or {}
        ship_addr  = payload.get("shipping_address") or {}
        bill_addr  = payload.get("billing_address") or {}
        first_name = (customer.get("first_name") or bill_addr.get("first_name") or
                      ship_addr.get("first_name") or "")
        last_name  = (customer.get("last_name") or bill_addr.get("last_name") or
                      ship_addr.get("last_name") or "")
        phone      = (customer.get("phone") or bill_addr.get("phone") or
                      ship_addr.get("phone") or payload.get("phone") or "")

        line_items_clean = [
            {
                "product_id":    str(i.get("product_id", "")),
                "variant_id":    str(i.get("variant_id", "")),
                "title":         i.get("title", ""),
                "variant_title": i.get("variant_title", ""),
                "quantity":      i.get("quantity", 1),
                "price":         i.get("price", "0"),
                "sku":           i.get("sku", ""),
                "vendor":        i.get("vendor", ""),
            }
            for i in items
        ]

        shopify_created = payload.get("created_at")
        shopify_updated = payload.get("updated_at")

        cur.execute("""
            INSERT INTO carritos_abandonados (
                checkout_token, email, first_name, last_name, phone,
                subtotal_price, total_price, total_discounts, currency,
                line_items,
                shipping_city, shipping_province, shipping_country,
                checkout_url, recovered,
                source_name, landing_site,
                shopify_created_at, shopify_updated_at,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                NOW(), NOW()
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
                source_name        = COALESCE(EXCLUDED.source_name, carritos_abandonados.source_name),
                landing_site       = COALESCE(EXCLUDED.landing_site, carritos_abandonados.landing_site),
                shopify_updated_at = EXCLUDED.shopify_updated_at,
                updated_at         = NOW()
        """, (
            token, email or None, first_name, last_name, phone,
            float(payload.get("subtotal_price") or 0),
            total,
            float(payload.get("total_discounts") or 0),
            payload.get("currency", "CLP"),
            json.dumps(line_items_clean),
            ship_addr.get("city"),
            ship_addr.get("province"),
            ship_addr.get("country"),
            payload.get("abandoned_checkout_url"),
            completed,
            payload.get("source_name"),
            payload.get("landing_site"),
            shopify_created,
            shopify_updated,
        ))

        _log_event(cur, topic, token, email, payload, now, "checkout_started")

    # ── Order created → Placed Order + Ordered Product + Coupon Used ─────────
    elif topic == "orders/create":
        order_id = str(payload.get("id", ""))
        total = float(payload.get("total_price", 0))
        items = payload.get("line_items", [])
        discount_codes = payload.get("discount_codes", [])

        # Mark checkout as recovered in both tables
        if email:
            cur.execute("""
                UPDATE shopify_checkouts SET recovered = TRUE, updated_at = %s
                WHERE email = %s AND recovered = FALSE
            """, (now, email))
            cur.execute("""
                UPDATE carritos_abandonados
                SET recovered = TRUE, recovered_at = %s, updated_at = %s
                WHERE email = %s AND recovered = FALSE
            """, (now, now, email))

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
