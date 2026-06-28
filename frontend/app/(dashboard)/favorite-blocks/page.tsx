"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { favoriteBlocksApi, FavoriteBlock, templatesApi } from "@/lib/api";
import { BlockPreview } from "@/components/TemplateBlockEditor";
import { Star, Trash2, Pencil, Info, LayoutGrid, ExternalLink } from "lucide-react";

const GALERIA_TEMPLATE_NAME = "Galería — Opciones de bloques (no enviar)";

const BLOCK_TYPE_LABELS: Record<string, string> = {
  header: "Encabezado",
  text: "Texto HTML",
  image: "Imagen",
  button: "Botón CTA",
  product: "Producto",
  product_grid: "Grilla productos",
  coupon: "Cupón",
  divider: "Divisor",
  spacer: "Espaciado",
  timer: "Timer",
};

export default function FavoriteBlocksPage() {
  const qc = useQueryClient();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");

  const { data: blocks = [], isLoading } = useQuery({
    queryKey: ["favorite-blocks"],
    queryFn: () => favoriteBlocksApi.list().then((r) => r.data),
  });

  const { data: templates = [] } = useQuery({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
  });

  const galeriaTemplate = templates.find((t) => t.name === GALERIA_TEMPLATE_NAME);

  const deleteMutation = useMutation({
    mutationFn: (id: number) => favoriteBlocksApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorite-blocks"] }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      favoriteBlocksApi.update(id, { name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["favorite-blocks"] });
      setEditingId(null);
    },
  });

  function startEdit(block: FavoriteBlock) {
    setEditingId(block.id);
    setEditName(block.name);
  }

  function saveEdit(id: number) {
    const name = editName.trim();
    if (!name) return;
    updateMutation.mutate({ id, name });
  }

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center">
            <Star size={20} className="text-amber-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Bloques favoritos</h1>
            <p className="text-sm text-gray-500 mt-1 max-w-xl">
              Bloques reutilizables para armar plantillas. Al insertarlos en el editor puedes cambiar
              textos, enlaces de botones y productos. Abre la galería para ver todas las variantes.
            </p>
          </div>
        </div>
        {galeriaTemplate ? (
          <Link
            href={`/templates/${galeriaTemplate.id}`}
            className="shrink-0 inline-flex items-center gap-2 px-4 py-2.5 bg-brand-600 text-white rounded-xl text-sm font-semibold hover:bg-brand-700 transition-colors"
          >
            <LayoutGrid size={16} />
            Abrir galería de bloques
            <ExternalLink size={14} className="opacity-80" />
          </Link>
        ) : (
          <Link
            href="/templates"
            className="shrink-0 inline-flex items-center gap-2 px-4 py-2.5 border border-gray-200 text-gray-600 rounded-xl text-sm font-medium hover:bg-gray-50"
          >
            Ir a Plantillas
          </Link>
        )}
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-900 flex gap-2 mb-6">
        <Info size={16} className="shrink-0 mt-0.5" />
        <p className="text-xs leading-relaxed">
          En el editor de plantillas, selecciona un bloque y usa <strong>Guardar como favorito</strong> para
          elegir un nombre personalizado. Los bloques que insertes desde favoritos son copias independientes:
          editar textos o URLs no modifica el favorito guardado.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : blocks.length === 0 ? (
        <p className="text-gray-500 text-sm">No hay bloques favoritos todavía.</p>
      ) : (
        <div className="space-y-4">
          {blocks.map((block) => (
            <div
              key={block.id}
              className="border border-gray-200 rounded-xl bg-white overflow-hidden shadow-sm"
            >
              <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 bg-gray-50">
                <Star size={14} className="text-amber-500 shrink-0" />
                {editingId === block.id ? (
                  <div className="flex-1 flex items-center gap-2">
                    <input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveEdit(block.id);
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      autoFocus
                    />
                    <button
                      type="button"
                      onClick={() => saveEdit(block.id)}
                      disabled={updateMutation.isPending}
                      className="px-3 py-1.5 text-xs font-semibold bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
                    >
                      Guardar
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700"
                    >
                      Cancelar
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-gray-900 truncate">{block.name}</p>
                      <p className="text-xs text-gray-400">
                        {BLOCK_TYPE_LABELS[block.block_type] ?? block.block_type}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => startEdit(block)}
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                      title="Renombrar"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`¿Eliminar "${block.name}"?`)) {
                          deleteMutation.mutate(block.id);
                        }
                      }}
                      className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                      title="Eliminar"
                    >
                      <Trash2 size={14} />
                    </button>
                  </>
                )}
              </div>
              <div className="max-w-[600px] mx-auto border-x border-gray-100">
                <BlockPreview
                  block={{
                    id: String(block.id),
                    type: block.block_type as Parameters<typeof BlockPreview>[0]["block"]["type"],
                    props: block.props,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
