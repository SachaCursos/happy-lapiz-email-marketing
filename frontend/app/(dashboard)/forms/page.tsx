"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formsApi } from "@/lib/api";
import { SignupForm } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { Plus, MousePointerClick, ExternalLink, Trash2, ToggleLeft, ToggleRight } from "lucide-react";
import Link from "next/link";

export default function FormsPage() {
  const qc = useQueryClient();
  const { data: forms = [], isLoading } = useQuery<SignupForm[]>({
    queryKey: ["forms"],
    queryFn: () => formsApi.list().then((r) => r.data),
    staleTime: 30_000,
  });

  const toggleMutation = useMutation({
    mutationFn: (f: SignupForm) =>
      formsApi.update(f.id, { status: f.status === "active" ? "paused" : "active" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["forms"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => formsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["forms"] }),
  });

  const TRIGGER_LABEL: Record<string, string> = {
    delay: "Después de X segundos",
    exit_intent: "Al intentar salir",
    scroll: "Al hacer scroll",
  };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Formularios de suscripción</h1>
          <p className="text-gray-500 mt-1 text-sm">
            Pop-ups embebibles en tu sitio web para capturar leads
          </p>
        </div>
        <Link
          href="/forms/new"
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors"
        >
          <Plus size={15} /> Nuevo formulario
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : forms.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
          <div className="w-14 h-14 bg-gray-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <MousePointerClick size={24} className="text-gray-300" />
          </div>
          <p className="text-gray-900 font-semibold">Sin formularios</p>
          <p className="text-gray-400 text-sm mt-1 mb-6">
            Crea un pop-up para capturar suscriptores en happylapiz.cl
          </p>
          <Link
            href="/forms/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors"
          >
            <Plus size={15} /> Crear formulario
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {forms.map((f) => (
            <div
              key={f.id}
              className="bg-white border border-gray-200 rounded-xl p-5 flex items-center gap-5"
            >
              <div className="w-10 h-10 bg-sky-100 rounded-xl flex items-center justify-center shrink-0">
                <MousePointerClick size={18} className="text-sky-600" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Link
                    href={`/forms/${f.id}`}
                    className="font-semibold text-gray-900 hover:text-brand-600 truncate"
                  >
                    {f.name}
                  </Link>
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      f.status === "active"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {f.status === "active" ? "Activo" : "Pausado"}
                  </span>
                </div>
                <p className="text-sm text-gray-500 truncate mt-0.5">
                  {f.title} &mdash; {TRIGGER_LABEL[f.popup_trigger]}
                  {f.popup_trigger === "delay" && ` (${f.popup_delay_seconds}s)`}
                  {f.popup_trigger === "scroll" && ` (${f.popup_scroll_pct}%)`}
                </p>
              </div>

              <p className="text-xs text-gray-400 shrink-0">{formatDate(f.created_at)}</p>

              <div className="flex items-center gap-2 shrink-0">
                <Link
                  href={`/forms/${f.id}`}
                  className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
                  title="Ver embed code"
                >
                  <ExternalLink size={14} />
                </Link>
                <button
                  onClick={() => toggleMutation.mutate(f)}
                  disabled={toggleMutation.isPending}
                  title={f.status === "active" ? "Pausar" : "Activar"}
                  className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  {f.status === "active" ? <ToggleRight size={16} className="text-green-500" /> : <ToggleLeft size={16} />}
                </button>
                <button
                  onClick={() => {
                    if (confirm(`¿Eliminar formulario "${f.name}"?`)) deleteMutation.mutate(f.id);
                  }}
                  disabled={deleteMutation.isPending}
                  className="p-2 rounded-lg border border-red-100 text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
