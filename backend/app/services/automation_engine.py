"""
Automation engine — runs every 60 seconds in a background thread.

Two-phase processing:
  Phase 1 (trigger detection): each handler detects qualifying events and creates
  AutomationEnrollment records. No emails sent here.
  Phase 2 (enrollment processing): _process_enrollments() sends emails for any
  enrollment whose next_send_at has passed, then advances to the next step or
  marks as completed/converted.
"""
import json
import logging
import random
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
from app.models.automation import Automation, AutomationEnrollment, AutomationRun
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


def _get_steps(auto: Automation) -> list:
    """Return the steps list for an automation, handling legacy single-step automations."""
    if auto.steps:
        return auto.steps
    # Backwards compat: convert legacy top-level template_id/subject to a single step
    if auto.template_id and auto.subject:
        config = auto.trigger_config or {}
        delay = float(config.get("delay_hours", 0))
        return [{"step": 1, "delay_hours": delay, "template_id": auto.template_id, "subject": auto.subject, "condition": None}]
    return []


def _already_sent_step(session: Session, automation_id: int, trigger_key: str, step_number: int) -> bool:
    """Check if a specific step was already successfully sent for this trigger_key."""
    return session.exec(
        select(AutomationRun).where(
            AutomationRun.automation_id == automation_id,
            AutomationRun.trigger_key == trigger_key,
            AutomationRun.step_number == step_number,
            AutomationRun.status == "sent",
        )
    ).first() is not None


def _enroll(
    session: Session,
    auto: Automation,
    contact_email: str,
    trigger_key: str,
    first_step_delay_hours: float,
    extra_vars: dict | None = None,
) -> bool:
    """Create an enrollment for a contact. Returns False if already enrolled."""
    existing = session.exec(
        select(AutomationEnrollment).where(
            AutomationEnrollment.automation_id == auto.id,
            AutomationEnrollment.trigger_key == trigger_key,
        )
    ).first()
    if existing:
        return False

    enrollment = AutomationEnrollment(
        automation_id=auto.id,
        contact_email=contact_email.lower(),
        trigger_key=trigger_key,
        enrolled_at=datetime.utcnow(),
        next_send_at=datetime.utcnow() + timedelta(hours=first_step_delay_hours),
        next_step=1,
        status="active",
        extra_vars_json=json.dumps(extra_vars or {}),
    )
    session.add(enrollment)
    session.commit()
    return True


def _passes_condition(condition: str | None, enrollment: AutomationEnrollment, session: Session) -> bool:
    """Check enrollment condition before sending a step. Returns True if the step should be sent."""
    if not condition or condition == "always":
        return True

    if condition == "not_purchased":
        # Skip if the contact made a purchase after enrollment
        result = session.execute(text("""
            SELECT 1 FROM shopify_orders
            WHERE LOWER(email) = LOWER(:email)
              AND created_at >= :since
            LIMIT 1
        """), {"email": enrollment.contact_email, "since": enrollment.enrolled_at}).fetchone()
        return result is None  # True = no purchase = still send

    if condition == "not_recovered":
        # For cart abandonment: skip if cart was recovered (purchased)
        extra = json.loads(enrollment.extra_vars_json or "{}")
        checkout_token = enrollment.trigger_key.replace("abandoned_cart:", "")
        result = session.execute(text("""
            SELECT 1 FROM carritos_abandonados
            WHERE checkout_token = :token AND recovered = TRUE
            LIMIT 1
        """), {"token": checkout_token}).fetchone()
        return result is None  # True = not recovered = still send

    return True


def _pick_variant(step: dict) -> tuple[dict, str | None]:
    """If the step has A/B variants, randomly pick one by weight. Returns (effective_step, variant_label)."""
    variants = step.get("variants")
    if not variants or len(variants) < 2:
        return step, None
    total_weight = sum(float(v.get("weight", 1)) for v in variants)
    rand = random.uniform(0, total_weight)
    cumulative = 0.0
    for v in variants:
        cumulative += float(v.get("weight", 1))
        if rand <= cumulative:
            return {**step, "template_id": v["template_id"], "subject": v["subject"]}, str(v["variant"])
    last = variants[-1]
    return {**step, "template_id": last["template_id"], "subject": last["subject"]}, str(last["variant"])


