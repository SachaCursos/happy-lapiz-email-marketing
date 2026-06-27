"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  Plus, ChevronUp, ChevronDown, FlaskConical, Pencil, Trash2,
  Pause, Play, RefreshCw, Mail, MousePointerClick,
} from "lucide-react";
import { evergreenApi } from "@/lib/api";
import { EvergreenCampaign, EvergreenStats } from "@/lib/types";

function StatsMini({ id }: { id: number }) {
  const { data } = useQuery<EvergreenStats>({
    queryKey: ["evergreen-stats", id],
    queryFn: () => evergreenApi.stats(id).then((r) => r.data),
  });
  if (!data || data.sent === 0) {
    return <span className="text-xs text-gray-400">Sin envíos aún</span>;
  }
  return (
    <span className="text-xs text-gray-500">
      {data.sent} envíos · {data.open_rate}% apertura · {data.click_rate}% clics
    </span>
  );
}

export default function EvergreenPage() {
  const qc = useQueryClient();
  const [testingId, setTestingId] = useState<number | null>(null);

  const { data: items = [], isLoading } = useQuery<EvergreenCampaign[]>({
    queryKey: ["evergreen"],
    queryFn: () => evergreenApi.list().then((r) => r.data),
  });

  const reorderMutation = useMutation({
    mutationFn: (ordered_ids: number[]) => evergreenApi.reorder(ordered_ids),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["evergreen"] }),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      evergreenApi.update(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["evergreen"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => evergreenApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["evergreen"] }),
  });

  const runNowMutation = useMutation({
    mutationFn: () => evergreenApi.runNow(),
  });

  function move(idx: number, dir: -1 | 1) {
    const next = [...items];
    const j = idx + dir;
    if (j < 0 || j >= next.length) return;
    [next[idx], next[j]] = [next[j], next[idx]];
    reorderMutation.mutate(next.map((x) => x.id));
  }

  async function sendTest(id: number) {
    setTestingId(id);
    try {
      await evergreenApi.sendTest(id);
      alert("Email de prueba enviado");
    } catch {
      alert("Error al enviar prueba");
    } finally {
      setTestingId(null);
    }
  }

  return (
    <div className="p-6 md:p-8 max-w-5xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Campañas evergreen</h1>
          <p className="text-sm text-gray-500 mt-1 max-w-2xl">
            Contenido atemporal que se envía automáticamente cuando un contacto lleva{" "}
            <strong>15 días</strong> sin recibir campañas ni automatizaciones, abrió al menos
            uno de sus últimos 5 correos, y aún no recibió esta pieza.
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => runNowMutation.mutate()}
            disabled={runNowMutation.isPending}
            className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw size={14} className={runNowMutation.isPending ? "animate-spin" : ""} />
            Ejecutar ahora
          </button>
          <Link
            href="/evergreen/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
          >
            <Plus size={16} /> Nueva evergreen
          </Link>
        </div>
      </div>

      {runNowMutation.isSuccess && (
        <div className="mb-4 px-4 py-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
          Job ejecutado: {(runNowMutation.data?.data?.entry?.sent ?? 0)} inicios +{" "}
          {(runNowMutation.data?.data?.followups?.sent ?? 0)} seguimientos enviados.
        </div>
      )}

      <div className="bg-teal-50 border border-teal-200 rounded-xl px-4 py-3 text-sm text-teal-800 mb-6">
        <strong>Orden de prioridad:</strong> arriba = se intenta enviar primero. Solo se envía{" "}
        <strong>una</strong> evergreen por contacto por ejecución.
      </div>

      {isLoading ? (
        <div className="text-gray-400 text-sm">Cargando…</div>
      ) : items.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-xl p-10 text-center">
          <Mail className="mx-auto text-gray-300 mb-3" size={32} />
          <p className="text-gray-600 font-medium">Aún no hay campañas evergreen</p>
          <p className="text-sm text-gray-400 mt-1">
            Crea contenido de valor reutilizable, como &quot;5 chistes para tus peques&quot;.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((eg, idx) => (
            <div
              key={eg.id}
              className={`bg-white border rounded-xl p-4 flex gap-3 items-start ${
                eg.status === "paused" ? "border-gray-200 opacity-75" : "border-gray-200"
              }`}
            >
              <div className="flex flex-col gap-0.5 pt-1">
                <button
                  type="button"
                  onClick={() => move(idx, -1)}
                  disabled={idx === 0 || reorderMutation.isPending}
                  className="p-1 rounded hover:bg-gray-100 text-gray-400 disabled:opacity-30"
                  aria-label="Subir"
                >
                  <ChevronUp size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => move(idx, 1)}
                  disabled={idx === items.length - 1 || reorderMutation.isPending}
                  className="p-1 rounded hover:bg-gray-100 text-gray-400 disabled:opacity-30"
                  aria-label="Bajar"
                >
                  <ChevronDown size={16} />
                </button>
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-mono text-gray-400">#{idx + 1}</span>
                  <h2 className="font-semibold text-gray-900 truncate">{eg.name}</h2>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      eg.status === "active"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {eg.status === "active" ? "Activa" : "Pausada"}
                  </span>
                </div>
                <p className="text-sm text-gray-500 truncate mt-0.5">{eg.subject}</p>
                <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-500">
                  <span>{eg.min_days_inactive} días inactivo</span>
                  <span>Abrió 1+ de últimos {eg.require_open_in_last_n}</span>
                  {eg.segment_id ? (
                    <span>Segmento #{eg.segment_id}</span>
                  ) : (
                    <span>Todos los suscritos</span>
                  )}
                  {eg.allow_resend ? (
                    <span>
                      Reenvío cada {eg.resend_after_days ?? "∞"} días
                    </span>
                  ) : (
                    <span>Una sola vez</span>
                  )}
                  {(eg.steps?.length ?? 1) > 1 && (
                    <span>{eg.steps!.length} correos en secuencia</span>
                  )}
                </div>
                <div className="mt-2">
                  <StatsMini id={eg.id} />
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() =>
                    toggleMutation.mutate({
                      id: eg.id,
                      status: eg.status === "active" ? "paused" : "active",
                    })
                  }
                  className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
                  title={eg.status === "active" ? "Pausar" : "Activar"}
                >
                  {eg.status === "active" ? <Pause size={16} /> : <Play size={16} />}
                </button>
                <button
                  onClick={() => sendTest(eg.id)}
                  disabled={testingId === eg.id}
                  className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
                  title="Enviar prueba"
                >
                  <FlaskConical size={16} />
                </button>
                <Link
                  href={`/evergreen/${eg.id}`}
                  className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
                  title="Editar"
                >
                  <Pencil size={16} />
                </Link>
                <button
                  onClick={() => {
                    if (confirm(`¿Eliminar "${eg.name}"?`)) deleteMutation.mutate(eg.id);
                  }}
                  className="p-2 rounded-lg hover:bg-red-50 text-red-500"
                  title="Eliminar"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-8 grid sm:grid-cols-3 gap-4 text-sm">
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <Mail size={18} className="text-brand-600 mb-2" />
          <p className="font-medium text-gray-900">Inactividad</p>
          <p className="text-gray-500 text-xs mt-1">
            Cuenta campañas + automatizaciones + otras evergreens enviadas.
          </p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <MousePointerClick size={18} className="text-brand-600 mb-2" />
          <p className="font-medium text-gray-900">Engagement</p>
          <p className="text-gray-500 text-xs mt-1">
            Excluye contactos que no abrieron ninguno de sus últimos 5 correos.
          </p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <RefreshCw size={18} className="text-brand-600 mb-2" />
          <p className="font-medium text-gray-900">Automático</p>
          <p className="text-gray-500 text-xs mt-1">
            El job corre diariamente junto con automatizaciones y campañas programadas.
          </p>
        </div>
      </div>
    </div>
  );
}
