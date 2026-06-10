"""
Automation engine — runs every 15 minutes in a background thread.
Implements 4 trigger types: abandoned_booking, welcome, post_visit, reactivation.
"""
import logging
import threading
import time
from datetime import datetime, timedelta

import resend
from jinja2 import Environment, ChainableUndefined
from sqlalchemy import create_engine, text
from sqlmodel import Session, select

from app.core.config import settings
from app.services.sync_shopify_orders import sync_contacts_from_shopify_orders
from app.database import engine as db_engine
from app.models.automation import Automation, AutomationRun
from app.models.campaign import Campaign, CampaignSend
from app.models.contact import Contact
from app.models.segment import Segment
from app.models.template import Template
from app.services.email_sender import _inject_footer, _unsub_headers, send_campaign_sync, _fmt_nombre
from app.core.unsub_token import unsub_url
from app.services.segment_evaluator import evaluate_segment

logger = logging.getLogger(__name__)


def _source_engine():
    url = settings.HOTBOAT_DATABASE_URL or settings.DATABASE_URL
    return create_engine(url)


def _already_sent(session: Session, automation_id: int, trigger_key: str) -> bool:
    return session.exec(
        select(AutomationRun).where(
            AutomationRun.automation_id == automation_id,
            AutomationRun.trigger_key == trigger_key,
            AutomationRun.status == "sent",
        )
    ).first() is not None


def _send_email(
    session: Session,
    automation: Automation,
    contact: Contact,
    trigger_key: str,
    extra_vars: dict | None = None,
) -> None:
    tpl = session.get(Template, automation.template_id)
    if not tpl:
        logger.warning("Automation %d: template %d not found", automation.id, automation.template_id)
        return

    # Create run record upfront so any error is always persisted
    run = AutomationRun(
        automation_id=automation.id,
        contact_id=contact.id,
        contact_email=contact.email,
        trigger_key=trigger_key,
        triggered_at=datetime.utcnow(),
        status="failed",
    )
    try:
        vars_ = {
            "nombre": _fmt_nombre(contact.name, contact.email),
            "first_name": _fmt_nombre(contact.name, contact.email).split()[0] if contact.name else "",
            "email": contact.email,
            "orders_count": contact.orders_count or 0,
            "ultima_visita": str(contact.ultima_visita) if contact.ultima_visita else "",
            "ticket_medio": contact.ticket_medio or 0,
            "total_spent": contact.total_spent or 0,
            "shipping_city": contact.shipping_city or "",
            **(extra_vars or {}),
        }
        # Replace Klaviyo-style {% unsubscribe %} with actual link before Jinja2 renders
        raw_html = tpl.html_content.replace("{% unsubscribe %}", unsub_url(contact.email))
        _env = Environment(undefined=ChainableUndefined)
        html = _inject_footer(_env.from_string(raw_html).render(**vars_), contact.email)
        resend.api_key = settings.RESEND_API_KEY
        result = resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [contact.email],
            "subject": automation.subject,
            "html": html,
            "headers": _unsub_headers(contact.email),
        })
        resend_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        run.status = "sent"
        run.resend_id = resend_id
        run.executed_at = datetime.utcnow()
        logger.info("Automation %d sent to %s (key=%s)", automation.id, contact.email, trigger_key)
    except Exception as exc:
        run.error = str(exc)[:500]
        run.executed_at = datetime.utcnow()
        logger.error("Automation %d failed for %s: %s", automation.id, contact.email, exc)

    session.add(run)
    session.commit()


# ── Trigger handlers ──────────────────────────────────────────────────────────

