"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { evergreenApi, segmentsApi, templatesApi } from "@/lib/api";
import { EvergreenCampaign, EvergreenStats, Segment, Template } from "@/lib/types";

export default function EvergreenDetailPage({ params }: { params: { id: string } }) {
  const id = parseInt(params.id);
  const router = useRouter();
  const qc = useQueryClient();

  const { data: eg, isLoading } = useQuery<EvergreenCampaign>({
    queryKey: ["evergreen", id],
    queryFn: () => evergreenApi.get(id).then((r) => r.data),
  });

  const { data: stats } = useQuery<EvergreenStats>({
    queryKey: ["evergreen-stats", id],
    queryFn: () => evergreenApi.stats(id).then((r) => r.data),
  });

  const { data: segments = [] } = useQuery<Segment[]>({
    queryKey: ["segments"],
    queryFn: () => segmentsApi.list().then((r) => r.data),
  });

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
  });

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

  useEffect(() => {
    if (eg) {
      setForm({
        name: eg.name,
        subject: eg.subject,
        preview_text: eg.preview_text ?? "",
        template_id: eg.template_id,
        segment_id: eg.segment_id,
        exclude_segment_ids: eg.exclude_segment_ids ?? [],
        allow_resend: eg.allow_resend,
        resend_after_days: eg.resend_after_days ?? "",
        min_days_inactive: eg.min_days_inactive,
        require_open_in_last_n: eg.require_open_in_last_n,
        status: eg.status,
      });
    }
  }, [eg]);

  const mutation = useMutation({
    mutationFn: () =>
      evergreenApi.update(id, {
        name: form.name,
        subject: form.subject,
        preview_text: form.preview_text || undefined,
        template_id: form.template_id,
        segment_id: form.segment_id || null,
        exclude_segment_ids: form.exclude_segment_ids.length
          ? form.exclude_segment_ids
          : [],
        allow_resend: form.allow_resend,
        resend_after_days:
          form.allow_resend && form.resend_after_days
            ? Number(form.resend_after_days)
            : null,
        min_days_inactive: form.min_days_inactive,
        require_open_in_last_n: form.require_open_in_last_n,
        status: form.status,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["evergreen"] });
      qc.invalidateQueries({ queryKey: ["evergreen", id] });
      router.push("/evergreen");
    },
  });

  function toggleExclude(segId: number) {
    setForm((f) => ({
      ...f,
      exclude_segment_ids: f.exclude_segment_ids.includes(segId)
        ? f.exclude_segment_ids.filter((x) => x !== segId)
        : [...f.exclude_segment_ids, segId],
    }));
  }

  if (isLoading || !eg) {
    return <div className="p-8 text-gray-400 text-sm">Cargando…</div>;
  }

  return (
    <div className="p-8 max-w-2xl">
      <Link
        href="/evergreen"
        className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6"
      >
        <ArrowLeft size={15} /> Volver
      </Link>

      <h1 className="text-2xl font-bold text-gray-900 mb-2">Editar evergreen</h1>

      {stats && stats.sent > 0 && (
        <div className="mb-6 grid grid-cols-3 gap-3">
          {[
            { label: "Enviados", value: stats.sent },
            { label: "Apertura", value: `${stats.open_rate}%` },
            { label: "Clics", value: `${stats.click_rate}%` },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white border border-gray-200 rounded-lg px-4 py-3">
              <p className="text-xs text-gray-400">{label}</p>
              <p className="text-lg font-semibold text-gray-900">{value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Nombre interno</label>
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Asunto</label>
          <input
            value={form.subject}
            onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Plantilla</label>
          <select
            value={form.template_id}
            onChange={(e) => setForm((f) => ({ ...f, template_id: Number(e.target.value) }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
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
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
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
              Excluir segmentos
            </label>
            <div className="flex flex-wrap gap-2">
              {segments.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => toggleExclude(s.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border ${
                    form.exclude_segment_ids.includes(s.id)
                      ? "bg-red-50 border-red-300 text-red-700"
                      : "bg-gray-50 border-gray-200 text-gray-600"
                  }`}
                >
                  {s.name}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Días sin email
            </label>
            <input
              type="number"
              min={1}
              value={form.min_days_inactive}
              onChange={(e) =>
                setForm((f) => ({ ...f, min_days_inactive: Number(e.target.value) }))
              }
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Últimos N correos (aperturas)
            </label>
            <input
              type="number"
              min={1}
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

        <div>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={form.allow_resend}
              onChange={(e) => setForm((f) => ({ ...f, allow_resend: e.target.checked }))}
              className="rounded border-gray-300"
            />
            Permitir reenvío
          </label>
          {form.allow_resend && (
            <input
              type="number"
              min={1}
              value={form.resend_after_days}
              onChange={(e) =>
                setForm((f) => ({ ...f, resend_after_days: e.target.value }))
              }
              placeholder="Días entre reenvíos (vacío = siempre elegible)"
              className="mt-2 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Estado</label>
          <select
            value={form.status}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                status: e.target.value as "active" | "paused",
              }))
            }
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="active">Activa</option>
            <option value="paused">Pausada</option>
          </select>
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="px-5 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {mutation.isPending ? "Guardando…" : "Guardar cambios"}
        </button>
      </div>
    </div>
  );
}
