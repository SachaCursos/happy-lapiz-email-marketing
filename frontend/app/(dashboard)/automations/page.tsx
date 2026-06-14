"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { automationsApi, templatesApi, api } from "@/lib/api";
import { Automation, AutomationStats, AutomationVariantStat, AutomationPending, AutomationStep, Template } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { Plus, Zap, Play, Pause, Trash2, ChevronDown, ChevronUp, Pencil, Save, X, Clock, GitBranch, FlaskConical, Tag, BarChart2 } from "lucide-react";

interface CouponCampaign { id: number; name: string; discount_type: string; discount_value: number; prefix: string; }
import Link from "next/link";

const TRIGGER_LABELS: Record<string, { label: string; description: string; color: string }> = {
  // Shopify
  abandoned_cart:           { label: "Carrito abandonado",              description: "Checkout iniciado sin completar compra.",                color: "bg-green-100 text-green-700" },
  checkout_started:         { label: "Checkout iniciado",               description: "Alguien comenzó el proceso de pago en Shopify.",         color: "bg-green-100 text-green-700" },
  added_to_cart:            { label: "Producto al carrito",             description: "Alguien agregó un producto al carrito.",                 color: "bg-green-100 text-green-700" },
  placed_order:             { label: "Compra realizada",                description: "Cliente completó una compra.",                           color: "bg-green-100 text-green-700" },
  ordered_product:          { label: "Producto comprado",               description: "Se dispara por cada producto dentro de una orden.",      color: "bg-green-100 text-green-700" },
  fulfilled_order:          { label: "Pedido enviado",                  description: "El pedido fue procesado y enviado completamente.",        color: "bg-green-100 text-green-700" },
  fulfilled_partial_order:  { label: "Envío parcial",                   description: "Parte del pedido fue enviada.",                          color: "bg-green-100 text-green-700" },
  confirmed_shipment:       { label: "Envío con tracking",              description: "El fulfillment incluye número de seguimiento.",          color: "bg-green-100 text-green-700" },
  delivered_shipment:       { label: "Pedido entregado",                description: "El transportista marcó el paquete como entregado.",      color: "bg-green-100 text-green-700" },
  marked_out_for_delivery:  { label: "En camino",                       description: "El paquete está en reparto.",                            color: "bg-green-100 text-green-700" },
  cancelled_order:          { label: "Pedido cancelado",                description: "Una orden fue cancelada en Shopify.",                    color: "bg-green-100 text-green-700" },
  refunded_order:           { label: "Pedido reembolsado",              description: "Se procesó un reembolso.",                               color: "bg-green-100 text-green-700" },
  // Cupones
  coupon_assigned:          { label: "Cupón asignado",                  description: "Se generó un cupón dinámico para el contacto.",          color: "bg-purple-100 text-purple-700" },
  coupon_used:              { label: "Cupón usado",                     description: "El cliente usó un código de descuento.",                 color: "bg-purple-100 text-purple-700" },
  // Web
  viewed_product:           { label: "Producto visto",                  description: "El contacto vio un producto en happylapiz.cl.",          color: "bg-blue-100 text-blue-700" },
  active_on_site:           { label: "Activo en el sitio",              description: "El contacto estuvo activo en happylapiz.cl.",            color: "bg-blue-100 text-blue-700" },
  subscribed_to_back_in_stock: { label: "Alerta de stock",             description: "El cliente se suscribió a notificación de stock.",       color: "bg-blue-100 text-blue-700" },
  // Internos
  welcome:                  { label: "Bienvenida",                      description: "Nuevo contacto con opt-in activo.",                      color: "bg-gray-100 text-gray-700" },
  reactivation:             { label: "Reactivación",                    description: "Clientes sin compra en N días.",                         color: "bg-gray-100 text-gray-700" },
  post_visit:               { label: "Post-compra",                     description: "N días después de la última compra.",                    color: "bg-gray-100 text-gray-700" },
  // HotBoat
  abandoned_booking:        { label: "Reserva abandonada",              description: "Reserva con pago pendiente sin completar.",              color: "bg-orange-100 text-orange-700" },
};

