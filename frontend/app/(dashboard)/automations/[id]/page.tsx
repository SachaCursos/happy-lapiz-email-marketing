"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { automationsApi } from "@/lib/api";
import {
  Automation, AutomationStats, AutomationStepStat,
  AutomationVariantStat, AutomationPending, AutomationRun,
} from "@/lib/types";
import { formatDate } from "@/lib/utils";
import {
  ArrowLeft, Zap, Play, Pause, FlaskConical, Clock, Trophy,
  Send, Mail, MousePointerClick, ShoppingBag, ChevronRight, GitBranch,
} from "lucide-react";

const TRIGGER_LABELS: Record<string, { label: string; color: string }> = {
  abandoned_cart:           { label: "Carrito abandonado",     color: "bg-green-100 text-green-700" },
  placed_order:             { label: "Compra realizada",       color: "bg-green-100 text-green-700" },
  ordered_product:          { label: "Producto comprado",      color: "bg-green-100 text-green-700" },
  fulfilled_order:          { label: "Pedido enviado",         color: "bg-green-100 text-green-700" },
  delivered_shipment:       { label: "Pedido entregado",       color: "bg-green-100 text-green-700" },
  confirmed_shipment:       { label: "Envío con tracking",     color: "bg-green-100 text-green-700" },
  marked_out_for_delivery:  { label: "En camino",              color: "bg-green-100 text-green-700" },
  fulfilled_partial_order:  { label: "Envío parcial",          color: "bg-green-100 text-green-700" },
  cancelled_order:          { label: "Pedido cancelado",       color: "bg-green-100 text-green-700" },
  refunded_order:           { label: "Pedido reembolsado",     color: "bg-green-100 text-green-700" },
  checkout_started:         { label: "Checkout iniciado",      color: "bg-green-100 text-green-700" },
  added_to_cart:            { label: "Producto al carrito",    color: "bg-green-100 text-green-700" },
  coupon_assigned:          { label: "Cupón asignado",         color: "bg-purple-100 text-purple-700" },
  coupon_used:              { label: "Cupón usado",            color: "bg-purple-100 text-purple-700" },
  viewed_product:           { label: "Producto visto",         color: "bg-blue-100 text-blue-700" },
  active_on_site:           { label: "Activo en el sitio",     color: "bg-blue-100 text-blue-700" },
  welcome:                  { label: "Bienvenida",             color: "bg-gray-100 text-gray-700" },
  reactivation:             { label: "Reactivación",           color: "bg-gray-100 text-gray-700" },
  post_visit:               { label: "Post-compra",            color: "bg-gray-100 text-gray-700" },
};

function delayLabel(h: number): string {
  if (h === 0) return "Inmediatamente";
  if (h < 1)  return `${Math.round(h * 60)} min después`;
  if (h < 24) return `${h}h después`;
  if (h % 24 === 0) return `${h / 24}d después`;
  return `${h}h después`;
}

function KpiCard({ label, value, sub, icon }: { label: string; value: string; sub?: string; icon: React.ReactNode }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 flex items-start gap-3">
      <div className="p-2 bg-gray-50 rounded-lg text-gray-500 shrink-0">{icon}</div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-xs text-gray-500 mt-0.5">{label}</p>
        {sub && <p className="text-xs text-gray-400">{sub}</p>}
      </div>
    </div>
  );
}

// Highlight the winning variant (highest open_rate)
function winner(variants: AutomationVariantStat[]): string | null {
  if (variants.length < 2) return null;
  return variants.reduce((best, v) => v.open_rate > best.open_rate ? v : best).variant;
}

