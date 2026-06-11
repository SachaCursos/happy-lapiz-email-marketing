"use client";

import { useState, useCallback, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formsApi } from "@/lib/api";
import { SignupForm, FormSubmission, FormField, FormDesign, FormStep } from "@/lib/types";
import type { Automation } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeft, Copy, Check, Users, Code, Plus, Trash2,
  ChevronUp, ChevronDown, Save, Eye, Palette, Layers,
  Tag, Settings, GripVertical,
} from "lucide-react";
import Link from "next/link";

const BACKEND_URL =
  typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8000"
    : (process.env.NEXT_PUBLIC_API_URL ?? "https://email-marketing-back-end-production.up.railway.app");

const DEFAULT_DESIGN: FormDesign = {
  header_bg: "#0369a1",
  header_bg2: "#0ea5e9",
  header_text: "#ffffff",
  body_bg: "#ffffff",
  btn_bg: "#0369a1",
  btn_bg2: "#0ea5e9",
  btn_text: "#ffffff",
  input_border: "#e2e8f0",
  border_radius: 16,
  font: "system-ui",
};

const HAPPY_LAPIZ_DESIGN: FormDesign = {
  header_bg: "#233dff",
  header_bg2: "#849bff",
  header_text: "#ffffff",
  body_bg: "#ffffff",
  btn_bg: "#ffd51e",
  btn_bg2: "#ffc827",
  btn_text: "#111111",
  input_border: "#d8dfff",
  border_radius: 16,
  font: "Poppins",
};

// Colores de marca Happy Lápiz (desde plantillas_de_la_marca)
const BRAND_PALETTE = [
  { hex: "#ffd51e", name: "Amarillo principal" },
  { hex: "#ffc827", name: "Amarillo oscuro" },
  { hex: "#233dff", name: "Azul fuerte" },
  { hex: "#849bff", name: "Azul claro" },
  { hex: "#d8dfff", name: "Azul pastel" },
  { hex: "#ffffff", name: "Blanco" },
  { hex: "#111111", name: "Negro" },
];

const FONTS = [
  { value: "Poppins", label: "Poppins ★ (tipografía Happy Lápiz)" },
  { value: "system-ui", label: "Sistema (por defecto)" },
  { value: "Inter", label: "Inter" },
  { value: "Georgia", label: "Georgia" },
  { value: "'Playfair Display'", label: "Playfair Display" },
  { value: "Montserrat", label: "Montserrat" },
  { value: "'DM Sans'", label: "DM Sans" },
];

const FIELD_TYPES = [
  { value: "text", label: "Texto" },
  { value: "date", label: "Fecha" },
  { value: "number", label: "Número" },
  { value: "tel", label: "Teléfono" },
  { value: "email", label: "Email" },
  { value: "textarea", label: "Texto largo" },
  { value: "select", label: "Desplegable" },
];

