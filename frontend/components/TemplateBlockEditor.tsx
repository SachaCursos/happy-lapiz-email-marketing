"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronUp, ChevronDown, Trash2, Plus, Eye, Layout, Code,
  Star, X, Monitor, Smartphone, Search, Link as LinkIcon,
  AlignLeft, AlignCenter, AlignRight, Send, Copy, Undo2,
} from "lucide-react";
import { shopifyApi, ShopifyProduct, api, adminApi, favoriteBlocksApi, FavoriteBlock } from "@/lib/api";
import { syncTextBlockColor, extractTextColorFromHtml, cloneBlockProps, isHeroTextBlock, getHeroTypography, applyHeroTypography, pruneEmptyHtmlContent } from "@/lib/templateBlockUtils";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────────
type BlockType = "header" | "text" | "image" | "button" | "product" | "product_grid" | "coupon" | "divider" | "spacer" | "timer";

export interface Block {
  id: string;
  type: BlockType;
  props: Record<string, string | number | boolean>;
  _favName?: string;
}

// ── Defaults ───────────────────────────────────────────────────────────────────
// Happy Lápiz brand palette (extracted from Klaviyo templates)
const BRAND_PALETTE = [
  "#682ae7", // morado marca
  "#f97316", // naranja marca
  "#ea580c", // naranja oscuro
  "#fb923c", // naranja claro
  "#fff7ed", // fondo naranja suave
  "#2a2ee7", // azul link
  "#222222", // texto oscuro
  "#727272", // texto secundario
  "#fcfcfc", // fondo sección
  "#ffffff", // blanco
  "#000000", // negro
  "#e53e3e", // precio oferta
];

