"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { automationsApi, templatesApi, api } from "@/lib/api";
import { Template, AutomationTrigger, AutomationStep } from "@/lib/types";
import { ArrowLeft, Clock, Info, Plus, Trash2, GitBranch, ChevronDown, ChevronUp, ShieldOff, FlaskConical, X, Tag, ShoppingCart, MapPin } from "lucide-react";

interface CouponCampaign { id: number; name: string; discount_type: string; discount_value: number; prefix: string; }
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

// Triggers where location-based delay makes sense (have shipping address in payload)
const LOCATION_DELAY_TRIGGERS = new Set<AutomationTrigger>([
  "placed_order", "ordered_product", "fulfilled_order", "fulfilled_partial_order",
  "confirmed_shipment", "delivered_shipment", "marked_out_for_delivery",
  "cancelled_order", "refunded_order",
]);

// Triggers where filtering by order count makes sense
const ORDER_COUNT_FILTERABLE = new Set<AutomationTrigger>([
  "placed_order", "ordered_product", "fulfilled_order", "fulfilled_partial_order",
  "confirmed_shipment", "delivered_shipment", "marked_out_for_delivery",
  "cancelled_order", "refunded_order", "abandoned_cart", "post_visit", "reactivation",
]);

// Exit conditions: checked BEFORE sending each step from step 2 onwards.
// If the condition fails, the contact exits the flow immediately.
const EXIT_CONDITIONS: Record<string, { value: string; label: string; hint: string }[]> = {
  abandoned_cart: [
    { value: "not_purchased", label: "Solo si aún NO ha comprado (recomendado)", hint: "" },
    { value: "always",        label: "Siempre, aunque ya haya comprado",         hint: "" },
  ],
  placed_order: [
    { value: "always", label: "Siempre", hint: "" },
  ],
  _default: [
    { value: "not_purchased", label: "Solo si aún NO ha comprado (recomendado)", hint: "" },
    { value: "always",        label: "Siempre, aunque ya haya comprado",         hint: "" },
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
const VARIANT_COLORS = [
  { bg: "bg-purple-100", text: "text-purple-700", border: "border-purple-300" },
  { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-300" },
  { bg: "bg-teal-100",   text: "text-teal-700",   border: "border-teal-300" },
  { bg: "bg-pink-100",   text: "text-pink-700",   border: "border-pink-300" },
];

interface VariantState {
  variant: string;       // "A", "B", "C", "D"
  subject: string;
  templateId: number | "";
  weight: number;
}

interface LocationDelayRule {
  id: string;
  label: string;
  cities: string;   // comma-separated, empty = default/fallback
  delay: number;
  unit: TimeUnit;
  is_default: boolean;
}

interface StepState {
  delayValue: number;
  delayUnit: TimeUnit;
  templateId: number | "";
  subject: string;
  previewText: string;
  condition: string;
  variants: VariantState[];  // empty = no A/B test
}

function VariantEditor({
  variants,
  templates,
  onChange,
}: {
  variants: VariantState[];
  templates: Template[];
  onChange: (v: VariantState[]) => void;
}) {
  const totalWeight = variants.reduce((s, v) => s + v.weight, 0);

  function addVariant() {
    const labels = ["A", "B", "C", "D"];
    const next = labels[variants.length] ?? String(variants.length + 1);
    const even = Math.floor(100 / (variants.length + 1));
    const updated = variants.map((v) => ({ ...v, weight: even }));
    onChange([...updated, { variant: next, subject: "", templateId: "", weight: even }]);
  }

  function removeVariant(idx: number) {
    if (variants.length <= 2) return;
    const updated = variants.filter((_, i) => i !== idx);
    const even = Math.floor(100 / updated.length);
    onChange(updated.map((v) => ({ ...v, weight: even })));
  }

  function updateVariant(idx: number, patch: Partial<VariantState>) {
    onChange(variants.map((v, i) => (i === idx ? { ...v, ...patch } : v)));
  }

  return (
    <div className="space-y-3">
      {variants.map((v, i) => {
        const col = VARIANT_COLORS[i % VARIANT_COLORS.length];
        return (
          <div key={v.variant} className={`rounded-lg border ${col.border} bg-white p-3 space-y-2`}>
            <div className="flex items-center justify-between">
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${col.bg} ${col.text}`}>
                Variante {v.variant}
              </span>
              <div className="flex items-center gap-2">
                <label className="text-xs text-gray-500">Peso</label>
                <input
                  type="number" min={1} max={100} value={v.weight}
                  onChange={(e) => updateVariant(i, { weight: Math.max(1, Number(e.target.value)) })}
                  className="w-16 border border-gray-300 rounded px-2 py-1 text-xs text-center focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <span className="text-xs text-gray-400">%</span>
                {variants.length > 2 && (
                  <button onClick={() => removeVariant(i)} className="p-1 text-gray-400 hover:text-red-500 rounded transition-colors">
                    <X size={12} />
                  </button>
                )}
              </div>
            </div>
            <select
              value={v.templateId}
              onChange={(e) => updateVariant(i, { templateId: Number(e.target.value) || "" })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="">Seleccionar plantilla...</option>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <input
              value={v.subject}
              onChange={(e) => updateVariant(i, { subject: e.target.value })}
              placeholder={`Asunto variante ${v.variant}...`}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        );
      })}

      <div className="flex items-center justify-between">
        {variants.length < 4 && (
          <button
            type="button"
            onClick={addVariant}
            className="text-xs text-brand-600 hover:text-brand-700 flex items-center gap-1 font-medium"
          >
            <Plus size={12} /> Agregar variante
          </button>
        )}
        <span className={`text-xs ml-auto font-medium ${Math.abs(totalWeight - 100) > 2 ? "text-red-500" : "text-gray-400"}`}>
          Total: {totalWeight}% {Math.abs(totalWeight - 100) > 2 ? "(debe sumar 100)" : "✓"}
        </span>
      </div>
    </div>
  );
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
  const condOptions = EXIT_CONDITIONS[triggerType] ?? EXIT_CONDITIONS["_default"];
  const abEnabled = step.variants.length >= 2;

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
          {abEnabled && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium flex items-center gap-1">
              <FlaskConical size={10} /> A/B
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            title={abEnabled ? "Desactivar A/B test" : "Activar A/B test"}
            onClick={() => {
              if (abEnabled) {
                // Disable: restore from variant A (or clear)
                const a = step.variants[0];
                onChange({ ...step, templateId: a?.templateId ?? "", subject: a?.subject ?? "", variants: [] });
              } else {
                // Enable: seed from current template/subject
                onChange({
                  ...step,
                  variants: [
                    { variant: "A", subject: step.subject, templateId: step.templateId, weight: 50 },
                    { variant: "B", subject: "",           templateId: step.templateId, weight: 50 },
                  ],
                });
              }
            }}
            className={`p-1.5 rounded-lg transition-colors ${abEnabled ? "bg-purple-100 text-purple-700 hover:bg-purple-200" : "text-gray-400 hover:text-purple-600 hover:bg-purple-50"}`}
          >
            <FlaskConical size={14} />
          </button>
          {total > 1 && (
            <button onClick={onRemove} className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">
              <Trash2 size={14} />
            </button>
          )}
        </div>
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

        {/* Send condition (only from step 2 onwards) */}
        {!isFirst && (
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-3 space-y-2">
            <label className="block text-xs font-semibold flex items-center gap-1.5 text-gray-600">
              <GitBranch size={12} />
              ¿Enviar este correo solo si...?
            </label>
            <select value={step.condition} onChange={(e) => onChange({ ...step, condition: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
              {condOptions.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            {step.condition === "always" ? (
              <p className="text-xs text-gray-500">
                Este correo se enviará aunque el contacto ya haya comprado.
              </p>
            ) : (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
                Si el contacto ya compró cuando llegue el momento de enviar este correo, <strong>no lo recibirá</strong> y saldrá del flujo.
              </p>
            )}
          </div>
        )}

        {/* Template + Subject (or A/B variants) */}
        {abEnabled ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1.5">
              <FlaskConical size={13} className="text-purple-500" />
              Variantes A/B
            </label>
            <VariantEditor
              variants={step.variants}
              templates={templates}
              onChange={(v) => onChange({ ...step, variants: v })}
            />
          </div>
        ) : (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Plantilla de email *</label>
              <select value={step.templateId} onChange={(e) => onChange({ ...step, templateId: Number(e.target.value) || "" })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
                <option value="">Seleccionar plantilla...</option>
                {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Asunto del email *</label>
              <input value={step.subject} onChange={(e) => onChange({ ...step, subject: e.target.value })}
                placeholder='ej. ¡Tu carrito te está esperando, {{ first_name }}!'
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Preview text <span className="text-gray-400 font-normal">(opcional)</span></label>
              <input value={step.previewText} onChange={(e) => onChange({ ...step, previewText: e.target.value })}
                placeholder='ej. Tu carrito tiene productos que te esperan...'
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              <p className="text-xs text-gray-400 mt-1">Texto gris que aparece bajo el asunto en el inbox.</p>
            </div>
          </>
        )}
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
    { delayValue: 1, delayUnit: "horas", templateId: "", subject: "", previewText: "", condition: "not_recovered", variants: [] },
  ]);

  // Lookback (trigger-level config, only for event triggers)
  const [lookbackValue, setLookbackValue] = useState(24);
  const [lookbackUnit, setLookbackUnit] = useState<"horas" | "dias">("horas");

  // Internal trigger configs
  const [inactivityDays, setInactivityDays] = useState(90);
  const [cooldownDays, setCooldownDays] = useState(180);
  const [postVisitDays, setPostVisitDays] = useState(3);
  const [bookingDelayMinutes, setBookingDelayMinutes] = useState(5);

  // Order count filter
  const [orderCountPreset, setOrderCountPreset] = useState("none");
  const [orderCountCustom, setOrderCountCustom] = useState(1);

  // Location-based delay
  const [locationDelayEnabled, setLocationDelayEnabled] = useState(false);
  const [locationDelayRules, setLocationDelayRules] = useState<LocationDelayRule[]>([
    { id: "1", label: "Región Metropolitana", cities: "", delay: 2, unit: "dias", is_default: false },
    { id: "2", label: "Regiones",             cities: "", delay: 7, unit: "dias", is_default: true },
  ]);

  function buildOrderCountFilter(): Record<string, unknown> | undefined {
    const presets: Record<string, { operator: string; value: number }> = {
      eq_1: { operator: "eq", value: 1 },
      eq_2: { operator: "eq", value: 2 },
      eq_3: { operator: "eq", value: 3 },
      gte_2: { operator: "gte", value: 2 },
      gte_3: { operator: "gte", value: 3 },
      lte_2: { operator: "lte", value: 2 },
    };
    if (orderCountPreset === "none") return undefined;
    if (presets[orderCountPreset]) return presets[orderCountPreset];
    if (orderCountPreset === "eq_custom") return { operator: "eq", value: orderCountCustom };
    if (orderCountPreset === "gte_custom") return { operator: "gte", value: orderCountCustom };
    if (orderCountPreset === "lte_custom") return { operator: "lte", value: orderCountCustom };
    return undefined;
  }

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

  const { data: couponCampaigns = [] } = useQuery<CouponCampaign[]>({
    queryKey: ["coupon-campaigns"],
    queryFn: () => api.get("/coupons/campaigns").then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  const [couponCampaignId, setCouponCampaignId] = useState<number | null>(null);

  const selectedTrigger = TRIGGERS.find((t) => t.value === triggerType)!;

  function addStep() {
    const defaultCondition = (EXIT_CONDITIONS[triggerType] ?? EXIT_CONDITIONS["_default"])[0].value;
    setSteps((prev) => [
      ...prev,
      { delayValue: 24, delayUnit: "horas", templateId: "", subject: "", previewText: "", condition: defaultCondition, variants: [] },
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
      let triggerConfig: Record<string, unknown> = {};

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

      // Attach order count filter if configured
      const orderFilter = buildOrderCountFilter();
      if (orderFilter && ORDER_COUNT_FILTERABLE.has(triggerType)) {
        triggerConfig.order_count_filter = orderFilter;
      }

      // Attach location delay rules if configured
      if (locationDelayEnabled && LOCATION_DELAY_TRIGGERS.has(triggerType) && locationDelayRules.length > 0) {
        triggerConfig.location_delay_rules = locationDelayRules.map((r) => ({
          label: r.label,
          cities: r.is_default ? [] : r.cities.split(",").map((c) => c.trim()).filter(Boolean),
          delay_hours: toHours(r.delay, r.unit),
          is_default: r.is_default,
        }));
      }

      const stepsPayload: AutomationStep[] = steps.map((s, i) => {
        const base = {
          step: i + 1,
          delay_hours: toHours(s.delayValue, s.delayUnit),
          condition: i === 0 ? null : (s.condition as AutomationStep["condition"]),
        };
        if (s.variants.length >= 2) {
          return {
            ...base,
            variants: s.variants.map((v) => ({
              variant: v.variant,
              subject: v.subject,
              template_id: Number(v.templateId),
              weight: v.weight,
            })),
            // Legacy fallback from variant A
            template_id: Number(s.variants[0].templateId),
            subject: s.variants[0].subject,
          };
        }
        return { ...base, template_id: Number(s.templateId), subject: s.subject, preview_text: s.previewText || undefined };
      });

      return automationsApi.create({
        name,
        trigger_type: triggerType,
        trigger_config: triggerConfig,
        steps: stepsPayload,
        // Keep legacy fields from step 1 for backwards compat
        template_id: Number(steps[0].templateId) || undefined,
        subject: steps[0].subject || undefined,
        coupon_campaign_id: couponCampaignId ?? undefined,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automations"] });
      router.push("/automations");
    },
  });

  const isValid = name && steps.every((s) => {
    if (s.variants.length >= 2) {
      return s.variants.every((v) => v.templateId && v.subject);
    }
    return s.templateId && s.subject;
  });

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

          {/* Location-based delay — shown for Shopify triggers with shipping address */}
          {LOCATION_DELAY_TRIGGERS.has(triggerType) && (
            <div>
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={locationDelayEnabled}
                  onChange={(e) => setLocationDelayEnabled(e.target.checked)}
                  className="accent-brand-600 w-4 h-4"
                />
                <span className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
                  <MapPin size={13} className="text-gray-400" />
                  Retraso según zona de envío (comuna)
                </span>
              </label>

              {locationDelayEnabled && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs text-gray-500">
                    El delay del primer paso se reemplaza según la comuna de envío. La regla «Por defecto» se aplica cuando ninguna otra coincide.
                  </p>

                  {locationDelayRules.map((rule, idx) => (
                    <div key={rule.id} className="border border-gray-200 rounded-lg p-3 bg-white space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <input
                          value={rule.label}
                          onChange={(e) => setLocationDelayRules((prev) =>
                            prev.map((r, i) => i === idx ? { ...r, label: e.target.value } : r)
                          )}
                          placeholder="ej. Región Metropolitana"
                          className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                        />
                        <label className="flex items-center gap-1 text-xs text-gray-500 shrink-0 cursor-pointer">
                          <input
                            type="radio"
                            name="location_default"
                            checked={rule.is_default}
                            onChange={() => setLocationDelayRules((prev) =>
                              prev.map((r, i) => ({ ...r, is_default: i === idx }))
                            )}
                            className="accent-brand-600"
                          />
                          Por defecto
                        </label>
                        {locationDelayRules.length > 1 && (
                          <button
                            type="button"
                            onClick={() => setLocationDelayRules((prev) => prev.filter((_, i) => i !== idx))}
                            className="p-1 text-gray-400 hover:text-red-500 rounded transition-colors"
                          >
                            <X size={13} />
                          </button>
                        )}
                      </div>

                      {!rule.is_default && (
                        <input
                          value={rule.cities}
                          onChange={(e) => setLocationDelayRules((prev) =>
                            prev.map((r, i) => i === idx ? { ...r, cities: e.target.value } : r)
                          )}
                          placeholder="ej. Santiago, Providencia, Las Condes, Vitacura"
                          className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                        />
                      )}
                      {rule.is_default && (
                        <p className="text-xs text-gray-400 italic">Esta regla aplica cuando ninguna otra zona coincide.</p>
                      )}

                      <div className="flex gap-2">
                        <input
                          type="number" min={0} value={rule.delay}
                          onChange={(e) => setLocationDelayRules((prev) =>
                            prev.map((r, i) => i === idx ? { ...r, delay: Math.max(0, Number(e.target.value)) } : r)
                          )}
                          className="w-24 border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-center focus:outline-none focus:ring-2 focus:ring-brand-500"
                        />
                        <select
                          value={rule.unit}
                          onChange={(e) => setLocationDelayRules((prev) =>
                            prev.map((r, i) => i === idx ? { ...r, unit: e.target.value as TimeUnit } : r)
                          )}
                          className="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                        >
                          {TIME_UNITS.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
                        </select>
                      </div>
                    </div>
                  ))}

                  <button
                    type="button"
                    onClick={() => setLocationDelayRules((prev) => [
                      ...prev,
                      { id: String(Date.now()), label: "", cities: "", delay: 3, unit: "dias", is_default: false },
                    ])}
                    className="text-xs text-brand-600 hover:text-brand-700 flex items-center gap-1 font-medium mt-1"
                  >
                    <Plus size={12} /> Agregar zona
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Order count filter — shown for all purchase-related triggers */}
          {ORDER_COUNT_FILTERABLE.has(triggerType) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
                <ShoppingCart size={13} className="text-gray-400" />
                Filtro por número de compra del cliente
              </label>
              <select
                value={orderCountPreset}
                onChange={(e) => setOrderCountPreset(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="none">Sin filtro — todos los clientes</option>
                <optgroup label="Compras específicas">
                  <option value="eq_1">Solo primera compra (pedido #1)</option>
                  <option value="eq_2">Solo segunda compra (pedido #2)</option>
                  <option value="eq_3">Solo tercera compra (pedido #3)</option>
                  <option value="eq_custom">Número de compra exacto...</option>
                </optgroup>
                <optgroup label="Rango">
                  <option value="gte_2">Segunda compra o más (#2+)</option>
                  <option value="gte_3">Tercera compra o más (#3+)</option>
                  <option value="gte_custom">A partir de la compra #...</option>
                  <option value="lte_2">Hasta la segunda compra (#1–2)</option>
                  <option value="lte_custom">Hasta la compra #...</option>
                </optgroup>
              </select>

              {/* Custom value input */}
              {(orderCountPreset.endsWith("_custom")) && (
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-sm text-gray-600">
                    {orderCountPreset.startsWith("eq") ? "Pedido #" : orderCountPreset.startsWith("gte") ? "A partir del pedido #" : "Hasta el pedido #"}
                  </span>
                  <input
                    type="number" min={1} max={999} value={orderCountCustom}
                    onChange={(e) => setOrderCountCustom(Math.max(1, Number(e.target.value)))}
                    className="w-20 border border-gray-300 rounded-lg px-3 py-2 text-sm text-center focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              )}

              {/* Contextual hint */}
              {orderCountPreset !== "none" && (
                <div className="mt-2 text-xs rounded-lg px-3 py-2 border bg-blue-50 border-blue-100 text-blue-700">
                  {triggerType === "abandoned_cart"
                    ? <>Para carrito abandonado, el conteo refleja pedidos <strong>ya completados</strong> antes de este evento. «Primera compra» = clientes que nunca han comprado.</>
                    : <>Para pedidos de Shopify, el conteo incluye el pedido actual. «Primera compra» (#1) = este es su primer pedido histórico en la tienda.</>
                  }
                </div>
              )}
            </div>
          )}
        </div>

        {/* Campaña de cupones */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center gap-1.5">
            <Tag size={13} className="text-gray-400" /> Campaña de cupones (opcional)
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
            <div className="mt-2 bg-purple-50 border border-purple-100 rounded-lg px-3 py-2">
              <p className="text-xs text-purple-700">En tu plantilla usa <code className="bg-white px-1 rounded border border-purple-200">{"{{ coupon_code }}"}</code> para mostrar el código, o <code className="bg-white px-1 rounded border border-purple-200">{"{{ event.extra.checkout_url_with_coupon }}"}</code> para el link al carrito con el descuento aplicado.</p>
            </div>
          )}
          {couponCampaigns.length === 0 && (
            <p className="text-xs text-gray-400 mt-1">No hay campañas de cupones. <a href="/coupons" className="text-brand-600 underline">Crear una en Cupones →</a></p>
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

          <div className="mt-3 space-y-2">
            <div className="flex items-start gap-2 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2.5">
              <Info size={13} className="text-blue-400 shrink-0 mt-0.5" />
              <p className="text-xs text-blue-700">
                Cada correo se envía con el delay configurado desde el paso anterior. El timer empieza cuando el contacto entra al flujo.
              </p>
            </div>
            {steps.length > 1 && steps.slice(1).some((s) => s.condition !== "always") && (
              <div className="flex items-start gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-2.5">
                <ShieldOff size={13} className="text-green-600 shrink-0 mt-0.5" />
                <p className="text-xs text-green-700 font-medium">
                  Los correos con condición activa no se envían si el contacto ya compró — evita molestar a quien ya convirtió.
                </p>
              </div>
            )}
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
