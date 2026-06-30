"""Resolve birthday automation data source and defaults."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models.automation import Automation

_GIFT_NAME_MARKERS = ("regalo", "regalon", "regalón", "1+1", "gift")


def resolve_birthday_data_source(auto: Automation) -> str:
    """contacts | form | gift_popup"""
    config = auto.trigger_config or {}
    explicit = config.get("data_source")
    if explicit in ("contacts", "form", "gift_popup"):
        return explicit
    if config.get("form_id"):
        return "form"
    if _is_gift_regalo_flow(auto):
        return "gift_popup"
    return "contacts"


def resolve_enroll_early_days(auto: Automation, data_source: str) -> int:
    config = auto.trigger_config or {}
    if data_source not in ("form", "gift_popup"):
        return 0
    return int(config.get("enroll_early_days", 30))


def supports_will_enter_preview(auto: Automation) -> bool:
    if auto.trigger_type != "birthday_reminder":
        return False
    return resolve_birthday_data_source(auto) in ("form", "gift_popup")


def _is_gift_regalo_flow(auto: Automation) -> bool:
    if auto.coupon_campaign_id:
        return True
    name_l = (auto.name or "").lower()
    return any(m in name_l for m in _GIFT_NAME_MARKERS)


def repair_birthday_automation_if_needed(auto: Automation, session: Session) -> bool:
    """Patch a single REGALO automation missing gift_popup config (e.g. after rename)."""
    if auto.trigger_type != "birthday_reminder" or not _is_gift_regalo_flow(auto):
        return False
    config = dict(auto.trigger_config or {})
    changed = False
    if config.get("data_source") not in ("form", "gift_popup"):
        config["data_source"] = "gift_popup"
        changed = True
    if int(config.get("enroll_early_days") or 0) <= 0:
        config["enroll_early_days"] = 30
        changed = True
    if not config.get("days_before"):
        config["days_before"] = 30
        changed = True
    if not changed:
        return False
    auto.trigger_config = config
    auto.updated_at = datetime.utcnow()
    session.add(auto)
    session.commit()
    session.refresh(auto)
    return True


def repair_birthday_automation_configs(session: Session) -> int:
    """Patch renamed REGALO/cumpleaños automations missing gift_popup config."""
    autos = session.exec(
        select(Automation).where(Automation.trigger_type == "birthday_reminder")
    ).all()
    fixed = 0
    for auto in autos:
        if not _is_gift_regalo_flow(auto):
            continue
        if repair_birthday_automation_if_needed(auto, session):
            fixed += 1
    return fixed
