"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { contactsApi, syncApi } from "@/lib/api";
import { Contact } from "@/lib/types";
import { formatDateTime, formatDate } from "@/lib/utils";
import { Plus, Upload, Search, Users, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

const PAGE_SIZE = 50;

function SkeletonRow() {
  return (
    <tr className="border-b border-gray-100">
      <td className="px-5 py-3"><div className="h-4 bg-gray-200 rounded w-36 animate-pulse" /></td>
      <td className="px-5 py-3"><div className="h-4 bg-gray-100 rounded w-44 animate-pulse" /></td>
      <td className="px-5 py-3"><div className="h-4 bg-gray-100 rounded w-28 animate-pulse" /></td>
      <td className="px-5 py-3"><div className="h-4 bg-gray-100 rounded w-32 animate-pulse" /></td>
      <td className="px-5 py-3"><div className="h-4 bg-gray-100 rounded w-32 animate-pulse" /></td>
      <td className="px-5 py-3"><div className="h-4 bg-gray-100 rounded w-24 animate-pulse" /></td>
      <td className="px-5 py-3"><div className="h-4 bg-gray-100 rounded w-28 animate-pulse" /></td>
      <td className="px-5 py-3"><div className="h-5 bg-gray-100 rounded-full w-14 animate-pulse mx-auto" /></td>
    </tr>
  );
}

export default function ContactsPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(0);
  const [syncResult, setSyncResult] = useState<{ created: number; updated: number; skipped: number } | null>(null);

  // Simple debounce on search
  function handleSearch(val: string) {
    setSearch(val);
    setPage(0);
    clearTimeout((window as unknown as { _st?: ReturnType<typeof setTimeout> })._st);
    (window as unknown as { _st?: ReturnType<typeof setTimeout> })._st = setTimeout(
      () => setDebouncedSearch(val),
      300,
    );
  }

  const { data: contacts = [], isLoading, isError, refetch } = useQuery<Contact[]>({
    queryKey: ["contacts", debouncedSearch, page],
    queryFn: () =>
      contactsApi
        .list({ search: debouncedSearch || undefined, skip: page * PAGE_SIZE, limit: PAGE_SIZE })
        .then((r) => r.data),
    staleTime: 2 * 60_000,
    retry: 1,
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => contactsApi.importCsv(file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["contacts"] }),
  });

const syncMutation = useMutation({
    mutationFn: () => syncApi.run(),
    onSuccess: (res) => {
      setSyncResult(res.data);
      qc.invalidateQueries({ queryKey: ["contacts"] });
    },
  });

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) importMutation.mutate(file);
    e.target.value = "";
  }

