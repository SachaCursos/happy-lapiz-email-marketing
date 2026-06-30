"""Compile template editor blocks to email HTML (mirrors frontend blocksToHtml)."""

from __future__ import annotations

import json
from typing import Any

FF = "'Helvetica Neue', Arial, sans-serif"


def _product_price_html(p: dict) -> str:
    font = FF
    compare_at = p.get("compare_at_price") or ""
    price = p.get("price") or ""
    if compare_at:
        return (
            f'<p style="margin:0 0 5px;text-align:center;">'
            f'<span style="font-size:13px;color:#9ca3af;text-decoration:line-through;font-family:{font};margin-right:6px;">{compare_at}</span>'
            f'<span style="font-size:14px;font-weight:bold;color:#e53e3e;font-family:{font};">{price}</span>'
            f"</p>"
        )
    return (
        f'<p style="margin:0 0 5px;font-size:14px;font-weight:normal;color:#222222;font-family:{font};text-align:center;">{price}</p>'
    )


def _product_block_html(p: dict) -> str:
    font = FF
    image_url = p.get("image_url") or ""
    title = p.get("title") or ""
    url = p.get("url") or "#"
    button_text = p.get("button_text") or "Comprar"
    button_color = p.get("button_color") or "#111111"
    bg_color = p.get("bg_color") or "#ffffff"
    description = p.get("description") or ""
    img = (
        f'<a href="{url}" style="display:block;text-decoration:none;">'
        f'<img src="{image_url}" alt="{title}" style="display:block;margin:0 auto 8px;max-width:100%;max-height:125px;width:auto;" />'
        f"</a>"
        if image_url
        else ""
    )
    desc = (
        f'<p style="margin:0 0 8px;font-size:13px;color:#666666;font-family:{font};text-align:center;">{description}</p>'
        if description
        else ""
    )
    return f"""<div style="background:{bg_color};padding:9px;text-align:center;">
  {img}
  <p style="margin:0 0 5px;font-size:14px;font-weight:bold;color:#222222;font-family:{font};text-align:center;">{title}</p>
  {_product_price_html(p)}
  {desc}
  <a href="{url}" style="display:inline-block;margin-top:9px;background:{button_color};color:#ffffff;font-size:16px;font-weight:400;padding:10px 10px;border-radius:5px;text-decoration:none;font-family:{font};">{button_text}</a>
</div>"""


def _product_row_html(products: list[dict]) -> str:
    n = len(products)
    col_pct = "50%" if n == 2 else "33.333%"
    bg = (products[0].get("props") or {}).get("bg_color") or "#ffffff"
    font = FF
    cols = []
    for block in products:
        p = block.get("props") or {}
        image_url = p.get("image_url") or ""
        title = p.get("title") or ""
        url = p.get("url") or "#"
        button_text = p.get("button_text") or "Comprar"
        button_color = p.get("button_color") or "#111111"
        img = (
            f'<a href="{url}" style="display:block;text-decoration:none;">'
            f'<img src="{image_url}" alt="{title}" style="display:block;margin:0 auto 8px;max-width:100%;max-height:125px;width:auto;" />'
            f"</a>"
            if image_url
            else ""
        )
        cols.append(
            f'<td width="{col_pct}" valign="top" style="padding:9px 9px;text-align:center;vertical-align:top;">\n'
            f"  {img}\n"
            f'  <p style="margin:0 0 5px;font-size:14px;font-weight:bold;color:#222222;font-family:{font};text-align:center;">{title}</p>\n'
            f"  {_product_price_html(p)}\n"
            f'  <a href="{url}" style="display:inline-block;margin-top:9px;background:{button_color};color:#ffffff;font-size:16px;font-weight:400;padding:10px 10px;border-radius:5px;text-decoration:none;font-family:{font};">{button_text}</a>\n'
            f"</td>"
        )
    return f"""<div style="background:{bg};padding:8px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
{chr(10).join(cols)}
  </tr></table>
</div>"""


