"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";

interface VarDef {
  tag: string;
  description: string;
  example: string;
}

interface VarGroup {
  title: string;
  color: string;
  description: string;
  vars: VarDef[];
}

const GROUPS: VarGroup[] = [
  {
    title: "Contacto",
    color: "bg-blue-50 border-blue-200",
    description: "Datos del contacto al que se envía el email. Disponibles en todas las automatizaciones y campañas.",
    vars: [
      { tag: "{{ nombre }}",        description: "Nombre completo del contacto",                   example: "María González" },
      { tag: "{{ first_name }}",    description: "Primer nombre del contacto",                     example: "María" },
      { tag: "{{ email }}",         description: "Email del contacto",                             example: "maria@ejemplo.com" },
      { tag: "{{ orders_count }}", description: "Cantidad de pedidos realizados",                  example: "5" },
      { tag: "{{ total_spent }}",  description: "Total gastado en CLP",                            example: "245000" },
      { tag: "{{ ticket_medio }}", description: "Ticket promedio en CLP",                          example: "49000" },
      { tag: "{{ ultima_visita }}", description: "Fecha de la última compra",                      example: "2024-11-15" },
      { tag: "{{ shipping_city }}", description: "Ciudad de envío registrada",                     example: "Santiago" },
    ],
  },
  {
    title: "Carrito abandonado",
    color: "bg-green-50 border-green-200",
    description: "Variables disponibles en automatizaciones de tipo \"Carrito abandonado\".",
    vars: [
      { tag: "{{ first_name }}",              description: "Nombre del comprador",                example: "Juan" },
      { tag: "{{ cart_total }}",              description: "Total del carrito formateado",         example: "$32.990" },
      { tag: "{{ first_product }}",           description: "Nombre del primer producto",          example: "Pack Mi Primer Taladro" },
      { tag: "{{ cart_url }}",                description: "Enlace directo al carrito",           example: "https://happylapiz.cl/cart/abc" },
      { tag: "{{ event.extra.checkout_url }}", description: "URL de checkout (compatible Klaviyo)", example: "https://happylapiz.cl/checkout/xyz" },
    ],
  },
  {
    title: "Pedidos Shopify",
    color: "bg-purple-50 border-purple-200",
    description: "Variables para automatizaciones de pedidos: compra realizada, enviado, entregado, cancelado.",
    vars: [
      { tag: "{{ order_number }}",    description: "Número de pedido",               example: "#1042" },
      { tag: "{{ order_total }}",     description: "Total del pedido formateado",    example: "$58.000" },
      { tag: "{{ first_product }}",   description: "Primer producto del pedido",     example: "Pack Científico Explorador" },
      { tag: "{{ tracking_number }}", description: "Número de seguimiento del envío", example: "CL123456789" },
      { tag: "{{ first_name }}",      description: "Nombre del comprador",           example: "Sofía" },
    ],
  },
  {
    title: "Desuscripción",
    color: "bg-gray-50 border-gray-200",
    description: "Tag especial para el enlace de desuscripción. Es reemplazado automáticamente por la URL personalizada del contacto.",
    vars: [
      { tag: "{% unsubscribe %}",    description: "Enlace de desuscripción personalizado por contacto", example: "https://happylapiz.cl/unsub/TOKEN" },
    ],
  },
];

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      onClick={copy}
      className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
      title="Copiar"
    >
      {copied ? <Check size={13} className="text-green-500" /> : <Copy size={13} />}
    </button>
  );
}

export default function VariablesPage() {
  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Variables de plantilla</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Códigos que puedes insertar en tus plantillas de email. Se reemplazan automáticamente con los datos del contacto al momento del envío.
        </p>
      </div>

      <div className="space-y-6">
        {GROUPS.map((group) => (
          <div key={group.title} className={`border rounded-xl overflow-hidden ${group.color}`}>
            <div className="px-5 py-4 border-b border-inherit">
              <h2 className="font-semibold text-gray-900">{group.title}</h2>
              <p className="text-sm text-gray-500 mt-0.5">{group.description}</p>
            </div>
            <div className="divide-y divide-inherit">
              {group.vars.map((v) => (
                <div key={v.tag} className="flex items-center gap-4 px-5 py-3 bg-white/60">
                  <div className="flex items-center gap-1 shrink-0">
                    <code className="font-mono text-sm bg-white border border-gray-200 text-brand-700 px-2 py-1 rounded-md">
                      {v.tag}
                    </code>
                    <CopyButton text={v.tag} />
                  </div>
                  <p className="text-sm text-gray-600 flex-1">{v.description}</p>
                  <p className="text-xs text-gray-400 font-mono shrink-0 hidden sm:block">
                    ej: <span className="text-gray-500">{v.example}</span>
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 bg-yellow-50 border border-yellow-200 rounded-xl px-5 py-4">
        <p className="text-sm font-semibold text-yellow-800 mb-1">Variables no reconocidas</p>
        <p className="text-sm text-yellow-700">
          Si una plantilla usa una variable que no está definida para ese tipo de automatización,
          el tag se reemplaza por texto vacío en lugar de fallar el envío.
        </p>
      </div>
    </div>
  );
}
