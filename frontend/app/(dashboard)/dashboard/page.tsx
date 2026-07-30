"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api";
import { OverviewStats } from "@/lib/types";
import { Users, Send, Filter, TrendingUp, ShoppingCart, Mail, Zap, ArrowUpRight, ArrowDownRight, ChevronDown, DollarSign } from "lucide-react";
import { formatDateTime } from "@/lib/utils";

// ── Helpers ───────────────────────────────────────────────────────────────────
function clp(n: number) {
  return "$ " + Math.round(n).toLocaleString("es-CL");
}

function pctChange(val: number | null | undefined) {
  if (val === null || val === undefined) return null;
  return val;
}

// ── Date presets ──────────────────────────────────────────────────────────────
type Preset = "30d" | "90d" | "365d" | "custom";

const PRESETS: { key: Preset; label: string }[] = [
  { key: "30d", label: "Últimos 30 días" },
  { key: "90d", label: "Últimos 90 días" },
  { key: "365d", label: "Último año" },
  { key: "custom", label: "Personalizado" },
];

function toIso(d: Date) {
  return d.toISOString().split("T")[0];
}

function presetDates(preset: Preset): { from: string; to: string } {
  const now = new Date();
  const to = toIso(now);
  if (preset === "30d") return { from: toIso(new Date(Date.now() - 30 * 86400e3)), to };
  if (preset === "90d") return { from: toIso(new Date(Date.now() - 90 * 86400e3)), to };
  if (preset === "365d") return { from: toIso(new Date(Date.now() - 365 * 86400e3)), to };
  return { from: toIso(new Date(Date.now() - 30 * 86400e3)), to };
}

// ── Small stat card ───────────────────────────────────────────────────────────
function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string | number; sub?: string; icon: React.ElementType; color: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-gray-500">{label}</span>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={16} className="text-white" />
        </div>
      </div>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-sm text-gray-500 mt-1">{sub}</p>}
    </div>
  );
}

// ── Revenue metric box (big) ──────────────────────────────────────────────────
function RevBig({ label, value, sub, badge }: { label: string; value: string; sub?: string; badge?: string }) {
  return (
    <div className="flex-1 min-w-0">
      <p className="text-4xl font-black text-gray-900 leading-none">{value}</p>
      <p className="text-sm text-gray-500 mt-1.5">{label}</p>
      {sub && (
        <div className="flex items-center gap-1 mt-1">
          <ArrowUpRight size={13} className="text-green-500" />
          <span className="text-xs font-semibold text-green-600 bg-green-50 px-1.5 py-0.5 rounded-full">{sub}</span>
          <span className="text-xs text-gray-400">vs. período anterior</span>
        </div>
      )}
      {badge && <div className="mt-1 text-xs text-gray-500">{badge}</div>}
    </div>
  );
}

