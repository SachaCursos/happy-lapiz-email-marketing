"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import { automationsApi, templatesApi } from "@/lib/api";
import { Template, AutomationTrigger } from "@/lib/types";
import { ArrowLeft, Clock, Info } from "lucide-react";
import Link from "next/link";

// ── Trigger definitions ────────────────────────────────────────────────────────
const TRIGGERS: {
  value: AutomationTrigger;
  label: string;
  description: string;
  badge: string;
  badgeColor: string;
}[] = [
  // Shopify: carrito y checkout
  { value: "abandoned_cart",           badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Carrito abandonado",                   description: "Checkout iniciado sin completar compra." },
  { value: "checkout_started",         badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Checkout iniciado",                    description: "Alguien comenzó el proceso de pago en Shopify." },
  { value: "added_to_cart",            badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Producto agregado al carrito",          description: "Alguien agregó un producto al carrito." },
  // Shopify: órdenes
  { value: "placed_order",             badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Compra realizada",                     description: "Cliente completó una compra. Para confirmación o cross-sell." },
  { value: "ordered_product",          badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Producto comprado",                    description: "Se dispara por cada producto dentro de una orden." },
  { value: "fulfilled_order",          badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Pedido enviado",                       description: "El pedido fue procesado y enviado completamente." },
  { value: "fulfilled_partial_order",  badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Envío parcial",                        description: "Parte del pedido fue enviada (fulfillment parcial)." },
  { value: "confirmed_shipment",       badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Envío con tracking confirmado",        description: "El fulfillment incluye un número de seguimiento." },
  { value: "delivered_shipment",       badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Pedido entregado",                     description: "El transportista marcó el paquete como entregado." },
  { value: "marked_out_for_delivery",  badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "En camino (Out for Delivery)",          description: "El paquete está en reparto en este momento." },
  { value: "cancelled_order",          badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Pedido cancelado",                     description: "Una orden fue cancelada en Shopify." },
  { value: "refunded_order",           badge: "Shopify",  badgeColor: "bg-green-100 text-green-700",  label: "Pedido reembolsado",                   description: "Se procesó un reembolso." },
  // Cupones
  { value: "coupon_assigned",          badge: "Cupón",    badgeColor: "bg-purple-100 text-purple-700", label: "Cupón asignado",                      description: "Se generó un cupón dinámico para el contacto." },
  { value: "coupon_used",              badge: "Cupón",    badgeColor: "bg-purple-100 text-purple-700", label: "Cupón usado",                         description: "El cliente usó un código de descuento al pagar." },
  // Web tracking
  { value: "viewed_product",           badge: "Web",      badgeColor: "bg-blue-100 text-blue-700",    label: "Producto visto",                       description: "El contacto vio un producto en happylapiz.cl." },
  { value: "active_on_site",           badge: "Web",      badgeColor: "bg-blue-100 text-blue-700",    label: "Activo en el sitio",                   description: "El contacto estuvo activo en happylapiz.cl." },
  { value: "subscribed_to_back_in_stock", badge: "Web",   badgeColor: "bg-blue-100 text-blue-700",    label: "Alerta de stock disponible",           description: "El cliente se suscribió a notificación cuando un producto vuelva." },
  // Internos
  { value: "welcome",                  badge: "Interno",  badgeColor: "bg-gray-100 text-gray-700",    label: "Bienvenida (nuevo suscriptor)",         description: "Nuevo contacto con opt-in activo." },
  { value: "reactivation",             badge: "Interno",  badgeColor: "bg-gray-100 text-gray-700",    label: "Reactivación (cliente inactivo)",       description: "Sin compra en N días." },
  { value: "post_visit",               badge: "Interno",  badgeColor: "bg-gray-100 text-gray-700",    label: "Seguimiento post-compra",               description: "N días después de la última compra." },
  { value: "abandoned_booking",        badge: "HotBoat",  badgeColor: "bg-orange-100 text-orange-700", label: "Reserva abandonada (HotBoat)",         description: "Reserva con pago pendiente sin completar." },
];

// Triggers that use delay_hours + lookback_hours (event-based Shopify)
const EVENT_TRIGGERS = new Set<AutomationTrigger>([
  "abandoned_cart", "checkout_started", "added_to_cart",
  "placed_order", "ordered_product", "fulfilled_order", "fulfilled_partial_order",
  "confirmed_shipment", "delivered_shipment", "marked_out_for_delivery",
  "cancelled_order", "refunded_order",
  "coupon_assigned", "coupon_used",
  "viewed_product", "active_on_site", "subscribed_to_back_in_stock",
  "welcome",
]);

type TimeUnit = "minutos" | "horas" | "dias";

function toHours(value: number, unit: TimeUnit): number {
  if (unit === "minutos") return value / 60;
  if (unit === "dias") return value * 24;
  return value;
}

// Defaults per trigger type
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

// ── Timer picker component ─────────────────────────────────────────────────────
function TimerPicker({
  label,
  hint,
  value,
  unit,
  units,
  onValueChange,
  onUnitChange,
}: {
  label: string;
  hint?: string;
  value: number;
  unit: string;
  units: { value: string; label: string }[];
  onValueChange: (v: number) => void;
  onUnitChange: (u: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
        <Clock size={13} className="text-gray-400" /> {label}
      </label>
      <div className="flex gap-2">
        <input
          type="number"
          min={0}
          value={value}
          onChange={(e) => onValueChange(Math.max(0, Number(e.target.value)))}
          className="w-28 border border-gray-300 rounded-lg px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-500 text-center"
        />
        <select
          value={unit}
          onChange={(e) => onUnitChange(e.target.value)}
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          {units.map((u) => (
            <option key={u.value} value={u.value}>{u.label}</option>
          ))}
        </select>
      </div>
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  );
}

// ── Number field ───────────────────────────────────────────────────────────────
function NumberField({
  label, hint, value, unit, min = 1, onChange,
}: {
  label: string; hint?: string; value: number; unit: string; min?: number; onChange: (v: number) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <div className="flex items-center gap-2">
        <input type="number" min={min} value={value}
          onChange={(e) => onChange(Math.max(min, Number(e.target.value)))}
          className="w-28 border border-gray-300 rounded-lg px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-brand-500 text-center" />
        <span className="text-sm text-gray-500">{unit}</span>
      </div>
      {hint && <p className="text-xs text-gray-400 mt-1">{hint}</p>}
    </div>
  );
}

const TIME_UNITS = [
  { value: "minutos", label: "minutos" },
  { value: "horas",   label: "horas" },
  { value: "dias",    label: "días" },
];
const LOOKBACK_UNITS = [
  { value: "horas", label: "horas" },
  { value: "dias",  label: "días" },
];

export default function NewAutomationPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [triggerType, setTriggerType] = useState<AutomationTrigger>("abandoned_cart");
  const [subject, setSubject] = useState("");
  const [templateId, setTemplateId] = useState<number | "">("");

  // Delay timer state
  const [delayValue, setDelayValue] = useState(1);
  const [delayUnit, setDelayUnit] = useState<TimeUnit>("horas");

  // Lookback window state (for event-based triggers)
  const [lookbackValue, setLookbackValue] = useState(24);
  const [lookbackUnit, setLookbackUnit] = useState<"horas" | "dias">("horas");

  // Inactivity/cooldown (reactivation)
  const [inactivityDays, setInactivityDays] = useState(90);
  const [cooldownDays, setCooldownDays] = useState(180);

  // Post-visit delay
  const [postVisitDays, setPostVisitDays] = useState(3);

  // Abandoned booking delay (in minutes)
  const [bookingDelayMinutes, setBookingDelayMinutes] = useState(5);

  // Reset defaults when trigger type changes
  useEffect(() => {
    const def = TRIGGER_DEFAULTS[triggerType];
    if (def) {
      setDelayValue(def.delay);
      setDelayUnit(def.unit);
      setLookbackValue(def.lookback);
      setLookbackUnit(def.lookbackUnit as "horas" | "dias");
    }
  }, [triggerType]);

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
    staleTime: 5 * 60_000,
  });

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
          delay_hours: toHours(delayValue, delayUnit),
          lookback_hours: toHours(lookbackValue, lookbackUnit as TimeUnit),
        };
      }

      return automationsApi.create({
        name,
        trigger_type: triggerType,
        trigger_config: triggerConfig,
        template_id: Number(templateId),
        subject,
      });
    },
    onSuccess: () => router.push("/automations"),
  });

  const isValid = name && subject && templateId;

  // Summary label for the delay
  function delayLabel(): string {
    if (triggerType === "reactivation") {
      return `Sin compra en ${inactivityDays} días → envío inmediato`;
    }
    if (triggerType === "post_visit") {
      return `${postVisitDays} día${postVisitDays !== 1 ? "s" : ""} después de la última compra`;
    }
    if (triggerType === "abandoned_booking") {
      return `${bookingDelayMinutes} minuto${bookingDelayMinutes !== 1 ? "s" : ""} después del evento`;
    }
    const hours = toHours(delayValue, delayUnit);
    if (hours === 0) return "Se envía inmediatamente al ocurrir el evento";
    return `Se envía ${delayValue} ${delayUnit} después del evento`;
  }

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
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ej. Recuperación carrito abandonado"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {/* Trigger */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Tipo de disparador *</label>
          <div className="space-y-1.5">
            {TRIGGERS.map((t) => (
              <label
                key={t.value}
                className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-colors ${
                  triggerType === t.value
                    ? "border-brand-500 bg-brand-50"
                    : "border-gray-200 bg-white hover:border-gray-300"
                }`}
              >
                <input
                  type="radio"
                  name="trigger"
                  value={t.value}
                  checked={triggerType === t.value}
                  onChange={() => setTriggerType(t.value)}
                  className="mt-0.5 accent-brand-600 shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-medium text-gray-900">{t.label}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${t.badgeColor}`}>{t.badge}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{t.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Config del temporizador */}
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-5 space-y-5">
          <p className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
            <Clock size={14} className="text-brand-500" /> Temporizador del envío
          </p>

          {/* EVENT_TRIGGERS: delay_hours + lookback_hours */}
          {EVENT_TRIGGERS.has(triggerType) && (
            <>
              <TimerPicker
                label="Demora del envío"
                hint={delayValue === 0 && delayUnit === "horas" ? "El email se enviará inmediatamente cuando ocurra el evento." : undefined}
                value={delayValue}
                unit={delayUnit}
                units={TIME_UNITS}
                onValueChange={setDelayValue}
                onUnitChange={(u) => setDelayUnit(u as TimeUnit)}
              />
              <TimerPicker
                label="Ventana de búsqueda"
                hint="El sistema buscará eventos ocurridos dentro de este período. Auméntalo si necesitas cubrir periodos más largos."
                value={lookbackValue}
                unit={lookbackUnit}
                units={LOOKBACK_UNITS}
                onValueChange={setLookbackValue}
                onUnitChange={(u) => setLookbackUnit(u as "horas" | "dias")}
              />
            </>
          )}

          {/* Post visit: delay_days */}
          {triggerType === "post_visit" && (
            <NumberField
              label="Enviar N días después de la última compra"
              value={postVisitDays}
              unit="días"
              min={1}
              onChange={setPostVisitDays}
            />
          )}

          {/* Reactivation: inactivity + cooldown */}
          {triggerType === "reactivation" && (
            <>
              <NumberField
                label="Disparar si no hay compra en"
                value={inactivityDays}
                unit="días"
                min={1}
                onChange={setInactivityDays}
              />
              <NumberField
                label="No volver a enviar por"
                hint="Tiempo de espera antes de repetir la automatización al mismo contacto."
                value={cooldownDays}
                unit="días"
                min={1}
                onChange={setCooldownDays}
              />
            </>
          )}

          {/* Abandoned booking: delay_minutes */}
          {triggerType === "abandoned_booking" && (
            <NumberField
              label="Enviar después de"
              value={bookingDelayMinutes}
              unit="minutos sin completar el pago"
              min={1}
              onChange={setBookingDelayMinutes}
            />
          )}

          {/* Summary */}
          <div className="flex items-start gap-2 bg-white border border-brand-100 rounded-lg px-3 py-2.5">
            <Info size={13} className="text-brand-400 shrink-0 mt-0.5" />
            <p className="text-xs text-brand-700">{delayLabel()}</p>
          </div>
        </div>

        {/* Plantilla */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Plantilla de email *</label>
          <select
            value={templateId}
            onChange={(e) => setTemplateId(Number(e.target.value) || "")}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
          >
            <option value="">Seleccionar plantilla...</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>

        {/* Asunto */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Asunto del email *</label>
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="ej. ¡Tu carrito te está esperando, {{ nombre }}!"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <p className="text-xs text-gray-400 mt-1">Puedes usar {"{{ nombre }}"} para personalizar</p>
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !isValid}
          className="w-full py-2.5 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-60 transition-colors"
        >
          {mutation.isPending ? "Creando..." : "Crear automatización"}
        </button>
      </div>
    </div>
  );
}
