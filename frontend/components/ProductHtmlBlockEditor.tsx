"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Code, Eye, Monitor, Save, Check, Smartphone } from "lucide-react";
import { htmlBlocksApi } from "@/lib/api";
import type { DynamicHtmlBlock } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  type ProductBlockDesign,
  type ProductSample,
  chunkProducts,
  compileProductBlockJinja,
  defaultDesignForBlock,
  mergeDesign,
} from "@/lib/productBlockDesign";

const BRAND_PALETTE = [
  "#682ae7", "#2a2ee7", "#222222", "#727272", "#fcfcfc", "#ffffff", "#000000", "#e53e3e", "#f97316", "#e85d04",
];

const FONT_OPTIONS = [
  { label: "Helvetica Neue (Klaviyo)", value: "'Helvetica Neue', Arial, sans-serif" },
  { label: "Sistema / Sans-serif", value: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" },
  { label: "Georgia (Serif)", value: "Georgia, 'Times New Roman', serif" },
  { label: "Verdana", value: "Verdana, Geneva, Tahoma, sans-serif" },
];

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function TI({ value, onChange, placeholder = "" }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
    />
  );
}

function NI({
  value,
  onChange,
  min = 0,
  max = 9999,
}: {
  value: string | number;
  onChange: (v: string) => void;
  min?: number;
  max?: number;
}) {
  return (
    <input
      type="number"
      value={value}
      min={min}
      max={max}
      onChange={(e) => onChange(e.target.value)}
      className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
    />
  );
}

function CI({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-1.5 flex-wrap">
        {BRAND_PALETTE.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => onChange(c)}
            title={c}
            style={{
              background: c,
              outline: value?.toLowerCase() === c.toLowerCase() ? "2px solid #6366f1" : "2px solid transparent",
              outlineOffset: 2,
            }}
            className="w-6 h-6 rounded-full cursor-pointer hover:scale-110 transition-transform border border-gray-300"
          />
        ))}
      </div>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value || "#ffffff"}
          onChange={(e) => onChange(e.target.value)}
          className="w-9 h-9 rounded border border-gray-200 cursor-pointer p-0.5 shrink-0"
        />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="#ffffff"
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>
    </div>
  );
}

