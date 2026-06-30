"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery, useQueries, useMutation, useQueryClient } from "@tanstack/react-query";
import { campaignsApi, segmentsApi, api } from "@/lib/api";
import { Campaign, CampaignConversions, CampaignStats, Segment } from "@/lib/types";
import {
  Plus, Send, Trash2, FlaskConical, MoreHorizontal, Mail,
  Search, CheckCircle, Pencil, ChevronDown, Eye, ShoppingCart,
  TrendingUp, Users,
} from "lucide-react";
import Link from "next/link";
import { formatDateTime, statusColor, statusLabel } from "@/lib/utils";

// ─── Helpers ─────────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium ${statusColor(status)}`}>
      {statusLabel(status)}
    </span>
  );
}

function StatCell({ pct, sub, highlight = false }: { pct: string; sub: string; highlight?: boolean }) {
  return (
    <div>
      <p className={`font-semibold text-sm ${highlight ? "text-brand-600" : "text-gray-900"}`}>{pct}</p>
      <p className="text-gray-400 text-xs mt-0.5">{sub}</p>
    </div>
  );
}

function RevenueCell({ value, orders }: { value: number; orders: number }) {
  return (
    <div>
      <p className="font-semibold text-sm text-green-600">
        ${Math.round(value).toLocaleString("es-CL")}
      </p>
      <p className="text-gray-400 text-xs mt-0.5">
        {orders} pedido{orders !== 1 ? "s" : ""}
      </p>
    </div>
  );
}