// Font options seen in Klaviyo + estándar email
const FONT_OPTIONS = [
  { label: "Helvetica Neue (Klaviyo)", value: "'Helvetica Neue', Arial, sans-serif" },
  { label: "Sistema / Sans-serif", value: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" },
  { label: "Georgia (Serif)", value: "Georgia, 'Times New Roman', serif" },
  { label: "Verdana", value: "Verdana, Geneva, Tahoma, sans-serif" },
  { label: "Courier New (Monospace)", value: "'Courier New', Courier, monospace" },
];

const TEMPLATE_VARS: { group: string; vars: { key: string; desc: string; raw?: boolean }[] }[] = [
  {
    group: "Siempre disponibles",
    vars: [
      { key: "nombre",        desc: "Nombre del contacto (ej: Juan)" },
      { key: "first_name",    desc: "Primer nombre" },
      { key: "email",         desc: "Email del contacto" },
      { key: "orders_count",  desc: "Número de pedidos en Shopify" },
      { key: "total_spent",   desc: "Total gastado en la tienda" },
      { key: "ticket_medio",  desc: "Ticket promedio por pedido" },
      { key: "shipping_city", desc: "Ciudad de envío" },
      { key: "coupon_code",   desc: "Código de cupón dinámico" },
      { key: "{% unsubscribe %}", desc: "Enlace para darse de baja", raw: true },
    ],
  },
  {
    group: "Carrito abandonado",
    vars: [
      { key: "cart_total",                    desc: "Total del carrito (ej: $29.990)" },
      { key: "first_product",                 desc: "Nombre del primer producto" },
      { key: "cart_url",                      desc: "URL del carrito" },
      { key: "event.extra.checkout_url",      desc: "URL de checkout directo" },
      { key: "event.extra.checkout_url_with_coupon", desc: "Checkout con cupón pre-aplicado" },
    ],
  },
  {
    group: "Pedidos",
    vars: [
      { key: "order_number",    desc: "Número de pedido (ej: #1234)" },
      { key: "order_total",     desc: "Total del pedido" },
      { key: "tracking_number", desc: "Número de seguimiento (fulfilled_order)" },
    ],
  },
  {
    group: "Historial de compras",
    vars: [
      { key: "producto_comprado_html",   desc: "HTML del producto comprado (solo cuando el cliente hizo 1 pedido)" },
      { key: "producto_comprado",        desc: "Nombre del producto comprado (1 pedido)" },
      { key: "productos_comprados_html", desc: "HTML lista de todos los productos comprados (más de 1 pedido)" },
      { key: "primer_producto_comprado", desc: "Nombre del primer producto en su historial (más de 1 pedido)" },
    ],
  },
  {
    group: "Cumpleaños / Regalón",
    vars: [
      { key: "nombre_regalado",                desc: "1.er regalado (nombre o «tu hijo/a» si el nombre es inválido)" },
      { key: "relacion",                       desc: "Relación del 1.er regalado en forma «tu»" },
      { key: "nombre_regalado2",               desc: "2.º regalado (nombre o relación en forma «tu»)" },
      { key: "relacion2",                      desc: "Relación del 2.º regalado en forma «tu»" },
      { key: "nombres_regalados",              desc: "Todos los regalados unidos con «y»" },
      { key: "dias_para_cumpleanos",           desc: "Días que faltan para el cumpleaños" },
      { key: "fecha_cumpleanos",               desc: "Fecha del próximo cumpleaños" },
      { key: "edad_regalon",                   desc: "Edad del regalón (custom_fields.edad_regalon)" },
      { key: "productos_recomendados_edad_html", desc: "Grilla HTML de productos para la edad del regalón, sin los ya comprados" },
    ],
  },
  {
    group: "Cross-sell (con configuración)",
    vars: [
      { key: "recommended_products_html", desc: "Grilla HTML de productos recomendados (requiere cross_sell_config en la automatización)" },
    ],
  },
];

const DEFAULTS: Record<BlockType, Record<string, string | number | boolean>> = {
  header: {
    logo_url: "https://cdn.shopify.com/s/files/1/0556/5343/3495/files/LOGO_HappyLapiz.png?v=1621889822",
    logo_width: "160",
    bg_color: "#ffffff",
    link: "https://www.happylapiz.cl",
  },
  text: {
    content: `<p style="margin:0;font-size:15px;line-height:1.75;color:#222222;font-family:'Helvetica Neue',Arial,sans-serif;">Hola, <strong>{{ nombre }}</strong> 👋<br/><br/>Escribe tu mensaje aquí.</p>`,
    bg_color: "#ffffff",
    text_color: "#222222",
    padding_y: "24",
    padding_x: "32",
    font_family: "'Helvetica Neue', Arial, sans-serif",
  },
  image: {
    src: "",
    alt: "",
    link: "",
    border_radius: "0",
    bg_color: "#ffffff",
    width: "",        // empty = 100%; pixel value = fixed width centered
    align: "center",
  },
  button: {
    text: "Ver más",
    url: "https://www.happylapiz.cl",
    bg_color: "#111111",
    text_color: "#ffffff",
    align: "center",
    border_radius: "5",
    font_size: "16",
    letter_spacing: "1",
    font_family: "'Helvetica Neue', Arial, sans-serif",
    full_width: false,
  },
  product: {
    title: "Nombre del producto",
    price: "$29.990",
    compare_at_price: "",
    image_url: "",
    url: "https://www.happylapiz.cl",
    description: "",
    button_text: "Comprar",
    button_color: "#111111",
    show_button: true,
    price_color: "#e53e3e",
    bg_color: "#ffffff",
  },
  coupon: {
    title: "Tu código de descuento",
    code: "{{ coupon_code }}",
    subtitle: "Úsalo en tu próxima compra",
    bg_color: "#f9fafb",
    text_color: "#111111",
    border_color: "#682ae7",
  },
  divider: {
    color: "#e5e7eb",
    thickness: "1",
    padding_y: "16",
  },
  spacer: {
    height: "32",
    bg_color: "#ffffff",
  },
  product_grid: {
    variable: "productos_recomendados_edad_html",
    bg_color: "#ffffff",
    btn_color: "#f97316",
    padding_y: "16",
    padding_x: "0",
  },
  timer: {
    timer_mode: "relativo",
    duration_hours: "24",
    target_date: "",
    title: "¡La oferta termina en!",
    subtitle: "Aprovecha antes de que sea tarde",
    design: "clasico",
    bg_color: "#111111",
    accent_color: "#682ae7",
    text_color: "#ffffff",
    show_seconds: true,
    label_days: "DÍAS",
    label_hours: "HRS",
    label_minutes: "MIN",
    label_seconds: "SEG",
  },
};

const PALETTE: { type: BlockType; label: string; sub: string }[] = [
  { type: "header",  label: "Encabezado",  sub: "Logo + enlace" },
  { type: "text",    label: "Texto",        sub: "Párrafo HTML" },
  { type: "image",   label: "Imagen",       sub: "Banner / foto" },
  { type: "button",  label: "Botón CTA",    sub: "Llamada a acción" },
  { type: "product", label: "Producto",     sub: "Imagen + precio" },
  { type: "coupon",  label: "Cupón",        sub: "Código descuento" },
  { type: "product_grid", label: "Grilla productos", sub: "Recomendados / historial" },
  { type: "divider", label: "Divisor",      sub: "Línea separadora" },
  { type: "spacer",  label: "Espaciado",    sub: "Espacio en blanco" },
  { type: "timer",   label: "Timer",        sub: "Cuenta regresiva" },
];

const FAV_KEY = "hl_template_favorites";

function migrateLocalFavorites(): FavoriteBlock[] | null {
  try {
    const raw = localStorage.getItem(FAV_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Block[];
    if (!Array.isArray(parsed) || parsed.length === 0) return null;
    return parsed.map((f, i) => ({
      id: -(i + 1),
      name: f._favName || PALETTE.find((x) => x.type === f.type)?.label || f.type,
      block_type: f.type,
      props: f.props,
      sort_order: 1000 + i * 10,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }));
  } catch {
    return null;
  }
}

function clearLocalFavorites() {
  try { localStorage.removeItem(FAV_KEY); } catch { /* noop */ }
}

// ── HTML → Blocks parser ───────────────────────────────────────────────────────
export function htmlToBlocks(htmlStr: string): Block[] {
  if (typeof window === "undefined") return [];
  let counter = Date.now();
  const uid = (t: string) => `${t}_${counter++}`;

  // ── Helpers ────────────────────────────────────────────────────────────────
  function attr(el: Element, a: string) { return el.getAttribute(a) || ""; }
  function css(el: Element, prop: string): string {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return ((el as HTMLElement).style as any)?.[prop] as string || "";
  }
  function rgb2hex(s: string): string {
    const m = s.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (!m) return s;
    return "#" + [m[1], m[2], m[3]].map((n) => (+n).toString(16).padStart(2, "0")).join("");
  }
  function normColor(s: string): string { return s.startsWith("rgb") ? rgb2hex(s) : s || "#ffffff"; }
  function textProps(content: string, extra: Record<string, string | number | boolean> = {}) {
    return {
      ...DEFAULTS.text,
      content,
      text_color: extractTextColorFromHtml(content, "#222222"),
      ...extra,
    };
  }
  function bgColor(el: Element): string {
    let cur: Element | null = el;
    while (cur && cur.tagName !== "HTML") {
      const bg = css(cur, "backgroundColor") || css(cur, "background");
      if (bg && bg !== "transparent" && !bg.startsWith("rgba(0, 0, 0, 0)")) return normColor(bg);
      const bga = cur.getAttribute("bgcolor");
      if (bga) return bga;
      cur = cur.parentElement;
    }
    return "#ffffff";
  }
  // Clean up Klaviyo/MJML inner HTML — strip table wrappers, keep text+anchors
  function cleanKlaviyoText(el: Element): string {
    // Return inner HTML but clean up excessive nesting from table-based layout
    const clone = el.cloneNode(true) as Element;
    // Remove MSO conditional comments and empty spans
    clone.querySelectorAll("[style*='mso-'], [class*='mso']").forEach((e) => e.remove());
    return clone.innerHTML.trim();
  }

  try {
    const doc = new DOMParser().parseFromString(htmlStr, "text/html");

    // ── Detect template type ────────────────────────────────────────────────
    const isKlaviyo =
      !!doc.querySelector("td.kl-text, td.kl-image, .kl-header-link-bar, .kl-product, [class*='component-wrapper']");
    const hasCssClasses =
      !isKlaviyo && !!doc.querySelector(".header, .hero, .container, .wrapper, .cta-btn, .coupon-section");

    // ════════════════════════════════════════════════════════════════════════
    // KLAVIYO / MJML PARSER
    // Uses semantic CSS classes to find blocks in document order.
    // ════════════════════════════════════════════════════════════════════════
    if (isKlaviyo) {
      const blocks: Block[] = [];
      const processed = new WeakSet<Element>();

      // Helper: extract one product block from a kl-product-cell-stack element
      const extractProduct = (cell: Element, cellBg: string): void => {
        const cellImgs = Array.from(cell.querySelectorAll("img")).filter(
          (img) => !/tracking|pixel|spacer/i.test(attr(img, "src")) && attr(img, "src").trim() !== ""
        );
        const cellLinks = Array.from(cell.querySelectorAll("a[href]"));
        const cellText = (cell.textContent || "").trim();
        const priceMatch = cellText.match(/\$\s?[\d.,]+/);
        const cellImg = cellImgs[0];

        const titleEl =
          cell.querySelector("td[style*='font-weight:bold'], td[style*='font-weight: bold']") ||
          cell.querySelector(".kl-product-subblock td");
        const titleRaw = titleEl?.textContent?.trim() || "";
        const title = titleRaw && !/^\$/.test(titleRaw) ? titleRaw : cellText.slice(0, 80);

        const lnk = cellImg?.closest("a")?.getAttribute("href") || cellLinks[0]?.getAttribute("href") || "";

        const btnLink = cellLinks.find((a) => {
          const t = (a.textContent || "").trim();
          return t.length > 0 && t.length < 30 && !/^https?/i.test(t);
        });
        const buttonText = btnLink?.textContent?.trim() || "Comprar";

        const btnColorEl = cell.querySelector("[bgcolor]");
        const btnColorAttr = btnColorEl ? attr(btnColorEl, "bgcolor") : "";
        const btnColorStyle = !btnColorAttr ? (() => {
          const bgEl = cell.querySelector("[style*='background:#'], [style*='background: #']");
          const m = bgEl ? attr(bgEl, "style").match(/background(?:-color)?:\s*(#[0-9a-fA-F]{3,8})/) : null;
          return m ? m[1] : "";
        })() : "";
        const buttonColor = btnColorAttr || btnColorStyle || "#111111";

        if (blocks.some((b) => b.type === "product" && b.props.url === lnk && lnk)) return;
        if (cellImg || priceMatch) {
          blocks.push({
            id: uid("product"), type: "product", props: {
              ...DEFAULTS.product, title, price: priceMatch?.[0] || "",
              image_url: cellImg ? attr(cellImg, "src") : "",
              url: lnk, button_text: buttonText, button_color: buttonColor, bg_color: cellBg,
            },
          });
        }
      };

      // Collect all semantic Klaviyo elements in DOM order.
      // .kl-product-cell-stack is included as a fallback: if the parent div.kl-product
      // is not found or fails to locate child cells, the cells are processed directly.
      const semanticSelector =
        ".kl-header-link-bar, td.kl-image, td.kl-text, table.kl-product, div.kl-product, .kl-product-cell-stack";
      const allSemantic = Array.from(doc.querySelectorAll(semanticSelector));

      for (const el of allSemantic) {
        // Skip if already handled as part of an ancestor
        let skip = false;
        let p: Element | null = el.parentElement;
        while (p) { if (processed.has(p)) { skip = true; break; } p = p.parentElement; }
        if (skip) continue;

        // Skip invisible/hidden MSO duplicate elements
        const elStyle = attr(el, "style");
        if (/opacity:\s*0|display:\s*none|max-height:\s*0/i.test(elStyle)) continue;
        if (attr(el, "role") === "presentation" && /opacity:\s*0/i.test(elStyle)) continue;

        processed.add(el);
        const text = (el.textContent || "").trim();
        const imgs = Array.from(el.querySelectorAll("img")).filter(
          (img) => !/tracking|pixel|spacer/i.test(attr(img, "src"))
        );
        const links = Array.from(el.querySelectorAll("a[href]"));
        const bg = bgColor(el);
        const elCls = attr(el, "class");

        // ── kl-header-link-bar → Header (logo) or Button (CTA bar) ──────
        if (/kl-header-link-bar/.test(elCls)) {
          // Filter out imgs with empty/missing src (MSO placeholders)
          const realImgs = imgs.filter((i) => attr(i, "src").trim() !== "");
          const logoImg = realImgs.find((i) => /logo|brand/i.test(attr(i, "src") + attr(i, "alt"))) || realImgs[0];
          if (logoImg) {
            const w = attr(logoImg, "width") || attr(logoImg, "height") || "160";
            const wNum = parseInt(w, 10);
            const isWideBanner = (!isNaN(wNum) && wNum >= 300) || /width\s*:\s*100%/i.test(attr(logoImg, "style"));
            const lnk = logoImg.closest("a")?.getAttribute("href") || links[0]?.getAttribute("href") || "https://www.happylapiz.cl";
            if (isWideBanner) {
              // Wide image in kl-header-link-bar → full-width image block, not a constrained logo
              blocks.push({ id: uid("image"), type: "image", props: { ...DEFAULTS.image, src: attr(logoImg, "src"), alt: attr(logoImg, "alt"), link: lnk, bg_color: bg } });
            } else {
              blocks.push({ id: uid("header"), type: "header", props: { ...DEFAULTS.header, logo_url: attr(logoImg, "src"), logo_width: w, link: lnk, bg_color: bg } });
            }
          } else if (links.length > 0) {
            // No logo → this is a CTA button bar (e.g. "Finaliza tu compra")
            const a = links[0];
            const btnText = (a.textContent || "").trim();
            // bg comes from the parent td with inline background-color
            blocks.push({ id: uid("button"), type: "button", props: { ...DEFAULTS.button, text: btnText || "Ver más", url: attr(a, "href"), bg_color: bg !== "#ffffff" ? bg : "#111111", text_color: normColor(css(a, "color") || "#ffffff"), full_width: true, border_radius: "0" } });
          }
          continue;
        }

        // ── td.kl-image → Header (small/logo image) or Image ──────────────
        if (/\bkl-image\b/.test(elCls)) {
          const img = imgs[0];
          if (img) {
            // 1. Try img width attribute first
            let wAttr = attr(img, "width");
            // 2. Fallback: find width from td.kl-img-base-auto-width or similar wrapper
            if (!wAttr || !/^\d+$/.test(wAttr.trim())) {
              const autoTd = el.querySelector("[class*='kl-img'], [style*='width']");
              if (autoTd) {
                const tdStyle = attr(autoTd, "style");
                const m = tdStyle.match(/(?:^|;)\s*width\s*:\s*(\d+)px/);
                if (m) wAttr = m[1];
                else {
                  const tdW = attr(autoTd, "width");
                  if (tdW && /^\d+$/.test(tdW)) wAttr = tdW;
                }
              }
            }
            // 3. Fallback: check img style
            if (!wAttr || !/^\d+$/.test(wAttr.trim())) {
              const m = attr(img, "style").match(/width\s*:\s*(\d+)px/);
              if (m) wAttr = m[1];
            }
            const wNum = (wAttr && /^\d+$/.test(wAttr.trim())) ? parseInt(wAttr.trim(), 10) : NaN;

            // Logo detection: BOTH small width AND logo-like src/alt OR colored background.
            // A content image that happens to be small should NOT become a header block.
            const srcAlt = (attr(img, "src") + " " + attr(img, "alt")).toLowerCase();
            const bgNorm = bg.toLowerCase().replace(/\s/g, "");
            const bgIsColored = bgNorm !== "#ffffff" && bgNorm !== "#fff" && bgNorm !== "white" && bgNorm !== "" && !/^#f[ef][ef][ef][ef]?$/i.test(bgNorm);
            const looksLikeLogo = /logo|brand|hl[-_]|lapiz/i.test(srcAlt);
            const isLogo = !isNaN(wNum) && wNum <= 200 && (bgIsColored || looksLikeLogo);

            // Image alignment from kl-image td
            const imgAlign = attr(el, "align") || "center";

            if (isLogo) {
              blocks.push({ id: uid("header"), type: "header", props: { ...DEFAULTS.header, logo_url: attr(img, "src"), logo_width: wAttr || "160", link: img.closest("a")?.getAttribute("href") || "https://www.happylapiz.cl", bg_color: bg } });
            } else {
              blocks.push({ id: uid("image"), type: "image", props: { ...DEFAULTS.image, src: attr(img, "src"), alt: attr(img, "alt"), link: img.closest("a")?.getAttribute("href") || "", bg_color: bg, width: (!isNaN(wNum) && wNum < 560) ? String(wNum) : "", align: imgAlign } });
            }
          }
          continue;
        }

        // ── td.kl-text → Text or Button ──────────────────────────────────
        if (/\bkl-text\b/.test(elCls)) {

          // If block contains only a single anchor with short text → Button
          const nonSpaceText = text.replace(/\s| /g, "");
          const isCtaOnly = links.length === 1 && imgs.length === 0 && nonSpaceText.length < 80
            && nonSpaceText.length > 0;
          if (isCtaOnly) {
            const a = links[0];
            const href = attr(a, "href");
            // Detect button color from nested table/td with bgcolor
            const bgEl = el.querySelector("[bgcolor], [style*='background']");
            const btnBg = (bgEl ? attr(bgEl, "bgcolor") || css(bgEl, "backgroundColor") : "") || "#111111";
            const btnColor = css(a, "color") || "#ffffff";
            blocks.push({ id: uid("button"), type: "button", props: { ...DEFAULTS.button, text: text || "Ver más", url: href, bg_color: normColor(btnBg), text_color: normColor(btnColor) } });
          } else if (nonSpaceText.length > 0) {
            // Extract padding from Klaviyo inline style (e.g. padding-top:9px;padding-right:18px)
            const elStyle = attr(el, "style");
            const parsePad = (prop: string, fallback: number) => {
              const m = elStyle.match(new RegExp(prop + "\\s*:\\s*(\\d+)px"));
              return m ? parseInt(m[1], 10) : fallback;
            };
            const py = Math.round((parsePad("padding-top", 9) + parsePad("padding-bottom", 9)) / 2);
            const px = Math.round((parsePad("padding-right", 18) + parsePad("padding-left", 18)) / 2);
            blocks.push({ id: uid("text"), type: "text", props: textProps(cleanKlaviyoText(el), { bg_color: bg, padding_y: String(py), padding_x: String(px) }) });
          }
          continue;
        }

        // ── div/table.kl-product → iterate child cells ────────────────────
        if (/\bkl-product\b/.test(elCls)) {
          const cells = Array.from(el.querySelectorAll(".kl-product-cell-stack"));
          // If no cells found as descendants, individual .kl-product-cell-stack
          // elements in allSemantic will handle products directly (ancestor check
          // won't block them since they're not inside this processed element).
          for (const cell of cells) extractProduct(cell, bg);
          continue;
        }

        // ── .kl-product-cell-stack → single product (fallback / direct match) ──
        // Reached when no ancestor div.kl-product was processed (cells are
        // siblings of div.kl-product in the DOM, or div.kl-product was absent).
        if (/\bkl-product-cell-stack\b/.test(elCls)) {
          extractProduct(el, bg);
          continue;
        }
      }

      return blocks;
    }

    // ════════════════════════════════════════════════════════════════════════
    // CSS-CLASS BASED PARSER (e.g. template 3: .header, .hero, .container)
    // ════════════════════════════════════════════════════════════════════════
    if (hasCssClasses) {
      const blocks: Block[] = [];
      const container = doc.querySelector(".container, .wrapper, [class*='container']") || doc.body;

      const sections = Array.from(container.children).filter(
        (el) => !["STYLE", "SCRIPT", "HEAD"].includes(el.tagName)
      );

      for (const sec of sections) {
        const cls = attr(sec, "class");
        const text = (sec.textContent || "").trim();
        const imgs = Array.from(sec.querySelectorAll("img"));
        const links = Array.from(sec.querySelectorAll("a[href]"));
        const bg = bgColor(sec);

        if (!text && imgs.length === 0) continue;

        // Header
        if (/header|logo/i.test(cls)) {
          const img = imgs[0];
          if (img) {
            const lnk = img.closest("a")?.getAttribute("href") || links[0]?.getAttribute("href") || "";
            blocks.push({ id: uid("header"), type: "header", props: { ...DEFAULTS.header, logo_url: attr(img, "src"), logo_width: attr(img, "width") || "160", link: lnk, bg_color: bg } });
          }
          continue;
        }

        // CTA button
        if (/btn|button|cta/i.test(cls) || (links.length === 1 && imgs.length === 0 && text.length < 80)) {
          if (links.length === 1) {
            const a = links[0];
            const aBg = normColor(css(a, "backgroundColor") || css(sec, "backgroundColor") || "#111111");
            const aColor = normColor(css(a, "color") || "#ffffff");
            blocks.push({ id: uid("button"), type: "button", props: { ...DEFAULTS.button, text: text || "Ver más", url: attr(a, "href"), bg_color: aBg, text_color: aColor } });
            continue;
          }
        }

        // Coupon
        if (/coupon/i.test(cls) || text.includes("coupon_code")) {
          const codeEl = sec.querySelector(".coupon-code, [class*='coupon-code']") || sec;
          blocks.push({ id: uid("coupon"), type: "coupon", props: { ...DEFAULTS.coupon, code: text.includes("coupon_code") ? "{{ coupon_code }}" : codeEl.textContent?.trim() || "{{ coupon_code }}", bg_color: bg } });
          continue;
        }

        // Single image
        if (imgs.length === 1 && text.replace(/\s/g, "").length < 20) {
          const img = imgs[0];
          blocks.push({ id: uid("image"), type: "image", props: { ...DEFAULTS.image, src: attr(img, "src"), alt: attr(img, "alt"), link: img.closest("a")?.getAttribute("href") || "", bg_color: bg } });
          continue;
        }

        // Text (catch-all)
        const content = sec.innerHTML.trim();
        if (content && text.replace(/\s/g, "").length > 0) {
          blocks.push({ id: uid("text"), type: "text", props: textProps(content, { bg_color: bg }) });
        }
      }
      return blocks;
    }

    // ════════════════════════════════════════════════════════════════════════
    // DIV-BASED INLINE STYLE PARSER (e.g. template 1: nested divs with style="...")
    // ════════════════════════════════════════════════════════════════════════
    {
      const blocks: Block[] = [];

      // Find the main max-width container
      const container =
        doc.querySelector("[style*='max-width']") ||
        doc.querySelector("[style*='max-width']") ||
        doc.body;

      let sections = Array.from(container.children).filter(
        (el) => !["STYLE", "SCRIPT"].includes(el.tagName)
      );
      if (sections.length === 1) {
        const inner = Array.from(sections[0].children).filter(
          (el) => !["STYLE", "SCRIPT"].includes(el.tagName)
        );
        if (inner.length > 1) sections = inner;
      }

      function classifySection(sec: Element): void {
        const text = (sec.textContent || "").trim();
        const imgs = Array.from(sec.querySelectorAll("img"));
        const links = Array.from(sec.querySelectorAll("a[href]"));
        const bg = bgColor(sec);
        const secStyle = attr(sec, "style");

        if (!text && imgs.length === 0) return;

        // Single image → header or image
        if (imgs.length === 1 && text.replace(/\s/g, "").length < 25) {
          const img = imgs[0];
          const src = attr(img, "src");
          const w = attr(img, "width") || "160";
          const lnk = img.closest("a")?.getAttribute("href") || links[0]?.getAttribute("href") || "";
          const seemsLogo = /logo|brand/i.test(src) || parseInt(w) < 300;
          if (seemsLogo) {
            blocks.push({ id: uid("header"), type: "header", props: { ...DEFAULTS.header, logo_url: src, logo_width: w, link: lnk, bg_color: bg } });
          } else {
            blocks.push({ id: uid("image"), type: "image", props: { ...DEFAULTS.image, src, alt: attr(img, "alt"), link: lnk, bg_color: bg } });
          }
          return;
        }

        // Standalone image
        if (imgs.length === 1 && links.length === 1 && text.replace(/[^a-z0-9]/gi, "").length < 30) {
          const img = imgs[0];
          blocks.push({ id: uid("image"), type: "image", props: { ...DEFAULTS.image, src: attr(img, "src"), alt: attr(img, "alt"), link: links[0].getAttribute("href") || "", bg_color: bg } });
          return;
        }

        // Coupon
        if (text.includes("coupon_code") || /cupón|código descuento/i.test(text)) {
          blocks.push({ id: uid("coupon"), type: "coupon", props: { ...DEFAULTS.coupon, code: "{{ coupon_code }}", bg_color: bg } });
          return;
        }

        // Divider
        if (sec.querySelector("hr")) {
          blocks.push({ id: uid("divider"), type: "divider", props: { ...DEFAULTS.divider } });
          return;
        }

        // Section containing a grid of product links — process children individually
        const isGrid = /flex|grid/i.test(secStyle) && links.length >= 2;
        if (isGrid) {
          Array.from(sec.children).forEach(classifySection);
          return;
        }

        // Product card (has image + price)
        const priceMatch = text.match(/\$\s?[\d.,]+/);
        if (imgs.length >= 1 && priceMatch) {
          const img = imgs[0];
          const titleEl = sec.querySelector("p[style*='font-weight:700'], p[style*='font-weight: 700'], strong");
          const lnk = img.closest("a")?.getAttribute("href") || links[0]?.getAttribute("href") || "";
          if (blocks.some((b) => b.type === "product" && b.props.url === lnk && lnk)) return;
          blocks.push({
            id: uid("product"), type: "product", props: {
              ...DEFAULTS.product,
              title: titleEl?.textContent?.trim() || text.slice(0, 60),
              price: priceMatch[0],
              image_url: attr(img, "src"),
              url: lnk,
              bg_color: bg,
            },
          });
          return;
        }

        // Single styled link → button
        if (links.length === 1 && imgs.length === 0 && text.length < 100) {
          const a = links[0] as HTMLAnchorElement;
          const aBg = normColor(css(a, "backgroundColor") || css(sec, "backgroundColor") || "");
          if (aBg && aBg !== "#ffffff") {
            blocks.push({ id: uid("button"), type: "button", props: { ...DEFAULTS.button, text: text || "Ver más", url: attr(a, "href"), bg_color: aBg, text_color: normColor(css(a, "color") || "#ffffff") } });
            return;
          }
        }

        // Text block
        const content = sec.innerHTML.trim();
        if (content && text.replace(/\s/g, "").length > 0) {
          blocks.push({ id: uid("text"), type: "text", props: textProps(content, { bg_color: bg }) });
        }
      }

      sections.forEach(classifySection);

      // Last-resort fallback: wrap the entire body content as a single text block.
      // Covers plain-text HTML (only <p> tags, no block structure recognised above).
      if (blocks.length === 0) {
        const bodyContent = container.innerHTML.trim();
        if (bodyContent) {
          blocks.push({
            id: uid("text"),
            type: "text",
            props: textProps(bodyContent, { bg_color: "#ffffff" }),
          });
        }
      }

      return blocks;
    }
  } catch {
    return [];
  }
}

// ── HTML generation ────────────────────────────────────────────────────────────
function priceHtml(price: string, compareAt: string): string {
  if (!compareAt) {
    return `<p style="margin:0 0 10px;font-size:19px;font-weight:800;color:#111;font-family:-apple-system,sans-serif;">${price}</p>`;
  }
  return `<p style="margin:0 0 10px;">
  <span style="font-size:14px;color:#9ca3af;text-decoration:line-through;font-family:-apple-system,sans-serif;margin-right:8px;">${compareAt}</span>
  <span style="font-size:19px;font-weight:800;color:#e53e3e;font-family:-apple-system,sans-serif;">${price}</span>
</p>`;
}

function blockHtml(block: Block): string {
  const p = block.props;
  switch (block.type) {
    case "header":
      return `<div style="background:${p.bg_color};padding:20px 32px;text-align:center;border-bottom:1px solid #f3f4f6;">
  <a href="${p.link}" style="display:inline-block;text-decoration:none;">
    <img src="${p.logo_url}" alt="Happy Lápiz" width="${p.logo_width}" style="height:auto;display:block;margin:0 auto;" />
  </a>
</div>`;

    case "text": {
      const ff = (p.font_family as string) || "'Helvetica Neue', Arial, sans-serif";
      const tc = (p.text_color as string) || "#222222";
      return `<div style="background:${p.bg_color};padding:${p.padding_y}px ${p.padding_x}px;font-family:${ff};color:${tc};word-break:break-word;overflow-wrap:break-word;">
  ${p.content}
</div>`;
    }

    case "image": {
      const wPx = p.width ? parseInt(p.width as string, 10) : 0;
      const isFull = !wPx || wPx >= 560;
      const rStr = p.border_radius && p.border_radius !== "0" ? `border-radius:${p.border_radius}px;` : "";
      const imgStyle = isFull
        ? `width:100%;height:auto;display:block;${rStr}`
        : `width:${wPx}px;max-width:100%;height:auto;display:inline-block;${rStr}`;
      const wrapStyle = isFull
        ? `background:${p.bg_color};`
        : `background:${p.bg_color};text-align:${p.align || "center"};`;
      const imgTag = `<img src="${p.src}" alt="${p.alt}" width="${isFull ? "600" : wPx}" style="${imgStyle}" />`;
      return `<div style="${wrapStyle}">
  ${p.link ? `<a href="${p.link}" style="display:${isFull ? "block" : "inline-block"};">${imgTag}</a>` : imgTag}
</div>`;
    }

    case "button": {
      const align = p.align === "left" ? "left" : p.align === "right" ? "right" : "center";
      const ff = (p.font_family as string) || "'Helvetica Neue', Arial, sans-serif";
      const ls = p.letter_spacing ? `letter-spacing:${p.letter_spacing}px;` : "";
      if (p.full_width) {
        // Full-width CTA bar (like Klaviyo kl-header-link-bar)
        return `<div style="background:${p.bg_color};padding:12px 0;text-align:center;">
  <a href="${p.url}" style="color:${p.text_color};font-size:${p.font_size}px;font-weight:400;text-decoration:none;font-family:${ff};${ls}display:inline-block;padding:4px 8px;">
    ${p.text}
  </a>
</div>`;
      }
      return `<div style="padding:16px 32px;text-align:${align};background:#ffffff;">
  <a href="${p.url}" style="display:inline-block;background:${p.bg_color};color:${p.text_color};font-size:${p.font_size}px;font-weight:400;padding:10px 24px;border-radius:${p.border_radius}px;text-decoration:none;font-family:${ff};${ls}">
    ${p.text}
  </a>
</div>`;
    }

    case "product": {
      const font = "'Helvetica Neue', Arial, sans-serif";
      const saleColor = (p.price_color as string) || "#e53e3e";
      const priceInline = (p.compare_at_price as string)
        ? `<p style="margin:0 0 5px;text-align:center;"><span style="font-size:13px;color:#9ca3af;text-decoration:line-through;font-family:${font};margin-right:6px;">${p.compare_at_price}</span><span style="font-size:14px;font-weight:bold;color:${saleColor};font-family:${font};">${p.price}</span></p>`
        : `<p style="margin:0 0 5px;font-size:14px;font-weight:normal;color:${saleColor};font-family:${font};text-align:center;">${p.price}</p>`;
      return `<div style="background:${p.bg_color};padding:9px;text-align:center;">
  ${p.image_url ? `<a href="${p.url}" style="display:block;text-decoration:none;"><img src="${p.image_url}" alt="${p.title}" style="display:block;margin:0 auto 8px;max-width:100%;max-height:125px;width:auto;" /></a>` : ""}
  <p style="margin:0 0 5px;font-size:14px;font-weight:bold;color:#222222;font-family:${font};text-align:center;">${p.title}</p>
  ${priceInline}
  ${p.description ? `<p style="margin:0 0 8px;font-size:13px;color:#666666;font-family:${font};text-align:center;">${p.description}</p>` : ""}
  ${p.show_button !== false ? `<a href="${p.url}" style="display:inline-block;margin-top:9px;background:${p.button_color};color:#ffffff;font-size:16px;font-weight:400;padding:10px 10px;border-radius:5px;text-decoration:none;font-family:${font};">${p.button_text}</a>` : ""}
</div>`;
    }

    case "coupon":
      return `<div style="background:${p.bg_color};padding:28px 32px;text-align:center;">
  <p style="margin:0 0 14px;font-size:16px;font-weight:600;color:${p.text_color};font-family:-apple-system,sans-serif;">${p.title}</p>
  <div style="display:inline-block;border:2px dashed ${p.border_color};border-radius:10px;padding:14px 32px;background:#ffffff;">
    <span style="font-size:24px;font-weight:800;letter-spacing:4px;color:${p.text_color};font-family:monospace;">${p.code}</span>
  </div>
  ${p.subtitle ? `<p style="margin:12px 0 0;font-size:13px;color:#888;font-family:-apple-system,sans-serif;">${p.subtitle}</p>` : ""}
</div>`;

    case "divider":
      return `<div style="padding:${p.padding_y}px 32px;background:#ffffff;">
  <div style="height:${p.thickness}px;background:${p.color};"></div>
</div>`;

    case "spacer":
      return `<div style="height:${p.height}px;background:${p.bg_color};line-height:${p.height}px;font-size:1px;">&nbsp;</div>`;

    case "product_grid":
      return `<div style="background:${p.bg_color};padding:${p.padding_y}px ${p.padding_x}px;">{{ ${p.variable} }}</div>`;

    case "timer": {
      const tf = "'Helvetica Neue', Arial, sans-serif";
      const isRelativo = (p.timer_mode as string) === "relativo";

      // Relative mode: emit a placeholder that the backend resolves at send time
      if (isRelativo) {
        const cfg = {
          design:        (p.design        as string) || "clasico",
          duration_hours: parseFloat((p.duration_hours as string) || "24") || 24,
          bg_color:      (p.bg_color      as string) || "#111111",
          accent_color:  (p.accent_color  as string) || "#682ae7",
          text_color:    (p.text_color    as string) || "#ffffff",
          title:         (p.title         as string) || "",
          subtitle:      (p.subtitle      as string) || "",
          show_seconds:  p.show_seconds !== false,
          label_days:    (p.label_days    as string) || "DÍAS",
          label_hours:   (p.label_hours   as string) || "HRS",
          label_minutes: (p.label_minutes as string) || "MIN",
          label_seconds: (p.label_seconds as string) || "SEG",
        };
        return `<!-- HOTBOAT_TIMER_RELATIVE:${JSON.stringify(cfg)} -->`;
      }

      const target = p.target_date ? new Date(p.target_date as string) : new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
      const diff = Math.max(0, target.getTime() - Date.now());
      const pad2 = (n: number) => String(n).padStart(2, "0");
      const tDays = pad2(Math.floor(diff / 86400000));
      const tHrs  = pad2(Math.floor((diff % 86400000) / 3600000));
      const tMins = pad2(Math.floor((diff % 3600000) / 60000));
      const tSecs = pad2(Math.floor((diff % 60000) / 1000));
      const tbg     = (p.bg_color     as string) || "#111111";
      const tacc    = (p.accent_color as string) || "#682ae7";
      const ttc     = (p.text_color   as string) || "#ffffff";
      const tdesign = (p.design       as string) || "clasico";
      const ttitle  = (p.title        as string) || "";
      const tsub    = (p.subtitle     as string) || "";
      const tUnits  = [
        { val: tDays, label: (p.label_days    as string) || "DÍAS" },
        { val: tHrs,  label: (p.label_hours   as string) || "HRS"  },
        { val: tMins, label: (p.label_minutes as string) || "MIN"  },
        ...(p.show_seconds !== false ? [{ val: tSecs, label: (p.label_seconds as string) || "SEG" }] : []),
      ];

      if (tdesign === "clasico") {
        const cells = tUnits.map((u, i) =>
          `${i > 0 ? `<td style="padding:0 6px;vertical-align:middle;"><span style="font-size:28px;color:rgba(255,255,255,0.3);font-weight:300;font-family:${tf};">:</span></td>` : ""}<td style="text-align:center;padding:0 4px;"><div style="background:${tacc};border-radius:10px;padding:14px 10px;min-width:58px;display:inline-block;"><div style="font-size:38px;font-weight:900;color:${ttc};line-height:1;font-family:${tf};letter-spacing:-1px;">${u.val}</div><div style="font-size:10px;color:rgba(255,255,255,0.65);margin-top:6px;letter-spacing:2px;font-family:${tf};">${u.label}</div></div></td>`
        ).join("");
        return `<div style="background:${tbg};padding:32px 24px;text-align:center;">
  ${ttitle ? `<p style="margin:0 0 20px;font-size:18px;font-weight:700;color:${ttc};font-family:${tf};">${ttitle}</p>` : ""}
  <table role="presentation" width="auto" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;"><tr>${cells}</tr></table>
  ${tsub ? `<p style="margin:20px 0 0;font-size:13px;color:rgba(255,255,255,0.5);font-family:${tf};">${tsub}</p>` : ""}
</div>`;
      }

      if (tdesign === "minimal") {
        const cells = tUnits.map((u, i) =>
          `${i > 0 ? `<td style="padding:0 4px;vertical-align:top;padding-top:6px;"><span style="font-size:36px;color:${tacc};font-weight:300;font-family:${tf};opacity:0.4;">:</span></td>` : ""}<td style="text-align:center;padding:0 12px;"><div style="font-size:52px;font-weight:900;color:${tacc};line-height:1;font-family:${tf};">${u.val}</div><div style="font-size:11px;color:#9ca3af;margin-top:6px;letter-spacing:2px;font-family:${tf};">${u.label}</div></td>`
        ).join("");
        return `<div style="background:${tbg};padding:32px 24px;text-align:center;border-top:3px solid ${tacc};">
  ${ttitle ? `<p style="margin:0 0 24px;font-size:16px;font-weight:600;color:#222;font-family:${tf};">${ttitle}</p>` : ""}
  <table role="presentation" width="auto" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;"><tr>${cells}</tr></table>
  ${tsub ? `<p style="margin:24px 0 0;font-size:13px;color:#6b7280;font-family:${tf};">${tsub}</p>` : ""}
</div>`;
      }

      if (tdesign === "urgencia") {
        const cells = tUnits.map((u, i) =>
          `${i > 0 ? `<td style="padding:0 5px;vertical-align:middle;"><span style="font-size:28px;color:rgba(255,255,255,0.4);font-family:${tf};">:</span></td>` : ""}<td style="text-align:center;padding:0 5px;"><div style="background:rgba(255,255,255,0.15);border:2px solid rgba(255,255,255,0.3);border-radius:8px;padding:12px 8px;min-width:56px;display:inline-block;"><div style="font-size:40px;font-weight:900;color:#ffffff;line-height:1;font-family:${tf};">${u.val}</div><div style="font-size:10px;color:rgba(255,255,255,0.7);margin-top:5px;letter-spacing:2px;font-family:${tf};">${u.label}</div></div></td>`
        ).join("");
        return `<div style="background:${tbg};padding:32px 24px;text-align:center;">
  ${ttitle ? `<p style="margin:0 0 16px;font-size:12px;font-weight:700;color:rgba(255,255,255,0.85);letter-spacing:3px;text-transform:uppercase;font-family:${tf};">&#9889; ${ttitle} &#9889;</p>` : ""}
  <table role="presentation" width="auto" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;"><tr>${cells}</tr></table>
  ${tsub ? `<p style="margin:20px 0 0;font-size:13px;color:rgba(255,255,255,0.7);font-family:${tf};">${tsub}</p>` : ""}
</div>`;
      }

      // elegante
      const cells = tUnits.map((u, i) =>
        `${i > 0 ? `<td style="padding:0 8px;vertical-align:top;padding-top:6px;"><span style="font-size:30px;color:${tacc};font-weight:200;font-family:${tf};opacity:0.4;">:</span></td>` : ""}<td style="text-align:center;padding:0 6px;"><div style="border:2px solid ${tacc};border-radius:12px;padding:14px 10px;min-width:62px;display:inline-block;background:#ffffff;"><div style="font-size:38px;font-weight:900;color:${tacc};line-height:1;font-family:${tf};">${u.val}</div><div style="font-size:10px;color:#9ca3af;margin-top:6px;letter-spacing:2px;font-family:${tf};">${u.label}</div></div></td>`
      ).join("");
      return `<div style="background:${tbg};padding:36px 24px;text-align:center;">
  ${ttitle ? `<p style="margin:0 0 6px;font-size:12px;font-weight:600;color:${tacc};letter-spacing:3px;text-transform:uppercase;font-family:${tf};">${ttitle}</p><div style="width:48px;height:2px;background:${tacc};margin:0 auto 20px;"></div>` : ""}
  <table role="presentation" width="auto" cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;"><tr>${cells}</tr></table>
  ${tsub ? `<p style="margin:24px 0 0;font-size:13px;color:#6b7280;font-family:${tf};">${tsub}</p>` : ""}
</div>`;
    }

    default:
      return "";
  }
}

// Renders 2–3 consecutive product blocks as a multi-column email row
function productRowHtml(products: Block[]): string {
  const n = products.length;
  const colPct = n === 2 ? "50%" : "33.333%";
  const bg = (products[0].props.bg_color as string) || "#ffffff";
  const font = "'Helvetica Neue',Arial,sans-serif";
  const cols = products.map((b) => {
    const p = b.props;
    const sc = (p.price_color as string) || "#e53e3e";
    const priceInline = p.compare_at_price
      ? `<p style="margin:0 0 5px;text-align:center;"><span style="font-size:13px;color:#9ca3af;text-decoration:line-through;font-family:${font};margin-right:6px;">${p.compare_at_price}</span><span style="font-size:14px;font-weight:bold;color:${sc};font-family:${font};">${p.price}</span></p>`
      : `<p style="margin:0 0 5px;font-size:14px;font-weight:normal;color:${sc};font-family:${font};text-align:center;">${p.price}</p>`;
    return `<td width="${colPct}" valign="top" style="padding:9px 9px;text-align:center;vertical-align:top;">
  ${p.image_url ? `<a href="${p.url}" style="display:block;text-decoration:none;"><img src="${p.image_url}" alt="${p.title}" style="display:block;margin:0 auto 8px;max-width:100%;max-height:125px;width:auto;" /></a>` : ""}
  <p style="margin:0 0 5px;font-size:14px;font-weight:bold;color:#222222;font-family:${font};text-align:center;">${p.title}</p>
  ${priceInline}
  ${p.show_button !== false ? `<a href="${p.url}" style="display:inline-block;margin-top:9px;background:${p.button_color};color:#ffffff;font-size:16px;font-weight:400;padding:10px 10px;border-radius:5px;text-decoration:none;font-family:${font};">${p.button_text}</a>` : ""}
</td>`;
  }).join("\n");
  return `<div style="background:${bg};padding:8px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
${cols}
  </tr></table>
</div>`;
}

export function blocksToHtml(blocks: Block[]): string {
  if (!blocks.length) return "";

  // Group consecutive product blocks (max 3 per row) for multi-column layout
  const groups: Array<Block | Block[]> = [];
  for (const block of blocks) {
    const last = groups[groups.length - 1];
    if (block.type === "product" && Array.isArray(last) && last.length < 3) {
      last.push(block);
    } else if (block.type === "product") {
      groups.push([block]);
    } else {
      groups.push(block);
    }
  }

  const bodyHtml = groups.map((g) => {
    if (Array.isArray(g)) return g.length === 1 ? blockHtml(g[0]) : productRowHtml(g);
    return blockHtml(g);
  }).join("\n");

  return `<!DOCTYPE html>
<html lang="es" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1.0" />
<meta http-equiv="X-UA-Compatible" content="IE=edge" />
<title>Email</title>
<style>
body { margin:0; padding:0; background:#ffffff; -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }
table, td { border-collapse:collapse; mso-table-lspace:0; mso-table-rspace:0; }
img { border:0; line-height:100%; outline:none; text-decoration:none; -ms-interpolation-mode:bicubic; display:block; max-width:100%; }
a { word-break:break-word; overflow-wrap:break-word; }
@media only screen and (max-width:600px) {
  .email-container { width:100% !important; max-width:100% !important; }
  .email-body td { padding-left:0 !important; padding-right:0 !important; }
}
</style>
</head>
<body style="margin:0;padding:0;background:#ffffff;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td align="center" style="padding:0;background:#ffffff;">
<div class="email-container" style="max-width:600px;width:100%;background:#ffffff;overflow:hidden;margin:0 auto;">
${bodyHtml}
</div>
</td></tr>
</table>
</body>
</html>`;
}

export function plainTextToHtml(text: string): string {
  const escaped = text
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" style="color:#2563eb;text-decoration:underline;">$1</a>')
    .split("\n\n")
    .map((para) => `<p style="margin:0 0 16px;font-size:15px;line-height:1.75;color:#333;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">${para.replace(/\n/g, "<br>")}</p>`)
    .join("\n");

  return `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1.0" />
<title>Email</title>
</head>
<body style="margin:0;padding:0;background:#ffffff;">
<div style="max-width:600px;margin:0 auto;padding:32px 24px;">
${escaped}
</div>
</body>
</html>`;
}

export function parseEditorState(raw: unknown): { blocks: Block[]; plainText: string; mode: "blocks" | "plain" } {
  if (Array.isArray(raw)) return { blocks: raw as Block[], plainText: "", mode: "blocks" };
  if (raw && typeof raw === "object" && (raw as Record<string, unknown>).mode === "plain") {
    return { blocks: [], plainText: String((raw as Record<string, unknown>).text || ""), mode: "plain" };
  }
  return { blocks: [], plainText: "", mode: "blocks" };
}

// Backwards compat alias
export function parseJsonBlocks(raw: unknown): Block[] {
  return parseEditorState(raw).blocks;
}

// ── Canvas block visual preview ────────────────────────────────────────────────
export function BlockPreview({ block, compact = false }: { block: Block; compact?: boolean }) {
  const p = block.props;
  const [imgError, setImgError] = useState(false);
  const logoUrl = p.logo_url as string | undefined;
  useEffect(() => { setImgError(false); }, [logoUrl]);

  const [timeLeft, setTimeLeft] = useState({ days: 0, hours: 0, minutes: 0, seconds: 0 });
  const timerTargetDate = block.type === "timer" ? (p.target_date as string) : "";
  const timerMode = block.type === "timer" ? (p.timer_mode as string) : "fijo";
  const timerDurationHours = block.type === "timer" ? (parseFloat(p.duration_hours as string) || 24) : 24;
  useEffect(() => {
    if (block.type !== "timer") return;
    const calc = () => {
      let t: Date;
      if (timerMode === "relativo") {
        t = new Date(Date.now() + timerDurationHours * 3600 * 1000);
      } else {
        t = timerTargetDate ? new Date(timerTargetDate) : new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
      }
      const diff = Math.max(0, t.getTime() - Date.now());
      return {
        days: Math.floor(diff / 86400000),
        hours: Math.floor((diff % 86400000) / 3600000),
        minutes: Math.floor((diff % 3600000) / 60000),
        seconds: Math.floor((diff % 60000) / 1000),
      };
    };
    setTimeLeft(calc());
    const id = setInterval(() => setTimeLeft(calc()), 1000);
    return () => clearInterval(id);
  }, [block.type, timerTargetDate, timerMode, timerDurationHours]);

  switch (block.type) {
    case "header":
      return (
        <div style={{ background: p.bg_color as string, padding: "14px 24px", textAlign: "center", borderBottom: "1px solid #f3f4f6" }}>
          {p.logo_url && !imgError
            ? <img
                src={p.logo_url as string}
                alt="logo"
                style={{ height: 40, maxWidth: "100%", objectFit: "contain", display: "block", margin: "0 auto" }}
                onError={() => setImgError(true)}
              />
            : <span style={{ fontWeight: 700, fontSize: 16, fontFamily: "system-ui", color: "#111" }}>Happy Lápiz</span>}
        </div>
      );
    case "text":
      return (
        <div
          style={{
            background: p.bg_color as string,
            padding: `${p.padding_y}px ${p.padding_x}px`,
            fontSize: 13,
            color: (p.text_color as string) || undefined,
            fontFamily: (p.font_family as string) || undefined,
          }}
          dangerouslySetInnerHTML={{ __html: p.content as string }}
        />
      );
    case "image": {
      const wPx = p.width ? parseInt(p.width as string, 10) : 0;
      const isFull = !wPx || wPx >= 560;
      const br = p.border_radius && p.border_radius !== "0" ? `${p.border_radius}px` : 0;
      return p.src
        ? <div style={{ background: p.bg_color as string, textAlign: isFull ? undefined : ((p.align || "center") as "center" | "left" | "right") }}>
            <img src={p.src as string} alt={p.alt as string}
              style={{ width: isFull ? "100%" : `${wPx}px`, maxWidth: "100%", height: "auto", display: isFull ? "block" : "inline-block", borderRadius: br }} />
          </div>
        : <div style={{ background: "#f9fafb", height: 90, display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: 12 }}>
            Añade URL de imagen
          </div>;
    }
    case "button": {
      const align = p.align === "left" ? "left" : p.align === "right" ? "right" : "center";
      const ls = p.letter_spacing ? `${p.letter_spacing}px` : "normal";
      if (p.full_width) {
        return (
          <div style={{ background: p.bg_color as string, padding: "12px 0", textAlign: "center" }}>
            <span style={{ color: p.text_color as string, fontSize: `${p.font_size}px`, fontWeight: 400, letterSpacing: ls }}>
              {p.text as string}
            </span>
          </div>
        );
      }
      return (
        <div style={{ padding: "14px 24px", textAlign: align as "center" | "left" | "right", background: "#ffffff" }}>
          <span style={{ display: "inline-block", background: p.bg_color as string, color: p.text_color as string, padding: "10px 24px", borderRadius: `${p.border_radius}px`, fontSize: `${p.font_size}px`, fontWeight: 400, letterSpacing: ls }}>
            {p.text as string}
          </span>
        </div>
      );
    }
    case "product": {
      // Shared vertical card layout (same for single and multi-column)
      const cardStyle: React.CSSProperties = { background: p.bg_color as string, padding: compact ? "12px 8px" : "14px 24px", textAlign: "center", height: "100%" };
      const imgH = compact ? 110 : 140;
      return (
        <div style={cardStyle}>
          {p.image_url
            ? <img src={p.image_url as string} alt="" style={{ width: "100%", maxHeight: imgH, objectFit: "cover", borderRadius: 6, display: "block", margin: "0 auto 8px" }} />
            : <div style={{ width: "100%", height: compact ? 90 : 110, background: "#f3f4f6", borderRadius: 6, marginBottom: 8, display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: 10 }}>Imagen</div>}
          <p style={{ margin: "0 0 3px", fontWeight: 700, fontSize: compact ? 12 : 14, lineHeight: 1.3, fontFamily: "'Helvetica Neue',Arial,sans-serif" }}>{p.title as string}</p>
          {p.compare_at_price
            ? <p style={{ margin: "0 0 8px" }}>
                <span style={{ fontSize: 11, color: "#9ca3af", textDecoration: "line-through", marginRight: 5 }}>{p.compare_at_price as string}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: (p.price_color as string) || "#e53e3e" }}>{p.price as string}</span>
              </p>
            : <p style={{ margin: "0 0 8px", fontWeight: 400, fontSize: compact ? 12 : 14, color: (p.price_color as string) || "#e53e3e" }}>{p.price as string}</p>}
          {p.show_button !== false && (
            <span style={{ background: p.button_color as string, color: "#fff", padding: compact ? "4px 12px" : "8px 18px", borderRadius: 5, fontSize: compact ? 10 : 13, fontWeight: 400, display: "inline-block" }}>{p.button_text as string}</span>
          )}
        </div>
      );
    }
    case "coupon":
      return (
        <div style={{ background: p.bg_color as string, padding: "16px 24px", textAlign: "center" }}>
          <p style={{ margin: "0 0 8px", fontWeight: 600, fontSize: 13, color: p.text_color as string }}>{p.title as string}</p>
          <div style={{ display: "inline-block", border: `2px dashed ${p.border_color}`, borderRadius: 8, padding: "8px 20px", background: "#fff" }}>
            <span style={{ fontFamily: "monospace", fontWeight: 800, fontSize: 18, letterSpacing: 3 }}>{p.code as string}</span>
          </div>
        </div>
      );
    case "divider":
      return (
        <div style={{ padding: `${p.padding_y}px 24px`, background: "#ffffff" }}>
          <div style={{ height: `${p.thickness}px`, background: p.color as string }} />
        </div>
      );
    case "spacer":
      return (
        <div style={{ height: Math.max(20, p.height as number), background: (p.bg_color || "#fff") as string, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <span style={{ fontSize: 11, color: "#d1d5db" }}>↕ {p.height}px</span>
        </div>
      );

    case "product_grid": {
      const varLabel: Record<string, string> = {
        "productos_recomendados_edad_html": "Recomendados por edad",
        "recommended_products_html": "Recomendados por compra",
        "productos_comprados_html": "Historial de compras",
      };
      const label = varLabel[p.variable as string] || String(p.variable);
      const placeholders = [
        { name: "Marcadores Happy Lápiz Set 12 colores", price: "$12.990" },
        { name: "Kit Lettering Completo Principiantes", price: "$24.990" },
        { name: "Cuaderno Bocetos A5", price: "$8.490" },
        { name: "Acuarelas 24 colores Premium", price: "$18.990" },
      ];
      return (
        <div style={{ background: (p.bg_color as string) || "#fff", padding: `${p.padding_y || 16}px ${p.padding_x || 0}px` }}>
          <div style={{ fontSize: 10, color: "#9ca3af", textAlign: "center", marginBottom: 10, fontFamily: "monospace" }}>
            {"{{ "}{p.variable as string}{" }}"}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {placeholders.map((prod, i) => (
              <div key={i} style={{ textAlign: "center", padding: 10, border: "1px dashed #e5e7eb", borderRadius: 10 }}>
                <div style={{ width: "100%", height: 90, backgroundColor: "#f3f4f6", borderRadius: 8, marginBottom: 8, display: "flex", alignItems: "center", justifyContent: "center", color: "#d1d5db", fontSize: 11 }}>imagen</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#111", lineHeight: 1.3, maxHeight: "3.9em", overflow: "hidden", marginBottom: 4 }}>{prod.name}</div>
                <div style={{ fontSize: 13, color: "#e85d04", fontWeight: 700, marginBottom: 6 }}>{prod.price}</div>
                <div style={{ display: "inline-block", background: "#f97316", color: "#fff", fontSize: 11, padding: "5px 12px", borderRadius: 12 }}>Ver producto →</div>
              </div>
            ))}
          </div>
          <div style={{ fontSize: 10, color: "#c4b5fd", textAlign: "center", marginTop: 8 }}>{label} · vista previa con productos de ejemplo</div>
        </div>
      );
    }

    case "timer": {
      const tdesign  = (p.design       as string) || "clasico";
      const tbg      = (p.bg_color     as string) || "#111111";
      const tacc     = (p.accent_color as string) || "#682ae7";
      const ttc      = (p.text_color   as string) || "#ffffff";
      const ttitle   = (p.title        as string) || "";
      const tsub     = (p.subtitle     as string) || "";
      const showSec  = p.show_seconds !== false;
      const pad2     = (n: number) => String(n).padStart(2, "0");
      const tUnits   = [
        { val: pad2(timeLeft.days),    label: (p.label_days    as string) || "DÍAS" },
        { val: pad2(timeLeft.hours),   label: (p.label_hours   as string) || "HRS"  },
        { val: pad2(timeLeft.minutes), label: (p.label_minutes as string) || "MIN"  },
        ...(showSec ? [{ val: pad2(timeLeft.seconds), label: (p.label_seconds as string) || "SEG" }] : []),
      ];

      const sepColor = tdesign === "clasico"
        ? "rgba(255,255,255,0.3)"
        : tdesign === "urgencia"
        ? "rgba(255,255,255,0.4)"
        : tacc;

      if (tdesign === "clasico") return (
        <div style={{ background: tbg, padding: "24px", textAlign: "center" }}>
          {ttitle && <p style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: ttc, fontFamily: "'Helvetica Neue',sans-serif" }}>{ttitle}</p>}
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 6 }}>
            {tUnits.map((u, i) => (
              <React.Fragment key={i}>
                {i > 0 && <span style={{ fontSize: 24, color: sepColor, fontWeight: 300 }}>:</span>}
                <div style={{ background: tacc, borderRadius: 8, padding: "12px 10px", minWidth: 52, textAlign: "center" }}>
                  <div style={{ fontSize: 32, fontWeight: 900, color: ttc, lineHeight: 1 }}>{u.val}</div>
                  <div style={{ fontSize: 9, color: "rgba(255,255,255,0.65)", marginTop: 5, letterSpacing: 2 }}>{u.label}</div>
                </div>
              </React.Fragment>
            ))}
          </div>
          {tsub && <p style={{ margin: "16px 0 0", fontSize: 12, color: "rgba(255,255,255,0.5)" }}>{tsub}</p>}
        </div>
      );

      if (tdesign === "minimal") return (
        <div style={{ background: tbg, padding: "24px", textAlign: "center", borderTop: `3px solid ${tacc}` }}>
          {ttitle && <p style={{ margin: "0 0 16px", fontSize: 14, fontWeight: 600, color: "#222", fontFamily: "'Helvetica Neue',sans-serif" }}>{ttitle}</p>}
          <div style={{ display: "flex", justifyContent: "center", alignItems: "flex-start", gap: 4 }}>
            {tUnits.map((u, i) => (
              <React.Fragment key={i}>
                {i > 0 && <span style={{ fontSize: 32, color: tacc, fontWeight: 300, opacity: 0.4, paddingTop: 2 }}>:</span>}
                <div style={{ textAlign: "center", padding: "0 8px" }}>
                  <div style={{ fontSize: 44, fontWeight: 900, color: tacc, lineHeight: 1 }}>{u.val}</div>
                  <div style={{ fontSize: 9, color: "#9ca3af", marginTop: 4, letterSpacing: 2 }}>{u.label}</div>
                </div>
              </React.Fragment>
            ))}
          </div>
          {tsub && <p style={{ margin: "16px 0 0", fontSize: 12, color: "#6b7280" }}>{tsub}</p>}
        </div>
      );

      if (tdesign === "urgencia") return (
        <div style={{ background: tbg, padding: "24px", textAlign: "center" }}>
          {ttitle && <p style={{ margin: "0 0 12px", fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,0.85)", letterSpacing: 3, textTransform: "uppercase" }}>⚡ {ttitle} ⚡</p>}
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 6 }}>
            {tUnits.map((u, i) => (
              <React.Fragment key={i}>
                {i > 0 && <span style={{ fontSize: 22, color: sepColor }}>:</span>}
                <div style={{ background: "rgba(255,255,255,0.15)", border: "2px solid rgba(255,255,255,0.3)", borderRadius: 8, padding: "10px 8px", minWidth: 52, textAlign: "center" }}>
                  <div style={{ fontSize: 34, fontWeight: 900, color: "#ffffff", lineHeight: 1 }}>{u.val}</div>
                  <div style={{ fontSize: 9, color: "rgba(255,255,255,0.7)", marginTop: 4, letterSpacing: 2 }}>{u.label}</div>
                </div>
              </React.Fragment>
            ))}
          </div>
          {tsub && <p style={{ margin: "14px 0 0", fontSize: 12, color: "rgba(255,255,255,0.7)" }}>{tsub}</p>}
        </div>
      );

      // elegante
      return (
        <div style={{ background: tbg, padding: "24px", textAlign: "center" }}>
          {ttitle && <>
            <p style={{ margin: "0 0 6px", fontSize: 10, fontWeight: 600, color: tacc, letterSpacing: 3, textTransform: "uppercase" }}>{ttitle}</p>
            <div style={{ width: 40, height: 2, background: tacc, margin: "0 auto 16px" }} />
          </>}
          <div style={{ display: "flex", justifyContent: "center", alignItems: "flex-start", gap: 8 }}>
            {tUnits.map((u, i) => (
              <React.Fragment key={i}>
                {i > 0 && <span style={{ fontSize: 28, color: tacc, fontWeight: 200, opacity: 0.4, paddingTop: 4 }}>:</span>}
                <div style={{ border: `2px solid ${tacc}`, borderRadius: 10, padding: "12px 10px", minWidth: 54, textAlign: "center", background: "#fff" }}>
                  <div style={{ fontSize: 32, fontWeight: 900, color: tacc, lineHeight: 1 }}>{u.val}</div>
                  <div style={{ fontSize: 9, color: "#9ca3af", marginTop: 4, letterSpacing: 2 }}>{u.label}</div>
                </div>
              </React.Fragment>
            ))}
          </div>
          {tsub && <p style={{ margin: "16px 0 0", fontSize: 12, color: "#6b7280" }}>{tsub}</p>}
        </div>
      );
    }

    default:
      return null;
  }
}

const LINK_STYLE = "color:#2a2ee7;text-decoration:underline;";

function promptTextLink(selectedFallback = "texto del enlace"): { href: string; label: string } | null {
  const href = window.prompt("URL del enlace:", "https://www.happylapiz.cl");
  if (!href?.trim()) return null;
  const label = window.prompt("Texto del enlace:", selectedFallback);
  if (!label?.trim()) return null;
  return { href: href.trim(), label: label.trim() };
}

function insertLinkHtml(label: string, href: string): string {
  const safeHref = href.replace(/"/g, "&quot;");
  return `<a href="${safeHref}" style="${LINK_STYLE}">${label}</a>`;
}

function insertLinkInHtmlString(value: string, start: number, end: number): string | null {
  const selected = value.slice(start, end);
  const picked = promptTextLink(selected || "texto del enlace");
  if (!picked) return null;
  return value.slice(0, start) + insertLinkHtml(picked.label, picked.href) + value.slice(end);
}

function insertLinkInContentEditable(container: HTMLElement | null): boolean {
  if (!container) return false;
  container.focus();
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return false;
  const range = sel.getRangeAt(0);
  const selectedText = range.toString();
  const picked = promptTextLink(selectedText || "texto del enlace");
  if (!picked) return false;

  const anchor = document.createElement("a");
  anchor.href = picked.href;
  anchor.style.cssText = LINK_STYLE;
  if (range.collapsed) {
    anchor.textContent = picked.label;
    range.insertNode(anchor);
    range.setStartAfter(anchor);
    range.collapse(true);
  } else {
    anchor.appendChild(range.extractContents());
    range.insertNode(anchor);
    range.selectNodeContents(anchor);
  }
  sel.removeAllRanges();
  sel.addRange(range);
  return true;
}

// ── Inline text editor (contentEditable) with rich-text toolbar ───────────────
function InlineTextEditor({
  content,
  style,
  onCommit,
}: {
  content: string;
  style: React.CSSProperties;
  onCommit: (html: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [, rerender] = useState(0);

  useEffect(() => {
    if (!ref.current) return;
    ref.current.innerHTML = content;
    ref.current.focus();
    const range = document.createRange();
    const sel = window.getSelection();
    range.selectNodeContents(ref.current);
    range.collapse(false);
    sel?.removeAllRanges();
    sel?.addRange(range);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function insertLink() {
    if (insertLinkInContentEditable(ref.current)) {
      rerender((n) => n + 1);
    }
  }

  function execFmt(cmd: string, value?: string) {
    ref.current?.focus();
    try { document.execCommand("styleWithCSS", false, "true"); } catch { /* noop */ }
    document.execCommand(cmd, false, value);
    rerender((n) => n + 1);
  }

  function applyInlineStyle(prop: string, value: string) {
    ref.current?.focus();
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    if (range.collapsed) {
      if (prop === "color" && ref.current) {
        ref.current.querySelectorAll("p, span, div, li, strong, em, b, i, h1, h2, h3, h4, a").forEach((el) => {
          (el as HTMLElement).style.color = value;
        });
        if (!ref.current.querySelector("p, span, div, li, h1, h2, h3, h4")) {
          ref.current.style.color = value;
        }
        rerender((n) => n + 1);
      } else if (prop === "color") {
        execFmt("foreColor", value);
      }
      return;
    }
    const span = document.createElement("span");
    (span.style as unknown as Record<string, string>)[prop] = value;
    // extractContents handles selections that cross element boundaries (unlike surroundContents)
    span.appendChild(range.extractContents());
    range.insertNode(span);
    // Restore selection to cover the new span
    range.selectNodeContents(span);
    sel.removeAllRanges();
    sel.addRange(range);
    rerender((n) => n + 1);
  }

  function isActive(cmd: string) {
    try { return document.queryCommandState(cmd); } catch { return false; }
  }

  const tb = "flex items-center justify-center w-7 h-7 rounded text-xs transition-colors select-none";
  const off = "text-gray-600 hover:bg-gray-100";
  const on  = "bg-brand-600 text-white";

  return (
    <div className="border-2 border-brand-400 rounded overflow-hidden">
      {/* Formatting toolbar */}
      <div
        className="flex items-center gap-0.5 px-2 py-1.5 bg-white border-b border-gray-200 flex-wrap"
        onMouseDown={(e) => e.preventDefault()}
      >
        {/* B / I / U */}
        <button onMouseDown={(e) => { e.preventDefault(); execFmt("bold"); }}
          className={`${tb} font-bold ${isActive("bold") ? on : off}`} title="Negrita (Ctrl+B)">B</button>
        <button onMouseDown={(e) => { e.preventDefault(); execFmt("italic"); }}
          className={`${tb} italic ${isActive("italic") ? on : off}`} title="Cursiva (Ctrl+I)">I</button>
        <button onMouseDown={(e) => { e.preventDefault(); execFmt("underline"); }}
          className={`${tb} underline ${isActive("underline") ? on : off}`} title="Subrayado (Ctrl+U)">U</button>

        <div className="w-px h-4 bg-gray-200 mx-0.5 shrink-0" />

        <button
          onMouseDown={(e) => { e.preventDefault(); insertLink(); }}
          className={`${tb} ${off}`}
          title="Insertar enlace (Ctrl+K)"
        >
          <LinkIcon size={13} />
        </button>

        <div className="w-px h-4 bg-gray-200 mx-0.5 shrink-0" />

        {/* Font sizes */}
        {[12, 14, 16, 18, 24, 32].map((sz) => (
          <button key={sz}
            onMouseDown={(e) => { e.preventDefault(); applyInlineStyle("fontSize", `${sz}px`); }}
            className={`px-1.5 h-6 rounded text-xs font-medium ${off}`} title={`Tamaño ${sz}px`}>
            {sz}
          </button>
        ))}

        <div className="w-px h-4 bg-gray-200 mx-0.5 shrink-0" />

        {/* Color swatches */}
        {BRAND_PALETTE.map((c) => (
          <button key={c}
            onMouseDown={(e) => { e.preventDefault(); applyInlineStyle("color", c); }}
            title={c}
            style={{ background: c }}
            className="w-5 h-5 rounded-full border border-gray-300 hover:scale-110 transition-transform shrink-0"
          />
        ))}
        <input type="color" defaultValue="#222222"
          onMouseDown={(e) => e.stopPropagation()}
          onChange={(e) => { ref.current?.focus(); applyInlineStyle("color", e.target.value); }}
          className="w-6 h-6 rounded border border-gray-300 cursor-pointer p-0 shrink-0" title="Color personalizado"
        />

        <div className="w-px h-4 bg-gray-200 mx-0.5 shrink-0" />

        {/* Alignment */}
        <button onMouseDown={(e) => { e.preventDefault(); execFmt("justifyLeft"); }}
          className={`${tb} ${isActive("justifyLeft") ? on : off}`} title="Alinear izquierda">
          <AlignLeft size={13} />
        </button>
        <button onMouseDown={(e) => { e.preventDefault(); execFmt("justifyCenter"); }}
          className={`${tb} ${isActive("justifyCenter") ? on : off}`} title="Centrar">
          <AlignCenter size={13} />
        </button>
        <button onMouseDown={(e) => { e.preventDefault(); execFmt("justifyRight"); }}
          className={`${tb} ${isActive("justifyRight") ? on : off}`} title="Alinear derecha">
          <AlignRight size={13} />
        </button>

        <div className="w-px h-4 bg-gray-200 mx-0.5 shrink-0" />

        {/* Font family */}
        <select
          onMouseDown={(e) => e.stopPropagation()}
          onChange={(e) => { ref.current?.focus(); applyInlineStyle("fontFamily", e.target.value); }}
          defaultValue={FONT_OPTIONS[0].value}
          className="h-6 text-xs border border-gray-200 rounded px-1 text-gray-700 max-w-[130px]"
        >
          {FONT_OPTIONS.map((f) => (
            <option key={f.value} value={f.value}>{f.label.split(" (")[0]}</option>
          ))}
        </select>
      </div>

      {/* Editable area */}
      <div
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        style={{ ...style, outline: "none", cursor: "text", minHeight: 40 }}
        onBlur={(e) => onCommit(pruneEmptyHtmlContent(e.currentTarget.innerHTML))}
        onClick={(e) => e.stopPropagation()}
        onKeyUp={() => rerender((n) => n + 1)}
        onMouseUp={() => rerender((n) => n + 1)}
        onKeyDown={(e) => {
          e.stopPropagation();
          if (e.key === "Escape") e.currentTarget.blur();
          if ((e.metaKey || e.ctrlKey) && e.key === "k") {
            e.preventDefault();
            insertLink();
          }
        }}
      />
    </div>
  );
}

// ── Properties panel helpers ───────────────────────────────────────────────────
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{label}</label>
      {children}
    </div>
  );
}
function TI({ value, onChange, placeholder = "" }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />;
}
function NI({ value, onChange, min = 0, max = 9999 }: { value: string | number; onChange: (v: string) => void; min?: number; max?: number }) {
  return <input type="number" value={value} min={min} max={max} onChange={(e) => onChange(e.target.value)}
    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />;
}
function CI({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-1.5 flex-wrap">
        {BRAND_PALETTE.map((c) => (
          <button key={c} type="button" onClick={() => onChange(c)}
            title={c}
            style={{ background: c, outline: value?.toLowerCase() === c.toLowerCase() ? "2px solid #6366f1" : "2px solid transparent", outlineOffset: 2 }}
            className="w-6 h-6 rounded-full cursor-pointer hover:scale-110 transition-transform border border-gray-300"
          />
        ))}
      </div>
      <div className="flex items-center gap-2">
        <input type="color" value={value || "#ffffff"} onChange={(e) => onChange(e.target.value)}
          className="w-9 h-9 rounded border border-gray-200 cursor-pointer p-0.5 shrink-0" />
        <input value={value} onChange={(e) => onChange(e.target.value)} placeholder="#ffffff"
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
      </div>
    </div>
  );
}

// ── Product Picker Modal ───────────────────────────────────────────────────────
function ProductPickerModal({
  onSelect,
  onClose,
}: {
  onSelect: (p: ShopifyProduct) => void;
  onClose: () => void;
}) {
  const [products, setProducts] = useState<ShopifyProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    shopifyApi.products()
      .then((r) => setProducts(r.data))
      .catch(() => setError("No se pudo conectar con Shopify. Verifica el token."))
      .finally(() => setLoading(false));
  }, []);

  const filtered = products.filter((p) =>
    p.title.toLowerCase().includes(search.toLowerCase())
  );

  function formatPrice(price: string) {
    const num = parseFloat(price);
    if (isNaN(num)) return price;
    return `$${Math.round(num).toLocaleString("es-CL")}`;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.5)" }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col" style={{ maxHeight: "80vh" }}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h2 className="font-bold text-gray-900">Seleccionar producto de Shopify</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-500">
            <X size={16} />
          </button>
        </div>
        <div className="px-5 py-3 border-b border-gray-100">
          <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2">
            <Search size={14} className="text-gray-400 shrink-0" />
            <input value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar producto..."
              className="flex-1 text-sm focus:outline-none" />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-3">
          {loading && (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400">
              <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mb-3" />
              <p className="text-sm">Cargando productos...</p>
            </div>
          )}
          {error && <p className="text-center text-red-600 text-sm py-8">{error}</p>}
          {!loading && !error && filtered.length === 0 && (
            <p className="text-center text-gray-400 text-sm py-8">No se encontraron productos</p>
          )}
          {!loading && !error && (
            <div className="grid grid-cols-2 gap-2">
              {filtered.map((prod) => (
                <button
                  key={prod.id}
                  onClick={() => onSelect(prod)}
                  className="flex items-start gap-3 p-3 rounded-xl border border-gray-200 hover:border-brand-400 hover:bg-brand-50 text-left transition-colors group"
                >
                  {prod.image_url
                    ? <img src={prod.image_url} alt="" className="w-14 h-14 object-cover rounded-lg shrink-0" />
                    : <div className="w-14 h-14 bg-gray-100 rounded-lg shrink-0 flex items-center justify-center text-gray-300 text-xs">Sin img</div>}
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-gray-800 leading-tight line-clamp-2">{prod.title}</p>
                    <div className="mt-1 flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs font-bold text-brand-700">{formatPrice(prod.price)}</span>
                      {prod.compare_at_price && (
                        <span className="text-xs text-gray-400 line-through">{formatPrice(prod.compare_at_price)}</span>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Properties panel ───────────────────────────────────────────────────────────
function PropsPanel({
  block,
  onChange,
  onPickProduct,
  onSaveToFavorites,
  onUploadImage,
  onPickShopifyImage,
  imgUploading,
  isEditing = false,
}: {
  block: Block;
  onChange: (p: Block["props"]) => void;
  onPickProduct: () => void;
  onSaveToFavorites: () => void;
  onUploadImage: () => void;
  onPickShopifyImage: () => void;
  imgUploading: string | null;
  isEditing?: boolean;
}) {
  const p = block.props;
  const set = (k: string, v: string | number | boolean) => onChange({ ...p, [k]: v });
  const textContentRef = useRef<HTMLTextAreaElement>(null);

  function insertLinkInContentField() {
    const ta = textContentRef.current;
    if (!ta) return;
    const next = insertLinkInHtmlString(
      p.content as string,
      ta.selectionStart,
      ta.selectionEnd,
    );
    if (next != null) set("content", pruneEmptyHtmlContent(next));
  }

  return (
    <div className="space-y-4">
      {block.type === "header" && <>
        <Field label="URL del Logo"><TI value={p.logo_url as string} onChange={(v) => set("logo_url", v)} placeholder="https://..." /></Field>
        <Field label="Tamaño del logo">
          <div className="flex gap-2 mb-2">
            {([["Pequeño", "50"], ["Mediano", "100"], ["Grande", "160"], ["XL", "240"]] as [string, string][]).map(([label, val]) => {
              const active = String(p.logo_width || "160") === val;
              return (
                <button key={label} type="button" onClick={() => set("logo_width", val)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors ${active ? "bg-brand-600 text-white border-brand-600" : "bg-white text-gray-600 border-gray-200 hover:border-brand-400"}`}>
                  {label}
                </button>
              );
            })}
          </div>
          <NI value={p.logo_width as string} onChange={(v) => set("logo_width", v)} min={40} max={400} />
          <p className="text-xs text-gray-400 mt-1">O ingresa un valor exacto en px</p>
        </Field>
        <Field label="Enlace del logo"><TI value={p.link as string} onChange={(v) => set("link", v)} /></Field>
        <Field label="Color de fondo"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
      </>}

      {block.type === "text" && <>
        {isHeroTextBlock(p.content as string) && (() => {
          const hero = getHeroTypography(p.content as string);
          const patchHero = (patch: Partial<typeof hero>) =>
            onChange({ ...p, content: applyHeroTypography(p.content as string, patch) });
          return (
            <div className="rounded-xl border border-orange-200 bg-orange-50/50 p-3 space-y-3">
              <p className="text-xs font-semibold text-orange-800">Hero con logo — ajustes visuales</p>
              <Field label="Ancho del logo (px)">
                <NI value={String(hero.logoWidth)} onChange={(v) => patchHero({ logoWidth: parseInt(v, 10) || hero.logoWidth })} min={40} max={180} />
              </Field>
              <div className="grid grid-cols-3 gap-2">
                <Field label="Subtítulo">
                  <NI value={String(hero.subtitlePx)} onChange={(v) => patchHero({ subtitlePx: parseInt(v, 10) || hero.subtitlePx })} min={9} max={18} />
                </Field>
                <Field label="Título">
                  <NI value={String(hero.titlePx)} onChange={(v) => patchHero({ titlePx: parseInt(v, 10) || hero.titlePx })} min={14} max={36} />
                </Field>
                <Field label="Cuerpo">
                  <NI value={String(hero.bodyPx)} onChange={(v) => patchHero({ bodyPx: parseInt(v, 10) || hero.bodyPx })} min={11} max={20} />
                </Field>
              </div>
              <p className="text-[10px] text-orange-700/80 leading-snug">
                También puedes editar el texto haciendo clic en el bloque en el canvas.
              </p>
            </div>
          );
        })()}
        <Field label="Contenido HTML">
          {isEditing ? (
            <div className="text-xs text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-2.5">
              Editando en el canvas — haz clic fuera del bloque para terminar.
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-1.5">
                <button
                  type="button"
                  onClick={insertLinkInContentField}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-gray-700 border border-gray-200 hover:bg-gray-50 transition-colors"
                >
                  <LinkIcon size={12} /> Insertar enlace
                </button>
                <span className="text-[10px] text-gray-400">Selecciona texto o usa el botón</span>
              </div>
              <textarea
                ref={textContentRef}
                value={p.content as string}
                onChange={(e) => set("content", pruneEmptyHtmlContent(e.target.value))}
                rows={9}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              />
              <p className="text-xs text-gray-400 mt-1">Variables: {"{{ nombre }}"}, {"{{ coupon_code }}"}</p>
            </>
          )}
        </Field>
        <Field label="Tipografía del bloque">
          <select value={(p.font_family as string) || FONT_OPTIONS[0].value} onChange={(e) => set("font_family", e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
            {FONT_OPTIONS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </Field>
        <Field label="Color de fondo"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
        <Field label="Color del texto">
          <CI
            value={(p.text_color as string) || extractTextColorFromHtml(p.content as string, "#222222")}
            onChange={(v) => onChange({ ...p, text_color: v, content: syncTextBlockColor(p.content as string, v) })}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Padding vertical"><NI value={p.padding_y as string} onChange={(v) => set("padding_y", v)} /></Field>
          <Field label="Padding horizontal"><NI value={p.padding_x as string} onChange={(v) => set("padding_x", v)} /></Field>
        </div>
        <button
          type="button"
          onClick={() => set("content", pruneEmptyHtmlContent(p.content as string))}
          className="w-full text-xs text-gray-600 hover:text-gray-900 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Quitar filas y espacios vacíos
        </button>
      </>}

      {block.type === "image" && <>
        <Field label="URL de la imagen">
          <TI value={p.src as string} onChange={(v) => set("src", v)} placeholder="https://cdn.shopify.com/..." />
          <div className="flex gap-3 mt-1.5">
            <button
              type="button"
              disabled={imgUploading === block.id}
              onClick={onUploadImage}
              className="flex items-center gap-1.5 text-xs text-brand-600 hover:text-brand-800 disabled:opacity-50"
            >
              <Upload size={13} />
              {imgUploading === block.id ? "Subiendo..." : "Subir desde PC"}
            </button>
            <button
              type="button"
              onClick={onPickShopifyImage}
              className="flex items-center gap-1.5 text-xs text-brand-600 hover:text-brand-800"
            >
              <Upload size={13} className="rotate-180" />
              Elegir de Shopify
            </button>
          </div>
        </Field>
        <Field label="Texto alternativo"><TI value={p.alt as string} onChange={(v) => set("alt", v)} placeholder="Descripción de la imagen" /></Field>
        <Field label="Enlace al hacer clic"><TI value={p.link as string} onChange={(v) => set("link", v)} placeholder="https://..." /></Field>
        <Field label="Tamaño de la imagen">
          <div className="flex gap-2 mb-2">
            {([["Completo", ""], ["75%", "450"], ["50%", "300"], ["25%", "150"]] as [string, string][]).map(([label, val]) => {
              const active = (p.width as string || "") === val;
              return (
                <button key={label} type="button" onClick={() => set("width", val)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors ${active ? "bg-brand-600 text-white border-brand-600" : "bg-white text-gray-600 border-gray-200 hover:border-brand-400"}`}>
                  {label}
                </button>
              );
            })}
          </div>
          <NI value={(p.width as string) || "0"} onChange={(v) => set("width", v === "0" ? "" : v)} min={0} max={600} />
          <p className="text-xs text-gray-400 mt-1">O ingresa un valor exacto en px (0 = ancho completo)</p>
        </Field>
        <Field label="Alineación">
          <select value={(p.align as string) || "center"} onChange={(e) => set("align", e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
            <option value="left">Izquierda</option>
            <option value="center">Centro</option>
            <option value="right">Derecha</option>
          </select>
        </Field>
        <Field label="Border radius (px)"><NI value={p.border_radius as string} onChange={(v) => set("border_radius", v)} /></Field>
        <Field label="Color de fondo"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
      </>}

      {block.type === "button" && <>
        <Field label="Texto del botón"><TI value={p.text as string} onChange={(v) => set("text", v)} /></Field>
        <Field label="URL de destino"><TI value={p.url as string} onChange={(v) => set("url", v)} placeholder="https://..." /></Field>
        <Field label="Color del botón"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
        <Field label="Color del texto"><CI value={p.text_color as string} onChange={(v) => set("text_color", v)} /></Field>
        <Field label="Tipografía">
          <select value={(p.font_family as string) || FONT_OPTIONS[0].value} onChange={(e) => set("font_family", e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
            {FONT_OPTIONS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </Field>
        <Field label="Estilo">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={!!p.full_width} onChange={(e) => set("full_width", e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500" />
            <span className="text-sm text-gray-700">Ancho completo (barra CTA)</span>
          </label>
        </Field>
        {!p.full_width && (
          <Field label="Alineación">
            <select value={p.align as string} onChange={(e) => set("align", e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
              <option value="left">Izquierda</option>
              <option value="center">Centro</option>
              <option value="right">Derecha</option>
            </select>
          </Field>
        )}
        <div className="grid grid-cols-3 gap-3">
          <Field label="Borde radius"><NI value={p.border_radius as string} onChange={(v) => set("border_radius", v)} /></Field>
          <Field label="Fuente (px)"><NI value={p.font_size as string} onChange={(v) => set("font_size", v)} min={10} max={36} /></Field>
          <Field label="Letter-spacing"><NI value={(p.letter_spacing as string) || "0"} onChange={(v) => set("letter_spacing", v)} min={0} max={10} /></Field>
        </div>
      </>}

      {block.type === "product" && <>
        <button onClick={onPickProduct}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-50 hover:bg-brand-100 border border-brand-200 rounded-xl text-sm font-semibold text-brand-700 transition-colors">
          <Search size={13} /> Buscar en Shopify
        </button>
        <Field label="Nombre del producto"><TI value={p.title as string} onChange={(v) => set("title", v)} /></Field>
        <Field label="Precio (actual)"><TI value={p.price as string} onChange={(v) => set("price", v)} placeholder="$29.990" /></Field>
        <Field label="Precio original (tachado)">
          <TI value={p.compare_at_price as string} onChange={(v) => set("compare_at_price", v)} placeholder="$39.990 (opcional)" />
          <p className="text-xs text-gray-400 mt-1">Déjalo vacío si no hay descuento</p>
        </Field>
        <Field label="URL de la imagen"><TI value={p.image_url as string} onChange={(v) => set("image_url", v)} placeholder="https://cdn.shopify.com/..." /></Field>
        <Field label="URL del producto"><TI value={p.url as string} onChange={(v) => set("url", v)} placeholder="https://..." /></Field>
        <Field label="Descripción"><TI value={p.description as string} onChange={(v) => set("description", v)} /></Field>
        <Field label="Botón">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={p.show_button !== false}
              onChange={(e) => set("show_button", e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
            />
            <span className="text-sm text-gray-700">Mostrar botón</span>
          </label>
        </Field>
        {p.show_button !== false && <>
          <Field label="Texto del botón"><TI value={p.button_text as string} onChange={(v) => set("button_text", v)} /></Field>
          <Field label="Color del botón"><CI value={p.button_color as string} onChange={(v) => set("button_color", v)} /></Field>
        </>}
        <Field label="Color del precio"><CI value={(p.price_color as string) || "#e53e3e"} onChange={(v) => set("price_color", v)} /></Field>
        <Field label="Color de fondo"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
      </>}

      {block.type === "coupon" && <>
        <Field label="Título"><TI value={p.title as string} onChange={(v) => set("title", v)} placeholder="Tu código de descuento" /></Field>
        <Field label="Código">
          <TI value={p.code as string} onChange={(v) => set("code", v)} placeholder="{{ coupon_code }}" />
          <p className="text-xs text-gray-400 mt-1">Usa {"{{ coupon_code }}"} para cupones dinámicos</p>
        </Field>
        <Field label="Subtítulo"><TI value={p.subtitle as string} onChange={(v) => set("subtitle", v)} /></Field>
        <Field label="Color de fondo"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
        <Field label="Color del texto"><CI value={p.text_color as string} onChange={(v) => set("text_color", v)} /></Field>
        <Field label="Color del borde"><CI value={p.border_color as string} onChange={(v) => set("border_color", v)} /></Field>
      </>}

      {block.type === "divider" && <>
        <Field label="Color"><CI value={p.color as string} onChange={(v) => set("color", v)} /></Field>
        <Field label="Grosor (px)"><NI value={p.thickness as string} onChange={(v) => set("thickness", v)} min={1} max={12} /></Field>
        <Field label="Padding vertical (px)"><NI value={p.padding_y as string} onChange={(v) => set("padding_y", v)} /></Field>
      </>}

      {block.type === "spacer" && <>
        <Field label="Altura (px)"><NI value={p.height as string} onChange={(v) => set("height", v)} min={8} max={200} /></Field>
        <Field label="Color de fondo"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
      </>}

      {block.type === "product_grid" && <>
        <Field label="Variable a usar">
          <select
            value={p.variable as string}
            onChange={(e) => set("variable", e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="productos_recomendados_edad_html">Recomendados por edad del regalón</option>
            <option value="recommended_products_html">Recomendados por última compra</option>
            <option value="productos_comprados_html">Historial de compras</option>
          </select>
        </Field>
        <Field label="Color botones"><CI value={p.btn_color as string ?? "#f97316"} onChange={(v) => set("btn_color", v)} /></Field>
        <Field label="Color de fondo"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
        <Field label="Padding vertical (px)"><NI value={p.padding_y as string} onChange={(v) => set("padding_y", v)} min={0} max={80} /></Field>
        <div className="text-xs text-gray-400 bg-gray-50 rounded-lg p-3 leading-relaxed">
          Este bloque inserta <code className="font-mono bg-gray-100 px-1 rounded">{"{{ variable }}"}</code> en el HTML. Los productos reales se inyectan automáticamente en cada automatización. La vista previa del editor usa productos de ejemplo.
        </div>
      </>}

      {block.type === "timer" && (() => {
        const designPresets: Record<string, { bg_color: string; accent_color: string; text_color: string }> = {
          clasico:  { bg_color: "#111111", accent_color: "#682ae7", text_color: "#ffffff" },
          minimal:  { bg_color: "#f9fafb", accent_color: "#682ae7", text_color: "#222222" },
          urgencia: { bg_color: "#dc2626", accent_color: "#f97316", text_color: "#ffffff" },
          elegante: { bg_color: "#ffffff", accent_color: "#682ae7", text_color: "#111111" },
        };
        return (
          <>
            <Field label="Diseño">
              <div className="grid grid-cols-2 gap-2">
                {([["clasico", "Clásico"], ["minimal", "Minimal"], ["urgencia", "Urgencia"], ["elegante", "Elegante"]] as [string, string][]).map(([val, lbl]) => {
                  const active = ((p.design as string) || "clasico") === val;
                  return (
                    <button key={val} type="button"
                      onClick={() => onChange({ ...p, design: val, ...designPresets[val] })}
                      className={`py-2 rounded-lg text-xs font-medium border transition-colors ${active ? "bg-brand-600 text-white border-brand-600" : "bg-white text-gray-600 border-gray-200 hover:border-brand-400"}`}>
                      {lbl}
                    </button>
                  );
                })}
              </div>
            </Field>
            <Field label="Modo del timer">
              <div className="flex gap-2">
                {([["relativo", "Duración relativa"], ["fijo", "Fecha fija"]] as [string, string][]).map(([val, lbl]) => {
                  const active = ((p.timer_mode as string) || "relativo") === val;
                  return (
                    <button key={val} type="button"
                      onClick={() => set("timer_mode", val)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-colors ${active ? "bg-brand-600 text-white border-brand-600" : "bg-white text-gray-600 border-gray-200 hover:border-brand-400"}`}>
                      {lbl}
                    </button>
                  );
                })}
              </div>
            </Field>
            {((p.timer_mode as string) || "relativo") === "relativo" ? (
              <Field label="Duración desde el envío">
                <div className="flex items-center gap-2">
                  <input
                    type="number" min={1} max={8760}
                    value={(p.duration_hours as string) || "24"}
                    onChange={(e) => set("duration_hours", e.target.value)}
                    className="w-24 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                  <span className="text-sm text-gray-500">horas</span>
                </div>
                <p className="text-xs text-gray-400 mt-1">El timer se calcula automáticamente al momento del envío</p>
              </Field>
            ) : (
              <Field label="Fecha y hora objetivo">
                <input type="datetime-local" value={(p.target_date as string) || ""}
                  onChange={(e) => set("target_date", e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <p className="text-xs text-gray-400 mt-1">El timer cuenta hacia esta fecha fija</p>
              </Field>
            )}
            <Field label="Título"><TI value={p.title as string} onChange={(v) => set("title", v)} placeholder="¡La oferta termina en!" /></Field>
            <Field label="Subtítulo"><TI value={p.subtitle as string} onChange={(v) => set("subtitle", v)} placeholder="Aprovecha antes de que sea tarde" /></Field>
            <Field label="Color de fondo"><CI value={(p.bg_color as string) || "#111111"} onChange={(v) => set("bg_color", v)} /></Field>
            <Field label="Color de acento"><CI value={(p.accent_color as string) || "#682ae7"} onChange={(v) => set("accent_color", v)} /></Field>
            <Field label="Color del texto"><CI value={(p.text_color as string) || "#ffffff"} onChange={(v) => set("text_color", v)} /></Field>
            <Field label="Etiquetas">
              <div className="grid grid-cols-4 gap-1">
                {([
                  ["label_days", "Días", "DÍAS"],
                  ["label_hours", "Horas", "HRS"],
                  ["label_minutes", "Min", "MIN"],
                  ["label_seconds", "Seg", "SEG"],
                ] as [string, string, string][]).map(([key, caption, ph]) => (
                  <div key={key}>
                    <p className="text-xs text-gray-400 mb-1">{caption}</p>
                    <input value={(p[key] as string) || ph} onChange={(e) => set(key, e.target.value)}
                      className="w-full border border-gray-200 rounded px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500" />
                  </div>
                ))}
              </div>
            </Field>
            <Field label="Opciones">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={p.show_seconds !== false} onChange={(e) => set("show_seconds", e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500" />
                <span className="text-sm text-gray-700">Mostrar segundos</span>
              </label>
            </Field>
          </>
        );
      })()}

      {/* Save to favorites */}
      <div className="pt-2 border-t border-gray-100">
        <button onClick={onSaveToFavorites}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200 transition-colors">
          <Star size={12} /> Guardar como favorito
        </button>
      </div>
    </div>
  );
}

// ── Save favorite modal ────────────────────────────────────────────────────────
function SaveFavoriteModal({
  defaultName,
  blockLabel,
  saving,
  onSave,
  onClose,
}: {
  defaultName: string;
  blockLabel: string;
  saving: boolean;
  onSave: (name: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(defaultName);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-bold text-gray-900 text-base flex items-center gap-2">
            <Star size={16} className="text-amber-500" /> Guardar como favorito
          </h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Guarda una copia de este bloque (<span className="font-medium text-gray-700">{blockLabel}</span>) en tu biblioteca.
          Al insertarlo en otra plantilla podrás editar textos, enlaces y productos libremente.
        </p>
        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
          Nombre del favorito
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Ej: Hero vacaciones con logo"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === "Enter" && name.trim()) onSave(name.trim());
            if (e.key === "Escape") onClose();
          }}
          className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 mb-5"
        />
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
          >
            Cancelar
          </button>
          <button
            type="button"
            disabled={saving || !name.trim()}
            onClick={() => onSave(name.trim())}
            className="px-5 py-2 bg-amber-500 text-white rounded-lg text-sm font-semibold hover:bg-amber-600 disabled:opacity-50"
          >
            {saving ? "Guardando..." : "Guardar favorito"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Shopify Image Picker Modal ────────────────────────────────────────────────
function ShopifyImagePickerModal({ onSelect, onClose }: { onSelect: (url: string) => void; onClose: () => void }) {
  const [images, setImages] = React.useState<{ url: string; alt: string }[]>([]);
  const [cursor, setCursor] = React.useState<string | undefined>(undefined);
  const [hasMore, setHasMore] = React.useState(false);
  const [loading, setLoading] = React.useState(true);

  const fetchImages = async (after?: string) => {
    setLoading(true);
    try {
      const res = await adminApi.shopifyImages(after);
      const data = res.data;
      setImages((prev) => after ? [...prev, ...data.images] : data.images);
      setHasMore(data.pageInfo.hasNextPage);
      setCursor(data.pageInfo.endCursor);
    } catch { /* noop */ }
    finally { setLoading(false); }
  };

  React.useEffect(() => { fetchImages(); }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl mx-4 flex flex-col" style={{ maxHeight: "85vh" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 shrink-0">
          <h3 className="font-semibold text-gray-900">Imágenes de Shopify</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><X size={20} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading && images.length === 0 ? (
            <div className="grid grid-cols-4 gap-3">
              {[...Array(12)].map((_, i) => <div key={i} className="aspect-square bg-gray-100 rounded-lg animate-pulse" />)}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-4 gap-3">
                {images.map((img, i) => (
                  <button
                    key={i}
                    onClick={() => onSelect(img.url)}
                    className="aspect-square rounded-lg overflow-hidden border-2 border-transparent hover:border-brand-500 transition-colors focus:outline-none focus:border-brand-500"
                  >
                    <img src={img.url} alt={img.alt} className="w-full h-full object-cover" />
                  </button>
                ))}
              </div>
              {hasMore && (
                <div className="text-center mt-4">
                  <button
                    onClick={() => fetchImages(cursor)}
                    disabled={loading}
                    className="px-4 py-2 text-sm text-brand-600 border border-brand-200 rounded-lg hover:bg-brand-50 disabled:opacity-50"
                  >
                    {loading ? "Cargando..." : "Cargar más"}
                  </button>
                </div>
              )}
              {images.length === 0 && <p className="text-center text-gray-400 py-12">No hay imágenes en Shopify Files.</p>}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Plain text editor ──────────────────────────────────────────────────────────
function PlainTextEditor({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  function insertLink() {
    const ta = ref.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = value.slice(start, end) || "texto del enlace";
    const url = prompt("URL del enlace:", "https://www.happylapiz.cl");
    if (!url) return;
    const link = `[${selected}](${url})`;
    const next = value.slice(0, start) + link + value.slice(end);
    onChange(next);
    setTimeout(() => {
      ta.focus();
      ta.selectionStart = ta.selectionEnd = start + link.length;
    }, 0);
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b border-gray-200 shrink-0">
        <button onClick={insertLink}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-gray-700 hover:bg-white hover:shadow-sm border border-transparent hover:border-gray-200 transition-all">
          <LinkIcon size={12} /> Insertar enlace
        </button>
        <span className="text-xs text-gray-400">Selecciona texto y haz clic, o usa <code className="bg-gray-200 px-1 rounded">[texto](url)</code></span>
      </div>

      <div className="flex flex-1 overflow-hidden gap-0">
        {/* Editor */}
        <div className="flex-1 flex flex-col">
          <p className="text-xs font-semibold text-gray-400 px-4 pt-3 pb-1">Editar</p>
          <textarea
            ref={ref}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={"Hola, {{ nombre }}!\n\nEscribe tu mensaje aquí.\n\n[Ver productos](https://www.happylapiz.cl)"}
            className="flex-1 px-4 pb-4 text-sm text-gray-800 resize-none focus:outline-none font-mono leading-relaxed"
          />
        </div>
        {/* Preview */}
        <div className="flex-1 border-l border-gray-200 flex flex-col overflow-hidden">
          <p className="text-xs font-semibold text-gray-400 px-4 pt-3 pb-1">Preview</p>
          <div className="flex-1 overflow-y-auto px-6 py-2 text-sm text-gray-700 leading-relaxed"
            dangerouslySetInnerHTML={{
              __html: value
                .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" style="color:#2563eb;text-decoration:underline;">$1</a>')
                .split("\n\n").map((p) => `<p style="margin:0 0 16px;">${p.replace(/\n/g, "<br>")}</p>`).join("")
            }}
          />
        </div>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export interface TemplateEditorSaveData {
  name: string;
  html: string;
  blocks: unknown;
}

interface Props {
  initialBlocks?: Block[];
  initialPlainText?: string;
  initialMode?: "blocks" | "plain";
  initialName?: string;
  initialHtmlOverride?: string | null;
  templateId?: number;
  onSave: (data: TemplateEditorSaveData) => void;
  saving?: boolean;
  saved?: boolean;
}

export function TemplateBlockEditor({
  initialBlocks = [],
  initialPlainText = "",
  initialMode = "blocks",
  initialName = "",
  initialHtmlOverride = null,
  templateId,
  onSave,
  saving = false,
  saved = false,
}: Props) {
  const [blocks, setBlocks] = useState<Block[]>(initialBlocks);
  const [plainText, setPlainText] = useState(initialPlainText);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState(initialName);
  const [sendTestOpen, setSendTestOpen] = useState(false);
  const [testEmail, setTestEmail] = useState("");
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; msg: string; cartFound?: boolean; checkoutUrl?: string } | null>(null);
  const [tab, setTab] = useState<"editor" | "preview" | "html" | "plain">(
    initialMode === "plain" ? "plain" : "editor"
  );
  const [previewDevice, setPreviewDevice] = useState<"desktop" | "mobile">("desktop");
  const qc = useQueryClient();
  const starterAppliedRef = useRef(false);
  const { data: serverFavorites = [] } = useQuery({
    queryKey: ["favorite-blocks"],
    queryFn: () => favoriteBlocksApi.list().then((r) => r.data),
  });
  const [varsOpen, setVarsOpen] = useState(false);
  const [productPickerBlockId, setProductPickerBlockId] = useState<string | null>(null);
  const [htmlOverride, setHtmlOverride] = useState<string | null>(initialHtmlOverride ?? null);
  const [convertMsg, setConvertMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [imgUploading, setImgUploading] = useState<string | null>(null);
  const [shopifyPickerOpen, setShopifyPickerOpen] = useState(false);
  const [saveFavOpen, setSaveFavOpen] = useState(false);
  const [saveFavSaving, setSaveFavSaving] = useState(false);
  const [insertHint, setInsertHint] = useState<string | null>(null);
  const imgInputRef = useRef<HTMLInputElement>(null);
  const imgUploadTargetRef = useRef<string | null>(null);
  const shopifyPickerTargetRef = useRef<string | null>(null);

  type EditorSnapshot = {
    blocks: Block[];
    plainText: string;
    htmlOverride: string | null;
    selectedId: string | null;
  };
  const UNDO_LIMIT = 50;
  const UNDO_DEBOUNCE_MS = 600;
  const undoStackRef = useRef<EditorSnapshot[]>([]);
  const isUndoingRef = useRef(false);
  const lastUndoBurstRef = useRef<{ at: number; key?: string } | null>(null);
  const [canUndo, setCanUndo] = useState(false);

  const cloneSnapshot = useCallback((): EditorSnapshot => ({
    blocks: JSON.parse(JSON.stringify(blocks)) as Block[],
    plainText,
    htmlOverride,
    selectedId,
  }), [blocks, plainText, htmlOverride, selectedId]);

  const refreshCanUndo = useCallback(() => {
    setCanUndo(undoStackRef.current.length > 0);
  }, []);

  const pushUndoSnapshot = useCallback((burstKey?: string) => {
    if (isUndoingRef.current) return;
    const now = Date.now();
    const last = lastUndoBurstRef.current;
    if (burstKey && last?.key === burstKey && now - last.at < UNDO_DEBOUNCE_MS) return;
    undoStackRef.current.push(cloneSnapshot());
    if (undoStackRef.current.length > UNDO_LIMIT) undoStackRef.current.shift();
    lastUndoBurstRef.current = burstKey ? { at: now, key: burstKey } : null;
    refreshCanUndo();
  }, [cloneSnapshot, refreshCanUndo]);

  const undo = useCallback(() => {
    const snap = undoStackRef.current.pop();
    if (!snap) return;
    isUndoingRef.current = true;
    lastUndoBurstRef.current = null;
    setBlocks(snap.blocks);
    setPlainText(snap.plainText);
    setHtmlOverride(snap.htmlOverride);
    setSelectedId(snap.selectedId);
    isUndoingRef.current = false;
    refreshCanUndo();
  }, [refreshCanUndo]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!(e.metaKey || e.ctrlKey) || e.key !== "z" || e.shiftKey) return;
      if (undoStackRef.current.length === 0) return;
      const el = e.target as HTMLElement;
      if (el.closest("[data-skip-global-undo]")) return;
      e.preventDefault();
      undo();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [undo]);

  // When the editor tab is active and there's a pending HTML override with no blocks,
  // auto-convert so the user lands directly in the editable canvas instead of a dead screen.
  useEffect(() => {
    if (tab === "editor" && htmlOverride && blocks.length === 0) {
      handleConvertToBlocks();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  // Migrate legacy localStorage favorites to the server (once).
  useEffect(() => {
    const legacy = migrateLocalFavorites();
    if (!legacy?.length) return;
    (async () => {
      for (const fav of legacy) {
        try {
          await favoriteBlocksApi.create({
            name: fav.name,
            block_type: fav.block_type,
            props: fav.props,
            sort_order: fav.sort_order,
          });
        } catch { /* skip duplicates */ }
      }
      clearLocalFavorites();
      qc.invalidateQueries({ queryKey: ["favorite-blocks"] });
    })();
  }, [qc]);

  // Preload favorite blocks when creating a new template.
  useEffect(() => {
    if (starterAppliedRef.current) return;
    if (templateId) {
      starterAppliedRef.current = true;
      return;
    }
    if (initialBlocks.length > 0) {
      starterAppliedRef.current = true;
      return;
    }
    if (htmlOverride) {
      starterAppliedRef.current = true;
      return;
    }
    if (serverFavorites.length === 0) return;
    const starter = serverFavorites
      .filter((f) => f.sort_order < 50)
      .map((f, i) => favoriteToBlock(f, `${f.block_type}_starter_${Date.now()}_${i}`));
    if (starter.length === 0) return;
    setBlocks(starter);
    starterAppliedRef.current = true;
  }, [serverFavorites, initialBlocks.length, htmlOverride, templateId]);

  const selected = blocks.find((b) => b.id === selectedId) ?? null;
  const isPlainMode = tab === "plain";

  function favoriteToBlock(fav: FavoriteBlock, id?: string): Block {
    const type = fav.block_type as BlockType;
    return {
      id: id ?? `${type}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      type,
      props: { ...DEFAULTS[type], ...cloneBlockProps(fav.props) },
    };
  }

  function showInsertHint(label: string) {
    setInsertHint(`«${label}» insertado — haz clic para editar textos, enlaces y productos.`);
    setTimeout(() => setInsertHint(null), 5000);
  }

  function addBlock(type: BlockType) {
    pushUndoSnapshot();
    const b: Block = { id: `${type}_${Date.now()}`, type, props: { ...DEFAULTS[type] } };
    setBlocks((prev) => [...prev, b]);
    setSelectedId(b.id);
    if (tab !== "editor") setTab("editor");
  }

  function addFavorite(fav: FavoriteBlock) {
    pushUndoSnapshot();
    const b = favoriteToBlock(fav);
    setBlocks((prev) => [...prev, b]);
    setSelectedId(b.id);
    if (tab !== "editor") setTab("editor");
    showInsertHint(fav.name);
  }

  async function removeFavorite(id: number) {
    if (!window.confirm("¿Eliminar este bloque favorito?")) return;
    try {
      await favoriteBlocksApi.delete(id);
      qc.invalidateQueries({ queryKey: ["favorite-blocks"] });
    } catch {
      alert("No se pudo eliminar el favorito.");
    }
  }

  async function saveToFavorites(name: string) {
    if (!selected) return;
    setSaveFavSaving(true);
    try {
      await favoriteBlocksApi.create({
        name,
        block_type: selected.type,
        props: cloneBlockProps(selected.props),
        sort_order: serverFavorites.length * 10 + 10,
      });
      qc.invalidateQueries({ queryKey: ["favorite-blocks"] });
      setSaveFavOpen(false);
    } catch {
      alert("No se pudo guardar el favorito.");
    } finally {
      setSaveFavSaving(false);
    }
  }

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    const blockId = imgUploadTargetRef.current;
    if (!file || !blockId) return;
    e.target.value = "";
    setImgUploading(blockId);
    try {
      const res = await adminApi.uploadImage(file);
      const url = res.data.url;
      pushUndoSnapshot();
      setBlocks((prev) =>
        prev.map((b) => b.id === blockId ? { ...b, props: { ...b.props, src: url } } : b)
      );
    } catch {
      alert("No se pudo subir la imagen. Revisa la consola o intenta de nuevo.");
    } finally {
      setImgUploading(null);
      imgUploadTargetRef.current = null;
    }
  }

  function handleConvertToBlocks() {
    const source = htmlOverride ?? "";
    // Always switch to editor tab, even on failure
    setTab("editor");
    if (!source.trim()) return;
    const parsed = htmlToBlocks(source);
    if (parsed.length === 0) {
      setConvertMsg({ type: "err", text: "No se pudieron detectar bloques en este HTML. Puedes editarlo directamente en la pestaña HTML." });
      setTimeout(() => setConvertMsg(null), 5000);
      return;
    }
    pushUndoSnapshot();
    setBlocks(parsed);
    setHtmlOverride(null);
    setSelectedId(null);
    setConvertMsg({ type: "ok", text: `${parsed.length} bloques importados. Revisa y guarda.` });
    setTimeout(() => setConvertMsg(null), 6000);
  }

  function update(id: string, props: Block["props"]) {
    pushUndoSnapshot(`block:${id}`);
    setBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, props } : b)));
  }

  function remove(id: string) {
    pushUndoSnapshot();
    setBlocks((prev) => prev.filter((b) => b.id !== id));
    if (selectedId === id) setSelectedId(null);
  }

  function duplicate(id: string) {
    pushUndoSnapshot();
    setBlocks((prev) => {
      const i = prev.findIndex((b) => b.id === id);
      if (i < 0) return prev;
      const copy = { ...prev[i], props: { ...prev[i].props }, id: `block_${Date.now()}` };
      const next = [...prev];
      next.splice(i + 1, 0, copy);
      return next;
    });
  }

  function move(id: string, dir: "up" | "down") {
    pushUndoSnapshot();
    setBlocks((prev) => {
      const i = prev.findIndex((b) => b.id === id);
      if (i < 0) return prev;
      const j = dir === "up" ? i - 1 : i + 1;
      if (j < 0 || j >= prev.length) return prev;
      const next = [...prev];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  }

  function handleSelectProduct(prod: ShopifyProduct) {
    if (!productPickerBlockId) return;
    const b = blocks.find((bl) => bl.id === productPickerBlockId);
    if (!b) return;
    const num = (s: string) => {
      const n = parseFloat(s);
      return isNaN(n) ? s : `$${Math.round(n).toLocaleString("es-CL")}`;
    };
    update(productPickerBlockId, {
      ...b.props,
      title: prod.title,
      price: num(prod.price),
      compare_at_price: prod.compare_at_price ? num(prod.compare_at_price) : "",
      image_url: prod.image_url,
      url: prod.url,
    });
    setProductPickerBlockId(null);
  }

  function handleSave() {
    if (isPlainMode) {
      onSave({
        name,
        html: plainTextToHtml(plainText),
        blocks: { mode: "plain", text: plainText },
      });
    } else {
      onSave({
        name,
        html: htmlOverride ?? blocksToHtml(blocks),
        blocks,
      });
    }
  }

  const generatedHtml = isPlainMode ? plainTextToHtml(plainText) : blocksToHtml(blocks);
  const previewHtml = htmlOverride ?? generatedHtml;
  const previewWidth = previewDevice === "mobile" ? 390 : 600;

  return (
    <>
      <input
        ref={imgInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleImageUpload}
      />
      {productPickerBlockId && (
        <ProductPickerModal
          onSelect={handleSelectProduct}
          onClose={() => setProductPickerBlockId(null)}
        />
      )}
      {saveFavOpen && selected && (
        <SaveFavoriteModal
          defaultName={PALETTE.find((x) => x.type === selected.type)?.label ?? selected.type}
          blockLabel={PALETTE.find((x) => x.type === selected.type)?.label ?? selected.type}
          saving={saveFavSaving}
          onSave={saveToFavorites}
          onClose={() => setSaveFavOpen(false)}
        />
      )}
      {shopifyPickerOpen && (
        <ShopifyImagePickerModal
          onSelect={(url) => {
            const blockId = shopifyPickerTargetRef.current;
            if (blockId) {
              pushUndoSnapshot();
              setBlocks((prev) => prev.map((b) => b.id === blockId ? { ...b, props: { ...b.props, src: url } } : b));
            }
            setShopifyPickerOpen(false);
            shopifyPickerTargetRef.current = null;
          }}
          onClose={() => { setShopifyPickerOpen(false); shopifyPickerTargetRef.current = null; }}
        />
      )}

      <div className="flex flex-col" style={{ height: "calc(100vh - 64px)" }}>
        {/* Top bar */}
        <div className="flex items-center gap-3 px-5 py-2.5 border-b border-gray-200 bg-white shrink-0">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre de la plantilla *"
            data-skip-global-undo
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm font-medium w-52 focus:outline-none focus:ring-2 focus:ring-brand-500" />
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={undo}
              disabled={!canUndo}
              title="Deshacer (⌘Z / Ctrl+Z)"
              className="px-3 py-2 border border-gray-200 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 transition-colors"
            >
              <Undo2 size={13} /> Deshacer
            </button>
            {saved && <span className="text-sm text-green-600 font-medium">✓ Guardado</span>}
            {templateId && (
              <button onClick={() => { setSendTestOpen(true); setTestResult(null); }}
                className="px-3 py-2 border border-gray-200 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-50 flex items-center gap-1.5 transition-colors">
                <Send size={13} /> Enviar prueba
              </button>
            )}
            <button onClick={handleSave} disabled={saving || !name}
              className="px-5 py-2 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-60 transition-colors">
              {saving ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </div>

        {insertHint && (
          <div className="px-5 py-2 bg-amber-50 border-b border-amber-200 text-amber-900 text-xs shrink-0">
            {insertHint}
          </div>
        )}

        {/* Send-test modal */}
        {sendTestOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-gray-900 text-base">Enviar email de prueba</h2>
                <button onClick={() => setSendTestOpen(false)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
              </div>

              <div className="space-y-4 text-sm text-gray-600 mb-5">
                <p>
                  Se enviará la plantilla renderizada con datos reales del carrito abandonado de ese email (si existe).
                  Así podés verificar el link de checkout, el unsubscribe y todas las variables.
                </p>
                <div className="bg-gray-50 rounded-xl p-3 text-xs space-y-1 font-mono text-gray-500">
                  <div><span className="text-brand-600">{"{{ first_name }}"}</span> → nombre del contacto</div>
                  <div><span className="text-brand-600">{"{{ event.extra.checkout_url }}"}</span> → link del carrito real</div>
                  <div><span className="text-brand-600">{"{% unsubscribe %}"}</span> → link de baja real</div>
                  <div><span className="text-brand-600">{"{{ coupon_code }}"}</span> → "CODIGO-PRUEBA"</div>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">Email destinatario</label>
                  <input
                    type="email"
                    value={testEmail}
                    onChange={(e) => setTestEmail(e.target.value)}
                    placeholder="tucorreo@ejemplo.com"
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                  <p className="text-xs text-gray-400 mt-1">Si este email dejó un carrito abandonado, se usarán sus datos reales.</p>
                </div>

                {testResult && (
                  <div className={`rounded-xl p-3 text-sm ${testResult.ok ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                    <p className="font-semibold">{testResult.msg}</p>
                    {testResult.ok && (
                      <div className="mt-2 text-xs space-y-1">
                        <p>{testResult.cartFound ? "✅ Carrito encontrado — variables reales usadas" : "⚠️ Sin carrito — variables de ejemplo usadas"}</p>
                        {testResult.checkoutUrl && (
                          <p>🔗 Checkout URL: <a href={testResult.checkoutUrl} target="_blank" rel="noopener noreferrer" className="underline break-all">{testResult.checkoutUrl}</a></p>
                        )}
                      </div>
                    )}
                  </div>
                )}

                <button
                  onClick={async () => {
                    if (!testEmail.trim()) return;
                    setTestSending(true);
                    setTestResult(null);
                    try {
                      const res = await api.post(`/templates/${templateId}/send-test`, {
                        to_email: testEmail.trim(),
                        subject: undefined,
                      });
                      setTestResult({
                        ok: true,
                        msg: `✓ Email enviado a ${testEmail}`,
                        cartFound: res.data.cart_data_found,
                        checkoutUrl: res.data.checkout_url_used,
                      });
                    } catch (e: unknown) {
                      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al enviar";
                      setTestResult({ ok: false, msg });
                    } finally {
                      setTestSending(false);
                    }
                  }}
                  disabled={testSending || !testEmail.trim()}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 text-white rounded-xl text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 transition-colors"
                >
                  <Send size={14} />
                  {testSending ? "Enviando..." : "Enviar ahora"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 3-panel */}
        <div className="flex flex-1 overflow-hidden">

          {/* Left: palette (hidden in plain text mode) */}
          {!isPlainMode && (
            <div className="w-44 border-r border-gray-200 bg-gray-50 flex flex-col shrink-0">
              <div className="flex-1 overflow-y-auto">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-widest px-4 pt-4 pb-2">Bloques</p>
              <div className="px-2 space-y-0.5">
                {PALETTE.map(({ type, label, sub }) => (
                  <button key={type} onClick={() => addBlock(type)}
                    className="w-full flex items-start gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-white hover:shadow-sm border border-transparent hover:border-gray-200 group">
                    <Plus size={12} className="text-brand-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-semibold text-gray-800 leading-tight">{label}</p>
                      <p className="text-xs text-gray-400">{sub}</p>
                    </div>
                  </button>
                ))}
              </div>

              {serverFavorites.length > 0 && (
                <>
                  <p className="text-xs font-bold text-amber-500 uppercase tracking-widest px-4 pt-4 pb-1 flex items-center gap-1.5">
                    <Star size={11} /> Favoritos
                  </p>
                  <p className="text-[10px] text-gray-400 px-4 pb-2 leading-snug">
                    Cada bloque se inserta como copia editable: textos, enlaces y productos.
                  </p>
                  <div className="px-2 pb-4 space-y-0.5">
                    {serverFavorites.map((fav) => {
                      const typeSub = PALETTE.find((x) => x.type === fav.block_type)?.sub ?? "";
                      return (
                        <div key={fav.id} className="flex items-center gap-1 group">
                          <button onClick={() => addFavorite(fav)}
                            className="flex-1 flex items-start gap-2 px-3 py-2 rounded-lg text-left hover:bg-white hover:shadow-sm border border-transparent hover:border-amber-200 transition-all">
                            <Star size={11} className="text-amber-400 shrink-0 mt-0.5" />
                            <div className="min-w-0">
                              <p className="text-xs font-semibold text-gray-700 truncate">{fav.name}</p>
                              {typeSub && <p className="text-xs text-gray-400 truncate">{typeSub}</p>}
                            </div>
                          </button>
                          <button onClick={() => removeFavorite(fav.id)}
                            className="opacity-0 group-hover:opacity-100 w-5 h-5 flex items-center justify-center text-gray-400 hover:text-red-500 transition-all shrink-0">
                            <X size={11} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
              </div>{/* end scrollable blocks */}

              {/* Variables panel — sticky at bottom, dropdown opens upward */}
              <div className="relative border-t border-gray-200 bg-gray-50 shrink-0">
                {varsOpen && (
                  <div className="absolute bottom-full left-0 right-0 z-50 bg-white border border-gray-200 shadow-xl rounded-t-xl overflow-y-auto"
                    style={{ maxHeight: "min(65vh, 520px)" }}>
                    <div className="px-2 py-3 space-y-3">
                      {TEMPLATE_VARS.map((group) => (
                        <div key={group.group}>
                          <p className="text-xs font-semibold text-gray-400 px-2 mb-1 uppercase tracking-wider">{group.group}</p>
                          <div className="space-y-0.5">
                            {group.vars.map((v) => {
                              const tag = v.raw ? v.key : `{{ ${v.key} }}`;
                              return (
                                <button
                                  key={v.key}
                                  onMouseDown={(e) => e.preventDefault()}
                                  onClick={() => {
                                    const active = document.activeElement;
                                    const isEditable =
                                      active?.getAttribute("contenteditable") === "true" ||
                                      active?.tagName === "TEXTAREA";
                                    if (isEditable) {
                                      document.execCommand("insertText", false, tag);
                                    } else {
                                      navigator.clipboard.writeText(tag).catch(() => {});
                                    }
                                  }}
                                  className="w-full text-left px-2 py-1.5 rounded-lg hover:bg-brand-50 border border-transparent hover:border-brand-200 transition-all group"
                                  title="Clic para insertar en el editor activo"
                                >
                                  <span className="text-xs font-mono text-brand-700 block truncate">{tag}</span>
                                  <span className="text-xs text-gray-400 group-hover:text-gray-600 leading-tight block">{v.desc}</span>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <button
                  onClick={() => setVarsOpen((v) => !v)}
                  className="w-full flex items-center gap-1.5 px-4 py-3 text-left hover:bg-gray-100 transition-colors"
                >
                  <span className="text-xs font-bold text-brand-500 uppercase tracking-widest">{"{{ }}"}</span>
                  <span className="text-xs font-bold text-gray-400 uppercase tracking-widest flex-1">Variables</span>
                  <span className="text-xs text-gray-400">{varsOpen ? "▾" : "▴"}</span>
                </button>
              </div>
            </div>
          )}

          {/* Center: canvas */}
          <div className="flex-1 flex flex-col overflow-hidden bg-gray-100">
            {/* Tab bar */}
            <div className="flex items-center border-b border-gray-200 bg-white px-1 shrink-0">
              {(["editor", "preview", "html", "plain"] as const).map((t) => (
                <button key={t}
                  onClick={() => {
                    // Switching to editor with a pending HTML override → auto-convert
                    if (t === "editor" && htmlOverride) {
                      handleConvertToBlocks();
                    } else {
                      setTab(t);
                    }
                  }}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${t === tab ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-800"}`}>
                  {t === "editor" && <><Layout size={13} /> Editar</>}
                  {t === "preview" && <><Eye size={13} /> Preview</>}
                  {t === "html" && <><Code size={13} /> HTML</>}
                  {t === "plain" && <><AlignLeft size={13} /> Texto plano</>}
                </button>
              ))}
              {/* Device toggle — only shown in preview */}
              {tab === "preview" && (
                <div className="ml-auto mr-2 flex items-center gap-1 bg-gray-100 rounded-lg p-1">
                  <button onClick={() => setPreviewDevice("desktop")}
                    className={`p-1.5 rounded-md transition-colors ${previewDevice === "desktop" ? "bg-white shadow text-brand-600" : "text-gray-400 hover:text-gray-700"}`}>
                    <Monitor size={14} />
                  </button>
                  <button onClick={() => setPreviewDevice("mobile")}
                    className={`p-1.5 rounded-md transition-colors ${previewDevice === "mobile" ? "bg-white shadow text-brand-600" : "text-gray-400 hover:text-gray-700"}`}>
                    <Smartphone size={14} />
                  </button>
                </div>
              )}
            </div>

            {/* Conversion notification */}
            {convertMsg && (
              <div className={`mx-4 mt-3 px-4 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2 shrink-0 ${convertMsg.type === "ok" ? "bg-green-50 border border-green-200 text-green-800" : "bg-red-50 border border-red-200 text-red-800"}`}>
                {convertMsg.type === "ok" ? "✓" : "⚠"} {convertMsg.text}
              </div>
            )}

            {/* Editor canvas */}
            {tab === "editor" && (
              <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-[600px] mx-auto bg-white shadow-md rounded overflow-hidden">
                  {blocks.length === 0 ? (
                    htmlOverride ? (
                      <div className="py-16 px-8 text-center">
                        <div className="text-5xl mb-4">🔍</div>
                        <p className="font-semibold text-gray-800 text-base mb-2">Este template tiene HTML personalizado</p>
                        <p className="text-sm text-gray-500 mb-6 leading-relaxed">
                          Puedes convertirlo a bloques editables para modificarlo visualmente,<br />
                          o ir a la pestaña <strong>HTML</strong> para editar el código directamente.
                        </p>
                        <button
                          onClick={handleConvertToBlocks}
                          className="inline-flex items-center gap-2 px-6 py-3 bg-brand-600 text-white rounded-xl text-sm font-semibold hover:bg-brand-700 transition-colors shadow-md"
                        >
                          ✨ Convertir HTML a bloques editables
                        </button>
                        <p className="text-xs text-gray-400 mt-4">La conversión es aproximada — se detectan secciones automáticamente.</p>
                        <button
                          onClick={() => setTab("html")}
                          className="mt-3 text-xs text-brand-500 hover:text-brand-700 underline block mx-auto"
                        >
                          Ir al editor HTML →
                        </button>
                      </div>
                    ) : (
                    <div className="py-24 text-center text-gray-400">
                      <Layout size={40} className="mx-auto mb-3 opacity-20" />
                      <p className="font-medium text-sm">Agrega bloques desde el panel izquierdo</p>
                      <p className="text-xs mt-1 opacity-70">Haz clic en cualquier bloque para empezar</p>
                    </div>
                    )
                  ) : (() => {
                    // Group consecutive product blocks into rows (max 3 per row)
                    type CanvasGroup =
                      | { kind: "single"; block: Block; idx: number }
                      | { kind: "product-row"; items: Array<{ block: Block; idx: number }> };
                    const canvasGroups: CanvasGroup[] = [];
                    blocks.forEach((block, idx) => {
                      if (block.type === "product") {
                        const last = canvasGroups[canvasGroups.length - 1];
                        if (last?.kind === "product-row" && last.items.length < 3) {
                          last.items.push({ block, idx });
                        } else {
                          canvasGroups.push({ kind: "product-row", items: [{ block, idx }] });
                        }
                      } else {
                        canvasGroups.push({ kind: "single", block, idx });
                      }
                    });

                    return canvasGroups.map((group) => {
                      if (group.kind === "single") {
                        const { block, idx } = group;
                        return (
                          <div key={block.id}
                            onClick={() => {
                              setSelectedId(block.id);
                              if (block.type === "text") setEditingId(block.id);
                              else setEditingId(null);
                            }}
                            className={`relative group cursor-pointer transition-all ${selectedId === block.id ? "ring-2 ring-brand-500 ring-inset" : "hover:ring-2 hover:ring-blue-200 hover:ring-inset"}`}>
                            {block.type === "text" && editingId === block.id ? (
                              <InlineTextEditor
                                content={block.props.content as string}
                                style={{
                                  background: block.props.bg_color as string,
                                  padding: `${block.props.padding_y}px ${block.props.padding_x}px`,
                                  fontSize: 13,
                                  fontFamily: (block.props.font_family as string) || undefined,
                                }}
                                onCommit={(html) => {
                                  const cleaned = pruneEmptyHtmlContent(html);
                                  const tc = extractTextColorFromHtml(
                                    cleaned,
                                    (block.props.text_color as string) || "#222222"
                                  );
                                  update(block.id, { ...block.props, content: cleaned, text_color: tc });
                                  setEditingId(null);
                                }}
                              />
                            ) : (
                              <BlockPreview block={block} />
                            )}
                            <div className={`absolute top-1 right-1 flex gap-1 z-10 ${selectedId === block.id && editingId !== block.id ? "flex" : "hidden group-hover:flex"}`}>
                              <button onClick={(e) => { e.stopPropagation(); move(block.id, "up"); }} disabled={idx === 0} className="w-6 h-6 bg-white border border-gray-200 rounded shadow text-gray-600 hover:bg-gray-50 disabled:opacity-30 flex items-center justify-center"><ChevronUp size={11} /></button>
                              <button onClick={(e) => { e.stopPropagation(); move(block.id, "down"); }} disabled={idx === blocks.length - 1} className="w-6 h-6 bg-white border border-gray-200 rounded shadow text-gray-600 hover:bg-gray-50 disabled:opacity-30 flex items-center justify-center"><ChevronDown size={11} /></button>
                              <button onClick={(e) => { e.stopPropagation(); duplicate(block.id); }} title="Duplicar sección" className="w-6 h-6 bg-white border border-gray-200 rounded shadow text-gray-600 hover:bg-gray-50 flex items-center justify-center"><Copy size={11} /></button>
                              <button onClick={(e) => { e.stopPropagation(); remove(block.id); }} className="w-6 h-6 bg-white border border-red-200 rounded shadow text-red-400 hover:bg-red-50 flex items-center justify-center"><Trash2 size={11} /></button>
                            </div>
                            {selectedId === block.id && <div className="absolute top-1 left-1 text-xs bg-brand-600 text-white px-2 py-0.5 rounded font-medium z-10 pointer-events-none">{PALETTE.find((x) => x.type === block.type)?.label}</div>}
                          </div>
                        );
                      }
                      // product-row: flex grid
                      const rowBg = group.items[0].block.props.bg_color as string || "#ffffff";
                      return (
                        <div key={group.items.map((x) => x.block.id).join("-")}
                          style={{ background: rowBg, display: "flex" }}>
                          {group.items.map(({ block, idx }) => (
                            <div key={block.id} onClick={() => { setSelectedId(block.id); setEditingId(null); }}
                              style={{ flex: 1 }}
                              className={`relative group cursor-pointer transition-all ${selectedId === block.id ? "ring-2 ring-brand-500 ring-inset" : "hover:ring-2 hover:ring-blue-200 hover:ring-inset"}`}>
                              <BlockPreview block={block} compact />
                              <div className={`absolute top-1 right-1 flex gap-1 z-10 ${selectedId === block.id ? "flex" : "hidden group-hover:flex"}`}>
                                <button onClick={(e) => { e.stopPropagation(); move(block.id, "up"); }} disabled={idx === 0} className="w-5 h-5 bg-white border border-gray-200 rounded shadow text-gray-600 hover:bg-gray-50 disabled:opacity-30 flex items-center justify-center"><ChevronUp size={9} /></button>
                                <button onClick={(e) => { e.stopPropagation(); move(block.id, "down"); }} disabled={idx === blocks.length - 1} className="w-5 h-5 bg-white border border-gray-200 rounded shadow text-gray-600 hover:bg-gray-50 disabled:opacity-30 flex items-center justify-center"><ChevronDown size={9} /></button>
                                <button onClick={(e) => { e.stopPropagation(); duplicate(block.id); }} title="Duplicar sección" className="w-5 h-5 bg-white border border-gray-200 rounded shadow text-gray-600 hover:bg-gray-50 flex items-center justify-center"><Copy size={9} /></button>
                                <button onClick={(e) => { e.stopPropagation(); remove(block.id); }} className="w-5 h-5 bg-white border border-red-200 rounded shadow text-red-400 hover:bg-red-50 flex items-center justify-center"><Trash2 size={9} /></button>
                              </div>
                              {selectedId === block.id && <div className="absolute top-1 left-1 text-xs bg-brand-600 text-white px-1.5 py-0.5 rounded font-medium z-10 pointer-events-none">Producto</div>}
                            </div>
                          ))}
                        </div>
                      );
                    });
                  })()
                  }
                </div>
              </div>
            )}

            {/* Preview */}
            {tab === "preview" && (
              <div className="flex-1 overflow-y-auto p-6 flex justify-center">
                <div style={{ width: previewWidth }} className="shadow-md transition-all duration-200">
                  {previewDevice === "mobile" && (
                    <div className="bg-gray-800 rounded-t-2xl px-3 pt-3 pb-1 flex justify-center">
                      <div className="w-16 h-1.5 bg-gray-600 rounded-full" />
                    </div>
                  )}
                  <iframe srcDoc={previewHtml} className="w-full border-0 bg-white"
                    style={{ minHeight: 500, borderRadius: previewDevice === "mobile" ? "0 0 16px 16px" : 0 }}
                    title="Preview email"
                    onLoad={(e) => {
                      const f = e.currentTarget;
                      try {
                        const h = f.contentDocument?.documentElement?.scrollHeight;
                        if (h && h > 0) f.style.height = h + "px";
                      } catch {}
                    }} />
                </div>
              </div>
            )}

            {/* HTML */}
            {tab === "html" && (
              <div className="flex-1 overflow-hidden p-4">
                <div className="h-full bg-gray-900 rounded-xl overflow-hidden flex flex-col">
                  <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700 gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400 font-mono">
                        {htmlOverride !== null ? "HTML personalizado ✎" : "HTML generado"}
                      </span>
                      {htmlOverride !== null && (
                        <>
                          <button
                            onClick={handleConvertToBlocks}
                            className="text-xs text-green-400 hover:text-green-200 transition-colors border border-green-700 rounded px-2 py-0.5 font-semibold"
                          >
                            ✨ Convertir a bloques
                          </button>
                          {blocks.length > 0 && (
                            <button
                              onClick={() => {
                                pushUndoSnapshot();
                                setHtmlOverride(null);
                              }}
                              className="text-xs text-amber-400 hover:text-amber-200 transition-colors border border-amber-700 rounded px-2 py-0.5"
                            >
                              ↩ Revertir a bloques
                            </button>
                          )}
                        </>
                      )}
                    </div>
                    <button onClick={() => navigator.clipboard.writeText(previewHtml)}
                      className="text-xs text-gray-400 hover:text-white transition-colors shrink-0">
                      Copiar
                    </button>
                  </div>
                  <textarea
                    value={htmlOverride ?? generatedHtml}
                    onChange={(e) => {
                      pushUndoSnapshot("html");
                      setHtmlOverride(e.target.value);
                    }}
                    spellCheck={false}
                    className="flex-1 p-4 font-mono text-xs text-green-400 bg-transparent resize-none focus:outline-none"
                  />
                </div>
              </div>
            )}

            {/* Plain text */}
            {tab === "plain" && (
              <PlainTextEditor
                value={plainText}
                onChange={(v) => {
                  pushUndoSnapshot("plain");
                  setPlainText(v);
                }}
              />
            )}
          </div>

          {/* Right: properties panel (hidden in plain text and preview modes) */}
          {!isPlainMode && tab !== "preview" && tab !== "html" && (
            <div className="w-72 border-l border-gray-200 bg-white flex flex-col shrink-0">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-widest px-4 pt-4 pb-2">Propiedades</p>
              <div className="flex-1 overflow-y-auto px-4 pb-4">
                {selected ? (
                  <PropsPanel
                    block={selected}
                    onChange={(props) => update(selected.id, props)}
                    onPickProduct={() => setProductPickerBlockId(selected.id)}
                    onSaveToFavorites={() => setSaveFavOpen(true)}
                    onUploadImage={() => { imgUploadTargetRef.current = selected.id; imgInputRef.current?.click(); }}
                    onPickShopifyImage={() => { shopifyPickerTargetRef.current = selected.id; setShopifyPickerOpen(true); }}
                    imgUploading={imgUploading}
                    isEditing={editingId === selected.id}
                  />
                ) : (
                  <div className="mt-12 text-center">
                    <div className="w-10 h-10 rounded-xl bg-gray-100 flex items-center justify-center mx-auto mb-3">
                      <Layout size={18} className="text-gray-400" />
                    </div>
                    <p className="text-sm font-medium text-gray-500">Selecciona un bloque</p>
                    <p className="text-xs text-gray-400 mt-1">para editar sus propiedades</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
