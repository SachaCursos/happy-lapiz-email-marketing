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
from app.models.evergreen import EvergreenCampaign, EvergreenSend
from app.models.segment import Segment
from app.models.template import Template
from app.services.email_sender import (
    RATE_DELAY,
    _inject_footer,
    _unsub_headers,
    build_contact_template_vars,
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


def _already_received_evergreen(
    session: Session,
    evergreen_id: int,
    contact_id: int,
    allow_resend: bool,
    resend_after_days: int | None,
) -> bool:
    sends = session.exec(
        select(EvergreenSend)
        .where(
            EvergreenSend.evergreen_id == evergreen_id,
            EvergreenSend.contact_id == contact_id,
            EvergreenSend.status != "failed",
        )
        .order_by(EvergreenSend.sent_at.desc())
    ).all()
    if not sends:
        return False
    if not allow_resend:
        return True
    if resend_after_days is None:
        return False
    last = sends[0].sent_at
    if not last:
        return True
    cutoff = datetime.utcnow() - timedelta(days=resend_after_days)
    return last > cutoff


def _send_evergreen_email(
    session: Session,
    eg: EvergreenCampaign,
    contact: Contact,
    tpl: Template,
) -> EvergreenSend | None:
    regalado = uses_regalado_vars(tpl.html_content, eg.subject)
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
        eg.subject,
        contact,
        vars_=vars_,
        preprocess_regalado=regalado,
    )

    send = EvergreenSend(
        evergreen_id=eg.id,
        contact_id=contact.id,
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
        logger.error("Evergreen %d send failed for %s: %s", eg.id, contact.email, exc)
        send.status = "failed"
        session.add(send)
        session.commit()
        return None


def run_evergreen_campaigns(force: bool = False) -> dict:
    """
    Daily job: for each inactive contact (>= min_days since any email),
    send the highest-priority eligible evergreen they haven't received.
    Runs at most once per UTC day unless force=True.
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

        template_ids = {c.template_id for c in campaigns}
        templates = {
            t.id: t
            for t in session.exec(select(Template).where(Template.id.in_(template_ids))).all()
        }

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

                    if _already_received_evergreen(
                        session,
                        eg.id,
                        contact.id,
                        eg.allow_resend,
                        eg.resend_after_days,
                    ):
                        continue

                    tpl = templates.get(eg.template_id)
                    if not tpl or not tpl.html_content:
                        continue

                    result = _send_evergreen_email(session, eg, contact, tpl)
                    if result and result.status == "sent":
                        stats["sent"] += 1
                        logger.info(
                            "Evergreen '%s' sent to %s",
                            eg.name,
                            contact.email,
                        )
                        time.sleep(RATE_DELAY)
                    break
        except Exception as exc:
            stats["errors"] += 1
            logger.exception("Evergreen dispatch error for %s: %s", contact.email, exc)

    _last_evergreen_run_date = today
    return stats
