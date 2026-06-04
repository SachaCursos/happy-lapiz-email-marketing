"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import { automationsApi, templatesApi } from "@/lib/api";
import { Template, AutomationTrigger } from "@/lib/types";
import { ArrowLeft, Info } from "lucide-react";
import Link from "next/link";

const TRIGGERS: { value: AutomationTrigger; label: string; description: string; badge: string; fields: JSX.Element }[] = [
  // ── Shopify: carrito y checkout ───────────────────────────────────────────
  { value: "abandoned_cart",           badge: "Shopify", label: "Carrito abandonado",                   description: "Checkout iniciado sin completar compra. Email se envía 1h después.", fields: <></> },
  { value: "checkout_started",         badge: "Shopify", label: "Checkout iniciado",                    description: "Alguien comenzó el proceso de pago en Shopify.", fields: <></> },
  { value: "added_to_cart",            badge: "Shopify", label: "Producto agregado al carrito",          description: "Alguien agregó un producto al carrito (sin necesariamente pagar).", fields: <></> },
  // ── Shopify: órdenes ─────────────────────────────────────────────────────
  { value: "placed_order",             badge: "Shopify", label: "Compra realizada (Placed Order)",       description: "Cliente completó una compra. Para gracias, confirmación o cross-sell.", fields: <></> },
  { value: "ordered_product",          badge: "Shopify", label: "Producto comprado (Ordered Product)",   description: "Se dispara por cada producto dentro de una orden.", fields: <></> },
  { value: "fulfilled_order",          badge: "Shopify", label: "Pedido enviado (Fulfilled Order)",      description: "El pedido fue procesado y enviado completamente.", fields: <></> },
  { value: "fulfilled_partial_order",  badge: "Shopify", label: "Envío parcial",                        description: "Parte del pedido fue enviada (fulfillment parcial).", fields: <></> },
  { value: "confirmed_shipment",       badge: "Shopify", label: "Envío confirmado con tracking",         description: "El fulfillment incluye un número de seguimiento.", fields: <></> },
  { value: "delivered_shipment",       badge: "Shopify", label: "Pedido entregado",                     description: "El transportista marcó el paquete como entregado.", fields: <></> },
  { value: "marked_out_for_delivery",  badge: "Shopify", label: "En camino (Out for Delivery)",          description: "El paquete está en reparto en este momento.", fields: <></> },
  { value: "cancelled_order",          badge: "Shopify", label: "Pedido cancelado",                     description: "Una orden fue cancelada en Shopify.", fields: <></> },
  { value: "refunded_order",           badge: "Shopify", label: "Pedido reembolsado",                   description: "Se procesó un reembolso. Útil para retener o pedir feedback.", fields: <></> },
  // ── Cupones ──────────────────────────────────────────────────────────────
  { value: "coupon_assigned",          badge: "Cupón",   label: "Cupón asignado",                       description: "Se generó un cupón dinámico para el contacto.", fields: <></> },
  { value: "coupon_used",              badge: "Cupón",   label: "Cupón usado",                          description: "El cliente usó un código de descuento al pagar.", fields: <></> },
  // ── Web tracking ─────────────────────────────────────────────────────────
  { value: "viewed_product",           badge: "Web",     label: "Producto visto",                       description: "El contacto vio un producto en happylapiz.cl. Pixel ya instalable en Shopify.", fields: <></> },
  { value: "active_on_site",           badge: "Web",     label: "Activo en el sitio",                   description: "El contacto estuvo activo en happylapiz.cl. Pixel ya instalable en Shopify.", fields: <></> },
  { value: "subscribed_to_back_in_stock", badge: "Web",  label: "Alerta de stock disponible",           description: "El cliente se suscribió a notificación cuando un producto vuelva a estar disponible.", fields: <></> },
  // ── Internos ─────────────────────────────────────────────────────────────
  { value: "welcome",                  badge: "Interno", label: "Bienvenida (nuevo suscriptor)",         description: "Nuevo contacto con opt-in activo. Para series de bienvenida.", fields: <></> },
  { value: "reactivation",             badge: "Interno", label: "Reactivación (cliente inactivo)",       description: "Sin compra en N días. Incluye cooldown para no repetir.", fields: <></> },
  { value: "post_visit",               badge: "Interno", label: "Seguimiento post-compra",               description: "N días después de la última compra. Para reseñas o cross-sell.", fields: <></> },
];

