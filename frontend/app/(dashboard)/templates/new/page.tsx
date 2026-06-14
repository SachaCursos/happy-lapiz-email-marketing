"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/lib/api";
import { ArrowLeft, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TemplateBlockEditor, TemplateEditorSaveData } from "@/components/TemplateBlockEditor";

const VARIABLES = [
  { var: "{{ nombre }}", desc: "Nombre completo del contacto" },
  { var: "{{ first_name }}", desc: "Primer nombre" },
  { var: "{{ email }}", desc: "Correo electrónico" },
  { var: "{{ orders_count }}", desc: "Número total de pedidos" },
  { var: "{{ total_spent }}", desc: "Total gastado" },
  { var: "{{ shipping_city }}", desc: "Ciudad de envío" },
  { var: "{{ coupon_code }}", desc: "Código de cupón (si aplica)" },
  { var: "{{ first_product }}", desc: "Primer producto de la orden ('producto comprado')" },
  { var: "{{ order_total }}", desc: "Total de la orden" },
  { var: "{{ order_number }}", desc: "Número de orden Shopify" },
  { var: "{{ recommended_products_html }}", desc: "Grid HTML cross-sell (automatización cross-sell)" },
  { var: "{{ event.extra.checkout_url }}", desc: "URL del carrito abandonado" },
  { var: "{{ event.extra.cart_total }}", desc: "Total del carrito abandonado" },
  { var: "{% if condicion %}...{% endif %}", desc: "Condicional Jinja2" },
  { var: "{{ variable or 'default' }}", desc: "Valor con fallback si vacío" },
];

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
        <div className="px-6 pb-3 grid grid-cols-2 gap-x-8 gap-y-1.5">
          {VARIABLES.map((v) => (
            <div key={v.var} className="flex items-start gap-2">
              <code className="text-[11px] bg-violet-50 text-violet-700 border border-violet-200 rounded px-1.5 py-0.5 shrink-0 font-mono">
                {v.var}
              </code>
              <span className="text-[11px] text-gray-500 leading-tight mt-0.5">{v.desc}</span>
            </div>
          ))}
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
