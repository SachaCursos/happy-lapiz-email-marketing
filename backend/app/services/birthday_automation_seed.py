"""Seed templates, REGALO coupon campaign, and birthday reminder automation."""

from __future__ import annotations

import logging
import random
import string
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.models.automation import Automation
from app.models.user import User
from app.services.favorite_blocks_seed import (
    BIRTHDAY_7_NAME,
    BIRTHDAY_7_PREVIEW,
    BIRTHDAY_7_SUBJECT,
    BIRTHDAY_15_NAME,
    BIRTHDAY_15_PREVIEW,
    BIRTHDAY_15_SUBJECT,
    BIRTHDAY_30_NAME,
    BIRTHDAY_30_PREVIEW,
    BIRTHDAY_30_SUBJECT,
)
from app.services.template_compositions import upsert_block_template, resolve_composition

logger = logging.getLogger(__name__)

AUTOMATION_NAME = "Recordatorio de cumpleaños — REGALO 1+1"
COUPON_CAMPAIGN_NAME = "REGALO — Compra 1 regalo, regalo 1 producto"

BIRTHDAY_TEMPLATES = [
    ("birthday_30", BIRTHDAY_30_NAME, BIRTHDAY_30_SUBJECT, BIRTHDAY_30_PREVIEW),
    ("birthday_15", BIRTHDAY_15_NAME, BIRTHDAY_15_SUBJECT, BIRTHDAY_15_PREVIEW),
    ("birthday_7", BIRTHDAY_7_NAME, BIRTHDAY_7_SUBJECT, BIRTHDAY_7_PREVIEW),
]

# Step 2: 15 days after step 1 (30 → 15 days before birthday)
# Step 3: 8 days after step 2 (15 → 7 days before birthday)
STEP_DELAYS_HOURS = [0, 15 * 24, 8 * 24]


def _random_code(prefix: str = "REGALO", length: int = 6) -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{suffix}"


def _create_shopify_tracking_discount(name: str, seed_code: str) -> str | None:
    """Create a 0% Shopify discount group for code tracking (no price reduction)."""
    if not settings.SHOPIFY_ACCESS_TOKEN:
        return None
    domain = getattr(settings, "SHOPIFY_DOMAIN", None) or "happy-lapiz.myshopify.com"
    api = f"https://{domain}/admin/api/2024-10/graphql.json"
    mutation = """
    mutation discountCodeBasicCreate($basicCodeDiscount: DiscountCodeBasicInput!) {
      discountCodeBasicCreate(basicCodeDiscount: $basicCodeDiscount) {
        codeDiscountNode { id }
        userErrors { field message }
      }
    }"""
    variables = {
        "basicCodeDiscount": {
            "title": name,
            "code": seed_code,
            "startsAt": datetime.now(timezone.utc).isoformat(),
            "endsAt": "2099-12-31T23:59:59Z",
            "customerSelection": {"all": True},
            "customerGets": {"value": {"percentage": 0}, "items": {"all": True}},
            "appliesOncePerCustomer": False,
        }
    }
    try:
        resp = httpx.post(
            api,
            json={"query": mutation, "variables": variables},
            headers={
                "X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN,
                "Content-Type": "application/json",
            },
            timeout=12,
        )
        data = resp.json()
        node = data.get("data", {}).get("discountCodeBasicCreate", {}).get("codeDiscountNode")
        if node:
            return node["id"]
        errors = data.get("data", {}).get("discountCodeBasicCreate", {}).get("userErrors", [])
        if errors:
            logger.warning("Shopify REGALO discount errors: %s", errors)
    except Exception as exc:
        logger.warning("Shopify REGALO discount create failed: %s", exc)
    return None