function configSummary(auto: Automation): string {
  const c = auto.trigger_config ?? {};
  switch (auto.trigger_type) {
    case "abandoned_booking":
      return `${c.delay_minutes ?? 5} min después de la reserva pendiente`;
    case "welcome":
      return c.delay_hours ? `${c.delay_hours}h después de registrarse` : "Inmediatamente al registrarse";
    case "post_visit":
      return `${c.delay_days ?? 3} días después de la última compra`;
    case "reactivation":
      return `Sin compra en ${c.inactivity_days ?? 90}+ días`;
    default:
      if (c.delay_hours !== undefined) {
        const h = Number(c.delay_hours);
        const delay = h === 0 ? "inmediatamente" : h < 1 ? `${Math.round(h * 60)} min después` : h < 24 ? `${h}h después` : `${h / 24}d después`;
        return `Envío ${delay} del evento`;
      }
      return "";
  }
}

const CONDITION_LABELS: Record<string, string> = {
  not_purchased: "Si no ha comprado",
  not_recovered: "Si no recuperó el carrito",
  always: "Siempre",
};

function delayLabel(hours: number): string {
  if (hours === 0) return "inmediatamente";
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  if (hours < 24) return `${hours}h`;
  if (hours % 24 === 0) return `${hours / 24}d`;
  return `${hours}h`;
}