const TRIGGER_MAP = Object.fromEntries(TRIGGERS.map((t) => [t.value, t]));

function ConfigFields({
  type,
  config,
  onChange,
}: {
  type: AutomationTrigger;
  config: Record<string, number>;
  onChange: (key: string, value: number) => void;
}) {
  const field = (key: string, label: string, min = 1, defaultVal = 2) => (
    <div key={key}>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type="number"
        min={min}
        value={config[key] ?? defaultVal}
        onChange={(e) => onChange(key, Number(e.target.value))}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      />
    </div>
  );

  switch (type) {
    case "abandoned_booking":
      return <>{field("delay_hours", "Enviar después de (horas sin completar)", 1, 2)}</>;
    case "welcome":
      return <>{field("delay_hours", "Enviar después de (horas del registro, 0 = inmediato)", 0, 0)}</>;
    case "post_visit":
      return <>{field("delay_days", "Enviar N días después de la visita", 1, 3)}</>;
    case "reactivation":
      return (
        <>
          {field("inactivity_days", "Días sin visitar para disparar", 1, 90)}
          {field("cooldown_days", "Días de espera antes de volver a enviar", 1, 180)}
        </>
      );
    default:
      return null;
  }
}

export default function NewAutomationPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [triggerType, setTriggerType] = useState<AutomationTrigger>("abandoned_booking");
  const [subject, setSubject] = useState("");
  const [templateId, setTemplateId] = useState<number | "">("");
  const [config, setConfig] = useState<Record<string, number>>({
    delay_hours: 2,
    delay_days: 3,
    inactivity_days: 90,
    cooldown_days: 180,
  });

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  const mutation = useMutation({
    mutationFn: () => {
      const configForType: Record<string, number> = {};
      switch (triggerType) {
        case "abandoned_booking": configForType.delay_hours = config.delay_hours ?? 2; break;
        case "welcome": configForType.delay_hours = config.delay_hours ?? 0; break;
        case "post_visit": configForType.delay_days = config.delay_days ?? 3; break;
        case "reactivation":
          configForType.inactivity_days = config.inactivity_days ?? 90;
          configForType.cooldown_days = config.cooldown_days ?? 180;
          break;
      }
      return automationsApi.create({
        name,
        trigger_type: triggerType,
        trigger_config: configForType,
        template_id: Number(templateId),
        subject,
      });
    },
    onSuccess: () => router.push("/automations"),
  });

  const selectedTrigger = TRIGGER_MAP[triggerType];
  const isValid = name && subject && templateId;

  return (
    <div className="p-8 max-w-2xl">
      <Link
        href="/automations"
        className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6"
      >
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
            placeholder="ej. Bienvenida a nuevos clientes"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {/* Trigger */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Tipo de disparador *</label>
          <div className="space-y-2">
            {TRIGGERS.map((t) => (
              <label
                key={t.value}
                className={`flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-colors ${
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
                  className="mt-0.5 accent-brand-600"
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-900">{t.label}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${t.badge === "Shopify" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>{t.badge}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">{t.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Config */}
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-5 space-y-4">
          <p className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
            <Info size={14} className="text-gray-400" /> Configuración del disparador
          </p>
          <ConfigFields
            type={triggerType}
            config={config}
            onChange={(key, val) => setConfig((prev) => ({ ...prev, [key]: val }))}
          />
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
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>

        {/* Asunto */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Asunto del email *</label>
          <input
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="ej. ¡Tu aventura en HotBoat te espera!"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !isValid}
          className="w-full py-2.5 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
        >
          {mutation.isPending ? "Creando..." : "Crear automatización"}
        </button>
      </div>
    </div>
  );
}
