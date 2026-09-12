"""Seed templates + automations for the on-site behavior funnel:
activo en el sitio → producto visto → producto agregado al carrito.

Mirrors birthday_automation_seed.py's shape. Templates hardcode happylapiz.cl
URLs, so — like the birthday templates — these are only seeded for Happy
Lápiz's shop, not auto-created for every tenant.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models.automation import Automation
from app.models.user import User
from app.services.favorite_blocks_seed import (
    ACTIVE_ON_SITE_NAME,
    ACTIVE_ON_SITE_PREVIEW,
    ACTIVE_ON_SITE_SUBJECT,
    CART_ADDED_1_NAME,
    CART_ADDED_1_PREVIEW,
    CART_ADDED_1_SUBJECT,
    CART_ADDED_2_NAME,
    CART_ADDED_2_PREVIEW,
    CART_ADDED_2_SUBJECT,
    VIEWED_PRODUCT_1_NAME,
    VIEWED_PRODUCT_1_PREVIEW,
    VIEWED_PRODUCT_1_SUBJECT,
    VIEWED_PRODUCT_2_NAME,
    VIEWED_PRODUCT_2_PREVIEW,
    VIEWED_PRODUCT_2_SUBJECT,
)
from app.services.template_compositions import upsert_block_template, resolve_composition

ACTIVE_ON_SITE_AUTOMATION_NAME = "Activo en el sitio"
VIEWED_PRODUCT_AUTOMATION_NAME = "Producto visto"
CART_ADDED_AUTOMATION_NAME = "Producto agregado al carrito"

# (composition key, template name, subject, preview)
TEMPLATE_SPECS = [
    ("activo_en_el_sitio", ACTIVE_ON_SITE_NAME, ACTIVE_ON_SITE_SUBJECT, ACTIVE_ON_SITE_PREVIEW),
    ("viewed_product_1", VIEWED_PRODUCT_1_NAME, VIEWED_PRODUCT_1_SUBJECT, VIEWED_PRODUCT_1_PREVIEW),
    ("viewed_product_2", VIEWED_PRODUCT_2_NAME, VIEWED_PRODUCT_2_SUBJECT, VIEWED_PRODUCT_2_PREVIEW),
    ("cart_added_1", CART_ADDED_1_NAME, CART_ADDED_1_SUBJECT, CART_ADDED_1_PREVIEW),
    ("cart_added_2", CART_ADDED_2_NAME, CART_ADDED_2_SUBJECT, CART_ADDED_2_PREVIEW),
]


def ensure_funnel_templates(session: Session, admin_id: int | None, shop_id: int, *, force: bool = False) -> dict[str, int]:
    ids: dict[str, int] = {}
    for composition, name, subject, preview in TEMPLATE_SPECS:
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


def _upsert_automation(
    session: Session,
    *,
    shop,
    admin_id: int | None,
    name: str,
    trigger_type: str,
    trigger_config: dict,
    steps: list[dict],
) -> Automation:
    existing = session.exec(
        select(Automation).where(Automation.name == name, Automation.shop_id == shop.id)
    ).first()
    now = datetime.utcnow()
    if existing:
        existing.trigger_type = trigger_type
        existing.trigger_config = trigger_config
        existing.steps = steps
        existing.template_id = steps[0]["template_id"]
        existing.subject = steps[0]["subject"]
        existing.updated_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    auto = Automation(
        name=name,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        steps=steps,
        template_id=steps[0]["template_id"],
        subject=steps[0]["subject"],
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


def ensure_funnel_automations(session: Session, admin_id: int | None, shop, *, force_templates: bool = False) -> list[Automation]:
    tpl_ids = ensure_funnel_templates(session, admin_id, shop.id, force=force_templates)

    active_on_site = _upsert_automation(
        session,
        shop=shop,
        admin_id=admin_id,
        name=ACTIVE_ON_SITE_AUTOMATION_NAME,
        trigger_type="active_on_site",
        trigger_config={"lookback_hours": 24},
        steps=[
            {
                "step": 1,
                "delay_hours": 3,
                "template_id": tpl_ids["activo_en_el_sitio"],
                "subject": ACTIVE_ON_SITE_SUBJECT,
                "condition": None,
            },
        ],
    )

    viewed_product = _upsert_automation(
        session,
        shop=shop,
        admin_id=admin_id,
        name=VIEWED_PRODUCT_AUTOMATION_NAME,
        trigger_type="viewed_product",
        trigger_config={"lookback_hours": 24},
        steps=[
            {
                "step": 1,
                "delay_hours": 2,
                "template_id": tpl_ids["viewed_product_1"],
                "subject": VIEWED_PRODUCT_1_SUBJECT,
                "condition": None,
            },
            {
                "step": 2,
                "delay_hours": 24,
                "template_id": tpl_ids["viewed_product_2"],
                "subject": VIEWED_PRODUCT_2_SUBJECT,
                "condition": "not_purchased",
            },
        ],
    )

    cart_added = _upsert_automation(
        session,
        shop=shop,
        admin_id=admin_id,
        name=CART_ADDED_AUTOMATION_NAME,
        trigger_type="added_to_cart",
        trigger_config={"lookback_hours": 48},
        steps=[
            {
                "step": 1,
                "delay_hours": 2,
                "template_id": tpl_ids["cart_added_1"],
                "subject": CART_ADDED_1_SUBJECT,
                "condition": None,
            },
            {
                "step": 2,
                "delay_hours": 24,
                "template_id": tpl_ids["cart_added_2"],
                "subject": CART_ADDED_2_SUBJECT,
                "condition": "not_purchased",
            },
        ],
    )

    return [active_on_site, viewed_product, cart_added]


def ensure_funnel_automations_setup(session: Session, shop=None, *, force_templates: bool = False) -> dict | None:
    """Seed the on-site funnel automations for Happy Lápiz (paused by default)."""
    from app.models.shop import Shop

    if shop is None:
        shop = session.exec(
            select(Shop).where(Shop.shopify_domain == "happy-lapiz.myshopify.com")
        ).first()
    if shop is None:
        return None

    admin = session.exec(select(User).where(User.shop_id == shop.id).order_by(User.id)).first()
    admin_id = admin.id if admin else None
    autos = ensure_funnel_automations(session, admin_id, shop, force_templates=force_templates)
    return {
        "automations": [
            {"id": a.id, "name": a.name, "status": a.status, "steps": len(a.steps or [])}
            for a in autos
        ],
    }
