"""
Recibe webhooks de Shopify y dispara automatizaciones de email.

Triggers cubiertos (espejo de Klaviyo):
  Desde Shopify:
    checkout_started       checkouts/create
    abandoned_cart         checkouts/create (sin orden tras X horas)
    placed_order            orders/create
    ordered_product         orders/create (por cada line_item)
    fulfilled_order         orders/fulfilled
    fulfilled_partial_order orders/partially_fulfilled
    confirmed_shipment      orders/fulfilled con tracking_number
    delivered_shipment      orders/updated con fulfillment status=delivered
    cancelled_order         orders/cancelled
    refunded_order          refunds/create
    added_to_cart           carts/create / carts/update

  Compliance (obligatorios para toda app de Shopify que accede a datos de clientes):
    customers/data_request  → export por mail al comerciante (shop_owner_email) + 200
    customers/redact        → log + 200
    shop/redact              → log + 200

  Internos (no-webhook):
    subscribed_to_email_marketing  → welcome flow
    subscribed_to_list             → added to segment
    unsubscribed_from_email_marketing → opt-out
    coupon_assigned                → coupon_sends insert
    coupon_used                    → orders/create con discount_codes

  Tracking web (JS pixel → /api/track):
    viewed_product         POST /api/track {event: viewed_product}
    active_on_site         POST /api/track {event: active_on_site}

Multi-tenant: cada webhook trae el header X-Shopify-Shop-Domain, que se usa
para resolver a qué Shop pertenece el evento y así popular shop_id en cada
tabla. Si el dominio no corresponde a una tienda instalada/activa, el evento
se descarta (devolviendo 200 igual, como exige Shopify para no reintentar).
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import get_current_shop
from app.models.shop import Shop
from app.services.email_provider import send_email
from app.services.shopify_client import shopify_headers, shopify_rest_url

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Shopify Products (for template editor product picker) ─────────────────────
@router.get("/products")
async def list_shopify_products(shop: Shop = Depends(get_current_shop)):
    """Devuelve los productos activos de Shopify para el editor de plantillas."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            shopify_rest_url(shop, "products.json"),
            params={"status": "active", "limit": 250, "fields": "id,title,handle,images,variants"},
            headers=shopify_headers(shop),
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
            "url": f"https://{shop.shopify_domain.replace('.myshopify.com', '')}.myshopify.com/products/{p.get('handle', '')}",
            "image_url": p["images"][0]["src"] if p.get("images") else "",
            "price": variant.get("price", ""),
            "compare_at_price": variant.get("compare_at_price") or "",
        })
    return result


@router.get("/collections")
async def list_shopify_collections(shop: Shop = Depends(get_current_shop)):
    """Devuelve todas las colecciones de Shopify para el configurador de cross-sell."""
    headers = shopify_headers(shop)
    smart, custom = [], []
    async with httpx.AsyncClient(timeout=15.0) as client:
        r1 = await client.get(
            shopify_rest_url(shop, "smart_collections.json"),
            params={"limit": 250, "fields": "id,title,handle"}, headers=headers,
        )
        if r1.status_code == 200:
            smart = r1.json().get("smart_collections", [])
        r2 = await client.get(
            shopify_rest_url(shop, "custom_collections.json"),
            params={"limit": 250, "fields": "id,title,handle"}, headers=headers,
        )
        if r2.status_code == 200:
            custom = r2.json().get("custom_collections", [])
    return sorted(
        [{"id": str(c["id"]), "title": c["title"]} for c in smart + custom],
        key=lambda c: c["title"],
    )


def _verify_shopify(body: bytes, hmac_header: str) -> bool:
    """Verifica la firma HMAC del webhook usando el client secret de la app.

    Shopify firma el body con el mismo secret usado en el OAuth flow
    (SHOPIFY_API_SECRET) — no hay un secret separado "de webhooks".
    """
    if not hmac_header or not settings.SHOPIFY_API_SECRET:
        return False
    import base64
    digest = hmac.new(settings.SHOPIFY_API_SECRET.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), hmac_header)


