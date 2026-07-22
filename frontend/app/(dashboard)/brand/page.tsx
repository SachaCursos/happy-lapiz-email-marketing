"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, authApi, brandApi } from "@/lib/api";
import { Copy, Check, Plus, X } from "lucide-react";
import { useState } from "react";
import { User } from "@/lib/types";

interface BrandItem {
  id: number;
  nombre: string;
  valor: string;
  descripcion: string;
}

interface BrandAssets {
  colores: BrandItem[];
  logos: BrandItem[];
  tipografia: BrandItem[];
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <button onClick={copy} className="ml-2 text-gray-400 hover:text-gray-700 transition-colors">
      {copied ? <Check size={13} className="text-green-500" /> : <Copy size={13} />}
    </button>
  );
}

function DeleteButton({ onDelete }: { onDelete: () => void }) {
  return (
    <button
      onClick={onDelete}
      title="Eliminar"
      className="absolute top-2 right-2 w-6 h-6 rounded-full bg-white/90 border border-gray-200 text-gray-400 hover:text-red-600 hover:border-red-200 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
    >
      <X size={13} />
    </button>
  );
}

function AddCard({
  fields,
  onSubmit,
  isPending,
  cta,
}: {
  fields: { key: "nombre" | "valor" | "descripcion"; label: string; placeholder: string; type?: string }[];
  onSubmit: (values: Record<string, string>) => void;
  isPending: boolean;
  cta: string;
}) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="border border-dashed border-gray-300 rounded-xl flex items-center justify-center gap-1.5 text-sm text-gray-400 hover:text-gray-600 hover:border-gray-400 transition-colors min-h-[96px] w-full"
      >
        <Plus size={14} /> {cta}
      </button>
    );
  }

  return (
    <div className="border border-gray-200 rounded-xl p-4 space-y-2 bg-white">
      {fields.map((f) => (
        <input
          key={f.key}
          type={f.type || "text"}
          placeholder={f.placeholder}
          value={values[f.key] || ""}
          onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
          className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      ))}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={() => { onSubmit(values); setValues({}); setOpen(false); }}
          disabled={isPending || !values.nombre || !values.valor}
          className="px-3 py-1.5 bg-brand-600 text-white text-xs font-medium rounded-lg hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >
          Guardar
        </button>
        <button
          onClick={() => { setOpen(false); setValues({}); }}
          className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700"
        >
          Cancelar
        </button>
      </div>
    </div>
  );
}

