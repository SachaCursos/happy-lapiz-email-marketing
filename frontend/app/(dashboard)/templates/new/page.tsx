"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/lib/api";
import { ArrowLeft, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TemplateBlockEditor, TemplateEditorSaveData } from "@/components/TemplateBlockEditor";

const VAR_GROUPS = [
  {
    label: "Contacto",
    color: "violet",
    vars: [
      { v: "{{ nombre }}", d: "Nombre completo del contacto" },
      { v: "{{ first_name }}", d: "Primer nombre" },
      { v: "{{ email }}", d: "Correo electrónico" },
      { v: "{{ orders_count }}", d: "Total de pedidos históricos" },
      { v: "{{ total_spent }}", d: "Total gastado (número, ej. 45000)" },
      { v: "{{ ticket_medio }}", d: "Ticket promedio por pedido" },
      { v: "{{ ultima_visita }}", d: "Fecha de última compra" },
      { v: "{{ shipping_city }}", d: "Ciudad de envío del contacto" },
    ],
  },
  {
    label: "Pedidos Shopify",
    color: "blue",
    vars: [
      { v: "{{ order_number }}", d: "Número de orden (ej. 1042)" },
      { v: "{{ order_total }}", d: "Total de la orden (ej. $12.990)" },
      { v: "{{ first_product }}", d: "Nombre del primer producto comprado" },
      { v: "{{ shipping_city }}", d: "Ciudad de envío de la orden" },
      { v: "{{ shipping_province }}", d: "Provincia/región de envío" },
      { v: "{{ tracking_number }}", d: "Número de seguimiento (solo pedidos despachados)" },
    ],
  },
  {
    label: "Carrito abandonado",
    color: "orange",
    vars: [
      { v: "{{ cart_total }}", d: "Total del carrito (ej. $8.990)" },
      { v: "{{ first_product }}", d: "Primer producto en el carrito" },
      { v: "{{ cart_url }}", d: "URL directa al carrito" },
      { v: "{{ event.extra.checkout_url }}", d: "URL del checkout abandonado" },
      { v: "{{ event.extra.checkout_url_with_coupon }}", d: "Checkout con cupón pre-aplicado (?discount=CODIGO)" },
    ],
  },
  {
    label: "Cupones",
    color: "green",
    vars: [
      { v: "{{ coupon_code }}", d: "Código de cupón generado para este contacto" },
      { v: "{{ event.extra.checkout_url_with_coupon }}", d: "URL carrito + cupón pre-aplicado (ej. ?discount=HL-XXXX)" },
    ],
  },
  {
    label: "Cross-sell",
    color: "pink",
    vars: [
      { v: "{{ recommended_products_html }}", d: "Grid HTML 2 columnas con productos recomendados" },
      { v: "{{ recommended_products }}", d: "Lista de dicts: [{title, url, image_url, price}]" },
    ],
  },
  {
    label: "Reserva HotBoat",
    color: "teal",
    vars: [
      { v: "{{ servicio }}", d: "Nombre del servicio/experiencia" },
      { v: "{{ fecha_reserva }}", d: "Fecha de la reserva" },
      { v: "{{ hora_reserva }}", d: "Hora de la reserva" },
      { v: "{{ personas }}", d: "Descripción de personas (ej. 2 adultos + 1 niño)" },
      { v: "{{ num_adultos }}", d: "Número de adultos" },
      { v: "{{ num_ninos }}", d: "Número de niños" },
      { v: "{{ ingreso_total }}", d: "Total de la reserva (ej. $45.000)" },
    ],
  },
  {
    label: "Jinja2",
    color: "gray",
    vars: [
      { v: "{{ variable or 'fallback' }}", d: "Valor por defecto si la variable está vacía" },
      { v: "{% if variable %}...{% endif %}", d: "Bloque condicional" },
      { v: "{% if x %}...{% else %}...{% endif %}", d: "Condicional con alternativa" },
      { v: "{{ variable | upper }}", d: "Convertir a mayúsculas" },
      { v: "{{ variable | lower }}", d: "Convertir a minúsculas" },
      { v: "{{ variable | title }}", d: "Primera letra de cada palabra en mayúscula" },
      { v: "{% unsubscribe %}", d: "URL de baja (se inyecta automáticamente)" },
    ],
  },
];

const COLOR_MAP: Record<string, { badge: string; header: string }> = {
  violet: { badge: "bg-violet-50 text-violet-700 border-violet-200", header: "text-violet-700" },
  blue:   { badge: "bg-blue-50 text-blue-700 border-blue-200",       header: "text-blue-700" },
  orange: { badge: "bg-orange-50 text-orange-700 border-orange-200", header: "text-orange-700" },
  green:  { badge: "bg-green-50 text-green-700 border-green-200",    header: "text-green-700" },
  pink:   { badge: "bg-pink-50 text-pink-700 border-pink-200",       header: "text-pink-700" },
  teal:   { badge: "bg-teal-50 text-teal-700 border-teal-200",       header: "text-teal-700" },
  gray:   { badge: "bg-gray-100 text-gray-600 border-gray-200",      header: "text-gray-600" },
};

function VariablesPanel() {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-gray-200 bg-gray-50">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 w-full px-6 py-2 text-xs font-semibold text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
      >
        {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        Variables disponibles en plantillas
      </button>
      {open && (
        <div className="px-6 pb-4 max-h-72 overflow-y-auto">
          <div className="grid grid-cols-2 gap-x-8 gap-y-0 pt-1">
            {VAR_GROUPS.map((group) => {
              const c = COLOR_MAP[group.color];
              return (
                <div key={group.label} className="mb-3">
                  <p className={`text-[10px] font-bold uppercase tracking-widest mb-1.5 ${c.header}`}>
                    {group.label}
                  </p>
                  <div className="space-y-1">
                    {group.vars.map((item) => (
                      <div key={item.v} className="flex items-start gap-2">
                        <code className={`text-[10px] border rounded px-1.5 py-0.5 shrink-0 font-mono whitespace-nowrap ${c.badge}`}>
                          {item.v}
                        </code>
                        <span className="text-[10px] text-gray-400 leading-tight mt-0.5">{item.d}</span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function NewTemplatePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [saved, setSaved] = useState(false);

  const mutation = useMutation({
    mutationFn: (data: TemplateEditorSaveData) =>
      templatesApi.create({
        name: data.name,
        html_content: data.html,
        json_blocks: data.blocks,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates"] });
      router.push("/templates");
    },
  });

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-3 px-6 py-3 border-b border-gray-200 bg-white shrink-0">
        <Link href="/templates" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft size={14} /> Volver
        </Link>
        <h1 className="text-sm font-semibold text-gray-900">Nueva plantilla</h1>
      </div>
      <VariablesPanel />
      {mutation.isError && (
        <div className="px-6 py-2 bg-red-50 border-b border-red-200 text-red-700 text-sm">
          Error al guardar. Intenta de nuevo.
        </div>
      )}
      <div className="flex-1 overflow-hidden">
        <TemplateBlockEditor
          onSave={(data) => mutation.mutate(data)}
          saving={mutation.isPending}
          saved={saved}
        />
      </div>
    </div>
  );
}
