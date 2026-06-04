"""
Recibe webhooks de Shopify y dispara automatizaciones de email.

Eventos manejados:
  checkouts/create  → guarda carrito pendiente
  checkouts/update  → actualiza carrito (puede marcar como recuperado)
  orders/create     → Placed Order → dispara automatización post-compra
  orders/fulfilled  → Fulfilled Order → dispara automatización envío
  orders/cancelled  → Cancelled Order
  orders/updated    → actualiza estado

El motor de automatización verifica cada 15 min los carritos abandonados (sin
orden asociada) y dispara el flujo correspondiente.
"""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.database import get_session
from app.models.contact import Contact

logger = logging.getLogger(__name__)
router = APIRouter()

# Map Shopify topic → our trigger name
TOPIC_TRIGGER_MAP = {
    "orders/create":    "placed_order",
    "orders/fulfilled": "fulfilled_order",
    "orders/cancelled": "cancelled_order",
}


def _verify_shopify(body: bytes, hmac_header: str) -> bool:
    secret = settings.SHOPIFY_WEBHOOK_SECRET if hasattr(settings, "SHOPIFY_WEBHOOK_SECRET") else ""
    if not secret:
        return True
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    import base64
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, hmac_header)


def _get_or_create_contact(session: Session, email: str, payload: dict) -> Contact | None:
    if not email:
        return None
    email = email.lower().strip()
    contact = session.exec(select(Contact).where(Contact.email == email)).first()
    if not contact:
        shipping = payload.get("shipping_address") or payload.get("customer", {}).get("default_address") or {}
        contact = Contact(
            email=email,
            name=(
                (payload.get("customer", {}).get("first_name", "") + " " +
                 payload.get("customer", {}).get("last_name", "")).strip() or None
            ),
            phone=payload.get("customer", {}).get("phone"),
            shipping_city=shipping.get("city"),
            shipping_province=shipping.get("province"),
            opted_in=True,
            opted_in_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(contact)
        session.flush()
    return contact


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

    # Use a plain psycopg2 connection for raw inserts (faster, no model mapping)
    import psycopg2
    conn = psycopg2.connect(settings.DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    email = (
        payload.get("email") or
        payload.get("customer", {}).get("email") or ""
    ).lower().strip()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # ── Checkout created/updated ─────────────────────────────────────────────
    if topic in ("checkouts/create", "checkouts/update"):
        token = payload.get("token") or payload.get("id") or ""
        total = payload.get("total_price") or payload.get("subtotal_price") or 0
        items = payload.get("line_items", [])

        # Check if this became an order (completed_at set)
        completed = bool(payload.get("completed_at") or payload.get("order_id"))

        cur.execute("""
            INSERT INTO shopify_checkouts (checkout_token, email, cart_total, line_items, recovered, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (checkout_token) DO UPDATE SET
                email = EXCLUDED.email,
                cart_total = EXCLUDED.cart_total,
                line_items = EXCLUDED.line_items,
                recovered = EXCLUDED.recovered OR %s,
                updated_at = EXCLUDED.updated_at
        """, (str(token), email or None, float(total), json.dumps(items), completed, now, completed))

        # Log event
        cur.execute("""
            INSERT INTO shopify_events (topic, shopify_id, email, payload, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (topic, str(token), email or None, json.dumps(payload), now))

    # ── Order created (Placed Order) ─────────────────────────────────────────
    elif topic == "orders/create":
        order_id = str(payload.get("id", ""))
        total = float(payload.get("total_price", 0))
        items = payload.get("line_items", [])

        # Mark any matching checkout as recovered
        if email:
            cur.execute("""
                UPDATE shopify_checkouts SET recovered = TRUE, updated_at = %s
                WHERE email = %s AND recovered = FALSE
            """, (now, email))

        cur.execute("""
            INSERT INTO shopify_events (topic, shopify_id, email, payload, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (topic, order_id, email or None, json.dumps(payload), now))

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

        _trigger_automation(cur, "placed_order", email, payload, now)

    # ── Order fulfilled ──────────────────────────────────────────────────────
    elif topic == "orders/fulfilled":
        order_id = str(payload.get("id", ""))
        cur.execute("""
            INSERT INTO shopify_events (topic, shopify_id, email, payload, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (topic, order_id, email or None, json.dumps(payload), now))
        _trigger_automation(cur, "fulfilled_order", email, payload, now)

    # ── Order cancelled ──────────────────────────────────────────────────────
    elif topic == "orders/cancelled":
        order_id = str(payload.get("id", ""))
        cur.execute("""
            INSERT INTO shopify_events (topic, shopify_id, email, payload, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (topic, order_id, email or None, json.dumps(payload), now))
        _trigger_automation(cur, "cancelled_order", email, payload, now)

    cur.close()
    conn.close()
    return {"ok": True, "topic": topic}


def _trigger_automation(cur, trigger_type: str, email: str, payload: dict, now: datetime):
    """Marca el evento para que el motor de automatización lo procese."""
    if not email:
        return
    cur.execute("""
        UPDATE shopify_events SET automation_triggered = %s
        WHERE topic = (
            SELECT topic FROM shopify_events WHERE email = %s ORDER BY created_at DESC LIMIT 1
        ) AND email = %s
    """, (trigger_type, email, email))
