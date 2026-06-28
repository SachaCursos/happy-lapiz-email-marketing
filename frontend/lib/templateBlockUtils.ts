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

/** Deep copy block props so inserted favorites are independent and fully editable. */
export function cloneBlockProps(
  props: Record<string, string | number | boolean>
): Record<string, string | number | boolean> {
  return JSON.parse(JSON.stringify(props));
}

export function blockFromFavorite(
  fav: { block_type: string; props: Record<string, string | number | boolean> },
  defaults: Record<string, Record<string, string | number | boolean>>,
  id?: string
): { id: string; type: string; props: Record<string, string | number | boolean> } {
  const type = fav.block_type;
  return {
    id: id ?? `${type}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    type,
    props: { ...(defaults[type] ?? {}), ...cloneBlockProps(fav.props) },
  };
}

export interface HeroTypography {
  logoWidth: number;
  subtitlePx: number;
  titlePx: number;
  bodyPx: number;
}

function parseRoot(html: string) {
  const doc = new DOMParser().parseFromString(`<div id="tb-root">${html}</div>`, "text/html");
  return doc.getElementById("tb-root");
}

function textParagraphs(root: HTMLElement) {
  return [...root.querySelectorAll("p")].filter((p) => !p.querySelector("img"));
}

function readFontSizePx(el: HTMLElement, fallback: number): number {
  const inline = el.style.fontSize || "";
  const m = inline.match(/(\d+(?:\.\d+)?)px/);
  if (m) return Math.round(parseFloat(m[1]));
  const attr = el.getAttribute("style") || "";
  const m2 = attr.match(/font-size:\s*(\d+(?:\.\d+)?)px/i);
  if (m2) return Math.round(parseFloat(m2[1]));
  return fallback;
}

/** Text block with centered logo + headline paragraphs (vacaciones-style hero). */
export function isHeroTextBlock(html: string): boolean {
  if (!html?.trim()) return false;
  try {
    const root = parseRoot(html);
    if (!root?.querySelector("img")) return false;
    return textParagraphs(root).length >= 2;
  } catch {
    return false;
  }
}

export function getHeroTypography(html: string): HeroTypography {
  const defaults: HeroTypography = { logoWidth: 88, subtitlePx: 11, titlePx: 20, bodyPx: 13 };
  try {
    const root = parseRoot(html);
    if (!root) return defaults;
    const img = root.querySelector("img");
    const logoWidth = img
      ? parseInt(img.getAttribute("width") || String(defaults.logoWidth), 10) || defaults.logoWidth
      : defaults.logoWidth;
    const ps = textParagraphs(root);
    return {
      logoWidth,
      subtitlePx: ps[0] ? readFontSizePx(ps[0] as HTMLElement, defaults.subtitlePx) : defaults.subtitlePx,
      titlePx: ps[1] ? readFontSizePx(ps[1] as HTMLElement, defaults.titlePx) : defaults.titlePx,
      bodyPx: ps[2] ? readFontSizePx(ps[2] as HTMLElement, defaults.bodyPx) : defaults.bodyPx,
    };
  } catch {
    return defaults;
  }
}

export function applyHeroTypography(html: string, patch: Partial<HeroTypography>): string {
  try {
    const root = parseRoot(html);
    if (!root) return html;
    if (patch.logoWidth != null) {
      const img = root.querySelector("img");
      if (img) {
        img.setAttribute("width", String(patch.logoWidth));
        (img as HTMLElement).style.maxWidth = "45%";
        (img as HTMLElement).style.height = "auto";
      }
    }
    const ps = textParagraphs(root);
    if (patch.subtitlePx != null && ps[0]) (ps[0] as HTMLElement).style.fontSize = `${patch.subtitlePx}px`;
    if (patch.titlePx != null && ps[1]) (ps[1] as HTMLElement).style.fontSize = `${patch.titlePx}px`;
    if (patch.bodyPx != null && ps[2]) (ps[2] as HTMLElement).style.fontSize = `${patch.bodyPx}px`;
    return root.innerHTML;
  } catch {
    return html;
  }
}

function normalizeText(s: string | null | undefined): string {
  return (s || "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
}

function isElementEmpty(el: Element): boolean {
  if (el.querySelector("img, table, a[href]")) return false;
  const clone = el.cloneNode(true) as HTMLElement;
  clone.querySelectorAll("br").forEach((b) => b.remove());
  return !normalizeText(clone.textContent);
}

/** Remove empty table rows, paragraphs and wrapper divs left after inline editing. */
export function pruneEmptyHtmlContent(html: string): string {
  if (!html?.trim()) return html;
  try {
    const root = parseRoot(html);
    if (!root) return html;

    root.querySelectorAll("tr").forEach((tr) => {
      const tds = tr.querySelectorAll("td");
      let hasContent = false;
      if (tds.length >= 2) {
        hasContent = !isElementEmpty(tds[tds.length - 1]);
      } else {
        hasContent = !isElementEmpty(tr);
      }
      if (!hasContent) tr.remove();
    });

    root.querySelectorAll("p").forEach((p) => {
      if (isElementEmpty(p)) p.remove();
    });

    let changed = true;
    while (changed) {
      changed = false;
      [...root.querySelectorAll("div")].forEach((div) => {
        if (div === root) return;
        if (isElementEmpty(div)) {
          div.remove();
          changed = true;
        }
      });
    }

    return root.innerHTML.trim();
  } catch {
    return html;
  }
}

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
