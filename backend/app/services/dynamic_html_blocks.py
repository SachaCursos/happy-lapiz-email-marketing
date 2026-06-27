"""Editable Jinja templates for dynamic email HTML blocks (preview uses sample data)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from jinja2 import Environment, ChainableUndefined
from sqlalchemy import text
from sqlmodel import Session

logger = logging.getLogger(__name__)

SAMPLE_PRODUCTS = [
    {
        "title": "Pack Científico Explorador",
        "handle": "pack-cientifico-explorador",
        "image_url": "https://cdn.shopify.com/s/files/1/0556/5343/3495/files/producto-ejemplo.jpg",
        "price": "$29.990",
        "price_raw": 29990,
        "url": "https://www.happylapiz.cl/products/pack-cientifico-explorador",
    },
    {
        "title": "Set de Pintura Creativa",
        "handle": "set-pintura-creativa",
        "image_url": "https://cdn.shopify.com/s/files/1/0556/5343/3495/files/producto-ejemplo.jpg",
        "price": "$24.990",
        "price_raw": 24990,
        "url": "https://www.happylapiz.cl/products/set-pintura-creativa",
    },
]

DEFAULT_BLOCKS: dict[str, dict[str, Any]] = {
    "featured_product_html": {
        "name": "Producto del mes",
        "description": "Bloque HTML para {{ featured_product_html }} — un producto destacado.",
        "html_template": """{% if products and products|length > 0 %}
{% set p = products[0] %}
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;max-width:560px;margin:0 auto;">
<tbody><tr>
<td width="50%" style="width:50%;padding:12px 8px;vertical-align:top;text-align:center;">
<a href="{{ p.url }}" style="text-decoration:none;color:#1a1a1a;display:block;">
{% if p.image_url %}<img src="{{ p.image_url }}" alt="{{ p.title }}" width="200" style="width:100%;max-width:200px;height:auto;border-radius:10px;display:block;margin:0 auto 12px;" />{% endif %}
<p style="font-size:14px;font-weight:600;margin:0 0 5px;line-height:1.3;max-height:3.9em;overflow:hidden;">{{ p.title }}</p>
<p style="font-size:15px;color:#e85d04;font-weight:700;margin:0 0 12px;">{{ p.price }}</p>
<span style="display:inline-block;background:{{ btn_color }};color:#fff;font-size:12px;font-weight:600;padding:7px 18px;border-radius:20px;text-decoration:none;">Ver producto &rarr;</span>
</a>
</td>
<td width="50%" style="width:50%;"></td>
</tr></tbody></table>
{% endif %}""",
        "sample_products": SAMPLE_PRODUCTS[:1],
    },
    "recommended_products_html": {
        "name": "Productos recomendados",
        "description": "Bloque HTML para {{ recommended_products_html }} — grilla de 2 columnas.",
        "html_template": """{% if product_rows %}
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;max-width:560px;margin:0 auto;">
<tbody>
{% for row in product_rows %}
<tr>
{% for p in row %}
<td width="50%" style="width:50%;padding:12px 8px;vertical-align:top;text-align:center;">
<a href="{{ p.url }}" style="text-decoration:none;color:#1a1a1a;display:block;">
{% if p.image_url %}<img src="{{ p.image_url }}" alt="{{ p.title }}" width="200" style="width:100%;max-width:200px;height:auto;border-radius:10px;display:block;margin:0 auto 12px;" />{% endif %}
<p style="font-size:14px;font-weight:600;margin:0 0 5px;line-height:1.3;max-height:3.9em;overflow:hidden;">{{ p.title }}</p>
<p style="font-size:15px;color:#e85d04;font-weight:700;margin:0 0 12px;">{{ p.price }}</p>
<span style="display:inline-block;background:{{ btn_color }};color:#fff;font-size:12px;font-weight:600;padding:7px 18px;border-radius:20px;text-decoration:none;">Ver producto &rarr;</span>
</a>
</td>
{% endfor %}
{% if row|length == 1 %}<td width="50%" style="width:50%;"></td>{% endif %}
</tr>
{% endfor %}
</tbody></table>
{% endif %}""",
        "sample_products": SAMPLE_PRODUCTS,
    },
}


def ensure_html_blocks_table(session: Session) -> None:
    session.execute(text("""
        CREATE TABLE IF NOT EXISTS dynamic_html_blocks (
            block_key VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            description TEXT,
            html_template TEXT NOT NULL,
            sample_products JSONB,
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))
    session.commit()