// ── Popup Preview ─────────────────────────────────────────────────────────────
function PopupPreview({
  form,
  design,
  steps,
  currentFields,
  previewStep = 0,
  couponCode,
}: {
  form: SignupForm;
  design: FormDesign;
  steps: FormStep[] | null;
  currentFields: FormField[];
  previewStep?: number;
  couponCode?: string;
}) {
  const r = design.border_radius;
  const headerStyle = {
    background: `linear-gradient(135deg, ${design.header_bg} 0%, ${design.header_bg2} 100%)`,
    padding: "20px 48px 20px 24px",
    position: "relative" as const,
  };
  const btnStyle = {
    width: "100%",
    padding: "12px",
    background: `linear-gradient(135deg, ${design.btn_bg}, ${design.btn_bg2})`,
    color: design.btn_text,
    border: "none",
    borderRadius: 10,
    fontSize: 15,
    fontWeight: 700,
    cursor: "default",
    marginTop: 4,
    fontFamily: design.font,
  };
  const inputStyle = {
    width: "100%",
    padding: "10px 14px",
    border: `1.5px solid ${design.input_border}`,
    borderRadius: 8,
    fontSize: 14,
    color: "#1e293b",
    marginBottom: 10,
    boxSizing: "border-box" as const,
    fontFamily: design.font,
  };

  const activeStep = steps && steps.length > 0 ? steps[previewStep] : null;
  const stepTitle = activeStep?.title || form.title;
  const stepDesc = activeStep?.description || form.description;
  const stepFields = activeStep?.fields || (
    (form.collect_name ? ["name"] : [])
      .concat(["email"])
      .concat(form.collect_phone ? ["phone"] : [])
      .concat(currentFields.map((f) => f.key))
  );
  const btnText = activeStep?.button_text ||
    (steps && previewStep < steps.length - 1 ? "Continuar →" : form.button_text);

  const fieldMap: Record<string, FormField> = {};
  currentFields.forEach((f) => { fieldMap[f.key] = f; });

  function renderFieldPreview(key: string) {
    if (key === "email") return <div key={key} style={{ ...inputStyle, color: "#94a3b8" }}>Tu email *</div>;
    if (key === "name") return <div key={key} style={{ ...inputStyle, color: "#94a3b8" }}>Tu nombre</div>;
    if (key === "phone") return <div key={key} style={{ ...inputStyle, color: "#94a3b8" }}>Tu teléfono</div>;
    const cf = fieldMap[key];
    if (!cf) return null;
    return <div key={key} style={{ ...inputStyle, color: "#94a3b8", height: cf.type === "textarea" ? 64 : 42 }}>{cf.label}{cf.required ? " *" : ""}</div>;
  }

  return (
    <div style={{ background: `linear-gradient(160deg,#f0f9ff,#f8fafc)`, padding: 24, display: "flex", justifyContent: "center", borderRadius: 12, minHeight: 320 }}>
      <div style={{ background: design.body_bg, borderRadius: r, overflow: "hidden", maxWidth: 380, width: "100%", boxShadow: "0 20px 60px rgba(0,0,0,0.15)", border: "1px solid #e2e8f0", fontFamily: design.font || "system-ui" }}>
        {/* Header */}
        <div style={headerStyle}>
          <div style={{ position: "absolute", top: 12, right: 12, background: "rgba(255,255,255,0.2)", width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", color: design.header_text, fontSize: 16, cursor: "default" }}>×</div>
          <h2 style={{ margin: 0, color: design.header_text, fontSize: 18, fontWeight: 700, lineHeight: 1.3 }}>{stepTitle}</h2>
          {stepDesc && <p style={{ margin: "4px 0 0", color: design.header_text, opacity: 0.8, fontSize: 13 }}>{stepDesc}</p>}
        </div>
        {/* Body */}
        <div style={{ padding: "20px 24px", background: design.body_bg }}>
          {/* Progress dots */}
          {steps && steps.length > 1 && (
            <div style={{ display: "flex", gap: 4, marginBottom: 16 }}>
              {steps.map((_, i) => (
                <div key={i} style={{ flex: 1, height: 4, borderRadius: 2, background: i <= previewStep ? design.btn_bg : "#e2e8f0", transition: "background .3s" }} />
              ))}
            </div>
          )}
          {stepFields.map((k) => renderFieldPreview(k))}
          <div style={btnStyle}>{btnText}</div>
        </div>
      </div>
    </div>
  );
}

const GOOGLE_FONT_URLS: Record<string, string> = {
  "Poppins": "https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap",
  "Montserrat": "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap",
  "'Playfair Display'": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&display=swap",
  "'DM Sans'": "https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600&display=swap",
};

// ── Design Editor ─────────────────────────────────────────────────────────────
function DesignEditor({
  design,
  onChange,
}: { design: FormDesign; onChange: (d: FormDesign) => void }) {
  // Load Google Font for live preview
  useEffect(() => {
    const url = GOOGLE_FONT_URLS[design.font];
    if (!url) return;
    if (document.querySelector(`link[href="${url}"]`)) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = url;
    document.head.appendChild(link);
  }, [design.font]);

  function set(key: keyof FormDesign, val: string | number) {
    onChange({ ...design, [key]: val });
  }

  function ColorRow({ label, k }: { label: string; k: keyof FormDesign }) {
    return (
      <div className="space-y-1.5">
        <label className="text-sm text-gray-600">{label}</label>
        <div className="flex items-center gap-2 flex-wrap">
          <input
            type="color"
            value={design[k] as string}
            onChange={(e) => set(k, e.target.value)}
            className="w-9 h-9 rounded-lg border border-gray-200 cursor-pointer p-0.5 shrink-0"
          />
          <input
            type="text"
            value={design[k] as string}
            onChange={(e) => set(k, e.target.value)}
            className="w-24 border border-gray-200 rounded-lg px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
          <div className="flex gap-1 flex-wrap">
            {BRAND_PALETTE.map((c) => (
              <button
                key={c.hex}
                type="button"
                title={c.name}
                onClick={() => set(k, c.hex)}
                className={`w-6 h-6 rounded-full border-2 hover:scale-110 transition-transform shrink-0 ${
                  (design[k] as string).toLowerCase() === c.hex.toLowerCase()
                    ? "border-gray-700 scale-110"
                    : "border-white shadow-sm"
                }`}
                style={{ background: c.hex }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Preset Happy Lápiz */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-yellow-800">Diseño Happy Lápiz</p>
          <p className="text-xs text-yellow-700 mt-0.5">Aplica los colores y tipografía oficiales de la marca con un clic.</p>
        </div>
        <button
          type="button"
          onClick={() => onChange({ ...HAPPY_LAPIZ_DESIGN })}
          className="shrink-0 px-4 py-2 bg-yellow-400 hover:bg-yellow-500 text-yellow-900 rounded-lg text-sm font-semibold transition-colors whitespace-nowrap"
        >
          Aplicar ★
        </button>
      </div>

      {/* Paleta de referencia */}
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Paleta Happy Lápiz</p>
        <div className="flex gap-2 flex-wrap">
          {BRAND_PALETTE.map((c) => (
            <div key={c.hex} className="flex flex-col items-center gap-1">
              <div className="w-8 h-8 rounded-lg border border-gray-200 shadow-sm" style={{ background: c.hex }} />
              <span className="text-xs text-gray-400 font-mono">{c.hex}</span>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-2">Haz clic en cualquier círculo de color para aplicarlo al campo correspondiente.</p>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <p className="text-sm font-semibold text-gray-700">Encabezado</p>
        <ColorRow label="Color primario" k="header_bg" />
        <ColorRow label="Color secundario" k="header_bg2" />
        <ColorRow label="Color texto header" k="header_text" />
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <p className="text-sm font-semibold text-gray-700">Cuerpo</p>
        <ColorRow label="Fondo del popup" k="body_bg" />
        <ColorRow label="Borde de inputs" k="input_border" />
        <div>
          <label className="text-sm text-gray-600">Radio de bordes</label>
          <div className="flex items-center gap-3 mt-1.5">
            <input
              type="range"
              min={0} max={32} step={2}
              value={design.border_radius}
              onChange={(e) => set("border_radius", Number(e.target.value))}
              className="flex-1 accent-brand-600"
            />
            <span className="text-xs text-gray-500 w-10">{design.border_radius}px</span>
          </div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <p className="text-sm font-semibold text-gray-700">Botón</p>
        <ColorRow label="Color botón" k="btn_bg" />
        <ColorRow label="Color botón 2" k="btn_bg2" />
        <ColorRow label="Texto del botón" k="btn_text" />
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <p className="text-sm font-semibold text-gray-700">Tipografía</p>
        <div>
          <label className="text-sm text-gray-600 block mb-1.5">Fuente</label>
          <select
            value={design.font}
            onChange={(e) => set("font", e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            {FONTS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
          {design.font === "Poppins" && (
            <p className="text-xs text-yellow-600 font-medium mt-1">★ Tipografía oficial Happy Lápiz</p>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={() => onChange({ ...DEFAULT_DESIGN })}
        className="text-xs text-gray-400 hover:text-gray-700 underline"
      >
        Restaurar colores por defecto
      </button>
    </div>
  );
}

// ── Steps Editor ──────────────────────────────────────────────────────────────
function StepsEditor({
  steps,
  form,
  customFields,
  onChange,
}: {
  steps: FormStep[] | null;
  form: SignupForm;
  customFields: FormField[];
  onChange: (s: FormStep[] | null) => void;
}) {
  const isMultiStep = steps !== null && steps.length > 0;

  const defaultSingleFields = (form.collect_name ? ["name"] : [])
    .concat(["email"])
    .concat(form.collect_phone ? ["phone"] : [])
    .concat(customFields.map((f) => f.key));

  const ALL_FIELDS = [
    { key: "email", label: "Email *" },
    { key: "name", label: "Nombre" },
    { key: "phone", label: "Teléfono" },
    ...customFields.map((f) => ({ key: f.key, label: f.label })),
  ];

  function enableMultiStep() {
    onChange([
      { step: 1, title: form.title, description: form.description || "", fields: ["email", "name"], button_text: "Continuar →" },
      { step: 2, title: "¡Casi listo!", description: "Cuéntanos un poco más", fields: defaultSingleFields.filter((k) => k !== "email" && k !== "name"), button_text: form.button_text },
    ]);
  }

  function useGiftTemplate() {
    const giftFields = customFields.map((f) => f.key);
    onChange([
      {
        step: 1,
        title: form.title || "¡Únete y recibe ofertas!",
        description: form.description || "Suscríbete para recibir novedades exclusivas.",
        fields: ["email", "name"],
        button_text: "Continuar →",
      },
      {
        step: 2,
        title: "Cuéntanos más 🎁",
        description: "Así podemos enviarte lo que más te sirve.",
        fields: giftFields.length > 0 ? giftFields : ["para_quien", "destinatario_nombre", "destinatario_edad", "destinatario_cumpleanos"],
        button_text: form.button_text || "Suscribirme",
      },
    ]);
  }

  function disableMultiStep() { onChange(null); }

  function addStep() {
    const newStep: FormStep = { step: (steps?.length || 0) + 1, title: "", description: "", fields: [], button_text: "Continuar →" };
    onChange([...(steps || []), newStep]);
  }

  function updateStep(idx: number, patch: Partial<FormStep>) {
    if (!steps) return;
    onChange(steps.map((s, i) => (i === idx ? { ...s, ...patch } : s)));
  }

  function removeStep(idx: number) {
    if (!steps || steps.length <= 1) return;
    onChange(steps.filter((_, i) => i !== idx).map((s, i) => ({ ...s, step: i + 1 })));
  }

  function toggleField(stepIdx: number, fieldKey: string) {
    if (!steps) return;
    const step = steps[stepIdx];
    const has = step.fields.includes(fieldKey);
    const next = has ? step.fields.filter((k) => k !== fieldKey) : [...step.fields, fieldKey];
    updateStep(stepIdx, { fields: next });
  }

  return (
    <div className="space-y-5">
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-sm text-blue-700">
        Los pasos múltiples permiten dividir el formulario en varias pantallas. Por ejemplo: paso 1 pide email + nombre, paso 2 pregunta por el destinatario del regalo.
      </div>

      {!isMultiStep && (
        <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 space-y-2">
          <p className="text-xs font-semibold text-purple-700">Plantillas rápidas</p>
          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={enableMultiStep}
              className="px-3 py-2 bg-white border border-purple-300 text-purple-700 rounded-lg text-xs font-medium hover:bg-purple-50 transition-colors"
            >
              2 pasos — básico (email → más datos)
            </button>
            <button
              type="button"
              onClick={useGiftTemplate}
              className="px-3 py-2 bg-purple-600 text-white rounded-lg text-xs font-medium hover:bg-purple-700 transition-colors"
            >
              🎁 2 pasos — flujo regalo (email+nombre → info destinatario)
            </button>
          </div>
        </div>
      )}

      <label className="flex items-center gap-3 cursor-pointer">
        <div
          onClick={() => (isMultiStep ? disableMultiStep() : enableMultiStep())}
          className={`w-10 h-6 rounded-full transition-colors ${isMultiStep ? "bg-brand-600" : "bg-gray-200"} relative cursor-pointer`}
        >
          <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all ${isMultiStep ? "left-5" : "left-1"}`} />
        </div>
        <span className="text-sm font-medium text-gray-700">
          {isMultiStep ? "Formulario multi-paso activado" : "Formulario de un solo paso (desactivado)"}
        </span>
      </label>

      {isMultiStep && steps && (
        <div className="space-y-4">
          {steps.map((step, idx) => (
            <div key={idx} className="border border-gray-200 rounded-xl bg-white overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-3 bg-gray-50 border-b border-gray-100">
                <GripVertical size={14} className="text-gray-300" />
                <span className="text-sm font-semibold text-gray-700">Paso {idx + 1}</span>
                <span className="ml-auto text-xs text-gray-400">{step.fields.length} campos</span>
                {steps.length > 1 && (
                  <button onClick={() => removeStep(idx)} className="text-red-400 hover:text-red-600">
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
              <div className="p-4 grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Título del paso</label>
                  <input
                    value={step.title}
                    onChange={(e) => updateStep(idx, { title: e.target.value })}
                    placeholder={form.title}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Texto del botón</label>
                  <input
                    value={step.button_text}
                    onChange={(e) => updateStep(idx, { button_text: e.target.value })}
                    placeholder={idx < steps.length - 1 ? "Continuar →" : form.button_text}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs text-gray-500 mb-1">Descripción (opcional)</label>
                  <input
                    value={step.description}
                    onChange={(e) => updateStep(idx, { description: e.target.value })}
                    placeholder="Descripción corta del paso"
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs text-gray-500 mb-2">Campos en este paso</label>
                  <div className="flex flex-wrap gap-2">
                    {ALL_FIELDS.map((f) => {
                      const checked = step.fields.includes(f.key);
                      return (
                        <button
                          key={f.key}
                          onClick={() => toggleField(idx, f.key)}
                          className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                            checked
                              ? "bg-brand-100 border-brand-400 text-brand-700"
                              : "bg-gray-50 border-gray-200 text-gray-500 hover:bg-gray-100"
                          }`}
                        >
                          {f.label}
                        </button>
                      );
                    })}
                  </div>
                  {step.fields.length === 0 && (
                    <p className="text-xs text-red-500 mt-1">Selecciona al menos un campo</p>
                  )}
                </div>
              </div>
            </div>
          ))}

          <button
            onClick={addStep}
            className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 hover:text-brand-600 hover:border-brand-300 transition-colors"
          >
            <Plus size={15} /> Añadir paso
          </button>
        </div>
      )}
    </div>
  );
}

// ── Preset fields for common use cases ────────────────────────────────────────
const PRESET_FIELDS: FormField[] = [
  {
    key: "para_quien",
    label: "¿Para quién es el regalo?",
    type: "select",
    required: false,
    placeholder: "",
    options: ["Para mí", "Para un regalo"],
  },
  {
    key: "destinatario_nombre",
    label: "¿Cómo se llama?",
    type: "text",
    required: false,
    placeholder: "Nombre del destinatario",
  },
  {
    key: "destinatario_edad",
    label: "¿Qué edad tiene?",
    type: "select",
    required: false,
    placeholder: "",
    options: ["0-3 años", "4-6 años", "7-9 años", "10-12 años", "13-17 años", "18-25 años", "26-40 años", "40+ años"],
  },
  {
    key: "destinatario_cumpleanos",
    label: "¿Cuál es su fecha de cumpleaños?",
    type: "date",
    required: false,
    placeholder: "",
  },
];

// ── Custom fields editor ──────────────────────────────────────────────────────
function FieldsEditor({ fields, onChange }: { fields: FormField[]; onChange: (f: FormField[]) => void }) {
  // Raw textarea value per field index — lets the user type spaces freely;
  // only converted to the options array on blur (trim happens then, not on every keystroke).
  const [rawOptions, setRawOptions] = useState<Record<number, string>>({});

  function update(i: number, patch: Partial<FormField>) {
    onChange(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));
  }
  function remove(i: number) {
    setRawOptions((prev) => { const next = { ...prev }; delete next[i]; return next; });
    onChange(fields.filter((_, idx) => idx !== i));
  }
  function move(i: number, dir: -1 | 1) {
    const next = [...fields];
    const j = i + dir;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  }
  function add() {
    onChange([...fields, { key: `campo_${fields.length + 1}`, label: "Nuevo campo", type: "text", required: false, placeholder: "" }]);
  }
  function addPreset(preset: FormField) {
    if (fields.some((f) => f.key === preset.key)) return;
    onChange([...fields, preset]);
  }

  const existingKeys = new Set(fields.map((f) => f.key));

  return (
    <div className="space-y-3">
      {/* Suggested presets */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
        <p className="text-xs font-semibold text-amber-700 mb-2.5">✨ Campos sugeridos para Happy Lápiz</p>
        <div className="flex flex-wrap gap-2">
          {PRESET_FIELDS.map((preset) => {
            const added = existingKeys.has(preset.key);
            return (
              <button
                key={preset.key}
                onClick={() => addPreset(preset)}
                disabled={added}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  added
                    ? "bg-green-100 border-green-300 text-green-700 cursor-default"
                    : "bg-white border-amber-300 text-amber-800 hover:bg-amber-100 hover:border-amber-400"
                }`}
              >
                {added ? "✓ " : "+ "}{preset.label}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-amber-600 mt-2">Haz clic para agregar. Luego ve a la pestaña <strong>Pasos</strong> para distribuirlos en múltiples pantallas.</p>
      </div>

      <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Campos fijos</div>
      {["Email * (requerido)", "Nombre (opcional)", "Teléfono (opcional)"].map((l) => (
        <div key={l} className="flex items-center gap-3 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl opacity-60">
          <span className="text-sm text-gray-500">{l}</span>
          <span className="ml-auto text-xs text-gray-400">fijo</span>
        </div>
      ))}

      {fields.length > 0 && (
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mt-4 mb-1">Campos personalizados</div>
      )}
      {fields.map((field, i) => (
        <div key={i} className="border border-gray-200 rounded-xl bg-white overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 bg-gray-50 border-b border-gray-100">
            <div className="flex flex-col gap-0.5">
              <button onClick={() => move(i, -1)} disabled={i === 0} className="text-gray-400 hover:text-gray-700 disabled:opacity-30"><ChevronUp size={13} /></button>
              <button onClick={() => move(i, 1)} disabled={i === fields.length - 1} className="text-gray-400 hover:text-gray-700 disabled:opacity-30"><ChevronDown size={13} /></button>
            </div>
            <input
              value={field.label}
              onChange={(e) => update(i, { label: e.target.value })}
              placeholder="Etiqueta del campo"
              className="flex-1 bg-transparent text-sm font-medium text-gray-800 outline-none"
            />
            <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer">
              <input type="checkbox" checked={field.required} onChange={(e) => update(i, { required: e.target.checked })} className="accent-brand-600" />
              Requerido
            </label>
            <button onClick={() => remove(i)} className="text-red-400 hover:text-red-600 ml-1"><Trash2 size={13} /></button>
          </div>
          <div className="px-4 py-3 grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Tipo</label>
              <select value={field.type} onChange={(e) => update(i, { type: e.target.value as FormField["type"] })} className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-brand-500">
                {FIELD_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Clave (name)</label>
              <input value={field.key} onChange={(e) => update(i, { key: e.target.value.toLowerCase().replace(/\s+/g, "_") })} className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Placeholder</label>
              <input value={field.placeholder ?? ""} onChange={(e) => update(i, { placeholder: e.target.value })} className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500" />
            </div>
            {field.type === "select" && (
              <div className="col-span-3">
                <label className="block text-xs text-gray-500 mb-1">Opciones (una por línea)</label>
                <textarea
                  value={rawOptions[i] !== undefined ? rawOptions[i] : (field.options ?? []).join("\n")}
                  onChange={(e) => setRawOptions((prev) => ({ ...prev, [i]: e.target.value }))}
                  onBlur={(e) => {
                    const opts = e.target.value.split("\n").map((s) => s.trim()).filter((s) => s.length > 0);
                    update(i, { options: opts });
                    setRawOptions((prev) => { const next = { ...prev }; delete next[i]; return next; });
                  }}
                  rows={3}
                  className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-brand-500"
                  placeholder={"Opción 1\nOpción 2"}
                />
              </div>
            )}
          </div>
        </div>
      ))}

      <button onClick={add} className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 hover:text-brand-600 hover:border-brand-300 transition-colors">
        <Plus size={15} /> Añadir campo personalizado
      </button>
    </div>
  );
}

// ── Coupon Editor ─────────────────────────────────────────────────────────────
function CouponEditor({
  form,
  onSave,
  saving,
}: { form: SignupForm; onSave: (data: Partial<SignupForm>) => void; saving: boolean }) {
  const [couponType, setCouponType] = useState<"none" | "static" | "dynamic">(
    form.coupon_campaign_id ? "dynamic" : form.coupon_code ? "static" : "none"
  );
  const [staticCode, setStaticCode] = useState(form.coupon_code || "");
  const [campaignId, setCampaignId] = useState<number | null>(form.coupon_campaign_id);
  const [automationId, setAutomationId] = useState<number | null>(form.coupon_automation_id);

  const { data: campaigns } = useQuery({
    queryKey: ["coupon-campaigns"],
    queryFn: () => fetch(`${BACKEND_URL}/api/coupons/campaigns`, { credentials: "include" }).then((r) => r.json()),
    staleTime: 60_000,
  });
  const { data: automations } = useQuery<Automation[]>({
    queryKey: ["automations"],
    queryFn: () => fetch(`${BACKEND_URL}/api/automations`, { credentials: "include" }).then((r) => r.json()),
    staleTime: 60_000,
  });

  function save() {
    if (couponType === "none") {
      onSave({ coupon_code: null, coupon_campaign_id: null, coupon_automation_id: null });
    } else if (couponType === "static") {
      onSave({ coupon_code: staticCode || null, coupon_campaign_id: null, coupon_automation_id: automationId });
    } else {
      onSave({ coupon_code: null, coupon_campaign_id: campaignId, coupon_automation_id: automationId });
    }
  }

  return (
    <div className="space-y-5">
      <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
        <p className="text-sm font-semibold text-gray-700">Tipo de cupón</p>
        <div className="space-y-2">
          {[
            { value: "none", label: "Sin cupón", desc: "El formulario no ofrece cupón" },
            { value: "static", label: "Cupón estático", desc: "Mismo código para todos (ej: BIENVENIDO10)" },
            { value: "dynamic", label: "Cupón dinámico (Shopify)", desc: "Código único generado en Shopify para cada persona" },
          ].map((opt) => (
            <label key={opt.value} className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${couponType === opt.value ? "border-brand-400 bg-brand-50" : "border-gray-200 hover:bg-gray-50"}`}>
              <input type="radio" name="couponType" value={opt.value} checked={couponType === opt.value} onChange={() => setCouponType(opt.value as typeof couponType)} className="mt-0.5 accent-brand-600" />
              <div>
                <p className="text-sm font-medium text-gray-800">{opt.label}</p>
                <p className="text-xs text-gray-500">{opt.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {couponType === "static" && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <p className="text-sm font-semibold text-gray-700">Código de cupón</p>
          <input
            type="text"
            value={staticCode}
            onChange={(e) => setStaticCode(e.target.value.toUpperCase())}
            placeholder="Ej: BIENVENIDO10"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono uppercase focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      )}

      {couponType === "dynamic" && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <p className="text-sm font-semibold text-gray-700">Campaña de cupones Shopify</p>
          {!campaigns || campaigns.length === 0 ? (
            <p className="text-sm text-gray-400">No hay campañas de cupones. Créalas en la sección <strong>Cupones</strong>.</p>
          ) : (
            <select
              value={campaignId ?? ""}
              onChange={(e) => setCampaignId(Number(e.target.value) || null)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              <option value="">Seleccionar campaña…</option>
              {campaigns.map((c: { id: number; name: string; discount_value: number; discount_type: string }) => (
                <option key={c.id} value={c.id}>{c.name} — {c.discount_value}{c.discount_type === "percentage" ? "%" : " CLP"} off</option>
              ))}
            </select>
          )}
        </div>
      )}

      {couponType !== "none" && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <p className="text-sm font-semibold text-gray-700">Email automático con cupón</p>
          <p className="text-xs text-gray-400">Opcional: selecciona una automatización tipo "Bienvenida" para enviar el cupón por email. El cupón estará disponible como <code className="font-mono bg-gray-100 px-1 rounded">{"{{coupon_code}}"}</code> en la plantilla.</p>
          <select
            value={automationId ?? ""}
            onChange={(e) => setAutomationId(Number(e.target.value) || null)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">Sin email automático</option>
            {(automations || []).map((a) => (
              <option key={a.id} value={a.id}>{a.name} ({a.trigger_type})</option>
            ))}
          </select>
        </div>
      )}

      <button
        onClick={save}
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
      >
        <Save size={14} /> {saving ? "Guardando…" : "Guardar configuración"}
      </button>
    </div>
  );
}

// ── HTML editor ───────────────────────────────────────────────────────────────
function HtmlEditor({ form, onSave, saving }: { form: SignupForm; onSave: (html: string | null) => void; saving: boolean }) {
  const [enabled, setEnabled] = useState(!!form.html_override);
  const [html, setHtml] = useState(form.html_override || "");
  const [tab, setTab] = useState<"editor" | "preview">("editor");

  return (
    <div className="space-y-4">
      <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-4 py-3 text-sm text-yellow-800">
        <p className="font-semibold mb-1">HTML personalizado</p>
        <p>Cuando está activado, usa tu HTML en lugar del diseño automático. Incluye un <code className="font-mono bg-yellow-100 px-1 rounded">&lt;form id="hb-popup-form"&gt;</code> con <code className="font-mono bg-yellow-100 px-1 rounded">input name="email"</code>.</p>
      </div>
      <label className="flex items-center gap-3 cursor-pointer">
        <div onClick={() => setEnabled((v) => !v)} className={`w-10 h-6 rounded-full transition-colors ${enabled ? "bg-brand-600" : "bg-gray-200"} relative cursor-pointer`}>
          <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all ${enabled ? "left-5" : "left-1"}`} />
        </div>
        <span className="text-sm font-medium text-gray-700">{enabled ? "HTML activado" : "HTML desactivado"}</span>
      </label>
      {enabled && (
        <div className="border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex border-b border-gray-100">
            {(["editor", "preview"] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)} className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${tab === t ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-800"}`}>
                {t === "editor" ? "Editor" : "Preview"}
              </button>
            ))}
          </div>
          {tab === "editor" ? (
            <textarea value={html} onChange={(e) => setHtml(e.target.value)} className="w-full p-4 font-mono text-xs text-gray-800 resize-none focus:outline-none" style={{ minHeight: 420 }} spellCheck={false} />
          ) : (
            <div className="bg-gradient-to-b from-sky-50 to-gray-100 p-6 flex justify-center" style={{ minHeight: 420 }}>
              <div className="bg-white rounded-2xl shadow-2xl overflow-hidden max-w-sm w-full border border-gray-200" dangerouslySetInnerHTML={{ __html: html }} />
            </div>
          )}
        </div>
      )}
      <button onClick={() => onSave(enabled ? html : null)} disabled={saving} className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors">
        <Save size={14} /> {saving ? "Guardando…" : "Guardar HTML"}
      </button>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function FormDetailPage() {
  const { id } = useParams<{ id: string }>();
  const formId = Number(id);
  const qc = useQueryClient();
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"install" | "design" | "steps" | "fields" | "coupon" | "html">("install");
  const [previewStep, setPreviewStep] = useState(0);

  const { data: form, isLoading } = useQuery<SignupForm>({
    queryKey: ["form", formId],
    queryFn: () => formsApi.get(formId).then((r) => r.data),
    staleTime: 30_000,
  });

  const { data: subsData } = useQuery<{ total: number; submissions: FormSubmission[] }>({
    queryKey: ["form-submissions", formId],
    queryFn: () => formsApi.submissions(formId).then((r) => r.data),
    staleTime: 30_000,
    enabled: !!formId,
  });

  const saveMutation = useMutation({
    mutationFn: (data: Partial<SignupForm>) => formsApi.update(formId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["form", formId] }),
  });

  // Local draft states
  const [localFields, setLocalFields] = useState<FormField[] | null>(null);
  const [localDesign, setLocalDesign] = useState<FormDesign | null>(null);
  const [localSteps, setLocalSteps] = useState<FormStep[] | null | "unset">("unset");

  const embedCode = `<script src="${BACKEND_URL}/api/forms/${formId}/embed.js" async></script>`;

  function copyEmbed() {
    navigator.clipboard.writeText(embedCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (isLoading) return <div className="p-8"><div className="h-5 bg-gray-200 rounded w-40 animate-pulse mb-4" /><div className="h-8 bg-gray-200 rounded w-64 animate-pulse" /></div>;
  if (!form) return <div className="p-8"><Link href="/forms" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-4"><ArrowLeft size={15} /> Volver</Link><div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">Formulario no encontrado.</div></div>;

  const currentFields = localFields ?? (form.custom_form_fields ?? []);
  const currentDesign: FormDesign = { ...DEFAULT_DESIGN, ...(form.design_config || {}), ...(localDesign || {}) };
  const currentSteps: FormStep[] | null = localSteps === "unset" ? (form.steps_config ?? null) : localSteps;

  const TABS = [
    { key: "install", label: "Instalación", icon: Code },
    { key: "design", label: "Diseño", icon: Palette },
    { key: "steps", label: "Pasos", icon: Layers },
    { key: "fields", label: `Campos${currentFields.length ? ` (${currentFields.length})` : ""}`, icon: Settings },
    { key: "coupon", label: "Cupón", icon: Tag },
    { key: "html", label: "HTML", icon: Code },
  ] as { key: typeof activeTab; label: string; icon: typeof Code }[];

  const TRIGGER_LABEL: Record<string, string> = {
    delay: `Después de ${form.popup_delay_seconds}s`,
    exit_intent: "Exit intent",
    scroll: `${form.popup_scroll_pct}% scroll`,
  };

  const hasCoupon = form.coupon_campaign_id || form.coupon_code;

  return (
    <div className="p-8">
      <Link href="/forms" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-6">
        <ArrowLeft size={15} /> Volver a formularios
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{form.name}</h1>
          <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${form.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
              {form.status === "active" ? "Activo" : "Pausado"}
            </span>
            <span>{TRIGGER_LABEL[form.popup_trigger]}</span>
            {currentSteps && currentSteps.length > 1 && <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium">{currentSteps.length} pasos</span>}
            {hasCoupon && <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs font-medium">Con cupón</span>}
          </div>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold text-gray-900">{subsData?.total ?? "—"}</p>
          <p className="text-xs text-gray-400 flex items-center gap-1 justify-end mt-0.5"><Users size={11} /> suscriptores</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-8">
        {/* Left: tabs */}
        <div className="xl:col-span-3">
          {/* Tab bar */}
          <div className="flex flex-wrap gap-1 border-b border-gray-200 mb-6">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeTab === t.key ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                <t.icon size={13} />
                {t.label}
              </button>
            ))}
          </div>

          {/* ── Tab: Instalación ── */}
          {activeTab === "install" && (
            <div className="space-y-6">
              <div className="bg-gray-950 rounded-xl p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-gray-400"><Code size={15} /><span className="text-sm font-medium">Código de instalación</span></div>
                  <button onClick={copyEmbed} className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg text-xs font-medium transition-colors">
                    {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                    {copied ? "¡Copiado!" : "Copiar"}
                  </button>
                </div>
                <p className="text-xs text-gray-500 mb-3">Pega esto antes del <code className="text-gray-400">&lt;/body&gt;</code> de tu sitio:</p>
                <pre className="text-xs text-green-400 font-mono break-all whitespace-pre-wrap">{embedCode}</pre>
              </div>

              {/* Submissions table */}
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100">
                  <h2 className="text-sm font-semibold text-gray-700">
                    Últimas suscripciones
                    {subsData && subsData.total > subsData.submissions.length && (
                      <span className="ml-2 text-xs font-normal text-gray-400">(mostrando {subsData.submissions.length} de {subsData.total})</span>
                    )}
                  </h2>
                </div>
                {!subsData || subsData.submissions.length === 0 ? (
                  <div className="p-12 text-center"><Users size={32} className="mx-auto text-gray-200 mb-3" /><p className="text-gray-400 text-sm">Sin suscripciones aún.</p></div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-100">
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nombre</th>
                          {hasCoupon && <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cupón</th>}
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fecha</th>
                        </tr>
                      </thead>
                      <tbody>
                        {subsData.submissions.map((s) => (
                          <tr key={s.id} className="border-b border-gray-50 hover:bg-gray-50">
                            <td className="px-4 py-3 font-mono text-xs text-gray-700">{s.email}</td>
                            <td className="px-4 py-3 text-gray-600 text-xs">{s.name || "—"}</td>
                            {hasCoupon && <td className="px-4 py-3 text-xs font-mono text-amber-700">{s.coupon_code || "—"}</td>}
                            <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{formatDate(s.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── Tab: Diseño ── */}
          {activeTab === "design" && (
            <div className="space-y-4">
              <DesignEditor design={currentDesign} onChange={(d) => setLocalDesign(d)} />
              <button
                onClick={() => { saveMutation.mutate({ design_config: currentDesign }); setLocalDesign(null); }}
                disabled={saveMutation.isPending || localDesign === null}
                className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-40 transition-colors"
              >
                <Save size={14} /> {saveMutation.isPending ? "Guardando…" : localDesign === null ? "Sin cambios" : "Guardar diseño"}
              </button>
            </div>
          )}

          {/* ── Tab: Pasos ── */}
          {activeTab === "steps" && (
            <div className="space-y-4">
              <StepsEditor
                steps={currentSteps}
                form={form}
                customFields={currentFields}
                onChange={(s) => setLocalSteps(s)}
              />
              {localSteps !== "unset" && (
                <button
                  onClick={() => { saveMutation.mutate({ steps_config: currentSteps ?? [] }); setLocalSteps("unset"); }}
                  disabled={saveMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
                >
                  <Save size={14} /> {saveMutation.isPending ? "Guardando…" : "Guardar pasos"}
                </button>
              )}
            </div>
          )}

          {/* ── Tab: Campos ── */}
          {activeTab === "fields" && (
            <div className="space-y-5">
              <FieldsEditor fields={currentFields} onChange={setLocalFields} />
              {localFields !== null && (
                <button
                  onClick={() => { saveMutation.mutate({ custom_form_fields: localFields }); setLocalFields(null); }}
                  disabled={saveMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
                >
                  <Save size={14} /> {saveMutation.isPending ? "Guardando…" : "Guardar campos"}
                </button>
              )}
            </div>
          )}

          {/* ── Tab: Cupón ── */}
          {activeTab === "coupon" && (
            <CouponEditor form={form} onSave={(d) => saveMutation.mutate(d)} saving={saveMutation.isPending} />
          )}

          {/* ── Tab: HTML ── */}
          {activeTab === "html" && (
            <HtmlEditor form={form} saving={saveMutation.isPending} onSave={(html) => saveMutation.mutate({ html_override: html })} />
          )}
        </div>

        {/* Right: live preview */}
        {!form.html_override && (
          <div className="xl:col-span-2">
            <div className="sticky top-6">
              <div className="flex items-center gap-2 mb-3">
                <Eye size={14} className="text-gray-400" />
                <p className="text-sm font-semibold text-gray-700">Vista previa</p>
                {currentSteps && currentSteps.length > 1 && (
                  <div className="ml-auto flex items-center gap-1">
                    {currentSteps.map((_, i) => (
                      <button
                        key={i}
                        onClick={() => setPreviewStep(i)}
                        className={`w-7 h-7 rounded-full text-xs font-medium transition-colors ${previewStep === i ? "bg-brand-600 text-white" : "bg-gray-100 text-gray-500 hover:bg-gray-200"}`}
                      >
                        {i + 1}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <PopupPreview
                form={form}
                design={currentDesign}
                steps={currentSteps}
                currentFields={currentFields}
                previewStep={previewStep}
                couponCode={form.coupon_code || undefined}
              />
              <p className="text-xs text-center text-gray-400 mt-3">La vista previa se actualiza en tiempo real</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
