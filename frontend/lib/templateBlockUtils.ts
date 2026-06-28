/** Helpers shared by the template block editor and favorite blocks UI. */

export type BlockType =
  | "header"
  | "text"
  | "image"
  | "button"
  | "product"
  | "product_grid"
  | "coupon"
  | "divider"
  | "spacer"
  | "timer";

export interface TemplateBlockShape {
  type: BlockType;
  props: Record<string, string | number | boolean>;
}

/** Apply a text color across common inline elements inside HTML content. */
export function syncTextBlockColor(html: string, color: string): string {
  if (!html?.trim()) return html;
  try {
    const doc = new DOMParser().parseFromString(`<div id="tb-root">${html}</div>`, "text/html");
    const root = doc.getElementById("tb-root");
    if (!root) return html;
    root.querySelectorAll("p, span, div, li, strong, em, b, i, h1, h2, h3, h4, a").forEach((el) => {
      (el as HTMLElement).style.color = color;
    });
    if (!root.querySelector("p, span, div, li, h1, h2, h3, h4")) {
      root.style.color = color;
    }
    return root.innerHTML;
  } catch {
    return html;
  }
}

export function extractTextColorFromHtml(html: string, fallback = "#222222"): string {
  try {
    const doc = new DOMParser().parseFromString(`<div id="tb-root">${html}</div>`, "text/html");
    const root = doc.getElementById("tb-root");
    const first = root?.querySelector("[style*='color']") as HTMLElement | null;
    if (!first?.style?.color) return fallback;
    const rgb = first.style.color;
    if (rgb.startsWith("#")) return rgb;
    const m = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (!m) return fallback;
    const hex = (n: number) => n.toString(16).padStart(2, "0");
    return `#${hex(+m[1])}${hex(+m[2])}${hex(+m[3])}`;
  } catch {
    return fallback;
  }
}