def ensure_regalo_coupon_campaign(session: Session, admin_id: int | None) -> int:
    row = session.execute(
        text("SELECT id FROM coupon_campaigns WHERE name = :name"),
        {"name": COUPON_CAMPAIGN_NAME},
    ).fetchone()
    if row:
        return int(row[0])

    seed_code = _random_code("REGALO", 6)
    shopify_id = _create_shopify_tracking_discount(COUPON_CAMPAIGN_NAME, seed_code)

    result = session.execute(
        text("""
            INSERT INTO coupon_campaigns (
                name, shopify_discount_id, discount_type, discount_value,
                min_purchase, prefix, expires_at, applies_to, coupon_mode, static_code, created_by
            )
            VALUES (
                :name, :sid, 'percentage', 0,
                0, 'REGALO', '2099-12-31T23:59:59Z', 'all', 'dynamic', NULL, :uid
            )
            RETURNING id
        """),
        {"name": COUPON_CAMPAIGN_NAME, "sid": shopify_id, "uid": admin_id},
    ).fetchone()
    session.commit()
    return int(result[0])


def ensure_birthday_templates(session: Session, admin_id: int | None, *, force: bool = False) -> dict[str, int]:
    ids: dict[str, int] = {}
    for composition, name, subject, preview in BIRTHDAY_TEMPLATES:
        blocks, _html = resolve_composition(composition)
        tpl = upsert_block_template(
            session,
            name=name,
            subject=subject,
            preview=preview,
            blocks=blocks,
            created_by=admin_id,
            force=force,
        )
        ids[composition] = tpl.id
    session.commit()
    return ids


def ensure_birthday_automation(session: Session, admin_id: int | None, *, force: bool = False) -> Automation:
    tpl_ids = ensure_birthday_templates(session, admin_id, force=force)
    coupon_id = ensure_regalo_coupon_campaign(session, admin_id)

    steps = [
        {
            "step": 1,
            "delay_hours": STEP_DELAYS_HOURS[0],
            "template_id": tpl_ids["birthday_30"],
            "subject": BIRTHDAY_30_SUBJECT,
            "condition": None,
        },
        {
            "step": 2,
            "delay_hours": STEP_DELAYS_HOURS[1],
            "template_id": tpl_ids["birthday_15"],
            "subject": BIRTHDAY_15_SUBJECT,
            "condition": None,
        },
        {
            "step": 3,
            "delay_hours": STEP_DELAYS_HOURS[2],
            "template_id": tpl_ids["birthday_7"],
            "subject": BIRTHDAY_7_SUBJECT,
            "condition": None,
        },
    ]

    trigger_config = {
        "days_before": 30,
        "data_source": "gift_popup",
        "enroll_early_days": 30,
        "birthday_field": "fecha_nacimiento",
        "name_field": "nombre_regalado",
    }

    existing = session.exec(select(Automation).where(Automation.name == AUTOMATION_NAME)).first()
    now = datetime.utcnow()
    if existing:
        existing.trigger_type = "birthday_reminder"
        existing.trigger_config = trigger_config
        existing.steps = steps
        existing.template_id = tpl_ids["birthday_30"]
        existing.subject = BIRTHDAY_30_SUBJECT
        existing.coupon_campaign_id = coupon_id
        existing.updated_at = now
        if existing.status not in ("active", "paused"):
            existing.status = "paused"
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    auto = Automation(
        name=AUTOMATION_NAME,
        trigger_type="birthday_reminder",
        trigger_config=trigger_config,
        steps=steps,
        template_id=tpl_ids["birthday_30"],
        subject=BIRTHDAY_30_SUBJECT,
        coupon_campaign_id=coupon_id,
        status="paused",
        created_by=admin_id,
        created_at=now,
        updated_at=now,
    )
    session.add(auto)
    session.commit()
    session.refresh(auto)
    return auto


def ensure_birthday_reminder_setup(session: Session, *, force_templates: bool = False) -> dict:
    admin = session.exec(select(User).order_by(User.id)).first()
    admin_id = admin.id if admin else None
    auto = ensure_birthday_automation(session, admin_id, force=force_templates)
    return {
        "automation_id": auto.id,
        "automation_name": auto.name,
        "automation_status": auto.status,
        "coupon_campaign_id": auto.coupon_campaign_id,
        "steps": len(auto.steps or []),
    }