export default function BrandPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery<BrandAssets>({
    queryKey: ["brand-assets"],
    queryFn: () => api.get("/admin/brand").then((r) => r.data),
  });
  const { data: user } = useQuery<User>({
    queryKey: ["me"],
    queryFn: () => authApi.me().then((r) => r.data),
  });
  const shopName = user?.shop_name || "tu tienda";

  const createMutation = useMutation({
    mutationFn: (data: { categoria: string; nombre: string; valor: string; descripcion?: string }) => brandApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["brand-assets"] }),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => brandApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["brand-assets"] }),
  });

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-48" />
          <div className="grid grid-cols-6 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-20 bg-gray-200 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const { colores = [], logos = [], tipografia = [] } = data ?? {};

  return (
    <div className="p-6 max-w-4xl space-y-10">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Plantilla de marca</h1>
        <p className="text-sm text-gray-500 mt-1">
          Activos oficiales de {shopName} para usar en campañas de email. Son propios de tu tienda — no los comparte con otras tiendas que usen esta plataforma.
        </p>
        {isError && (
          <p className="text-xs text-red-500 mt-2">No se pudieron cargar los activos de marca. Intenta recargar la página.</p>
        )}
      </div>

      {/* Logos */}
      <section>
        <h2 className="text-base font-semibold text-gray-700 mb-4">Logos</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {logos.map((logo) => (
            <div key={logo.id} className="group relative bg-white border border-gray-200 rounded-xl overflow-hidden">
              <DeleteButton onDelete={() => deleteMutation.mutate(logo.id)} />
              <div className="bg-gray-50 flex items-center justify-center p-8 border-b border-gray-100">
                <img src={logo.valor} alt={logo.nombre} className="max-h-24 max-w-full object-contain" />
              </div>
              <div className="p-4">
                <p className="text-sm font-semibold text-gray-800">{logo.nombre}</p>
                <p className="text-xs text-gray-400 mt-0.5">{logo.descripcion}</p>
                <div className="flex items-center mt-2">
                  <code className="text-xs bg-gray-100 px-2 py-1 rounded text-gray-600 truncate max-w-[260px]">
                    {logo.valor}
                  </code>
                  <CopyButton text={logo.valor} />
                </div>
              </div>
            </div>
          ))}
          <AddCard
            cta="Agregar logo"
            isPending={createMutation.isPending}
            fields={[
              { key: "nombre", label: "Nombre", placeholder: "Nombre (ej. Logo principal)" },
              { key: "valor", label: "URL", placeholder: "URL de la imagen (https://...)" },
              { key: "descripcion", label: "Descripción", placeholder: "Descripción (opcional)" },
            ]}
            onSubmit={(v) => createMutation.mutate({ categoria: "logo", nombre: v.nombre, valor: v.valor, descripcion: v.descripcion })}
          />
        </div>
        {logos.length === 0 && (
          <p className="text-xs text-gray-400 mt-3">Todavía no agregaste ningún logo.</p>
        )}
      </section>

      {/* Colores */}
      <section>
        <h2 className="text-base font-semibold text-gray-700 mb-4">Paleta de colores</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {colores.map((color) => (
            <div key={color.id} className="group relative bg-white border border-gray-200 rounded-xl overflow-hidden">
              <DeleteButton onDelete={() => deleteMutation.mutate(color.id)} />
              <div
                className="h-20 w-full"
                style={{ backgroundColor: color.valor }}
              />
              <div className="p-3">
                <p className="text-xs font-semibold text-gray-800">{color.nombre}</p>
                <div className="flex items-center mt-1">
                  <code className="text-xs font-mono text-gray-500">{color.valor}</code>
                  <CopyButton text={color.valor} />
                </div>
                {color.descripcion && (
                  <p className="text-xs text-gray-400 mt-0.5">{color.descripcion}</p>
                )}
              </div>
            </div>
          ))}
          <AddCard
            cta="Agregar color"
            isPending={createMutation.isPending}
            fields={[
              { key: "nombre", label: "Nombre", placeholder: "Nombre (ej. Primario)" },
              { key: "valor", label: "Color", placeholder: "#RRGGBB", type: "text" },
              { key: "descripcion", label: "Descripción", placeholder: "Descripción (opcional)" },
            ]}
            onSubmit={(v) => createMutation.mutate({ categoria: "color", nombre: v.nombre, valor: v.valor, descripcion: v.descripcion })}
          />
        </div>
        {colores.length === 0 && (
          <p className="text-xs text-gray-400 mt-3">Todavía no agregaste ningún color.</p>
        )}
      </section>

      {/* Tipografía */}
      <section>
        <h2 className="text-base font-semibold text-gray-700 mb-4">Tipografía</h2>
        <div className="space-y-3">
          {tipografia.map((tipo) => (
            <div key={tipo.id} className="group relative bg-white border border-gray-200 rounded-xl p-5 flex items-center justify-between">
              <DeleteButton onDelete={() => deleteMutation.mutate(tipo.id)} />
              <div>
                <p
                  className="text-gray-900 mb-1"
                  style={{ fontFamily: tipo.valor, fontSize: tipo.nombre.includes("Título") ? "28px" : "20px", fontWeight: tipo.nombre.includes("Título") ? 700 : 600 }}
                >
                  {tipo.nombre} — {tipo.valor}
                </p>
                <p className="text-xs text-gray-400">{tipo.descripcion}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0 ml-4 mr-6">
                <code className="text-xs bg-gray-100 px-2 py-1 rounded text-gray-600">{tipo.valor}</code>
                <CopyButton text={tipo.valor} />
              </div>
            </div>
          ))}
          <AddCard
            cta="Agregar tipografía"
            isPending={createMutation.isPending}
            fields={[
              { key: "nombre", label: "Nombre", placeholder: "Nombre (ej. Título)" },
              { key: "valor", label: "Fuente", placeholder: "Nombre de la fuente (ej. Poppins)" },
              { key: "descripcion", label: "Descripción", placeholder: "Descripción (opcional)" },
            ]}
            onSubmit={(v) => createMutation.mutate({ categoria: "tipografia", nombre: v.nombre, valor: v.valor, descripcion: v.descripcion })}
          />
        </div>
        {tipografia.length === 0 && (
          <p className="text-xs text-gray-400 mt-3">Todavía no agregaste ninguna tipografía.</p>
        )}
      </section>

      {/* Embed snippet */}
      <section>
        <h2 className="text-base font-semibold text-gray-700 mb-2">Popup de cumpleaños de regalados</h2>
        <p className="text-sm text-gray-500 mb-3">
          Agrega este script en tu tienda Shopify para capturar los datos del regalo directamente.
        </p>
        <div className="bg-gray-900 rounded-xl p-4 relative">
          <code className="text-green-400 text-xs font-mono whitespace-pre-wrap break-all">
            {`<script src="${process.env.NEXT_PUBLIC_BACKEND_URL || ""}/api/forms/gift/embed.js" defer></script>`}
          </code>
          <CopyButton text={`<script src="${process.env.NEXT_PUBLIC_BACKEND_URL || ""}/api/forms/gift/embed.js" defer></script>`} />
        </div>
      </section>
    </div>
  );
}
