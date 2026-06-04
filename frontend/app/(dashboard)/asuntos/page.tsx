"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { TrendingUp, Mail, MousePointer, Search, X, ArrowUpDown } from "lucide-react";

interface Asunto {
  id: number;
  subject: string;
  preview_text: string | null;
  campaign_name: string | null;
  campaign_id: string | null;
  open_rate: number | null;
  click_rate: number | null;
  recipients: number | null;
  opens_unique: number | null;
  send_time: string | null;
  notas: string | null;
}

function rateColor(rate: number | null): string {
  if (rate === null) return "text-gray-400";
  if (rate >= 0.45) return "text-green-600 font-bold";
  if (rate >= 0.35) return "text-green-500";
  if (rate >= 0.25) return "text-yellow-600";
  if (rate >= 0.15) return "text-orange-500";
  return "text-red-500";
}

function RateBar({ value, max = 0.6 }: { value: number | null; max?: number }) {
  if (value === null) return <div className="h-1.5 bg-gray-100 rounded-full w-24" />;
  const pct = Math.min(100, (value / max) * 100);
  const color = value >= 0.45 ? "bg-green-500" : value >= 0.35 ? "bg-green-400" : value >= 0.25 ? "bg-yellow-400" : "bg-orange-400";
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 h-1.5 bg-gray-100 rounded-full">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

type SortKey = "open_rate" | "click_rate" | "recipients" | "send_time";

export default function AsuntosPage() {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<SortKey>("open_rate");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");

  const { data: asuntos = [], isLoading } = useQuery<Asunto[]>({
    queryKey: ["asuntos"],
    queryFn: () => api.get("/analytics/asuntos").then((r) => r.data),
    staleTime: 10 * 60_000,
  });

  const filtered = asuntos
    .filter((a) => !search || a.subject.toLowerCase().includes(search.toLowerCase()) ||
      (a.campaign_name ?? "").toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const va = (a[sort] as number | string | null) ?? (sort === "open_rate" ? -1 : "");
      const vb = (b[sort] as number | string | null) ?? (sort === "open_rate" ? -1 : "");
      if (typeof va === "number" && typeof vb === "number") return sortDir === "desc" ? vb - va : va - vb;
      return sortDir === "desc" ? String(vb).localeCompare(String(va)) : String(va).localeCompare(String(vb));
    });

  const withRate = asuntos.filter((a) => a.open_rate !== null);
  const avgOpenRate = withRate.length ? withRate.reduce((s, a) => s + (a.open_rate ?? 0), 0) / withRate.length : 0;
  const bestOpenRate = withRate.length ? Math.max(...withRate.map((a) => a.open_rate ?? 0)) : 0;
  const best = withRate.find((a) => a.open_rate === bestOpenRate);

  function toggleSort(key: SortKey) {
    if (sort === key) setSortDir(d => d === "desc" ? "asc" : "desc");
    else { setSort(key); setSortDir("desc"); }
  }

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Análisis de asuntos</h1>
        <p className="text-gray-500 mt-1 text-sm">Ranking de asuntos por open rate — basado en campañas enviadas desde Klaviyo</p>
      </div>

      {/* Stats top */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Asuntos analizados</p>
          <p className="text-3xl font-bold text-gray-900">{withRate.length}</p>
          <p className="text-xs text-gray-400 mt-1">con datos de open rate</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Open rate promedio</p>
          <p className={`text-3xl font-bold ${rateColor(avgOpenRate)}`}>{(avgOpenRate * 100).toFixed(1)}%</p>
          <p className="text-xs text-gray-400 mt-1">histórico de campañas</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Mejor asunto</p>
          <p className={`text-2xl font-bold ${rateColor(bestOpenRate)}`}>{(bestOpenRate * 100).toFixed(1)}%</p>
          <p className="text-xs text-gray-500 mt-1 truncate">{best?.subject ?? "—"}</p>
        </div>
      </div>

      {/* Patrones ganadores */}
      <div className="bg-brand-50 border border-brand-200 rounded-xl p-5 mb-6">
        <p className="text-sm font-semibold text-brand-800 mb-3">Patrones de asuntos con mayor open rate</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Urgencia", ejemplo: "¡últimas 24 horas! 🔥", tip: "Funciona sobre 45%" },
            { label: "Personalización", ejemplo: "un regalito para ti 🎁", tip: "Informal y cercano" },
            { label: "Curiosidad", ejemplo: "revisa estoo", tip: "Intriga sin spoilear" },
            { label: "Evento en vivo", ejemplo: "Live: ¡por comenzar!", tip: "Urgencia real" },
          ].map((p) => (
            <div key={p.label} className="bg-white rounded-lg p-3 border border-brand-100">
              <p className="text-xs font-bold text-brand-700 mb-1">{p.label}</p>
              <p className="text-xs text-gray-700 italic mb-1">"{p.ejemplo}"</p>
              <p className="text-xs text-gray-400">{p.tip}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Tabla */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <p className="text-sm font-semibold text-gray-700">Todos los asuntos</p>
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar..."
              className="pl-8 pr-7 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 w-48"
            />
            {search && (
              <button onClick={() => setSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400">
                <X size={12} />
              </button>
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Cargando...</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs text-gray-400 uppercase tracking-wider">
                <th className="text-left px-5 py-3 font-semibold">Asunto</th>
                <th className="text-left px-3 py-3 font-semibold hidden md:table-cell">Campaña</th>
                <th className="px-3 py-3 font-semibold cursor-pointer hover:text-gray-700 text-center" onClick={() => toggleSort("open_rate")}>
                  <span className="flex items-center justify-center gap-1"><Mail size={12} /> Open % <ArrowUpDown size={11} /></span>
                </th>
                <th className="px-3 py-3 font-semibold cursor-pointer hover:text-gray-700 text-center hidden md:table-cell" onClick={() => toggleSort("click_rate")}>
                  <span className="flex items-center justify-center gap-1"><MousePointer size={12} /> Click % <ArrowUpDown size={11} /></span>
                </th>
                <th className="px-3 py-3 font-semibold cursor-pointer hover:text-gray-700 text-center hidden lg:table-cell" onClick={() => toggleSort("recipients")}>
                  <span className="flex items-center justify-center gap-1"><TrendingUp size={12} /> Enviados <ArrowUpDown size={11} /></span>
                </th>
                <th className="px-3 py-3 font-semibold text-center hidden lg:table-cell">Fecha</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((a, i) => (
                <tr key={a.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3">
                    <div className="flex items-start gap-3">
                      <span className="text-xs text-gray-300 font-mono w-5 mt-0.5">{i + 1}</span>
                      <div>
                        <p className="font-medium text-gray-900 leading-snug">{a.subject}</p>
                        {a.preview_text && <p className="text-xs text-gray-400 mt-0.5 truncate max-w-xs">{a.preview_text}</p>}
                        <RateBar value={a.open_rate} />
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-3 hidden md:table-cell">
                    <p className="text-xs text-gray-500 truncate max-w-[180px]">{a.campaign_name ?? "—"}</p>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className={`text-sm ${rateColor(a.open_rate)}`}>
                      {a.open_rate !== null ? `${(a.open_rate * 100).toFixed(1)}%` : "—"}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-center hidden md:table-cell">
                    <span className="text-sm text-gray-500">
                      {a.click_rate !== null ? `${(a.click_rate * 100).toFixed(2)}%` : "—"}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-center hidden lg:table-cell">
                    <span className="text-xs text-gray-400">{a.recipients?.toLocaleString("es-CL") ?? "—"}</span>
                  </td>
                  <td className="px-3 py-3 text-center hidden lg:table-cell">
                    <span className="text-xs text-gray-400">
                      {a.send_time ? new Date(a.send_time).toLocaleDateString("es-CL", { day: "numeric", month: "short", year: "2-digit" }) : "—"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