def _check_abandoned_booking(auto: Automation, session: Session) -> None:
    """
    Fire when a booking has status='pending_payment' and paid_at IS NULL,
    created between delay_minutes and lookback_hours ago.
    Passes full booking details to the template as variables.
    """
    config = auto.trigger_config or {}
    delay_minutes = int(config.get("delay_minutes", 5))
    lookback_hours = int(config.get("lookback_hours", 24))

    now = datetime.utcnow()
    cutoff_old = now - timedelta(minutes=delay_minutes)
    cutoff_recent = now - timedelta(hours=lookback_hours)

    try:
        src = _source_engine()
        with src.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, email, nombre_cliente, servicio, fecha, hora,
                       num_adultos, num_ninos, ingreso_total, created_at
                FROM all_appointments
                WHERE status = 'pending_payment'
                  AND (paid_at IS NULL OR payment_status != 'completed')
                  AND created_at <= :cutoff_old
                  AND created_at >= :cutoff_recent
                  AND email IS NOT NULL AND email <> ''
                ORDER BY created_at DESC
                LIMIT 200
            """), {"cutoff_old": cutoff_old, "cutoff_recent": cutoff_recent}).fetchall()
    except Exception as exc:
        logger.error("Automation %d: cannot read source DB: %s", auto.id, exc)
        return

    for row in rows:
        email = row.email.lower().strip()
        # Dedup per booking row ID — one email per abandoned cart attempt
        trigger_key = f"abandoned:{row.id}"
        if _already_sent(session, auto.id, trigger_key):
            continue
        contact = session.exec(select(Contact).where(Contact.email == email)).first()
        if not contact or not contact.opted_in:
            continue

        # Format booking details for the template
        fecha_str = str(row.fecha) if row.fecha else ""
        hora_str = str(row.hora)[:5] if row.hora else ""
        adultos = int(row.num_adultos or 0)
        ninos = int(row.num_ninos or 0)
        total = f"${int(row.ingreso_total):,}".replace(",", ".") if row.ingreso_total else ""
        personas_str = f"{adultos} adulto{'s' if adultos != 1 else ''}"
        if ninos:
            personas_str += f" + {ninos} niño{'s' if ninos != 1 else ''}"

        extra_vars = {
            "servicio": row.servicio or "tu experiencia",
            "fecha_reserva": fecha_str,
            "hora_reserva": hora_str,
            "personas": personas_str,
            "num_adultos": adultos,
            "num_ninos": ninos,
            "ingreso_total": total,
        }
        _send_email(session, auto, contact, trigger_key, extra_vars=extra_vars)


_BATCH_ORIGINS = {"Formulario T&C", "Sincronización Shopify", "importación CSV", ""}


def _check_welcome(auto: Automation, session: Session) -> None:
    """Fire welcome email to contacts created organically (popup/form), not batch imports."""
    config = auto.trigger_config or {}
    delay_hours = float(config.get("delay_hours", 0))
    window_end = datetime.utcnow() - timedelta(hours=delay_hours)
    window_start = window_end - timedelta(minutes=20)

    contacts = session.exec(
        select(Contact).where(
            Contact.created_at >= window_start,
            Contact.created_at <= window_end,
            Contact.opted_in == True,
        )
    ).all()

    for contact in contacts:
        # Skip contacts imported in batch (TC form, sync, CSV) — only fire for
        # organic signups via the popup/embed form (origin_utm is a URL or form name)
        origin = (contact.origin_utm or "").strip()
        if origin in _BATCH_ORIGINS or origin.startswith("Formulario #"):
            continue
        trigger_key = f"welcome:{contact.id}"
        if _already_sent(session, auto.id, trigger_key):
            continue
        _send_email(session, auto, contact, trigger_key)


def _check_post_visit(auto: Automation, session: Session) -> None:
    """Fire N days after ultima_visita."""
    config = auto.trigger_config or {}
    delay_days = int(config.get("delay_days", 3))
    target_date = (datetime.utcnow() - timedelta(days=delay_days)).date()

    contacts = session.exec(
        select(Contact).where(
            Contact.ultima_visita == target_date,
            Contact.opted_in == True,
        )
    ).all()

    for contact in contacts:
        trigger_key = f"postvisit:{contact.id}:{target_date}"
        if _already_sent(session, auto.id, trigger_key):
            continue
        _send_email(session, auto, contact, trigger_key)


def _check_reactivation(auto: Automation, session: Session) -> None:
    """Fire when contact hasn't visited in N days, respecting a cooldown period."""
    config = auto.trigger_config or {}
    inactivity_days = int(config.get("inactivity_days", 90))
    cooldown_days = int(config.get("cooldown_days", 180))

    cutoff_date = (datetime.utcnow() - timedelta(days=inactivity_days)).date()
    cooldown_start = datetime.utcnow() - timedelta(days=cooldown_days)

    contacts = session.exec(
        select(Contact).where(
            Contact.ultima_visita != None,
            Contact.ultima_visita <= cutoff_date,
            Contact.opted_in == True,
        )
    ).all()

    for contact in contacts:
        recent_run = session.exec(
            select(AutomationRun).where(
                AutomationRun.automation_id == auto.id,
                AutomationRun.contact_id == contact.id,
                AutomationRun.triggered_at >= cooldown_start,
                AutomationRun.status == "sent",
            )
        ).first()
        if recent_run:
            continue
        # Weekly dedup to avoid burst on startup
        week = datetime.utcnow().strftime("%Y-W%W")
        trigger_key = f"reactivation:{contact.id}:{week}"
        if _already_sent(session, auto.id, trigger_key):
            continue
        _send_email(session, auto, contact, trigger_key)