const hasNextPage = contacts.length === PAGE_SIZE;
  const hasPrevPage = page > 0;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Clientes</h1>
        <div className="flex gap-2.5">
          <button
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            className="flex items-center gap-2 px-3.5 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            <RefreshCw size={14} className={syncMutation.isPending ? "animate-spin" : ""} />
            {syncMutation.isPending ? "Sincronizando..." : "Sincronizar"}
          </button>
          <label className="flex items-center gap-2 px-3.5 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-50 cursor-pointer transition-colors">
            <Upload size={14} />
            Importar CSV
            <input type="file" accept=".csv" className="hidden" onChange={handleFileChange} />
          </label>
          <Link
            href="/contacts/new"
            className="flex items-center gap-2 px-3.5 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors"
          >
            <Plus size={14} />
            Nuevo cliente
          </Link>
        </div>
      </div>

      {/* Notifications */}
      {isError && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 flex items-center justify-between">
          <span>Error al cargar clientes.</span>
          <button onClick={() => refetch()} className="text-xs font-medium underline">Reintentar</button>
        </div>
      )}
      {syncMutation.isError && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          Error al sincronizar. Verifica que el backend esté activo y las variables de entorno configuradas.
        </div>
      )}
      {syncResult && (
        <div className="mb-4 bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-4 py-3 flex items-center justify-between">
          <span>Sincronización completada: <strong>{syncResult.created}</strong> nuevos · <strong>{syncResult.updated}</strong> actualizados · <strong>{syncResult.skipped}</strong> omitidos</span>
          <button onClick={() => setSyncResult(null)} className="text-green-500 hover:text-green-700 ml-4 text-xs">✕</button>
        </div>
      )}
      {importMutation.data && (
        <div className="mb-4 bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-4 py-3">
          Importados: {importMutation.data.data.created} nuevos · {importMutation.data.data.skipped} omitidos
        </div>
      )}

      {/* Table card */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">

        {/* Search bar */}
        <div className="px-5 py-3.5 border-b border-gray-100 flex items-center gap-3 sticky top-0 bg-white z-10">
          <div className="relative flex-1 max-w-sm">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Buscar por nombre o email..."
              className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
          {!isLoading && (
            <span className="text-xs text-gray-400 ml-auto">
              {contacts.length < PAGE_SIZE
                ? `${contacts.length} cliente${contacts.length !== 1 ? "s" : ""}`
                : `${page * PAGE_SIZE + 1}–${page * PAGE_SIZE + contacts.length}`}
            </span>
          )}
        </div>

        <div className="overflow-x-auto">
        <table className="text-sm" style={{ minWidth: "900px", width: "100%" }}>
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Perfil</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Email</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Teléfono</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Pedidos</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Total gastado</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Última compra</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Ciudad</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Región</th>
              <th className="px-5 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Suscripción</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              [...Array(8)].map((_, i) => <SkeletonRow key={i} />)
            ) : contacts.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-5 py-16 text-center">
                  <Users size={36} className="mx-auto text-gray-300 mb-3" />
                  <p className="text-gray-500 font-medium">
                    {debouncedSearch ? "Sin resultados" : "No hay clientes"}
                  </p>
                  <p className="text-gray-400 text-xs mt-1">
                    {debouncedSearch ? "Prueba con otro nombre o email" : "Importa un CSV o agrega clientes manualmente"}
                  </p>
                </td>
              </tr>
            ) : (
              contacts.map((c) => (
                <tr key={c.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors group">
                  {/* Profile */}
                  <td className="px-5 py-3">
                    <Link
                      href={`/contacts/${c.id}`}
                      className="font-medium text-brand-600 hover:underline"
                    >
                      {c.name || c.email}
                    </Link>
                    {c.accepts_marketing === false && (
                      <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-red-50 text-red-500 font-medium">
                        baja
                      </span>
                    )}
                  </td>

                  {/* Email */}
                  <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">
                    {c.email}
                  </td>

                  {/* Phone */}
                  <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">
                    {c.phone || <span className="text-gray-300">—</span>}
                  </td>

                  {/* Pedidos */}
                  <td className="px-5 py-3 text-gray-700 text-xs whitespace-nowrap text-center">
                    {c.orders_count > 0 ? c.orders_count : <span className="text-gray-300">0</span>}
                  </td>

                  {/* Total gastado */}
                  <td className="px-5 py-3 text-xs whitespace-nowrap">
                    {c.total_spent
                      ? <span className="font-medium text-gray-800">${Math.round(c.total_spent).toLocaleString("es-CL")}</span>
                      : <span className="text-gray-300">—</span>}
                  </td>

                  {/* Última compra */}
                  <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">
                    {c.last_purchase ? formatDate(c.last_purchase) : <span className="text-gray-300">—</span>}
                  </td>

                  {/* Ciudad */}
                  <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">
                    {c.shipping_city || <span className="text-gray-300">—</span>}
                  </td>

                  {/* Región */}
                  <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">
                    {c.shipping_province || <span className="text-gray-300">—</span>}
                  </td>

                  {/* Suscripción */}
                  <td className="px-5 py-3 text-center whitespace-nowrap">
                    {c.accepts_marketing === true
                      ? <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700">Activo</span>
                      : c.accepts_marketing === false
                        ? <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-500">Baja</span>
                        : <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-400">—</span>}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        </div>

        {/* Pagination */}
        {(hasPrevPage || hasNextPage) && (
          <div className="px-5 py-3 border-t border-gray-100 flex items-center justify-between">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={!hasPrevPage}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={13} /> Anterior
            </button>
            <span className="text-xs text-gray-400">Página {page + 1}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasNextPage}
              className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-200 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Siguiente <ChevronRight size={13} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
