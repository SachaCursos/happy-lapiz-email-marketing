"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, X } from "lucide-react";
import { ShopifyProduct } from "@/lib/api";

interface ProductMultiSelectProps {
  selected: string[];
  onChange: (v: string[]) => void;
  products: ShopifyProduct[];
  loading: boolean;
  emptyLabel?: string;
}

export function ProductMultiSelect({
  selected,
  onChange,
  products,
  loading,
  emptyLabel = "Seleccionar productos…",
}: ProductMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = products.filter((p) => p.title.toLowerCase().includes(search.toLowerCase()));
  const selectedProducts = products.filter((p) => selected.includes(p.id));

  function toggle(id: string) {
    onChange(selected.includes(id) ? selected.filter((i) => i !== id) : [...selected, id]);
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 flex items-center justify-between bg-white"
      >
        <span className={selected.length === 0 ? "text-gray-400" : "text-gray-900"}>
          {loading
            ? "Cargando productos..."
            : selected.length === 0
              ? emptyLabel
              : `${selected.length} producto${selected.length !== 1 ? "s" : ""} seleccionado${selected.length !== 1 ? "s" : ""}`}
        </span>
        <ChevronDown size={14} className="text-gray-400 shrink-0" />
      </button>

      {selectedProducts.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {selectedProducts.map((p) => (
            <span key={p.id} className="inline-flex items-center gap-1 bg-brand-100 text-brand-700 text-xs px-2 py-0.5 rounded-full max-w-[220px]">
              <span className="truncate">{p.title}</span>
              <button type="button" onClick={() => toggle(p.id)} className="hover:text-brand-900 shrink-0">
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}

      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-xl shadow-xl">
          <div className="p-2 border-b border-gray-100">
            <input
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar producto..."
              className="w-full text-sm px-3 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div className="max-h-64 overflow-y-auto">
            {filtered.map((p) => (
              <label key={p.id} className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-50">
                <input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggle(p.id)} className="accent-brand-600 shrink-0" />
                {p.image_url && <img src={p.image_url} alt={p.title} className="w-9 h-9 rounded object-cover shrink-0 border border-gray-100" />}
                <div className="min-w-0">
                  <p className="text-sm text-gray-800 truncate">{p.title}</p>
                  {p.price && <p className="text-xs text-gray-400">${parseFloat(p.price).toLocaleString("es-CL")}</p>}
                </div>
              </label>
            ))}
            {filtered.length === 0 && !loading && <p className="text-sm text-gray-400 px-3 py-3 text-center">Sin resultados</p>}
            {loading && <p className="text-sm text-gray-400 px-3 py-3 text-center">Cargando...</p>}
          </div>
          <div className="p-2 border-t border-gray-100 flex justify-between items-center">
            <button type="button" onClick={() => onChange([])} className="text-xs text-gray-400 hover:text-red-500">
              Limpiar
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setSearch("");
              }}
              className="text-xs text-brand-600 font-medium hover:text-brand-700"
            >
              Listo ✓
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
