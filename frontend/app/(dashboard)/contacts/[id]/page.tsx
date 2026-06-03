"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { contactsApi } from "@/lib/api";
import { Contact, ContactBooking, CampaignEmailSend } from "@/lib/types";
import { formatDate, formatDateTime } from "@/lib/utils";
import {
  ArrowLeft, Mail, Calendar, StickyNote, Save, Plus, Trash2, Search,
  MousePointerClick, CheckCircle, AlertTriangle, TrendingUp,
  ChevronDown, ChevronUp, Anchor, XCircle,
} from "lucide-react";
import Link from "next/link";

// ─── helpers ─────────────────────────────────────────────────────────────────
function initials(name: string | null, email: string) {
  if (name) return name.split(" ").slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return email[0].toUpperCase();
}

const BOOKING_STATUS_COLOR: Record<string, string> = {
  completed: "bg-green-100 text-green-700",
  confirmed: "bg-blue-100 text-blue-700",
  pending:   "bg-yellow-100 text-yellow-700",
  cancelled: "bg-red-100 text-red-700",
  no_show:   "bg-gray-100 text-gray-500",
};

function Tick({ yes, date }: { yes: boolean; date?: string | null }) {
  if (yes) return (
    <span title={date ?? undefined} className="inline-flex items-center gap-1 text-green-600 font-medium text-xs">
      <CheckCircle size={13} /> Sí
    </span>
  );
  return <span className="inline-flex items-center gap-1 text-gray-300 text-xs"><XCircle size={13} /> —</span>;
}

const PREDEFINED = [
  { key: "acompanantes",        label: "Nombres de acompañantes",    placeholder: "ej. Ana García, Pedro García" },
  { key: "hijos",               label: "Nombres de hijos",           placeholder: "ej. Sofía (8), Mateo (5)" },
  { key: "cumple_acompanantes", label: "Cumpleaños acompañantes",    placeholder: "ej. Ana 15/03" },
  { key: "cumple_hijos",        label: "Cumpleaños hijos",           placeholder: "ej. Sofía 10/04" },
  { key: "actividades",         label: "Actividades favoritas",      placeholder: "ej. wakeboard, snorkel" },
  { key: "alergias",            label: "Alergias / restricciones",   placeholder: "ej. sin gluten" },
];

