"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SlidersHorizontal, Info, Check } from "lucide-react";
import { dynamicCriteriaApi, shopifyApi, DynamicCriteria } from "@/lib/api";
import {
  CriteriaConfigForm,
  ProductCriteriaConfig,
  configFromApi,
  configToApi,
} from "@/components/CriteriaConfigForm";

export default function CriteriosDinamicosPage() {
  const qc = useQueryClient();
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProductCriteriaConfig | null>(null);
  const [saved, setSaved] = useState(false);

  const { data: criteriaList = [], isLoading } = useQuery<DynamicCriteria[]>({
    queryKey: ["dynamic-criteria"],
    queryFn: () => dynamicCriteriaApi.list().then((r) => r.data),
  });

  const { data: products = [], isLoading: productsLoading } = useQuery({
    queryKey: ["shopify-products"],
    queryFn: () => shopifyApi.products().then((r) => r.data),
    staleTime: 10 * 60_000,
  });

  const active = criteriaList.find((c) => c.criteria_key === (activeKey ?? criteriaList[0]?.criteria_key));

  useEffect(() => {
    if (active) {
      setDraft(configFromApi(active.config));
      setSaved(false);
    }
  }, [active?.criteria_key, active?.updated_at]);

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!active || !draft) throw new Error("Sin criterio activo");
      return dynamicCriteriaApi.update(active.criteria_key, configToApi(draft));
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dynamic-criteria"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-start gap-3 mb-6">
        <div className="w-10 h-10 bg-violet-100 rounded-xl flex items-center justify-center">
          <SlidersHorizontal size={20} className="text-violet-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Criterios dinámicos</h1>
          <p className="text-sm text-gray-500 mt-1">
            Define cómo se eligen los productos para las variables dinámicas de tus plantillas y automatizaciones.
            Los criterios se aplican automáticamente en cada envío.
          </p>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-800 flex gap-2 mb-6">
        <Info size={16} className="shrink-0 mt-0.5" />
        <p className="text-xs">
          No hace falta configurar nada en cada automatización: al usar variables como{" "}
          <code className="bg-white/80 px-1 rounded">{"{{ productos_recomendados_edad_html }}"}</code> o{" "}
          <code className="bg-white/80 px-1 rounded">{"{{ recommended_products_html }}"}</code>, el motor lee estos criterios globales.
        </p>
      </div>

      {isLoading ? (
        <div className="h-40 bg-gray-100 rounded-xl animate-pulse" />
      ) : criteriaList.length === 0 ? (
        <p className="text-gray-500 text-sm">No hay criterios configurados.</p>
      ) : (
        <>
          <div className="flex flex-wrap gap-2 mb-6">
            {criteriaList.map((c) => (
              <button
                key={c.criteria_key}
                type="button"
                onClick={() => setActiveKey(c.criteria_key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                  active?.criteria_key === c.criteria_key
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>

          {active && draft && (
            <div className="border border-gray-200 rounded-xl bg-white p-6 space-y-5">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">{active.name}</h2>
                {active.description && <p className="text-sm text-gray-500 mt-1">{active.description}</p>}
                {active.variables.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
                    {active.variables.map((v) => (
                      <code key={v} className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                        {`{{ ${v} }}`}
                      </code>
                    ))}
                  </div>
                )}
              </div>

              <CriteriaConfigForm
                config={draft}
                onChange={(cfg) => {
                  setDraft(cfg);
                  setSaved(false);
                }}
                products={products}
                productsLoading={productsLoading}
                showAgeFilter={active.criteria_key === "recommended_products"}
              />

              <div className="flex items-center gap-3 pt-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => saveMutation.mutate()}
                  disabled={saveMutation.isPending}
                  className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50"
                >
                  {saveMutation.isPending ? "Guardando…" : "Guardar criterios"}
                </button>
                {saved && (
                  <span className="text-sm text-green-600 flex items-center gap-1">
                    <Check size={14} /> Guardado
                  </span>
                )}
                {saveMutation.isError && (
                  <span className="text-sm text-red-600">Error al guardar. Intenta de nuevo.</span>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
