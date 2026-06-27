"""Product of the month — calendar helpers and inventory-based product rotation."""
from __future__ import annotations

import calendar
import json
import logging
from datetime import date, datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlmodel import Session

logger = logging.getLogger(__name__)

DEFAULT_TZ = "America/Santiago"
DEFAULT_SEND_HOUR = 10


def mondays_in_month(year: int, month: int) -> list[date]:
    """All Mondays in a calendar month."""
    _, last_day = calendar.monthrange(year, month)
    return [
        date(year, month, day)
        for day in range(1, last_day + 1)
        if date(year, month, day).weekday() == 0
    ]


def nth_monday(year: int, month: int, n: int) -> date | None:
    """1-based Monday index (1=first, 3=third, etc.)."""
    mondays = mondays_in_month(year, month)
    if n < 1 or n > len(mondays):
        return None
    return mondays[n - 1]


def last_monday(year: int, month: int) -> date | None:
    mondays = mondays_in_month(year, month)
    return mondays[-1] if mondays else None


def which_monday_occurrence(d: date) -> str | None:
    """Return 'first', 'third', or 'last' if d is that Monday occurrence, else None."""
    if d.weekday() != 0:
        return None
    mondays = mondays_in_month(d.year, d.month)
    if not mondays or d not in mondays:
        return None
    idx = mondays.index(d)
    if idx == 0:
        return "first"
    if idx == 2:
        return "third"
    if idx == len(mondays) - 1:
        return "last"
    return None


def today_in_tz(tz_name: str) -> date:
    return datetime.now(ZoneInfo(tz_name)).date()


