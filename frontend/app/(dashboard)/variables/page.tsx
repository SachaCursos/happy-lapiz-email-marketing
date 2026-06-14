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
      { tag: "{{ nombre }}",         description: "Nombre completo del contacto",             example: "María González" },
      { tag: "{{ first_name }}",     description: "Primer nombre del contacto",               example: "María" },
      { tag: "{{ email }}",          description: "Email del contacto",                       example: "maria@ejemplo.com" },
      { tag: "{{ orders_count }}",   description: "Cantidad de pedidos realizados",           example: "5" },
      { tag: "{{ total_spent }}",    description: "Total gastado en CLP",                     example: "245000" },
      { tag: "{{ ticket_medio }}",   description: "Ticket promedio en CLP",                   example: "49000" },
      { tag: "{{ ultima_visita }}",  description: "Fecha de la última visita/compra",         example: "2024-11-15" },
      { tag: "{{ shipping_city }}",  description: "Ciudad de envío registrada",               example: "Santiago" },
      { tag: "{{ shipping_province }}", description: "Región de envío registrada",            example: "Región Metropolitana" },
      { tag: "{{ smile_points }}",   description: "Puntos de fidelidad (Smile.io)",           example: "320" },
    ],
  },
  {
    title: "Campos personalizados (formularios)",
    color: "bg-pink-50 border-pink-200",
    description: "Datos capturados en formularios de Happy Lápiz (regalo, cumpleaños, etc.). Se guardan en custom_fields del contacto y están disponibles en automatizaciones de cumpleaños y post-formulario.",
    vars: [
      { tag: "{{ nombre_regalado }}",      description: "Nombre del niño/a que recibirá el regalo",          example: "Matías" },
      { tag: "{{ relacion }}",             description: "Relación entre quien regala y el regalado",         example: "hijo" },
      { tag: "{{ fecha_nacimiento }}",     description: "Fecha de nacimiento del niño/a (YYYY-MM-DD)",       example: "2019-06-15" },
      { tag: "{{ dias_para_cumpleanos }}", description: "Días que faltan para el cumpleaños (automatización)", example: "30" },
      { tag: "{{ fecha_cumpleanos }}",     description: "Fecha exacta del próximo cumpleaños",               example: "2026-06-15" },
      { tag: "{{ custom_fields.nombre_regalado }}", description: "Acceso directo al campo personalizado (forma alternativa)", example: "Matías" },
      { tag: "{{ custom_fields.relacion }}",        description: "Forma alternativa de acceder a la relación",              example: "hijo" },
    ],
  },
  {
    title: "Carrito abandonado",
    color: "bg-orange-50 border-orange-200",
    description: "Variables disponibles en automatizaciones de tipo \"Carrito abandonado\" y \"Checkout iniciado\".",
    vars: [
      { tag: "{{ first_name }}",                description: "Nombre del comprador",                        example: "Juan" },
      { tag: "{{ cart_total }}",                description: "Total del carrito formateado",                 example: "$32.990" },
      { tag: "{{ first_product }}",             description: "Nombre del primer producto",                  example: "Pack Mi Primer Taladro" },
      { tag: "{{ cart_url }}",                  description: "Enlace directo al carrito",                   example: "https://happylapiz.cl/cart/abc" },
      { tag: "{{ event.extra.checkout_url }}", description: "URL de checkout sin cupón",                    example: "https://happylapiz.cl/checkouts/abc123" },
      { tag: "{{ event.extra.checkout_url_with_coupon }}", description: "⭐ URL de checkout con cupón ya aplicado — usar esta para botones CTA cuando la automatización tiene cupón configurado", example: "https://happylapiz.cl/checkouts/abc123?discount=BIENVENIDA10" },
      { tag: "{{ coupon_code }}",               description: "Solo el código del cupón (para mostrarlo en texto: 'Usa el código X')", example: "BIENVENIDA10" },
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
    title: "Cross-sell",
    color: "bg-green-50 border-green-200",
    description: "Variables para emails de recomendación de productos. El motor busca productos relacionados según las compras anteriores del contacto.",
    vars: [
      { tag: "{{ recommended_products_html }}", description: "Grid HTML listo (2 columnas, imagen + nombre + precio + botón). Insertar tal cual.", example: "<tabla con productos recomendados>" },
      { tag: "{{ recommended_products }}",      description: "Lista de dicts para render manual: [{title, url, image_url, price}]", example: "[{title: 'Pack...', price: 29990}]" },
      { tag: "{{ first_product }}",             description: "Nombre del primer producto recomendado (para el asunto del email)", example: "Pack Mi Primer Taladro" },
    ],
  },
  {
    title: "Cupones",
    color: "bg-yellow-50 border-yellow-200",
    description: "Variables de descuento. Se asignan automáticamente cuando la automatización tiene una campaña de cupones configurada.",
    vars: [
      { tag: "{{ coupon_code }}",    description: "Código de descuento asignado al contacto",   example: "CUMPLE-A8K2" },
      { tag: "{{ coupon_amount }}",  description: "Valor del descuento (% o monto fijo)",       example: "15%" },
      { tag: "{{ coupon_expiry }}",  description: "Fecha de vencimiento del cupón",             example: "2026-07-15" },
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

const JINJA2_EXAMPLES = [
  {
    title: "Botón de carrito abandonado con cupón",
    description: "Usar checkout_url_with_coupon si hay cupón, y cart_url como fallback si no.",
    code: `<a href="{{ event.extra.checkout_url_with_coupon or cart_url }}"
   style="background:#682ae7;color:#fff;padding:14px 32px;border-radius:30px;text-decoration:none;font-weight:700;">
  Volver al carrito{% if coupon_code %} — {{ coupon_code }}{% endif %}
</a>`,
  },
  {
    title: "Condicional simple",
    description: "Mostrar algo solo si la variable tiene valor.",
    code: `{% if first_name %}Hola {{ first_name }}{% else %}Hola{% endif %}`,
  },
  {
    title: "Condicional con datos del contacto",
    description: "Personalizar según cantidad de pedidos.",
    code: `{% if orders_count >= 3 %}
  ¡Gracias por ser cliente frecuente, {{ first_name }}!
{% else %}
  Esperamos que disfrutes tu compra, {{ first_name }}.
{% endif %}`,
  },
  {
    title: "Condicional cumpleaños",
    description: "Cambiar mensaje según el plazo del cumpleaños.",
    code: `{% if dias_para_cumpleanos == 30 %}
  El cumpleaños de {{ nombre_regalado }} es en un mes.
{% elif dias_para_cumpleanos == 15 %}
  ¡Ya faltan solo 15 días para el cumpleaños de {{ nombre_regalado }}!
{% elif dias_para_cumpleanos == 7 %}
  ¡Esta semana es el cumpleaños de {{ nombre_regalado }}!
{% endif %}`,
  },
  {
    title: "Bucle de productos recomendados",
    description: "Iterar manualmente sobre recommended_products para un diseño propio.",
    code: `{% for p in recommended_products %}
  <div>
    <img src="{{ p.image_url }}" alt="{{ p.title }}" />
    <a href="{{ p.url }}">{{ p.title }}</a>
    <strong>${{ p.price }}</strong>
  </div>
{% endfor %}`,
  },
  {
    title: "Filtro de texto",
    description: "Transformar texto con filtros Jinja2 estándar.",
    code: `{{ nombre | upper }}        {# MARÍA GONZÁLEZ #}
{{ first_name | capitalize }} {# María #}
{{ email | lower }}           {# maria@ejemplo.com #}`,
  },
  {
    title: "Valor por defecto",
    description: "Usar un valor fallback si la variable está vacía.",
    code: `Hola {{ first_name | default('amigo/a') }},
Tu ciudad: {{ shipping_city | default('Chile') }}`,
  },
  {
    title: "Acceder a custom_fields",
    description: "Leer cualquier campo del formulario que no tenga variable directa.",
    code: `{{ custom_fields.get('nombre_regalado', '') }}
{{ custom_fields.get('fecha_nacimiento', '') }}`,
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
    <div className="p-8 max-w-5xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Variables de plantilla</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Códigos que puedes insertar en tus plantillas de email. Se reemplazan automáticamente con los datos del contacto al momento del envío.
        </p>
      </div>

      <div className="space-y-6 mb-10">
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

      {/* Jinja2 section */}
      <div className="mb-8">
        <h2 className="text-xl font-bold text-gray-900 mb-1">Lógica Jinja2</h2>
        <p className="text-sm text-gray-500 mb-5">
          Las plantillas usan el motor Jinja2. Puedes usar condiciones, bucles y filtros directamente en el HTML del email.
          Las variables de las tablas de arriba están disponibles dentro de estos bloques.
        </p>
        <div className="space-y-4">
          {JINJA2_EXAMPLES.map((ex) => (
            <div key={ex.title} className="border border-gray-200 rounded-xl overflow-hidden">
              <div className="px-5 py-3 bg-gray-50 border-b border-gray-200 flex items-start justify-between gap-4">
                <div>
                  <p className="font-semibold text-gray-800 text-sm">{ex.title}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{ex.description}</p>
                </div>
                <CopyButton text={ex.code} />
              </div>
              <pre className="px-5 py-4 text-xs font-mono text-gray-700 bg-gray-950 text-green-300 overflow-x-auto leading-relaxed">
                {ex.code}
              </pre>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-xl px-5 py-4">
        <p className="text-sm font-semibold text-yellow-800 mb-1">Variables no reconocidas</p>
        <p className="text-sm text-yellow-700">
          Si una plantilla usa una variable que no está definida para ese tipo de automatización,
          el tag se reemplaza por texto vacío en lugar de fallar el envío.
          Para depurar, usa{" "}
          <code className="bg-yellow-100 px-1 rounded text-xs">{"{{ variable | default('FALTA') }}"}</code>
          {" "}para detectar qué variables llegan vacías.
        </p>
      </div>
    </div>
  );
}