def _send_email_step(
    session: Session,
    auto: Automation,
    contact: Contact,
    trigger_key: str,
    step: dict,
    step_number: int,
    extra_vars: dict | None = None,
    variant: str | None = None,
) -> None:
    """Send the email for a specific step and record the run."""
    tpl = session.get(Template, int(step["template_id"]))
    if not tpl:
        logger.warning("Automation %d step %d: template %d not found", auto.id, step_number, step["template_id"])
        return

    run = AutomationRun(
        automation_id=auto.id,
        contact_id=contact.id,
        contact_email=contact.email,
        trigger_key=trigger_key,
        step_number=step_number,
        triggered_at=datetime.utcnow(),
        status="failed",
        variant_sent=variant,
    )
    try:
        # Generate dynamic coupon if automation has one configured
        coupon_code: str | None = None
        if auto.coupon_campaign_id:
            try:
                from app.routers.forms import _generate_dynamic_coupon
                coupon_code = _generate_dynamic_coupon(session, auto.coupon_campaign_id, contact.email)
            except Exception as exc:
                logger.warning("Coupon generation failed for %s: %s", contact.email, exc)

        nombre = _fmt_nombre(contact.name, contact.email)
        first_name = nombre.split()[0] if contact.name else ""
        vars_ = {
            "nombre": nombre,
            "first_name": first_name,
            "email": contact.email,
            "orders_count": contact.orders_count or 0,
            "ultima_visita": str(contact.ultima_visita) if contact.ultima_visita else "",
            "ticket_medio": contact.ticket_medio or 0,
            "total_spent": contact.total_spent or 0,
            "shipping_city": contact.shipping_city or "",
            "coupon_code": coupon_code or "",
            **(extra_vars or {}),
        }
        raw_html = tpl.html_content.replace("{% unsubscribe %}", unsub_url(contact.email))
        _env = Environment(undefined=ChainableUndefined)
        html = _inject_footer(_env.from_string(raw_html).render(**vars_), contact.email)

        resend.api_key = settings.RESEND_API_KEY
        result = resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [contact.email],
            "subject": str(step["subject"]),
            "html": html,
            "headers": _unsub_headers(contact.email),
        })
        resend_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        run.status = "sent"
        run.resend_id = resend_id
        run.executed_at = datetime.utcnow()
        logger.info("Automation %d step %d variant=%s sent to %s", auto.id, step_number, variant or "-", contact.email)
    except Exception as exc:
        run.error = str(exc)[:500]
        run.executed_at = datetime.utcnow()
        logger.error("Automation %d step %d failed for %s: %s", auto.id, step_number, contact.email, exc)

    session.add(run)
    session.commit()


# ── Enrollment processing ──────────────────────────────────────────────────────

def _process_enrollments(session: Session) -> None:
    """Phase 2: send emails for all ready enrollments and advance to next step."""
    now = datetime.utcnow()

    ready = session.exec(
        select(AutomationEnrollment)
        .where(AutomationEnrollment.status == "active")
        .where(AutomationEnrollment.next_send_at <= now)
    ).all()

    for enrollment in ready:
        auto = session.get(Automation, enrollment.automation_id)
        if not auto or auto.status != "active":
            enrollment.status = "cancelled"
            session.add(enrollment)
            session.commit()
            continue

        steps = _get_steps(auto)
        step_idx = enrollment.next_step - 1  # 0-indexed

        if step_idx >= len(steps):
            enrollment.status = "completed"
            session.add(enrollment)
            session.commit()
            continue

        step = steps[step_idx]

        # Check condition — if it fails, the contact converted/shouldn't receive
        if not _passes_condition(step.get("condition"), enrollment, session):
            enrollment.status = "converted"
            logger.info("Enrollment %d: condition '%s' failed, marking converted", enrollment.id, step.get("condition"))
            session.add(enrollment)
            session.commit()
            continue

        # Guard against double-send (e.g. if engine ran twice concurrently)
        if _already_sent_step(session, auto.id, enrollment.trigger_key, enrollment.next_step):
            logger.warning("Enrollment %d step %d already sent, advancing", enrollment.id, enrollment.next_step)
        else:
            contact = session.exec(
                select(Contact).where(Contact.email == enrollment.contact_email.lower())
            ).first()
            if not contact:
                extra = json.loads(enrollment.extra_vars_json or "{}")
                contact = Contact(
                    email=enrollment.contact_email,
                    name=extra.get("nombre", enrollment.contact_email),
                    opted_in=True,
                    orders_count=0,
                )

            extra_vars = json.loads(enrollment.extra_vars_json or "{}")
            effective_step, variant_label = _pick_variant(step)
            _send_email_step(session, auto, contact, enrollment.trigger_key, effective_step, enrollment.next_step, extra_vars, variant_label)

        # Advance to next step
        next_step_num = enrollment.next_step + 1
        if next_step_num > len(steps):
            enrollment.status = "completed"
        else:
            next_step = steps[next_step_num - 1]
            delay = float(next_step.get("delay_hours", 24))
            enrollment.next_step = next_step_num
            enrollment.next_send_at = now + timedelta(hours=delay)

        session.add(enrollment)
        session.commit()


