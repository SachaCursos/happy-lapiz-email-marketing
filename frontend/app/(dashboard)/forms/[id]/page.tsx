"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formsApi } from "@/lib/api";
import { SignupForm, FormSubmission, FormField } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeft, Copy, Check, Users, Code, Plus, Trash2,
  ChevronUp, ChevronDown, Save, Eye,
} from "lucide-react";
import Link from "next/link";

const BACKEND_URL =
  typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8000"
    : (process.env.NEXT_PUBLIC_API_URL ?? "https://email-marketing-back-end-production.up.railway.app");

const FIELD_TYPES = [
  { value: "text",     label: "Texto" },
  { value: "date",     label: "Fecha" },
  { value: "number",   label: "Número" },
  { value: "tel",      label: "Teléfono" },
  { value: "email",    label: "Email" },
  { value: "textarea", label: "Texto largo" },
  { value: "select",   label: "Desplegable" },
];

const HTML_TEMPLATE = (title: string, btnText: string, successMsg: string) => `<!--
  Popup personalizado Happy Lápiz
  Elementos requeridos: #hb-popup-form con input name="email"
  Opcional: #hb-popup-close para el botón de cerrar
             #hb-popup-success para el mensaje de éxito
-->
<div style="background:linear-gradient(135deg,#0369a1,#0ea5e9);padding:24px 48px 24px 24px;position:relative">
  <button id="hb-popup-close" style="position:absolute;top:12px;right:12px;background:rgba(255,255,255,0.2);border:none;color:#fff;width:28px;height:28px;border-radius:50%;cursor:pointer;font-size:18px;line-height:28px">×</button>
  <p style="margin:0 0 4px;color:rgba(255,255,255,0.7);font-size:11px;letter-spacing:2px;text-transform:uppercase;font-weight:700">Happy Lápiz</p>
  <h2 style="margin:0;color:#fff;font-size:20px;font-weight:700">${title}</h2>
</div>
<div style="padding:24px">
  <form id="hb-popup-form" novalidate>
    <label style="display:block;font-size:12px;color:#64748b;margin-bottom:4px">Tu nombre</label>
    <input name="name" type="text" placeholder="Nombre completo"
      style="width:100%;padding:10px 14px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:14px;margin-bottom:10px;box-sizing:border-box;outline:none" />

    <label style="display:block;font-size:12px;color:#64748b;margin-bottom:4px">Email *</label>
    <input name="email" type="email" placeholder="tu@email.com" required
      style="width:100%;padding:10px 14px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:14px;margin-bottom:10px;box-sizing:border-box;outline:none" />

    <!-- Añade más campos aquí -->

    <button type="submit"
      style="width:100%;padding:12px;background:linear-gradient(135deg,#0369a1,#0ea5e9);color:#fff;border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;margin-top:4px">
      ${btnText}
    </button>
  </form>

  <div id="hb-popup-success" style="display:none;text-align:center;padding:16px 0">
    <div style="font-size:40px;margin-bottom:8px">✅</div>
    <p style="color:#166534;font-weight:700;font-size:15px;margin:0">${successMsg}</p>
  </div>

  <p style="margin:12px 0 0;color:#94a3b8;font-size:11px;text-align:center">
    Respetamos tu privacidad. Puedes darte de baja cuando quieras.
  </p>
</div>`;

