"""Compile template editor blocks to email HTML (mirrors frontend blocksToHtml)."""

from __future__ import annotations

FF = "'Helvetica Neue', Arial, sans-serif"


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
    inner = "".join(block_to_html(b) for b in blocks)
    return (
        f'<div style="font-family:{FF};max-width:600px;margin:0 auto;background:#ffffff;">'
        f"{inner}</div>"
    )


def make_block(block_type: str, props: dict, block_id: str | None = None) -> dict:
    return {
        "id": block_id or f"{block_type}_seed",
        "type": block_type,
        "props": props,
    }
