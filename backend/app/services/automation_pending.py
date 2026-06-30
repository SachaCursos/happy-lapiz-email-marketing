"""Build «próximos envíos» and «entrarán al flujo» views for automations."""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.automation import Automation, AutomationEnrollment
from app.services.birthday_triggers import iter_form_all, iter_gift_popup_all
from app.services.regalado_vars import get_regalado_field, parse_birthday_mmdd

CONTACTS_PER_STEP_LIMIT = 40
_WILL_ENTER_CACHE_TTL = 300  # seconds
_will_enter_cache: dict[int, tuple[float, dict | None]] = {}


def _is_ready(dt: datetime, now: datetime) -> bool:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt <= now


def _contact_row(enrollment: AutomationEnrollment, now: datetime) -> dict:
    extra = json.loads(enrollment.extra_vars_json or "{}")
    name = extra.get("nombre") or extra.get("first_name") or enrollment.contact_email
    detail = extra.get("cart_total") or extra.get("order_number") or ""
    if extra.get("nombre_regalado"):
        detail = str(extra["nombre_regalado"])
    if extra.get("first_product"):
        detail = f"{extra['first_product']} · {detail}" if detail else extra["first_product"]
    return {
        "email": enrollment.contact_email,
        "name": name,
        "detail": detail,
        "send_at": enrollment.next_send_at.isoformat(),
        "ready": _is_ready(enrollment.next_send_at, now),
        "step": enrollment.next_step,
    }


def build_pending_response(auto: Automation, session: Session) -> dict:
    """Active enrollments grouped by step, plus optional will_enter count."""
    now = datetime.now(timezone.utc)

    enrollments = session.exec(
        select(AutomationEnrollment)
        .where(AutomationEnrollment.automation_id == auto.id)
        .where(AutomationEnrollment.status == "active")
        .order_by(AutomationEnrollment.next_send_at.asc())
    ).all()

    by_step: dict[int, list[AutomationEnrollment]] = {}
    for e in enrollments:
        by_step.setdefault(e.next_step, []).append(e)

    steps_out = []
    total = 0
    for step_num in sorted(by_step):
        group = by_step[step_num]
        total += len(group)
        steps_out.append({
            "step": step_num,
            "count": len(group),
            "contacts": [_contact_row(e, now) for e in group[:CONTACTS_PER_STEP_LIMIT]],
        })

    will_enter = _cached_will_enter(auto, session)

    return {
        "count": total,
        "steps": steps_out,
        "will_enter": will_enter,
    }


def _cached_will_enter(auto: Automation, session: Session) -> dict | None:
    now = time.monotonic()
    cached = _will_enter_cache.get(auto.id)
    if cached and now - cached[0] < _WILL_ENTER_CACHE_TTL:
        return cached[1]
    result = _will_enter_count(auto, session)
    _will_enter_cache[auto.id] = (now, result)
    return result


def _birthday_form_sources(auto: Automation) -> tuple[str, int] | None:
    if auto.trigger_type != "birthday_reminder":
        return None
    config = auto.trigger_config or {}
    data_source = config.get("data_source") or ("form" if config.get("form_id") else "contacts")
    if data_source not in ("form", "gift_popup"):
        return None
    enroll_early_days = int(config.get("enroll_early_days", 30))
    return data_source, enroll_early_days


def _first_send_date(raw_date: str, days_before: int, today: date) -> tuple[date, date] | None:
    mmdd = parse_birthday_mmdd(raw_date)
    if not mmdd:
        return None
    month, day = map(int, mmdd.split("-"))
    bday = date(today.year, month, day)
    if bday < today:
        bday = date(today.year + 1, month, day)
    first_send = bday - timedelta(days=days_before)
    if first_send < today:
        bday = date(bday.year + 1, month, day)
        first_send = bday - timedelta(days=days_before)
    return bday, first_send


def _already_in_flow(session: Session, auto_id: int, trigger_key: str) -> bool:
    return session.exec(
        select(AutomationEnrollment).where(
            AutomationEnrollment.automation_id == auto_id,
            AutomationEnrollment.trigger_key == trigger_key,
        )
    ).first() is not None


def _will_enter_count(auto: Automation, session: Session) -> dict | None:
    src = _birthday_form_sources(auto)
    if not src:
        return None

    data_source, enroll_early_days = src
    config = auto.trigger_config or {}
    days_before = int(config.get("days_before", 30))
    birthday_field = config.get("birthday_field", "fecha_nacimiento")
    today = datetime.utcnow().date()

    if data_source == "gift_popup":
        candidates = iter_gift_popup_all(session)
    else:
        form_id = config.get("form_id")
        if not form_id:
            return {"count": 0}
        candidates = iter_form_all(session, int(form_id))

    count = 0
    dedupe: set[tuple] = set()

    for email, data, contact in candidates:
        raw_date = get_regalado_field(data, birthday_field)
        schedule = _first_send_date(raw_date, days_before, today) if raw_date else None
        if not schedule:
            continue

        bday, first_send = schedule
        days_until = (first_send - today).days
        if days_until <= enroll_early_days:
            continue

        owner_key = contact.id if contact else email
        trigger_key = f"birthday:{owner_key}:{birthday_field}:{bday.year}:{days_before}"
        dedupe_key = (email, birthday_field, bday.year, days_before)
        if dedupe_key in dedupe:
            continue
        dedupe.add(dedupe_key)

        if _already_in_flow(session, auto.id, trigger_key):
            continue

        count += 1

    return {"count": count}
