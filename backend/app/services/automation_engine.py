"""
Automation engine — runs every 15 minutes in a background thread.
Implements 4 trigger types: abandoned_booking, welcome, post_visit, reactivation.
"""
import logging
import threading
import time
from datetime import datetime, timedelta

import resend
from jinja2 import Template as JTemplate
from sqlalchemy import create_engine, text
from sqlmodel import Session, select

from app.core.config import settings
from app.database import engine as db_engine
from app.models.automation import Automation, AutomationRun
from app.models.campaign import Campaign, CampaignSend
from app.models.contact import Contact
from app.models.segment import Segment
from app.models.template import Template
from app.services.email_sender import _inject_footer, _unsub_headers, send_campaign_sync, _fmt_nombre
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

    vars_ = {
        "nombre": _fmt_nombre(contact.name, contact.email),
        "email": contact.email,
        "veces_hotboat": contact.veces_hotboat,
        "ultima_visita": str(contact.ultima_visita) if contact.ultima_visita else "",
        "ticket_medio": contact.ticket_medio or 0,
        **(extra_vars or {}),
    }
    html = _inject_footer(JTemplate(tpl.html_content).render(**vars_), contact.email)
    resend.api_key = settings.RESEND_API_KEY

    run = AutomationRun(
        automation_id=automation.id,
        contact_id=contact.id,
        contact_email=contact.email,
        trigger_key=trigger_key,
        triggered_at=datetime.utcnow(),
    )
    try:
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
        run.status = "failed"
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
    delay_hours = int(config.get("delay_hours", 0))
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


HANDLERS = {
    "abandoned_booking": _check_abandoned_booking,
    "welcome": _check_welcome,
    "post_visit": _check_post_visit,
    "reactivation": _check_reactivation,
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
                if not contacts:
                    logger.warning("Scheduled campaign %d: no opted-in contacts", campaign.id)
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
            except Exception as exc:
                logger.exception("Automation scheduler error: %s", exc)
            time.sleep(60)  # 1 minute

    t = threading.Thread(target=loop, daemon=True, name="automation-scheduler")
    t.start()
    logger.info("Automation scheduler started (interval: 1 min)")
