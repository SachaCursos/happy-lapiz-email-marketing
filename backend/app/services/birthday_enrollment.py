"""Birthday automation enrollment — daily trigger + form-submit catch-up."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Iterator

from sqlmodel import Session, select

from app.models.automation import Automation, AutomationEnrollment
from app.models.contact import Contact
from app.services.birthday_config import (
    repair_birthday_automation_if_needed,
    resolve_birthday_data_source,
    resolve_enroll_early_days,
)
from app.services.birthday_triggers import (
    iter_contacts_on_mmdd,
    iter_form_all,
    iter_gift_flow_all,
)
from app.services.regalado_vars import (
    get_regalado_field,
    parse_birthday_mmdd,
    prepare_regalado_vars,
)

logger = logging.getLogger(__name__)

# How many days off the intended "X días antes" window is still acceptable.
BIRTHDAY_STEP_TOLERANCE_DAYS = 5

REGALADO_BIRTHDAY_SPECS: tuple[tuple[str, str, str], ...] = (
    ("fecha_nacimiento_regalado", "nombre_regalado", "relacion_regalado"),
    ("fecha_nacimiento_regalado2", "nombre_regalado2", "relacion_regalado2"),
)


def intended_days_before_for_step(
    auto: Automation,
    step_num: int,
    steps: list | None = None,
) -> int:
    """Days-before-birthday this step's email is supposed to represent.

    Step 1 → trigger_config.days_before (default 30).
    Later steps subtract the delay of each subsequent step (e.g. +15d → 15, +8d → 7).
    """
    config = auto.trigger_config or {}
    days_before = int(config.get("days_before", 30))
    if step_num <= 1:
        return days_before
    step_list = steps if steps is not None else (auto.steps or [])
    if isinstance(step_list, str):
        step_list = json.loads(step_list)
    delayed = 0.0
    for i, step in enumerate(step_list):
        if i == 0:
            continue  # step-1 delay is wait-to-first-send, not birthday offset
        if i + 1 > step_num:
            break
        delayed += float(step.get("delay_hours", 0) or 0) / 24.0
    return max(0, int(round(days_before - delayed)))


def parse_enrollment_birthday(extra_vars: dict | None) -> date | None:
    if not extra_vars:
        return None
    raw = (extra_vars.get("fecha_cumpleanos") or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def birthday_step_still_valid(
    auto: Automation,
    enrollment: AutomationEnrollment,
    *,
    as_of: date | None = None,
    steps: list | None = None,
    tolerance_days: int = BIRTHDAY_STEP_TOLERANCE_DAYS,
) -> tuple[bool, str]:
    """Return (ok, reason). Rejects steps whose send timing no longer matches the birthday.

    This catches enrollments that received a wrong step 1 and are queued for step 2/3
    when the birthday is already past or far from the email's 'faltan X días' claim.
    """
    as_of = as_of or datetime.utcnow().date()
    extra = {}
    if enrollment.extra_vars_json:
        try:
            extra = json.loads(enrollment.extra_vars_json)
        except Exception:
            extra = {}
    bday = parse_enrollment_birthday(extra)
    if not bday:
        return False, "missing_fecha_cumpleanos"

    days_until = (bday - as_of).days
    if days_until < 0:
        return False, f"birthday_passed:{bday}:days={days_until}"

    intended = intended_days_before_for_step(auto, enrollment.next_step, steps)
    drift = abs(days_until - intended)
    if drift > tolerance_days:
        return False, (
            f"timing_mismatch:step={enrollment.next_step}:intended={intended}:"
            f"actual={days_until}:drift={drift}"
        )
    return True, "ok"


def refresh_birthday_countdown(extra_vars: dict, *, as_of: date | None = None) -> dict:
    """Update dias_para_cumpleanos so the email body matches the real send day."""
    as_of = as_of or datetime.utcnow().date()
    out = dict(extra_vars or {})
    bday = parse_enrollment_birthday(out)
    if bday:
        out["dias_para_cumpleanos"] = max(0, (bday - as_of).days)
        out["fecha_cumpleanos"] = str(bday)
    return out


def first_send_date(raw_date: str, days_before: int, today: date) -> tuple[date, date] | None:
    """Return (birthday_this_cycle, first_send_date) or None."""
    mmdd = parse_birthday_mmdd(raw_date)
    if not mmdd:
        return None
    month, day = map(int, mmdd.split("-"))
    bday = date(today.year, month, day)
    if bday < today:
        bday = date(today.year + 1, month, day)
    first_send = bday - timedelta(days=days_before)
    return bday, first_send


def iter_regalado_birthdays(data: dict) -> Iterator[tuple[str, str, str, str, str]]:
    """Yield (date_field, raw_date, mmdd, name_field, relation_field) per regalado."""
    seen_mmdd: set[str] = set()
    for date_field, name_field, relation_field in REGALADO_BIRTHDAY_SPECS:
        raw = (data.get(date_field) or "").strip()
        if not raw:
            continue
        mmdd = parse_birthday_mmdd(raw)
        if not mmdd or mmdd in seen_mmdd:
            continue
        seen_mmdd.add(mmdd)
        yield date_field, raw, mmdd, name_field, relation_field


def _delay_hours_until(first_send: date, now: datetime) -> float:
    target = datetime(first_send.year, first_send.month, first_send.day)
    if target <= now:
        return 0.0
    return (target - now).total_seconds() / 3600.0


def _already_enrolled(session: Session, auto_id: int, trigger_key: str) -> bool:
    return session.exec(
        select(AutomationEnrollment).where(
            AutomationEnrollment.automation_id == auto_id,
            AutomationEnrollment.trigger_key == trigger_key,
        )
    ).first() is not None


def _build_extra_vars(
    contact: Contact | None,
    email: str,
    data: dict,
    *,
    name_field: str,
    relation_field: str,
    bday: date,
    days_before: int,
) -> dict:
    child_name = (data.get(name_field) or "").strip() or get_regalado_field(data, name_field)
    relation = (data.get(relation_field) or "").strip() or get_regalado_field(data, relation_field)
    contact_name = (contact.name if contact else None) or data.get("nombre") or email
    first = str(contact_name).split()[0]
    extra_vars = {
        **{k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)},
        "nombre": contact_name,
        "first_name": first,
        "dias_para_cumpleanos": max(0, (bday - datetime.utcnow().date()).days),
        "fecha_cumpleanos": str(bday),
    }
    if isinstance(data.get("regalados"), list):
        extra_vars["regalados"] = data["regalados"]
    prepare_regalado_vars(extra_vars)
    # Override display fields for this specific regalado (prepare_regalado_vars defaults to #1).
    if child_name:
        extra_vars["nombre_regalado"] = child_name
    if relation:
        extra_vars["relacion"] = relation
        extra_vars["relacion_regalado"] = relation
    return extra_vars


def try_enroll_birthday(
    session: Session,
    auto: Automation,
    email: str,
    contact: Contact | None,
    data: dict,
    *,
    days_before: int,
    enroll_early_days: int,
    today: date | None = None,
) -> int:
    """Enroll contact for each upcoming regalado birthday. Returns enrollments created."""
    now = datetime.utcnow()
    today = today or now.date()
    email_l = email.lower()
    owner_key = contact.id if contact else email_l
    enrolled = 0

    for date_field, raw_date, _mmdd, name_field, relation_field in iter_regalado_birthdays(data):
        schedule = first_send_date(raw_date, days_before, today)
        if not schedule:
            continue
        bday, first_send = schedule

        if bday < today:
            continue

        enroll_start = first_send - timedelta(days=enroll_early_days)
        if today < enroll_start or today > first_send:
            continue

        trigger_key = f"birthday:{owner_key}:{date_field}:{bday.year}:{days_before}"
        if _already_enrolled(session, auto.id, trigger_key):
            continue

        if enroll_early_days > 0 and today < first_send:
            delay_hours = _delay_hours_until(first_send, now)
        else:
            steps = auto.steps or []
            if isinstance(steps, str):
                steps = json.loads(steps)
            delay_hours = float(steps[0].get("delay_hours", 0)) if steps else 0.0

        extra_vars = _build_extra_vars(
            contact,
            email_l,
            data,
            name_field=name_field,
            relation_field=relation_field,
            bday=bday,
            days_before=days_before,
        )
        enrollment = AutomationEnrollment(
            automation_id=auto.id,
            contact_email=email_l,
            trigger_key=trigger_key,
            enrolled_at=now,
            next_send_at=now + timedelta(hours=delay_hours),
            next_step=1,
            status="active",
            extra_vars_json=json.dumps(extra_vars),
        )
        session.add(enrollment)
        session.commit()
        enrolled += 1
        logger.info(
            "Birthday auto %d enrolled %s (%s) first_send=%s delay=%.1fh",
            auto.id,
            email_l,
            date_field,
            first_send,
            delay_hours,
        )
    return enrolled


def enroll_birthday_for_email(session: Session, email: str) -> int:
    """Catch-up: run birthday enrollment for one email after form submit."""
    email_l = email.lower()
    autos = session.exec(
        select(Automation).where(
            Automation.trigger_type == "birthday_reminder",
            Automation.status == "active",
        )
    ).all()

    total = 0
    for auto in autos:
        repair_birthday_automation_if_needed(auto, session)
        config = auto.trigger_config or {}
        days_before = int(config.get("days_before", 30))
        data_source = resolve_birthday_data_source(auto)
        enroll_early_days = resolve_enroll_early_days(auto, data_source)

        contact = session.exec(select(Contact).where(Contact.email == email_l)).first()
        candidates: list[tuple[str, dict, Contact | None]] = []

        if data_source == "gift_popup":
            for em, data, c in iter_gift_flow_all(session):
                if em == email_l:
                    candidates.append((em, data, c))
        elif data_source == "form":
            form_id = config.get("form_id")
            if form_id:
                for em, data, c in iter_form_all(session, int(form_id)):
                    if em == email_l:
                        candidates.append((em, data, c))
        else:
            if contact:
                cf = contact.custom_fields or {}
                if isinstance(cf, str):
                    try:
                        cf = json.loads(cf)
                    except Exception:
                        cf = {}
                candidates.append((email_l, cf if isinstance(cf, dict) else {}, contact))

        for em, data, c in candidates:
            total += try_enroll_birthday(
                session,
                auto,
                em,
                c or contact,
                data,
                days_before=days_before,
                enroll_early_days=enroll_early_days,
            )
    return total


def backfill_birthday_enrollments(session: Session) -> dict:
    """Enroll every eligible form/gift contact into active birthday automations (idempotent)."""
    stats = {"automations": 0, "candidates": 0, "enrolled": 0, "skipped_opt_out": 0}
    autos = session.exec(
        select(Automation).where(
            Automation.trigger_type == "birthday_reminder",
            Automation.status == "active",
        )
    ).all()
    today = datetime.utcnow().date()

    for auto in autos:
        repair_birthday_automation_if_needed(auto, session)
        config = auto.trigger_config or {}
        days_before = int(config.get("days_before", 30))
        data_source = resolve_birthday_data_source(auto)
        enroll_early_days = resolve_enroll_early_days(auto, data_source)

        if data_source == "gift_popup":
            candidates = iter_gift_flow_all(session)
        elif data_source == "form":
            form_id = config.get("form_id")
            if not form_id:
                continue
            candidates = iter_form_all(session, int(form_id))
        else:
            continue

        stats["automations"] += 1
        seen: set[str] = set()
        for email, data, contact in candidates:
            em = email.lower()
            if em in seen:
                continue
            seen.add(em)
            if contact and not contact.opted_in:
                stats["skipped_opt_out"] += 1
                continue
            stats["candidates"] += 1
            stats["enrolled"] += try_enroll_birthday(
                session,
                auto,
                em,
                contact,
                data,
                days_before=days_before,
                enroll_early_days=enroll_early_days,
                today=today,
            )

    logger.info(
        "Birthday backfill: %d automations, %d candidates, %d new enrollments",
        stats["automations"],
        stats["candidates"],
        stats["enrolled"],
    )
    return stats


def run_birthday_reminder(auto: Automation, session: Session) -> None:
    """Daily scan: enroll contacts whose birthday reminder window is open."""
    repair_birthday_automation_if_needed(auto, session)
    config = auto.trigger_config or {}
    days_before = int(config.get("days_before", 30))
    data_source = resolve_birthday_data_source(auto)
    enroll_early_days = resolve_enroll_early_days(auto, data_source)
    today = datetime.utcnow().date()

    if data_source == "gift_popup":
        candidates = iter_gift_flow_all(session)
    elif data_source == "form":
        form_id = config.get("form_id")
        if not form_id:
            return
        candidates = iter_form_all(session, int(form_id))
    else:
        birthday_field = config.get("birthday_field", "fecha_nacimiento")
        enroll_when = days_before + enroll_early_days
        target = today + timedelta(days=enroll_when)
        candidates = iter_contacts_on_mmdd(session, target.month, target.day, birthday_field)

    seen: set[tuple[str, str]] = set()
    for email, data, contact in candidates:
        dedupe = (email.lower(), id(data))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        try_enroll_birthday(
            session,
            auto,
            email,
            contact,
            data,
            days_before=days_before,
            enroll_early_days=enroll_early_days,
            today=today,
        )
