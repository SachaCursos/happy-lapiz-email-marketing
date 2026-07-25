"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authApi, syncApi, api, adminApi } from "@/lib/api";
import { User } from "@/lib/types";
import { RefreshCw, PackagePlus, ImageOff, Package, CalendarRange } from "lucide-react";

interface YearlyPlanEntry {
  name: string;
  date: string;
  subject: string;
  teaser: string;
  status: string;
}

interface YearlyPlanResult {
  ok: boolean;
  preview: boolean;
  profile: {
    product_count: number;
    top_categories: { category: string; count: number }[];
    price_min: number | null;
    price_max: number | null;
    brand_color: string;
    logo_url: string | null;
  };
  planned: YearlyPlanEntry[];
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data: user } = useQuery<User>({
    queryKey: ["me"],
    queryFn: () => authApi.me().then((r) => r.data),
  });

  const syncMutation = useMutation({
    mutationFn: () => syncApi.run(),
    onSuccess: () => {
      setTimeout(() => {
        syncApi.status().then((r) => setSyncResult(r.data));
        qc.invalidateQueries({ queryKey: ["contacts"] });
      }, 3000);
    },
  });

  const [syncResult, setSyncResult] = useState<Record<string, unknown> | null>(null);
  const [planResult, setPlanResult] = useState<YearlyPlanResult | null>(null);
  const [analyzingPlan, setAnalyzingPlan] = useState(false);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [logoResult, setLogoResult] = useState<{ ok: boolean; fixed: string[] } | null>(null);
  const [fixingLogo, setFixingLogo] = useState(false);
  const [syncProductsResult, setSyncProductsResult] = useState<{ ok?: boolean; synced?: number; total_fetched?: number; error?: string; errors?: string[] } | null>(null);
  const [syncingProducts, setSyncingProducts] = useState(false);

  async function syncProducts() {
    setSyncingProducts(true);
    setSyncProductsResult(null);
    try {
      const r = await adminApi.syncProducts();
      setSyncProductsResult(r.data);
    } catch {
      setSyncProductsResult({ ok: false, error: "Error al sincronizar" });
    } finally {
      setSyncingProducts(false);
    }
  }

  async function fixLogo() {
    setFixingLogo(true);
    setLogoResult(null);
    try {
      const r = await api.post("/admin/fix-logo");
      setLogoResult(r.data);
    } catch {
      setLogoResult({ ok: false, fixed: [] });
    } finally {
      setFixingLogo(false);
    }
  }

  async function analyzePlan() {
    setAnalyzingPlan(true);
    setPlanResult(null);
    try {
      const r = await adminApi.yearlyPlanPreview();
      setPlanResult(r.data);
    } catch {
      setPlanResult(null);
    } finally {
      setAnalyzingPlan(false);
    }
  }

  async function generatePlan() {
    setGeneratingPlan(true);
    try {
      const r = await adminApi.yearlyPlanGenerate();
      setPlanResult(r.data);
    } catch {
      // keep the last preview visible; the button will just show the error state briefly
    } finally {
      setGeneratingPlan(false);
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-8">Configuración</h1>

      <div className="space-y-6">
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Mi cuenta</h2>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Nombre</span>
              <span className="font-medium text-gray-900">{user?.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Email</span>
              <span className="font-medium text-gray-900">{user?.email}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Rol</span>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 capitalize">
                {user?.role}
              </span>
            </div>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 mb-1">Sincronización de contactos</h2>
          <p className="text-gray-500 text-sm mb-4">
            Importa y actualiza contactos desde Shopify.
            Calcula automáticamente: nº pedidos, última compra y ticket medio.
          </p>
          <button
            onClick={() => { setSyncResult(null); syncMutation.mutate(); }}
            disabled={syncMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
          >
            <RefreshCw size={14} className={syncMutation.isPending ? "animate-spin" : ""} />
            {syncMutation.isPending ? "Sincronizando..." : "Sincronizar ahora"}
          </button>
          {syncResult && (
            <div className={`mt-3 px-4 py-3 rounded-lg text-sm ${syncResult.status === "done" ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
              {syncResult.status === "done"
                ? `✓ Sync completado — ${syncResult.created} nuevos · ${syncResult.updated} actualizados · ${syncResult.skipped} omitidos`
                : `Error: ${syncResult.detail}`}
            </div>
          )}
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 mb-1">Sincronización de productos Shopify</h2>
          <p className="text-gray-500 text-sm mb-4">
            Importa el catálogo de productos (título, tags, tipo, imagen, precio) a la base de datos local.
            Necesario para el motor de recomendaciones cross-sell dinámico.
          </p>
          <button
            onClick={syncProducts}
            disabled={syncingProducts}
            className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 disabled:opacity-60 transition-colors"
          >
            <Package size={14} className={syncingProducts ? "animate-pulse" : ""} />
            {syncingProducts ? "Sincronizando..." : "Sincronizar catálogo"}
          </button>
          {syncProductsResult && (
            <div className={`mt-3 px-4 py-3 rounded-lg text-sm ${syncProductsResult.ok ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
              {syncProductsResult.ok
                ? `✓ ${syncProductsResult.synced} productos guardados (de ${syncProductsResult.total_fetched} obtenidos)`
                : `Error: ${syncProductsResult.error}`}
              {syncProductsResult.errors && syncProductsResult.errors.length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs opacity-70">{syncProductsResult.errors.length} errores de inserción</summary>
                  <ul className="mt-1 text-xs space-y-0.5 opacity-70">
                    {syncProductsResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </details>
              )}
            </div>
          )}
        </div>

        {user?.role === "admin" && (
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <h2 className="font-semibold text-gray-900 mb-1">Plan de contenido anual</h2>
            <p className="text-gray-500 text-sm mb-4">
              Genera hasta 11 plantillas y campañas en borrador para fechas comerciales del año
              (Día de la Madre, Cyber Monday, Navidad, aniversario de la tienda, etc.), usando tus
              propios productos y color de marca cuando están disponibles. No envía nada — todo
              queda como borrador para que lo revises. Es seguro correrlo varias veces.
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={analyzePlan}
                disabled={analyzingPlan}
                className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-700 disabled:opacity-60 transition-colors"
              >
                <CalendarRange size={14} className={analyzingPlan ? "animate-pulse" : ""} />
                {analyzingPlan ? "Analizando..." : "Analizar tienda"}
              </button>
              {planResult && planResult.preview && (
                <button
                  onClick={generatePlan}
                  disabled={generatingPlan}
                  className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
                >
                  <PackagePlus size={14} className={generatingPlan ? "animate-pulse" : ""} />
                  {generatingPlan ? "Generando..." : "Generar plan"}
                </button>
              )}
            </div>

            {planResult && (
              <div className="mt-4 space-y-3">
                <div className="px-4 py-3 rounded-lg text-sm bg-gray-50 border border-gray-200">
                  <p className="text-gray-700">
                    {planResult.profile.product_count > 0
                      ? `${planResult.profile.product_count} productos sincronizados · categoría principal: ${planResult.profile.top_categories[0]?.category ?? "—"}`
                      : "Sin productos sincronizados todavía — se usarán bloques de producto genéricos."}
                  </p>
                  <p className="text-gray-500 mt-1">
                    Color de marca detectado:{" "}
                    <span className="inline-block w-3 h-3 rounded-full align-middle border border-gray-300" style={{ backgroundColor: planResult.profile.brand_color }} />{" "}
                    {planResult.profile.brand_color}
                  </p>
                </div>

                {!planResult.preview && (
                  <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
                    ✓ Listo. Revisá las campañas creadas en la sección Campañas antes de programarlas.
                  </p>
                )}

                <ul className="divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
                  {planResult.planned.map((entry) => (
                    <li key={entry.name} className="px-4 py-2.5 text-sm flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-medium text-gray-900 truncate">{entry.name}</p>
                        <p className="text-gray-400 text-xs truncate">{entry.subject}</p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="text-gray-500 text-xs">{entry.date}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${entry.status === "ya existe" ? "bg-gray-100 text-gray-500" : "bg-brand-50 text-brand-700"}`}>
                          {entry.status}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {user?.role === "admin" && (
          <div className="bg-white border border-gray-200 rounded-xl p-6">
            <h2 className="font-semibold text-gray-900 mb-1">Corregir logo en plantillas</h2>
            <p className="text-gray-500 text-sm mb-4">
              Reemplaza el logo SVG (no compatible con Gmail/Outlook) por la imagen PNG alojada en el backend.
              Corre esto una sola vez después de desplegar.
            </p>
            <button
              onClick={fixLogo}
              disabled={fixingLogo}
              className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-700 disabled:opacity-60 transition-colors"
            >
              <ImageOff size={14} className={fixingLogo ? "animate-pulse" : ""} />
              {fixingLogo ? "Corrigiendo..." : "Corregir logos"}
            </button>
            {logoResult && (
              <div className={`mt-3 px-4 py-3 rounded-lg text-sm ${logoResult.ok ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                {logoResult.ok
                  ? logoResult.fixed.length === 0
                    ? "✓ No había plantillas con el logo SVG. Todo al día."
                    : `✓ Logo corregido en: ${logoResult.fixed.join(", ")}`
                  : "Error al corregir. Revisá los logs del backend."}
              </div>
            )}
          </div>
        )}

        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 mb-2">Resend</h2>
          <p className="text-gray-500 text-sm mb-4">La API key de Resend se configura en las variables de entorno de Railway.</p>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 font-mono text-xs text-gray-600 space-y-1">
            <p>RESEND_API_KEY=re_xxxxxxxxxxxx</p>
            <p>RESEND_FROM_EMAIL=Tu Tienda &lt;ventas@tudominio.cl&gt;</p>
            <p>RESEND_WEBHOOK_SECRET=tu_secreto</p>
            <p className="text-brand-600 mt-2">NOTIFY_EMAIL=tu@email.com &nbsp;<span className="text-gray-400 font-sans not-italic">← recibe alertas de desuscripciones</span></p>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 mb-2">Webhook Resend</h2>
          <p className="text-gray-500 text-sm mb-3">Copia este URL y pégalo en el dashboard de Resend → Webhooks → Add Endpoint:</p>
          <div
            className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 font-mono text-sm text-gray-700 break-all cursor-pointer hover:bg-gray-100 transition-colors"
            onClick={() => {
              const url = `${window.location.origin}/api/webhooks/resend`;
              navigator.clipboard.writeText(url);
            }}
            title="Click para copiar"
          >
            {typeof window !== "undefined" ? `${window.location.origin}/api/webhooks/resend` : "https://tu-dominio.up.railway.app/api/webhooks/resend"}
          </div>
          <p className="text-xs text-gray-400 mt-2">Eventos a activar en Resend: <strong>email.sent · email.delivered · email.opened · email.clicked · email.bounced · email.complained</strong></p>
        </div>

        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 mb-2">Pixel de tracking web (Shopify)</h2>
          <p className="text-gray-500 text-sm mb-3">
            Pega este script en Shopify → <strong>Configuración → Checkout → Código adicional</strong> (o en el <code className="bg-gray-100 px-1 rounded text-xs">&lt;head&gt;</code> del tema).
            Trackea productos vistos, actividad en el sitio y productos al carrito.
          </p>
          <div
            className="bg-gray-900 text-green-400 font-mono text-xs rounded-lg px-4 py-3 break-all cursor-pointer hover:bg-gray-800 transition-colors"
            onClick={() => {
              const url = `${window.location.origin}/api/forms/track.js`;
              const snippet = `<script src="${url}" async></script>`;
              navigator.clipboard.writeText(snippet);
            }}
            title="Click para copiar"
          >
            {`<script src="${typeof window !== "undefined" ? window.location.origin : "https://email-marketing-front-end-production.up.railway.app"}/api/forms/track.js" async></script>`}
          </div>
          <p className="text-xs text-gray-400 mt-2">Click para copiar · Trackea: producto visto · activo en sitio · agregado al carrito</p>
        </div>
      </div>
    </div>
  );
}
