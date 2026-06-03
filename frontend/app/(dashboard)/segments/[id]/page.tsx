"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { segmentsApi } from "@/lib/api";
import { Segment, Contact } from "@/lib/types";
import { ArrowLeft, Users, Trash2, Filter } from "lucide-react";
import Link from "next/link";
import { formatDate } from "@/lib/utils";

export default function SegmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const segId = Number(id);

  const { data: segment, isLoading: loadingSeg, isError: errorSeg } = useQuery<Segment>({
    queryKey: ["segment", segId],
    queryFn: () => segmentsApi.get(segId).then((r) => r.data),
    staleTime: 2 * 60_000,
  });

  const { data: contacts = [], isLoading: loadingContacts } = useQuery<Contact[]>({
    queryKey: ["segment-preview", segId],
    queryFn: () => segmentsApi.preview(segId).then((r) => r.data),
    staleTime: 2 * 60_000,
    enabled: !!segId,
  });

  const deleteMutation = useMutation({
    mutationFn: () => segmentsApi.delete(segId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["segments"] });
      router.push("/segments");
    },
  });

  if (loadingSeg) {
    return (
      <div className="p-8">
        <div className="h-6 bg-gray-200 rounded w-48 animate-pulse mb-4" />
        <div className="h-4 bg-gray-100 rounded w-64 animate-pulse" />
      </div>
    );
  }

  if (errorSeg || !segment) {
    return (
      <div className="p-8">
        <Link href="/segments" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-6">
          <ArrowLeft size={15} /> Volver a segmentos
        </Link>
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          No se encontró el segmento.
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl">
      <Link href="/segments" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-6">
        <ArrowLeft size={15} /> Volver a segmentos
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center flex-shrink-0">
            <Filter size={20} className="text-purple-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{segment.name}</h1>
            {segment.description && (
              <p className="text-gray-500 text-sm mt-1">{segment.description}</p>
            )}
            <div className="flex items-center gap-1 mt-2 text-sm font-semibold text-gray-900">
              <Users size={14} className="text-gray-400" />
              {segment.contact_count?.toLocaleString() ?? "—"} contactos
            </div>
          </div>
        </div>
        <button
          onClick={() => {
            if (confirm(`¿Eliminar segmento "${segment.name}"?`)) deleteMutation.mutate();
          }}
          disabled={deleteMutation.isPending}
          className="flex items-center gap-2 px-3 py-2 border border-red-200 text-red-600 rounded-lg text-sm font-medium hover:bg-red-50 disabled:opacity-50 transition-colors"
        >
          <Trash2 size={14} /> Eliminar
        </button>
      </div>

      {/* Contacts preview */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">
            Contactos en este segmento
            {segment.contact_count != null && segment.contact_count > 20 && (
              <span className="ml-2 text-xs font-normal text-gray-400">(mostrando primeros 20 de {segment.contact_count.toLocaleString()})</span>
            )}
          </h2>
        </div>

        {loadingContacts ? (
          <div className="divide-y divide-gray-50">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="px-6 py-3 flex items-center gap-3 animate-pulse">
                <div className="w-8 h-8 bg-gray-200 rounded-full" />
                <div>
                  <div className="h-3.5 bg-gray-200 rounded w-32 mb-1.5" />
                  <div className="h-3 bg-gray-100 rounded w-48" />
                </div>
              </div>
            ))}
          </div>
        ) : contacts.length === 0 ? (
          <div className="p-12 text-center">
            <Users size={36} className="mx-auto text-gray-200 mb-3" />
            <p className="text-gray-400 text-sm">Ningún contacto coincide con este segmento.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nombre / Email</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Visitas</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Última visita</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Origen</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Opt-in</th>
              </tr>
            </thead>
            <tbody>
              {contacts.map((c) => (
                <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-6 py-3">
                    <Link href={`/contacts/${c.id}`} className="hover:underline">
                      <p className="font-medium text-gray-900">{c.name || "Sin nombre"}</p>
                      <p className="text-gray-400 text-xs">{c.email}</p>
                    </Link>
                  </td>
                  <td className="px-6 py-3 text-gray-700">{c.veces_hotboat} pedido{c.veces_hotboat !== 1 ? "s" : ""}</td>
                  <td className="px-6 py-3 text-gray-500 text-xs">{formatDate(c.ultima_visita)}</td>
                  <td className="px-6 py-3 text-gray-500 text-xs">{c.origin_utm || "—"}</td>
                  <td className="px-6 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${c.opted_in ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                      {c.opted_in ? "Activo" : "Baja"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="text-xs text-gray-400 mt-4">Segmento creado el {formatDate(segment.created_at)}</p>
    </div>
  );
}
