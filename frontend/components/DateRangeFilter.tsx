"use client";

import { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";

export type DatePreset = "all" | "7d" | "30d" | "90d" | "custom";

const PRESETS: { key: DatePreset; label: string }[] = [
  { key: "all", label: "Todo el tiempo" },
  { key: "7d", label: "Últimos 7 días" },
  { key: "30d", label: "Últimos 30 días" },
  { key: "90d", label: "Últimos 90 días" },
  { key: "custom", label: "Personalizado" },
];

function toIso(d: Date) {
  return d.toISOString().split("T")[0];
}

function presetDates(preset: DatePreset): { from?: string; to?: string } {
  if (preset === "all") return {};
  const to = toIso(new Date());
  if (preset === "7d") return { from: toIso(new Date(Date.now() - 7 * 86400e3)), to };
  if (preset === "30d") return { from: toIso(new Date(Date.now() - 30 * 86400e3)), to };
  if (preset === "90d") return { from: toIso(new Date(Date.now() - 90 * 86400e3)), to };
  return {};
}

export function useStatsDateRange(defaultPreset: DatePreset = "all") {
  const [preset, setPreset] = useState<DatePreset>(defaultPreset);
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");

  const range = useMemo(() => {
    if (preset === "custom" && customFrom && customTo) {
      return { from: customFrom, to: customTo };
    }
    return presetDates(preset);
  }, [preset, customFrom, customTo]);

  return {
    preset,
    setPreset,
    customFrom,
    setCustomFrom,
    customTo,
    setCustomTo,
    dateFrom: range.from,
    dateTo: range.to,
  };
}

export default function DateRangeFilter({
  preset,
  setPreset,
  customFrom,
  setCustomFrom,
  customTo,
  setCustomTo,
  dateFrom,
  dateTo,
}: {
  preset: DatePreset;
  setPreset: (p: DatePreset) => void;
  customFrom: string;
  setCustomFrom: (v: string) => void;
  customTo: string;
  setCustomTo: (v: string) => void;
  dateFrom?: string;
  dateTo?: string;
}) {
  const [open, setOpen] = useState(false);
  const label = PRESETS.find((p) => p.key === preset)?.label ?? "Período";
  const dateLabel =
    preset === "all"
      ? "todos"
      : dateFrom && dateTo
        ? `${dateFrom} — ${dateTo}`
        : "";

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors shadow-sm"
      >
        <span>{label}</span>
        {dateLabel && <span className="text-gray-400 text-xs">{dateLabel}</span>}
        <ChevronDown size={14} className="text-gray-400" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 bg-white border border-gray-200 rounded-xl shadow-lg z-30 min-w-[260px] p-2">
          {PRESETS.filter((p) => p.key !== "custom").map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => {
                setPreset(p.key);
                setOpen(false);
              }}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                preset === p.key ? "bg-brand-50 text-brand-700 font-medium" : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              {p.label}
            </button>
          ))}
          <div className="border-t border-gray-100 mt-1 pt-2 px-3 space-y-2">
            <p className="text-xs font-medium text-gray-500">Personalizado</p>
            <div className="flex gap-2 items-center">
              <input
                type="date"
                value={customFrom}
                onChange={(e) => {
                  setCustomFrom(e.target.value);
                  setPreset("custom");
                }}
                className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              <span className="text-gray-400 text-xs">→</span>
              <input
                type="date"
                value={customTo}
                onChange={(e) => {
                  setCustomTo(e.target.value);
                  setPreset("custom");
                }}
                className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>
            {preset === "custom" && customFrom && customTo && (
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="w-full py-1.5 bg-brand-600 text-white rounded-lg text-xs font-medium hover:bg-brand-700"
              >
                Aplicar
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
