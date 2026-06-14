"use client";

import { useState } from "react";
import { adminApi } from "@/lib/api";
import { RefreshCw, CheckCircle, AlertCircle, Package } from "lucide-react";

export default function SyncProductsPage() {
  const [status, setStatus] = useState<"idle" | "running" | "ok" | "error">("idle");
  const [result, setResult] = useState<{ synced?: number; total_fetched?: number; error?: string } | null>(null);
  const [seedStatus, setSeedStatus] = useState<"idle" | "running" | "ok" | "error">("idle");

  async function runSync() {
    setStatus("running");
    setResult(null);
    try {
      const r = await adminApi.syncProducts();
      setResult(r.data);
      setStatus(r.data.ok ? "ok" : "error");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setResult({ error: msg });
      setStatus("error");
    }
  }

  async function runSeed() {
    setSeedStatus("running");
    try {
      await adminApi.seedTemplates();
      setSeedStatus("ok");
    } catch {
      setSeedStatus("error");
    }
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <Package size={22} className="text-brand-600" />
        <h1 className="text-xl font-bold">Sincronizar productos Shopify</h1>
      </div>
      <p className="text-sm text-gray-500 mb-8">
        Importa el catálogo de Shopify a la base de datos local (título, tags, tipo, imagen, precio).
        Necesario para que el motor de cross-sell dinámico pueda recomendar productos por tags.
      </p>

      <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6 space-y-4">
        <div>
          <h2 className="font-semibold text-gray-800 mb-1">1. Sincronizar productos</h2>
          <p className="text-sm text-gray-500 mb-4">
            Descarga todos los productos activos de Shopify y los guarda en <code className="bg-gray-100 px-1 rounded text-xs">shopify_products</code>.
            Vuelve a ejecutar cuando actualices el catálogo.
          </p>
          <button
            onClick={runSync}
            disabled={status === "running"}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 text-white rounded-xl text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <RefreshCw size={15} className={status === "running" ? "animate-spin" : ""} />
            {status === "running" ? "Sincronizando..." : "Sincronizar ahora"}
          </button>
        </div>

        {status === "ok" && result && (
          <div className="flex items-start gap-3 p-4 bg-green-50 border border-green-200 rounded-xl text-sm">
            <CheckCircle size={16} className="text-green-600 mt-0.5 shrink-0" />
            <div>
              <p className="font-semibold text-green-800">Sincronización completada</p>
              <p className="text-green-700">
                {result.synced} productos guardados de {result.total_fetched} obtenidos desde Shopify.
              </p>
            </div>
          </div>
        )}

        {status === "error" && (
          <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-sm">
            <AlertCircle size={16} className="text-red-600 mt-0.5 shrink-0" />
            <div>
              <p className="font-semibold text-red-800">Error al sincronizar</p>
              <p className="text-red-700">{result?.error || "Error desconocido"}</p>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white border border-gray-200 rounded-2xl p-6">
        <h2 className="font-semibold text-gray-800 mb-1">2. Crear plantilla cross-sell</h2>
        <p className="text-sm text-gray-500 mb-4">
          Crea la plantilla <strong>"Cross-sell — Recomendados por compra"</strong> con el bloque{" "}
          <code className="bg-gray-100 px-1 rounded text-xs">{"{{ recommended_products_html }}"}</code> ya incluido,
          lista para usar en automatizaciones.
        </p>
        <button
          onClick={runSeed}
          disabled={seedStatus === "running"}
          className="flex items-center gap-2 px-5 py-2.5 bg-violet-600 text-white rounded-xl text-sm font-semibold hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw size={15} className={seedStatus === "running" ? "animate-spin" : ""} />
          {seedStatus === "running" ? "Creando..." : "Crear plantilla cross-sell"}
        </button>
        {seedStatus === "ok" && (
          <p className="mt-3 text-sm text-green-700 flex items-center gap-1.5">
            <CheckCircle size={14} /> Plantilla creada — búscala en Plantillas.
          </p>
        )}
        {seedStatus === "error" && (
          <p className="mt-3 text-sm text-red-700 flex items-center gap-1.5">
            <AlertCircle size={14} /> Error al crear la plantilla.
          </p>
        )}
      </div>

      <div className="mt-6 bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
        <p className="font-semibold mb-1">¿Cómo funciona el cross-sell dinámico?</p>
        <ol className="list-decimal list-inside space-y-1 text-amber-700">
          <li>El cliente compra un producto (e.g. "Pack Mi Primer Taladro" con tags "3-10 años, educativo").</li>
          <li>La automatización detecta la compra y guarda los IDs de productos comprados.</li>
          <li>Al enviar el correo, busca en la BD productos con los mismos tags o tipo.</li>
          <li>Excluye todo lo que el cliente ya compró (historial completo de órdenes).</li>
          <li>Inyecta el grid HTML con los recomendados en <code>{"{{ recommended_products_html }}"}</code>.</li>
        </ol>
      </div>
    </div>
  );
}