function Section({
  title,
  open,
  onToggle,
  children,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden bg-white">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-gray-800 hover:bg-gray-50"
      >
        {title}
        {open ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
      </button>
      {open && <div className="px-4 pb-4 space-y-4 border-t border-gray-100 pt-4">{children}</div>}
    </div>
  );
}

function ProductCardPreview({
  product,
  design,
  discountPreview,
}: {
  product: ProductSample;
  design: ProductBlockDesign;
  discountPreview?: number;
}) {
  return (
    <a
      href={product.url || "#"}
      onClick={(e) => e.preventDefault()}
      style={{
        textDecoration: "none",
        color: design.title_color,
        display: "block",
        fontFamily: design.font_family,
      }}
    >
      {design.show_discount_badge && discountPreview != null && discountPreview > 0 && (
        <span
          style={{
            display: "inline-block",
            background: design.discount_badge_bg,
            color: design.discount_badge_text_color,
            fontSize: 11,
            fontWeight: 700,
            padding: "4px 10px",
            borderRadius: 12,
            marginBottom: 10,
          }}
        >
          {discountPreview}% OFF
        </span>
      )}
      {product.image_url ? (
        <img
          src={product.image_url}
          alt={product.title}
          style={{
            width: "100%",
            maxWidth: design.image_max_width,
            height: "auto",
            borderRadius: design.image_radius,
            display: "block",
            margin: "0 auto 12px",
          }}
        />
      ) : (
        <div
          style={{
            width: "100%",
            maxWidth: design.image_max_width,
            height: 140,
            background: "#f3f4f6",
            borderRadius: design.image_radius,
            margin: "0 auto 12px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#d1d5db",
            fontSize: 12,
          }}
        >
          sin imagen
        </div>
      )}
      <p
        style={{
          fontSize: design.title_font_size,
          fontWeight: design.title_font_weight,
          color: design.title_color,
          margin: "0 0 5px",
          lineHeight: 1.3,
          maxHeight: "3.9em",
          overflow: "hidden",
          fontFamily: design.font_family,
        }}
      >
        {product.title}
      </p>
      <p
        style={{
          fontSize: design.price_font_size,
          color: design.price_color,
          fontWeight: design.price_font_weight,
          margin: "0 0 12px",
          fontFamily: design.font_family,
        }}
      >
        {product.price}
      </p>
      <span
        style={{
          display: "inline-block",
          background: design.btn_bg,
          color: design.btn_text_color,
          fontSize: design.btn_font_size,
          fontWeight: design.btn_font_weight,
          padding: `${design.btn_padding_y}px ${design.btn_padding_x}px`,
          borderRadius: design.btn_border_radius,
        }}
      >
        {design.btn_text}
      </span>
    </a>
  );
}

function ProductBlockLivePreview({
  design,
  products,
  discountPreview = 20,
  width,
}: {
  design: ProductBlockDesign;
  products: ProductSample[];
  discountPreview?: number;
  width?: number | "full";
}) {
  const containerStyle: React.CSSProperties = {
    background: design.bg_color,
    maxWidth: width === "full" ? undefined : design.max_width,
    margin: "0 auto",
    fontFamily: design.font_family,
    width: width === "full" ? "100%" : undefined,
  };

  if (design.layout === "featured") {
    const p = products[0];
    if (!p) {
      return <p className="text-sm text-gray-400 text-center py-12">Añade al menos un producto de ejemplo.</p>;
    }
    return (
      <div style={containerStyle}>
        <div style={{ padding: `${design.padding_y}px ${design.padding_x}px`, textAlign: "center" }}>
          <ProductCardPreview product={p} design={design} discountPreview={discountPreview} />
        </div>
      </div>
    );
  }

  const rows = chunkProducts(products, 2);
  if (rows.length === 0) {
    return <p className="text-sm text-gray-400 text-center py-12">Añade productos de ejemplo para la grilla.</p>;
  }

  return (
    <div style={containerStyle}>
      <table width="100%" cellPadding={0} cellSpacing={0} style={{ borderCollapse: "collapse", width: "100%" }}>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri}>
              {row.map((p, pi) => (
                <td
                  key={pi}
                  width="50%"
                  style={{
                    width: "50%",
                    padding: `${design.padding_y}px ${design.padding_x}px`,
                    verticalAlign: "top",
                    textAlign: "center",
                  }}
                >
                  <ProductCardPreview product={p} design={design} />
                </td>
              ))}
              {row.length === 1 && <td width="50%" style={{ width: "50%" }} />}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function parseSamples(json: string): ProductSample[] {
  const parsed = JSON.parse(json) as ProductSample[];
  if (!Array.isArray(parsed)) throw new Error("invalid");
  return parsed;
}

export function ProductHtmlBlockEditor({ block }: { block: DynamicHtmlBlock }) {
  const qc = useQueryClient();
  const [design, setDesign] = useState<ProductBlockDesign>(() =>
    mergeDesign(block.block_key, block.design_config as Partial<ProductBlockDesign> | null)
  );
  const [samplesJson, setSamplesJson] = useState(JSON.stringify(block.sample_products ?? [], null, 2));
  const [samples, setSamples] = useState<ProductSample[]>(
    () => (block.sample_products as unknown as ProductSample[]) ?? []
  );
  const [jsonError, setJsonError] = useState("");
  const [saved, setSaved] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [showSamples, setShowSamples] = useState(false);
  const [previewMode, setPreviewMode] = useState<"desktop" | "mobile">("desktop");
  const [serverHtml, setServerHtml] = useState("");
  const [openSections, setOpenSections] = useState({
    container: true,
    card: true,
    button: true,
    badge: block.block_key === "featured_product_html",
  });

  const compiledTemplate = useMemo(() => compileProductBlockJinja(design), [design]);

  useEffect(() => {
    setDesign(mergeDesign(block.block_key, block.design_config as Partial<ProductBlockDesign> | null));
    setSamplesJson(JSON.stringify(block.sample_products ?? [], null, 2));
    setSamples((block.sample_products as unknown as ProductSample[]) ?? []);
  }, [block.block_key, block.design_config, block.sample_products]);

  useEffect(() => {
    try {
      setSamples(parseSamples(samplesJson));
      setJsonError("");
    } catch {
      // keep last valid samples until save/preview
    }
  }, [samplesJson]);

  const set = <K extends keyof ProductBlockDesign>(key: K, value: ProductBlockDesign[K]) => {
    setDesign((prev) => ({ ...prev, [key]: value }));
  };

  const toggleSection = (key: keyof typeof openSections) => {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const saveMutation = useMutation({
    mutationFn: () => {
      let parsed: ProductSample[];
      try {
        parsed = parseSamples(samplesJson);
        setJsonError("");
      } catch {
        setJsonError("JSON de productos de ejemplo inválido");
        throw new Error("invalid json");
      }
      return htmlBlocksApi.update(block.block_key, {
        design_config: design as unknown as Record<string, unknown>,
        html_template: compiledTemplate,
        sample_products: parsed,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["html-blocks"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const previewMutation = useMutation({
    mutationFn: () =>
      htmlBlocksApi.preview(block.block_key, {
        html_template: compiledTemplate,
        sample_products: samples,
        design_config: design as unknown as Record<string, unknown>,
      }),
    onSuccess: (res) => setServerHtml(res.data.html),
  });

  useEffect(() => {
    const t = setTimeout(() => {
      if (samples.length > 0) previewMutation.mutate();
    }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compiledTemplate, samplesJson, design]);

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-4">
        <div>
          <h2 className="font-semibold text-gray-900">{block.name}</h2>
          <p className="text-xs text-gray-500 mt-0.5 font-mono">{`{{ ${block.block_key} }}`}</p>
          {block.description && <p className="text-sm text-gray-600 mt-2">{block.description}</p>}
        </div>
        <p className="text-xs text-gray-400 shrink-0">Actualizado {formatDate(block.updated_at)}</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,380px)_1fr] gap-0 xl:divide-x divide-gray-100">
        <div className="p-5 space-y-3 max-h-[calc(100vh-220px)] overflow-y-auto">
          <Section title="Contenedor" open={openSections.container} onToggle={() => toggleSection("container")}>
            <Field label="Color de fondo">
              <CI value={design.bg_color} onChange={(v) => set("bg_color", v)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Padding vertical (px)">
                <NI value={design.padding_y} onChange={(v) => set("padding_y", Number(v) || 0)} min={0} max={80} />
              </Field>
              <Field label="Padding horizontal (px)">
                <NI value={design.padding_x} onChange={(v) => set("padding_x", Number(v) || 0)} min={0} max={80} />
              </Field>
            </div>
            <Field label="Ancho máximo (px)">
              <NI value={design.max_width} onChange={(v) => set("max_width", Number(v) || 560)} min={320} max={700} />
            </Field>
            <Field label="Tipografía">
              <select
                value={design.font_family}
                onChange={(e) => set("font_family", e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                {FONT_OPTIONS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </Field>
          </Section>

          <Section title="Tarjeta de producto" open={openSections.card} onToggle={() => toggleSection("card")}>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Radio imagen (px)">
                <NI value={design.image_radius} onChange={(v) => set("image_radius", Number(v) || 0)} min={0} max={40} />
              </Field>
              <Field label="Ancho máx. imagen (px)">
                <NI value={design.image_max_width} onChange={(v) => set("image_max_width", Number(v) || 120)} min={80} max={400} />
              </Field>
            </div>
            <Field label="Color título">
              <CI value={design.title_color} onChange={(v) => set("title_color", v)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Tamaño título (px)">
                <NI value={design.title_font_size} onChange={(v) => set("title_font_size", Number(v) || 14)} min={10} max={24} />
              </Field>
              <Field label="Peso título">
                <NI value={design.title_font_weight} onChange={(v) => set("title_font_weight", Number(v) || 600)} min={400} max={900} />
              </Field>
            </div>
            <Field label="Color precio">
              <CI value={design.price_color} onChange={(v) => set("price_color", v)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Tamaño precio (px)">
                <NI value={design.price_font_size} onChange={(v) => set("price_font_size", Number(v) || 15)} min={10} max={28} />
              </Field>
              <Field label="Peso precio">
                <NI value={design.price_font_weight} onChange={(v) => set("price_font_weight", Number(v) || 700)} min={400} max={900} />
              </Field>
            </div>
          </Section>

          <Section title="Botón" open={openSections.button} onToggle={() => toggleSection("button")}>
            <Field label="Texto del botón">
              <TI value={design.btn_text} onChange={(v) => set("btn_text", v)} />
            </Field>
            <Field label="Color del botón">
              <CI value={design.btn_bg} onChange={(v) => set("btn_bg", v)} />
            </Field>
            <Field label="Color del texto">
              <CI value={design.btn_text_color} onChange={(v) => set("btn_text_color", v)} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Tamaño texto (px)">
                <NI value={design.btn_font_size} onChange={(v) => set("btn_font_size", Number(v) || 12)} min={10} max={18} />
              </Field>
              <Field label="Border radius (px)">
                <NI value={design.btn_border_radius} onChange={(v) => set("btn_border_radius", Number(v) || 0)} min={0} max={40} />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Padding vertical (px)">
                <NI value={design.btn_padding_y} onChange={(v) => set("btn_padding_y", Number(v) || 0)} min={4} max={24} />
              </Field>
              <Field label="Padding horizontal (px)">
                <NI value={design.btn_padding_x} onChange={(v) => set("btn_padding_x", Number(v) || 0)} min={8} max={40} />
              </Field>
            </div>
          </Section>

          {block.block_key === "featured_product_html" && (
            <Section title="Badge de descuento" open={openSections.badge} onToggle={() => toggleSection("badge")}>
              <label className="flex items-center gap-2 cursor-pointer mb-3">
                <input
                  type="checkbox"
                  checked={design.show_discount_badge}
                  onChange={(e) => set("show_discount_badge", e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                />
                <span className="text-sm text-gray-700">Mostrar badge con {"{{ descuento_producto_mes }}"}% OFF</span>
              </label>
              {design.show_discount_badge && (
                <>
                  <Field label="Color fondo badge">
                    <CI value={design.discount_badge_bg} onChange={(v) => set("discount_badge_bg", v)} />
                  </Field>
                  <Field label="Color texto badge">
                    <CI value={design.discount_badge_text_color} onChange={(v) => set("discount_badge_text_color", v)} />
                  </Field>
                  <p className="text-xs text-gray-400">
                    El porcentaje real lo define la automatización «Producto del mes». En la vista previa se usa 20%.
                  </p>
                </>
              )}
            </Section>
          )}

          <div className="border border-gray-200 rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setShowSamples((v) => !v)}
              className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-gray-800 hover:bg-gray-50"
            >
              Productos de ejemplo
              {showSamples ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
            </button>
            {showSamples && (
              <div className="px-4 pb-4 border-t border-gray-100 pt-3">
                <textarea
                  value={samplesJson}
                  onChange={(e) => setSamplesJson(e.target.value)}
                  rows={8}
                  className="w-full font-mono text-xs border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                  spellCheck={false}
                />
                {jsonError && <p className="text-xs text-red-600 mt-1">{jsonError}</p>}
                <p className="text-xs text-gray-400 mt-2">
                  Solo para vista previa. Los envíos reales usan productos de Shopify.
                </p>
              </div>
            )}
          </div>

          <div className="border border-gray-200 rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setShowCode((v) => !v)}
              className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-gray-800 hover:bg-gray-50"
            >
              <span className="flex items-center gap-2">
                <Code size={14} />
                Código Jinja generado
              </span>
              {showCode ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
            </button>
            {showCode && (
              <div className="px-4 pb-4 border-t border-gray-100 pt-3">
                <textarea
                  readOnly
                  value={compiledTemplate}
                  rows={10}
                  className="w-full font-mono text-xs border border-gray-200 rounded-lg px-3 py-2 bg-gray-50 text-gray-600"
                  spellCheck={false}
                />
              </div>
            )}
          </div>

          <div className="flex gap-2 pt-1 sticky bottom-0 bg-white pb-1">
            <button
              type="button"
              onClick={() => setDesign(defaultDesignForBlock(block.block_key))}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
            >
              Restaurar
            </button>
            <button
              type="button"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
              className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
            >
              {saved ? <Check size={14} /> : <Save size={14} />}
              {saved ? "Guardado" : "Guardar diseño"}
            </button>
          </div>
        </div>

        <div className="p-5 bg-gray-50/80 min-h-[480px]">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium text-gray-700 flex items-center gap-2">
              <Eye size={14} />
              Vista previa en tiempo real
            </p>
            <div className="flex gap-1 bg-white border border-gray-200 rounded-lg p-0.5">
              <button
                type="button"
                onClick={() => setPreviewMode("desktop")}
                className={`p-1.5 rounded-md ${previewMode === "desktop" ? "bg-brand-100 text-brand-700" : "text-gray-400"}`}
                title="Escritorio"
              >
                <Monitor size={14} />
              </button>
              <button
                type="button"
                onClick={() => setPreviewMode("mobile")}
                className={`p-1.5 rounded-md ${previewMode === "mobile" ? "bg-brand-100 text-brand-700" : "text-gray-400"}`}
                title="Móvil"
              >
                <Smartphone size={14} />
              </button>
            </div>
          </div>

          <div
            className="mx-auto transition-all duration-200"
            style={{ maxWidth: previewMode === "mobile" ? 375 : "100%" }}
          >
            <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
              <div className="px-3 py-2 border-b border-gray-100 bg-gray-50 text-[10px] text-gray-400 font-mono text-center">
                {`{{ ${block.block_key} }}`} · productos de ejemplo
              </div>
              <div className="p-4 min-h-[320px]">
                <ProductBlockLivePreview
                  design={design}
                  products={samples}
                  discountPreview={20}
                  width={previewMode === "mobile" ? "full" : undefined}
                />
              </div>
            </div>

            {serverHtml && (
              <details className="mt-4">
                <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                  Ver HTML renderizado por el servidor (Jinja)
                </summary>
                <div
                  className="mt-2 border border-gray-200 rounded-lg bg-white p-4 overflow-auto max-h-64 text-sm"
                  dangerouslySetInnerHTML={{ __html: serverHtml }}
                />
              </details>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