function ActionsMenu({ campaign, onTest, onSend, onDelete }: {
  campaign: Campaign; onTest: () => void; onSend: () => void; onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function h(e: MouseEvent) { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); }
    if (open) document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);
  const canSend = campaign.status === "draft" || campaign.status === "scheduled";
  const canDelete = campaign.status === "draft";
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} className="p-1.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors">
        <MoreHorizontal size={16} />
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-20 bg-white border border-gray-200 rounded-lg shadow-lg w-44 py-1 text-sm">
          <Link href={`/campaigns/${campaign.id}`} className="flex items-center gap-2.5 px-3.5 py-2 hover:bg-gray-50 text-gray-700" onClick={() => setOpen(false)}>
            <Pencil size={13} className="text-gray-400" /> Ver / editar
          </Link>
          {canSend && (
            <>
              <button onClick={() => { setOpen(false); onTest(); }} className="w-full flex items-center gap-2.5 px-3.5 py-2 hover:bg-gray-50 text-gray-700">
                <FlaskConical size={13} className="text-gray-400" /> Enviar prueba
              </button>
              <button onClick={() => { setOpen(false); onSend(); }} className="w-full flex items-center gap-2.5 px-3.5 py-2 hover:bg-gray-50 text-gray-700">
                <Send size={13} className="text-gray-400" /> Enviar ahora
              </button>
            </>
          )}
          {canDelete && (
            <>
              <div className="border-t border-gray-100 my-1" />
              <button onClick={() => { setOpen(false); onDelete(); }} className="w-full flex items-center gap-2.5 px-3.5 py-2 hover:bg-red-50 text-red-600">
                <Trash2 size={13} /> Eliminar
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function SkeletonRow() {
  return (
    <tr className="border-b border-gray-100">
      {[48, 4, 16, 28, 16, 16, 20, 4].map((w, i) => (
        <td key={i} className="px-5 py-3.5">
          <div className={`h-4 bg-gray-100 rounded animate-pulse w-${w}`} />
        </td>
      ))}
    </tr>
  );
}

const STATUS_OPTS = [
  { value: "", label: "Todos" }, { value: "sent", label: "Enviadas" },
  { value: "draft", label: "Borradores" }, { value: "scheduled", label: "Programadas" },
  { value: "sending", label: "Enviando" }, { value: "paused", label: "Pausadas" }, { value: "cancelled", label: "Canceladas" },
];

// ─── Klaviyo history table ────────────────────────────────────────────────────
interface KlaviyoCampaign {
  id: string; name: string; status: string; send_time: string | null;
  subject: string | null; recipients: number | null; open_rate: number | null;
  opens_unique: number | null; click_rate: number | null; clicks_unique: number | null;
  conversion_value: number | null; conversions: number | null;
  average_order_value: number | null; audience: string | null;
}

const KLAVIYO_PAGE_SIZE = 20;

function KlaviyoTable({ search }: { search: string }) {
  const [page, setPage] = useState(0);

  const { data: campaigns = [], isLoading } = useQuery<KlaviyoCampaign[]>({
    queryKey: ["klaviyo-campaigns"],
    queryFn: () => api.get("/analytics/klaviyo-campaigns").then((r) => r.data),
    staleTime: 10 * 60_000,
  });

  const filtered = (search
    ? campaigns.filter((c) => c.name.toLowerCase().includes(search.toLowerCase()) || (c.subject ?? "").toLowerCase().includes(search.toLowerCase()))
    : campaigns);

  const totalPages = Math.ceil(filtered.length / KLAVIYO_PAGE_SIZE);
  const paginated = filtered.slice(page * KLAVIYO_PAGE_SIZE, (page + 1) * KLAVIYO_PAGE_SIZE);

  const totRevenue = campaigns.reduce((s, c) => s + (c.conversion_value ?? 0), 0);
  const totOrders  = campaigns.reduce((s, c) => s + (c.conversions ?? 0), 0);
  const avgOpen    = campaigns.filter((c) => c.open_rate).reduce((s, c, _, a) => s + (c.open_rate ?? 0) / a.length, 0);

  function rateColor(r: number | null) {
    if (!r) return "text-gray-400";
    if (r >= 0.40) return "text-green-600 font-semibold";
    if (r >= 0.25) return "text-yellow-600";
    return "text-red-500";
  }

  return (
    <div>
      {/* Summary cards */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-gray-500">{filtered.length} campañas · mostrando {page * KLAVIYO_PAGE_SIZE + 1}–{Math.min((page + 1) * KLAVIYO_PAGE_SIZE, filtered.length)}</p>
        <div className="flex items-center gap-2">
          <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}
            className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-40">← Anterior</button>
          <span className="text-xs text-gray-500">{page + 1} / {totalPages}</span>
          <button onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
            className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-40">Siguiente →</button>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-4 mb-5">
        {[
          { label: "Campañas enviadas", value: campaigns.length, icon: Mail },
          { label: "Revenue total (Klaviyo)", value: `$${Math.round(totRevenue).toLocaleString("es-CL")}`, icon: TrendingUp },
          { label: "Open rate promedio", value: `${(avgOpen * 100).toFixed(1)}%`, icon: Users },
        ].map(({ label, value, icon: Icon }) => (
          <div key={label} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-1">
              <Icon size={14} className="text-gray-400" />
              <p className="text-xs text-gray-500">{label}</p>
            </div>
            <p className="text-xl font-bold text-gray-900">{value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white border border-gray-200 rounded-xl overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Campaña</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Audiencia</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Enviados</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Open %</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Click %</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Placed Order</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Fecha</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? [...Array(5)].map((_, i) => <SkeletonRow key={i} />) :
              paginated.map((c) => (
                <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-5 py-3.5 max-w-xs">
                    <p className="font-medium text-gray-900 truncate">{c.name}</p>
                    {c.subject && <p className="text-gray-400 text-xs mt-0.5 truncate">{c.subject}</p>}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="text-xs text-gray-500">{c.audience ?? "—"}</span>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-gray-700">
                    {c.recipients?.toLocaleString("es-CL") ?? "—"}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`text-sm ${rateColor(c.open_rate)}`}>
                      {c.open_rate != null ? `${(c.open_rate * 100).toFixed(1)}%` : "—"}
                    </span>
                    {c.opens_unique != null && (
                      <p className="text-xs text-gray-400">{c.opens_unique.toLocaleString()} únicos</p>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="text-sm text-gray-700">
                      {c.click_rate != null ? `${(c.click_rate * 100).toFixed(2)}%` : "—"}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    {c.conversion_value != null && c.conversion_value > 0 ? (
                      <div>
                        <p className="font-semibold text-sm text-green-600">
                          ${Math.round(c.conversion_value).toLocaleString("es-CL")}
                        </p>
                        <p className="text-gray-400 text-xs">{c.conversions ?? 0} pedido{(c.conversions ?? 0) !== 1 ? "s" : ""}</p>
                      </div>
                    ) : <span className="text-gray-300 text-xs">—</span>}
                  </td>
                  <td className="px-5 py-3.5 text-xs text-gray-400 whitespace-nowrap">
                    {c.send_time ? new Date(c.send_time).toLocaleDateString("es-CL", { day: "numeric", month: "short", year: "2-digit" }) : "—"}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function CampaignsPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"own" | "klaviyo">("own");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [statusOpen, setStatusOpen] = useState(false);
  const statusRef = useRef<HTMLDivElement>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    function h(e: MouseEvent) { if (statusRef.current && !statusRef.current.contains(e.target as Node)) setStatusOpen(false); }
    if (statusOpen) document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [statusOpen]);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 6000); };

  const { data: campaigns = [], isLoading, isError } = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn: () => campaignsApi.list().then((r) => r.data),
    staleTime: 2 * 60_000,
    refetchInterval: (q) => (q.state.data as Campaign[] | undefined)?.some((c) => c.status === "sending") ? 3000 : false,
  });

  const { data: segments = [] } = useQuery<Segment[]>({
    queryKey: ["segments"],
    queryFn: () => segmentsApi.list().then((r) => r.data),
    staleTime: 5 * 60_000,
  });
  const segMap = Object.fromEntries(segments.map((s) => [s.id, s]));

  const sentCampaigns = campaigns.filter((c) => c.status === "sent" || c.status === "draft");
  const statsQueries = useQueries({
    queries: sentCampaigns.map((c) => ({
      queryKey: ["campaign-stats", c.id],
      queryFn: () => campaignsApi.stats(c.id).then((r) => r.data as CampaignStats),
      staleTime: 10 * 60_000,
    })),
  });
  const statsMap: Record<number, CampaignStats> = {};
  statsQueries.forEach((q) => { if (q.data) statsMap[q.data.campaign_id] = q.data; });

  const convQueries = useQueries({
    queries: sentCampaigns.map((c) => ({
      queryKey: ["campaign-conversions", c.id],
      queryFn: () => campaignsApi.conversions(c.id).then((r) => r.data as CampaignConversions),
      staleTime: 15 * 60_000,
    })),
  });
  const convMap: Record<number, CampaignConversions> = {};
  convQueries.forEach((q) => { if (q.data) convMap[q.data.campaign_id] = q.data; });

  const sendMutation = useMutation({
    mutationFn: (id: number) => campaignsApi.send(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["campaigns"] }); setTimeout(() => qc.invalidateQueries({ queryKey: ["campaigns"] }), 5000); },
  });
  const testMutation = useMutation({
    mutationFn: (id: number) => campaignsApi.sendTest(id),
    onSuccess: (res) => showToast(`Prueba enviada a ${res.data?.sent_to ?? "tu correo"}`),
  });
  const delMutation = useMutation({
    mutationFn: (id: number) => campaignsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });

  const filtered = campaigns.filter((c) => {
    const matchSearch = !search || c.name.toLowerCase().includes(search.toLowerCase()) || c.subject.toLowerCase().includes(search.toLowerCase());
    const matchStatus = !statusFilter || c.status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Campañas</h1>
        </div>
        <Link href="/campaigns/new" className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors">
          <Plus size={15} /> Crear campaña
        </Link>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6 gap-0">
        {[
          { key: "own", label: "Mis campañas" },
          { key: "klaviyo", label: `Historial Klaviyo` },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key as "own" | "klaviyo")}
            className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === key ? "border-brand-600 text-brand-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Toast */}
      {toast && (
        <div className="mb-4 bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-4 py-3 flex items-center gap-2">
          <CheckCircle size={15} /> {toast}
        </div>
      )}
      {isError && tab === "own" && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">Error al cargar campañas.</div>
      )}

      {/* Filter bar (only own tab) */}
      {tab === "own" && (
        <div className="flex items-center gap-2.5 mb-5 flex-wrap">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input type="text" placeholder="Buscar campañas" value={search} onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-500 w-52" />
          </div>
          <div className="relative" ref={statusRef}>
            <button onClick={() => setStatusOpen(!statusOpen)}
              className={`flex items-center gap-1.5 px-3 py-2 border rounded-lg text-sm font-medium transition-colors ${statusFilter ? "border-brand-500 text-brand-700 bg-brand-50" : "border-gray-300 text-gray-600 bg-white hover:bg-gray-50"}`}>
              {STATUS_OPTS.find((o) => o.value === statusFilter)?.label ?? "Estado"}
              {statusFilter ? <span onClick={(e) => { e.stopPropagation(); setStatusFilter(""); }} className="ml-1 text-brand-500 font-bold text-xs">×</span>
                : <ChevronDown size={13} />}
            </button>
            {statusOpen && (
              <div className="absolute left-0 top-10 z-20 bg-white border border-gray-200 rounded-lg shadow-lg w-44 py-1 text-sm">
                {STATUS_OPTS.map((o) => (
                  <button key={o.value} onClick={() => { setStatusFilter(o.value); setStatusOpen(false); }}
                    className={`w-full text-left px-3.5 py-2 hover:bg-gray-50 ${statusFilter === o.value ? "text-brand-600 font-medium" : "text-gray-700"}`}>
                    {o.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <span className="text-xs text-gray-400 ml-auto">{filtered.length} campaña{filtered.length !== 1 ? "s" : ""}</span>
        </div>
      )}

      {/* Klaviyo tab */}
      {tab === "klaviyo" && (
        <KlaviyoTable search={search} />
      )}

      {/* Own campaigns table */}
      {tab === "own" && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Campaña</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tipo</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Estado</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Fecha envío</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tasa apertura</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tasa clics</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-1">
                  <ShoppingCart size={12} /> Placed Order
                </th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody>
              {isLoading ? [...Array(5)].map((_, i) => <SkeletonRow key={i} />) :
                filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-5 py-16 text-center">
                      <Send size={36} className="mx-auto text-gray-300 mb-3" />
                      <p className="text-gray-500 font-medium">{search || statusFilter ? "Sin resultados" : "No hay campañas"}</p>
                      <p className="text-gray-400 text-xs mt-1">{search || statusFilter ? "Prueba con otros filtros" : "Crea tu primera campaña"}</p>
                      {!search && !statusFilter && (
                        <Link href="/campaigns/new" className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800">
                          <Plus size={14} /> Crear campaña
                        </Link>
                      )}
                    </td>
                  </tr>
                ) : filtered.map((c) => {
                  const seg = segMap[c.segment_id];
                  const stats = statsMap[c.id];
                  const conv = convMap[c.id];
                  const hasSent = c.status === "sent" || (stats != null && stats.sent > 0);
                  return (
                    <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                      <td className="px-5 py-3.5 max-w-xs">
                        <Link href={`/campaigns/${c.id}`} className="group">
                          <p className="font-medium text-brand-600 group-hover:underline truncate">{c.name}</p>
                          <p className="text-gray-400 text-xs mt-0.5 truncate">{seg?.name ?? `Segmento #${c.segment_id}`}</p>
                        </Link>
                      </td>
                      <td className="px-5 py-3.5"><Mail size={16} className="text-gray-400" /></td>
                      <td className="px-5 py-3.5"><StatusBadge status={c.status} /></td>
                      <td className="px-5 py-3.5 text-xs text-gray-500 whitespace-nowrap">
                        {formatDateTime(c.sent_at) || formatDateTime(c.scheduled_at) || "—"}
                      </td>
                      <td className="px-5 py-3.5">
                        {hasSent && stats ? <StatCell pct={`${stats.open_rate.toFixed(2)}%`} sub={`${stats.opened.toLocaleString()} dest.`} />
                          : <span className="text-gray-300 text-sm">—</span>}
                      </td>
                      <td className="px-5 py-3.5">
                        {hasSent && stats ? <StatCell pct={`${stats.click_rate.toFixed(2)}%`} sub={`${stats.clicked.toLocaleString()} dest.`} highlight />
                          : <span className="text-gray-300 text-sm">—</span>}
                      </td>
                      <td className="px-5 py-3.5">
                        {hasSent && conv ? (
                          conv.revenue > 0
                            ? <RevenueCell value={conv.revenue} orders={conv.bookings} />
                            : <span className="text-gray-300 text-xs">—</span>
                        ) : hasSent ? <span className="text-gray-200 text-xs animate-pulse">···</span>
                          : <span className="text-gray-300 text-sm">—</span>}
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-1.5">
                          {(c.status === "draft" || c.status === "scheduled" || c.status === "sending" || c.status === "paused") && (
                            <>
                              <button onClick={() => testMutation.mutate(c.id)} disabled={testMutation.isPending} title="Enviar prueba"
                                className="flex items-center gap-1 px-2.5 py-1.5 border border-gray-300 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-50 disabled:opacity-50">
                                <FlaskConical size={11} /> Prueba
                              </button>
                              <button onClick={() => { if (confirm(`¿Enviar "${c.name}" ahora?`)) sendMutation.mutate(c.id); }}
                                disabled={sendMutation.isPending}
                                className="flex items-center gap-1 px-2.5 py-1.5 bg-gray-900 text-white rounded-lg text-xs font-medium hover:bg-gray-800 disabled:opacity-60">
                                <Send size={11} /> {c.status === "paused" ? "Reanudar" : c.status === "sending" ? "Reintentar" : "Enviar"}
                              </button>
                            </>
                          )}
                          {c.status === "sent" && (
                            <Link href={`/campaigns/${c.id}`}
                              className="flex items-center gap-1 px-2.5 py-1.5 border border-gray-300 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-50">
                              <Eye size={11} /> Stats
                            </Link>
                          )}
                          <ActionsMenu campaign={c}
                            onTest={() => testMutation.mutate(c.id)}
                            onSend={() => { if (confirm(`¿Enviar "${c.name}" ahora?`)) sendMutation.mutate(c.id); }}
                            onDelete={() => { if (confirm("¿Eliminar esta campaña?")) delMutation.mutate(c.id); }} />
                        </div>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