// ── Custom fields editor ──────────────────────────────────────────────────────
function FieldsEditor({
  fields,
  onChange,
}: {
  fields: FormField[];
  onChange: (f: FormField[]) => void;
}) {
  function update(i: number, patch: Partial<FormField>) {
    const next = fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f));
    onChange(next);
  }
  function remove(i: number) { onChange(fields.filter((_, idx) => idx !== i)); }
  function move(i: number, dir: -1 | 1) {
    const next = [...fields];
    const j = i + dir;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  }
  function add() {
    onChange([...fields, {
      key: `campo_${fields.length + 1}`,
      label: "Nuevo campo",
      type: "text",
      required: false,
      placeholder: "",
    }]);
  }

  return (
    <div className="space-y-3">
      {/* Fixed built-in fields (read-only display) */}
      <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Campos fijos</div>
      {["Nombre (texto)", "Email * (requerido)", "Teléfono (texto)"].map((l) => (
        <div key={l} className="flex items-center gap-3 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl opacity-60">
          <span className="text-sm text-gray-500">{l}</span>
          <span className="ml-auto text-xs text-gray-400">fijo</span>
        </div>
      ))}

      {/* Custom fields */}
      {fields.length > 0 && (
        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mt-4 mb-1">
          Campos personalizados
        </div>
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
              <select
                value={field.type}
                onChange={(e) => update(i, { type: e.target.value as FormField["type"] })}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                {FIELD_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Clave (name)</label>
              <input
                value={field.key}
                onChange={(e) => update(i, { key: e.target.value.toLowerCase().replace(/\s+/g, "_") })}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Placeholder</label>
              <input
                value={field.placeholder ?? ""}
                onChange={(e) => update(i, { placeholder: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
            {field.type === "select" && (
              <div className="col-span-3">
                <label className="block text-xs text-gray-500 mb-1">Opciones (una por línea)</label>
                <textarea
                  value={(field.options ?? []).join("\n")}
                  onChange={(e) => update(i, { options: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })}
                  rows={3}
                  className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-brand-500"
                  placeholder={"Opción 1\nOpción 2\nOpción 3"}
                />
              </div>
            )}
          </div>
        </div>
      ))}

      <button
        onClick={add}
        className="w-full flex items-center justify-center gap-2 py-3 border-2 border-dashed border-gray-200 rounded-xl text-sm text-gray-400 hover:text-brand-600 hover:border-brand-300 transition-colors"
      >
        <Plus size={15} /> Añadir campo
      </button>

      {fields.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-xs text-blue-700">
          <p className="font-semibold mb-1">Campos disponibles en emails:</p>
          <p className="font-mono">{fields.map((f) => `{{${f.key}}}`).join("  ")}</p>
        </div>
      )}
    </div>
  );
}

// ── HTML editor ───────────────────────────────────────────────────────────────
function HtmlEditor({
  form,
  onSave,
  saving,
}: {
  form: SignupForm;
  onSave: (html: string | null) => void;
  saving: boolean;
}) {
  const [enabled, setEnabled] = useState(!!form.html_override);
  const [html, setHtml] = useState(
    form.html_override || HTML_TEMPLATE(form.title, form.button_text, form.success_message)
  );
  const [tab, setTab] = useState<"editor" | "preview">("editor");

  return (
    <div className="space-y-4">
      <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-4 py-3 text-sm text-yellow-800">
        <p className="font-semibold mb-1">HTML personalizado</p>
        <p>Cuando está activado, el popup usa tu HTML en lugar del diseño automático.
        El sistema inyecta automáticamente la lógica de envío — solo necesitas incluir
        un <code className="font-mono bg-yellow-100 px-1 rounded">&lt;form id="hb-popup-form"&gt;</code> con
        un <code className="font-mono bg-yellow-100 px-1 rounded">input name="email"</code>.
        </p>
      </div>

      <label className="flex items-center gap-3 cursor-pointer">
        <div
          onClick={() => setEnabled((v) => !v)}
          className={`w-10 h-6 rounded-full transition-colors ${enabled ? "bg-brand-600" : "bg-gray-200"} relative cursor-pointer`}
        >
          <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all ${enabled ? "left-5" : "left-1"}`} />
        </div>
        <span className="text-sm font-medium text-gray-700">
          {enabled ? "HTML personalizado activado" : "HTML personalizado desactivado (usando diseño automático)"}
        </span>
      </label>

      {enabled && (
        <div className="border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex border-b border-gray-100">
            {(["editor", "preview"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                  tab === t ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                {t === "editor" ? "Editor HTML" : "Preview"}
              </button>
            ))}
          </div>
          {tab === "editor" ? (
            <textarea
              value={html}
              onChange={(e) => setHtml(e.target.value)}
              className="w-full p-4 font-mono text-xs text-gray-800 resize-none focus:outline-none"
              style={{ minHeight: 420 }}
              spellCheck={false}
            />
          ) : (
            <div className="bg-gradient-to-b from-sky-50 to-gray-100 p-6 flex justify-center" style={{ minHeight: 420 }}>
              <div
                className="bg-white rounded-2xl shadow-2xl overflow-hidden max-w-sm w-full border border-gray-200"
                dangerouslySetInnerHTML={{ __html: html }}
              />
            </div>
          )}
        </div>
      )}

      <button
        onClick={() => onSave(enabled ? html : null)}
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
      >
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
  const [activeTab, setActiveTab] = useState<"install" | "fields" | "html">("install");

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

  const [localFields, setLocalFields] = useState<FormField[] | null>(null);
  const [previewScreen, setPreviewScreen] = useState<1 | 2>(1);
  const [localCoupon, setLocalCoupon] = useState<string | null>(null);

  const embedCode = `<script src="${BACKEND_URL}/api/forms/${formId}/embed.js" async></script>`;

  function copyEmbed() {
    navigator.clipboard.writeText(embedCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (isLoading) return (
    <div className="p-8">
      <div className="h-5 bg-gray-200 rounded w-40 animate-pulse mb-4" />
      <div className="h-8 bg-gray-200 rounded w-64 animate-pulse" />
    </div>
  );

  if (!form) return (
    <div className="p-8">
      <Link href="/forms" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-4">
        <ArrowLeft size={15} /> Volver
      </Link>
      <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
        Formulario no encontrado.
      </div>
    </div>
  );

  const currentFields = localFields ?? (form.custom_form_fields ?? []);
  const TRIGGER_LABEL: Record<string, string> = {
    delay: `Después de ${form.popup_delay_seconds}s`,
    exit_intent: "Exit intent",
    scroll: `${form.popup_scroll_pct}% scroll`,
  };

  // Extra field keys from all submissions
  const extraKeys = Array.from(
    new Set(subsData?.submissions.flatMap((s) => Object.keys(s.extra_data ?? {})) ?? [])
  );

  return (
    <div className="p-8 max-w-3xl">
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
            {form.html_override && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs font-medium">HTML custom</span>}
          </div>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold text-gray-900">{subsData?.total ?? "—"}</p>
          <p className="text-xs text-gray-400 flex items-center gap-1 justify-end mt-0.5"><Users size={11} /> suscriptores</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6">
        {([
          { key: "install", label: "Instalación" },
          { key: "fields",  label: `Campos${currentFields.length ? ` (${currentFields.length})` : ""}` },
          { key: "html",    label: "HTML personalizado" },
        ] as { key: typeof activeTab; label: string }[]).map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === t.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-gray-500 hover:text-gray-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab: Instalación ── */}
      {activeTab === "install" && (
        <div className="space-y-6">
          {/* Embed code */}
          <div className="bg-gray-950 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-gray-400"><Code size={15} /><span className="text-sm font-medium">Código de instalación</span></div>
              <button onClick={copyEmbed} className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg text-xs font-medium transition-colors">
                {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                {copied ? "¡Copiado!" : "Copiar"}
              </button>
            </div>
            <p className="text-xs text-gray-500 mb-3">Pega esto antes del <code className="text-gray-400">&lt;/body&gt;</code> de hotboat.cl:</p>
            <pre className="text-xs text-green-400 font-mono break-all whitespace-pre-wrap">{embedCode}</pre>
          </div>

          {/* Coupon code */}
          <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
            <p className="text-sm font-semibold text-gray-700">Código de cupón (Pantalla 2)</p>
            <p className="text-xs text-gray-400">Si lo rellenas, aparecerá destacado después de que el visitante envíe el formulario.</p>
            <div className="flex gap-3">
              <input
                type="text"
                value={localCoupon ?? form.coupon_code ?? ""}
                onChange={(e) => setLocalCoupon(e.target.value.toUpperCase())}
                placeholder="Ej: DRON"
                className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono uppercase focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <button
                onClick={() => {
                  saveMutation.mutate({ coupon_code: localCoupon ?? form.coupon_code ?? null });
                  setLocalCoupon(null);
                }}
                disabled={saveMutation.isPending || localCoupon === null}
                className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors flex items-center gap-2"
              >
                <Save size={13} /> Guardar
              </button>
            </div>
          </div>

          {/* Preview */}
          {!form.html_override && (
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm font-semibold text-gray-700 flex items-center gap-2"><Eye size={14} className="text-gray-400" /> Vista previa</p>
                <div className="flex rounded-lg border border-gray-200 overflow-hidden text-xs font-medium">
                  <button onClick={() => setPreviewScreen(1)} className={`px-3 py-1.5 transition-colors ${previewScreen === 1 ? "bg-gray-900 text-white" : "text-gray-500 hover:bg-gray-50"}`}>Pantalla 1</button>
                  <button onClick={() => setPreviewScreen(2)} className={`px-3 py-1.5 transition-colors ${previewScreen === 2 ? "bg-gray-900 text-white" : "text-gray-500 hover:bg-gray-50"}`}>Pantalla 2</button>
                </div>
              </div>
              <div className="bg-gradient-to-b from-sky-50 to-gray-100 rounded-xl p-6 flex justify-center">
                <div className="bg-white rounded-2xl shadow-2xl overflow-hidden max-w-sm w-full border border-gray-200">
                  {previewScreen === 1 ? (
                    <>
                      <div className="bg-gradient-to-r from-sky-700 to-sky-500 px-6 py-5 relative">
                        <p className="text-xs text-sky-200 font-bold tracking-widest uppercase mb-1">HotBoat</p>
                        <h3 className="text-white font-bold text-lg">{form.title}</h3>
                      </div>
                      <div className="px-6 py-5 space-y-2">
                        {form.description && <p className="text-gray-500 text-sm mb-2">{form.description}</p>}
                        {form.collect_name && <div className="h-9 rounded-lg border border-gray-200 bg-gray-50 px-3 flex items-center text-sm text-gray-400">Tu nombre</div>}
                        <div className="h-9 rounded-lg border border-gray-200 bg-gray-50 px-3 flex items-center text-sm text-gray-400">Tu email *</div>
                        {form.collect_phone && <div className="h-9 rounded-lg border border-gray-200 bg-gray-50 px-3 flex items-center text-sm text-gray-400">Tu teléfono</div>}
                        {currentFields.map((f) => (
                          <div key={f.key} className="rounded-lg border border-gray-200 bg-gray-50 px-3 flex items-center text-sm text-gray-400" style={{ height: f.type === "textarea" ? 64 : 36 }}>
                            {f.label}{f.required ? " *" : ""}
                          </div>
                        ))}
                        <div className="h-10 rounded-xl bg-gradient-to-r from-sky-700 to-sky-500 flex items-center justify-center text-white text-sm font-bold">{form.button_text}</div>
                      </div>
                    </>
                  ) : (
                    <div className="px-6 py-8 text-center space-y-3">
                      <div className="text-4xl">✅</div>
                      <p className="text-green-700 font-bold text-sm">{form.success_message}</p>
                      {(localCoupon ?? form.coupon_code) && (
                        <div className="mt-2 p-4 bg-sky-50 border-2 border-dashed border-sky-400 rounded-xl">
                          <p className="text-xs text-gray-500 uppercase tracking-widest font-semibold mb-1">Tu cupón de reserva</p>
                          <p className="text-2xl font-black text-sky-700 tracking-widest">{localCoupon ?? form.coupon_code}</p>
                          <p className="text-xs text-gray-400 mt-1">Úsalo al reservar en hotboat.cl</p>
                        </div>
                      )}
                      <p className="text-xs text-gray-400">Respetamos tu privacidad. Puedes darte de baja cuando quieras.</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Submissions */}
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
                      {extraKeys.map((k) => (
                        <th key={k} className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{k}</th>
                      ))}
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Página</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fecha</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subsData.submissions.map((s) => (
                      <tr key={s.id} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="px-4 py-3 font-mono text-xs text-gray-700">{s.email}</td>
                        <td className="px-4 py-3 text-gray-600 text-xs">{s.name || "—"}</td>
                        {extraKeys.map((k) => (
                          <td key={k} className="px-4 py-3 text-gray-600 text-xs">{s.extra_data?.[k] || "—"}</td>
                        ))}
                        <td className="px-4 py-3 text-gray-400 text-xs truncate max-w-[160px]">
                          {s.source_url ? <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="hover:text-brand-600">{s.source_url.replace(/^https?:\/\/[^/]+/, "") || "/"}</a> : "—"}
                        </td>
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

      {/* ── Tab: Campos ── */}
      {activeTab === "fields" && (
        <div className="space-y-5">
          <FieldsEditor fields={currentFields} onChange={setLocalFields} />
          {localFields !== null && (
            <button
              onClick={() => {
                saveMutation.mutate({ custom_form_fields: localFields });
                setLocalFields(null);
              }}
              disabled={saveMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
            >
              <Save size={14} /> {saveMutation.isPending ? "Guardando…" : "Guardar campos"}
            </button>
          )}
        </div>
      )}

      {/* ── Tab: HTML ── */}
      {activeTab === "html" && (
        <HtmlEditor
          form={form}
          saving={saveMutation.isPending}
          onSave={(html) => saveMutation.mutate({ html_override: html })}
        />
      )}
    </div>
  );
}