function EditPanel({
  auto,
  templates,
  couponCampaigns,
  onSave,
  onCancel,
  saving,
}: {
  auto: Automation;
  templates: Template[];
  couponCampaigns: CouponCampaign[];
  onSave: (data: Partial<Automation>) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const effectiveSteps: AutomationStep[] = auto.steps?.length
    ? auto.steps
    : auto.template_id && auto.subject
      ? [{ step: 1, delay_hours: (auto.trigger_config as Record<string,number>)?.delay_hours ?? 0, template_id: auto.template_id, subject: auto.subject, condition: null }]
      : [];

  const [name, setName] = useState(auto.name);
  const [couponCampaignId, setCouponCampaignId] = useState<number | null>(auto.coupon_campaign_id ?? null);
  const [steps, setSteps] = useState<AutomationStep[]>(
    effectiveSteps.length > 0 ? effectiveSteps : [{ step: 1, delay_hours: 1, template_id: 0, subject: "", condition: null }]
  );
  const [cfg, setCfg] = useState<Record<string, number>>(
    (auto.trigger_config as Record<string,number>) ?? {}
  );

  function updateStep(idx: number, patch: Partial<AutomationStep>) {
    setSteps((prev) => prev.map((s, i) => i === idx ? { ...s, ...patch } : s));
  }

  function addStep() {
    setSteps((prev) => [...prev, { step: prev.length + 1, delay_hours: 24, template_id: 0, subject: "", condition: "not_purchased" }]);
  }

  function removeStep(idx: number) {
    setSteps((prev) => prev.filter((_, i) => i !== idx).map((s, i) => ({ ...s, step: i + 1 })));
  }

  const isValid = name && steps.every((s) => s.template_id && s.subject);

  return (
    <div className="border-t border-brand-100 bg-blue-50 px-5 py-4 space-y-4">
      <p className="text-xs font-semibold text-brand-700 uppercase tracking-wider">Editar automatización</p>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Nombre interno</label>
        <input value={name} onChange={(e) => setName(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1 flex items-center gap-1.5">
          <Tag size={11} /> Campaña de cupones (opcional)
        </label>
        <select
          value={couponCampaignId ?? ""}
          onChange={(e) => setCouponCampaignId(e.target.value ? Number(e.target.value) : null)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">Sin cupón</option>
          {couponCampaigns.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} — {c.discount_type === "percentage" ? `${c.discount_value}% OFF` : `$${c.discount_value.toLocaleString("es-CL")}`} ({c.prefix}-XXXX)
            </option>
          ))}
        </select>
        {couponCampaignId && (
          <p className="text-xs text-purple-600 mt-1">Usa <code className="bg-purple-50 px-1 rounded">{"{{ coupon_code }}"}</code> o <code className="bg-purple-50 px-1 rounded">{"{{ event.extra.checkout_url_with_coupon }}"}</code> en la plantilla.</p>
        )}
      </div>

      {/* Trigger config */}
      {auto.trigger_type === "abandoned_booking" && (
        <div className="grid grid-cols-2 gap-3 max-w-sm">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Delay (min)</label>
            <input type="number" min={1} value={cfg.delay_minutes ?? 5}
              onChange={(e) => setCfg((c) => ({ ...c, delay_minutes: Number(e.target.value) }))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Ventana (horas)</label>
            <input type="number" min={1} value={cfg.lookback_hours ?? 24}
              onChange={(e) => setCfg((c) => ({ ...c, lookback_hours: Number(e.target.value) }))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
        </div>
      )}

      {/* Steps */}
      <div className="space-y-3">
        <p className="text-xs font-medium text-gray-600">Pasos del flujo</p>
        {steps.map((step, i) => (
          <div key={i} className="bg-white border border-gray-200 rounded-lg p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-500">Correo {i + 1}</span>
              {steps.length > 1 && (
                <button onClick={() => removeStep(i)} className="text-red-400 hover:text-red-600 p-0.5">
                  <Trash2 size={12} />
                </button>
              )}
            </div>
            <div className="flex gap-2 items-center">
              <input type="number" min={0} value={step.delay_hours}
                onChange={(e) => updateStep(i, { delay_hours: Number(e.target.value) })}
                className="w-20 border border-gray-300 rounded px-2 py-1 text-sm text-center focus:outline-none focus:ring-1 focus:ring-brand-500" />
              <span className="text-xs text-gray-500">{i === 0 ? "horas desde el evento" : "horas desde el paso anterior"}</span>
            </div>
            {i > 0 && (
              <div className={`rounded border px-2 py-2 space-y-1 ${step.condition !== "always" ? "bg-red-50 border-red-200" : "bg-gray-50 border-gray-200"}`}>
                <p className="text-xs font-medium text-gray-500 flex items-center gap-1"><GitBranch size={10} /> Salida del flujo si...</p>
                <select value={step.condition ?? "not_purchased"}
                  onChange={(e) => updateStep(i, { condition: e.target.value as AutomationStep["condition"] })}
                  className="w-full border border-gray-300 rounded px-2 py-1 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-brand-500">
                  <option value="not_purchased">El contacto realizó una compra</option>
                  <option value="not_recovered">El carrito fue recuperado</option>
                  <option value="always">Nunca (siempre enviar)</option>
                </select>
                {step.condition !== "always" && (
                  <p className="text-xs text-red-500">Si la condición se cumple, el contacto sale del flujo.</p>
                )}
              </div>
            )}
            <select value={step.template_id || 0}
              onChange={(e) => updateStep(i, { template_id: Number(e.target.value) })}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-500">
              <option value={0}>— Plantilla —</option>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <input value={step.subject}
              onChange={(e) => updateStep(i, { subject: e.target.value })}
              placeholder="Asunto del email"
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500" />
            <input value={step.preview_text ?? ""}
              onChange={(e) => updateStep(i, { preview_text: e.target.value || undefined })}
              placeholder="Preview text (opcional)"
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500 text-gray-500" />
          </div>
        ))}
        <button onClick={addStep}
          className="w-full py-2 border border-dashed border-gray-300 rounded-lg text-xs text-gray-500 hover:border-brand-400 hover:text-brand-600 transition-colors flex items-center justify-center gap-1">
          <Plus size={11} /> Agregar paso
        </button>
      </div>

      <div className="flex gap-2 pt-1">
        <button
          onClick={() => onSave({ name, steps: steps.map((s, i) => ({ ...s, step: i + 1 })), trigger_config: cfg as Record<string, number>, template_id: steps[0]?.template_id || null, subject: steps[0]?.subject || null, coupon_campaign_id: couponCampaignId })}
          disabled={saving || !isValid}
          className="flex items-center gap-1.5 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >
          <Save size={13} /> {saving ? "Guardando..." : "Guardar cambios"}
        </button>
        <button onClick={onCancel}
          className="flex items-center gap-1.5 px-3 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm hover:bg-gray-50 transition-colors">
          <X size={13} /> Cancelar
        </button>
      </div>
    </div>
  );
}

function AutomationRow({ auto, templates, couponCampaigns }: { auto: Automation; templates: Template[]; couponCampaigns: CouponCampaign[] }) {
  const qc = useQueryClient();
  const [showRuns, setShowRuns] = useState(false);
  const [editing, setEditing] = useState(false);

  const { data: stats } = useQuery<AutomationStats>({
    queryKey: ["automation-stats", auto.id],
    queryFn: () => automationsApi.stats(auto.id).then((r) => r.data),
    staleTime: 60_000,
  });

  const toggleMutation = useMutation({
    mutationFn: () => automationsApi.toggle(auto.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automations"] }),
  });

  const updateMutation = useMutation({
    mutationFn: (data: unknown) => automationsApi.update(auto.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automations"] });
      setEditing(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => automationsApi.delete(auto.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automations"] }),
  });

  const trigger = TRIGGER_LABELS[auto.trigger_type] ?? {
    label: auto.trigger_type,
    description: "",
    color: "bg-gray-100 text-gray-700",
  };
  const isActive = auto.status === "active";
  const stepCount = auto.steps?.length ?? 1;
  const tplName = stepCount === 1
    ? templates.find((t) => t.id === (auto.steps?.[0]?.template_id ?? auto.template_id))?.name
    : null;

  return (
    <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
      <div className="p-5 flex items-start gap-4">
        <div className={`mt-0.5 px-2.5 py-1 rounded-full text-xs font-semibold shrink-0 ${trigger.color}`}>
          {trigger.label}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Link href={`/automations/${auto.id}`} className="font-semibold text-gray-900 truncate hover:text-brand-600 transition-colors">
              {auto.name}
            </Link>
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                isActive ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isActive ? "bg-green-500" : "bg-gray-400"}`} />
              {isActive ? "Activa" : "Pausada"}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            <p className="text-sm text-gray-500">{configSummary(auto)}</p>
            {stepCount > 1 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700">
                <GitBranch size={10} /> {stepCount} pasos
              </span>
            )}
          </div>
          {stepCount === 1 && auto.subject && (
            <p className="text-xs text-gray-400 mt-0.5 truncate">Asunto: {auto.steps?.[0]?.subject ?? auto.subject}</p>
          )}
          {stepCount === 1 && tplName && (
            <p className="text-xs text-gray-400 mt-0.5 truncate">Plantilla: <span className="text-gray-600">{tplName}</span></p>
          )}
          {stepCount > 1 && (
            <p className="text-xs text-gray-400 mt-0.5">
              {auto.steps?.map((s, i) => `Paso ${i+1}: ${s.subject}`).join(" · ")}
            </p>
          )}
        </div>

        <div className="flex items-start gap-4 shrink-0">
          {/* Enviados */}
          <div className="text-center min-w-[52px]">
            <p className="text-xl font-bold text-gray-900">{stats?.sent ?? "—"}</p>
            <p className="text-xs text-gray-400">enviados</p>
          </div>
          {/* Open rate */}
          <div className="text-center min-w-[52px]">
            <p className="text-xl font-bold text-gray-900">
              {stats ? `${stats.open_rate}%` : "—"}
            </p>
            <p className="text-xs text-gray-400">abiertos</p>
          </div>
          {/* Click rate */}
          <div className="text-center min-w-[52px]">
            <p className="text-xl font-bold text-gray-900">
              {stats ? `${stats.click_rate}%` : "—"}
            </p>
            <p className="text-xs text-gray-400">clicks</p>
          </div>
          {/* Conversiones */}
          <div className="text-center min-w-[72px]">
            <p className="text-xl font-bold text-gray-900">
              {stats
                ? stats.revenue >= 1000
                  ? `$${(stats.revenue / 1000).toFixed(0)}K`
                  : `$${stats.revenue.toFixed(0)}`
                : "—"}
            </p>
            <p className="text-xs text-gray-400">en ventas</p>
            {stats && stats.orders > 0 && (
              <p className="text-xs text-gray-400">{stats.orders} pedido{stats.orders !== 1 ? "s" : ""}</p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Link
            href={`/automations/${auto.id}`}
            title="Ver métricas detalladas"
            className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:bg-brand-50 hover:text-brand-600 hover:border-brand-300 transition-colors"
          >
            <BarChart2 size={14} />
          </Link>
          <button
            onClick={() => { setEditing((v) => !v); setShowRuns(false); }}
            title="Editar"
            className={`p-2 rounded-lg border transition-colors ${editing ? "border-brand-400 bg-brand-50 text-brand-600" : "border-gray-200 text-gray-500 hover:bg-gray-50"}`}
          >
            <Pencil size={14} />
          </button>
          <button
            onClick={() => toggleMutation.mutate()}
            disabled={toggleMutation.isPending}
            title={isActive ? "Pausar" : "Activar"}
            className={`p-2 rounded-lg border transition-colors ${
              isActive
                ? "border-yellow-200 text-yellow-600 hover:bg-yellow-50"
                : "border-green-200 text-green-600 hover:bg-green-50"
            } disabled:opacity-50`}
          >
            {isActive ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button
            onClick={() => {
              if (confirm(`¿Eliminar automatización "${auto.name}"?`)) deleteMutation.mutate();
            }}
            disabled={deleteMutation.isPending}
            className="p-2 rounded-lg border border-red-100 text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            <Trash2 size={14} />
          </button>
          <button
            onClick={() => { setShowRuns((v) => !v); setEditing(false); }}
            className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
            title="Ver historial"
          >
            {showRuns ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {stats?.variants && stats.variants.length > 0 && (
        <div className="border-t border-gray-100 px-5 py-3 bg-purple-50">
          <p className="text-xs font-semibold text-purple-700 flex items-center gap-1.5 mb-2">
            <FlaskConical size={11} /> Resultados A/B
          </p>
          <div className="flex gap-4 flex-wrap">
            {stats.variants.map((v: AutomationVariantStat) => (
              <div key={v.variant} className="flex items-center gap-3 bg-white border border-purple-200 rounded-lg px-3 py-2 text-xs">
                <span className="font-bold text-purple-700 w-4">
                  {v.variant}
                </span>
                <span className="text-gray-600">{v.sent} env.</span>
                <span className="text-blue-600">{v.open_rate}% abr.</span>
                <span className="text-green-600">{v.click_rate}% clic</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {editing && (
        <EditPanel
          auto={auto}
          templates={templates}
          couponCampaigns={couponCampaigns}
          onSave={(data) => updateMutation.mutate(data)}
          onCancel={() => setEditing(false)}
          saving={updateMutation.isPending}
        />
      )}
      {showRuns && <ExpandedPanel automationId={auto.id} />}
    </div>
  );
}

function ExpandedPanel({ automationId }: { automationId: number }) {
  const { data: runs = [], isLoading: runsLoading } = useQuery({
    queryKey: ["automation-runs", automationId],
    queryFn: () => automationsApi.runs(automationId).then((r) => r.data),
    staleTime: 30_000,
  });

  const { data: pending, isLoading: pendingLoading } = useQuery<AutomationPending>({
    queryKey: ["automation-pending", automationId],
    queryFn: () => automationsApi.pending(automationId).then((r) => r.data),
    staleTime: 60_000,
  });

  function timeUntil(isoDate: string): string {
    const diff = new Date(isoDate).getTime() - Date.now();
    if (diff <= 0) return "ahora";
    const mins = Math.round(diff / 60000);
    if (mins < 60) return `en ${mins} min`;
    const hrs = Math.round(diff / 3600000);
    if (hrs < 24) return `en ${hrs}h`;
    return `en ${Math.round(diff / 86400000)}d`;
  }

  return (
    <div className="border-t border-gray-100 divide-y divide-gray-100">
      {/* Próximos envíos */}
      <div className="bg-blue-50 px-5 py-3">
        <p className="text-xs font-semibold text-blue-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
          <Clock size={11} /> Próximos envíos
          {pending && pending.count > 0 && (
            <span className="ml-1 bg-blue-600 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">
              {pending.count}
            </span>
          )}
        </p>
        {pendingLoading ? (
          <p className="text-xs text-blue-400">Cargando...</p>
        ) : !pending || pending.count === 0 ? (
          <p className="text-xs text-blue-400">No hay envíos pendientes.</p>
        ) : (
          <div className="space-y-1 max-h-40 overflow-y-auto">
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
                <span className="text-gray-700 font-medium truncate max-w-[130px]">{c.name}</span>
                <span className="text-gray-400 font-mono truncate max-w-[150px]">{c.email}</span>
                {c.detail && <span className="text-gray-400 truncate max-w-[140px] ml-auto shrink-0">{c.detail}</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Últimos envíos */}
      <div className="bg-gray-50 px-5 py-3">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Últimos envíos
        </p>
        {runsLoading ? (
          <p className="text-xs text-gray-400">Cargando...</p>
        ) : runs.length === 0 ? (
          <p className="text-xs text-gray-400">Aún no hay envíos registrados.</p>
        ) : (
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {runs.map((r: { id: number; contact_email: string; status: string; triggered_at: string; error?: string }) => (
              <div key={r.id} className="flex items-center gap-3 text-xs">
                <span className={`px-1.5 py-0.5 rounded font-medium shrink-0 ${
                  r.status === "sent" ? "bg-green-100 text-green-700"
                  : r.status === "failed" ? "bg-red-100 text-red-700"
                  : "bg-gray-100 text-gray-500"
                }`}>
                  {r.status}
                </span>
                <span className="text-gray-700 font-mono truncate max-w-[200px]">{r.contact_email}</span>
                <span className="text-gray-400 ml-auto shrink-0">{formatDate(r.triggered_at)}</span>
                {r.error && <span className="text-red-500 truncate max-w-[150px]" title={r.error}>{r.error}</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

type FilterTab = "active" | "paused" | "all";

export default function AutomationsPage() {
  const [filter, setFilter] = useState<FilterTab>("active");

  const { data: automations = [], isLoading } = useQuery<Automation[]>({
    queryKey: ["automations"],
    queryFn: () => automationsApi.list().then((r) => r.data),
    staleTime: 0,
  });

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  const { data: couponCampaigns = [] } = useQuery<CouponCampaign[]>({
    queryKey: ["coupon-campaigns"],
    queryFn: () => api.get("/coupons/campaigns").then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  const activeCount = automations.filter((a) => a.status === "active").length;
  const pausedCount = automations.filter((a) => a.status !== "active").length;

  const visible = filter === "all"
    ? automations
    : automations.filter((a) => filter === "active" ? a.status === "active" : a.status !== "active");

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Automatizaciones</h1>
          <p className="text-gray-500 mt-1 text-sm">
            {activeCount} activa{activeCount !== 1 ? "s" : ""} · {pausedCount} pausada{pausedCount !== 1 ? "s" : ""}
          </p>
        </div>
        <Link
          href="/automations/new"
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors"
        >
          <Plus size={15} />
          Nueva automatización
        </Link>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit">
        {([
          { key: "active", label: "Activas", count: activeCount },
          { key: "paused", label: "Pausadas", count: pausedCount },
          { key: "all",    label: "Todas",    count: automations.length },
        ] as { key: FilterTab; label: string; count: number }[]).map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${
              filter === key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {label}
            <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${
              filter === key ? "bg-gray-100 text-gray-600" : "bg-gray-200 text-gray-500"
            }`}>
              {count}
            </span>
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : automations.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
          <div className="w-14 h-14 bg-gray-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Zap size={24} className="text-gray-300" />
          </div>
          <p className="text-gray-900 font-semibold">Sin automatizaciones</p>
          <p className="text-gray-400 text-sm mt-1 mb-6">
            Crea flujos de email que se disparan automáticamente según el comportamiento de tus clientes.
          </p>
          <Link
            href="/automations/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors"
          >
            <Plus size={15} /> Crear primera automatización
          </Link>
        </div>
      ) : visible.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <p className="text-gray-500 text-sm">No hay automatizaciones {filter === "active" ? "activas" : "pausadas"}.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {visible.map((a) => (
            <AutomationRow key={a.id} auto={a} templates={templates} couponCampaigns={couponCampaigns} />
          ))}
        </div>
      )}
    </div>
  );
}
