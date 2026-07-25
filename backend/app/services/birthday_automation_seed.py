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


def _create_shopify_tracking_discount(name: str, seed_code: str, shop=None) -> str | None:
    """Create a $1 CLP Shopify discount group — marker that order should include a gift."""
    if shop is not None:
        from app.services.shopify_client import get_shopify_credentials
        token, domain = get_shopify_credentials(shop)
    else:
        # Legacy fallback for call sites without a shop yet resolved.
        token = settings.SHOPIFY_ACCESS_TOKEN
        domain = getattr(settings, "SHOPIFY_DOMAIN", None) or "happy-lapiz.myshopify.com"
    if not token:
        return None
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
            # $1 fixed — flags the order for a gift without a real promo
            "customerGets": {
                "value": {"discountAmount": {"amount": "1.0", "appliesOnEachItem": False}},
                "items": {"all": True},
            },
            "appliesOncePerCustomer": False,
            "combinesWith": {
                "orderDiscounts": True,
                "productDiscounts": True,
                "shippingDiscounts": True,
            },
        }
    }
    try:
        resp = httpx.post(
            api,
            json={"query": mutation, "variables": variables},
            headers={
                "X-Shopify-Access-Token": token,
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


def ensure_regalo_coupon_campaign(session: Session, admin_id: int | None, shop) -> int:
    row = session.execute(
        text("""
            SELECT id, shopify_discount_id FROM coupon_campaigns WHERE name = :name AND shop_id = :shop_id
        """),
        {"name": COUPON_CAMPAIGN_NAME, "shop_id": shop.id},
    ).fetchone()
    if row:
        campaign_id = int(row[0])
        # Repair: campaign existed without a Shopify parent discount
        if not row[1]:
            seed_code = _random_code("REGALO", 6)
            shopify_id = _create_shopify_tracking_discount(COUPON_CAMPAIGN_NAME, seed_code, shop)
            if shopify_id:
                session.execute(
                    text("""
                        UPDATE coupon_campaigns
                        SET shopify_discount_id = :sid,
                            discount_type = 'fixed',
                            discount_value = 1,
                            combines_with_order_discounts = TRUE,
                            combines_with_product_discounts = TRUE,
                            combines_with_shipping_discounts = TRUE
                        WHERE id = :id
                    """),
                    {"sid": shopify_id, "id": campaign_id},
                )
                session.commit()
                logger.info("Repaired REGALO coupon campaign %s → %s", campaign_id, shopify_id)
        return campaign_id

    seed_code = _random_code("REGALO", 6)
    shopify_id = _create_shopify_tracking_discount(COUPON_CAMPAIGN_NAME, seed_code, shop)

    result = session.execute(
        text("""
            INSERT INTO coupon_campaigns (
                name, shopify_discount_id, discount_type, discount_value,
                min_purchase, prefix, expires_at, applies_to, coupon_mode, static_code, created_by, shop_id,
                combines_with_order_discounts, combines_with_product_discounts, combines_with_shipping_discounts
            )
            VALUES (
                :name, :sid, 'fixed', 1,
                0, 'REGALO', '2099-12-31T23:59:59Z', 'all', 'dynamic', NULL, :uid, :shop_id,
                TRUE, TRUE, TRUE
            )
            RETURNING id
        """),
        {"name": COUPON_CAMPAIGN_NAME, "sid": shopify_id, "uid": admin_id, "shop_id": shop.id},
    ).fetchone()
    session.commit()
    return int(result[0])


def ensure_birthday_templates(session: Session, admin_id: int | None, shop_id: int, *, force: bool = False) -> dict[str, int]:
    ids: dict[str, int] = {}
    for composition, name, subject, preview in BIRTHDAY_TEMPLATES:
        blocks, _html = resolve_composition(composition)
        tpl = upsert_block_template(
            session,
            shop_id=shop_id,
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


def ensure_birthday_automation(session: Session, admin_id: int | None, shop, *, force: bool = False) -> Automation:
    tpl_ids = ensure_birthday_templates(session, admin_id, shop.id, force=force)
    coupon_id = ensure_regalo_coupon_campaign(session, admin_id, shop)

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

    existing = session.exec(
        select(Automation).where(Automation.name == AUTOMATION_NAME, Automation.shop_id == shop.id)
    ).first()
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
        shop_id=shop.id,
        created_at=now,
        updated_at=now,
    )
    session.add(auto)
    session.commit()
    session.refresh(auto)
    return auto


def ensure_birthday_reminder_setup(session: Session, shop=None, *, force_templates: bool = False) -> dict | None:
    """Seed the REGALO birthday automation for a shop.

    Runs at startup with no per-request context, so when `shop` isn't passed
    explicitly this resolves Happy Lápiz's shop by domain (the only shop this
    auto-seed subsystem is meant to run for today). Returns None (no-op) if
    that shop doesn't exist yet, e.g. on a fresh multi-tenant-only deploy.
    """
    from app.models.shop import Shop
    from app.services.birthday_config import repair_birthday_automation_configs

    if shop is None:
        shop = session.exec(
            select(Shop).where(Shop.shopify_domain == "happy-lapiz.myshopify.com")
        ).first()
    if shop is None:
        return None

    admin = session.exec(select(User).where(User.shop_id == shop.id).order_by(User.id)).first()
    admin_id = admin.id if admin else None
    auto = ensure_birthday_automation(session, admin_id, shop, force=force_templates)
    repaired = repair_birthday_automation_configs(session, shop.id)
    return {
        "automation_id": auto.id,
        "automation_name": auto.name,
        "automation_status": auto.status,
        "coupon_campaign_id": auto.coupon_campaign_id,
        "steps": len(auto.steps or []),
        "configs_repaired": repaired,
    }
