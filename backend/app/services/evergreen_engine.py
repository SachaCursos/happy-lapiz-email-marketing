"""Daily dispatch for evergreen (always-on) value campaigns."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import resend
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.database import engine
from app.models.contact import Contact
from app.models.evergreen import (
    EvergreenCampaign,
    EvergreenEnrollment,
    EvergreenSend,
    get_evergreen_steps,
)
from app.models.segment import Segment
from app.models.template import Template
from app.services.email_sender import (
    RATE_DELAY,
    _inject_footer,
    _unsub_headers,
    build_contact_template_vars,
    inject_preheader,
    render_html,
    render_template_text,
    uses_regalado_vars,
)
from app.services.segment_evaluator import evaluate_segment

logger = logging.getLogger(__name__)

_last_evergreen_run_date = None


def _contact_last_email_at(session: Session, contact_id: int, email: str) -> datetime | None:
    row = session.execute(text("""
        SELECT MAX(ts) FROM (
            SELECT sent_at AS ts
            FROM campaign_sends
            WHERE contact_id = :cid
              AND sent_at IS NOT NULL
              AND status NOT IN ('failed', 'queued')
            UNION ALL
            SELECT COALESCE(executed_at, triggered_at) AS ts
            FROM automation_runs
            WHERE status = 'sent'
              AND (contact_id = :cid OR LOWER(contact_email) = LOWER(:email))
            UNION ALL
            SELECT sent_at AS ts
            FROM evergreen_sends
            WHERE contact_id = :cid
              AND sent_at IS NOT NULL
              AND status NOT IN ('failed', 'queued')
        ) AS combined
    """), {"cid": contact_id, "email": email.lower()}).fetchone()
    if not row or not row[0]:
        return None
    return row[0]


def _recent_email_sends(session: Session, contact_id: int, email: str, limit: int) -> list[dict]:
    rows = session.execute(text("""
        SELECT ts, opened_at FROM (
            SELECT sent_at AS ts, opened_at
            FROM campaign_sends
            WHERE contact_id = :cid
              AND sent_at IS NOT NULL
              AND status NOT IN ('failed', 'queued')
            UNION ALL
            SELECT COALESCE(executed_at, triggered_at) AS ts, opened_at
            FROM automation_runs
            WHERE status = 'sent'
              AND (contact_id = :cid OR LOWER(contact_email) = LOWER(:email))
            UNION ALL
            SELECT sent_at AS ts, opened_at
            FROM evergreen_sends
            WHERE contact_id = :cid
              AND sent_at IS NOT NULL
              AND status NOT IN ('failed', 'queued')
        ) AS combined
        ORDER BY ts DESC
        LIMIT :lim
    """), {"cid": contact_id, "email": email.lower(), "lim": limit}).fetchall()
    return [{"ts": r[0], "opened_at": r[1]} for r in rows]


def _has_open_in_last_n(session: Session, contact_id: int, email: str, n: int) -> bool:
    recent = _recent_email_sends(session, contact_id, email, n)
    if not recent:
        return True
    return any(r["opened_at"] is not None for r in recent)


def _days_since_last_email(session: Session, contact_id: int, email: str) -> int | None:
    last = _contact_last_email_at(session, contact_id, email)
    if not last:
        return None
    if last.tzinfo:
        last = last.replace(tzinfo=None)
    delta = datetime.utcnow() - last
    return delta.days


def _in_segment(session: Session, contact: Contact, eg: EvergreenCampaign) -> bool:
    if eg.segment_id:
        seg = session.get(Segment, eg.segment_id)
        if not seg:
            return False
        ids = {c.id for c in evaluate_segment(seg.conditions, session)}
        if contact.id not in ids:
            return False

    if eg.exclude_segment_ids:
        for excl_id in eg.exclude_segment_ids:
            excl_seg = session.get(Segment, excl_id)
            if excl_seg:
                excl_ids = {c.id for c in evaluate_segment(excl_seg.conditions, session)}
                if contact.id in excl_ids:
                    return False
    return True


def _has_active_enrollment(session: Session, evergreen_id: int, contact_id: int) -> bool:
    row = session.exec(
        select(EvergreenEnrollment).where(
            EvergreenEnrollment.evergreen_id == evergreen_id,
            EvergreenEnrollment.contact_id == contact_id,
            EvergreenEnrollment.status == "active",
        )
    ).first()
    return row is not None


def _can_start_evergreen_cycle(
    session: Session,
    eg: EvergreenCampaign,
    contact_id: int,
) -> bool:
    if _has_active_enrollment(session, eg.id, contact_id):
        return False

    step1_sends = session.exec(
        select(EvergreenSend)
        .where(
            EvergreenSend.evergreen_id == eg.id,
            EvergreenSend.contact_id == contact_id,
            EvergreenSend.step_number == 1,
            EvergreenSend.status != "failed",
        )
        .order_by(EvergreenSend.sent_at.desc())
    ).all()
    if not step1_sends:
        return True
    if not eg.allow_resend:
        return False
    if eg.resend_after_days is None:
        return True
    last = step1_sends[0].sent_at
    if not last:
        return False
    cutoff = datetime.utcnow() - timedelta(days=eg.resend_after_days)
    return last <= cutoff


def _send_evergreen_step(
    session: Session,
    eg: EvergreenCampaign,
    contact: Contact,
    step_cfg: dict,
    *,
    step_number: int,
    enrollment_id: int | None = None,
) -> EvergreenSend | None:
    tpl = session.get(Template, int(step_cfg["template_id"]))
    if not tpl or not tpl.html_content:
        return None

    subject_raw = step_cfg["subject"]
    regalado = uses_regalado_vars(tpl.html_content, subject_raw)
    vars_ = build_contact_template_vars(
        contact,
        session=session,
        load_submission=regalado,
    )
    html = _inject_footer(
        render_html(
            tpl.html_content,
            contact,
            vars_=vars_,
            preprocess_regalado=regalado,
        ),
        contact.email,
    )
    subject = render_template_text(
        subject_raw,
        contact,
        vars_=vars_,
        preprocess_regalado=regalado,
    )
    preview_raw = step_cfg.get("preview_text") or ""
    if preview_raw:
        preview_text = render_template_text(
            str(preview_raw),
            contact,
            vars_=vars_,
            preprocess_regalado=regalado,
        )
        html = inject_preheader(html, preview_text)

    send = EvergreenSend(
        evergreen_id=eg.id,
        contact_id=contact.id,
        enrollment_id=enrollment_id,
        step_number=step_number,
        status="queued",
    )
    session.add(send)
    session.commit()
    session.refresh(send)

    resend.api_key = settings.RESEND_API_KEY
    try:
        result = resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [contact.email],
            "subject": subject,
            "html": html,
            "headers": _unsub_headers(contact.email),
            "tags": [
                {"name": "evergreen_id", "value": str(eg.id)},
                {"name": "contact_id", "value": str(contact.id)},
                {"name": "evergreen_step", "value": str(step_number)},
            ],
        })
        resend_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
        send.resend_id = resend_id
        send.status = "sent"
        send.sent_at = datetime.utcnow()
        session.add(send)
        session.commit()
        return send
    except Exception as exc:
        logger.error(
            "Evergreen %d step %d failed for %s: %s",
            eg.id, step_number, contact.email, exc,
        )
        send.status = "failed"
        session.add(send)
        session.commit()
        return None


def _start_evergreen_cycle(
    session: Session,
    eg: EvergreenCampaign,
    contact: Contact,
    steps: list[dict],
) -> bool:
    """Send step 1 and enroll for follow-ups if configured."""
    result = _send_evergreen_step(session, eg, contact, steps[0], step_number=1)
    if not result or result.status != "sent":
        return False

    if len(steps) > 1:
        delay = float(steps[1].get("delay_hours", 24))
        enrollment = EvergreenEnrollment(
            evergreen_id=eg.id,
            contact_id=contact.id,
            started_at=result.sent_at or datetime.utcnow(),
            next_step=2,
            next_send_at=(result.sent_at or datetime.utcnow()) + timedelta(hours=delay),
            status="active",
        )
        session.add(enrollment)
        session.commit()
    return True


def process_evergreen_followups() -> dict:
    """Send step 2/3 follow-ups when their delay since step 1 has elapsed."""
    stats = {"checked": 0, "sent": 0, "errors": 0}
    now = datetime.utcnow()

    with Session(engine) as session:
        due = session.exec(
            select(EvergreenEnrollment)
            .where(
                EvergreenEnrollment.status == "active",
                EvergreenEnrollment.next_send_at <= now,
            )
        ).all()
        if not due:
            return stats

        eg_ids = {e.evergreen_id for e in due}
        campaigns = {
            c.id: c
            for c in session.exec(
                select(EvergreenCampaign).where(EvergreenCampaign.id.in_(eg_ids))
            ).all()
        }

    for enrollment in due:
        stats["checked"] += 1
        try:
            with Session(engine) as session:
                eg = campaigns.get(enrollment.evergreen_id)
                if not eg or eg.status != "active":
                    en = session.get(EvergreenEnrollment, enrollment.id)
                    if en:
                        en.status = "completed"
                        session.add(en)
                        session.commit()
                    continue

                contact = session.get(Contact, enrollment.contact_id)
                if not contact or not contact.opted_in:
                    en = session.get(EvergreenEnrollment, enrollment.id)
                    if en:
                        en.status = "completed"
                        session.add(en)
                        session.commit()
                    continue

                steps = get_evergreen_steps(eg)
                step_idx = enrollment.next_step - 1
                if step_idx >= len(steps):
                    en = session.get(EvergreenEnrollment, enrollment.id)
                    if en:
                        en.status = "completed"
                        session.add(en)
                        session.commit()
                    continue

                step_cfg = steps[step_idx]
                result = _send_evergreen_step(
                    session,
                    eg,
                    contact,
                    step_cfg,
                    step_number=enrollment.next_step,
                    enrollment_id=enrollment.id,
                )
                if not result or result.status != "sent":
                    continue

                stats["sent"] += 1
                en = session.get(EvergreenEnrollment, enrollment.id)
                if not en:
                    continue

                next_step_num = enrollment.next_step + 1
                if next_step_num <= len(steps):
                    next_cfg = steps[next_step_num - 1]
                    delay_from_start = float(next_cfg.get("delay_hours", 0))
                    en.next_step = next_step_num
                    en.next_send_at = en.started_at + timedelta(hours=delay_from_start)
                else:
                    en.status = "completed"
                session.add(en)
                session.commit()
                time.sleep(RATE_DELAY)
        except Exception as exc:
            stats["errors"] += 1
            logger.exception("Evergreen follow-up error enrollment %d: %s", enrollment.id, exc)

    return stats


def run_evergreen_campaigns(force: bool = False) -> dict:
    """
    Daily job: for each inactive contact (>= min_days since any email),
    send step 1 of the highest-priority eligible evergreen they haven't started.
    """
    global _last_evergreen_run_date
    today = datetime.utcnow().date()
    if not force and _last_evergreen_run_date == today:
        return {"skipped": True, "contacts_checked": 0, "sent": 0, "errors": 0}

    stats = {"contacts_checked": 0, "sent": 0, "errors": 0}

    with Session(engine) as session:
        campaigns = session.exec(
            select(EvergreenCampaign)
            .where(EvergreenCampaign.status == "active")
            .order_by(EvergreenCampaign.sort_order.asc(), EvergreenCampaign.id.asc())
        ).all()
        if not campaigns:
            _last_evergreen_run_date = today
            return stats

        contacts = session.exec(
            select(Contact).where(Contact.opted_in == True)  # noqa: E712
        ).all()

    for contact in contacts:
        stats["contacts_checked"] += 1
        try:
            with Session(engine) as session:
                days_idle = _days_since_last_email(session, contact.id, contact.email)

                for eg in campaigns:
                    if days_idle is not None and days_idle < eg.min_days_inactive:
                        continue

                    if not _in_segment(session, contact, eg):
                        continue

                    if not _has_open_in_last_n(
                        session, contact.id, contact.email, eg.require_open_in_last_n
                    ):
                        continue

                    if not _can_start_evergreen_cycle(session, eg, contact.id):
                        continue

                    steps = get_evergreen_steps(eg)
                    if _start_evergreen_cycle(session, eg, contact, steps):
                        stats["sent"] += 1
                        logger.info(
                            "Evergreen '%s' step 1 sent to %s (%d steps)",
                            eg.name,
                            contact.email,
                            len(steps),
                        )
                        time.sleep(RATE_DELAY)
                    break
        except Exception as exc:
            stats["errors"] += 1
            logger.exception("Evergreen dispatch error for %s: %s", contact.email, exc)

    _last_evergreen_run_date = today
    return stats
