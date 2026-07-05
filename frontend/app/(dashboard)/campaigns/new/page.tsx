"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { campaignsApi, segmentsApi, templatesApi } from "@/lib/api";
import { Segment, Template } from "@/lib/types";
import { ArrowLeft, ArrowRight, Check, Calendar, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CampaignAudienceSummary } from "@/components/CampaignAudienceSummary";

const STEPS = ["Información", "Segmento", "Plantilla", "Revisar"];

export default function NewCampaignPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    name: "",
    subject: "",
    preview_text: "",
    segment_ids: [] as number[],
    exclude_segment_ids: [] as number[],
    template_id: 0,
    scheduled_at: "",
  });

  const { data: segments = [] } = useQuery<Segment[]>({
    queryKey: ["segments"],
    queryFn: () => segmentsApi.list().then((r) => r.data),
  });

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
  });

  const mutation = useMutation({
    mutationFn: () => campaignsApi.create({
      ...form,
      segment_ids: form.segment_ids,
      segment_id: form.segment_ids[0] ?? undefined,
      exclude_segment_ids: form.exclude_segment_ids.length ? form.exclude_segment_ids : undefined,
      scheduled_at: form.scheduled_at ? new Date(form.scheduled_at).toISOString() : undefined,
      status: form.scheduled_at ? "scheduled" : "draft",
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      router.push("/campaigns");
    },
  });

  const selectedSegs = segments.filter((s) => form.segment_ids.includes(s.id));
  const selectedTpl = templates.find((t) => t.id === form.template_id);
  const excludedSegs = segments.filter((s) => form.exclude_segment_ids.includes(s.id));

  function toggleInclude(id: number) {
    setForm((f) => ({
      ...f,
      segment_ids: f.segment_ids.includes(id)
        ? f.segment_ids.filter((x) => x !== id)
        : [...f.segment_ids, id],
      exclude_segment_ids: f.exclude_segment_ids.filter((x) => x !== id),
    }));
  }

  function toggleExclude(id: number) {
    setForm((f) => ({
      ...f,
      exclude_segment_ids: f.exclude_segment_ids.includes(id)
        ? f.exclude_segment_ids.filter((x) => x !== id)
        : [...f.exclude_segment_ids, id],
    }));
  }

  function canNext() {
    if (step === 0) return form.name && form.subject;
    if (step === 1) return form.segment_ids.length > 0;
    if (step === 2) return form.template_id > 0;
    return true;
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
        {step === 0 && (
          <div className="space-y-4">
            <h2 className="font-semibold text-gray-900 mb-4">Información de la campaña</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nombre interno *</label>
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Ej: Newsletter mayo 2025" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Asunto del email *</label>
              <input value={form.subject} onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))} placeholder="Ej: ¡Nuevas fechas disponibles, {{nombre}}!" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              <p className="text-xs text-gray-400 mt-1">Puedes usar {"{{nombre}}"} para personalizar</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Preview text</label>
              <input value={form.preview_text} onChange={(e) => setForm((f) => ({ ...f, preview_text: e.target.value }))} placeholder="Texto de vista previa en el cliente de correo" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center gap-1.5"><Calendar size={13} /> Programar envío — hora de Chile (tu zona horaria local)</label>
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

        {step === 1 && (
          <div className="space-y-6">
            {/* Incluir */}
            <div>
              <h2 className="font-semibold text-gray-900 mb-1">Enviar a</h2>
              <p className="text-xs text-gray-400 mb-3">Selecciona uno o más segmentos. Los contactos duplicados entre segmentos solo recibirán el correo una vez.</p>
              {segments.length === 0 ? (
                <p className="text-gray-500 text-sm">No hay segmentos. <Link href="/segments/new" className="text-brand-600 underline">Crear uno</Link></p>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {segments.map((s) => {
                    const checked = form.segment_ids.includes(s.id);
                    return (
                      <button
                        key={s.id}
                        type="button"
                        onClick={() => toggleInclude(s.id)}
                        className={`w-full flex items-center gap-3 px-4 py-3 border rounded-xl text-left transition-colors ${checked ? "border-brand-500 bg-brand-50" : "border-gray-200 hover:border-gray-300"}`}
                      >
                        <div className={`w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 ${checked ? "border-brand-500 bg-brand-500" : "border-gray-300"}`}>
                          {checked && <Check size={10} className="text-white" strokeWidth={3} />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-900 text-sm">{s.name}</p>
                          {s.description && <p className="text-xs text-gray-400 truncate">{s.description}</p>}
                        </div>
                        <span className="text-sm font-semibold text-gray-600 shrink-0">{s.contact_count?.toLocaleString()} contactos</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Excluir */}
            <div className="border-t border-gray-100 pt-5">
              <h3 className="font-semibold text-gray-900 mb-1">Excluir segmentos</h3>
              <p className="text-xs text-gray-400 mb-3">Opcional — los contactos de estos segmentos no recibirán la campaña</p>
              <div className="space-y-2">
                {segments
                  .filter((s) => !form.segment_ids.includes(s.id))
                  .map((s) => {
                    const checked = form.exclude_segment_ids.includes(s.id);
                    return (
                      <button
                        key={s.id}
                        type="button"
                        onClick={() => toggleExclude(s.id)}
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

            <CampaignAudienceSummary
              segmentIds={form.segment_ids}
              excludeSegmentIds={form.exclude_segment_ids}
            />
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 className="font-semibold text-gray-900 mb-4">Seleccionar plantilla</h2>
            {templates.length === 0 ? (
              <p className="text-gray-500 text-sm">No hay plantillas. <Link href="/templates/new" className="text-brand-600 underline">Crear una</Link></p>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                {templates.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, template_id: t.id }))}
                    className={`border rounded-xl p-4 text-left transition-colors ${form.template_id === t.id ? "border-brand-500 bg-brand-50" : "border-gray-200 hover:border-gray-300"}`}
                  >
                    <p className="font-medium text-gray-900">{t.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5 truncate">{t.subject_default}</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <h2 className="font-semibold text-gray-900 mb-4">Revisar y crear</h2>

            <CampaignAudienceSummary
              segmentIds={form.segment_ids}
              excludeSegmentIds={form.exclude_segment_ids}
            />

            {[
              { label: "Nombre", value: form.name },
              { label: "Asunto", value: form.subject },
              { label: "Plantilla", value: selectedTpl?.name ?? "—" },
              { label: "Programada para", value: form.scheduled_at ? new Date(form.scheduled_at).toLocaleString("es-CL") : "Borrador (envío manual)" },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between py-2 border-b border-gray-100 text-sm">
                <span className="text-gray-500">{label}</span>
                <span className="font-medium text-gray-900">{value}</span>
              </div>
            ))}

            <div className="py-2 border-b border-gray-100 text-sm">
              <div className="flex justify-between mb-2">
                <span className="text-gray-500">Enviar a</span>
              </div>
              <div className="flex flex-wrap gap-1.5 justify-end">
                {selectedSegs.map((s) => (
                  <span key={s.id} className="inline-flex items-center gap-1 px-2 py-0.5 bg-brand-50 text-brand-700 border border-brand-200 rounded-full text-xs font-medium">
                    {s.name}
                  </span>
                ))}
              </div>
            </div>

            {excludedSegs.length > 0 && (
              <div className="py-2 border-b border-gray-100 text-sm">
                <div className="flex justify-between mb-2">
                  <span className="text-gray-500">Excluir</span>
                </div>
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
        <button
          type="button"
          onClick={() => setStep((s) => s - 1)}
          disabled={step === 0}
          className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-30 transition-colors"
        >
          <ArrowLeft size={14} /> Anterior
        </button>
        {step < 3 ? (
          <button
            type="button"
            onClick={() => setStep((s) => s + 1)}
            disabled={!canNext()}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
          >
            Siguiente <ArrowRight size={14} />
          </button>
        ) : (
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="flex items-center gap-2 px-5 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
          >
            <Check size={14} /> {mutation.isPending ? "Creando..." : "Crear campaña"}
          </button>
        )}
      </div>
    </div>
  );
}
