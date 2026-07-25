"""Rules-based yearly content plan generator (no LLM) — builds ~11 draft
templates + campaigns spread across common retail dates, using each shop's
own synced products/brand color where available. Always produces something,
even for a shop with an empty catalog and no brand assets (neutral fallbacks).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.campaign import Campaign
from app.models.segment import Segment
from app.models.shop import Shop
from app.models.template import Template
from app.services.template_block_compiler import blocks_to_html, make_block

DEFAULT_BRAND_COLOR = "#682ae7"

# Generic LatAm/Chile retail calendar — no product-vertical assumptions.
COMMERCIAL_CALENDAR = [
    {"key": "vuelta_clases", "month": 2, "day": 25, "title": "Vuelta a clases",
     "headline": "¡Prepárate para la vuelta a clases!",
     "teaser": "encontrá todo lo que necesitás para este nuevo comienzo.",
     "cta_text": "Ver ofertas"},
    {"key": "dia_mujer", "month": 3, "day": 8, "title": "Día de la Mujer",
     "headline": "Hoy celebramos el Día de la Mujer",
     "teaser": "tenemos algo especial pensado para vos.",
     "cta_text": "Ver selección"},
    {"key": "dia_madre", "month": 5, "day": 11, "title": "Día de la Madre",
     "headline": "Un regalo con cariño para el Día de la Madre",
     "teaser": "sorprendé a esa persona especial.",
     "cta_text": "Ver regalos"},
    {"key": "dia_padre", "month": 6, "day": 15, "title": "Día del Padre",
     "headline": "Ideas para regalar en el Día del Padre",
     "teaser": "tenemos opciones para todos los gustos.",
     "cta_text": "Ver ideas"},
    {"key": "rebajas_invierno", "month": 7, "day": 15, "title": "Rebajas de invierno",
     "headline": "Llegaron las rebajas de invierno",
     "teaser": "descuentos por tiempo limitado.",
     "cta_text": "Ver descuentos"},
    {"key": "dia_nino", "month": 8, "day": 10, "title": "Día del Niño",
     "headline": "Celebrá el Día del Niño",
     "teaser": "encontrá el regalo perfecto.",
     "cta_text": "Ver catálogo"},
    {"key": "fiestas_patrias", "month": 9, "day": 10, "title": "Fiestas Patrias",
     "headline": "¡Se viene Fiestas Patrias!",
     "teaser": "preparate para celebrar con lo mejor de nuestra tienda.",
     "cta_text": "Ver ofertas"},
    {"key": "halloween", "month": 10, "day": 25, "title": "Halloween",
     "headline": "Algo especial para Halloween",
     "teaser": "sumate a la celebración.",
     "cta_text": "Ver más"},
    {"key": "cyber_black", "month": 11, "day": 20, "title": "Cyber Monday / Black Friday",
     "headline": "Los mejores descuentos del año",
     "teaser": "no te los pierdas, por tiempo limitado.",
     "cta_text": "Comprar ahora"},
    {"key": "navidad", "month": 12, "day": 10, "title": "Navidad",
     "headline": "Preparate para la Navidad",
     "teaser": "encontrá el regalo ideal para cada persona de tu lista.",
     "cta_text": "Ver regalos"},
]


def infer_store_profile(session: Session, shop: Shop) -> dict:
    """Best-effort read of the shop's own product catalog + brand assets.
    Every field has a neutral fallback — a shop with nothing synced yet still
    gets a usable (empty) profile, never an error."""
    category_rows = session.execute(
        text("""
            SELECT COALESCE(NULLIF(product_type, ''), 'General') AS category, COUNT(*) AS n
            FROM shopify_products
            WHERE shop_id = :shop_id AND status = 'active'
            GROUP BY 1 ORDER BY n DESC LIMIT 5
        """),
        {"shop_id": shop.id},
    ).fetchall()
    top_categories = [{"category": r[0], "count": r[1]} for r in category_rows]

    price_row = session.execute(
        text("""
            SELECT MIN(price), MAX(price), COUNT(*) FROM shopify_products
            WHERE shop_id = :shop_id AND status = 'active' AND price IS NOT NULL
        """),
        {"shop_id": shop.id},
    ).fetchone()
    price_min, price_max, product_count = price_row if price_row else (None, None, 0)

    brand_color = session.execute(
        text("SELECT valor FROM plantillas_de_la_marca WHERE shop_id = :shop_id AND categoria = 'color' ORDER BY id LIMIT 1"),
        {"shop_id": shop.id},
    ).scalar()
    logo_url = session.execute(
        text("SELECT valor FROM plantillas_de_la_marca WHERE shop_id = :shop_id AND categoria = 'logo' ORDER BY id LIMIT 1"),
        {"shop_id": shop.id},
    ).scalar()

    return {
        "product_count": product_count or 0,
        "top_categories": top_categories,
        "price_min": float(price_min) if price_min is not None else None,
        "price_max": float(price_max) if price_max is not None else None,
        "brand_color": brand_color or DEFAULT_BRAND_COLOR,
        "logo_url": logo_url,
    }


def _pick_featured_products(session: Session, shop: Shop, n: int = 3) -> list[dict]:
    """Up to n real active products for this shop. Falls back to generic
    placeholder product blocks when the catalog hasn't been synced yet — the
    plan still gets generated, just without real product data."""
    rows = session.execute(
        text("""
            SELECT title, price, image_url, handle FROM shopify_products
            WHERE shop_id = :shop_id AND status = 'active'
            ORDER BY synced_at DESC LIMIT :n
        """),
        {"shop_id": shop.id, "n": n},
    ).fetchall()

    products = []
    for title, price, image_url, handle in rows:
        products.append({
            "title": title or "Producto destacado",
            "price": f"${price:,.0f}".replace(",", ".") if price else "",
            "image_url": image_url or "",
            "url": f"https://{shop.shopify_domain}/products/{handle}" if handle else f"https://{shop.shopify_domain}",
            "button_text": "Ver producto",
        })

    while len(products) < min(n, 3) and len(products) < n:
        products.append({
            "title": "Producto destacado",
            "price": "",
            "image_url": "",
            "url": f"https://{shop.shopify_domain}",
            "button_text": "Ver más",
            "show_button": True,
        })

    return products


def _build_generic_blocks(shop: Shop, entry: dict, profile: dict, products: list[dict]) -> list[dict]:
    brand_color = profile.get("brand_color") or DEFAULT_BRAND_COLOR
    blocks: list[dict] = []

    if profile.get("logo_url"):
        blocks.append(make_block("header", {
            "logo_url": profile["logo_url"],
            "link": f"https://{shop.shopify_domain}",
        }))
    else:
        blocks.append(make_block("text", {
            "content": f'<p style="text-align:center;font-size:20px;font-weight:700;margin:0;">{shop.display_name()}</p>',
            "bg_color": brand_color,
            "text_color": "#ffffff",
        }))

    blocks.append(make_block("text", {
        "content": (
            f'<p style="font-size:20px;font-weight:700;text-align:center;margin:0 0 8px;">{entry["headline"]}</p>'
            f'<p style="font-size:14px;text-align:center;margin:0;">{{{{ nombre or \'hola\' }}}}, {entry["teaser"]}</p>'
        ),
    }))

    for p in products:
        blocks.append(make_block("product", p))

    blocks.append(make_block("button", {
        "text": entry.get("cta_text") or "Ver más",
        "url": f"https://{shop.shopify_domain}",
        "bg_color": brand_color,
    }))

    return blocks


def _next_occurrence(month: int, day: int, today: date) -> date:
    year = today.year
    try:
        d = date(year, month, day)
    except ValueError:
        d = date(year, month, 28)
    if d < today:
        try:
            d = date(year + 1, month, day)
        except ValueError:
            d = date(year + 1, month, 28)
    return d


def generate_yearly_plan(session: Session, shop: Shop, admin_id: int | None, *, preview: bool = False) -> dict:
    profile = infer_store_profile(session, shop)
    products = _pick_featured_products(session, shop, n=3)
    today = datetime.utcnow().date()
    now = datetime.utcnow()

    entries = list(COMMERCIAL_CALENDAR) + [{
        "key": "aniversario",
        "month": shop.installed_at.month,
        "day": shop.installed_at.day,
        "title": "Aniversario de la tienda",
        "headline": "¡Estamos de aniversario!",
        "teaser": f"gracias por ser parte de {shop.display_name()}. Tenemos algo especial para vos.",
        "cta_text": "Descubrir",
    }]

    segment_id = session.exec(
        select(Segment.id).where(Segment.name == "Todos los suscriptores", Segment.shop_id == shop.id)
    ).first()

    planned = []
    for entry in entries:
        target_date = _next_occurrence(entry["month"], entry["day"], today)
        name = f'{entry["title"]} {target_date.year}'
        subject = f'{entry["headline"]} — {shop.display_name()}'
        lead_days = 0 if entry["key"] == "aniversario" else 7
        scheduled_at = datetime.combine(target_date, datetime.min.time()) - timedelta(days=lead_days)

        existing_tpl = session.exec(select(Template).where(Template.name == name, Template.shop_id == shop.id)).first()
        existing_camp = session.exec(select(Campaign).where(Campaign.name == name, Campaign.shop_id == shop.id)).first()
        already_exists = bool(existing_tpl or existing_camp)

        planned.append({
            "name": name,
            "date": target_date.isoformat(),
            "subject": subject,
            "teaser": entry["teaser"],
            "status": "ya existe" if already_exists else "se creará",
        })

        if preview or already_exists:
            continue

        blocks = _build_generic_blocks(shop, entry, profile, products)
        html = blocks_to_html(blocks)

        tpl = Template(
            name=name, subject_default=subject, preview_text=entry["teaser"],
            html_content=html, json_blocks=blocks, created_by=admin_id,
            shop_id=shop.id, created_at=now, updated_at=now,
        )
        session.add(tpl)
        session.flush()

        camp = Campaign(
            name=name, subject=subject, template_id=tpl.id,
            segment_id=segment_id, status="draft", scheduled_at=scheduled_at,
            created_by=admin_id, shop_id=shop.id, created_at=now,
        )
        session.add(camp)

    if not preview:
        session.commit()

    return {"ok": True, "preview": preview, "profile": profile, "planned": planned}
