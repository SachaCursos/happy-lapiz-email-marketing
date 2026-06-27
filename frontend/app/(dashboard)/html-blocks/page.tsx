"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { htmlBlocksApi } from "@/lib/api";
import type { DynamicHtmlBlock } from "@/lib/api";
import { Code, Save, Eye, Check, Info } from "lucide-react";
import { formatDate } from "@/lib/utils";

function BlockEditor({ block }: { block: DynamicHtmlBlock }) {
  const qc = useQueryClient();
  const [template, setTemplate] = useState(block.html_template);
  const [samplesJson, setSamplesJson] = useState(
    JSON.stringify(block.sample_products ?? [], null, 2)
  );
  const [previewHtml, setPreviewHtml] = useState("");
  const [saved, setSaved] = useState(false);
  const [jsonError, setJsonError] = useState("");

  const saveMutation = useMutation({
    mutationFn: () => {
      let samples: unknown[];
      try {
        samples = JSON.parse(samplesJson);
        setJsonError("");
      } catch {
        setJsonError("JSON de productos de ejemplo inválido");
        throw new Error("invalid json");
      }
      return htmlBlocksApi.update(block.block_key, {
        html_template: template,
        sample_products: samples as Record<string, unknown>[],
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["html-blocks"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const previewMutation = useMutation({
    mutationFn: () => {
      let samples: unknown[] | undefined;
      try {
        samples = JSON.parse(samplesJson);
        setJsonError("");
      } catch {
        setJsonError("JSON de productos de ejemplo inválido");
        throw new Error("invalid json");
      }
      return htmlBlocksApi.preview(block.block_key, {
        html_template: template,
        sample_products: samples,
      });
    },
    onSuccess: (res) => setPreviewHtml(res.data.html),
  });

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-4">
        <div>
          <h2 className="font-semibold text-gray-900">{block.name}</h2>
          <p className="text-xs text-gray-500 mt-0.5 font-mono">{`{{ ${block.block_key} }}`}</p>
          {block.description && <p className="text-sm text-gray-600 mt-2">{block.description}</p>}
        </div>
        <p className="text-xs text-gray-400 shrink-0">Actualizado {formatDate(block.updated_at)}</p>
      </div>

      <div className="p-5 grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Plantilla HTML (Jinja2)</label>
            <textarea
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              rows={16}
              className="w-full font-mono text-xs border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
              spellCheck={false}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Productos de ejemplo (solo vista previa)
            </label>
            <textarea
              value={samplesJson}
              onChange={(e) => setSamplesJson(e.target.value)}
              rows={8}
              className="w-full font-mono text-xs border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
              spellCheck={false}
            />
            {jsonError && <p className="text-xs text-red-600 mt-1">{jsonError}</p>}
            <p className="text-xs text-gray-400 mt-1">
              Al enviar emails reales se usan productos de Shopify, no estos ejemplos.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => previewMutation.mutate()}
              disabled={previewMutation.isPending}
              className="flex items-center gap-1.5 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
            >
              <Eye size={14} />
              {previewMutation.isPending ? "Generando…" : "Vista previa"}
            </button>
            <button
              type="button"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
              className="flex items-center gap-1.5 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
            >
              {saved ? <Check size={14} /> : <Save size={14} />}
              {saved ? "Guardado" : "Guardar"}
            </button>
          </div>
        </div>

        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">Vista previa</p>
          <div className="border border-gray-200 rounded-lg bg-gray-50 min-h-[320px] overflow-auto p-4">
            {previewHtml ? (
              <div dangerouslySetInnerHTML={{ __html: previewHtml }} />
            ) : (
              <p className="text-sm text-gray-400 text-center py-16">
                Pulsa «Vista previa» para ver el bloque con productos de ejemplo.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function HtmlBlocksPage() {
  const [activeKey, setActiveKey] = useState<string | null>(null);

  const { data: blocks = [], isLoading } = useQuery({
    queryKey: ["html-blocks"],
    queryFn: () => htmlBlocksApi.list().then((r) => r.data),
  });

  const active = blocks.find((b) => b.block_key === (activeKey ?? blocks[0]?.block_key));

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-start gap-3 mb-6">
        <div className="w-10 h-10 bg-indigo-100 rounded-xl flex items-center justify-center">
          <Code size={20} className="text-indigo-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bloques HTML dinámicos</h1>
          <p className="text-sm text-gray-500 mt-1">
            Edita el HTML que generan variables como <code className="text-xs bg-gray-100 px-1 rounded">{"{{ featured_product_html }}"}</code> y{" "}
            <code className="text-xs bg-gray-100 px-1 rounded">{"{{ recommended_products_html }}"}</code>.
            La vista previa usa productos de ejemplo; los envíos reales usan datos de Shopify.
          </p>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-800 flex gap-2 mb-6">
        <Info size={16} className="shrink-0 mt-0.5" />
        <div>
          <p className="font-medium">Variables en la plantilla Jinja2</p>
          <p className="text-xs mt-1 text-blue-700">
            <code>products</code>, <code>product_rows</code> (pares para grilla), <code>btn_color</code>, y por producto{" "}
            <code>p.title</code>, <code>p.url</code>, <code>p.image_url</code>, <code>p.price</code>.
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
                  (active?.block_key === b.block_key)
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                {b.name}
              </button>
            ))}
          </div>
          {active && <BlockEditor key={active.block_key} block={active} />}
        </>
      )}
    </div>
  );
}