function VariantCard({ v, isWinner }: { v: AutomationVariantStat; isWinner: boolean }) {
  return (
    <div className={`flex-1 rounded-lg border p-3 space-y-1.5 ${
      isWinner ? "border-amber-300 bg-amber-50" : "border-gray-200 bg-white"
    }`}>
      <div className="flex items-center gap-2">
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
          isWinner ? "bg-amber-200 text-amber-800" : "bg-gray-100 text-gray-600"
        }`}>
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

function StepCard({
  stat,
  stepDef,
  prevSent,
  isLast,
}: {
  stat: AutomationStepStat;
  stepDef?: { delay_hours: number; subject?: string; condition?: string | null; variants?: unknown[] };
  prevSent: number | null;
  isLast: boolean;
}) {
  const hasAB = stat.variants.length >= 2;
  const winnerVariant = winner(stat.variants);
  const continuationRate = prevSent ? Math.round((stat.sent / prevSent) * 100) : null;

  return (
    <div className="relative">
      {/* Connector from previous step */}
      {prevSent !== null && (
        <div className="flex items-center gap-3 mb-2 ml-5">
          <div className="w-0.5 h-6 bg-gray-200" />
          {continuationRate !== null && (
            <span className="text-xs text-gray-400">
              {continuationRate}% pasaron a este paso
            </span>
          )}
        </div>
      )}

      <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
        {/* Step header */}
        <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-6 h-6 bg-brand-600 text-white text-xs font-bold rounded-full flex items-center justify-center shrink-0">
              {stat.step}
            </span>
            {stepDef && (
              <div className="flex items-center gap-2 flex-wrap min-w-0">
                <span className="flex items-center gap-1 text-xs text-gray-500 shrink-0">
                  <Clock size={11} /> {delayLabel(stepDef.delay_hours)}
                </span>
                {stepDef.subject && (
                  <span className="text-sm font-medium text-gray-800 truncate">
                    "{stepDef.subject}"
                  </span>
                )}
              </div>
            )}
          </div>
          {hasAB && (
            <span className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 shrink-0">
              <FlaskConical size={10} /> A/B
            </span>
          )}
        </div>

        {/* Metrics */}
        <div className="px-5 py-4">
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-gray-900">{stat.sent.toLocaleString("es-CL")}</p>
              <p className="text-xs text-gray-400">enviados</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-600">{stat.open_rate}%</p>
              <p className="text-xs text-gray-400">abiertos</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600">{stat.click_rate}%</p>
              <p className="text-xs text-gray-400">clics</p>
            </div>
          </div>

          {/* A/B breakdown */}
          {hasAB && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Resultados A/B</p>
              <div className="flex gap-2">
                {stat.variants.map((v) => (
                  <VariantCard key={v.variant} v={v} isWinner={v.variant === winnerVariant} />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function timeUntil(isoDate: string): string {
  const diff = new Date(isoDate).getTime() - Date.now();
  if (diff <= 0) return "listo";
  const mins = Math.round(diff / 60000);
  if (mins < 60) return `en ${mins} min`;
  const hrs = Math.round(diff / 3600000);
  if (hrs < 24) return `en ${hrs}h`;
  return `en ${Math.round(diff / 86400000)}d`;
}

export default function AutomationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const autoId = Number(id);
  const qc = useQueryClient();

  const { data: auto, isLoading: autoLoading } = useQuery<Automation>({
    queryKey: ["automation", autoId],
    queryFn: () => automationsApi.get(autoId).then((r) => r.data),
    staleTime: 30_000,
  });

  const { data: stats } = useQuery<AutomationStats>({
    queryKey: ["automation-stats", autoId],
    queryFn: () => automationsApi.stats(autoId).then((r) => r.data),
    staleTime: 60_000,
    enabled: !!auto,
  });

  const { data: stepStats = [] } = useQuery<AutomationStepStat[]>({
    queryKey: ["automation-step-stats", autoId],
    queryFn: () => automationsApi.stepStats(autoId).then((r) => r.data),
    staleTime: 60_000,
    enabled: !!auto,
  });

  const { data: pending } = useQuery<AutomationPending>({
    queryKey: ["automation-pending", autoId],
    queryFn: () => automationsApi.pending(autoId).then((r) => r.data),
    staleTime: 30_000,
    enabled: !!auto,
  });

  const { data: runs = [] } = useQuery<AutomationRun[]>({
    queryKey: ["automation-runs", autoId],
    queryFn: () => automationsApi.runs(autoId).then((r) => r.data),
    staleTime: 30_000,
    enabled: !!auto,
  });

  const toggleMutation = useMutation({
    mutationFn: () => automationsApi.toggle(autoId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automation", autoId] });
      qc.invalidateQueries({ queryKey: ["automations"] });
    },
  });

  if (autoLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-48" />
          <div className="h-10 bg-gray-200 rounded w-80" />
          <div className="grid grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <div key={i} className="h-20 bg-gray-200 rounded-xl" />)}
          </div>
        </div>
      </div>
    );
  }

  if (!auto) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Automatización no encontrada.</p>
        <Link href="/automations" className="text-brand-600 text-sm mt-2 inline-flex items-center gap-1">
          <ArrowLeft size={14} /> Volver
        </Link>
      </div>
    );
  }

  const trigger = TRIGGER_LABELS[auto.trigger_type] ?? { label: auto.trigger_type, color: "bg-gray-100 text-gray-700" };
  const isActive = auto.status === "active";
  const steps = auto.steps ?? [];

  // Build step definitions map: step number → step config
  const stepDefMap: Record<number, (typeof steps)[0]> = {};
  steps.forEach((s) => { stepDefMap[s.step] = s; });

  const revenueLabel = stats
    ? stats.revenue >= 1_000_000
      ? `$${(stats.revenue / 1_000_000).toFixed(1)}M`
      : stats.revenue >= 1_000
        ? `$${(stats.revenue / 1_000).toFixed(0)}K`
        : `$${stats.revenue.toFixed(0)}`
    : "—";

  return (
    <div className="p-8 max-w-3xl">
      {/* Back */}
      <Link href="/automations" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 mb-6">
        <ArrowLeft size={14} /> Automatizaciones
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-8">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${trigger.color}`}>{trigger.label}</span>
            <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${
              isActive ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isActive ? "bg-green-500" : "bg-gray-400"}`} />
              {isActive ? "Activa" : "Pausada"}
            </span>
            {steps.length > 1 && (
              <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium bg-indigo-100 text-indigo-700">
                <GitBranch size={10} /> {steps.length} pasos
              </span>
            )}
          </div>
          <h1 className="text-2xl font-bold text-gray-900 truncate">{auto.name}</h1>
          {stats?.last_run && (
            <p className="text-xs text-gray-400 mt-1">Último envío: {formatDate(stats.last_run)}</p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => toggleMutation.mutate()}
            disabled={toggleMutation.isPending}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors disabled:opacity-50 ${
              isActive
                ? "border-yellow-200 text-yellow-700 hover:bg-yellow-50"
                : "border-green-200 text-green-700 hover:bg-green-50"
            }`}
          >
            {isActive ? <><Pause size={13} /> Pausar</> : <><Play size={13} /> Activar</>}
          </button>
          <Link
            href="/automations"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors"
          >
            Editar
          </Link>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        <KpiCard label="Correos enviados" value={stats?.sent?.toLocaleString("es-CL") ?? "—"} icon={<Send size={16} />} />
        <KpiCard label="Tasa de apertura" value={stats ? `${stats.open_rate}%` : "—"} sub={stats ? `${stats.opened} abiertos` : undefined} icon={<Mail size={16} />} />
        <KpiCard label="Tasa de clics" value={stats ? `${stats.click_rate}%` : "—"} sub={stats ? `${stats.clicked} clics` : undefined} icon={<MousePointerClick size={16} />} />
        <KpiCard label="Ingresos atribuidos" value={revenueLabel} sub={stats?.orders ? `${stats.orders} pedido${stats.orders !== 1 ? "s" : ""}` : undefined} icon={<ShoppingBag size={16} />} />
      </div>

      {/* Step funnel */}
      {stepStats.length > 0 ? (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-1.5">
            <Zap size={14} className="text-brand-500" /> Rendimiento por paso
          </h2>
          <div className="space-y-0">
            {stepStats.map((stat, idx) => (
              <StepCard
                key={stat.step}
                stat={stat}
                stepDef={stepDefMap[stat.step]}
                prevSent={idx > 0 ? stepStats[idx - 1].sent : null}
                isLast={idx === stepStats.length - 1}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="mb-8 bg-gray-50 border border-gray-200 rounded-xl px-5 py-8 text-center">
          <p className="text-sm text-gray-400">Aún no hay envíos registrados para esta automatización.</p>
          <p className="text-xs text-gray-400 mt-1">Las métricas aparecerán aquí una vez que los primeros correos sean enviados.</p>
        </div>
      )}

      {/* Próximos envíos */}
      {pending && pending.count > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-1.5">
            <Clock size={14} className="text-blue-500" /> Próximos envíos
            <span className="ml-1 bg-blue-600 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">{pending.count}</span>
          </h2>
          <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 space-y-1.5 max-h-52 overflow-y-auto">
            {pending.contacts.map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className={`px-1.5 py-0.5 rounded font-medium shrink-0 ${
                  c.ready ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                }`}>
                  {c.ready ? "listo" : timeUntil(c.send_at)}
                </span>
                {c.step && c.step > 1 && (
                  <span className="px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 font-medium shrink-0">
                    paso {c.step}
                  </span>
                )}
                <span className="text-gray-700 font-medium truncate max-w-[140px]">{c.name}</span>
                <span className="text-gray-400 font-mono truncate">{c.email}</span>
                {c.detail && <span className="text-gray-400 truncate ml-auto shrink-0">{c.detail}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Historial de envíos */}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Historial de envíos</h2>
        {runs.length === 0 ? (
          <p className="text-xs text-gray-400">No hay envíos registrados aún.</p>
        ) : (
          <div className="border border-gray-200 rounded-xl overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium text-gray-500">Contacto</th>
                  <th className="px-3 py-2.5 text-left font-medium text-gray-500">Paso</th>
                  <th className="px-3 py-2.5 text-left font-medium text-gray-500">Variante</th>
                  <th className="px-3 py-2.5 text-left font-medium text-gray-500">Estado</th>
                  <th className="px-3 py-2.5 text-left font-medium text-gray-500">Abierto</th>
                  <th className="px-4 py-2.5 text-left font-medium text-gray-500">Fecha</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5 font-mono text-gray-700 max-w-[180px] truncate">{r.contact_email}</td>
                    <td className="px-3 py-2.5 text-gray-500">
                      {r.step_number ? (
                        <span className="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 font-medium">
                          {r.step_number}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      {r.variant_sent ? (
                        <span className="px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 font-bold">
                          {r.variant_sent}
                        </span>
                      ) : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={`px-1.5 py-0.5 rounded font-medium ${
                        r.status === "sent"   ? "bg-green-50 text-green-700" :
                        r.status === "failed" ? "bg-red-50 text-red-600"    :
                                                "bg-gray-50 text-gray-500"
                      }`}>
                        {r.status}
                      </span>
                      {r.error && <span className="ml-2 text-red-400 truncate max-w-[100px]" title={r.error}>!</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {r.opened_at ? (
                        <span className="text-blue-600">✓</span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-gray-400 whitespace-nowrap">{formatDate(r.triggered_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
