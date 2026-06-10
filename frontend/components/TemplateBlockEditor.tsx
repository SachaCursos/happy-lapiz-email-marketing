"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronUp, ChevronDown, Trash2, Plus, Eye, Layout, Code,
  Star, X, Monitor, Smartphone, Search, Link as LinkIcon,
  AlignLeft,
} from "lucide-react";
import { shopifyApi, ShopifyProduct } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────
type BlockType = "header" | "text" | "image" | "button" | "product" | "coupon" | "divider" | "spacer";

export interface Block {
  id: string;
  type: BlockType;
  props: Record<string, string | number | boolean>;
}

// ── Defaults ───────────────────────────────────────────────────────────────────
const DEFAULTS: Record<BlockType, Record<string, string | number | boolean>> = {
  header: {
    logo_url: "https://cdn.shopify.com/s/files/1/0751/8441/0881/files/logo-happy-lapiz.png",
    logo_width: "160",
    bg_color: "#ffffff",
    link: "https://www.happylapiz.cl",
  },
  text: {
    content: `<p style="margin:0;font-size:15px;line-height:1.75;color:#333333;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">Hola, <strong>{{ nombre }}</strong> 👋<br/><br/>Escribe tu mensaje aquí.</p>`,
    bg_color: "#ffffff",
    padding_y: "24",
    padding_x: "32",
  },
  image: {
    src: "",
    alt: "",
    link: "",
    border_radius: "0",
    bg_color: "#ffffff",
  },
  button: {
    text: "Ver más",
    url: "https://www.happylapiz.cl",
    bg_color: "#111111",
    text_color: "#ffffff",
    align: "center",
    border_radius: "8",
    font_size: "15",
  },
  product: {
    title: "Nombre del producto",
    price: "$29.990",
    compare_at_price: "",
    image_url: "",
    url: "https://www.happylapiz.cl",
    description: "Descripción breve del producto.",
    button_text: "Comprar ahora",
    button_color: "#111111",
    bg_color: "#ffffff",
  },
  coupon: {
    title: "Tu código de descuento",
    code: "{{ coupon_code }}",
    subtitle: "Úsalo en tu próxima compra",
    bg_color: "#f9fafb",
    text_color: "#111111",
    border_color: "#d1d5db",
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
};

const PALETTE: { type: BlockType; label: string; sub: string }[] = [
  { type: "header",  label: "Encabezado",  sub: "Logo + enlace" },
  { type: "text",    label: "Texto",        sub: "Párrafo HTML" },
  { type: "image",   label: "Imagen",       sub: "Banner / foto" },
  { type: "button",  label: "Botón CTA",    sub: "Llamada a acción" },
  { type: "product", label: "Producto",     sub: "Imagen + precio" },
  { type: "coupon",  label: "Cupón",        sub: "Código descuento" },
  { type: "divider", label: "Divisor",      sub: "Línea separadora" },
  { type: "spacer",  label: "Espaciado",    sub: "Espacio en blanco" },
];

const FAV_KEY = "hl_template_favorites";

function loadFavorites(): Block[] {
  try {
    const raw = localStorage.getItem(FAV_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function saveFavorites(favs: Block[]) {
  try { localStorage.setItem(FAV_KEY, JSON.stringify(favs)); } catch { /* noop */ }
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

    case "text":
      return `<div style="background:${p.bg_color};padding:${p.padding_y}px ${p.padding_x}px;">
  ${p.content}
</div>`;

    case "image": {
      const img = `<img src="${p.src}" alt="${p.alt}" style="width:100%;display:block;${p.border_radius !== "0" ? `border-radius:${p.border_radius}px;` : ""}" />`;
      return `<div style="background:${p.bg_color};">
  ${p.link ? `<a href="${p.link}" style="display:block;">${img}</a>` : img}
</div>`;
    }

    case "button": {
      const align = p.align === "left" ? "left" : p.align === "right" ? "right" : "center";
      return `<div style="padding:16px 32px;text-align:${align};background:#ffffff;">
  <a href="${p.url}" style="display:inline-block;background:${p.bg_color};color:${p.text_color};font-size:${p.font_size}px;font-weight:600;padding:14px 32px;border-radius:${p.border_radius}px;text-decoration:none;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
    ${p.text}
  </a>
</div>`;
    }

    case "product":
      return `<div style="background:${p.bg_color};padding:24px 32px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      ${p.image_url ? `<td width="140" valign="top" style="padding-right:20px;"><a href="${p.url}" style="display:block;"><img src="${p.image_url}" alt="${p.title}" width="140" style="border-radius:8px;display:block;" /></a></td>` : ""}
      <td valign="top">
        <p style="margin:0 0 8px;font-size:17px;font-weight:700;color:#111;font-family:-apple-system,sans-serif;">${p.title}</p>
        ${priceHtml(p.price as string, p.compare_at_price as string)}
        ${p.description ? `<p style="margin:0 0 16px;font-size:14px;color:#666;line-height:1.6;font-family:-apple-system,sans-serif;">${p.description}</p>` : ""}
        <a href="${p.url}" style="display:inline-block;background:${p.button_color};color:#ffffff;font-size:14px;font-weight:600;padding:10px 24px;border-radius:6px;text-decoration:none;font-family:-apple-system,sans-serif;">${p.button_text}</a>
      </td>
    </tr>
  </table>
</div>`;

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

    default:
      return "";
  }
}

export function blocksToHtml(blocks: Block[]): string {
  if (!blocks.length) return "";
  return `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1.0" />
<title>Email</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td align="center" style="padding:24px 16px;">
<div style="max-width:600px;width:100%;background:#ffffff;overflow:hidden;">
${blocks.map(blockHtml).join("\n")}
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
function BlockPreview({ block }: { block: Block }) {
  const p = block.props;
  const [imgError, setImgError] = useState(false);

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
          style={{ background: p.bg_color as string, padding: `${p.padding_y}px ${p.padding_x}px`, fontSize: 13 }}
          dangerouslySetInnerHTML={{ __html: p.content as string }}
        />
      );
    case "image":
      return p.src
        ? <div style={{ background: p.bg_color as string }}>
            <img src={p.src as string} alt={p.alt as string}
              style={{ width: "100%", display: "block", borderRadius: p.border_radius ? `${p.border_radius}px` : 0 }} />
          </div>
        : <div style={{ background: "#f9fafb", height: 90, display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: 12 }}>
            Añade URL de imagen
          </div>;
    case "button": {
      const align = p.align === "left" ? "left" : p.align === "right" ? "right" : "center";
      return (
        <div style={{ padding: "14px 24px", textAlign: align as "center" | "left" | "right", background: "#ffffff" }}>
          <span style={{ display: "inline-block", background: p.bg_color as string, color: p.text_color as string, padding: "10px 24px", borderRadius: `${p.border_radius}px`, fontSize: `${p.font_size}px`, fontWeight: 600 }}>
            {p.text as string}
          </span>
        </div>
      );
    }
    case "product":
      return (
        <div style={{ background: p.bg_color as string, padding: "14px 24px", display: "flex", gap: 14, alignItems: "flex-start" }}>
          {p.image_url
            ? <img src={p.image_url as string} alt="" style={{ width: 88, height: 88, objectFit: "cover", borderRadius: 8, flexShrink: 0 }} />
            : <div style={{ width: 88, height: 88, background: "#f3f4f6", borderRadius: 8, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "#9ca3af", fontSize: 10 }}>Imagen</div>}
          <div>
            <p style={{ margin: "0 0 3px", fontWeight: 700, fontSize: 14 }}>{p.title as string}</p>
            {p.compare_at_price
              ? <p style={{ margin: "0 0 6px" }}>
                  <span style={{ fontSize: 12, color: "#9ca3af", textDecoration: "line-through", marginRight: 6 }}>{p.compare_at_price as string}</span>
                  <span style={{ fontSize: 15, fontWeight: 800, color: "#e53e3e" }}>{p.price as string}</span>
                </p>
              : <p style={{ margin: "0 0 6px", fontWeight: 800, fontSize: 15 }}>{p.price as string}</p>}
            <span style={{ background: p.button_color as string, color: "#fff", padding: "5px 14px", borderRadius: 6, fontSize: 11, fontWeight: 600 }}>{p.button_text as string}</span>
          </div>
        </div>
      );
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
    default:
      return null;
  }
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
    <div className="flex items-center gap-2">
      <input type="color" value={value || "#ffffff"} onChange={(e) => onChange(e.target.value)}
        className="w-9 h-9 rounded border border-gray-200 cursor-pointer p-0.5 shrink-0" />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder="#ffffff"
        className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500" />
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
}: {
  block: Block;
  onChange: (p: Block["props"]) => void;
  onPickProduct: () => void;
  onSaveToFavorites: () => void;
}) {
  const p = block.props;
  const set = (k: string, v: string | number | boolean) => onChange({ ...p, [k]: v });

  return (
    <div className="space-y-4">
      {block.type === "header" && <>
        <Field label="URL del Logo"><TI value={p.logo_url as string} onChange={(v) => set("logo_url", v)} placeholder="https://..." /></Field>
        <Field label="Ancho del logo (px)"><NI value={p.logo_width as string} onChange={(v) => set("logo_width", v)} min={40} max={400} /></Field>
        <Field label="Enlace del logo"><TI value={p.link as string} onChange={(v) => set("link", v)} /></Field>
        <Field label="Color de fondo"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
      </>}

      {block.type === "text" && <>
        <Field label="Contenido HTML">
          <textarea value={p.content as string} onChange={(e) => set("content", e.target.value)} rows={9}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none" />
          <p className="text-xs text-gray-400 mt-1">Variables: {"{{ nombre }}"}, {"{{ coupon_code }}"}</p>
        </Field>
        <Field label="Color de fondo"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Padding vertical"><NI value={p.padding_y as string} onChange={(v) => set("padding_y", v)} /></Field>
          <Field label="Padding horizontal"><NI value={p.padding_x as string} onChange={(v) => set("padding_x", v)} /></Field>
        </div>
      </>}

      {block.type === "image" && <>
        <Field label="URL de la imagen"><TI value={p.src as string} onChange={(v) => set("src", v)} placeholder="https://cdn.shopify.com/..." /></Field>
        <Field label="Texto alternativo"><TI value={p.alt as string} onChange={(v) => set("alt", v)} placeholder="Descripción de la imagen" /></Field>
        <Field label="Enlace al hacer clic"><TI value={p.link as string} onChange={(v) => set("link", v)} placeholder="https://..." /></Field>
        <Field label="Border radius (px)"><NI value={p.border_radius as string} onChange={(v) => set("border_radius", v)} /></Field>
        <Field label="Color de fondo"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
      </>}

      {block.type === "button" && <>
        <Field label="Texto del botón"><TI value={p.text as string} onChange={(v) => set("text", v)} /></Field>
        <Field label="URL de destino"><TI value={p.url as string} onChange={(v) => set("url", v)} placeholder="https://..." /></Field>
        <Field label="Color del botón"><CI value={p.bg_color as string} onChange={(v) => set("bg_color", v)} /></Field>
        <Field label="Color del texto"><CI value={p.text_color as string} onChange={(v) => set("text_color", v)} /></Field>
        <Field label="Alineación">
          <select value={p.align as string} onChange={(e) => set("align", e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
            <option value="left">Izquierda</option>
            <option value="center">Centro</option>
            <option value="right">Derecha</option>
          </select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Borde radius"><NI value={p.border_radius as string} onChange={(v) => set("border_radius", v)} /></Field>
          <Field label="Tamaño fuente"><NI value={p.font_size as string} onChange={(v) => set("font_size", v)} min={10} max={30} /></Field>
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
        <Field label="Texto del botón"><TI value={p.button_text as string} onChange={(v) => set("button_text", v)} /></Field>
        <Field label="Color del botón"><CI value={p.button_color as string} onChange={(v) => set("button_color", v)} /></Field>
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
  subject: string;
  previewText: string;
  html: string;
  blocks: unknown;
}

interface Props {
  initialBlocks?: Block[];
  initialPlainText?: string;
  initialMode?: "blocks" | "plain";
  initialName?: string;
  initialSubject?: string;
  initialPreviewText?: string;
  onSave: (data: TemplateEditorSaveData) => void;
  saving?: boolean;
  saved?: boolean;
}

export function TemplateBlockEditor({
  initialBlocks = [],
  initialPlainText = "",
  initialMode = "blocks",
  initialName = "",
  initialSubject = "",
  initialPreviewText = "",
  onSave,
  saving = false,
  saved = false,
}: Props) {
  const [blocks, setBlocks] = useState<Block[]>(initialBlocks);
  const [plainText, setPlainText] = useState(initialPlainText);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState(initialName);
  const [subject, setSubject] = useState(initialSubject);
  const [previewText, setPreviewText] = useState(initialPreviewText);
  const [tab, setTab] = useState<"editor" | "preview" | "html" | "plain">(
    initialMode === "plain" ? "plain" : "editor"
  );
  const [previewDevice, setPreviewDevice] = useState<"desktop" | "mobile">("desktop");
  const [favorites, setFavorites] = useState<Block[]>(() => loadFavorites());
  const [productPickerBlockId, setProductPickerBlockId] = useState<string | null>(null);
  const [htmlOverride, setHtmlOverride] = useState<string | null>(null);

  const selected = blocks.find((b) => b.id === selectedId) ?? null;
  const isPlainMode = tab === "plain";

  function addBlock(type: BlockType) {
    const b: Block = { id: `${type}_${Date.now()}`, type, props: { ...DEFAULTS[type] } };
    setBlocks((prev) => [...prev, b]);
    setSelectedId(b.id);
    if (tab !== "editor") setTab("editor");
  }

  function addFavorite(fav: Block) {
    const b: Block = { ...fav, id: `${fav.type}_${Date.now()}` };
    setBlocks((prev) => [...prev, b]);
    setSelectedId(b.id);
    if (tab !== "editor") setTab("editor");
  }

  function removeFavorite(id: string) {
    const next = favorites.filter((f) => f.id !== id);
    setFavorites(next);
    saveFavorites(next);
  }

  function saveToFavorites() {
    if (!selected) return;
    const fav: Block = { ...selected, id: `fav_${Date.now()}` };
    const next = [...favorites, fav];
    setFavorites(next);
    saveFavorites(next);
  }

  function update(id: string, props: Block["props"]) {
    setBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, props } : b)));
  }

  function remove(id: string) {
    setBlocks((prev) => prev.filter((b) => b.id !== id));
    if (selectedId === id) setSelectedId(null);
  }

  function move(id: string, dir: "up" | "down") {
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
        name, subject, previewText,
        html: plainTextToHtml(plainText),
        blocks: { mode: "plain", text: plainText },
      });
    } else {
      onSave({
        name, subject, previewText,
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
      {productPickerBlockId && (
        <ProductPickerModal
          onSelect={handleSelectProduct}
          onClose={() => setProductPickerBlockId(null)}
        />
      )}

      <div className="flex flex-col" style={{ height: "calc(100vh - 64px)" }}>
        {/* Top bar */}
        <div className="flex items-center gap-3 px-5 py-2.5 border-b border-gray-200 bg-white shrink-0">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre de la plantilla *"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm font-medium w-52 focus:outline-none focus:ring-2 focus:ring-brand-500" />
          <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Asunto del email *"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm flex-1 max-w-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          <input value={previewText} onChange={(e) => setPreviewText(e.target.value)} placeholder="Preview text (opcional)"
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-brand-500 hidden xl:block" />
          <div className="ml-auto flex items-center gap-2">
            {saved && <span className="text-sm text-green-600 font-medium">✓ Guardado</span>}
            <button onClick={handleSave} disabled={saving || !name || !subject}
              className="px-5 py-2 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-60 transition-colors">
              {saving ? "Guardando..." : "Guardar"}
            </button>
          </div>
        </div>

        {/* 3-panel */}
        <div className="flex flex-1 overflow-hidden">

          {/* Left: palette (hidden in plain text mode) */}
          {!isPlainMode && (
            <div className="w-44 border-r border-gray-200 bg-gray-50 flex flex-col shrink-0 overflow-y-auto">
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

              {favorites.length > 0 && (
                <>
                  <p className="text-xs font-bold text-amber-500 uppercase tracking-widest px-4 pt-4 pb-2 flex items-center gap-1.5">
                    <Star size={11} /> Favoritos
                  </p>
                  <div className="px-2 pb-4 space-y-0.5">
                    {favorites.map((fav) => {
                      const label = PALETTE.find((x) => x.type === fav.type)?.label ?? fav.type;
                      return (
                        <div key={fav.id} className="flex items-center gap-1 group">
                          <button onClick={() => addFavorite(fav)}
                            className="flex-1 flex items-start gap-2 px-3 py-2 rounded-lg text-left hover:bg-white hover:shadow-sm border border-transparent hover:border-amber-200 transition-all">
                            <Star size={11} className="text-amber-400 shrink-0 mt-0.5" />
                            <p className="text-xs font-semibold text-gray-700 truncate">{label}</p>
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
            </div>
          )}

          {/* Center: canvas */}
          <div className="flex-1 flex flex-col overflow-hidden bg-gray-100">
            {/* Tab bar */}
            <div className="flex items-center border-b border-gray-200 bg-white px-1 shrink-0">
              {(["editor", "preview", "html", "plain"] as const).map((t) => (
                <button key={t} onClick={() => setTab(t)}
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

            {/* Editor canvas */}
            {tab === "editor" && (
              <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-[600px] mx-auto bg-white shadow-md rounded overflow-hidden">
                  {blocks.length === 0 ? (
                    <div className="py-24 text-center text-gray-400">
                      <Layout size={40} className="mx-auto mb-3 opacity-20" />
                      <p className="font-medium text-sm">Agrega bloques desde el panel izquierdo</p>
                      <p className="text-xs mt-1 opacity-70">Haz clic en cualquier bloque para empezar</p>
                    </div>
                  ) : (
                    blocks.map((block, i) => (
                      <div key={block.id} onClick={() => setSelectedId(block.id)}
                        className={`relative group cursor-pointer transition-all ${
                          selectedId === block.id
                            ? "ring-2 ring-brand-500 ring-inset"
                            : "hover:ring-2 hover:ring-blue-200 hover:ring-inset"
                        }`}>
                        <BlockPreview block={block} />
                        <div className={`absolute top-1 right-1 flex gap-1 z-10 ${selectedId === block.id ? "flex" : "hidden group-hover:flex"}`}>
                          <button onClick={(e) => { e.stopPropagation(); move(block.id, "up"); }} disabled={i === 0}
                            className="w-6 h-6 bg-white border border-gray-200 rounded shadow text-gray-600 hover:bg-gray-50 disabled:opacity-30 flex items-center justify-center">
                            <ChevronUp size={11} />
                          </button>
                          <button onClick={(e) => { e.stopPropagation(); move(block.id, "down"); }} disabled={i === blocks.length - 1}
                            className="w-6 h-6 bg-white border border-gray-200 rounded shadow text-gray-600 hover:bg-gray-50 disabled:opacity-30 flex items-center justify-center">
                            <ChevronDown size={11} />
                          </button>
                          <button onClick={(e) => { e.stopPropagation(); remove(block.id); }}
                            className="w-6 h-6 bg-white border border-red-200 rounded shadow text-red-400 hover:bg-red-50 flex items-center justify-center">
                            <Trash2 size={11} />
                          </button>
                        </div>
                        {selectedId === block.id && (
                          <div className="absolute top-1 left-1 text-xs bg-brand-600 text-white px-2 py-0.5 rounded font-medium z-10 pointer-events-none">
                            {PALETTE.find((x) => x.type === block.type)?.label}
                          </div>
                        )}
                      </div>
                    ))
                  )}
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
                    title="Preview email" />
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
                        <button
                          onClick={() => setHtmlOverride(null)}
                          className="text-xs text-amber-400 hover:text-amber-200 transition-colors border border-amber-700 rounded px-2 py-0.5"
                        >
                          Regenerar desde bloques
                        </button>
                      )}
                    </div>
                    <button onClick={() => navigator.clipboard.writeText(previewHtml)}
                      className="text-xs text-gray-400 hover:text-white transition-colors shrink-0">
                      Copiar
                    </button>
                  </div>
                  <textarea
                    value={htmlOverride ?? generatedHtml}
                    onChange={(e) => setHtmlOverride(e.target.value)}
                    spellCheck={false}
                    className="flex-1 p-4 font-mono text-xs text-green-400 bg-transparent resize-none focus:outline-none"
                  />
                </div>
              </div>
            )}

            {/* Plain text */}
            {tab === "plain" && (
              <PlainTextEditor value={plainText} onChange={setPlainText} />
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
                    onSaveToFavorites={saveToFavorites}
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
