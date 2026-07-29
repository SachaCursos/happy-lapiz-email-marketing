"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { emailLogApi } from "@/lib/api";
import { EmailLogEntry, EmailLogList, EmailLogDetail, EmailLogSource } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";
import { Mail, Search, ChevronLeft, ChevronRight, X } from "lucide-react";

const PAGE_SIZE = 50;

const SOURCE_LABEL: Record<EmailLogSource, string> = {
  campaign: "Campaña",
  automation: "Automatización",
  evergreen: "Evergreen",
};

const STATUS_STYLE: Record<string, string> = {
  queued: "bg-gray-100 text-gray-500",
  sent: "bg-blue-50 text-blue-600",
  delivered: "bg-green-50 text-green-700",
  opened: "bg-emerald-50 text-emerald-700",
  clicked: "bg-purple-50 text-purple-700",
  bounced: "bg-red-50 text-red-600",
  complained: "bg-red-50 text-red-700",
  failed: "bg-red-50 text-red-600",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[status] || "bg-gray-100 text-gray-500"}`}>
      {status}
    </span>
  );
}

function useDebounced(value: string, delayMs: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

function DetailModal({ source, id, onClose }: { source: EmailLogSource; id: number; onClose: () => void }) {
  const { data, isLoading } = useQuery<EmailLogDetail>({
    queryKey: ["email-log-detail", source, id],
    queryFn: () => emailLogApi.detail(source, id).then((r) => r.data),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 flex flex-col"
        style={{ maxHeight: "90vh" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between px-6 py-4 border-b border-gray-100">
          <div className="min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{data?.subject || "(sin asunto)"}</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              {data ? `${data.contact_email} · ${SOURCE_LABEL[data.source]} "${data.source_name}"` : "Cargando..."}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 transition-colors shrink-0 ml-4">
            <X size={20} />
          </button>
        </div>

        {data && (
          <div className="px-6 py-3 border-b border-gray-100 flex flex-wrap items-center gap-2 text-xs text-gray-500">
            <StatusBadge status={data.status} />
            {data.send_provider && <span className="uppercase text-gray-400">{data.send_provider}</span>}
            {data.sent_at && <span>Enviado: {formatDateTime(data.sent_at)}</span>}
            {data.delivered_at && <span>Entregado: {formatDateTime(data.delivered_at)}</span>}
            {data.opened_at && <span>Abierto: {formatDateTime(data.opened_at)}</span>}
            {data.clicked_at && <span>Click: {formatDateTime(data.clicked_at)}</span>}
            {data.bounced_at && <span className="text-red-500">Rebotado: {formatDateTime(data.bounced_at)}</span>}
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="h-64 flex items-center justify-center text-gray-400 text-sm">Cargando...</div>
          ) : !data?.has_snapshot ? (
            <div className="h-64 flex flex-col items-center justify-center text-gray-400 text-sm gap-2">
              <Mail size={28} className="text-gray-300" />
              Contenido no disponible — este envío es anterior al visor de correos.
            </div>
          ) : (
            <iframe
              srcDoc={data.html ?? undefined}
              sandbox="allow-same-origin"
              title={data.subject || "email"}
              className="w-full rounded-lg border border-gray-100"
              style={{ minHeight: "300px", height: "700px" }}
              onLoad={(e) => {
                const f = e.currentTarget;
                try {
                  const h = f.contentDocument?.documentElement?.scrollHeight;
                  if (h && h > 0) f.style.height = h + "px";
                } catch {}
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export default function EmailLogPage() {
  const [emailInput, setEmailInput] = useState("");
  const [subjectInput, setSubjectInput] = useState("");
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<{ source: EmailLogSource; id: number } | null>(null);

  const email = useDebounced(emailInput, 300);
  const subject = useDebounced(subjectInput, 300);

  const { data, isLoading, isError, refetch } = useQuery<EmailLogList>({
    queryKey: ["email-log", email, subject, status, source, dateFrom, dateTo, page],
    queryFn: () =>
      emailLogApi
        .list({
          email: email || undefined,
          subject: subject || undefined,
          status: status || undefined,
          source: source || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          page: page + 1,
          page_size: PAGE_SIZE,
        })
        .then((r) => r.data),
    staleTime: 30_000,
    retry: 1,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const hasNextPage = (page + 1) * PAGE_SIZE < total;
  const hasPrevPage = page > 0;

  function resetPage<T>(setter: (v: T) => void) {
    return (v: T) => { setter(v); setPage(0); };
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Correos enviados</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Campañas, automatizaciones y evergreen — {total.toLocaleString()} envíos
          </p>
        </div>
      </div>

      {isError && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 flex items-center justify-between">
          <span>Error al cargar los envíos.</span>
          <button onClick={() => refetch()} className="text-xs font-medium underline">Reintentar</button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-3.5 border-b border-gray-100 flex flex-wrap items-center gap-2.5">
          <div className="relative flex-1 min-w-[200px] max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={emailInput}
              onChange={(e) => resetPage(setEmailInput)(e.target.value)}
              placeholder="Buscar por email..."
              className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
          <div className="relative flex-1 min-w-[200px] max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={subjectInput}
              onChange={(e) => resetPage(setSubjectInput)(e.target.value)}
              placeholder="Buscar por asunto..."
              className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
          <select
            value={source}
            onChange={(e) => resetPage(setSource)(e.target.value)}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Todos los orígenes</option>
            <option value="campaign">Campañas</option>
            <option value="automation">Automatizaciones</option>
            <option value="evergreen">Evergreen</option>
          </select>
          <select
            value={status}
            onChange={(e) => resetPage(setStatus)(e.target.value)}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Todos los estados</option>
            <option value="sent">Enviado</option>
            <option value="delivered">Entregado</option>
            <option value="opened">Abierto</option>
            <option value="clicked">Click</option>
            <option value="bounced">Rebotado</option>
            <option value="complained">Queja</option>
            <option value="failed">Falló</option>
          </select>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => resetPage(setDateFrom)(e.target.value)}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <span className="text-gray-400 text-sm">–</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => resetPage(setDateTo)(e.target.value)}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div className="overflow-x-auto">
          <table className="text-sm" style={{ minWidth: "900px", width: "100%" }}>
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Email</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Fecha</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Asunto</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Origen</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Estado</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                [...Array(8)].map((_, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="px-5 py-3"><div className="h-4 bg-gray-100 rounded w-44 animate-pulse" /></td>
                    <td className="px-5 py-3"><div className="h-4 bg-gray-100 rounded w-28 animate-pulse" /></td>
                    <td className="px-5 py-3"><div className="h-4 bg-gray-100 rounded w-64 animate-pulse" /></td>
                    <td className="px-5 py-3"><div className="h-4 bg-gray-100 rounded w-24 animate-pulse" /></td>
                    <td className="px-5 py-3"><div className="h-5 bg-gray-100 rounded-full w-16 animate-pulse" /></td>
                  </tr>
                ))
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-16 text-center">
                    <Mail size={36} className="mx-auto text-gray-300 mb-3" />
                    <p className="text-gray-500 font-medium">Sin envíos</p>
                    <p className="text-gray-400 text-xs mt-1">Ajusta los filtros o vuelve más tarde</p>
                  </td>
                </tr>
              ) : (
                items.map((it: EmailLogEntry) => (
                  <tr
                    key={`${it.source}-${it.id}`}
                    onClick={() => setSelected({ source: it.source, id: it.id })}
                    className="border-b border-gray-100 hover:bg-gray-50 transition-colors cursor-pointer"
                  >
                    <td className="px-5 py-3 text-gray-700 text-xs whitespace-nowrap">{it.contact_email}</td>
                    <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">{formatDateTime(it.sent_at)}</td>
                    <td className="px-5 py-3 text-gray-700 text-xs max-w-xs truncate">
                      {it.subject || <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-5 py-3 text-gray-500 text-xs whitespace-nowrap">
                      {SOURCE_LABEL[it.source]}
                      <span className="text-gray-300 ml-1">· {it.source_name}</span>
                    </td>
                    <td className="px-5 py-3 whitespace-nowrap"><StatusBadge status={it.status} /></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

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

      {selected && (
        <DetailModal source={selected.source} id={selected.id} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
