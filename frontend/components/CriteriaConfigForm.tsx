"use client";

import { Plus, Trash2 } from "lucide-react";
import { ShopifyProduct } from "@/lib/api";
import { ProductMultiSelect } from "@/components/ProductMultiSelect";

export type RecStrategy = "bestseller" | "rules" | "rules_then_bestseller";

export interface CrossSellRule {
  id: string;
  if_product_ids: string[];
  recommend_product_ids: string[];
}

export interface ProductCriteriaConfig {
  enabled: boolean;
  max_products: number;
  strategy: RecStrategy;
  lookback_days: number;
  require_age_match: boolean;
  exclude_purchased: boolean;
  rules: CrossSellRule[];
}

export const DEFAULT_CRITERIA_CONFIG: ProductCriteriaConfig = {
  enabled: true,
  max_products: 4,
  strategy: "bestseller",
  lookback_days: 180,
  require_age_match: true,
  exclude_purchased: true,
  rules: [],
};

export function configFromApi(raw: Record<string, unknown> | undefined): ProductCriteriaConfig {
  const rules = Array.isArray(raw?.rules)
    ? (raw!.rules as Record<string, unknown>[]).map((r, i) => ({
        id: String(i),
        if_product_ids: Array.isArray(r.if_product_ids) ? r.if_product_ids.map(String) : [],
        recommend_product_ids: Array.isArray(r.recommend_product_ids) ? r.recommend_product_ids.map(String) : [],
      }))
    : [];
  const strat = String(raw?.strategy ?? "bestseller");
  return {
    enabled: raw?.enabled !== false,
    max_products: Number(raw?.max_products ?? 4),
    strategy: (strat === "rules" || strat === "rules_then_bestseller" ? strat : "bestseller") as RecStrategy,
    lookback_days: Number(raw?.lookback_days ?? 180),
    require_age_match: raw?.require_age_match !== false,
    exclude_purchased: raw?.exclude_purchased !== false,
    rules,
  };
}

export function configToApi(cfg: ProductCriteriaConfig): Record<string, unknown> {
  return {
    enabled: cfg.enabled,
    max_products: cfg.max_products,
    strategy: cfg.strategy,
    lookback_days: cfg.lookback_days,
    require_age_match: cfg.require_age_match,
    exclude_purchased: cfg.exclude_purchased,
    rules: cfg.rules
      .filter((r) => r.if_product_ids.length > 0 && r.recommend_product_ids.length > 0)
      .map((r) => ({
        if_product_ids: r.if_product_ids,
        recommend_product_ids: r.recommend_product_ids,
      })),
  };
}

