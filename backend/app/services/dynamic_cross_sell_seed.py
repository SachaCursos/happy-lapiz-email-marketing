"""Seed dynamic sequential cross-sell automation (age + bestsellers + free shipping)."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.automation import Automation
from app.models.user import User
from app.services.template_block_compiler import make_block
from app.services.template_compositions import upsert_block_template

logger = logging.getLogger(__name__)

TEMPLATE_NAME = "Cross-sell dinámico — Producto por edad"
AUTOMATION_NAME = "Cross-sell dinámico — Bestsellers por edad (envío gratis)"
COUPON_CAMPAIGN_NAME = "Envío gratis cross-sell dinámico"
LEGACY_STATIC_AUTOMATION = "Cross-sell: Pista Autos → Mi Primer Taladro (envío gratis)"

HL_LOGO = "https://cdn.shopify.com/s/files/1/0556/5343/3495/files/LOGO_HappyLapiz.png?v=1621889822"
FF = "'Helvetica Neue', Arial, sans-serif"

SUBJECT = (
    "{% if first_product %}Si te gustó {{ first_product }}, esto también te va a encantar 🎁"
    "{% else %}Esto también te va a encantar 🎁{% endif %}"
)
PREVIEW = "{{ cross_sell_product_title }} — con envío gratis solo para ti"

# Step 1: 10 days after order; steps 2–8: every 14 days
MAX_STEPS = 8
FIRST_DELAY_HOURS = 10 * 24
FOLLOWUP_DELAY_HOURS = 14 * 24


def _template_blocks() -> list[dict]:
    return [
        make_block(
            "header",
            {
                "logo_url": HL_LOGO,
                "logo_width": "140",
                "bg_color": "#ffffff",
                "link": "https://www.happylapiz.cl",
            },
            "header_1",
        ),
        make_block(
            "text",
            {
                "content": (
                    f'<p style="margin:0;font-size:11px;font-weight:600;color:rgba(255,255,255,0.85);'
                    f'text-transform:uppercase;letter-spacing:1.2px;text-align:center;'
                    f'font-family:{FF};">Recomendado para ti</p>'
                    f'<p style="margin:10px 0 0;font-size:22px;font-weight:800;color:#ffffff;'
                    f'line-height:1.25;text-align:center;font-family:{FF};">'
                    f'{{% if first_product %}}Si te gust&#243; {{{{ first_product }}}}...<br/>'
                    f'&#161;Esto tambi&#233;n te va a encantar!{{% else %}}'
                    f'&#161;Esto te va a encantar!{{% endif %}}</p>'
                    f'<p style="margin:10px 0 0;font-size:14px;color:#ffffff;line-height:1.5;'
                    f'text-align:center;opacity:0.92;font-family:{FF};">'
                    f'Seleccionamos el juguete m&#225;s querido para la edad de tu peque.</p>'
                ),
                "bg_color": "#2563eb",
                "text_color": "#ffffff",
                "padding_y": "28",
                "padding_x": "28",
                "font_family": FF,
            },
            "hero_1",
        ),
        make_block(
            "text",
            {
                "content": "{{ cross_sell_product_html }}",
                "bg_color": "#ffffff",
                "text_color": "#111827",
                "padding_y": "20",
                "padding_x": "16",
                "font_family": FF,
            },
            "product_dyn",
        ),
        make_block(
            "coupon",
            {
                "title": "Env&#237;o gratis solo para ti",
                "code": "{{ coupon_code }}",
                "subtitle": "El bot&#243;n de arriba ya lleva el cup&#243;n activo",
                "bg_color": "#eff6ff",
                "text_color": "#1e40af",
                "border_color": "#2563eb",
            },
            "coupon_shipping",
        ),
        make_block(
            "button",
            {
                "text": "Llevarme este juguete con envío gratis →",
                "url": "{{ cross_sell_product_url }}",
                "bg_color": "#2563eb",
                "text_color": "#ffffff",
                "align": "center",
                "border_radius": "30",
                "font_size": "15",
                "letter_spacing": "0",
                "font_family": FF,
                "full_width": False,
            },
            "cta_buy",
        ),
        make_block(
            "text",
            {
                "content": (
                    f'<div style="background:#f0fdf4;border-radius:12px;padding:18px 22px;text-align:center;">'
                    f'<p style="font-size:14px;color:#15803d;margin:0;line-height:1.6;font-family:{FF};">'
                    f'<strong>&#127793; Juguete educativo</strong> — Elegido por edad y entre los '
                    f'm&#225;s vendidos de Happy L&#225;piz.</p></div>'
                ),
                "bg_color": "#ffffff",
                "text_color": "#374151",
                "padding_y": "12",
                "padding_x": "28",
                "font_family": FF,
            },
            "footer_tip",
        ),
    ]


def _build_steps(template_id: int) -> list[dict]:
    steps = [
        {
            "step": 1,
            "delay_hours": FIRST_DELAY_HOURS,
            "template_id": template_id,
            "subject": SUBJECT,
            "preview_text": PREVIEW,
            "condition": None,
        }
    ]
    for i in range(2, MAX_STEPS + 1):
        steps.append(
            {
                "step": i,
                "delay_hours": FOLLOWUP_DELAY_HOURS,
                "template_id": template_id,
                "subject": SUBJECT,
                "preview_text": PREVIEW,
                "condition": "not_purchased",
            }
        )
    return steps


def _ensure_coupon_campaign(session: Session, shop_id: int, created_by: int | None) -> int | None:
    """Reuse existing free-shipping campaign or create a DB row pointing at the PriceRule."""
    row = session.execute(
        text(
            "SELECT id FROM coupon_campaigns WHERE shop_id = :shop_id "
            "AND (name = :n OR name LIKE 'Envío gratis cross-sell%') "
            "ORDER BY id DESC LIMIT 1"
        ),
        {"n": COUPON_CAMPAIGN_NAME, "shop_id": shop_id},
    ).fetchone()
    if row:
        session.execute(
            text("UPDATE coupon_campaigns SET name = :n WHERE id = :id"),
            {"n": COUPON_CAMPAIGN_NAME, "id": row[0]},
        )
        session.flush()
        return int(row[0])

    pr = session.execute(
        text(
            "SELECT shopify_discount_id FROM coupon_campaigns "
            "WHERE shop_id = :shop_id AND discount_type = 'shipping' "
            "AND shopify_discount_id IS NOT NULL LIMIT 1"
        ),
        {"shop_id": shop_id},
    ).fetchone()
    sid = pr[0] if pr else None
    if not sid:
        logger.warning("No shipping coupon campaign found for shop %s — automation without coupons", shop_id)
        return None

    session.execute(
        text("""
            INSERT INTO coupon_campaigns (
                name, shopify_discount_id, discount_type, discount_value,
                min_purchase, prefix, expires_at, applies_to, coupon_mode, static_code, created_by,
                combines_with_order_discounts, combines_with_product_discounts, combines_with_shipping_discounts,
                shop_id
            ) VALUES (
                :name, :sid, 'shipping', 0,
                0, 'ENVIO', '2099-12-31T23:59:59Z', 'all', 'dynamic', NULL, :uid,
                TRUE, TRUE, TRUE, :shop_id
            )
        """),
        {"name": COUPON_CAMPAIGN_NAME, "sid": sid, "uid": created_by, "shop_id": shop_id},
    )
    session.flush()
    new_id = session.execute(
        text(
            "SELECT id FROM coupon_campaigns WHERE name = :n AND shop_id = :shop_id "
            "ORDER BY id DESC LIMIT 1"
        ),
        {"n": COUPON_CAMPAIGN_NAME, "shop_id": shop_id},
    ).scalar()
    return int(new_id) if new_id else None


def ensure_dynamic_cross_sell_setup(session: Session, shop=None, *, force_template: bool = False) -> dict | None:
    """Upsert template + multi-step automation for dynamic age-based cross-sell."""
    from app.models.shop import Shop

    if shop is None:
        shop = session.exec(
            select(Shop).where(Shop.shopify_domain == "happy-lapiz.myshopify.com")
        ).first()
    if shop is None:
        return None

    user = session.exec(select(User).where(User.shop_id == shop.id).order_by(User.id)).first()
    uid = user.id if user else None

    tpl = upsert_block_template(
        session,
        shop_id=shop.id,
        name=TEMPLATE_NAME,
        subject=SUBJECT,
        preview=PREVIEW,
        blocks=_template_blocks(),
        created_by=uid,
        force=force_template,
    )
    session.flush()

    coupon_id = _ensure_coupon_campaign(session, shop.id, uid)
    steps = _build_steps(int(tpl.id))
    trigger_config = {
        "dynamic_cross_sell": True,
        "cross_sell_max_products": MAX_STEPS,
        "lookback_hours": 72,
        "product_recommendation_config": {
            "enabled": True,
            "strategy": "bestseller",
            "require_age_match": True,
            "require_edad_catalog": True,
            "exclude_purchased": True,
            "lookback_days": 180,
            "max_products": MAX_STEPS,
        },
    }

    legacy = session.exec(
        select(Automation).where(
            Automation.name == LEGACY_STATIC_AUTOMATION,
            Automation.shop_id == shop.id,
        )
    ).first()
    if legacy and legacy.status != "cancelled":
        legacy.status = "cancelled"
        legacy.updated_at = datetime.utcnow()
        session.add(legacy)

    auto = session.exec(
        select(Automation).where(Automation.name == AUTOMATION_NAME, Automation.shop_id == shop.id)
    ).first()
    if auto:
        auto.trigger_type = "placed_order"
        auto.trigger_config = trigger_config
        auto.steps = steps
        auto.template_id = int(tpl.id)
        auto.subject = SUBJECT
        auto.coupon_campaign_id = coupon_id
        if auto.status in ("draft", "cancelled"):
            auto.status = "active"
        auto.updated_at = datetime.utcnow()
        session.add(auto)
    else:
        auto = Automation(
            name=AUTOMATION_NAME,
            trigger_type="placed_order",
            trigger_config=trigger_config,
            steps=steps,
            template_id=int(tpl.id),
            subject=SUBJECT,
            coupon_campaign_id=coupon_id,
            status="active",
            created_by=uid,
            shop_id=shop.id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(auto)

    session.commit()
    session.refresh(auto)
    session.refresh(tpl)
    logger.info(
        "Dynamic cross-sell ready: shop=%s template=%s automation=%s coupon=%s steps=%d",
        shop.id, tpl.id, auto.id, coupon_id, len(steps),
    )
    return {
        "template_id": tpl.id,
        "automation_id": auto.id,
        "coupon_campaign_id": coupon_id,
        "steps": len(steps),
        "status": auto.status,
        "shop_id": shop.id,
    }
