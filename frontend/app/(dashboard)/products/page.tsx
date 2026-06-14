"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "@/lib/api";
import type { SyncedProduct } from "@/lib/api";
import { Search, RefreshCw, Package, Tag, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

function formatPrice(price: number) {
  return price > 0
    ? new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(price)
    : "—";
}

function formatDate(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("es-CL", { day: "2-digit", month: "short", year: "numeric" });
}

type SortKey = "title" | "product_type" | "tags" | "price" | "status" | "edad_recomendada";

function SortIcon({ col, sortBy, sortDir }: { col: SortKey; sortBy: SortKey; sortDir: "asc" | "desc" }) {
  if (sortBy !== col) return <ChevronsUpDown size={13} className="ml-1 text-gray-300 inline" />;
  return sortDir === "asc"
    ? <ChevronUp size={13} className="ml-1 text-brand-500 inline" />
    : <ChevronDown size={13} className="ml-1 text-brand-500 inline" />;
}

export default function ProductsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortKey>("title");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [syncResult, setSyncResult] = useState<{ ok?: boolean; synced?: number; total_fetched?: number; errors?: string[]; error?: string } | null>(null);

  function handleSort(col: SortKey) {
    if (sortBy === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("asc");
    }
    setPage(1);
  }

  const { data, isLoading, isError } = useQuery({
    queryKey: ["synced-products", search, typeFilter, page, sortBy, sortDir],
    queryFn: () => adminApi.getProducts({ search, product_type: typeFilter, page, sort_by: sortBy, sort_dir: sortDir }).then((r) => r.data),
    placeholderData: (prev) => prev,
    retry: 1,
  });

  const syncMutation = useMutation({
    mutationFn: () => adminApi.syncProducts(),
    onSuccess: (res) => {
      setSyncResult(res.data);
      qc.invalidateQueries({ queryKey: ["synced-products"] });
    },
  });

  const products: SyncedProduct[] = data?.products ?? [];
  const total = data?.total ?? 0;
  const perPage = data?.per_page ?? 50;
  const totalPages = Math.ceil(total / perPage);
  const productTypes: string[] = data?.product_types ?? [];

  function th(label: string, col: SortKey, className = "") {
    return (
      <th
        className={`px-4 py-3 text-left font-medium text-gray-500 cursor-pointer select-none hover:text-gray-800 transition-colors ${className}`}
        onClick={() => handleSort(col)}
      >
        {label}
        <SortIcon col={col} sortBy={sortBy} sortDir={sortDir} />
      </th>
    );
  }

  return (
    <div className="p-8 max-w-7xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Catálogo Shopify</h1>
          <p className="text-sm text-gray-500 mt-1">
            Productos sincronizados desde la tienda. Usados por el motor de cross-sell.
          </p>
        </div>
        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white font-medium px-4 py-2 rounded-lg text-sm disabled:opacity-60 transition-colors"
        >
          <RefreshCw size={15} className={syncMutation.isPending ? "animate-spin" : ""} />
          {syncMutation.isPending ? "Sincronizando…" : "Sincronizar productos"}
        </button>
      </div>

      {syncResult && (
        <div className={`mb-5 rounded-xl border px-4 py-3 text-sm ${
          syncResult.error || (syncResult.errors?.length ?? 0) > 0
            ? "bg-yellow-50 border-yellow-200"
            : "bg-green-50 border-green-200"
        }`}>
          {syncResult.error ? (
            <p className="font-semibold text-red-700">{syncResult.error}</p>
          ) : (
            <p className={`font-semibold ${(syncResult.errors?.length ?? 0) > 0 ? "text-yellow-800" : "text-green-800"}`}>
              {syncResult.synced ?? 0} productos guardados de {syncResult.total_fetched ?? 0} obtenidos
            </p>
          )}
          {(syncResult.errors?.length ?? 0) > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-yellow-700 font-medium">
                {syncResult.errors!.length} error(es) — ver detalle
              </summary>
              <ul className="mt-1 space-y-0.5">
                {syncResult.errors!.map((e, i) => (
                  <li key={i} className="font-mono text-xs text-yellow-700">{e}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      <div className="flex gap-3 mb-5 flex-wrap">
        <div className="relative flex-1 min-w-56">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar por nombre o etiqueta…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-600 focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">Todos los tipos</option>
          {productTypes.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <p className="text-sm text-gray-400 self-center">{total} producto{total !== 1 ? "s" : ""}</p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20 text-gray-400">Cargando…</div>
      ) : isError ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400 gap-3">
          <Package size={36} className="opacity-30" />
          <p className="text-sm text-red-500">No se pudo cargar el catálogo. Verifica que el backend esté activo.</p>
        </div>
      ) : products.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400 gap-3">
          <Package size={36} className="opacity-30" />
          <p className="text-sm">No hay productos. Pulsa "Sincronizar productos" para importar desde Shopify.</p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 w-12"></th>
                {th("Producto", "title")}
                {th("Tipo", "product_type", "hidden md:table-cell")}
                {th("Etiquetas", "tags", "hidden lg:table-cell")}
                {th("Edad rec.", "edad_recomendada", "hidden md:table-cell")}
                {th("Precio", "price", "text-right")}
                {th("Estado", "status", "text-center hidden sm:table-cell")}
                <th className="px-4 py-3 text-right font-medium text-gray-500 hidden xl:table-cell">Sincronizado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {products.map((p) => (
                <tr key={p.shopify_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-2">
                    {p.image_url ? (
                      <img
                        src={p.image_url}
                        alt={p.title}
                        className="w-10 h-10 object-cover rounded-lg border border-gray-100"
                      />
                    ) : (
                      <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                        <Package size={16} className="text-gray-300" />
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <a
                      href={`https://www.happylapiz.cl/products/${p.handle}`}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-gray-900 hover:text-brand-600 hover:underline"
                    >
                      {p.title}
                    </a>
                    <p className="text-xs text-gray-400 mt-0.5">{p.vendor}</p>
                  </td>
                  <td className="px-4 py-2 hidden md:table-cell text-gray-500">
                    {p.product_type || <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-2 hidden lg:table-cell max-w-xs">
                    {p.tags ? (
                      <div className="flex flex-wrap gap-1">
                        {p.tags.split(",").slice(0, 4).map((t) => (
                          <span key={t.trim()} className="inline-flex items-center gap-0.5 bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded-full">
                            <Tag size={10} />
                            {t.trim()}
                          </span>
                        ))}
                        {p.tags.split(",").length > 4 && (
                          <span className="text-xs text-gray-400">+{p.tags.split(",").length - 4}</span>
                        )}
                      </div>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2 hidden md:table-cell text-gray-500 text-sm">
                    {p.edad_recomendada || <span className="text-gray-300">—</span>}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-gray-700">
                    {formatPrice(p.price)}
                  </td>
                  <td className="px-4 py-2 text-center hidden sm:table-cell">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                      p.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                    }`}>
                      {p.status === "active" ? "Activo" : p.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right text-xs text-gray-400 hidden xl:table-cell">
                    {formatDate(p.synced_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50">
              <p className="text-sm text-gray-500">
                Página {page} de {totalPages}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1.5 rounded border border-gray-200 text-gray-500 hover:bg-white disabled:opacity-40 transition-colors"
                >
                  <ChevronLeft size={16} />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="p-1.5 rounded border border-gray-200 text-gray-500 hover:bg-white disabled:opacity-40 transition-colors"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
