"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/lib/api";
import { Template } from "@/lib/types";
import { Plus, Copy, Trash2, Eye, X, Search, Tag, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { formatDate } from "@/lib/utils";

function TemplateSkeleton() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden animate-pulse">
      <div className="bg-gray-100 h-40" />
      <div className="p-4 space-y-2">
        <div className="h-4 bg-gray-200 rounded w-3/4" />
        <div className="h-3 bg-gray-100 rounded w-full" />
        <div className="h-3 bg-gray-100 rounded w-1/3 mt-3" />
      </div>
    </div>
  );
}

function PreviewModal({ tpl, onClose }: { tpl: Template; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 flex flex-col"
        style={{ maxHeight: "90vh" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h3 className="font-semibold text-gray-900">{tpl.name}</h3>
            <p className="text-xs text-gray-400 mt-0.5">{tpl.subject_default}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 transition-colors">
            <X size={20} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <iframe
            srcDoc={tpl.html_content}
            sandbox="allow-same-origin"
            title={tpl.name}
            className="w-full rounded-lg border border-gray-100"
            style={{ height: "900px" }}
          />
        </div>
      </div>
    </div>
  );
}

function CuponesPanel() {
  const [open, setOpen] = useState(false);
  const ejemplos = [
    { tag: "{% coupon_code 'CYBER30' %}", desc: "Código estático: CYBER30" },
    { tag: "{{ coupon_code }}", desc: "Cupón dinámico asignado al perfil (Klaviyo)" },
    { tag: "{% coupon_code 'Cross5k' %}", desc: "Cupón cruzado $5.000" },
  ];
  return (
    <div className="mb-6 bg-white border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Tag size={16} className="text-brand-600" />
          <span className="text-sm font-semibold text-gray-800">Cupones dinámicos — integración Shopify + Klaviyo</span>
        </div>
        {open ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
      </button>
      {open && (
        <div className="px-5 pb-5 border-t border-gray-100">
          <p className="text-xs text-gray-500 mt-3 mb-4">
            Pega estas variables en el HTML de tus plantillas. En Klaviyo los cupones dinámicos se generan desde
            <strong> Flows → Action → Send Email → Coupon block</strong>, conectado con Shopify discount codes.
          </p>
          <div className="space-y-3">
            {ejemplos.map((e) => (
              <div key={e.tag} className="flex items-center gap-3 bg-gray-50 rounded-lg px-4 py-2.5">
                <code className="text-xs font-mono text-brand-700 bg-brand-50 px-2 py-1 rounded flex-1">{e.tag}</code>
                <span className="text-xs text-gray-500">{e.desc}</span>
                <button
                  onClick={() => navigator.clipboard.writeText(e.tag)}
                  className="text-xs text-gray-400 hover:text-brand-600 transition-colors ml-auto"
                  title="Copiar"
                >
                  <Copy size={13} />
                </button>
              </div>
            ))}
          </div>
          <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-xs font-semibold text-amber-800 mb-1">Cómo crear cupones dinámicos en Shopify + Klaviyo</p>
            <ol className="text-xs text-amber-700 space-y-1 list-decimal pl-4">
              <li>En Shopify → <strong>Descuentos → Crear código de descuento</strong> (porcentaje o monto fijo)</li>
              <li>En Klaviyo → <strong>Coupons → Add coupon → conectar con Shopify</strong></li>
              <li>En el flow o campaña, agrega un bloque <strong>Coupon</strong> y selecciona el descuento</li>
              <li>Klaviyo genera un código único por persona y lo pone disponible como <code>{"{{ coupon_code }}"}</code></li>
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TemplatesPage() {
  const qc = useQueryClient();
  const [preview, setPreview] = useState<Template | null>(null);
  const [search, setSearch]   = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const { data: templates = [], isLoading, isError } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  const dupMutation = useMutation({
    mutationFn: (id: number) => templatesApi.duplicate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });

  const delMutation = useMutation({
    mutationFn: (id: number) => templatesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates"] });
      setDeleteError(null);
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "No se pudo eliminar la plantilla.";
      setDeleteError(msg);
    },
  });

  return (
    <div className="p-8">
      {preview && <PreviewModal tpl={preview} onClose={() => setPreview(null)} />}

      {deleteError && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 flex items-start gap-2">
          <span className="flex-1">{deleteError}</span>
          <button onClick={() => setDeleteError(null)} className="text-red-400 hover:text-red-600 shrink-0"><X size={14} /></button>
        </div>
      )}

      <CuponesPanel />

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Plantillas</h1>
          <p className="text-gray-500 mt-1 text-sm">{templates.length} plantillas disponibles</p>
        </div>
        <Link
          href="/templates/new"
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors"
        >
          <Plus size={15} />
          Nueva plantilla
        </Link>
      </div>

      {/* Buscador */}
      <div className="relative mb-6 max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar plantilla..."
          className="w-full pl-9 pr-8 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        {search && (
          <button onClick={() => setSearch("")} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
            <X size={14} />
          </button>
        )}
      </div>

      {isError && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          Error al cargar plantillas. Verifica tu conexion.
        </div>
      )}

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <TemplateSkeleton key={i} />)}
        </div>
      ) : (() => {
        const filtered = search.trim()
          ? templates.filter(t =>
              t.name.toLowerCase().includes(search.toLowerCase()) ||
              t.subject_default.toLowerCase().includes(search.toLowerCase())
            )
          : templates;
        return filtered.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <div className="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center mx-auto mb-3">
              <Search size={20} className="text-gray-400" />
            </div>
            {search ? (
              <>
                <p className="text-gray-500 font-medium">Sin resultados para "{search}"</p>
                <button onClick={() => setSearch("")} className="mt-3 text-sm text-brand-600 hover:underline">Limpiar búsqueda</button>
              </>
            ) : (
              <>
                <p className="text-gray-500 font-medium">No hay plantillas</p>
                <p className="text-gray-400 text-sm mt-1">Crea tu primera plantilla de email</p>
                <Link href="/templates/new" className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors">
                  <Plus size={14} /> Crear plantilla
                </Link>
              </>
            )}
          </div>
        ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((tpl) => (
            <div key={tpl.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden hover:shadow-md transition-shadow group">
              {/* HTML preview thumbnail */}
              <div
                className="bg-gray-50 h-52 relative overflow-hidden border-b border-gray-100 cursor-pointer"
                onClick={() => setPreview(tpl)}
              >
                <iframe
                  srcDoc={tpl.html_content}
                  sandbox="allow-same-origin"
                  title={tpl.name}
                  className="absolute top-0 left-0 border-0 pointer-events-none"
                  style={{ width: "600px", height: "800px", transform: "scale(0.37)", transformOrigin: "top left" }}
                />
                <div className="absolute inset-0 bg-transparent group-hover:bg-black/5 transition-colors flex items-center justify-center">
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-white/90 rounded-lg px-3 py-1.5 text-xs font-medium text-gray-700 flex items-center gap-1.5">
                    <Eye size={13} /> Vista previa
                  </div>
                </div>
              </div>

              <div className="p-4">
                <h3 className="font-semibold text-gray-900 truncate">{tpl.name}</h3>
                <p className="text-gray-400 text-xs mt-0.5 truncate">{tpl.subject_default}</p>
                <p className="text-gray-400 text-xs mt-2">{formatDate(tpl.created_at)}</p>
                <div className="mt-3 flex items-center gap-2">
                  <Link
                    href={`/templates/${tpl.id}`}
                    className="flex-1 text-center px-3 py-1.5 border border-gray-300 rounded-lg text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Editar
                  </Link>
                  <button
                    onClick={() => setPreview(tpl)}
                    title="Vista previa"
                    className="p-1.5 text-gray-400 hover:text-brand-600 transition-colors"
                  >
                    <Eye size={14} />
                  </button>
                  <button
                    onClick={() => dupMutation.mutate(tpl.id)}
                    title="Duplicar"
                    className="p-1.5 text-gray-400 hover:text-gray-700 transition-colors"
                  >
                    <Copy size={14} />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm("Eliminar esta plantilla?")) delMutation.mutate(tpl.id);
                    }}
                    title="Eliminar"
                    className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
        );
      })()}
    </div>
  );
}
