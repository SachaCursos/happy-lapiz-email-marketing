"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Copy, Check } from "lucide-react";
import { useState } from "react";

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

export default function BrandPage() {
  const { data, isLoading } = useQuery<BrandAssets>({
    queryKey: ["brand-assets"],
    queryFn: () => api.get("/admin/brand").then((r) => r.data),
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
          Activos oficiales de Happy Lápiz para usar en campañas de email.
        </p>
      </div>

      {/* Logos */}
      <section>
        <h2 className="text-base font-semibold text-gray-700 mb-4">Logos</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {logos.map((logo) => (
            <div key={logo.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
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
        </div>
      </section>

      {/* Colores */}
      <section>
        <h2 className="text-base font-semibold text-gray-700 mb-4">Paleta de colores</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {colores.map((color) => (
            <div key={color.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
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
        </div>
      </section>

      {/* Tipografía */}
      <section>
        <h2 className="text-base font-semibold text-gray-700 mb-4">Tipografía</h2>
        <div className="space-y-3">
          {tipografia.map((tipo) => (
            <div key={tipo.id} className="bg-white border border-gray-200 rounded-xl p-5 flex items-center justify-between">
              <div>
                <p
                  className="text-gray-900 mb-1"
                  style={{ fontFamily: tipo.valor, fontSize: tipo.nombre.includes("Título") ? "28px" : "20px", fontWeight: tipo.nombre.includes("Título") ? 700 : 600 }}
                >
                  {tipo.nombre} — {tipo.valor}
                </p>
                <p className="text-xs text-gray-400">{tipo.descripcion}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0 ml-4">
                <code className="text-xs bg-gray-100 px-2 py-1 rounded text-gray-600">{tipo.valor}</code>
                <CopyButton text={tipo.valor} />
              </div>
            </div>
          ))}
        </div>
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