# ── Trigger handlers (Phase 1 — enroll only, don't send) ─────────────────────

def _check_abandoned_booking(auto: Automation, session: Session) -> None:
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

    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", delay_minutes / 60))

    for row in rows:
        email = row.email.lower().strip()
        trigger_key = f"abandoned_booking:{row.id}"
        contact = session.exec(select(Contact).where(Contact.email == email)).first()
        if not contact or not contact.opted_in:
            continue

        fecha_str = str(row.fecha) if row.fecha else ""
        hora_str = str(row.hora)[:5] if row.hora else ""
        adultos = int(row.num_adultos or 0)
        ninos = int(row.num_ninos or 0)
        total = f"${int(row.ingreso_total):,}".replace(",", ".") if row.ingreso_total else ""
        personas_str = f"{adultos} adulto{'s' if adultos != 1 else ''}"
        if ninos:
            personas_str += f" + {ninos} niño{'s' if ninos != 1 else ''}"

        extra_vars = {
            "nombre": contact.name or email,
            "first_name": (contact.name or email).split()[0],
            "servicio": row.servicio or "tu experiencia",
            "fecha_reserva": fecha_str,
            "hora_reserva": hora_str,
            "personas": personas_str,
            "num_adultos": adultos,
            "num_ninos": ninos,
            "ingreso_total": total,
        }
        _enroll(session, auto, email, trigger_key, first_delay, extra_vars)


_BATCH_ORIGINS = {"Formulario T&C", "Sincronización Shopify", "importación CSV", ""}


def _check_welcome(auto: Automation, session: Session) -> None:
    config = auto.trigger_config or {}
    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", float(config.get("delay_hours", 0))))

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
        origin = (contact.origin_utm or "").strip()
        if origin in _BATCH_ORIGINS or origin.startswith("Formulario #"):
            continue
        trigger_key = f"welcome:{contact.id}"
        extra_vars = {"nombre": contact.name or contact.email, "first_name": (contact.name or contact.email).split()[0]}
        _enroll(session, auto, contact.email, trigger_key, first_delay, extra_vars)


def _check_post_visit(auto: Automation, session: Session) -> None:
    config = auto.trigger_config or {}
    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", 0))
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
        extra_vars = {"nombre": contact.name or contact.email, "first_name": (contact.name or contact.email).split()[0]}
        _enroll(session, auto, contact.email, trigger_key, first_delay, extra_vars)


def _check_reactivation(auto: Automation, session: Session) -> None:
    config = auto.trigger_config or {}
    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", 0))

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
        week = datetime.utcnow().strftime("%Y-W%W")
        trigger_key = f"reactivation:{contact.id}:{week}"
        extra_vars = {"nombre": contact.name or contact.email, "first_name": (contact.name or contact.email).split()[0]}
        _enroll(session, auto, contact.email, trigger_key, first_delay, extra_vars)


def _check_abandoned_cart(auto: Automation, session: Session) -> None:
    config = auto.trigger_config or {}
    lookback_hours = float(config.get("lookback_hours", 24))
    now = datetime.utcnow()
    cutoff_recent = now - timedelta(hours=lookback_hours)

    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", float(config.get("delay_hours", 1))))

    rows = session.execute(text("""
        SELECT id, checkout_token, email, first_name, last_name,
               subtotal_price, line_items, checkout_url
        FROM carritos_abandonados
        WHERE recovered = FALSE
          AND abandoned_email_sent = FALSE
          AND email IS NOT NULL AND email <> ''
          AND created_at >= :recent
        ORDER BY created_at ASC
        LIMIT 200
    """), {"recent": cutoff_recent}).fetchall()

    for row in rows:
        email = (row[2] or "").lower().strip()
        if not email:
            continue

        contact = session.exec(select(Contact).where(Contact.email == email)).first()
        if contact and contact.opted_in is False:
            continue

        # Atomically claim the cart to prevent concurrent duplicate enrollments
        claimed = session.execute(text("""
            UPDATE carritos_abandonados
            SET abandoned_email_sent = TRUE
            WHERE id = :id AND abandoned_email_sent = FALSE
        """), {"id": row[0]})
        session.commit()
        if claimed.rowcount == 0:
            continue

        trigger_key = f"abandoned_cart:{row[1]}"
        first_name = (row[3] or "").strip()
        last_name  = (row[4] or "").strip()
        full_name  = f"{first_name} {last_name}".strip() or email
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
        _enroll(session, auto, email, trigger_key, first_delay, extra_vars)