def seed_default_blocks(session: Session) -> None:
    ensure_html_blocks_table(session)
    for key, meta in DEFAULT_BLOCKS.items():
        exists = session.execute(
            text("SELECT 1 FROM dynamic_html_blocks WHERE block_key = :k"),
            {"k": key},
        ).fetchone()
        if exists:
            continue
        session.execute(
            text("""
                INSERT INTO dynamic_html_blocks (block_key, name, description, html_template, sample_products, updated_at)
                VALUES (:k, :name, :desc, :tpl, CAST(:samples AS jsonb), :now)
            """),
            {
                "k": key,
                "name": meta["name"],
                "desc": meta.get("description"),
                "tpl": meta["html_template"],
                "samples": __import__("json").dumps(meta.get("sample_products") or [], ensure_ascii=False),
                "now": datetime.utcnow(),
            },
        )
    session.commit()


def _trunc_title(title: str, max_chars: int = 55) -> str:
    if len(title) <= max_chars:
        return title
    return title[:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _normalize_products(products: list[dict]) -> list[dict]:
    out = []
    for p in products or []:
        if not isinstance(p, dict):
            continue
        title = _trunc_title(str(p.get("title") or ""))
        handle = p.get("handle") or ""
        price_raw = p.get("price_raw")
        if price_raw is None and p.get("price"):
            try:
                price_raw = float(str(p["price"]).replace("$", "").replace(".", "").replace(",", ""))
            except (TypeError, ValueError):
                price_raw = 0
        price_val = float(price_raw or 0)
        out.append({
            **p,
            "title": title,
            "price": p.get("price") or (f"${price_val:,.0f}".replace(",", ".") if price_val else ""),
            "url": p.get("url") or f"https://www.happylapiz.cl/products/{handle}",
        })
    return out


def _product_rows(products: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    for i in range(0, len(products), 2):
        rows.append(products[i : i + 2])
    return rows


def render_html_block(
    session: Session,
    block_key: str,
    products: list[dict],
    btn_color: str = "#f97316",
    extra_vars: dict | None = None,
) -> str:
    """Render a stored block template with real or sample products."""
    seed_default_blocks(session)
    row = session.execute(
        text("""
            SELECT html_template FROM dynamic_html_blocks WHERE block_key = :k
        """),
        {"k": block_key},
    ).fetchone()

    if row and row[0]:
        template_str = row[0]
    elif block_key in DEFAULT_BLOCKS:
        template_str = DEFAULT_BLOCKS[block_key]["html_template"]
    else:
        return ""

    normalized = _normalize_products(products)
    ctx: dict[str, Any] = {
        "products": normalized,
        "product_rows": _product_rows(normalized),
        "btn_color": btn_color,
        **(extra_vars or {}),
    }
    try:
        env = Environment(undefined=ChainableUndefined)
        return env.from_string(template_str).render(**ctx)
    except Exception as exc:
        logger.error("render_html_block %s failed: %s", block_key, exc)
        return ""


def preview_html_block(
    session: Session,
    block_key: str,
    html_template: str | None = None,
    sample_products: list | None = None,
    btn_color: str = "#f97316",
) -> str:
    seed_default_blocks(session)
    if html_template is None or sample_products is None:
        row = session.execute(
            text("SELECT html_template, sample_products FROM dynamic_html_blocks WHERE block_key = :k"),
            {"k": block_key},
        ).fetchone()
        if row:
            html_template = html_template or row[0]
            sample_products = sample_products if sample_products is not None else row[1]
    if not html_template:
        meta = DEFAULT_BLOCKS.get(block_key, {})
        html_template = meta.get("html_template", "")
        sample_products = sample_products or meta.get("sample_products", [])

    normalized = _normalize_products(sample_products or [])
    ctx = {
        "products": normalized,
        "product_rows": _product_rows(normalized),
        "btn_color": btn_color,
        "descuento_producto_mes": 20,
    }
    env = Environment(undefined=ChainableUndefined)
    return env.from_string(html_template).render(**ctx)