def _check_abandoned_cart(auto: Automation, session: Session) -> None:
    """Carrito abandonado: checkout en carritos_abandonados hace más de delay_hours sin recuperar."""
    config = auto.trigger_config or {}
    delay_hours = float(config.get("delay_hours", 1))
    lookback_hours = float(config.get("lookback_hours", 24))
    now = datetime.utcnow()
    cutoff_old = now - timedelta(hours=delay_hours)
    cutoff_recent = now - timedelta(hours=lookback_hours)

    rows = session.execute(text("""
        SELECT id, checkout_token, email, first_name, last_name,
               subtotal_price, line_items, checkout_url
        FROM carritos_abandonados
        WHERE recovered = FALSE
          AND abandoned_email_sent = FALSE
          AND email IS NOT NULL AND email <> ''
          AND created_at <= :old
          AND created_at >= :recent
        ORDER BY created_at ASC
        LIMIT 200
    """), {"old": cutoff_old, "recent": cutoff_recent}).fetchall()

    for row in rows:
        email = (row[2] or "").lower().strip()
        if not email:
            continue
        trigger_key = f"abandoned_cart:{row[1]}"
        if _already_sent(session, auto.id, trigger_key):
            continue

        # Look up contact — if opted_out explicitly, skip; otherwise send
        contact = session.exec(select(Contact).where(Contact.email == email)).first()
        if contact and contact.opted_in is False:
            continue

        # Atomically claim the cart: only proceed if this process is the one that
        # flips abandoned_email_sent from FALSE → TRUE. Prevents duplicate sends
        # when two engine instances run concurrently (e.g. during a deploy).
        claimed = session.execute(text("""
            UPDATE carritos_abandonados
            SET abandoned_email_sent = TRUE
            WHERE id = :id AND abandoned_email_sent = FALSE
        """), {"id": row[0]})
        session.commit()
        if claimed.rowcount == 0:
            continue  # Another instance already claimed this cart

        # Use cart name if contact not registered
        first_name = (row[3] or "").strip()
        last_name  = (row[4] or "").strip()
        full_name  = f"{first_name} {last_name}".strip() or email

        if not contact:
            contact = Contact(
                email=email,
                name=full_name,
                opted_in=True,
                orders_count=0,
            )

        items = row[6] or []
        first_item = items[0].get("title", "") if items else ""
        subtotal = float(row[5] or 0)
        checkout_url = row[7] or "https://happylapiz.cl/cart"
        extra_vars = {
            "nombre":        full_name,
            "first_name":    first_name or full_name.split()[0],
            "cart_total":    f"${int(subtotal):,}".replace(",", "."),
            "first_product": first_item,
            "cart_url":      checkout_url,
            "event":         {"extra": {"checkout_url": checkout_url}},
        }
        _send_email(session, auto, contact, trigger_key, extra_vars=extra_vars)


def _check_shopify_event(auto: Automation, session: Session, trigger_type: str) -> None:
    """Dispara email cuando hay un evento de Shopify no procesado del tipo indicado."""
    config = auto.trigger_config or {}
    delay_hours = float(config.get("delay_hours", 0))
    lookback_hours = float(config.get("lookback_hours", 48))
    now = datetime.utcnow()
    cutoff_old = now - timedelta(hours=delay_hours)
    cutoff_recent = now - timedelta(hours=lookback_hours)

    # Map trigger_type back to shopify topic
    topic_map = {
        "placed_order":    "orders/create",
        "fulfilled_order": "orders/fulfilled",
        "cancelled_order": "orders/cancelled",
    }
    topic = topic_map.get(trigger_type)
    if not topic:
        return

    rows = session.execute(text("""
        SELECT id, email, payload FROM shopify_events
        WHERE topic = :topic
          AND processed = FALSE
          AND email IS NOT NULL
          AND created_at <= :old
          AND created_at >= :recent
        ORDER BY created_at ASC LIMIT 200
    """), {"topic": topic, "old": cutoff_old, "recent": cutoff_recent}).fetchall()

    for row in rows:
        email = (row[1] or "").lower().strip()
        if not email:
            continue
        trigger_key = f"{trigger_type}:{row[0]}"
        if _already_sent(session, auto.id, trigger_key):
            continue
        contact = session.exec(select(Contact).where(Contact.email == email)).first()
        if not contact or not contact.opted_in:
            continue
        payload = row[2] or {}
        items = payload.get("line_items", [])
        first_item = items[0].get("title", "") if items else ""
        tracking = ""
        if trigger_type == "fulfilled_order":
            for fulfillment in payload.get("fulfillments", []):
                tracking = fulfillment.get("tracking_number", "") or ""
                break
        extra_vars = {
            "order_number": str(payload.get("order_number", "")),
            "order_total": f"${int(float(payload.get('total_price', 0))):,}".replace(",", "."),
            "first_product": first_item,
            "tracking_number": tracking,
        }
        _send_email(session, auto, contact, trigger_key, extra_vars=extra_vars)
        session.execute(text("UPDATE shopify_events SET processed = TRUE WHERE id = :id"), {"id": row[0]})
        session.commit()