def _check_shopify_event(auto: Automation, session: Session, trigger_type: str) -> None:
    config = auto.trigger_config or {}
    lookback_hours = float(config.get("lookback_hours", 48))
    now = datetime.utcnow()
    cutoff_recent = now - timedelta(hours=lookback_hours)

    steps = _get_steps(auto)
    if not steps:
        return
    first_delay = float(steps[0].get("delay_hours", float(config.get("delay_hours", 0))))

    topic_map = {
        "placed_order":    "orders/create",
        "fulfilled_order": "orders/fulfilled",
        "cancelled_order": "orders/cancelled",
    }
    topic = topic_map.get(trigger_type)
    if not topic:
        return

    # For event-based triggers, only enroll events that haven't been enrolled yet
    rows = session.execute(text("""
        SELECT se.id, se.email, se.payload
        FROM shopify_events se
        WHERE se.topic = :topic
          AND se.processed = FALSE
          AND se.email IS NOT NULL
          AND se.created_at >= :recent
        ORDER BY se.created_at ASC LIMIT 200
    """), {"topic": topic, "recent": cutoff_recent}).fetchall()

    for row in rows:
        email = (row[1] or "").lower().strip()
        if not email:
            continue
        contact = session.exec(select(Contact).where(Contact.email == email)).first()
        if not contact or not contact.opted_in:
            continue
        trigger_key = f"{trigger_type}:{row[0]}"
        payload = row[2] or {}
        items = payload.get("line_items", [])
        first_item = items[0].get("title", "") if items else ""
        tracking = ""
        if trigger_type == "fulfilled_order":
            for f in payload.get("fulfillments", []):
                tracking = f.get("tracking_number", "") or ""
                break
        extra_vars = {
            "nombre": contact.name or email,
            "first_name": (contact.name or email).split()[0],
            "order_number": str(payload.get("order_number", "")),
            "order_total": f"${int(float(payload.get('total_price', 0))):,}".replace(",", "."),
            "first_product": first_item,
            "tracking_number": tracking,
        }
        enrolled = _enroll(session, auto, email, trigger_key, first_delay, extra_vars)
        if enrolled:
            session.execute(text("UPDATE shopify_events SET processed = TRUE WHERE id = :id"), {"id": row[0]})
            session.commit()


def _make_shopify_handler(trigger_type: str):
    def handler(auto, session): _check_shopify_event(auto, session, trigger_type)
    handler.__name__ = f"_check_{trigger_type}"
    return handler


HANDLERS = {
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
    "coupon_assigned":          _make_shopify_handler("coupon_assigned"),
    "coupon_used":              _make_shopify_handler("coupon_used"),
    "subscribed_to_back_in_stock": _make_shopify_handler("subscribed_to_back_in_stock"),
    "viewed_product":           _make_shopify_handler("viewed_product"),
    "active_on_site":           _make_shopify_handler("active_on_site"),
    "welcome":                  _check_welcome,
    "post_visit":               _check_post_visit,
    "reactivation":             _check_reactivation,
    "abandoned_booking":        _check_abandoned_booking,
}


def run_scheduled_campaigns() -> None:
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
            except Exception as exc:
                logger.exception("Scheduled campaign %d error: %s", campaign.id, exc)


def run_automations() -> None:
    with Session(db_engine) as session:
        automations = session.exec(
            select(Automation).where(Automation.status == "active")
        ).all()
        # Phase 1: detect triggers → enroll
        for auto in automations:
            handler = HANDLERS.get(auto.trigger_type)
            if handler:
                try:
                    handler(auto, session)
                except Exception as exc:
                    logger.exception("Automation %d (%s) trigger error: %s", auto.id, auto.trigger_type, exc)
        # Phase 2: process ready enrollments → send emails
        try:
            _process_enrollments(session)
        except Exception as exc:
            logger.exception("Enrollment processing error: %s", exc)


def start_scheduler() -> None:
    def loop():
        time.sleep(10)
        while True:
            try:
                run_automations()
                run_scheduled_campaigns()
                sync_contacts_from_shopify_orders()
            except Exception as exc:
                logger.exception("Automation scheduler error: %s", exc)
            time.sleep(60)

    t = threading.Thread(target=loop, daemon=True, name="automation-scheduler")
    t.start()
    logger.info("Automation scheduler started (interval: 1 min)")
