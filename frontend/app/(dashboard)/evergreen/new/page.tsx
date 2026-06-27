"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { evergreenApi, segmentsApi, templatesApi } from "@/lib/api";
import { Segment, Template } from "@/lib/types";

export default function NewEvergreenPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    subject: "",
    preview_text: "",
    template_id: 0,
    segment_id: 0 as number | null,
    exclude_segment_ids: [] as number[],
    allow_resend: false,
    resend_after_days: "" as string | number,
    min_days_inactive: 15,
    require_open_in_last_n: 5,
    status: "active" as "active" | "paused",
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
    mutationFn: () =>
      evergreenApi.create({
        name: form.name,
        subject: form.subject,
        preview_text: form.preview_text || undefined,
        template_id: form.template_id,
        segment_id: form.segment_id || null,
        exclude_segment_ids: form.exclude_segment_ids.length
          ? form.exclude_segment_ids
          : undefined,
        allow_resend: form.allow_resend,
        resend_after_days:
          form.allow_resend && form.resend_after_days
            ? Number(form.resend_after_days)
            : undefined,
        min_days_inactive: form.min_days_inactive,
        require_open_in_last_n: form.require_open_in_last_n,
        status: form.status,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["evergreen"] });
      router.push("/evergreen");
    },
  });

  function toggleExclude(id: number) {
    setForm((f) => ({
      ...f,
      exclude_segment_ids: f.exclude_segment_ids.includes(id)
        ? f.exclude_segment_ids.filter((x) => x !== id)
        : [...f.exclude_segment_ids, id],
    }));
  }

  const canSave = form.name && form.subject && form.template_id > 0;

  return (
    <div className="p-8 max-w-2xl">
      <Link
        href="/evergreen"
        className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6"
      >
        <ArrowLeft size={15} /> Volver
      </Link>

      <h1 className="text-2xl font-bold text-gray-900 mb-2">Nueva campaña evergreen</h1>
      <p className="text-sm text-gray-500 mb-6">
        Contenido atemporal que se envía sola cuando un contacto cumple las reglas de elegibilidad.
      </p>

      <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Nombre interno *</label>
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Ej: 5 chistes para tus peques"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Asunto *</label>
          <input
            value={form.subject}
            onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
            placeholder="Ej: {{ first_name }}, 5 chistes para contarle a {{ nombre_regalado }}"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Plantilla *</label>
          <select
            value={form.template_id}
            onChange={(e) => setForm((f) => ({ ...f, template_id: Number(e.target.value) }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value={0}>Seleccionar plantilla…</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Segmento</label>
          <select
            value={form.segment_id ?? 0}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                segment_id: Number(e.target.value) || null,
              }))
            }
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value={0}>Todos los contactos con opt-in</option>
            {segments.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        {segments.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Excluir segmentos (opcional)
            </label>
            <div className="flex flex-wrap gap-2">
              {segments.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => toggleExclude(s.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                    form.exclude_segment_ids.includes(s.id)
                      ? "bg-red-50 border-red-300 text-red-700"
                      : "bg-gray-50 border-gray-200 text-gray-600 hover:border-gray-300"
                  }`}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="border-t border-gray-100 pt-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Reglas de envío</h3>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Días sin ningún email
              </label>
              <input
                type="number"
                min={1}
                max={365}
                value={form.min_days_inactive}
                onChange={(e) =>
                  setForm((f) => ({ ...f, min_days_inactive: Number(e.target.value) }))
                }
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Revisar aperturas en últimos N correos
              </label>
              <input
                type="number"
                min={1}
                max={20}
                value={form.require_open_in_last_n}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    require_open_in_last_n: Number(e.target.value),
                  }))
                }
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
          </div>
        </div>

        <div className="border-t border-gray-100 pt-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Repetición</h3>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={form.allow_resend}
              onChange={(e) => setForm((f) => ({ ...f, allow_resend: e.target.checked }))}
              className="rounded border-gray-300"
            />
            Permitir reenvío a la misma persona
          </label>
          {form.allow_resend && (
            <div className="mt-3">
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Reenviar después de (días)
              </label>
              <input
                type="number"
                min={1}
                value={form.resend_after_days}
                onChange={(e) =>
                  setForm((f) => ({ ...f, resend_after_days: e.target.value }))
                }
                placeholder="Ej: 90 para ofertas recurrentes"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">
                Déjalo vacío para reenviar cada vez que vuelva a cumplir inactividad.
              </p>
            </div>
          )}
          {!form.allow_resend && (
            <p className="text-xs text-gray-400 mt-2">
              Ideal para chistes o contenido único: cada contacto lo recibe una sola vez.
            </p>
          )}
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={() => mutation.mutate()}
            disabled={!canSave || mutation.isPending}
            className="px-5 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            {mutation.isPending ? "Guardando…" : "Crear evergreen"}
          </button>
          <Link
            href="/evergreen"
            className="px-5 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancelar
          </Link>
        </div>
      </div>
    </div>
  );
}