function CrossSellRulesEditor({
  rules,
  onChange,
  products,
  loading,
}: {
  rules: CrossSellRule[];
  onChange: (rules: CrossSellRule[]) => void;
  products: ShopifyProduct[];
  loading: boolean;
}) {
  function addRule() {
    onChange([...rules, { id: String(Date.now()), if_product_ids: [], recommend_product_ids: [] }]);
  }

  function updateRule(idx: number, patch: Partial<CrossSellRule>) {
    onChange(rules.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  }

  function moveRecommend(ruleIdx: number, prodIdx: number, dir: -1 | 1) {
    const rule = rules[ruleIdx];
    const next = [...rule.recommend_product_ids];
    const target = prodIdx + dir;
    if (target < 0 || target >= next.length) return;
    [next[prodIdx], next[target]] = [next[target], next[prodIdx]];
    updateRule(ruleIdx, { recommend_product_ids: next });
  }

  return (
    <div className="space-y-3">
      {rules.map((rule, idx) => (
        <div key={rule.id} className="border border-gray-200 rounded-xl p-4 bg-gray-50 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Regla {idx + 1}</span>
            <button type="button" onClick={() => onChange(rules.filter((_, i) => i !== idx))} className="text-gray-400 hover:text-red-500">
              <Trash2 size={14} />
            </button>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Si el cliente compró</label>
            <ProductMultiSelect
              selected={rule.if_product_ids}
              onChange={(v) => updateRule(idx, { if_product_ids: v })}
              products={products}
              loading={loading}
              emptyLabel="Seleccionar producto(s) disparador…"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Recomendar en este orden (opción 1, 2, 3…)</label>
            <ProductMultiSelect
              selected={rule.recommend_product_ids}
              onChange={(v) => updateRule(idx, { recommend_product_ids: v })}
              products={products}
              loading={loading}
              emptyLabel="Seleccionar productos a recomendar…"
            />
            {rule.recommend_product_ids.length > 1 && (
              <div className="mt-2 space-y-1">
                {rule.recommend_product_ids.map((pid, pi) => {
                  const p = products.find((x) => x.id === pid);
                  return (
                    <div key={pid} className="flex items-center gap-2 text-xs text-gray-600 bg-white border border-gray-100 rounded-lg px-2 py-1">
                      <span className="font-semibold text-brand-600 w-5">{pi + 1}.</span>
                      <span className="flex-1 truncate">{p?.title ?? pid}</span>
                      <button type="button" disabled={pi === 0} onClick={() => moveRecommend(idx, pi, -1)} className="text-gray-400 hover:text-gray-700 disabled:opacity-30">↑</button>
                      <button type="button" disabled={pi === rule.recommend_product_ids.length - 1} onClick={() => moveRecommend(idx, pi, 1)} className="text-gray-400 hover:text-gray-700 disabled:opacity-30">↓</button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ))}
      <button type="button" onClick={addRule} className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-700 font-medium">
        <Plus size={14} /> Agregar regla
      </button>
    </div>
  );
}

interface CriteriaConfigFormProps {
  config: ProductCriteriaConfig;
  onChange: (cfg: ProductCriteriaConfig) => void;
  products: ShopifyProduct[];
  productsLoading: boolean;
  showAgeFilter?: boolean;
}

export function CriteriaConfigForm({
  config,
  onChange,
  products,
  productsLoading,
  showAgeFilter = true,
}: CriteriaConfigFormProps) {
  function patch(p: Partial<ProductCriteriaConfig>) {
    onChange({ ...config, ...p });
  }

  return (
    <div className="space-y-4">
      <label className="flex items-center gap-2 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={config.enabled}
          onChange={(e) => patch({ enabled: e.target.checked })}
          className="accent-brand-600 w-4 h-4"
        />
        <span className="text-sm font-medium text-gray-700">Activo</span>
      </label>

      {config.enabled && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Estrategia</label>
              <select
                value={config.strategy}
                onChange={(e) => patch({ strategy: e.target.value as RecStrategy })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="bestseller">Más vendidos (últimos N días)</option>
                <option value="rules">Solo reglas personalizadas</option>
                <option value="rules_then_bestseller">Reglas primero, luego más vendidos</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Máximo de productos</label>
              <input
                type="number"
                min={1}
                max={8}
                value={config.max_products}
                onChange={(e) => patch({ max_products: Math.max(1, Math.min(8, Number(e.target.value))) })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>

          {(config.strategy === "bestseller" || config.strategy === "rules_then_bestseller") && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Ventas de los últimos (días)</label>
                <input
                  type="number"
                  min={7}
                  max={365}
                  value={config.lookback_days}
                  onChange={(e) => patch({ lookback_days: Math.max(7, Math.min(365, Number(e.target.value))) })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                <p className="text-xs text-gray-400 mt-1">Fuente: pedidos en shopify_orders.</p>
              </div>
              <div className="space-y-2 pt-1">
                {showAgeFilter && (
                  <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-700">
                    <input
                      type="checkbox"
                      checked={config.require_age_match}
                      onChange={(e) => patch({ require_age_match: e.target.checked })}
                      className="accent-brand-600"
                    />
                    Filtrar por edad del regalón
                  </label>
                )}
                <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={config.exclude_purchased}
                    onChange={(e) => patch({ exclude_purchased: e.target.checked })}
                    className="accent-brand-600"
                  />
                  Excluir productos ya comprados
                </label>
              </div>
            </div>
          )}

          {(config.strategy === "rules" || config.strategy === "rules_then_bestseller") && (
            <div>
              <p className="text-xs text-gray-500 mb-2">
                Ejemplo: si compró Mi Primer Taladro → opción 1: Pista de Autos, opción 2: Piedras Musicales.
              </p>
              <CrossSellRulesEditor
                rules={config.rules}
                onChange={(rules) => patch({ rules })}
                products={products}
                loading={productsLoading}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
