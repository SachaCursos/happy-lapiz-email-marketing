"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { campaignsApi, segmentsApi, templatesApi } from "@/lib/api";
import { Segment, Template, CampaignVariant } from "@/lib/types";
import { ArrowLeft, ArrowRight, Check, Calendar, X, FlaskConical, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const STEPS = ["Información", "Segmento", "Revisar"];

const VARIANT_COLORS = [
  { bg: "bg-purple-100", text: "text-purple-700", border: "border-purple-300" },
  { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-300" },
  { bg: "bg-teal-100",   text: "text-teal-700",   border: "border-teal-300" },
  { bg: "bg-pink-100",   text: "text-pink-700",   border: "border-pink-300" },
];

interface VariantState {
  variant: string;
  subject: string;
  templateId: number | "";
  weight: number;
}

function VariantEditor({
  variants,
  templates,
  onChange,
}: {
  variants: VariantState[];
  templates: Template[];
  onChange: (v: VariantState[]) => void;
}) {
  const totalWeight = variants.reduce((s, v) => s + v.weight, 0);

  function addVariant() {
    const labels = ["A", "B", "C", "D"];
    const next = labels[variants.length] ?? String(variants.length + 1);
    const even = Math.floor(100 / (variants.length + 1));
    onChange([...variants.map((v) => ({ ...v, weight: even })), { variant: next, subject: "", templateId: "", weight: even }]);
  }

  function removeVariant(idx: number) {
    if (variants.length <= 2) return;
    const updated = variants.filter((_, i) => i !== idx);
    const even = Math.floor(100 / updated.length);
    onChange(updated.map((v) => ({ ...v, weight: even })));
  }

  function update(idx: number, patch: Partial<VariantState>) {
    onChange(variants.map((v, i) => (i === idx ? { ...v, ...patch } : v)));
  }

  return (
    <div className="space-y-3">
      {variants.map((v, i) => {
        const col = VARIANT_COLORS[i % VARIANT_COLORS.length];
        return (
          <div key={v.variant} className={`rounded-lg border ${col.border} bg-white p-3 space-y-2`}>
            <div className="flex items-center justify-between">
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${col.bg} ${col.text}`}>
                Variante {v.variant}
              </span>
              <div className="flex items-center gap-2">
                <label className="text-xs text-gray-500">Peso</label>
                <input
                  type="number" min={1} max={100} value={v.weight}
                  onChange={(e) => update(i, { weight: Math.max(1, Number(e.target.value)) })}
                  className="w-16 border border-gray-300 rounded px-2 py-1 text-xs text-center focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <span className="text-xs text-gray-400">%</span>
                {variants.length > 2 && (
                  <button type="button" onClick={() => removeVariant(i)} className="p-1 text-gray-400 hover:text-red-500 rounded">
                    <X size={12} />
                  </button>
                )}
              </div>
            </div>
            <select
              value={v.templateId}
              onChange={(e) => update(i, { templateId: Number(e.target.value) || "" })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Seleccionar plantilla...</option>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <input
              value={v.subject}
              onChange={(e) => update(i, { subject: e.target.value })}
              placeholder={`Asunto variante ${v.variant}...`}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        );
      })}
      <div className="flex items-center justify-between">
        {variants.length < 4 && (
          <button type="button" onClick={addVariant} className="text-xs text-brand-600 hover:text-brand-700 flex items-center gap-1 font-medium">
            <Plus size={12} /> Agregar variante
          </button>
        )}
        <span className={`text-xs ml-auto font-medium ${Math.abs(totalWeight - 100) > 2 ? "text-red-500" : "text-gray-400"}`}>
          Total: {totalWeight}% {Math.abs(totalWeight - 100) > 2 ? "(debe sumar 100)" : "✓"}
        </span>
      </div>
    </div>
  );
}

export default function NewCampaignPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    name: "",
    subject: "",
    preview_text: "",
    segment_id: 0,
    exclude_segment_ids: [] as number[],
    template_id: 0,
    scheduled_at: "",
  });

  const [abEnabled, setAbEnabled] = useState(false);
  const [variants, setVariants] = useState<VariantState[]>([
    { variant: "A", subject: "", templateId: "", weight: 50 },
    { variant: "B", subject: "", templateId: "", weight: 50 },
  ]);

  const { data: segments = [] } = useQuery<Segment[]>({
    queryKey: ["segments"],
    queryFn: () => segmentsApi.list().then((r) => r.data),
  });

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: () => {
      const base = {
        name: form.name,
        segment_id: form.segment_id,
        exclude_segment_ids: form.exclude_segment_ids.length ? form.exclude_segment_ids : undefined,
        scheduled_at: form.scheduled_at ? new Date(form.scheduled_at).toISOString() : undefined,
        status: form.scheduled_at ? "scheduled" : "draft",
      };

      if (abEnabled) {
        const builtVariants: CampaignVariant[] = variants.map((v) => ({
          variant: v.variant,
          subject: v.subject,
          template_id: Number(v.templateId),
          weight: v.weight,
        }));
        return campaignsApi.create({
          ...base,
          subject: variants[0].subject,
          template_id: Number(variants[0].templateId),
          variants: builtVariants,
        });
      }

      return campaignsApi.create({
        ...base,
        subject: form.subject,
        preview_text: form.preview_text || undefined,
        template_id: form.template_id,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      router.push("/campaigns");
    },
  });

  const selectedSeg = segments.find((s) => s.id === form.segment_id);
  const excludedSegs = segments.filter((s) => form.exclude_segment_ids.includes(s.id));

  function toggleExclude(id: number) {
    setForm((f) => ({
      ...f,
      exclude_segment_ids: f.exclude_segment_ids.includes(id)
        ? f.exclude_segment_ids.filter((x) => x !== id)
        : [...f.exclude_segment_ids, id],
    }));
  }

  function canNext() {
    if (step === 0) {
      if (!form.name) return false;
      if (abEnabled) return variants.every((v) => v.templateId && v.subject) && Math.abs(variants.reduce((s, v) => s + v.weight, 0) - 100) <= 2;
      return !!(form.subject && form.template_id);
    }
    if (step === 1) return form.segment_id > 0;
    return true;
  }

  function toggleAb() {
    if (!abEnabled) {
      setVariants([
        { variant: "A", subject: form.subject, templateId: form.template_id || "", weight: 50 },
        { variant: "B", subject: "",           templateId: form.template_id || "", weight: 50 },
      ]);
    }
    setAbEnabled((v) => !v);
  }

  return (
    <div className="p-8 max-w-3xl">
      <Link href="/campaigns" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6">
        <ArrowLeft size={15} /> Volver
      </Link>

      <h1 className="text-2xl font-bold text-gray-900 mb-6">Nueva campaña</h1>

      {/* Stepper */}
      <div className="flex items-center gap-0 mb-8">
        {STEPS.map((label, i) => (
          <div key={i} className="flex items-center">
            <div className={`flex items-center gap-2 text-sm font-medium ${i === step ? "text-brand-600" : i < step ? "text-green-600" : "text-gray-400"}`}>
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${i === step ? "bg-brand-600 text-white" : i < step ? "bg-green-500 text-white" : "bg-gray-200 text-gray-500"}`}>
                {i < step ? <Check size={12} /> : i + 1}
              </div>
              {label}
            </div>
            {i < STEPS.length - 1 && <div className="w-8 h-px bg-gray-200 mx-3" />}
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        {/* ── Step 0: Información ─────────────────────────────────────── */}
        {step === 0 && (
          <div className="space-y-4">
            <h2 className="font-semibold text-gray-900 mb-4">Información de la campaña</h2>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nombre interno *</label>
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Ej: Newsletter julio 2025"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>

            {/* A/B toggle */}
            <div className="flex items-center justify-between py-2 border-y border-gray-100">
              <div className="flex items-center gap-2">
                <FlaskConical size={14} className={abEnabled ? "text-purple-600" : "text-gray-400"} />
                <span className="text-sm font-medium text-gray-700">Test A/B</span>
                {abEnabled && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">activo</span>
                )}
              </div>
              <button
                type="button"
                onClick={toggleAb}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none ${abEnabled ? "bg-purple-600" : "bg-gray-200"}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${abEnabled ? "translate-x-4" : "translate-x-0"}`} />
              </button>
            </div>

            {abEnabled ? (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1.5">
                  <FlaskConical size={13} className="text-purple-500" /> Variantes A/B
                </label>
                <VariantEditor variants={variants} templates={templates} onChange={setVariants} />
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Asunto del email *</label>
                  <input value={form.subject} onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
                    placeholder="Ej: ¡Nuevas fechas disponibles, {{nombre}}!"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                  <p className="text-xs text-gray-400 mt-1">Puedes usar {"{{nombre}}"} para personalizar</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Preview text</label>
                  <input value={form.preview_text} onChange={(e) => setForm((f) => ({ ...f, preview_text: e.target.value }))}
                    placeholder="Texto de vista previa en el cliente de correo"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Plantilla de email *</label>
                  <select value={form.template_id} onChange={(e) => setForm((f) => ({ ...f, template_id: Number(e.target.value) }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
                    <option value={0}>Seleccionar plantilla...</option>
                    {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                </div>
              </>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center gap-1.5">
                <Calendar size={13} /> Programar envío — hora de Chile (tu zona horaria local)
              </label>
              <input
                type="datetime-local"
                value={form.scheduled_at}
                onChange={(e) => setForm((f) => ({ ...f, scheduled_at: e.target.value }))}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <p className="text-xs text-gray-400 mt-1">Si lo dejas vacío se crea como borrador y puedes enviarla manualmente.</p>
            </div>
          </div>
        )}

        {/* ── Step 1: Segmento ────────────────────────────────────────── */}
        {step === 1 && (
          <div className="space-y-6">
            <div>
              <h2 className="font-semibold text-gray-900 mb-1">Enviar a</h2>
              <p className="text-xs text-gray-400 mb-3">Selecciona el segmento que recibirá esta campaña</p>
              {segments.length === 0 ? (
                <p className="text-gray-500 text-sm">No hay segmentos. <Link href="/segments/new" className="text-brand-600 underline">Crear uno</Link></p>
              ) : (
                <div className="space-y-2">
                  {segments.map((s) => (
                    <button key={s.id} type="button"
                      onClick={() => setForm((f) => ({ ...f, segment_id: s.id, exclude_segment_ids: f.exclude_segment_ids.filter((x) => x !== s.id) }))}
                      className={`w-full flex items-center justify-between px-4 py-3 border rounded-xl text-left transition-colors ${form.segment_id === s.id ? "border-brand-500 bg-brand-50" : "border-gray-200 hover:border-gray-300"}`}
                    >
                      <div>
                        <p className="font-medium text-gray-900">{s.name}</p>
                        {s.description && <p className="text-xs text-gray-400">{s.description}</p>}
                      </div>
                      <span className="text-sm font-semibold text-gray-600">{s.contact_count?.toLocaleString()} contactos</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="border-t border-gray-100 pt-5">
              <h3 className="font-semibold text-gray-900 mb-1">Excluir segmentos</h3>
              <p className="text-xs text-gray-400 mb-3">Opcional — los contactos de estos segmentos no recibirán la campaña</p>
              <div className="space-y-2">
                {segments.filter((s) => s.id !== form.segment_id).map((s) => {
                  const checked = form.exclude_segment_ids.includes(s.id);
                  return (
                    <button key={s.id} type="button" onClick={() => toggleExclude(s.id)}
                      className={`w-full flex items-center gap-3 px-4 py-3 border rounded-xl text-left transition-colors ${checked ? "border-red-300 bg-red-50" : "border-gray-200 hover:border-gray-300"}`}
                    >
                      <div className={`w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 ${checked ? "border-red-400 bg-red-400" : "border-gray-300"}`}>
                        {checked && <X size={10} className="text-white" strokeWidth={3} />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 text-sm">{s.name}</p>
                        {s.description && <p className="text-xs text-gray-400 truncate">{s.description}</p>}
                      </div>
                      <span className="text-sm font-semibold text-gray-500 shrink-0">{s.contact_count?.toLocaleString()}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ── Step 2: Revisar ─────────────────────────────────────────── */}
        {step === 2 && (
          <div className="space-y-4">
            <h2 className="font-semibold text-gray-900 mb-4">Revisar y crear</h2>

            {abEnabled ? (
              <>
                {[
                  { label: "Nombre", value: form.name },
                  { label: "Enviar a", value: selectedSeg ? `${selectedSeg.name} (${selectedSeg.contact_count?.toLocaleString()} contactos)` : "—" },
                  { label: "Tipo", value: "Test A/B" },
                  { label: "Programada para", value: form.scheduled_at ? new Date(form.scheduled_at).toLocaleString("es-CL") : "Borrador (envío manual)" },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between py-2 border-b border-gray-100 text-sm">
                    <span className="text-gray-500">{label}</span>
                    <span className="font-medium text-gray-900">{value}</span>
                  </div>
                ))}
                <div className="py-2 border-b border-gray-100 text-sm">
                  <p className="text-gray-500 mb-2">Variantes</p>
                  <div className="space-y-1.5">
                    {variants.map((v, i) => {
                      const col = VARIANT_COLORS[i % VARIANT_COLORS.length];
                      const tpl = templates.find((t) => t.id === Number(v.templateId));
                      return (
                        <div key={v.variant} className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${col.border} ${col.bg.replace("100", "50")}`}>
                          <span className={`text-xs font-bold px-1.5 py-0.5 rounded-full ${col.bg} ${col.text}`}>{v.variant}</span>
                          <span className="text-xs text-gray-600 flex-1 truncate">"{v.subject}"</span>
                          <span className="text-xs text-gray-400">{tpl?.name ?? "—"}</span>
                          <span className={`text-xs font-medium ${col.text}`}>{v.weight}%</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : (
              [
                { label: "Nombre", value: form.name },
                { label: "Asunto", value: form.subject },
                { label: "Enviar a", value: selectedSeg ? `${selectedSeg.name} (${selectedSeg.contact_count?.toLocaleString()} contactos)` : "—" },
                { label: "Plantilla", value: templates.find((t) => t.id === form.template_id)?.name ?? "—" },
                { label: "Programada para", value: form.scheduled_at ? new Date(form.scheduled_at).toLocaleString("es-CL") : "Borrador (envío manual)" },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between py-2 border-b border-gray-100 text-sm">
                  <span className="text-gray-500">{label}</span>
                  <span className="font-medium text-gray-900">{value}</span>
                </div>
              ))
            )}

            {excludedSegs.length > 0 && (
              <div className="py-2 border-b border-gray-100 text-sm">
                <div className="flex justify-between mb-2"><span className="text-gray-500">Excluir</span></div>
                <div className="flex flex-wrap gap-1.5 justify-end">
                  {excludedSegs.map((s) => (
                    <span key={s.id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-50 text-red-600 border border-red-200 rounded-full text-xs font-medium">
                      <X size={10} /> {s.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <p className="text-xs text-gray-400 mt-4">La campaña se creará como borrador. Podrás enviarla desde la lista de campañas.</p>
          </div>
        )}
      </div>

      {mutation.isError && (
        <p className="text-red-600 text-sm mt-3">Error al crear la campaña. Intenta de nuevo.</p>
      )}

      <div className="flex justify-between mt-6">
        <button type="button" onClick={() => setStep((s) => s - 1)} disabled={step === 0}
          className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-30 transition-colors">
          <ArrowLeft size={14} /> Anterior
        </button>
        {step < STEPS.length - 1 ? (
          <button type="button" onClick={() => setStep((s) => s + 1)} disabled={!canNext()}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors">
            Siguiente <ArrowRight size={14} />
          </button>
        ) : (
          <button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending || !canNext()}
            className="flex items-center gap-2 px-5 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors">
            <Check size={14} /> {mutation.isPending ? "Creando..." : "Crear campaña"}
          </button>
        )}
      </div>
    </div>
  );
}