def _log_event(cur, topic: str, shopify_id: str, email: str, payload: dict, now: datetime, shop_id: int, trigger: str = None):
    cur.execute("""
        INSERT INTO shopify_events (shop_id, topic, shopify_id, email, payload, automation_triggered, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (shop_id, topic, shopify_id, email or None, json.dumps(payload), trigger, now))


def _resolve_shop_id(cur, shop_domain: str, require_active: bool = True) -> int | None:
    if not shop_domain:
        return None
    # Compliance topics (customers/redact, shop/redact) legitimately arrive for
    # a shop that's already 'uninstalled' — shop/redact by design fires ~48h
    # *after* app/uninstalled. Business topics still require 'active' so we
    # don't process new orders/checkouts for a shop that's no longer installed.
    if require_active:
        cur.execute("SELECT id FROM shops WHERE shopify_domain = %s AND status = 'active'", (shop_domain,))
    else:
        cur.execute("SELECT id FROM shops WHERE shopify_domain = %s", (shop_domain,))
    row = cur.fetchone()
    return row[0] if row else None


def _redact_customer(cur, shop_id: int, email: str) -> None:
    """Erase/anonymize one customer's PII within one shop (Shopify customers/redact).

    contacts is anonymized in place rather than deleted: campaign_sends and
    automation_runs hold a NOT NULL/optional FK to contacts.id and are legitimate
    business records (send/open/click history) worth keeping for reporting —
    deleting the contacts row would either violate that FK or destroy those
    records. Tables that store the raw email as free text with no FK pointing
    at them are wiped or anonymized directly.

    shopify_orders is intentionally left untouched: it's owned by the separate
    ETL pipeline (happylapiz-etl), not this app, and would just get overwritten
    on the next sync — redacting it needs an equivalent fix on that side.
    """
    if not shop_id or not email:
        return
    placeholder = f"redacted-{uuid.uuid4().hex[:12]}@redacted.invalid"

    cur.execute("""
        UPDATE contacts SET
            email = %s, name = NULL, phone = NULL,
            shipping_city = NULL, shipping_province = NULL,
            all_shipping_cities = NULL, custom_fields = NULL,
            klaviyo_properties = NULL, klaviyo_location = NULL,
            location = NULL
        WHERE shop_id = %s AND email = %s
    """, (placeholder, shop_id, email))

    cur.execute(
        "DELETE FROM automation_enrollments WHERE shop_id = %s AND contact_email = %s",
        (shop_id, email),
    )
    cur.execute(
        "UPDATE automation_runs SET contact_email = %s WHERE shop_id = %s AND contact_email = %s",
        (placeholder, shop_id, email),
    )
    cur.execute(
        "DELETE FROM form_submissions WHERE shop_id = %s AND email = %s",
        (shop_id, email),
    )
    cur.execute(
        "DELETE FROM gift_recipients WHERE shop_id = %s AND email = %s",
        (shop_id, email),
    )
    cur.execute(
        "DELETE FROM shopify_events WHERE shop_id = %s AND email = %s",
        (shop_id, email),
    )
    cur.execute(
        "UPDATE shopify_checkouts SET email = NULL WHERE shop_id = %s AND email = %s",
        (shop_id, email),
    )
    cur.execute("""
        UPDATE carritos_abandonados SET email = %s, first_name = NULL, last_name = NULL, phone = NULL
        WHERE shop_id = %s AND email = %s
    """, (placeholder, shop_id, email))
    cur.execute(
        "UPDATE coupon_sends SET contact_email = %s WHERE shop_id = %s AND contact_email = %s",
        (placeholder, shop_id, email),
    )


def _export_customer_data(cur, shop_id: int, email: str) -> dict:
    """Read one customer's data across the same tables _redact_customer touches
    (Shopify customers/data_request: deliver, don't erase)."""
    if not shop_id or not email:
        return {}

    def _rows(sql: str) -> list[dict]:
        cur.execute(sql, (shop_id, email))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    return {
        "contacts": _rows(
            "SELECT * FROM contacts WHERE shop_id = %s AND email = %s"
        ),
        "automation_enrollments": _rows(
            "SELECT * FROM automation_enrollments WHERE shop_id = %s AND contact_email = %s"
        ),
        "automation_runs": _rows(
            "SELECT * FROM automation_runs WHERE shop_id = %s AND contact_email = %s"
        ),
        "form_submissions": _rows(
            "SELECT * FROM form_submissions WHERE shop_id = %s AND email = %s"
        ),
        "gift_recipients": _rows(
            "SELECT * FROM gift_recipients WHERE shop_id = %s AND email = %s"
        ),
        "shopify_events": _rows(
            "SELECT * FROM shopify_events WHERE shop_id = %s AND email = %s"
        ),
        "shopify_checkouts": _rows(
            "SELECT * FROM shopify_checkouts WHERE shop_id = %s AND email = %s"
        ),
        "carritos_abandonados": _rows(
            "SELECT * FROM carritos_abandonados WHERE shop_id = %s AND email = %s"
        ),
        "coupon_sends": _rows(
            "SELECT * FROM coupon_sends WHERE shop_id = %s AND contact_email = %s"
        ),
    }


def _redact_shop_data(cur, shop_id: int) -> None:
    """Full tenant wipe for one shop (Shopify shop/redact, fired ~48h after
    app/uninstalled). Ordered to respect FK constraints — children before the
    parents they reference (campaign_sends before campaigns/contacts, everything
    that references users.created_by before users, etc).

    shopify_orders carries real PII (email, phone, name, shipping address) and
    is included below. Caveat: it's also written by a separate external ETL
    pipeline (happylapiz-etl) that syncs independently of this app's own OAuth
    token — if that pipeline still has its own Shopify access and keeps
    syncing this shop after uninstall, it can re-populate rows we just
    deleted. Stopping that requires a matching fix in the ETL pipeline itself
    (out of this repo); this deletion is still correct for everything this
    app's own webhook can control.
    shopify_order_line_items/shopify_customers (also ETL-owned) are left out:
    line items hold no personal data, and shopify_customers has no shop_id
    column at all, so there's no safe way to scope a delete to one tenant.
    """
    if not shop_id:
        return
    tables_in_fk_order = [
        "campaign_sends", "automation_runs", "automation_enrollments",
        "coupon_sends", "form_submissions",
        "campaigns", "automations", "signup_forms",
        "templates", "segments", "coupon_campaigns",
        "contacts", "gift_recipients",
        "shopify_events", "shopify_checkouts", "carritos_abandonados",
        "shopify_products", "shopify_orders",
        "users",
    ]
    for table in tables_in_fk_order:
        cur.execute(f"DELETE FROM {table} WHERE shop_id = %s", (shop_id,))
    # Blank the access token too — status is already 'uninstalled' from the
    # app/uninstalled handler, but this makes a stale/leaked credential unusable
    # even if the shops row itself is kept around for audit purposes.
    cur.execute(
        "UPDATE shops SET access_token_encrypted = '', shop_owner_email = NULL WHERE id = %s",
        (shop_id,),
    )


def _dispatch_webhook_topic(cur, topic: str, payload: dict, email: str, now: datetime, shop_id: int) -> None:
    """Runs the per-topic side effects for one webhook. Raises on failure (e.g. a
    raw table like shopify_checkouts/shopify_events not existing yet in this
    environment) — the caller is responsible for catching that and still
    returning 200 to Shopify so it doesn't retry-storm the endpoint.
    """
    # ── Cart events → Added to Cart ──────────────────────────────────────────
    if topic in ("carts/create", "carts/update"):
        cart_id = str(payload.get("id", payload.get("token", "")))
        _log_event(cur, topic, cart_id, email, payload, now, shop_id, "added_to_cart")

    # ── Checkout → Checkout Started + future Abandoned Cart ──────────────────
    elif topic in ("checkouts/create", "checkouts/update"):
        token = str(payload.get("token") or payload.get("id") or "")
        total = float(payload.get("total_price") or payload.get("subtotal_price") or 0)
        items = payload.get("line_items", [])
        completed = bool(payload.get("completed_at") or payload.get("order_id"))

        # Legacy table (used by automation engine)
        cur.execute("""
            INSERT INTO shopify_checkouts (shop_id, checkout_token, email, cart_total, line_items, recovered, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (checkout_token) DO UPDATE SET
                email = EXCLUDED.email, cart_total = EXCLUDED.cart_total,
                line_items = EXCLUDED.line_items,
                recovered = shopify_checkouts.recovered OR %s,
                updated_at = EXCLUDED.updated_at
        """, (shop_id, token, email or None, total, json.dumps(items), completed, now, completed))

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
                shop_id, checkout_token, email, first_name, last_name, phone,
                subtotal_price, total_price, total_discounts, currency,
                line_items,
                shipping_city, shipping_province, shipping_country,
                checkout_url, recovered,
                source_name, landing_site,
                shopify_created_at, shopify_updated_at,
                created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
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
            shop_id, token, email or None, first_name, last_name, phone,
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

        _log_event(cur, topic, token, email, payload, now, shop_id, "checkout_started")

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
                WHERE email = %s AND shop_id = %s AND recovered = FALSE
            """, (now, email, shop_id))
            cur.execute("""
                UPDATE carritos_abandonados
                SET recovered = TRUE, recovered_at = %s, updated_at = %s
                WHERE email = %s AND shop_id = %s AND recovered = FALSE
            """, (now, now, email, shop_id))

        # Update contact stats
        if email:
            cur.execute("""
                UPDATE contacts SET
                    orders_count = orders_count + 1,
                    total_spent = COALESCE(total_spent, 0) + %s,
                    last_purchase = %s,
                    ticket_medio = (COALESCE(total_spent, 0) + %s) / NULLIF(orders_count + 1, 0),
                    updated_at = %s
                WHERE email = %s AND shop_id = %s
            """, (total, now.date(), total, now, email, shop_id))

        # placed_order trigger
        _log_event(cur, topic, order_id, email, payload, now, shop_id, "placed_order")

        # ordered_product: one event per line item
        for item in items:
            _log_event(cur, "ordered_product", order_id,
                       email, {**payload, "_item": item}, now, shop_id, "ordered_product")

        # Sync to normalized order tables so the purchased_product segment filter works
        import json as _json
        cur.execute("""
            INSERT INTO shopify_orders (id, order_number, email, phone, financial_status, fulfillment_status,
                total_price, subtotal_price, total_tax, total_discounts, currency, created_at, customer_id,
                raw, synced_at, first_name, last_name, order_name, payment_gateway, line_items_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (id) DO NOTHING
        """, (
            order_id,
            payload.get("order_number"),
            email,
            payload.get("phone"),
            payload.get("financial_status"),
            payload.get("fulfillment_status"),
            float(payload.get("total_price") or 0),
            float(payload.get("subtotal_price") or 0),
            float(payload.get("total_tax") or 0),
            float(payload.get("total_discounts") or 0),
            payload.get("currency"),
            now,
            str(((payload.get("customer") or {}).get("id") or "")),
            _json.dumps(payload),
            now,
            (payload.get("billing_address") or {}).get("first_name") or (payload.get("customer") or {}).get("first_name"),
            (payload.get("billing_address") or {}).get("last_name") or (payload.get("customer") or {}).get("last_name"),
            payload.get("name"),
            payload.get("payment_gateway"),
            _json.dumps(items),
        ))
        order_number = payload.get("order_number")
        for item in items:
            cur.execute("""
                INSERT INTO shopify_order_line_items (id, order_id, order_number, product_id, variant_id,
                    title, variant_title, sku, quantity, price, total_discount, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                str(item.get("id", "")),
                order_id,
                order_number,
                str(item.get("product_id", "")),
                str(item.get("variant_id", "")),
                item.get("title", ""),
                item.get("variant_title", ""),
                item.get("sku", ""),
                item.get("quantity", 1),
                float(item.get("price") or 0),
                float(item.get("total_discount") or 0),
                now,
            ))

        # coupon_used: if discount codes present
        for dc in discount_codes:
            code = dc.get("code", "")
            if code:
                # Mark coupon as used in our system
                cur.execute("""
                    UPDATE coupon_sends SET used = TRUE WHERE code = %s AND shop_id = %s
                """, (code, shop_id))
                _log_event(cur, "coupon_used", order_id, email,
                           {**payload, "_coupon": code}, now, shop_id, "coupon_used")

    # ── Order fulfilled ───────────────────────────────────────────────────────
    elif topic == "orders/fulfilled":
        order_id = str(payload.get("id", ""))
        fulfillments = payload.get("fulfillments", [])
        has_tracking = any(f.get("tracking_number") for f in fulfillments)
        _log_event(cur, topic, order_id, email, payload, now, shop_id, "fulfilled_order")
        if has_tracking:
            _log_event(cur, "confirmed_shipment", order_id, email, payload, now, shop_id, "confirmed_shipment")

    # ── Partial fulfillment ───────────────────────────────────────────────────
    elif topic == "orders/partially_fulfilled":
        order_id = str(payload.get("id", ""))
        _log_event(cur, topic, order_id, email, payload, now, shop_id, "fulfilled_partial_order")

    # ── Order updated → check for delivered shipment ──────────────────────────
    elif topic == "orders/updated":
        order_id = str(payload.get("id", ""))
        for f in payload.get("fulfillments", []):
            if f.get("shipment_status") == "delivered":
                _log_event(cur, "delivered_shipment", order_id, email, payload, now, shop_id, "delivered_shipment")
                break
        # marked_out_for_delivery
        for f in payload.get("fulfillments", []):
            if f.get("shipment_status") in ("out_for_delivery", "in_transit"):
                _log_event(cur, "marked_out_for_delivery", order_id, email, payload, now, shop_id, "marked_out_for_delivery")
                break

    # ── Order cancelled ───────────────────────────────────────────────────────
    elif topic == "orders/cancelled":
        order_id = str(payload.get("id", ""))
        _log_event(cur, topic, order_id, email, payload, now, shop_id, "cancelled_order")

    # ── Refund ────────────────────────────────────────────────────────────────
    elif topic == "refunds/create":
        order_id = str(payload.get("order_id", ""))
        _log_event(cur, topic, order_id, email, payload, now, shop_id, "refunded_order")

    # ── App uninstalled ─────────────────────────────────────────────────────────
    elif topic == "app/uninstalled":
        cur.execute("""
            UPDATE shops SET status = 'uninstalled', uninstalled_at = %s, updated_at = %s
            WHERE id = %s
        """, (now, now, shop_id))
        logger.info("App desinstalada por la tienda id=%s", shop_id)

    # ── Compliance / GDPR (obligatorios) ─────────────────────────────────────────
    elif topic in ("customers/data_request", "customers/redact", "shop/redact"):
        subject_id = str(
            (payload.get("customer") or {}).get("id") or payload.get("shop_id") or ""
        )
        trigger = "gdpr_" + topic.replace("/", "_")

        if topic == "customers/redact":
            _redact_customer(cur, shop_id, email)
            # Log the fact that a redact happened, not the PII we just erased.
            _log_event(cur, topic, subject_id, None, {"redacted": True}, now, shop_id, trigger)
            logger.info("customers/redact: PII borrada/anonimizada (shop_id=%s)", shop_id)
        elif topic == "shop/redact":
            _redact_shop_data(cur, shop_id)
            _log_event(cur, topic, subject_id, None, {"redacted": True}, now, shop_id, trigger)
            logger.info("shop/redact: datos de shop_id=%s eliminados", shop_id)
        else:
            # customers/data_request exige *entregar* los datos al comerciante,
            # no borrarlos. Se junta lo que tenemos de ese email en esta tienda
            # y se manda por mail al dueño de la tienda (shop_owner_email).
            _log_event(cur, topic, subject_id, email, payload, now, shop_id, trigger)
            if email:
                export = _export_customer_data(cur, shop_id, email)
                cur.execute("SELECT name, shopify_domain, shop_owner_email FROM shops WHERE id = %s", (shop_id,))
                shop_row = cur.fetchone()
                owner_email = shop_row[2] if shop_row else None
                shop_label = (shop_row[0] or shop_row[1]) if shop_row else str(shop_id)
                if owner_email:
                    export_json = json.dumps(export, indent=2, ensure_ascii=False, default=str)
                    html = f"""
                    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:640px;margin:0 auto;">
                      <h2>Solicitud de datos de cliente (GDPR/CCPA)</h2>
                      <p>Shopify pidió, en nombre de un cliente de <strong>{shop_label}</strong>,
                         una copia de los datos que tenemos sobre <strong>{email}</strong>.</p>
                      <p>Adjuntamos el detalle en formato JSON abajo.</p>
                      <pre style="background:#f3f4f6;padding:12px;border-radius:8px;font-size:12px;
                         white-space:pre-wrap;word-break:break-word;">{export_json}</pre>
                    </div>
                    """
                    try:
                        send_email(
                            shop_id=shop_id,
                            from_email=settings.RESEND_FROM_EMAIL,
                            to=[owner_email],
                            subject=f"Solicitud de datos de cliente: {email}",
                            html=html,
                        )
                        logger.info("customers/data_request: export enviado a %s (shop_id=%s)", owner_email, shop_id)
                    except Exception:
                        logger.exception("customers/data_request: fallo el envío del export (shop_id=%s)", shop_id)
                else:
                    logger.warning(
                        "customers/data_request: shop_id=%s no tiene shop_owner_email, no se pudo enviar el export",
                        shop_id,
                    )
            else:
                logger.info("customers/data_request recibido sin email (shop_id=%s)", shop_id)


@router.post("/webhooks")
async def shopify_webhook(
    request: Request,
    x_shopify_topic: str = Header(default="", alias="x-shopify-topic"),
    x_shopify_hmac_sha256: str = Header(default="", alias="x-shopify-hmac-sha256"),
    x_shopify_shop_domain: str = Header(default="", alias="x-shopify-shop-domain"),
):
    body = await request.body()
    if not _verify_shopify(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="HMAC inválido")
    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    topic = x_shopify_topic
    logger.info("Shopify webhook: %s (shop=%s)", topic, x_shopify_shop_domain)

    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    compliance_topics = ("customers/data_request", "customers/redact", "shop/redact")
    shop_id = _resolve_shop_id(cur, x_shopify_shop_domain, require_active=topic not in compliance_topics)
    if shop_id is None:
        logger.warning("Webhook de tienda desconocida o desinstalada: %s", x_shopify_shop_domain)
        cur.close()
        conn.close()
        # Shopify exige 200 para no reintentar, aunque no procesemos el evento.
        return {"ok": True, "topic": topic, "skipped": "unknown_shop"}

    email = (
        payload.get("email") or
        payload.get("customer", {}).get("email") or
        payload.get("contact_email") or ""
    ).lower().strip()

    try:
        _dispatch_webhook_topic(cur, topic, payload, email, now, shop_id)
    except Exception:
        # No dejar que un error de procesamiento (ej. una tabla que todavía no
        # existe en este ambiente) tumbe la respuesta con un 500 — Shopify
        # reintenta webhooks fallidos agresivamente y puede llegar a desactivar
        # la suscripción. Se loguea y se responde 200 igual.
        logger.exception("Error procesando webhook %s (shop_id=%s)", topic, shop_id)
        cur.close()
        conn.close()
        return {"ok": True, "topic": topic, "skipped": "processing_error"}

    cur.close()
    conn.close()
    return {"ok": True, "topic": topic}


# ── Web tracking pixel ────────────────────────────────────────────────────────
class TrackEvent(BaseModel):
    event: str           # viewed_product | active_on_site | added_to_cart
    shop_domain: str = ""  # ej: "mi-tienda.myshopify.com" — lo setea el snippet embebido
    email: str = ""
    product_id: str = ""
    product_title: str = ""
    url: str = ""
    extra: dict = {}


@router.post("/track")
async def track_event(body: TrackEvent):
    """Recibe eventos de tracking desde el JS pixel embebido en la tienda (público,
    lo llaman visitantes anónimos del storefront — no requiere login)."""
    allowed = {"viewed_product", "active_on_site", "added_to_cart", "subscribed_to_back_in_stock"}
    if body.event not in allowed:
        raise HTTPException(status_code=400, detail=f"Evento no permitido: {body.event}")

    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    shop_id = _resolve_shop_id(cur, body.shop_domain)
    if shop_id is None:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Tienda desconocida")

    email = body.email.lower().strip() if body.email else ""

    # Update last_event_date if contact exists
    if email and body.event == "active_on_site":
        cur.execute("""
            UPDATE contacts SET ultima_visita_web = %s, updated_at = %s WHERE email = %s AND shop_id = %s
        """, (now, now, email, shop_id))

    _log_event(cur, body.event, body.product_id or "web", email,
               {"url": body.url, "product_title": body.product_title, **body.extra}, now, shop_id, body.event)

    cur.close()
    conn.close()
    return {"ok": True}
