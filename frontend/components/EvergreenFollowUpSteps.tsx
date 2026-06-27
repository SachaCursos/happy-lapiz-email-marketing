"use client";

import { Plus, Trash2 } from "lucide-react";
import { Template } from "@/lib/types";

export interface EvergreenStepForm {
  step: number;
  delay_hours: number;
  subject: string;
  template_id: number;
  preview_text: string;
}

export function defaultFollowUpStep(step: number): EvergreenStepForm {
  return {
    step,
    delay_hours: step === 2 ? 48 : 66,
    subject: "",
    template_id: 0,
    preview_text: "",
  };
}

export function buildStepsPayload(
  subject: string,
  template_id: number,
  preview_text: string,
  followUps: EvergreenStepForm[],
): EvergreenStepForm[] {
  const steps: EvergreenStepForm[] = [
    {
      step: 1,
      delay_hours: 0,
      subject,
      template_id,
      preview_text,
    },
  ];
  followUps.forEach((fu, i) => {
    if (fu.subject && fu.template_id > 0) {
      steps.push({
        ...fu,
        step: i + 2,
        preview_text: fu.preview_text || undefined,
      });
    }
  });
  return steps;
}

export function followUpsFromSteps(
  steps: { step: number; delay_hours?: number; subject: string; template_id: number; preview_text?: string }[] | null | undefined,
): EvergreenStepForm[] {
  if (!steps?.length) return [];
  return steps
    .filter((s) => s.step > 1)
    .map((s) => ({
      step: s.step,
      delay_hours: s.delay_hours ?? 48,
      subject: s.subject,
      template_id: s.template_id,
      preview_text: s.preview_text ?? "",
    }));
}

interface Props {
  followUps: EvergreenStepForm[];
  onChange: (followUps: EvergreenStepForm[]) => void;
  templates: Template[];
}

export function EvergreenFollowUpSteps({ followUps, onChange, templates }: Props) {
  function update(idx: number, patch: Partial<EvergreenStepForm>) {
    onChange(followUps.map((f, i) => (i === idx ? { ...f, ...patch } : f)));
  }

  function addStep() {
    if (followUps.length >= 2) return;
    onChange([...followUps, defaultFollowUpStep(followUps.length + 2)]);
  }

  function removeStep(idx: number) {
    onChange(followUps.filter((_, i) => i !== idx));
  }

  return (
    <div className="border-t border-gray-100 pt-5 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Correos de seguimiento</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Opcional. Ej: oferta 72h → recordatorio a las 48h (&quot;quedan 24 horas&quot;).
          </p>
        </div>
        {followUps.length < 2 && (
          <button
            type="button"
            onClick={addStep}
            className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700"
          >
            <Plus size={14} /> Agregar seguimiento
          </button>
        )}
      </div>

      {followUps.length === 0 && (
        <p className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-2">
          Sin seguimientos: solo se envía el correo principal.
        </p>
      )}

      {followUps.map((fu, idx) => (
        <div
          key={idx}
          className="border border-teal-200 bg-teal-50/40 rounded-xl p-4 space-y-3"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-teal-800 uppercase tracking-wide">
              Correo {idx + 2}
            </span>
            <button
              type="button"
              onClick={() => removeStep(idx)}
              className="p-1 text-red-500 hover:bg-red-50 rounded"
              aria-label="Eliminar seguimiento"
            >
              <Trash2 size={14} />
            </button>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Horas después del primer correo
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                max={720}
                value={fu.delay_hours}
                onChange={(e) =>
                  update(idx, { delay_hours: Math.max(1, Number(e.target.value)) })
                }
                className="w-24 border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
              <span className="text-xs text-gray-500">horas (ej. 48 = quedan 24h en oferta de 72h)</span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Asunto</label>
            <input
              value={fu.subject}
              onChange={(e) => update(idx, { subject: e.target.value })}
              placeholder="Ej: ⏰ Solo quedan 24 horas para tu 20% OFF"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Preview text</label>
            <input
              value={fu.preview_text}
              onChange={(e) => update(idx, { preview_text: e.target.value })}
              placeholder="Ej: Tu cupón vence mañana — no te lo pierdas"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Plantilla</label>
            <select
              value={fu.template_id}
              onChange={(e) => update(idx, { template_id: Number(e.target.value) })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            >
              <option value={0}>Seleccionar plantilla…</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
        </div>
      ))}
    </div>
  );
}
