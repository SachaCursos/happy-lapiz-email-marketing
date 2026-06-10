"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { automationsApi, templatesApi } from "@/lib/api";
import { Template, AutomationTrigger, AutomationStep } from "@/lib/types";
import { ArrowLeft, Clock, Info, Plus, Trash2, GitBranch, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";

// ── Trigger definitions ────────────────────────────────────────────────────────
const TRIGGERS: {
  value: AutomationTrigger;
  label: string;
  description: string;
  badge: string;
  badgeColor: string;
}[] = [
  { value: "abandoned_cart",           badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Carrito abandonado",               description: "Checkout iniciado sin completar compra." },
  { value: "checkout_started",         badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Checkout iniciado",                description: "Alguien comenzó el proceso de pago." },
  { value: "added_to_cart",            badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Producto agregado al carrito",     description: "Alguien agregó un producto al carrito." },
  { value: "placed_order",             badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Compra realizada",                 description: "Cliente completó una compra." },
  { value: "ordered_product",          badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Producto comprado",                description: "Se dispara por cada producto dentro de una orden." },
  { value: "fulfilled_order",          badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Pedido enviado",                   description: "El pedido fue procesado y enviado completamente." },
  { value: "fulfilled_partial_order",  badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Envío parcial",                    description: "Parte del pedido fue enviada." },
  { value: "confirmed_shipment",       badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Envío con tracking",               description: "El fulfillment incluye número de seguimiento." },
  { value: "delivered_shipment",       badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Pedido entregado",                 description: "El transportista marcó el paquete como entregado." },
  { value: "marked_out_for_delivery",  badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "En camino",                        description: "El paquete está en reparto." },
  { value: "cancelled_order",          badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Pedido cancelado",                 description: "Una orden fue cancelada en Shopify." },
  { value: "refunded_order",           badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",   label: "Pedido reembolsado",               description: "Se procesó un reembolso." },
  { value: "coupon_assigned",          badge: "Cupón",    badgeColor: "bg-purple-100 text-purple-700", label: "Cupón asignado",                   description: "Se generó un cupón dinámico para el contacto." },
  { value: "coupon_used",              badge: "Cupón",    badgeColor: "bg-purple-100 text-purple-700", label: "Cupón usado",                      description: "El cliente usó un código de descuento." },
  { value: "viewed_product",           badge: "Web",      badgeColor: "bg-blue-100 text-blue-700",     label: "Producto visto",                   description: "El contacto vio un producto en happylapiz.cl." },
  { value: "active_on_site",           badge: "Web",      badgeColor: "bg-blue-100 text-blue-700",     label: "Activo en el sitio",               description: "El contacto estuvo activo en happylapiz.cl." },
  { value: "subscribed_to_back_in_stock", badge: "Web",  badgeColor: "bg-blue-100 text-blue-700",     label: "Alerta de stock",                  description: "El cliente se suscribió a notificación de stock." },
  { value: "welcome",                  badge: "Interno",  badgeColor: "bg-gray-100 text-gray-700",     label: "Bienvenida (nuevo suscriptor)",    description: "Nuevo contacto con opt-in activo." },
  { value: "reactivation",             badge: "Interno",  badgeColor: "bg-gray-100 text-gray-700",     label: "Reactivación (cliente inactivo)",  description: "Sin compra en N días." },
  { value: "post_visit",               badge: "Interno",  badgeColor: "bg-gray-100 text-gray-700",     label: "Seguimiento post-compra",          description: "N días después de la última compra." },
  { value: "abandoned_booking",        badge: "HotBoat",  badgeColor: "bg-orange-100 text-orange-700", label: "Reserva abandonada (HotBoat)",     description: "Reserva con pago pendiente sin completar." },
];

const EVENT_TRIGGERS = new Set<AutomationTrigger>([
  "abandoned_cart", "checkout_started", "added_to_cart",
  "placed_order", "ordered_product", "fulfilled_order", "fulfilled_partial_order",
  "confirmed_shipment", "delivered_shipment", "marked_out_for_delivery",
  "cancelled_order", "refunded_order", "coupon_assigned", "coupon_used",
  "viewed_product", "active_on_site", "subscribed_to_back_in_stock", "welcome",
]);

// Conditions available per trigger type
const CONDITION_OPTIONS: Record<string, { value: string; label: string; hint: string }[]> = {
  abandoned_cart: [
    { value: "not_recovered", label: "Si aún no compró (carrito no recuperado)", hint: "Solo enviar si el carrito sigue abandonado." },
    { value: "always",        label: "Siempre enviar",                            hint: "Enviar sin importar si ya compró." },
  ],
  placed_order: [
    { value: "always", label: "Siempre enviar", hint: "" },
  ],
  _default: [
    { value: "not_purchased", label: "Si no ha comprado desde que entró al flujo", hint: "Se detiene si el contacto realizó una compra." },
    { value: "always",        label: "Siempre enviar",                             hint: "Enviar sin condiciones." },
  ],
};

type TimeUnit = "minutos" | "horas" | "dias";

function toHours(value: number, unit: TimeUnit): number {
  if (unit === "minutos") return value / 60;
  if (unit === "dias") return value * 24;
  return value;
}

const TRIGGER_DEFAULTS: Partial<Record<AutomationTrigger, { delay: number; unit: TimeUnit; lookback: number; lookbackUnit: "horas" | "dias" }>> = {
  abandoned_cart:          { delay: 1,  unit: "horas",   lookback: 24, lookbackUnit: "horas" },
  checkout_started:        { delay: 0,  unit: "horas",   lookback: 48, lookbackUnit: "horas" },
  added_to_cart:           { delay: 0,  unit: "horas",   lookback: 48, lookbackUnit: "horas" },
  placed_order:            { delay: 0,  unit: "horas",   lookback: 48, lookbackUnit: "horas" },
  ordered_product:         { delay: 0,  unit: "horas",   lookback: 48, lookbackUnit: "horas" },
  fulfilled_order:         { delay: 0,  unit: "horas",   lookback: 72, lookbackUnit: "horas" },
  fulfilled_partial_order: { delay: 0,  unit: "horas",   lookback: 72, lookbackUnit: "horas" },
  confirmed_shipment:      { delay: 0,  unit: "horas",   lookback: 72, lookbackUnit: "horas" },
  delivered_shipment:      { delay: 1,  unit: "dias",    lookback: 3,  lookbackUnit: "dias" },
  marked_out_for_delivery: { delay: 0,  unit: "horas",   lookback: 48, lookbackUnit: "horas" },
  cancelled_order:         { delay: 1,  unit: "horas",   lookback: 48, lookbackUnit: "horas" },
  refunded_order:          { delay: 1,  unit: "horas",   lookback: 48, lookbackUnit: "horas" },
  coupon_assigned:         { delay: 0,  unit: "minutos", lookback: 48, lookbackUnit: "horas" },
  coupon_used:             { delay: 0,  unit: "horas",   lookback: 48, lookbackUnit: "horas" },
  viewed_product:          { delay: 0,  unit: "horas",   lookback: 24, lookbackUnit: "horas" },
  active_on_site:          { delay: 0,  unit: "horas",   lookback: 24, lookbackUnit: "horas" },
  subscribed_to_back_in_stock: { delay: 0, unit: "horas", lookback: 48, lookbackUnit: "horas" },
  welcome:                 { delay: 0,  unit: "horas",   lookback: 48, lookbackUnit: "horas" },
};

const TIME_UNITS = [
  { value: "minutos", label: "minutos" },
  { value: "horas",   label: "horas" },
  { value: "dias",    label: "días" },
];
const LOOKBACK_UNITS = [
  { value: "horas", label: "horas" },
  { value: "dias",  label: "días" },
];

function TimerPicker({ label, hint, value, unit, units, onValueChange, onUnitChange }: {
  label: string; hint?: string; value: number; unit: string;
  units: { value: string; label: string }[];
  onValueChange: (v: number) => void; onUnitChange: (u: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
        <Clock size={13} className="text-gray-400" /> {label}
      </label>
      <div className="flex gap-2">
        <input type="number" min={0} value={value}
          onChange={(e) => onValueChange(Math.max(0, Number(e.target.value)))}
          className="w-28 border border-gray-300 rounded-lg px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-500 text-center" />
        <select value={unit} onChange={(e) => onUnitChange(e.target.value)}
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
          {units.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
        </select>
      </div>
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  );
}

// ── Step card ────────────────────────────────────────────────────────────────
interface StepState {
  delayValue: number;
  delayUnit: TimeUnit;
  templateId: number | "";
  subject: string;
  condition: string;
}

function StepCard({
  stepNum,
  total,
  step,
  templates,
  triggerType,
  isFirst,
  onChange,
  onRemove,
}: {
  stepNum: number;
  total: number;
  step: StepState;
  templates: Template[];
  triggerType: AutomationTrigger;
  isFirst: boolean;
  onChange: (s: StepState) => void;
  onRemove: () => void;
}) {
  const condOptions = CONDITION_OPTIONS[triggerType] ?? CONDITION_OPTIONS["_default"];

  return (
    <div className="relative border border-gray-200 rounded-xl bg-white overflow-hidden">
      {/* Connector line above (for steps after first) */}
      {!isFirst && (
        <div className="absolute -top-5 left-7 w-0.5 h-5 bg-gray-200" />
      )}

      <div className="px-5 py-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-6 h-6 bg-brand-600 text-white text-xs font-bold rounded-full flex items-center justify-center">
            {stepNum}
          </span>
          <span className="text-sm font-semibold text-gray-700">
            {isFirst ? "Primer correo" : `Correo ${stepNum}`}
          </span>
        </div>
        {total > 1 && (
          <button onClick={onRemove} className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">
            <Trash2 size={14} />
          </button>
        )}
      </div>

      <div className="px-5 py-4 space-y-4">
        {/* Delay */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
            <Clock size={13} className="text-gray-400" />
            {isFirst ? "Enviar después del evento" : `Esperar antes de enviar este correo`}
          </label>
          <div className="flex gap-2">
            <input type="number" min={0} value={step.delayValue}
              onChange={(e) => onChange({ ...step, delayValue: Math.max(0, Number(e.target.value)) })}
              className="w-28 border border-gray-300 rounded-lg px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-500 text-center" />
            <select value={step.delayUnit} onChange={(e) => onChange({ ...step, delayUnit: e.target.value as TimeUnit })}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
              {TIME_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </div>
          {!isFirst && (
            <p className="text-xs text-gray-400 mt-1">Tiempo desde el envío del correo anterior.</p>
          )}
        </div>

        {/* Condition (only from step 2 onwards) */}
        {!isFirst && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
              <GitBranch size={13} className="text-gray-400" /> Condición para enviar
            </label>
            <select value={step.condition} onChange={(e) => onChange({ ...step, condition: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
              {condOptions.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            {condOptions.find((o) => o.value === step.condition)?.hint && (
              <p className="text-xs text-gray-400 mt-1">
                {condOptions.find((o) => o.value === step.condition)?.hint}
              </p>
            )}
          </div>
        )}

        {/* Template */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Plantilla de email *</label>
          <select value={step.templateId} onChange={(e) => onChange({ ...step, templateId: Number(e.target.value) || "" })}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
            <option value="">Seleccionar plantilla...</option>
            {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>

        {/* Subject */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Asunto del email *</label>
          <input value={step.subject} onChange={(e) => onChange({ ...step, subject: e.target.value })}
            placeholder='ej. ¡Tu carrito te está esperando, {{ first_name }}!'
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────
export default function NewAutomationPage() {
  const router = useRouter();
  const qc = useQueryClient();

  const [name, setName] = useState("");
  const [triggerType, setTriggerType] = useState<AutomationTrigger>("abandoned_cart");
  const [showTriggers, setShowTriggers] = useState(false);

  // Steps
  const [steps, setSteps] = useState<StepState[]>([
    { delayValue: 1, delayUnit: "horas", templateId: "", subject: "", condition: "not_recovered" },
  ]);

  // Lookback (trigger-level config, only for event triggers)
  const [lookbackValue, setLookbackValue] = useState(24);
  const [lookbackUnit, setLookbackUnit] = useState<"horas" | "dias">("horas");

  // Internal trigger configs
  const [inactivityDays, setInactivityDays] = useState(90);
  const [cooldownDays, setCooldownDays] = useState(180);
  const [postVisitDays, setPostVisitDays] = useState(3);
  const [bookingDelayMinutes, setBookingDelayMinutes] = useState(5);

  // Reset defaults when trigger type changes
  useEffect(() => {
    const def = TRIGGER_DEFAULTS[triggerType];
    if (def) {
      setLookbackValue(def.lookback);
      setLookbackUnit(def.lookbackUnit as "horas" | "dias");
      setSteps((prev) => prev.map((s, i) =>
        i === 0 ? { ...s, delayValue: def.delay, delayUnit: def.unit } : s
      ));
    }
  }, [triggerType]);

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  const selectedTrigger = TRIGGERS.find((t) => t.value === triggerType)!;

  function addStep() {
    setSteps((prev) => [
      ...prev,
      { delayValue: 24, delayUnit: "horas", templateId: "", subject: "", condition: "not_purchased" },
    ]);
  }

  function removeStep(idx: number) {
    setSteps((prev) => prev.filter((_, i) => i !== idx).map((s, i) => ({ ...s })));
  }

  function updateStep(idx: number, s: StepState) {
    setSteps((prev) => prev.map((old, i) => (i === idx ? s : old)));
  }

  const mutation = useMutation({
    mutationFn: () => {
      let triggerConfig: Record<string, number> = {};

      if (triggerType === "reactivation") {
        triggerConfig = { inactivity_days: inactivityDays, cooldown_days: cooldownDays };
      } else if (triggerType === "post_visit") {
        triggerConfig = { delay_days: postVisitDays };
      } else if (triggerType === "abandoned_booking") {
        triggerConfig = { delay_minutes: bookingDelayMinutes, lookback_hours: 24 };
      } else if (EVENT_TRIGGERS.has(triggerType)) {
        triggerConfig = {
          lookback_hours: toHours(lookbackValue, lookbackUnit as TimeUnit),
        };
      }

      const stepsPayload: AutomationStep[] = steps.map((s, i) => ({
        step: i + 1,
        delay_hours: toHours(s.delayValue, s.delayUnit),
        template_id: Number(s.templateId),
        subject: s.subject,
        condition: i === 0 ? null : (s.condition as AutomationStep["condition"]),
      }));

      return automationsApi.create({
        name,
        trigger_type: triggerType,
        trigger_config: triggerConfig,
        steps: stepsPayload,
        // Keep legacy fields from step 1 for backwards compat
        template_id: Number(steps[0].templateId) || undefined,
        subject: steps[0].subject || undefined,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automations"] });
      router.push("/automations");
    },
  });

  const isValid = name && steps.every((s) => s.templateId && s.subject);

  return (
    <div className="p-8 max-w-2xl">
      <Link href="/automations" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6">
        <ArrowLeft size={15} /> Volver
      </Link>
      <h1 className="text-2xl font-bold text-gray-900 mb-8">Nueva automatización</h1>

      {mutation.isError && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          Error al crear. Intenta de nuevo.
        </div>
      )}

      <div className="space-y-6">
        {/* Nombre */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Nombre interno *</label>
          <input value={name} onChange={(e) => setName(e.target.value)}
            placeholder="ej. Recuperación carrito — 3 pasos"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>

        {/* Trigger selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Tipo de disparador *</label>
          <button
            type="button"
            onClick={() => setShowTriggers((v) => !v)}
            className="w-full flex items-center justify-between p-3.5 rounded-xl border border-brand-500 bg-brand-50 transition-colors"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${selectedTrigger.badgeColor}`}>
                {selectedTrigger.badge}
              </span>
              <div className="text-left min-w-0">
                <p className="text-sm font-medium text-gray-900">{selectedTrigger.label}</p>
                <p className="text-xs text-gray-500 truncate">{selectedTrigger.description}</p>
              </div>
            </div>
            {showTriggers ? <ChevronUp size={16} className="text-gray-400 shrink-0" /> : <ChevronDown size={16} className="text-gray-400 shrink-0" />}
          </button>

          {showTriggers && (
            <div className="mt-2 border border-gray-200 rounded-xl overflow-hidden shadow-sm max-h-72 overflow-y-auto">
              {TRIGGERS.map((t) => (
                <label key={t.value}
                  className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors border-b border-gray-100 last:border-0 ${
                    triggerType === t.value ? "bg-brand-50" : "bg-white hover:bg-gray-50"
                  }`}>
                  <input type="radio" name="trigger" value={t.value} checked={triggerType === t.value}
                    onChange={() => { setTriggerType(t.value); setShowTriggers(false); }}
                    className="mt-0.5 accent-brand-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-medium text-gray-900">{t.label}</p>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${t.badgeColor}`}>{t.badge}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{t.description}</p>
                  </div>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Trigger-level config */}
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-5 space-y-4">
          <p className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
            <Clock size={14} className="text-brand-500" /> Configuración del disparador
          </p>

          {EVENT_TRIGGERS.has(triggerType) && (
            <TimerPicker label="Ventana de búsqueda"
              hint="El sistema buscará eventos dentro de este período. Generalmente 24–72 horas."
              value={lookbackValue} unit={lookbackUnit} units={LOOKBACK_UNITS}
              onValueChange={setLookbackValue} onUnitChange={(u) => setLookbackUnit(u as "horas" | "dias")} />
          )}
          {triggerType === "post_visit" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Enviar N días después de la última compra</label>
              <div className="flex items-center gap-2">
                <input type="number" min={1} value={postVisitDays}
                  onChange={(e) => setPostVisitDays(Math.max(1, Number(e.target.value)))}
                  className="w-28 border border-gray-300 rounded-lg px-3 py-2 text-sm text-center focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <span className="text-sm text-gray-500">días</span>
              </div>
            </div>
          )}
          {triggerType === "reactivation" && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Disparar si no hay compra en</label>
                <div className="flex items-center gap-2">
                  <input type="number" min={1} value={inactivityDays}
                    onChange={(e) => setInactivityDays(Math.max(1, Number(e.target.value)))}
                    className="w-24 border border-gray-300 rounded-lg px-3 py-2 text-sm text-center focus:outline-none focus:ring-2 focus:ring-brand-500" />
                  <span className="text-sm text-gray-500">días</span>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">No repetir por</label>
                <div className="flex items-center gap-2">
                  <input type="number" min={1} value={cooldownDays}
                    onChange={(e) => setCooldownDays(Math.max(1, Number(e.target.value)))}
                    className="w-24 border border-gray-300 rounded-lg px-3 py-2 text-sm text-center focus:outline-none focus:ring-2 focus:ring-brand-500" />
                  <span className="text-sm text-gray-500">días</span>
                </div>
              </div>
            </div>
          )}
          {triggerType === "abandoned_booking" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ventana máxima (horas)</label>
              <div className="flex items-center gap-2">
                <input type="number" min={1} value={bookingDelayMinutes}
                  onChange={(e) => setBookingDelayMinutes(Math.max(1, Number(e.target.value)))}
                  className="w-24 border border-gray-300 rounded-lg px-3 py-2 text-sm text-center focus:outline-none focus:ring-2 focus:ring-brand-500" />
                <span className="text-sm text-gray-500">horas hacia atrás</span>
              </div>
            </div>
          )}
        </div>

        {/* Multi-step builder */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-semibold text-gray-700">
              Pasos del flujo
              <span className="ml-2 text-xs font-normal text-gray-400">({steps.length} correo{steps.length !== 1 ? "s" : ""})</span>
            </p>
          </div>

          <div className="space-y-5 relative">
            {/* Vertical line connecting steps */}
            {steps.length > 1 && (
              <div className="absolute left-7 top-10 bottom-10 w-0.5 bg-gray-200 -z-10" />
            )}

            {steps.map((step, i) => (
              <StepCard
                key={i}
                stepNum={i + 1}
                total={steps.length}
                step={step}
                templates={templates}
                triggerType={triggerType}
                isFirst={i === 0}
                onChange={(s) => updateStep(i, s)}
                onRemove={() => removeStep(i)}
              />
            ))}
          </div>

          {/* Add step button */}
          <button
            type="button"
            onClick={addStep}
            className="mt-4 w-full py-3 border-2 border-dashed border-gray-300 rounded-xl text-sm text-gray-500 hover:border-brand-400 hover:text-brand-600 hover:bg-brand-50 transition-colors flex items-center justify-center gap-2"
          >
            <Plus size={14} /> Agregar otro correo al flujo
          </button>

          <div className="mt-3 flex items-start gap-2 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2.5">
            <Info size={13} className="text-blue-400 shrink-0 mt-0.5" />
            <p className="text-xs text-blue-700">
              Cada correo del flujo se envía a la misma persona con el delay configurado entre pasos.
              Si la condición del paso no se cumple (ej. ya compró), el flujo se detiene automáticamente.
            </p>
          </div>
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !isValid || !name}
          className="w-full py-2.5 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-60 transition-colors"
        >
          {mutation.isPending ? "Creando..." : `Crear automatización${steps.length > 1 ? ` (${steps.length} pasos)` : ""}`}
        </button>
      </div>
    </div>
  );
}