// ─── Tab button ───────────────────────────────────────────────────────────────
function Tab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
        active
          ? "border-gray-900 text-gray-900"
          : "border-transparent text-gray-500 hover:text-gray-700"
      }`}
    >
      {label}
    </button>
  );
}

// ─── Custom fields editor ─────────────────────────────────────────────────────
function CustomPropertiesCard({ contact, onSave, saving }: {
  contact: Contact;
  onSave: (fields: Record<string, string>, notes: string, birthday: string) => void;
  saving: boolean;
}) {
  const [fields,   setFields]   = useState<Record<string, string>>(contact.custom_fields ?? {});
  const [notes,    setNotes]    = useState(contact.notes ?? "");
  const [birthday, setBirthday] = useState(contact.birthday ?? "");
  const [newKey,   setNewKey]   = useState("");

  const predefinedKeys = PREDEFINED.map((p) => p.key);
  const customKeys = Object.keys(fields).filter((k) => !predefinedKeys.includes(k));
  const dirty =
    JSON.stringify(fields) !== JSON.stringify(contact.custom_fields ?? {}) ||
    notes !== (contact.notes ?? "") ||
    birthday !== (contact.birthday ?? "");

  const set = (key: string, val: string) => setFields((p) => ({ ...p, [key]: val }));
  const remove = (key: string) => setFields((p) => { const n = { ...p }; delete n[key]; return n; });
  const addKey = () => {
    const k = newKey.trim().toLowerCase().replace(/\s+/g, "_");
    if (!k || fields[k] !== undefined) return;
    setFields((p) => ({ ...p, [k]: "" }));
    setNewKey("");
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-3.5 border-b border-gray-100 flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <StickyNote size={14} className="text-gray-400" /> Propiedades personalizadas
        </span>
        {dirty && (
          <button
            onClick={() => onSave(fields, notes, birthday)}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 text-white rounded-lg text-xs font-medium hover:bg-brand-700 disabled:opacity-60"
          >
            <Save size={11} /> {saving ? "Guardando…" : "Guardar"}
          </button>
        )}
      </div>
      <div className="p-5 space-y-3.5">
        <div>
          <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1">Cumpleaños</label>
          <input type="date" value={birthday} onChange={(e) => setBirthday(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        {PREDEFINED.map(({ key, label, placeholder }) => (
          <div key={key}>
            <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1">{label}</label>
            <input type="text" value={fields[key] ?? ""} onChange={(e) => set(key, e.target.value)}
              placeholder={placeholder}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
        ))}
        {customKeys.map((key) => (
          <div key={key}>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-gray-400 uppercase tracking-wider">{key}</label>
              <button onClick={() => remove(key)}><Trash2 size={11} className="text-red-400 hover:text-red-600" /></button>
            </div>
            <input type="text" value={fields[key]} onChange={(e) => set(key, e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>
        ))}
        <div className="flex gap-2">
          <input type="text" value={newKey} onChange={(e) => setNewKey(e.target.value)}
            placeholder="+ Añadir campo personalizado"
            onKeyDown={(e) => e.key === "Enter" && addKey()}
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500" />
          {newKey && (
            <button onClick={addKey}
              className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-xs font-medium text-gray-700">
              <Plus size={12} />
            </button>
          )}
        </div>
        <div className="pt-2 border-t border-gray-100">
          <label className="block text-xs text-gray-400 uppercase tracking-wider mb-1">Notas internas</label>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3}
            placeholder="Notas privadas (no se envían en emails)"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
      </div>
    </div>
  );
}

// ─── Tab 1: Detalles ──────────────────────────────────────────────────────────
function DetailsTab({ contact, onSave, saving }: {
  contact: Contact;
  onSave: (fields: Record<string, string>, notes: string, birthday: string) => void;
  saving: boolean;
}) {
  const { data: sends = [], isLoading: sendsLoading } = useQuery<CampaignEmailSend[]>({
    queryKey: ["contact-email-sends", contact.id],
    queryFn: () => contactsApi.emailSends(contact.id).then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  return (
    <div className="grid grid-cols-5 gap-5">
      {/* Left — info cards */}
      <div className="col-span-3 space-y-4">

        {/* Information */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Información</p>

          <p className="text-xs font-semibold text-gray-500 mb-2">Detalles del perfil</p>
          <div className="space-y-2 mb-5">
            {[
              ["ID único",    String(contact.id)],
              ["Idioma",      contact.language === "es" ? "es-CL" : contact.language ?? null],
              ["Ubicación",   contact.location],
              ["Zona horaria","America/Santiago"],
            ].map(([label, value]) => value ? (
              <div key={label} className="flex gap-3 text-sm">
                <span className="w-28 text-gray-400 shrink-0">{label}</span>
                <span className="text-gray-700">{value}</span>
              </div>
            ) : null)}
          </div>

          <p className="text-xs font-semibold text-gray-500 mb-2">Cómo te encontró</p>
          <div className="space-y-2 mb-5">
            {[
              ["Fuente",    contact.origin_utm],
              ["Campaña",   null],
              ["Medio",     null],
            ].map(([label, value]) => (
              <div key={label} className="flex gap-3 text-sm">
                <span className="w-28 text-gray-400 shrink-0">{label}</span>
                <span className="text-gray-500">{value ?? "—"}</span>
              </div>
            ))}
          </div>

          <p className="text-xs font-semibold text-gray-500 mb-2">Actividad</p>
          <div className="space-y-2">
            {[
              ["Perfil creado",   formatDateTime(contact.created_at)],
              ["Perfil actualizado", formatDateTime(contact.updated_at)],
              ["Primer opt-in",  contact.opted_in_at  ? formatDateTime(contact.opted_in_at)  : null],
              ["Última visita",  contact.ultima_visita ? formatDate(contact.ultima_visita) : null],
            ].map(([label, value]) => value ? (
              <div key={label} className="flex gap-3 text-sm">
                <span className="w-36 text-gray-400 shrink-0">{label}</span>
                <span className="text-gray-700">{value}</span>
              </div>
            ) : null)}
          </div>
        </div>

        {/* Custom properties */}
        <CustomPropertiesCard contact={contact} onSave={onSave} saving={saving} />
      </div>

      {/* Right — email sends table */}
      <div className="col-span-2">
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden sticky top-4">
          <div className="px-5 py-3.5 border-b border-gray-100 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-700">Emails enviados</span>
            {sends.length > 0 && (
              <span className="text-xs text-gray-400">{sends.length} campaña{sends.length !== 1 ? "s" : ""}</span>
            )}
          </div>

          {sendsLoading ? (
            <div className="p-6 space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : sends.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-400">
              <Mail size={28} className="mx-auto text-gray-300 mb-2" />
              Aún no se ha enviado ningún email a este contacto
            </div>
          ) : (
            <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-gray-50 border-b border-gray-100">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-semibold text-gray-500 uppercase tracking-wider">Campaña</th>
                    <th className="px-3 py-2.5 text-center font-semibold text-gray-500 uppercase tracking-wider">
                      <span title="¿Llegó al inbox?"><CheckCircle size={12} className="mx-auto" /></span>
                    </th>
                    <th className="px-3 py-2.5 text-center font-semibold text-gray-500 uppercase tracking-wider">
                      <span title="¿Abrió el email?"><Mail size={12} className="mx-auto" /></span>
                    </th>
                    <th className="px-3 py-2.5 text-center font-semibold text-gray-500 uppercase tracking-wider">
                      <span title="¿Hizo clic?"><MousePointerClick size={12} className="mx-auto" /></span>
                    </th>
                    <th className="px-3 py-2.5 text-center font-semibold text-gray-500 uppercase tracking-wider">
                      <span title="¿Rebotó?"><AlertTriangle size={12} className="mx-auto" /></span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {sends.map((s, i) => (
                    <tr key={i} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-800 truncate max-w-[140px]" title={s.campaign_name}>
                          {s.campaign_name}
                        </p>
                        {s.sent_at && (
                          <p className="text-gray-400 mt-0.5">{formatDateTime(s.sent_at)}</p>
                        )}
                      </td>
                      <td className="px-3 py-3 text-center">
                        <Tick yes={!!s.delivered_at} date={s.delivered_at} />
                      </td>
                      <td className="px-3 py-3 text-center">
                        <Tick yes={!!s.opened_at} date={s.opened_at} />
                      </td>
                      <td className="px-3 py-3 text-center">
                        <Tick yes={!!s.clicked_at} date={s.clicked_at} />
                      </td>
                      <td className="px-3 py-3 text-center">
                        {s.bounced_at
                          ? <span className="inline-flex items-center gap-1 text-red-500 text-xs"><AlertTriangle size={12} /> Sí</span>
                          : <span className="text-gray-300 text-xs">—</span>
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Tab 2: Métricas ──────────────────────────────────────────────────────────
function MetricsTab({ contact }: { contact: Contact }) {
  const [period, setPeriod] = useState<"30" | "all">("all");

  const { data: bookings = [], isLoading } = useQuery<ContactBooking[]>({
    queryKey: ["contact-bookings", contact.id],
    queryFn: () => contactsApi.bookings(contact.id).then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  const cutoff = period === "30"
    ? new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
    : null;

  const filtered = cutoff
    ? bookings.filter((b) => new Date(b.fecha) >= cutoff)
    : bookings;

  const confirmedFiltered = filtered.filter((b) =>
    !["cancelled", "no_show", "pending"].includes(b.status)
  );

  const totalRevenue = confirmedFiltered.reduce((s, b) => s + (b.ingreso_total ?? 0), 0);
  const avgTicket    = confirmedFiltered.length
    ? totalRevenue / confirmedFiltered.length
    : (contact.ticket_medio ?? 0);

  // Predictive analytics (computed from available data)
  const historicCLV   = contact.veces_hotboat * (contact.ticket_medio ?? 0);
  const daysSinceVisit = contact.ultima_visita
    ? Math.floor((Date.now() - new Date(contact.ultima_visita).getTime()) / 86_400_000)
    : null;

  const churnRisk = daysSinceVisit === null ? null
    : daysSinceVisit <= 30  ? { label: "Bajo",     pct: 5,  color: "bg-green-500" }
    : daysSinceVisit <= 60  ? { label: "Medio",    pct: 30, color: "bg-yellow-400" }
    : daysSinceVisit <= 90  ? { label: "Alto",     pct: 60, color: "bg-orange-500" }
    : daysSinceVisit <= 180 ? { label: "Muy alto", pct: 80, color: "bg-red-500" }
    :                         { label: "Crítico",  pct: 95, color: "bg-red-700" };

  // Expected next visit: ultima_visita + avg interval (approx 365/veces days)
  const expectedNext = contact.ultima_visita && contact.veces_hotboat > 0
    ? new Date(new Date(contact.ultima_visita).getTime() + (365 / Math.max(contact.veces_hotboat, 1)) * 86_400_000)
    : null;

  const predictedCLV = contact.ticket_medio && contact.veces_hotboat > 0
    ? historicCLV + contact.ticket_medio * Math.max(1, Math.round(contact.veces_hotboat * 0.3))
    : null;

  return (
    <div className="space-y-5">
      {/* Métricas header */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-700">Métricas</span>
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-xs font-medium">
            {(["30", "all"] as const).map((p) => (
              <button key={p} onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 transition-colors ${period === p ? "bg-gray-900 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}>
                {p === "30" ? "30 días" : "Todo"}
              </button>
            ))}
          </div>
        </div>

        <div className="p-5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Métricas destacadas</p>
          <div className="grid grid-cols-3 gap-3 mb-5">
            {[
              { label: "Reservas",      value: confirmedFiltered.length,                              sub: "confirmadas" },
              { label: "Revenue",       value: `CLP ${Math.round(totalRevenue).toLocaleString("es-CL")}`, sub: "ingresos totales" },
              { label: "Ticket medio",  value: avgTicket ? `CLP ${Math.round(avgTicket).toLocaleString("es-CL")}` : "—", sub: "por reserva" },
            ].map(({ label, value, sub }) => (
              <div key={label} className="border border-gray-200 rounded-xl p-4">
                <p className="text-xl font-bold text-gray-900">{value}</p>
                <p className="text-xs text-gray-500 mt-1">{label}</p>
                <p className="text-xs text-gray-400">{sub}</p>
              </div>
            ))}
          </div>

          {/* Bookings list */}
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Historial de reservas</p>
          {isLoading ? (
            <div className="text-xs text-gray-400 py-4">Cargando…</div>
          ) : filtered.length === 0 ? (
            <div className="text-xs text-gray-400 py-4">
              {period === "30" ? "Sin reservas en los últimos 30 días." : "Sin reservas registradas."}
            </div>
          ) : (
            <div className="border border-gray-100 rounded-lg divide-y divide-gray-50">
              {filtered.map((b, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-3">
                  <Calendar size={14} className="text-gray-300 shrink-0" />
                  <span className="text-sm text-gray-700 flex-1">{b.fecha}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${BOOKING_STATUS_COLOR[b.status] ?? "bg-gray-100 text-gray-600"}`}>
                    {b.status}
                  </span>
                  {b.ingreso_total != null && (
                    <span className="text-sm font-semibold text-gray-800">
                      CLP {b.ingreso_total.toLocaleString("es-CL")}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Predictive analytics */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
          <TrendingUp size={15} className="text-brand-600" />
          <span className="text-sm font-semibold text-gray-700">Análisis predictivo</span>
          <span className="ml-1 px-2 py-0.5 bg-brand-50 text-brand-700 text-xs rounded-full font-medium">Estimado</span>
        </div>
        <div className="p-5">
          {/* CLV */}
          <div className="mb-5">
            <p className="text-3xl font-bold text-gray-900">
              {predictedCLV ? `CLP ${Math.round(predictedCLV).toLocaleString("es-CL")}` : "—"}
            </p>
            <p className="text-xs text-gray-400 mt-0.5">Customer Lifetime Value (CLV)</p>
            {historicCLV > 0 && (
              <div className="mt-3 space-y-1.5">
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-brand-600 h-2 rounded-full"
                    style={{ width: predictedCLV ? `${Math.min(100, (historicCLV / predictedCLV) * 100)}%` : "100%" }}
                  />
                </div>
                <div className="flex gap-4 text-xs text-gray-500">
                  <span>✓ CLV histórico (CLP {Math.round(historicCLV).toLocaleString("es-CL")}, {contact.veces_hotboat} reservas)</span>
                </div>
                {predictedCLV && predictedCLV > historicCLV && (
                  <div className="text-xs text-gray-400">
                    ✓ CLV proyectado (CLP {Math.round(predictedCLV - historicCLV).toLocaleString("es-CL")} adicional estimado)
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            {[
              ["Próxima visita estimada", expectedNext ? formatDate(expectedNext.toISOString()) : "—"],
              ["Ticket promedio",         contact.ticket_medio ? `CLP ${Math.round(contact.ticket_medio).toLocaleString("es-CL")}` : "—"],
            ].map(([label, value]) => (
              <div key={label}>
                <p className="text-xs text-gray-400 mb-0.5">{label}</p>
                <p className="text-sm font-semibold text-gray-800">{value}</p>
              </div>
            ))}
          </div>

          {/* Churn risk */}
          {churnRisk && (
            <div className="mt-5 pt-4 border-t border-gray-100">
              <p className="text-xs text-gray-400 mb-2">Riesgo de churn</p>
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div className={`h-2 rounded-full ${churnRisk.color}`} style={{ width: `${churnRisk.pct}%` }} />
                </div>
                <span className="text-sm font-semibold text-gray-700 w-20 text-right">
                  {churnRisk.label} ({churnRisk.pct}%)
                </span>
              </div>
              {daysSinceVisit !== null && (
                <p className="text-xs text-gray-400 mt-1">{daysSinceVisit} días desde última visita</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Tab 3: Segmentos ─────────────────────────────────────────────────────────
function SegmentsTab({ contactId }: { contactId: number }) {
  const [search, setSearch] = useState("");

  const { data: segments = [], isLoading } = useQuery<{ id: number; name: string; description: string | null }[]>({
    queryKey: ["contact-segments", contactId],
    queryFn: () => contactsApi.segments(contactId).then((r) => r.data),
    staleTime: 2 * 60_000,
  });

  const filtered = segments.filter((s) =>
    !search || s.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-700">Listas y segmentos</span>
      </div>
      <div className="px-5 py-3 border-b border-gray-100">
        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar segmento..."
            className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="p-6 space-y-2">
          {[...Array(3)].map((_, i) => <div key={i} className="h-12 bg-gray-100 rounded-lg animate-pulse" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="p-10 text-center text-sm text-gray-400">
          {search ? "Sin resultados" : "No pertenece a ningún segmento activo"}
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Nombre</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Descripción</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr key={s.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                <td className="px-5 py-3.5">
                  <Link href={`/segments/${s.id}`} className="font-medium text-brand-600 hover:underline flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-brand-400 shrink-0" />
                    {s.name}
                  </Link>
                </td>
                <td className="px-5 py-3.5 text-gray-400 text-xs">{s.description ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── Tab 4: Objetos (reservas detalladas) ────────────────────────────────────
function ObjectsTab({ contactId }: { contactId: number }) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const { data: bookings = [], isLoading } = useQuery<ContactBooking[]>({
    queryKey: ["contact-bookings", contactId],
    queryFn:  () => contactsApi.bookings(contactId).then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  function toggle(i: number) {
    setExpanded((prev) => ({ ...prev, [i]: !prev[i] }));
  }

  if (isLoading) return (
    <div className="space-y-3">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="h-16 bg-gray-100 rounded-xl animate-pulse" />
      ))}
    </div>
  );

  if (bookings.length === 0) return (
    <div className="bg-white border border-gray-200 rounded-xl p-16 text-center">
      <div className="flex justify-center mb-4 opacity-20">
        <Anchor size={48} className="text-gray-400" />
      </div>
      <p className="text-sm font-medium text-gray-600">Este cliente no tiene reservas registradas</p>
      <p className="text-xs text-gray-400 mt-1">Los pedidos de Happy Lápiz aparecerán aquí automáticamente al sincronizar</p>
    </div>
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-gray-400">{bookings.length} pedido{bookings.length !== 1 ? "s" : ""} encontrados en Shopify</p>
        <button
          onClick={() => {
            const anyOpen = bookings.some((_, i) => expanded[i]);
            const next: Record<number, boolean> = {};
            bookings.forEach((_, i) => { next[i] = !anyOpen; });
            setExpanded(next);
          }}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          {bookings.some((_, i) => expanded[i]) ? "Colapsar todo" : "Expandir todo"}
        </button>
      </div>

      {bookings.map((b, i) => {
        const extras = Object.entries(b.extras ?? {}).filter(([k]) => !k.startsWith("aloj__"));
        const isOpen = !!expanded[i];
        const statusColor = BOOKING_STATUS_COLOR[b.status] ?? "bg-gray-100 text-gray-600";

        return (
          <div key={i} className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            {/* Row header */}
            <button
              onClick={() => toggle(i)}
              className="w-full px-5 py-4 flex items-center gap-4 hover:bg-gray-50 transition-colors text-left"
            >
              <div className="w-9 h-9 rounded-lg bg-sky-50 flex items-center justify-center shrink-0">
                <Anchor size={15} className="text-sky-500" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900">Reserva · {b.fecha}</p>
                {b.como_supieron && (
                  <p className="text-xs text-gray-400 mt-0.5">Vía: {b.como_supieron}</p>
                )}
              </div>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium shrink-0 ${statusColor}`}>
                {b.status}
              </span>
              {b.ingreso_total != null && (
                <span className="text-sm font-bold text-gray-900 shrink-0">
                  CLP {b.ingreso_total.toLocaleString("es-CL")}
                </span>
              )}
              {isOpen
                ? <ChevronUp size={14} className="text-gray-400 shrink-0" />
                : <ChevronDown size={14} className="text-gray-400 shrink-0" />
              }
            </button>

            {/* Expanded detail */}
            {isOpen && (
              <div className="border-t border-gray-100 px-5 py-4 bg-gray-50">
                <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                  {[
                    ["Fecha",          b.fecha],
                    ["Estado",         b.status],
                    ["Ingreso total",  b.ingreso_total != null ? `CLP ${b.ingreso_total.toLocaleString("es-CL")}` : null],
                    ["Cómo supieron",  b.como_supieron],
                  ].map(([label, value]) => value ? (
                    <div key={label}>
                      <p className="text-xs text-gray-400 uppercase tracking-wider mb-0.5">{label}</p>
                      <p className="text-sm text-gray-800">{value}</p>
                    </div>
                  ) : null)}
                </div>

                {extras.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-gray-200">
                    <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Extras contratados</p>
                    <div className="flex flex-wrap gap-2">
                      {extras.map(([key, val]) => (
                        <span key={key} className="px-2.5 py-1 bg-white border border-gray-200 rounded-lg text-xs text-gray-700">
                          <span className="font-medium">{key}</span>
                          {val && val !== true && val !== "true" && (
                            <span className="text-gray-400"> · {String(val)}</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function ContactDetailPage() {
  const { id }      = useParams<{ id: string }>();
  const router      = useRouter();
  const qc          = useQueryClient();
  const contactId   = Number(id);
  const [tab, setTab] = useState<"details" | "metrics" | "segments" | "objects">("details");

  const { data: contact, isLoading } = useQuery<Contact>({
    queryKey: ["contact", contactId],
    queryFn:  () => contactsApi.get(contactId).then((r) => r.data),
    staleTime: 60_000,
  });

  const updateMutation = useMutation({
    mutationFn: (data: Partial<Contact>) => contactsApi.update(contactId, data),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ["contact", contactId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => contactsApi.delete(contactId),
    onSuccess:  () => router.push("/contacts"),
  });

  if (isLoading) return (
    <div className="p-8 max-w-5xl">
      <div className="h-4 bg-gray-200 rounded w-28 animate-pulse mb-6" />
      <div className="h-24 bg-gray-100 rounded-xl animate-pulse mb-4" />
      <div className="h-10 bg-gray-100 rounded animate-pulse mb-6" />
      <div className="h-64 bg-gray-100 rounded-xl animate-pulse" />
    </div>
  );

  if (!contact) return (
    <div className="p-8">
      <Link href="/contacts" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-4">
        <ArrowLeft size={15} /> Volver
      </Link>
      <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
        Contacto no encontrado.
      </div>
    </div>
  );

  return (
    <div className="p-8 max-w-5xl">
      <Link href="/contacts" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-5">
        <ArrowLeft size={14} /> Volver a clientes
      </Link>

      {/* ── Header ── */}
      <div className="mb-0">
        <div className="flex items-start justify-between gap-4 mb-1">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{contact.name || "Sin nombre"}</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {contact.email}
              {contact.phone && <> · {contact.phone}</>}
              {contact.location && <> · {contact.location}</>}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${contact.opted_in ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
              {contact.opted_in ? "Suscrito" : "Dado de baja"}
            </span>
            <button
              onClick={() => updateMutation.mutate({ opted_in: !contact.opted_in })}
              className="px-3 py-1.5 border border-gray-200 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-50"
            >
              {contact.opted_in ? "Dar de baja" : "Reactivar"}
            </button>
            <button
              onClick={() => { if (confirm(`¿Eliminar ${contact.email}?`)) deleteMutation.mutate(); }}
              className="px-3 py-1.5 border border-red-100 text-red-500 rounded-lg text-xs font-medium hover:bg-red-50"
            >
              Eliminar
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 border-b border-gray-200 mt-4 mb-6">
          <Tab label="Detalles"            active={tab === "details"}  onClick={() => setTab("details")} />
          <Tab label="Métricas e insights" active={tab === "metrics"}  onClick={() => setTab("metrics")} />
          <Tab label="Listas y segmentos"  active={tab === "segments"} onClick={() => setTab("segments")} />
          <Tab label="Objetos"             active={tab === "objects"}  onClick={() => setTab("objects")} />
        </div>
      </div>

      {/* ── Tab content ── */}
      {tab === "details" && (
        <DetailsTab
          contact={contact}
          saving={updateMutation.isPending}
          onSave={(fields, notes, birthday) =>
            updateMutation.mutate({ custom_fields: fields, notes: notes || null, birthday: birthday || null } as Partial<Contact>)
          }
        />
      )}
      {tab === "metrics"  && <MetricsTab  contact={contact} />}
      {tab === "segments" && <SegmentsTab contactId={contactId} />}
      {tab === "objects"  && <ObjectsTab  contactId={contactId} />}
    </div>
  );
}
