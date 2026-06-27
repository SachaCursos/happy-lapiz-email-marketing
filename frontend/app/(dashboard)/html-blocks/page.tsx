"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { htmlBlocksApi } from "@/lib/api";
import { Code, Info, Palette } from "lucide-react";
import { ProductHtmlBlockEditor } from "@/components/ProductHtmlBlockEditor";

export default function HtmlBlocksPage() {
  const [activeKey, setActiveKey] = useState<string | null>(null);

  const { data: blocks = [], isLoading } = useQuery({
    queryKey: ["html-blocks"],
    queryFn: () => htmlBlocksApi.list().then((r) => r.data),
  });

  const active = blocks.find((b) => b.block_key === (activeKey ?? blocks[0]?.block_key));

  return (
    <div className="p-8 max-w-7xl">
      <div className="flex items-start gap-3 mb-6">
        <div className="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center">
          <Code size={20} className="text-indigo-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bloques HTML dinámicos</h1>
          <p className="text-sm text-gray-500 mt-1">
            Diseña visualmente los bloques que generan variables como{" "}
            <code className="text-xs bg-gray-100 px-1 rounded">{"{{ featured_product_html }}"}</code> y{" "}
            <code className="text-xs bg-gray-100 px-1 rounded">{"{{ recommended_products_html }}"}</code>.
            Los cambios se ven al instante; al guardar se genera el HTML para los envíos reales.
          </p>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-800 flex gap-2 mb-6">
        <Info size={16} className="shrink-0 mt-0.5" />
        <div>
          <p className="font-medium flex items-center gap-1.5">
            <Palette size={14} />
            Editor visual en tiempo real
          </p>
          <p className="text-xs mt-1 text-blue-700">
            Ajusta colores, tipografía, botones y espaciado como en el editor de plantillas. La vista previa usa
            productos de ejemplo; los envíos reales inyectan datos de Shopify automáticamente.
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="h-40 bg-gray-100 rounded-xl animate-pulse" />
      ) : blocks.length === 0 ? (
        <p className="text-gray-500 text-sm">No hay bloques configurados.</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2 mb-6">
            {blocks.map((b) => (
              <button
                key={b.block_key}
                type="button"
                onClick={() => setActiveKey(b.block_key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                  active?.block_key === b.block_key
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                {b.name}
              </button>
            ))}
          </div>
          {active && <ProductHtmlBlockEditor key={active.block_key} block={active} />}
        </>
      )}
    </div>
  );
}