def block_to_html(block: dict) -> str:
    t = block.get("type", "")
    p = block.get("props") or {}

    if t == "header":
        return f"""<div style="background:{p.get('bg_color', '#ffffff')};padding:20px 32px;text-align:center;border-bottom:1px solid #f3f4f6;">
  <a href="{p.get('link', 'https://www.happylapiz.cl')}" style="display:inline-block;text-decoration:none;">
    <img src="{p.get('logo_url', '')}" alt="Happy Lápiz" width="{p.get('logo_width', '160')}" style="height:auto;display:block;margin:0 auto;" />
  </a>
</div>"""

    if t == "text":
        ff = p.get("font_family") or FF
        tc = p.get("text_color") or "#222222"
        return f"""<div style="background:{p.get('bg_color', '#ffffff')};padding:{p.get('padding_y', '24')}px {p.get('padding_x', '32')}px;font-family:{ff};color:{tc};word-break:break-word;overflow-wrap:break-word;">
  {p.get('content', '')}
</div>"""

    if t == "button":
        align = p.get("align") or "center"
        if align not in ("left", "right", "center"):
            align = "center"
        ff = p.get("font_family") or FF
        ls = f"letter-spacing:{p.get('letter_spacing', '0')}px;" if p.get("letter_spacing") else ""
        if p.get("full_width"):
            return f"""<div style="background:{p.get('bg_color', '#111111')};padding:12px 0;text-align:center;">
  <a href="{p.get('url', '#')}" style="color:{p.get('text_color', '#ffffff')};font-size:{p.get('font_size', '16')}px;font-weight:400;text-decoration:none;font-family:{ff};{ls}display:inline-block;padding:4px 8px;">
    {p.get('text', 'Ver más')}
  </a>
</div>"""
        return f"""<div style="padding:16px 32px;text-align:{align};background:#ffffff;">
  <a href="{p.get('url', '#')}" style="display:inline-block;background:{p.get('bg_color', '#111111')};color:{p.get('text_color', '#ffffff')};font-size:{p.get('font_size', '16')}px;font-weight:400;padding:10px 24px;border-radius:{p.get('border_radius', '5')}px;text-decoration:none;font-family:{ff};{ls}">
    {p.get('text', 'Ver más')}
  </a>
</div>"""

    if t == "divider":
        return f"""<div style="padding:{p.get('padding_y', '16')}px 32px;background:#ffffff;">
  <div style="height:{p.get('thickness', '1')}px;background:{p.get('color', '#e5e7eb')};"></div>
</div>"""

    if t == "spacer":
        h = p.get("height", "32")
        return f"""<div style="height:{h}px;background:{p.get('bg_color', '#ffffff')};line-height:{h}px;font-size:1px;">&nbsp;</div>"""

    if t == "product":
        return _product_block_html(p)

    if t == "product_grid":
        var = p.get("variable", "recommended_products_html")
        return f"""<div style="background:{p.get('bg_color', '#ffffff')};padding:{p.get('padding_y', '16')}px {p.get('padding_x', '0')}px;">{{{{ {var} }}}}</div>"""

    if t == "coupon":
        subtitle = p.get("subtitle") or ""
        sub_html = (
            f'<p style="margin:12px 0 0;font-size:13px;color:#888;font-family:-apple-system,sans-serif;">{subtitle}</p>'
            if subtitle
            else ""
        )
        return f"""<div style="background:{p.get('bg_color', '#f9fafb')};padding:28px 32px;text-align:center;">
  <p style="margin:0 0 14px;font-size:16px;font-weight:600;color:{p.get('text_color', '#111111')};font-family:-apple-system,sans-serif;">{p.get('title', '')}</p>
  <div style="display:inline-block;border:2px dashed {p.get('border_color', '#682ae7')};border-radius:10px;padding:14px 32px;background:#ffffff;">
    <span style="font-size:24px;font-weight:800;letter-spacing:4px;color:{p.get('text_color', '#111111')};font-family:monospace;">{p.get('code', '')}</span>
  </div>
  {sub_html}
</div>"""

    return ""


def blocks_to_html(blocks: list[dict]) -> str:
    """Compile blocks; consecutive product blocks render side-by-side (max 3 per row)."""
    if not blocks:
        return ""

    groups: list[Any] = []
    for block in blocks:
        last = groups[-1] if groups else None
        if block.get("type") == "product" and isinstance(last, list) and len(last) < 3:
            last.append(block)
        elif block.get("type") == "product":
            groups.append([block])
        else:
            groups.append(block)

    parts: list[str] = []
    for group in groups:
        if isinstance(group, list):
            parts.append(_product_block_html(group[0]["props"]) if len(group) == 1 else _product_row_html(group))
        else:
            parts.append(block_to_html(group))

    inner = "".join(parts)
    return (
        f'<div style="font-family:{FF};max-width:600px;margin:0 auto;background:#ffffff;">'
        f"{inner}</div>"
    )


def resolve_template_html(template: Any) -> str:
    """Prefer fresh compile from json_blocks so product blocks are never stripped."""
    from app.services.template_compositions import is_editor_block_list

    blocks = getattr(template, "json_blocks", None)
    if isinstance(blocks, str):
        try:
            blocks = json.loads(blocks)
        except Exception:
            blocks = None
    if is_editor_block_list(blocks):
        return blocks_to_html(blocks)
    return getattr(template, "html_content", None) or ""


def make_block(block_type: str, props: dict, block_id: str | None = None) -> dict:
    return {
        "id": block_id or f"{block_type}_seed",
        "type": block_type,
        "props": props,
    }
