/** Visual design config for dynamic product HTML blocks (featured + grid). */

export type ProductBlockLayout = "featured" | "grid";

export interface ProductBlockDesign {
  layout: ProductBlockLayout;
  bg_color: string;
  padding_y: number;
  padding_x: number;
  max_width: number;
  image_radius: number;
  image_max_width: number;
  title_font_size: number;
  title_color: string;
  title_font_weight: number;
  price_font_size: number;
  price_color: string;
  price_font_weight: number;
  btn_text: string;
  btn_bg: string;
  btn_text_color: string;
  btn_border_radius: number;
  btn_font_size: number;
  btn_font_weight: number;
  btn_padding_y: number;
  btn_padding_x: number;
  show_discount_badge: boolean;
  discount_badge_bg: string;
  discount_badge_text_color: string;
  font_family: string;
}

export interface ProductSample {
  title: string;
  handle?: string;
  image_url?: string;
  price: string;
  url?: string;
}

const BASE_DESIGN: ProductBlockDesign = {
  layout: "grid",
  bg_color: "#ffffff",
  padding_y: 16,
  padding_x: 8,
  max_width: 560,
  image_radius: 10,
  image_max_width: 200,
  title_font_size: 14,
  title_color: "#1a1a1a",
  title_font_weight: 600,
  price_font_size: 15,
  price_color: "#e85d04",
  price_font_weight: 700,
  btn_text: "Ver producto →",
  btn_bg: "#f97316",
  btn_text_color: "#ffffff",
  btn_border_radius: 20,
  btn_font_size: 12,
  btn_font_weight: 600,
  btn_padding_y: 7,
  btn_padding_x: 18,
  show_discount_badge: false,
  discount_badge_bg: "#e53e3e",
  discount_badge_text_color: "#ffffff",
  font_family: "'Helvetica Neue', Arial, sans-serif",
};

export const DEFAULT_FEATURED_DESIGN: ProductBlockDesign = {
  ...BASE_DESIGN,
  layout: "featured",
  show_discount_badge: true,
};

export const DEFAULT_GRID_DESIGN: ProductBlockDesign = {
  ...BASE_DESIGN,
  layout: "grid",
};

export function defaultDesignForBlock(blockKey: string): ProductBlockDesign {
  if (blockKey === "featured_product_html") {
    return { ...DEFAULT_FEATURED_DESIGN };
  }
  return { ...DEFAULT_GRID_DESIGN };
}

export function mergeDesign(
  blockKey: string,
  stored: Partial<ProductBlockDesign> | null | undefined
): ProductBlockDesign {
  const base = defaultDesignForBlock(blockKey);
  if (!stored || typeof stored !== "object") return base;
  return { ...base, ...stored };
}

function productInnerJinja(d: ProductBlockDesign): string {
  const badge = d.show_discount_badge
    ? `{% if descuento_producto_mes %}
<span style="display:inline-block;background:${d.discount_badge_bg};color:${d.discount_badge_text_color};font-size:11px;font-weight:700;padding:4px 10px;border-radius:12px;margin-bottom:10px;">{{ descuento_producto_mes }}% OFF</span>
{% endif %}
`
    : "";

  return `<a href="{{ p.url }}" style="text-decoration:none;color:${d.title_color};display:block;font-family:${d.font_family};">
${badge}{% if p.image_url %}<img src="{{ p.image_url }}" alt="{{ p.title }}" width="${d.image_max_width}" style="width:100%;max-width:${d.image_max_width}px;height:auto;border-radius:${d.image_radius}px;display:block;margin:0 auto 12px;" />{% endif %}
<p style="font-size:${d.title_font_size}px;font-weight:${d.title_font_weight};color:${d.title_color};margin:0 0 5px;line-height:1.3;max-height:3.9em;overflow:hidden;font-family:${d.font_family};">{{ p.title }}</p>
<p style="font-size:${d.price_font_size}px;color:${d.price_color};font-weight:${d.price_font_weight};margin:0 0 12px;font-family:${d.font_family};">{{ p.price }}</p>
<span style="display:inline-block;background:${d.btn_bg};color:${d.btn_text_color};font-size:${d.btn_font_size}px;font-weight:${d.btn_font_weight};padding:${d.btn_padding_y}px ${d.btn_padding_x}px;border-radius:${d.btn_border_radius}px;text-decoration:none;">${d.btn_text.replace(/→/g, "&rarr;")}</span>
</a>`;
}

function gridCellJinja(d: ProductBlockDesign): string {
  return `<td width="50%" style="width:50%;padding:${d.padding_y}px ${d.padding_x}px;vertical-align:top;text-align:center;">
${productInnerJinja(d)}
</td>`;
}

/** Compile design settings into a Jinja2 email-safe HTML template. */
export function compileProductBlockJinja(d: ProductBlockDesign): string {
  const cell = gridCellJinja(d);
  const inner = productInnerJinja(d);

  if (d.layout === "featured") {
    return `{% if products and products|length > 0 %}
{% set p = products[0] %}
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;max-width:${d.max_width}px;margin:0 auto;background:${d.bg_color};font-family:${d.font_family};">
<tbody><tr>
<td style="padding:${d.padding_y}px ${d.padding_x}px;text-align:center;vertical-align:top;">
${inner}
</td>
</tr></tbody></table>
{% endif %}`;
  }

  return `{% if product_rows %}
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;max-width:${d.max_width}px;margin:0 auto;background:${d.bg_color};font-family:${d.font_family};">
<tbody>
{% for row in product_rows %}
<tr>
{% for p in row %}
${cell}
{% endfor %}
{% if row|length == 1 %}<td width="50%" style="width:50%;"></td>{% endif %}
</tr>
{% endfor %}
</tbody></table>
{% endif %}`;
}

export function chunkProducts<T>(items: T[], size: number): T[][] {
  const rows: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    rows.push(items.slice(i, i + size));
  }
  return rows;
}
