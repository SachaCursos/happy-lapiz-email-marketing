"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formsApi, api } from "@/lib/api";
import { SignupForm } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { Plus, MousePointerClick, ExternalLink, Trash2, ToggleLeft, ToggleRight, Gift, Copy, Check, Calendar } from "lucide-react";
import Link from "next/link";

// ─── Gift recipients section ──────────────────────────────────────────────────

interface GiftRecipient {
  id: number;
  email: string;
  relacion: string;
  nombre_regalado: string;
  fecha_nacimiento_regalado: string | null;
  contact_id: number | null;
  source_url: string | null;
  created_at: string;
}

function CopySnippet({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);
  const snippet = `<script src="${url}/api/forms/gift/embed.js" defer></script>`;
  function copy() {
    navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <div className="mt-3 bg-gray-900 rounded-xl p-3 flex items-start gap-2">
      <code className="text-green-400 text-xs font-mono flex-1 break-all">{snippet}</code>
      <button onClick={copy} className="shrink-0 text-gray-400 hover:text-white mt-0.5">
        {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
      </button>
    </div>
  );
}

function GiftSection() {
  const [show, setShow] = useState(false);
  const { data: recipients = [], isLoading } = useQuery<GiftRecipient[]>({
    queryKey: ["gift-recipients"],
    queryFn: () => api.get("/forms/gift/recipients").then((r) => r.data),
    enabled: show,
  });

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

  function age(dateStr: string | null) {
    if (!dateStr) return null;
    const bday = new Date(dateStr);
    const now = new Date();
    const thisYear = new Date(now.getFullYear(), bday.getMonth(), bday.getDate());
    const nextBday = thisYear < now
      ? new Date(now.getFullYear() + 1, bday.getMonth(), bday.getDate())
      : thisYear;
    const days = Math.round((nextBday.getTime() - now.getTime()) / 86400000);
    return days;
  }

  return (
    <div className="bg-white border border-purple-100 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between p-5 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center">
            <Gift size={18} className="text-purple-600" />
          </div>
          <div>
            <p className="font-semibold text-gray-900">Popup de regalos</p>
            <p className="text-xs text-gray-500 mt-0.5">
              Captura datos del regalado para recordatorios de cumpleaños
            </p>
          </div>
        </div>
        <button
          onClick={() => setShow((s) => !s)}
          className="text-sm font-medium text-purple-600 hover:text-purple-700"
        >
          {show ? "Ocultar" : "Ver datos →"}
        </button>
      </div>

      <div className="px-5 py-4 bg-purple-50 border-b border-purple-100">
        <p className="text-xs font-semibold text-gray-600 mb-1">Snippet para happylapiz.cl</p>
        <CopySnippet url={backendUrl} />
        <p className="text-xs text-gray-400 mt-2">
          Pégalo en el <code className="bg-white px-1 rounded">{"<head>"}</code> o antes del{" "}
          <code className="bg-white px-1 rounded">{"</body>"}</code> de tu tienda Shopify.
          El popup aparece automáticamente 8 segundos después de cargar la página.
        </p>
      </div>

      {show && (
        <div className="p-5">
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />)}
            </div>
          ) : recipients.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">
              Aún no hay datos capturados. Instala el snippet en tu tienda.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 uppercase tracking-wider border-b border-gray-100">
                    <th className="pb-2 pr-4">Email cliente</th>
                    <th className="pb-2 pr-4">Relación</th>
                    <th className="pb-2 pr-4">Nombre regalado</th>
                    <th className="pb-2 pr-4">Cumpleaños</th>
                    <th className="pb-2">Próximo cumple</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {recipients.map((r) => {
                    const days = age(r.fecha_nacimiento_regalado);
                    return (
                      <tr key={r.id} className="hover:bg-gray-50">
                        <td className="py-2.5 pr-4 text-gray-700">{r.email}</td>
                        <td className="py-2.5 pr-4">
                          <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs capitalize">
                            {r.relacion}
                          </span>
                        </td>
                        <td className="py-2.5 pr-4 font-medium text-gray-900">{r.nombre_regalado}</td>
                        <td className="py-2.5 pr-4 text-gray-500">
                          {r.fecha_nacimiento_regalado
                            ? new Date(r.fecha_nacimiento_regalado + "T12:00:00").toLocaleDateString("es-CL", { day: "numeric", month: "short" })
                            : "—"}
                        </td>
                        <td className="py-2.5">
                          {days !== null ? (
                            <span className={`flex items-center gap-1 text-xs ${days <= 30 ? "text-orange-600 font-semibold" : "text-gray-400"}`}>
                              <Calendar size={11} />
                              {days === 0 ? "¡Hoy!" : `en ${days} días`}
                            </span>
                          ) : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

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
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
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

      {/* Gift popup section */}
      <GiftSection />

      {/* Regular forms */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
          Formularios de suscripción
        </h2>

        {isLoading ? (
          <div className="space-y-3">
            {[...Array(2)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : forms.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
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
              <div key={f.id} className="bg-white border border-gray-200 rounded-xl p-5 flex items-center gap-5">
                <div className="w-10 h-10 bg-sky-100 rounded-xl flex items-center justify-center shrink-0">
                  <MousePointerClick size={18} className="text-sky-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Link href={`/forms/${f.id}`} className="font-semibold text-gray-900 hover:text-brand-600 truncate">
                      {f.name}
                    </Link>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${f.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
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
                  <Link href={`/forms/${f.id}`} className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors" title="Ver embed code">
                    <ExternalLink size={14} />
                  </Link>
                  <button onClick={() => toggleMutation.mutate(f)} disabled={toggleMutation.isPending} title={f.status === "active" ? "Pausar" : "Activar"} className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors disabled:opacity-50">
                    {f.status === "active" ? <ToggleRight size={16} className="text-green-500" /> : <ToggleLeft size={16} />}
                  </button>
                  <button onClick={() => { if (confirm(`¿Eliminar formulario "${f.name}"?`)) deleteMutation.mutate(f.id); }} disabled={deleteMutation.isPending} className="p-2 rounded-lg border border-red-100 text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