// ── Attribution breakdown item ────────────────────────────────────────────────
function RevItem({ icon: Icon, label, value, pct, sub }: {
  icon: React.ElementType; label: string; value: string; pct?: string; sub?: string;
}) {
  return (
    <div className="flex-1 min-w-[130px]">
      <div className="flex items-center gap-1.5 text-sm font-semibold text-gray-600 mb-1">
        <Icon size={14} className="text-gray-400" />
        {label}
      </div>
      <p className="text-lg font-bold text-gray-900">{value}</p>
      {pct && <p className="text-sm text-gray-500">{pct}</p>}
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

// ── Revenue table ─────────────────────────────────────────────────────────────
function RevTable({
  title, rows, totalRevenue, type,
}: {
  title: string;
  rows: Array<{ id: number; name: string; revenue: number; recipients?: number; sends?: number; orders: number; rpr?: number; send_time?: string }>;
  totalRevenue: number;
  type: "campaign" | "automation" | "klaviyo";
}) {
  if (rows.length === 0) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nombre</th>
              <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Ventas</th>
              <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">% del total email</th>
              <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                {type === "automation" ? "Envíos" : "Destinatarios"}
              </th>
              <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Por recipient</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const pct = totalRevenue > 0 ? (r.revenue / totalRevenue * 100).toFixed(1) : "0.0";
              const recipients = r.recipients ?? r.sends ?? 0;
              const rpr = r.rpr ?? (recipients > 0 ? r.revenue / recipients : 0);
              return (
                <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3 font-medium text-gray-800">{r.name}</td>
                  <td className="px-5 py-3 text-right font-semibold text-gray-900">{clp(r.revenue)}</td>
                  <td className="px-5 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-20 bg-gray-100 rounded-full h-1.5">
                        <div className="bg-brand-500 h-1.5 rounded-full" style={{ width: `${Math.min(100, parseFloat(pct))}%` }} />
                      </div>
                      <span className="text-gray-600 text-xs w-10 text-right">{pct}%</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-right text-gray-600">{recipients.toLocaleString()}</td>
                  <td className="px-5 py-3 text-right text-gray-600">{rpr > 0 ? clp(rpr) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [preset, setPreset] = useState<Preset>("30d");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [showPresets, setShowPresets] = useState(false);

  const { from, to } = useMemo(() => {
    if (preset === "custom" && customFrom && customTo) return { from: customFrom, to: customTo };
    return presetDates(preset);
  }, [preset, customFrom, customTo]);

  const { data: overview, isLoading: loadingOverview } = useQuery<OverviewStats>({
    queryKey: ["overview"],
    queryFn: () => analyticsApi.overview().then((r) => r.data),
    staleTime: 2 * 60_000,
  });

  const { data: revenue, isLoading: loadingRevenue } = useQuery({
    queryKey: ["revenue", from, to],
    queryFn: () => analyticsApi.revenue(from, to).then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  const { data: recent } = useQuery({
    queryKey: ["recent-campaigns"],
    queryFn: () => analyticsApi.recentCampaigns().then((r) => r.data),
    staleTime: 2 * 60_000,
  });

  const presetLabel = PRESETS.find((p) => p.key === preset)?.label ?? "Período";
  const dateLabel = `${from} — ${to}`;

  const emailTotal = revenue?.email_total ?? 0;

  return (
    <div className="p-8 max-w-7xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1 text-sm">Resumen de ventas y email marketing</p>
        </div>

        {/* Date picker */}
        <div className="relative">
          <button
            onClick={() => setShowPresets((v) => !v)}
            className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors shadow-sm"
          >
            <span>{presetLabel}</span>
            <span className="text-gray-400 text-xs">{dateLabel}</span>
            <ChevronDown size={14} className="text-gray-400" />
          </button>
          {showPresets && (
            <div className="absolute right-0 top-full mt-2 bg-white border border-gray-200 rounded-xl shadow-lg z-30 min-w-[260px] p-2">
              {PRESETS.filter((p) => p.key !== "custom").map((p) => (
                <button
                  key={p.key}
                  onClick={() => { setPreset(p.key); setShowPresets(false); }}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${preset === p.key ? "bg-brand-50 text-brand-700 font-medium" : "text-gray-700 hover:bg-gray-50"}`}
                >
                  {p.label}
                </button>
              ))}
              <div className="border-t border-gray-100 mt-1 pt-2 px-3 space-y-2">
                <p className="text-xs font-medium text-gray-500">Personalizado</p>
                <div className="flex gap-2 items-center">
                  <input type="date" value={customFrom} onChange={(e) => { setCustomFrom(e.target.value); setPreset("custom"); }} className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500" />
                  <span className="text-gray-400 text-xs">→</span>
                  <input type="date" value={customTo} onChange={(e) => { setCustomTo(e.target.value); setPreset("custom"); }} className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500" />
                </div>
                {preset === "custom" && customFrom && customTo && (
                  <button onClick={() => setShowPresets(false)} className="w-full py-1.5 bg-brand-600 text-white rounded-lg text-xs font-medium hover:bg-brand-700">Aplicar</button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Revenue summary block ── */}
      <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6 shadow-sm">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="font-bold text-gray-900 text-base">Resumen de ventas</h2>
            <p className="text-xs text-gray-400 mt-0.5">{dateLabel}</p>
          </div>
        </div>

        {loadingRevenue ? (
          <div className="animate-pulse space-y-4">
            <div className="flex gap-8">
              <div className="h-14 bg-gray-100 rounded-xl flex-1" />
              <div className="h-14 bg-gray-100 rounded-xl flex-1" />
            </div>
            <div className="flex gap-6 pt-2">
              {[...Array(4)].map((_, i) => <div key={i} className="h-16 bg-gray-100 rounded-xl flex-1" />)}
            </div>
          </div>
        ) : (
          <>
            {/* Top row: big numbers */}
            <div className="flex gap-10 pb-6 border-b border-gray-100 mb-6 flex-wrap">
              <RevBig
                label="Ventas totales Shopify"
                value={clp(revenue?.shopify_total ?? 0)}
                sub={revenue?.shopify_change_pct != null ? `${revenue.shopify_change_pct > 0 ? "+" : ""}${revenue.shopify_change_pct}%` : undefined}
                badge={`${revenue?.shopify_orders ?? 0} pedidos`}
              />
              <div className="w-px bg-gray-100 self-stretch hidden sm:block" />
              <RevBig
                label={`Ventas email marketing (${revenue?.email_pct ?? 0}% del total)`}
                value={clp(emailTotal)}
              />
            </div>

            {/* Attribution breakdown row */}
            <div>
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Ingresos atribuidos</p>
              <div className="flex flex-wrap gap-6">
                <RevItem
                  icon={Users}
                  label="Por recipient"
                  value={clp(revenue?.per_recipient ?? 0)}
                  sub={`${(revenue?.total_recipients ?? 0).toLocaleString()} destinatarios enviados`}
                />
                <div className="w-px bg-gray-100 self-stretch hidden sm:block" />
                <RevItem
                  icon={Send}
                  label="Campañas"
                  value={clp(revenue?.campaigns_total ?? 0)}
                  pct={emailTotal > 0 ? `${((revenue?.campaigns_total ?? 0) / emailTotal * 100).toFixed(1)}%` : "—"}
                />
                <RevItem
                  icon={Zap}
                  label="Automatizaciones"
                  value={clp(revenue?.automations_total ?? 0)}
                  pct={emailTotal > 0 ? `${((revenue?.automations_total ?? 0) / emailTotal * 100).toFixed(1)}%` : "—"}
                />
                {(revenue?.klaviyo_total ?? 0) > 0 && (
                  <RevItem
                    icon={Mail}
                    label="Klaviyo (histórico)"
                    value={clp(revenue?.klaviyo_total ?? 0)}
                    pct={emailTotal > 0 ? `${((revenue?.klaviyo_total ?? 0) / emailTotal * 100).toFixed(1)}%` : "—"}
                  />
                )}
                <div className="w-px bg-gray-100 self-stretch hidden sm:block" />
                <RevItem
                  icon={Mail}
                  label="Email total"
                  value={clp(emailTotal)}
                  pct={`${revenue?.email_pct ?? 0}%`}
                />
              </div>
            </div>
          </>
        )}
      </div>

      {/* ── Platform overview cards ── */}
      {!loadingOverview && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
          <StatCard
            label="Contactos activos"
            value={overview?.contacts.opted_in.toLocaleString() ?? "—"}
            sub={`${overview?.contacts.total.toLocaleString()} total`}
            icon={Users}
            color="bg-blue-500"
          />
          <StatCard
            label="Campañas enviadas"
            value={overview?.campaigns.sent ?? "—"}
            sub={`${overview?.campaigns.total} total`}
            icon={Send}
            color="bg-brand-600"
          />
          <StatCard
            label="Tasa apertura global"
            value={`${overview?.sends.open_rate ?? 0}%`}
            sub={`${overview?.sends.opened.toLocaleString()} aperturas`}
            icon={TrendingUp}
            color="bg-green-500"
          />
          <StatCard
            label="Pedidos Shopify"
            value={(revenue?.shopify_orders ?? 0).toLocaleString()}
            sub={`${clp(revenue?.shopify_total ?? 0)} en ventas`}
            icon={ShoppingCart}
            color="bg-orange-500"
          />
          <StatCard
            label="Costo SES (este mes)"
            value={`US$ ${(overview?.email_cost.estimated_usd ?? 0).toFixed(2)}`}
            sub={`${overview?.email_cost.ses_sent_month.toLocaleString() ?? 0} correos · estimado`}
            icon={DollarSign}
            color="bg-slate-600"
          />
        </div>
      )}

      {/* ── Revenue breakdown tables ── */}
      {!loadingRevenue && revenue && (
        <div className="space-y-4 mb-8">
          <RevTable
            title="Campañas — ingresos atribuidos (Klaviyo: open/click, 5 días)"
            rows={(revenue.campaigns ?? []).filter((c: { revenue: number }) => c.revenue > 0)}
            totalRevenue={emailTotal}
            type="campaign"
          />
          <RevTable
            title="Automatizaciones — ingresos atribuidos (Klaviyo: open/click, 5 días)"
            rows={(revenue.automations ?? []).filter((a: { revenue: number }) => a.revenue > 0)}
            totalRevenue={emailTotal}
            type="automation"
          />
          {(revenue.klaviyo_campaigns ?? []).length > 0 && (
            <RevTable
              title="Campañas Klaviyo — ingresos en el período"
              rows={revenue.klaviyo_campaigns ?? []}
              totalRevenue={emailTotal}
              type="klaviyo"
            />
          )}
        </div>
      )}

      {/* ── Recent campaigns table ── */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Últimas campañas enviadas</h2>
        </div>
        {!recent || recent.length === 0 ? (
          <div className="px-6 py-12 text-center text-gray-400 text-sm">Aún no hay campañas enviadas</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Campaña</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Enviados</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Apertura</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((c: { id: number; name: string; total: number; open_rate: number; sent_at: string }) => (
                <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-6 py-3 font-medium text-gray-900">{c.name}</td>
                  <td className="px-6 py-3 text-gray-600">{c.total.toLocaleString()}</td>
                  <td className="px-6 py-3"><span className="font-semibold text-green-700">{c.open_rate}%</span></td>
                  <td className="px-6 py-3 text-gray-500">{formatDateTime(c.sent_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
