"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ClipboardList, Plus, Users, ExternalLink, Pencil } from "lucide-react";

interface Survey {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  status: string;
  created_at: string;
  response_count: number;
}

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "";
const PUBLIC_BASE = BACKEND
  ? BACKEND.replace("/api", "").replace(/:8\d{3}$/, "")  // strip port in prod
  : "";

function surveyUrl(slug: string) {
  return `${PUBLIC_BASE}/encuesta/${slug}`;
}

export default function EncuestasPage() {
  const { data: surveys = [], isLoading, isError, refetch } = useQuery<Survey[]>({
    queryKey: ["surveys"],
    queryFn: () => api.get("/surveys").then((r) => r.data),
  });

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Encuestas</h1>
          <p className="text-gray-500 mt-1 text-sm">Crea encuestas post compra y consulta las respuestas</p>
        </div>
        <Link
          href="/encuestas/new"
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700"
        >
          <Plus size={15} /> Nueva encuesta
        </Link>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-white border border-gray-200 rounded-xl p-5 animate-pulse h-32" />
          ))}
        </div>
      ) : isError ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
          <p className="text-red-700 text-sm mb-3">No se pudieron cargar las encuestas.</p>
          <button
            onClick={() => refetch()}
            className="text-sm text-red-600 font-medium hover:underline"
          >
            Reintentar
          </button>
        </div>
      ) : surveys.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-xl p-16 text-center">
          <ClipboardList size={32} className="text-gray-300 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">Sin encuestas aún</p>
          <Link href="/encuestas/new" className="mt-3 inline-block text-brand-600 text-sm hover:underline">
            Crear la primera
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {surveys.map((s) => (
            <div key={s.id} className="bg-white border border-gray-200 rounded-xl p-5 hover:border-gray-300 transition-all">
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="min-w-0">
                  <p className="font-semibold text-gray-900 truncate">{s.name}</p>
                  {s.description && (
                    <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{s.description}</p>
                  )}
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 font-medium ${
                  s.status === "active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                }`}>
                  {s.status === "active" ? "Activa" : "Inactiva"}
                </span>
              </div>

              <div className="flex items-center gap-1 text-xs text-gray-500 mb-4">
                <Users size={12} />
                <span>{s.response_count} respuesta{s.response_count !== 1 ? "s" : ""}</span>
              </div>

              <div className="flex gap-2">
                <Link
                  href={`/encuestas/${s.id}`}
                  className="flex-1 text-center text-xs font-medium py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                >
                  Ver respuestas
                </Link>
                <Link
                  href={`/encuestas/${s.id}/edit`}
                  className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                >
                  <Pencil size={11} /> Editar
                </Link>
                <a
                  href={surveyUrl(s.slug)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                >
                  <ExternalLink size={11} /> Link
                </a>
              </div>

              <p className="text-xs text-gray-400 mt-3 font-mono truncate">/encuesta/{s.slug}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
