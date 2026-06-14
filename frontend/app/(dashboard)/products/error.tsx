"use client";

import { useEffect } from "react";
import { Package } from "lucide-react";

export default function ProductsError({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    console.error("Products page error:", error);
  }, [error]);

  return (
    <div className="p-8 max-w-7xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Catálogo Shopify</h1>
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <Package size={40} className="text-gray-300" />
        <p className="text-gray-600 font-medium">Error al cargar la página</p>
        <p className="text-sm text-gray-400 max-w-sm text-center">{error.message}</p>
        <button
          onClick={reset}
          className="mt-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          Reintentar
        </button>
      </div>
    </div>
  );
}
