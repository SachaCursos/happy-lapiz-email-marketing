"use client";

import { useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { campaignsApi, contactsApi, segmentsApi, templatesApi } from "@/lib/api";
import { Campaign, CampaignStats, CampaignConversions, CampaignVariantStat, Segment, Template } from "@/lib/types";
import { ArrowLeft, TrendingUp, Mail, MousePointer, AlertTriangle, Send, Users, Trash2, Pencil, Save, X, Calendar, UserMinus, BarChart2, ShoppingCart, FlaskConical, Trophy } from "lucide-react";
import Link from "next/link";
import { formatDateTime, statusColor, statusLabel } from "@/lib/utils";

// Convert a UTC datetime string from the backend (may lack Z) to a local
// time string suitable for a datetime-local input.
function utcToLocalInput(utcStr: string): string {
  const s = utcStr.endsWith("Z") ? utcStr : utcStr + "Z";
  const d = new Date(s);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

interface CampaignSendRow {
  contact_id: number;
  name: string;
  email: string;
  opted_in: boolean | null;
  status: string;
  variant_sent: string | null;
  sent_at: string | null;
  delivered_at: string | null;
  opened_at: string | null;
  clicked_at: string | null;
  bounced_at: string | null;
}

const VARIANT_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  A: { bg: "bg-purple-100", text: "text-purple-700", border: "border-purple-300" },
  B: { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-300" },
  C: { bg: "bg-teal-100",   text: "text-teal-700",   border: "border-teal-300" },
  D: { bg: "bg-pink-100",   text: "text-pink-700",   border: "border-pink-300" },
};

function VariantResultCard({ v, isWinner }: { v: CampaignVariantStat; isWinner: boolean }) {
  const col = VARIANT_COLORS[v.variant] ?? { bg: "bg-gray-100", text: "text-gray-700", border: "border-gray-300" };
  return (
    <div className={`flex-1 rounded-lg border p-3 space-y-1.5 ${isWinner ? "border-amber-300 bg-amber-50" : `${col.border} bg-white`}`}>
      <div className="flex items-center gap-2">
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${isWinner ? "bg-amber-200 text-amber-800" : `${col.bg} ${col.text}`}`}>
          Variante {v.variant}
        </span>
        {isWinner && (
          <span className="flex items-center gap-1 text-xs font-semibold text-amber-700">
            <Trophy size={11} /> Ganador
          </span>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-sm font-bold text-gray-900">{v.sent.toLocaleString("es-CL")}</p>
          <p className="text-xs text-gray-400">enviados</p>
        </div>
        <div>
          <p className={`text-sm font-bold ${isWinner ? "text-amber-700" : "text-gray-900"}`}>{v.open_rate}%</p>
          <p className="text-xs text-gray-400">abiertos</p>
        </div>
        <div>
          <p className="text-sm font-bold text-gray-900">{v.click_rate}%</p>
          <p className="text-xs text-gray-400">clics</p>
        </div>
      </div>
    </div>
  );
}

function Tick({ date, label }: { date: string | null; label: string }) {
  if (!date) return <span title={`Sin ${label}`} className="text-gray-200">—</span>;
  return (
    <span title={`${label}: ${formatDateTime(date)}`} className="text-green-500 font-semibold">✓</span>
  );
}

function isBounced(s: CampaignSendRow) {
  return s.status === "bounced" || s.bounced_at != null;
}

function isFailed(s: CampaignSendRow) {
  return s.status === "failed";
}

interface SendProgress {
  total_in_segment: number;
  already_sent: number;
}

function StatBar({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-semibold text-gray-900">{value.toLocaleString()} <span className="text-gray-400 font-normal">({pct.toFixed(1)}%)</span></span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function CampaignDetailPage({ params }: { params: { id: string } }) {
  const id = parseInt(params.id);
  const queryClient = useQueryClient();
  const [limit, setLimit] = useState(20);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());
  const [activeTab, setActiveTab] = useState<"overview" | "analytics" | "recipients">("overview");
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<{
    name: string; subject: string; preview_text: string;
    segment_id: number; template_id: number; scheduled_at: string;
  } | null>(null);
  type SortCol = "name" | "sent_at" | "delivered_at" | "opened_at" | "clicked_at" | "bounced_at" | "opted_in";
  const [sortCol, setSortCol] = useState<SortCol>("sent_at");
  const [sortAsc, setSortAsc] = useState(false);

  function toggleSort(col: SortCol) {
    if (sortCol === col) setSortAsc((v) => !v);
    else { setSortCol(col); setSortAsc(false); }
  }

  const { data: segments = [] } = useQuery<Segment[]>({
    queryKey: ["segments"],
    queryFn: () => segmentsApi.list().then((r) => r.data),
    enabled: editing,
  });

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
    enabled: editing,
  });

  const updateMutation = useMutation({
    mutationFn: (data: Parameters<typeof campaignsApi.update>[1]) => campaignsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      setEditing(false);
      setEditForm(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (contactId: number) => contactsApi.delete(contactId),
    onSuccess: (_, contactId) => {
      setDeletingIds((prev) => { const s = new Set(prev); s.delete(contactId); return s; });
      queryClient.invalidateQueries({ queryKey: ["campaign-sends", id] });
      queryClient.invalidateQueries({ queryKey: ["campaign-stats", id] });
    },
  });

  async function deleteContact(contactId: number) {
    setDeletingIds((prev) => new Set(prev).add(contactId));
    deleteMutation.mutate(contactId);
  }

  async function deleteAllBounced() {
    const bounced = sends.filter(isBounced);
    if (!confirm(`¿Eliminar ${bounced.length} contactos rebotados de la base de datos?`)) return;
    for (const s of bounced) await contactsApi.delete(s.contact_id);
    queryClient.invalidateQueries({ queryKey: ["campaign-sends", id] });
    queryClient.invalidateQueries({ queryKey: ["campaign-stats", id] });
  }

  const { data: campaign } = useQuery<Campaign>({
    queryKey: ["campaign", id],
    queryFn: () => campaignsApi.get(id).then((r) => r.data),
  });

  const { data: sends = [] } = useQuery<CampaignSendRow[]>({
    queryKey: ["campaign-sends", id],
    queryFn: () => campaignsApi.sends(id).then((r) => r.data),
    staleTime: 30_000,
  });

  const { data: stats } = useQuery<CampaignStats>({
    queryKey: ["campaign-stats", id],
    queryFn: () => campaignsApi.stats(id).then((r) => r.data),
    enabled: sends.length > 0 || campaign?.status === "sent" || campaign?.status === "sending",
  });

  const { data: conversions } = useQuery<CampaignConversions>({
    queryKey: ["campaign-conversions", id],
    queryFn: () => campaignsApi.conversions(id, 90).then((r) => r.data),
    enabled: campaign?.status === "sent",
    staleTime: 15 * 60_000,
  });

  const failedCount = sends.filter(isFailed).length;

  const { data: progress } = useQuery<SendProgress>({
    queryKey: ["campaign-progress", id],
    queryFn: () => campaignsApi.sendProgress(id).then((r) => r.data),
    enabled: campaign?.status === "draft" || failedCount > 0,
    refetchInterval: campaign?.status === "sending" ? 3000 : false,
  });

  async function handleSend(sendAll: boolean) {
    setSendError("");
    setSending(true);
    try {
      await campaignsApi.send(id, sendAll ? undefined : limit);
      await queryClient.invalidateQueries({ queryKey: ["campaign", id] });
      await queryClient.invalidateQueries({ queryKey: ["campaign-progress", id] });
      await queryClient.invalidateQueries({ queryKey: ["campaign-stats", id] });
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Error al enviar";
      setSendError(msg);
    } finally {
      setSending(false);
    }
  }

  if (!campaign) return <div className="p-8 text-gray-400 text-sm">Cargando...</div>;

  const sortedSends = [...sends].sort((a, b) => {
    if (sortCol === "name") {
      const cmp = a.name.localeCompare(b.name, "es");
      return sortAsc ? cmp : -cmp;
    }
    const val = (s: CampaignSendRow) =>
      sortCol === "bounced_at" ? (isBounced(s) ? 1 : 0) :
      sortCol === "opted_in"   ? (s.opted_in === false ? 1 : 0) :
      (s[sortCol] ? 1 : 0);
    return sortAsc ? val(a) - val(b) : val(b) - val(a);
  });

  const remaining = progress ? progress.total_in_segment - progress.already_sent : 0;
  const safeLimit = Math.min(limit, remaining);
  const progressPct = progress && progress.total_in_segment > 0
    ? (progress.already_sent / progress.total_in_segment) * 100
    : 0;

  return (
    <div className="p-8 max-w-4xl">
      <Link href="/campaigns" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6">
        <ArrowLeft size={15} /> Volver a campañas
      </Link>

      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{campaign.name}</h1>
          <p className="text-gray-500 text-sm mt-1">{campaign.subject}</p>
        </div>
        <div className="flex items-center gap-2">
          {campaign.status !== "sent" && campaign.status !== "sending" && (
            <button
              onClick={() => {
                setEditing((v) => !v);
                if (!editing) setEditForm({
                  name: campaign.name,
                  subject: campaign.subject,
                  preview_text: campaign.preview_text ?? "",
                  segment_id: campaign.segment_id,
                  template_id: campaign.template_id,
                  scheduled_at: campaign.scheduled_at
                    ? utcToLocalInput(campaign.scheduled_at)
                    : "",
                });
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-200 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-50 transition-colors"
            >
              {editing ? <X size={13} /> : <Pencil size={13} />}
              {editing ? "Cancelar" : "Editar"}
            </button>
          )}
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColor(campaign.status)}`}>
            {statusLabel(campaign.status)}
          </span>
        </div>
      </div>

      {/* ── Tabs ─────────────────────────────────────────────────────────── */}
      <div className="flex border-b border-gray-200 mb-6 gap-0">
        {[
          { key: "overview", label: "Resumen", icon: Mail },
          { key: "analytics", label: "Análisis", icon: BarChart2 },
          { key: "recipients", label: "Destinatarios", icon: Users },
        ].map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setActiveTab(key as typeof activeTab)}
            className={`flex items-center gap-1.5 px-5 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              activeTab === key ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>

      {/* ── Analytics tab ────────────────────────────────────────────────── */}
      {activeTab === "analytics" && (
        <div className="space-y-5">
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Enviados", value: stats?.total?.toLocaleString("es-CL") ?? "—", icon: Send, color: "text-gray-900" },
              { label: "Open rate", value: stats ? `${stats.open_rate.toFixed(1)}%` : "—", icon: Mail, color: "text-brand-600" },
              { label: "Click rate", value: stats ? `${stats.click_rate.toFixed(2)}%` : "—", icon: MousePointer, color: "text-indigo-600" },
              { label: "Bounce rate", value: stats ? `${stats.bounce_rate.toFixed(2)}%` : "—", icon: AlertTriangle, color: "text-red-500" },
            ].map(({ label, value, icon: Icon, color }) => (
              <div key={label} className="bg-white border border-gray-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-1"><Icon size={13} className="text-gray-400" /><p className="text-xs text-gray-500">{label}</p></div>
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Placed Order */}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <ShoppingCart size={16} className="text-green-600" />
              <p className="font-semibold text-gray-800">Placed Order (90 días)</p>
            </div>
            {conversions ? (
              <div className="grid grid-cols-3 gap-6">
                <div>
                  <p className="text-3xl font-bold text-green-600">${Math.round(conversions.revenue).toLocaleString("es-CL")}</p>
                  <p className="text-xs text-gray-400 mt-1">Revenue atribuido</p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-gray-900">{conversions.bookings}</p>
                  <p className="text-xs text-gray-400 mt-1">Pedidos generados</p>
                </div>
                <div>
                  <p className="text-3xl font-bold text-gray-900">{conversions.converted_contacts}</p>
                  <p className="text-xs text-gray-400 mt-1">Contactos convertidos</p>
                </div>
              </div>
            ) : (
              <p className="text-gray-400 text-sm">
                {campaign.status === "sent" ? "Calculando conversiones..." : "Disponible después del envío"}
              </p>
            )}
          </div>

          {/* A/B breakdown */}
          {stats && stats.variants.length >= 2 && (() => {
            const winner = stats.variants.reduce((best, v) => v.open_rate > best.open_rate ? v : best).variant;
            return (
              <div className="bg-white border border-gray-200 rounded-xl p-5">
                <p className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
                  <FlaskConical size={15} className="text-purple-500" /> Resultados A/B
                </p>
                <div className="flex gap-3">
                  {stats.variants.map((v) => (
                    <VariantResultCard key={v.variant} v={v} isWinner={v.variant === winner} />
                  ))}
                </div>
              </div>
            );
          })()}

          {/* Funnel */}
          {stats && (
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <p className="font-semibold text-gray-800 mb-4">Embudo de conversión</p>
              <div className="space-y-3">
                {[
                  { label: "Entregados", value: stats.delivered, color: "bg-gray-400" },
                  { label: "Abiertos", value: stats.opened, color: "bg-brand-500" },
                  { label: "Clics", value: stats.clicked, color: "bg-indigo-500" },
                  { label: "Pedidos", value: conversions?.bookings ?? 0, color: "bg-green-500" },
                ].map(({ label, value, color }) => (
                  <div key={label}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-600">{label}</span>
                      <span className="font-semibold">{value.toLocaleString("es-CL")}
                        <span className="text-gray-400 font-normal text-xs ml-1">
                          ({stats.total > 0 ? ((value / stats.total) * 100).toFixed(1) : "0"}%)
                        </span>
                      </span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full">
                      <div className={`h-full ${color} rounded-full`} style={{ width: `${stats.total > 0 ? (value / stats.total) * 100 : 0}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Edit panel ──────────────────────────────────────────────────── */}
      {editing && editForm && (
        <div className="bg-white border border-brand-200 rounded-xl p-6 mb-6 space-y-4">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2"><Pencil size={14} /> Editar campaña</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Nombre interno</label>
              <input value={editForm.name} onChange={(e) => setEditForm((f) => f && ({ ...f, name: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Asunto del email</label>
              <input value={editForm.subject} onChange={(e) => setEditForm((f) => f && ({ ...f, subject: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Preview text</label>
            <input value={editForm.preview_text} onChange={(e) => setEditForm((f) => f && ({ ...f, preview_text: e.target.value }))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Segmento</label>
              <select value={editForm.segment_id} onChange={(e) => setEditForm((f) => f && ({ ...f, segment_id: Number(e.target.value) }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
                <option value={0}>— Seleccionar —</option>
                {segments.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.contact_count?.toLocaleString()} contactos)</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Plantilla</label>
              <select value={editForm.template_id} onChange={(e) => setEditForm((f) => f && ({ ...f, template_id: Number(e.target.value) }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
                <option value={0}>— Seleccionar —</option>
                {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1 flex items-center gap-1.5"><Calendar size={12} /> Programar envío — hora de Chile (tu zona horaria local)</label>
            <div className="flex gap-3 items-center">
              <input
                type="datetime-local"
                value={editForm.scheduled_at}
                onChange={(e) => setEditForm((f) => f && ({ ...f, scheduled_at: e.target.value }))}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              {editForm.scheduled_at && (
                <button onClick={() => setEditForm((f) => f && ({ ...f, scheduled_at: "" }))}
                  className="text-xs text-gray-400 hover:text-red-500 underline">
                  Quitar programación
                </button>
              )}
            </div>
            <p className="text-xs text-gray-400 mt-1">Si lo dejas vacío la campaña queda en borrador. Si pones una fecha, se enviará automáticamente.</p>
          </div>

          {updateMutation.isError && (
            <p className="text-sm text-red-600">Error al guardar. Intenta de nuevo.</p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              onClick={() => {
                if (!editForm) return;
                updateMutation.mutate({
                  name: editForm.name,
                  subject: editForm.subject,
                  preview_text: editForm.preview_text || undefined,
                  segment_id: editForm.segment_id || undefined,
                  template_id: editForm.template_id || undefined,
                  scheduled_at: editForm.scheduled_at ? new Date(editForm.scheduled_at).toISOString() : null,
                  status: editForm.scheduled_at ? "scheduled" : "draft",
                });
              }}
              disabled={updateMutation.isPending || !editForm.name || !editForm.subject}
              className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
            >
              <Save size={13} /> {updateMutation.isPending ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-6">
        {[
          { label: "Fecha de envío", value: formatDateTime(campaign.sent_at) },
          { label: "Programada para", value: formatDateTime(campaign.scheduled_at) },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white border border-gray-200 rounded-xl px-5 py-4">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">{label}</p>
            <p className="text-gray-900 font-medium">{value}</p>
          </div>
        ))}
      </div>

      {/* ── Envío por fases / Reintentar errores ───────────────────────── */}
      {(campaign.status === "draft" || failedCount > 0) && progress && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <Users size={16} className="text-gray-400" />
            <h2 className="font-semibold text-gray-900">
              {campaign.status === "draft" ? "Envío por fases" : `Reintentar ${failedCount} envíos con error`}
            </h2>
          </div>

          {/* Progreso del segmento */}
          <div className="mb-5">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-gray-600">Contactos enviados</span>
              <span className="font-semibold text-gray-900">
                {progress.already_sent.toLocaleString()}
                <span className="text-gray-400 font-normal"> / {progress.total_in_segment.toLocaleString()}</span>
              </span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-600 rounded-full transition-all"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            {remaining > 0 && (
              <p className="text-xs text-gray-400 mt-1.5">{remaining.toLocaleString()} contactos pendientes</p>
            )}
          </div>

          {remaining > 0 ? (
            <>
              {/* Input de cantidad */}
              <div className="flex items-center gap-3 mb-4">
                <label className="text-sm text-gray-600 whitespace-nowrap">Enviar a</label>
                <input
                  type="number"
                  min={1}
                  max={remaining}
                  value={limit}
                  onChange={(e) => setLimit(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-24 border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-center font-semibold focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <span className="text-sm text-gray-600">contactos</span>
              </div>

              {sendError && (
                <p className="text-sm text-red-600 mb-3">{sendError}</p>
              )}

              <div className="flex items-center gap-3 flex-wrap">
                <button
                  onClick={() => handleSend(false)}
                  disabled={sending}
                  className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
                >
                  <Send size={14} />
                  {sending ? "Enviando..." : `Enviar a ${safeLimit} contactos`}
                </button>

                <button
                  onClick={() => handleSend(true)}
                  disabled={sending}
                  className="text-sm text-gray-500 hover:text-gray-900 underline underline-offset-2 transition-colors disabled:opacity-50"
                >
                  Enviar a todos los restantes ({remaining.toLocaleString()})
                </button>
              </div>
            </>
          ) : (
            <p className="text-sm text-green-700 font-medium">
              ✓ Todos los contactos del segmento ya recibieron esta campaña.
            </p>
          )}
        </div>
      )}

      {/* ── Overview + Recipients tabs content ──────────────────────────── */}
      {(activeTab === "overview" || activeTab === "recipients") && stats && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
          <h2 className="font-semibold text-gray-900 mb-5">Estadísticas</h2>

          {(() => {
            const unsubCount = sends.filter(s => s.opted_in === false).length;
            return (
              <>
                <div className="grid grid-cols-5 gap-4 mb-6">
                  {[
                    { label: "Enviados",      value: stats.sent,             icon: Mail,         color: "text-blue-600" },
                    { label: "Aperturas",     value: `${stats.open_rate}%`,  icon: TrendingUp,   color: "text-green-600" },
                    { label: "Clics",         value: `${stats.click_rate}%`, icon: MousePointer, color: "text-purple-600" },
                    { label: "Rebotes",       value: `${stats.bounce_rate}%`,icon: AlertTriangle, color: "text-red-600" },
                    { label: "Desuscritos",   value: unsubCount,             icon: UserMinus,    color: "text-orange-500" },
                  ].map(({ label, value, icon: Icon, color }) => (
                    <div key={label} className="text-center">
                      <Icon size={20} className={`mx-auto mb-1 ${color}`} />
                      <p className="text-2xl font-bold text-gray-900">{value}</p>
                      <p className="text-xs text-gray-500">{label}</p>
                    </div>
                  ))}
                </div>

                <div className="space-y-4">
                  <StatBar label="Entregados"    value={stats.delivered} total={stats.sent}                        color="bg-blue-500" />
                  <StatBar label="Abiertos"      value={stats.opened}    total={stats.delivered || stats.sent}     color="bg-green-500" />
                  <StatBar label="Con clics"     value={stats.clicked}   total={stats.delivered || stats.sent}     color="bg-purple-500" />
                  <StatBar label="Rebotados"     value={stats.bounced}   total={stats.sent}                        color="bg-red-400" />
                  <StatBar label="Desuscritos"   value={unsubCount}      total={stats.sent}                        color="bg-orange-400" />
                </div>
              </>
            );
          })()}
        </div>
      )}

      {/* ── Lista de contactos enviados ──────────────────────────────────── */}
      {sends.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-6">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between gap-3 flex-wrap">
            <h2 className="font-semibold text-gray-900">Contactos</h2>
            <div className="flex items-center gap-3">
              {sends.filter(isBounced).length > 0 && (
                <button
                  onClick={deleteAllBounced}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 border border-red-200 text-red-600 rounded-lg text-xs font-medium hover:bg-red-100 transition-colors"
                >
                  <Trash2 size={12} />
                  Eliminar {sends.filter(isBounced).length} rebotados
                </button>
              )}
              <span className="text-xs text-gray-400">{sends.length} enviados</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  {([
                    { col: "name",         label: "Contacto",    align: "left"   },
                    { col: "sent_at",      label: "Enviado",     align: "center" },
                    { col: "delivered_at", label: "Entregado",   align: "center" },
                    { col: "opened_at",    label: "Abrió",       align: "center" },
                    { col: "clicked_at",   label: "Clic",        align: "center" },
                    { col: "bounced_at",   label: "Rebote",      align: "center" },
                    { col: "opted_in",     label: "Desuscripto", align: "center" },
                  ] as { col: SortCol; label: string; align: string }[]).map(({ col, label, align }) => (
                    <th
                      key={col}
                      onClick={() => toggleSort(col)}
                      className={`px-4 py-3 text-${align} cursor-pointer select-none hover:text-gray-800 transition-colors`}
                    >
                      {label}
                      {sortCol === col ? (sortAsc ? " ↑" : " ↓") : ""}
                    </th>
                  ))}
                  {sends.some((s) => s.variant_sent) && (
                    <th className="px-4 py-3 text-center">Variante</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {sortedSends.map((s) => (
                  <tr key={s.contact_id} className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${isBounced(s) ? "bg-red-50/40" : isFailed(s) ? "bg-orange-50/40" : ""}`}>
                    <td className="px-5 py-3">
                      <Link href={`/contacts/${s.contact_id}`} className="hover:text-brand-600 transition-colors">
                        <p className="font-medium text-gray-900">{s.name}</p>
                        <p className="text-xs text-gray-400">{s.email}</p>
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-center"><Tick date={s.sent_at} label="enviado" /></td>
                    <td className="px-4 py-3 text-center"><Tick date={s.delivered_at} label="entregado" /></td>
                    <td className="px-4 py-3 text-center"><Tick date={s.opened_at} label="abierto" /></td>
                    <td className="px-4 py-3 text-center"><Tick date={s.clicked_at} label="clic" /></td>
                    <td className="px-4 py-3 text-center">
                      {isBounced(s) ? (
                        <div className="flex items-center justify-center gap-2">
                          <span title={`Rebotó: ${formatDateTime(s.bounced_at)}`} className="text-red-400 font-semibold">✕</span>
                          <button
                            onClick={() => deleteContact(s.contact_id)}
                            disabled={deletingIds.has(s.contact_id)}
                            title="Eliminar contacto"
                            className="text-red-300 hover:text-red-600 transition-colors disabled:opacity-40"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      ) : isFailed(s) ? (
                        <span title="Error técnico — no se envió" className="text-orange-400 font-semibold text-xs">Error</span>
                      ) : <span className="text-gray-200">—</span>}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {s.opted_in === false
                        ? <span title="Se desuscribió" className="text-orange-500 font-semibold">✕</span>
                        : <span className="text-gray-200">—</span>}
                    </td>
                    {sends.some((r) => r.variant_sent) && (
                      <td className="px-4 py-3 text-center">
                        {s.variant_sent ? (
                          <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                            VARIANT_COLORS[s.variant_sent]
                              ? `${VARIANT_COLORS[s.variant_sent].bg} ${VARIANT_COLORS[s.variant_sent].text}`
                              : "bg-gray-100 text-gray-600"
                          }`}>
                            {s.variant_sent}
                          </span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