def _make_shopify_handler(trigger_type: str):
    def handler(auto, session): _check_shopify_event(auto, session, trigger_type)
    handler.__name__ = f"_check_{trigger_type}"
    return handler


HANDLERS = {
    # Shopify order lifecycle
    "checkout_started":         _make_shopify_handler("checkout_started"),
    "abandoned_cart":           _check_abandoned_cart,
    "placed_order":             _make_shopify_handler("placed_order"),
    "ordered_product":          _make_shopify_handler("ordered_product"),
    "fulfilled_order":          _make_shopify_handler("fulfilled_order"),
    "fulfilled_partial_order":  _make_shopify_handler("fulfilled_partial_order"),
    "confirmed_shipment":       _make_shopify_handler("confirmed_shipment"),
    "delivered_shipment":       _make_shopify_handler("delivered_shipment"),
    "marked_out_for_delivery":  _make_shopify_handler("marked_out_for_delivery"),
    "cancelled_order":          _make_shopify_handler("cancelled_order"),
    "refunded_order":           _make_shopify_handler("refunded_order"),
    "added_to_cart":            _make_shopify_handler("added_to_cart"),
    # Klaviyo-style internal
    "coupon_assigned":          _make_shopify_handler("coupon_assigned"),
    "coupon_used":              _make_shopify_handler("coupon_used"),
    "subscribed_to_back_in_stock": _make_shopify_handler("subscribed_to_back_in_stock"),
    # Web tracking
    "viewed_product":           _make_shopify_handler("viewed_product"),
    "active_on_site":           _make_shopify_handler("active_on_site"),
    # Internal
    "welcome":                  _check_welcome,
    "post_visit":               _check_post_visit,
    "reactivation":             _check_reactivation,
    "abandoned_booking":        _check_abandoned_booking,
}


def run_scheduled_campaigns() -> None:
    """Fire campaigns whose scheduled_at has passed and are still in 'scheduled' status."""
    with Session(db_engine) as session:
        now = datetime.utcnow()
        due = session.exec(
            select(Campaign).where(
                Campaign.status == "scheduled",
                Campaign.scheduled_at <= now,
            )
        ).all()
        for campaign in due:
            try:
                seg = session.get(Segment, campaign.segment_id)
                if not seg:
                    logger.warning("Scheduled campaign %d: segment %d not found", campaign.id, campaign.segment_id)
                    continue
                contacts = evaluate_segment(seg.conditions, session)
                if campaign.exclude_segment_ids:
                    excluded_ids: set = set()
                    for excl_id in campaign.exclude_segment_ids:
                        excl_seg = session.get(Segment, excl_id)
                        if excl_seg:
                            excluded_ids.update(ct.id for ct in evaluate_segment(excl_seg.conditions, session))
                    contacts = [ct for ct in contacts if ct.id not in excluded_ids]
                if not contacts:
                    logger.warning("Scheduled campaign %d: no contacts after exclusions", campaign.id)
                    continue
                already_sent = set(session.exec(
                    select(CampaignSend.contact_id).where(
                        CampaignSend.campaign_id == campaign.id,
                        CampaignSend.status != "failed",
                    )
                ).all())
                to_send = [c for c in contacts if c.id not in already_sent]
                if not to_send:
                    campaign.status = "sent"
                    session.add(campaign)
                    session.commit()
                    continue
                campaign.status = "sending"
                session.add(campaign)
                session.commit()
                contact_ids = [c.id for c in to_send]
                send_campaign_sync(campaign.id, contact_ids, len(contacts))
                logger.info("Scheduled campaign %d fired to %d contacts", campaign.id, len(contact_ids))
            except Exception as exc:
                logger.exception("Scheduled campaign %d error: %s", campaign.id, exc)


def run_automations() -> None:
    with Session(db_engine) as session:
        automations = session.exec(
            select(Automation).where(Automation.status == "active")
        ).all()
        for auto in automations:
            handler = HANDLERS.get(auto.trigger_type)
            if handler:
                try:
                    handler(auto, session)
                except Exception as exc:
                    logger.exception("Automation %d (%s) error: %s", auto.id, auto.trigger_type, exc)


def start_scheduler() -> None:
    def loop():
        # Small delay to let the app fully start
        time.sleep(10)
        while True:
            try:
                run_automations()
                run_scheduled_campaigns()
                sync_contacts_from_shopify_orders()
            except Exception as exc:
                logger.exception("Automation scheduler error: %s", exc)
            time.sleep(60)  # 1 minute

    t = threading.Thread(target=loop, daemon=True, name="automation-scheduler")
    t.start()
    logger.info("Automation scheduler started (interval: 1 min)")
