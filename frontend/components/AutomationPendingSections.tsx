"use client";

import { AutomationPending } from "@/lib/types";
import { Clock, Users } from "lucide-react";

function timeUntil(isoDate: string): string {
  const diff = new Date(isoDate).getTime() - Date.now();
  if (diff <= 0) return "ahora";
  const mins = Math.round(diff / 60000);
  if (mins < 60) return `en ${mins} min`;
  const hrs = Math.round(diff / 3600000);
  if (hrs < 24) return `en ${hrs}h`;
  return `en ${Math.round(diff / 86400000)}d`;
}

function ContactRow({ c }: { c: AutomationPending["steps"][0]["contacts"][0] }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`px-1.5 py-0.5 rounded font-medium shrink-0 ${
        c.ready ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
      }`}>
        {c.ready ? "listo" : timeUntil(c.send_at)}
      </span>
      <span className="text-gray-700 font-medium truncate max-w-[140px]">{c.name}</span>
      <span className="text-gray-400 font-mono truncate">{c.email}</span>
      {c.detail && <span className="text-gray-400 truncate ml-auto shrink-0">{c.detail}</span>}
    </div>
  );
}

interface Props {
  pending?: AutomationPending;
  isLoading?: boolean;
  compact?: boolean;
}

export default function AutomationPendingSections({ pending, isLoading, compact }: Props) {
  const iconSize = compact ? 11 : 14;
  const titleClass = compact
    ? "text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-1.5"
    : "text-sm font-semibold text-gray-700 mb-3 flex items-center gap-1.5";

  return (
    <div className={compact ? "space-y-0" : "space-y-4 mb-6"}>
      {pending?.will_enter != null && (
        <div className={compact ? "bg-violet-50 px-5 py-3 border-b border-violet-100" : "bg-violet-50 border border-violet-100 rounded-xl px-4 py-3 mb-4"}>
          {!compact && (
            <h2 className={titleClass}>
              <Users size={iconSize} className="text-violet-500" />
              Entrarán al flujo
            </h2>
          )}
          {compact && (
            <p className="text-xs font-semibold text-violet-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Users size={iconSize} /> Entrarán al flujo
            </p>
          )}
          <div className={`${compact ? "" : "bg-violet-50 border border-violet-100 rounded-xl px-4 py-3"}`}>
            {isLoading ? (
              <p className="text-xs text-violet-400">Cargando...</p>
            ) : (
              <p className={`${compact ? "text-xs" : "text-sm"} text-violet-800`}>
                <span className="font-bold text-lg mr-1">{pending.will_enter.count.toLocaleString("es-CL")}</span>
                persona{pending.will_enter.count !== 1 ? "s" : ""} recibirán este flujo en el futuro
              </p>
            )}
          </div>
        </div>
      )}

      <div className={compact ? "bg-blue-50 px-5 py-3" : "bg-blue-50 border border-blue-100 rounded-xl px-4 py-3"}>
        <h2 className={compact ? "text-xs font-semibold text-blue-700 uppercase tracking-wider mb-2 flex items-center gap-1.5" : titleClass}>
          <Clock size={iconSize} className="text-blue-500" />
          Próximos envíos
          {pending && pending.count > 0 && (
            <span className="ml-1 bg-blue-600 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">
              {pending.count}
            </span>
          )}
        </h2>
        {isLoading ? (
          <p className="text-xs text-blue-400">Cargando...</p>
        ) : !pending || pending.count === 0 ? (
          <p className="text-xs text-blue-400">No hay envíos pendientes.</p>
        ) : (
          <div className={`space-y-3 ${compact ? "max-h-48" : "max-h-64"} overflow-y-auto`}>
            {pending.steps.map((group) => (
              <div key={group.step}>
                <p className="text-xs font-semibold text-blue-800 mb-1.5 flex items-center gap-1.5">
                  Paso {group.step}
                  <span className="bg-blue-200 text-blue-800 text-xs font-bold px-1.5 py-0.5 rounded-full">
                    {group.count}
                  </span>
                </p>
                <div className={`space-y-1 ${compact ? "" : "bg-blue-50/80 border border-blue-100 rounded-lg px-3 py-2"}`}>
                  {group.contacts.map((c, i) => (
                    <ContactRow key={`${group.step}-${i}`} c={c} />
                  ))}
                  {group.count > group.contacts.length && (
                    <p className="text-xs text-blue-500 pt-0.5">
                      +{group.count - group.contacts.length} más
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
