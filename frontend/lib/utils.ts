import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatDate(date: string | null | undefined): string {
  if (!date) return "—";
  // Date-only strings (YYYY-MM-DD) must not get "Z" appended — that makes them invalid
  const s = date.includes("T") ? (date.endsWith("Z") ? date : date + "Z") : date;
  const d = new Date(s);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("es-CL", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: date.includes("T") ? undefined : "UTC",
  });
}

export function formatDateTime(date: string | null | undefined): string {
  if (!date) return "—";
  const s = date.includes("T") ? (date.endsWith("Z") ? date : date + "Z") : date;
  const d = new Date(s);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("es-CL", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    draft: "Borrador",
    scheduled: "Programada",
    sending: "Enviando",
    paused: "Pausada",
    sent: "Enviada",
    cancelled: "Cancelada",
    queued: "En cola",
    delivered: "Entregado",
    opened: "Abierto",
    clicked: "Clic",
    bounced: "Rebotado",
    complained: "Spam",
  };
  return map[status] ?? status;
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    draft: "bg-gray-100 text-gray-700",
    scheduled: "bg-blue-100 text-blue-700",
    sending: "bg-yellow-100 text-yellow-700",
    paused: "bg-orange-100 text-orange-700",
    sent: "bg-green-100 text-green-700",
    cancelled: "bg-red-100 text-red-700",
  };
  return map[status] ?? "bg-gray-100 text-gray-600";
}