def month_key_for(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def _local_send_utc(d: date, hour: int, tz_name: str) -> datetime:
    """Naive UTC datetime for sending at `hour` local time on date `d`."""
    local_dt = datetime.combine(d, time(hour, 0), tzinfo=ZoneInfo(tz_name))
    return local_dt.astimezone(timezone.utc).replace(tzinfo=None)


DEFAULT_MONDAY_SEQUENCE = ("first", "third", "last")
VALID_MONDAY_KEYS = frozenset({"first", "second", "third", "fourth", "last"})


def monday_for_occurrence(year: int, month: int, which: str) -> date | None:
    """Map 'first'|'second'|'third'|'fourth'|'last' to a date in the month."""
    if which not in VALID_MONDAY_KEYS:
        return None
    mondays = mondays_in_month(year, month)
    if not mondays:
        return None
    if which == "first":
        return mondays[0]
    if which == "second":
        return mondays[1] if len(mondays) >= 2 else None
    if which == "third":
        return mondays[2] if len(mondays) >= 3 else None
    if which == "fourth":
        return mondays[3] if len(mondays) >= 4 else None
    if which == "last":
        return mondays[-1]
    return None


def step_send_on_monday(step: dict, step_index: int) -> str:
    """Monday key for a step (0-based index)."""
    raw = step.get("send_on_monday")
    if raw in VALID_MONDAY_KEYS:
        return str(raw)
    if step_index < len(DEFAULT_MONDAY_SEQUENCE):
        return DEFAULT_MONDAY_SEQUENCE[step_index]
    return "last"


def is_enrollment_day(today: date, steps: list) -> bool:
    """True if today is the Monday configured for step 1."""
    if not steps or today.weekday() != 0:
        return False
    which = step_send_on_monday(steps[0], 0)
    target = monday_for_occurrence(today.year, today.month, which)
    return target == today


def build_step_schedules_from_steps(
    steps: list,
    year: int,
    month: int,
    tz_name: str = DEFAULT_TZ,
    send_hour: int = DEFAULT_SEND_HOUR,
) -> dict[str, str]:
    """UTC ISO timestamps for steps 2+ based on each step's send_on_monday."""
    out: dict[str, str] = {}
    for idx, step in enumerate(steps):
        step_num = idx + 1
        if step_num == 1:
            continue
        which = step_send_on_monday(step, idx)
        d = monday_for_occurrence(year, month, which)
        if d:
            out[str(step_num)] = _local_send_utc(d, send_hour, tz_name).isoformat()
    return out


def build_step_schedules(
    year: int,
    month: int,
    tz_name: str = DEFAULT_TZ,
    send_hour: int = DEFAULT_SEND_HOUR,
) -> dict[str, str]:
    """Legacy default: 3rd and last Monday for steps 2 and 3."""
    steps = [
        {"send_on_monday": "first"},
        {"send_on_monday": "third"},
        {"send_on_monday": "last"},
    ]
    return build_step_schedules_from_steps(steps, year, month, tz_name, send_hour)


def ensure_calendar_state_table(session: Session) -> None:
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS automation_calendar_state (
            automation_id INTEGER NOT NULL,
            month_key VARCHAR(7) NOT NULL,
            rotation_index INTEGER NOT NULL DEFAULT 0,
            product_shopify_id BIGINT,
            product_json JSONB,
            enrolled_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (automation_id, month_key)
        )
    """))
    session.commit()


def _product_row_to_dict(row: tuple) -> dict[str, Any]:
    shopify_id, title, handle, image_url, price, inventory = row
    price_val = float(price) if price else 0
    handle_str = handle or ""
    return {
        "shopify_id": int(shopify_id),
        "title": title or "",
        "handle": handle_str,
        "image_url": image_url or "",
        "price": f"${price_val:,.0f}".replace(",", ".") if price_val else "",
        "price_raw": price_val,
        "inventory_total": int(inventory or 0),
        "url": f"https://www.happylapiz.cl/products/{handle_str}",
    }


def _fetch_top_inventory_products(session: Session, pool_size: int) -> list[dict[str, Any]]:
    rows = session.execute(text("""
        SELECT shopify_id, title, handle, image_url, price,
               COALESCE(inventory_total, 0) AS inventory_total
        FROM shopify_products
        WHERE status = 'active'
          AND handle IS NOT NULL
          AND handle <> ''
        ORDER BY COALESCE(inventory_total, 0) DESC, title ASC
        LIMIT :limit
    """), {"limit": max(1, pool_size)}).fetchall()
    return [_product_row_to_dict(r) for r in rows]


def _get_global_rotation_index(session: Session, automation_id: int) -> int:
    row = session.execute(text("""
        SELECT rotation_index FROM automation_calendar_state
        WHERE automation_id = :aid
        ORDER BY month_key DESC
        LIMIT 1
    """), {"aid": automation_id}).fetchone()
    return int(row[0]) if row else 0


def get_or_create_monthly_product(
    session: Session,
    automation_id: int,
    month_key: str,
    pool_size: int = 5,
) -> dict[str, Any] | None:
    """Pick one featured product for the month (same for all 3 emails). Rotates through top-N inventory."""
    ensure_calendar_state_table(session)

    existing = session.execute(text("""
        SELECT product_json FROM automation_calendar_state
        WHERE automation_id = :aid AND month_key = :mk
    """), {"aid": automation_id, "mk": month_key}).fetchone()
    if existing and existing[0]:
        try:
            data = existing[0] if isinstance(existing[0], dict) else json.loads(existing[0])
            if isinstance(data, dict) and data.get("title"):
                return data
        except Exception:
            pass

    pool = _fetch_top_inventory_products(session, pool_size)
    if not pool:
        logger.warning("product_of_month: no products in shopify_products for automation %d", automation_id)
        return None

    prev_index = _get_global_rotation_index(session, automation_id)
    pick_index = prev_index % len(pool)
    product = pool[pick_index]
    next_index = (prev_index + 1) % max(len(pool), 1)

    session.execute(text("""
        INSERT INTO automation_calendar_state
            (automation_id, month_key, rotation_index, product_shopify_id, product_json)
        VALUES (:aid, :mk, :ridx, :sid, CAST(:pjson AS jsonb))
        ON CONFLICT (automation_id, month_key) DO UPDATE SET
            rotation_index = EXCLUDED.rotation_index,
            product_shopify_id = EXCLUDED.product_shopify_id,
            product_json = EXCLUDED.product_json
    """), {
        "aid": automation_id,
        "mk": month_key,
        "ridx": next_index,
        "sid": product["shopify_id"],
        "pjson": json.dumps(product, ensure_ascii=False),
    })
    session.commit()
    return product


def month_already_enrolled(session: Session, automation_id: int, month_key: str) -> bool:
    ensure_calendar_state_table(session)
    row = session.execute(text("""
        SELECT enrolled_at FROM automation_calendar_state
        WHERE automation_id = :aid AND month_key = :mk
    """), {"aid": automation_id, "mk": month_key}).fetchone()
    return bool(row and row[0])


def mark_month_enrolled(session: Session, automation_id: int, month_key: str) -> None:
    session.execute(text("""
        UPDATE automation_calendar_state
        SET enrolled_at = COALESCE(enrolled_at, NOW())
        WHERE automation_id = :aid AND month_key = :mk
    """), {"aid": automation_id, "mk": month_key})
    session.commit()
