"use client";

import { useQuery } from "@tanstack/react-query";
import { Users, Loader2 } from "lucide-react";
import { campaignsApi } from "@/lib/api";
import { CampaignAudiencePreview } from "@/lib/types";

type Props = {
  segmentId: number;
  excludeSegmentIds: number[];
  className?: string;
};

export function CampaignAudienceSummary({ segmentId, excludeSegmentIds, className = "" }: Props) {
  const excludeKey = [...excludeSegmentIds].sort((a, b) => a - b).join(",");

  const { data, isLoading, isError } = useQuery<CampaignAudiencePreview>({
    queryKey: ["campaign-audience", segmentId, excludeKey],
    queryFn: () =>
      campaignsApi
        .audiencePreview({
          segment_id: segmentId,
          exclude_segment_ids: excludeSegmentIds,
        })
        .then((r) => r.data),
    enabled: segmentId > 0,
    staleTime: 30_000,
  });

  if (segmentId <= 0) return null;

  return (
    <div className={`rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 ${className}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-lg bg-white p-2 text-brand-600 shadow-sm">
          {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Users size={16} />}
        </div>
        <div className="min-w-0 flex-1">
          {isLoading && (
            <p className="text-sm font-medium text-brand-900">Calculando audiencia…</p>
          )}
          {isError && (
            <p className="text-sm text-red-600">No se pudo calcular la audiencia.</p>
          )}
          {!isLoading && !isError && data && (
            <>
              <p className="text-sm font-semibold text-brand-900">
                {data.recipient_count.toLocaleString("es-CL")}{" "}
                {data.recipient_count === 1 ? "persona recibirá" : "personas recibirán"} esta campaña
              </p>
              <p className="mt-1 text-xs text-brand-700/80">
                {data.segment_count.toLocaleString("es-CL")} en el segmento
                {data.excluded_count > 0 && (
                  <>
                    {" · "}
                    {data.excluded_count.toLocaleString("es-CL")} excluidas por los segmentos seleccionados
                  </>
                )}
              </p>
              {data.recipient_count === 0 && (
                <p className="mt-1 text-xs font-medium text-red-600">
                  No hay destinatarios. Revisa el segmento o las exclusiones.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
