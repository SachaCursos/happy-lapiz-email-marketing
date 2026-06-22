"use client";

import { useState, useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { segmentsApi, contactsApi } from "@/lib/api";
import { SegmentConditions, SegmentRule } from "@/lib/types";
import { ArrowLeft, Plus, Trash2, Search, X, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const FIELDS = [
  { value: "email",                label: "Email",                  type: "string" },
  { value: "orders_count",         label: "Nº pedidos",             type: "number" },
  { value: "total_spent",          label: "Total gastado ($)",       type: "number" },
  { value: "ticket_medio",         label: "Ticket medio ($)",       type: "number" },
  { value: "last_purchase",        label: "Última compra",          type: "date" },
  { value: "shipping_city",        label: "Ciudad de envío",        type: "string" },
  { value: "shipping_province",    label: "Región de envío",        type: "string" },
  { value: "language",             label: "Idioma",                 type: "string" },
  { value: "origin_utm",           label: "Origen UTM",             type: "string" },
  { value: "opted_in",             label: "Opt-in activo",          type: "boolean" },
  { value: "ultima_visita",        label: "Última visita web",      type: "date" },
  { value: "smile_points",         label: "Puntos de fidelidad",    type: "number" },
  { value: "has_gift_recipient",   label: "Tiene regalado registrado", type: "boolean" },
];

const OPS_BY_TYPE: Record<string, { value: string; label: string }[]> = {
  number:  [
    { value: "eq",  label: "igual a" },
    { value: "gt",  label: "mayor que" },
    { value: "gte", label: "mayor o igual que" },
    { value: "lt",  label: "menor que" },
    { value: "lte", label: "menor o igual que" },
  ],
  string:  [
    { value: "eq",       label: "es" },
    { value: "contains", label: "contiene" },
    { value: "starts",   label: "empieza por" },
  ],
  boolean: [{ value: "eq", label: "es" }],
  date:    [
    { value: "gt",  label: "después de" },
    { value: "lt",  label: "antes de" },
    { value: "gte", label: "desde" },
    { value: "lte", label: "hasta" },
  ],
};

function emptyRule(): SegmentRule {
  return { field: "orders_count", op: "gte", value: 1 };
}

interface ContactOption { id: number; name: string; email: string; }

function ContactPicker({
  selected,
  onChange,
}: {
  selected: ContactOption[];
  onChange: (c: ContactOption[]) => void;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const { data: results = [] } = useQuery({
    queryKey: ["contact-search", search],
    queryFn: () => contactsApi.list({ search, limit: 10 }).then((r) => r.data as ContactOption[]),
    enabled: search.length >= 1,
    staleTime: 10_000,
  });

  useEffect(() => {
    function h(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  function add(c: ContactOption) {
    if (!selected.find((s) => s.id === c.id)) onChange([...selected, c]);
    setSearch("");
    setOpen(false);
  }

  function remove(id: number) {
    onChange(selected.filter((s) => s.id !== id));
  }

  return (
    <div className="space-y-3">
      {selected.length > 0 && (
        <div className="space-y-2">
          {selected.map((c) => (
            <div key={c.id} className="flex items-center justify-between bg-brand-50 border border-brand-100 rounded-lg px-3 py-2">
              <div>
                <p className="text-sm font-medium text-gray-900">{c.name}</p>
                <p className="text-xs text-gray-400">{c.email}</p>
              </div>
              <button onClick={() => remove(c.id)} className="text-gray-300 hover:text-red-500 transition-colors">
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="relative" ref={ref}>
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder="Buscar contacto por nombre o email..."
          className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        {open && results.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
            {results
              .filter((r) => !selected.find((s) => s.id === r.id))
              .map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => add(c)}
                  className="w-full text-left px-4 py-2.5 hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0"
                >
                  <p className="text-sm font-medium text-gray-900">{c.name}</p>
                  <p className="text-xs text-gray-400">{c.email}</p>
                </button>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function NewSegmentPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<"conditions" | "manual">("conditions");
  const [operator, setOperator] = useState<"AND" | "OR">("AND");
  const [rules, setRules] = useState<SegmentRule[]>([emptyRule()]);
  const [manualContacts, setManualContacts] = useState<ContactOption[]>([]);

  const mutation = useMutation({
    mutationFn: (data: { name: string; description?: string; conditions: SegmentConditions }) =>
      segmentsApi.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["segments"] });
      router.push("/segments");
    },
  });

  function updateRule(i: number, patch: Partial<SegmentRule>) {
    setRules((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function getFieldType(field: string): string {
    return FIELDS.find((f) => f.value === field)?.type ?? "string";
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    let conditions: SegmentConditions;
    if (mode === "manual") {
      conditions = {
        operator: "AND",
        rules: [{ field: "id", op: "in", value: manualContacts.map((c) => c.id) }],
      };
    } else {
      conditions = { operator, rules };
    }
    mutation.mutate({ name, description: description || undefined, conditions });
  }

  return (
    <div className="p-8 max-w-2xl">
      <Link href="/segments" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6">
        <ArrowLeft size={15} /> Volver a segmentos
      </Link>

      <h1 className="text-2xl font-bold text-gray-900 mb-6">Nuevo segmento</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h2 className="font-semibold text-gray-900">Información</h2>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre del segmento *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="Ej: Clientes recurrentes"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Descripción</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Descripción opcional"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        </div>

        {/* Modo */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => setMode("conditions")}
            className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl border text-sm font-medium transition-colors ${
              mode === "conditions"
                ? "border-brand-500 bg-brand-50 text-brand-700"
                : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            <Plus size={15} /> Por condiciones
          </button>
          <button
            type="button"
            onClick={() => setMode("manual")}
            className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl border text-sm font-medium transition-colors ${
              mode === "manual"
                ? "border-brand-500 bg-brand-50 text-brand-700"
                : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            <Users size={15} /> Contactos específicos
          </button>
        </div>

        {mode === "conditions" ? (
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">Condiciones</h2>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-gray-500">Operador:</span>
                {(["AND", "OR"] as const).map((op) => (
                  <button
                    key={op}
                    type="button"
                    onClick={() => setOperator(op)}
                    className={`px-3 py-1 rounded-lg font-medium transition-colors ${operator === op ? "bg-brand-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
                  >
                    {op === "AND" ? "Todas" : "Alguna"}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              {rules.map((rule, i) => {
                const fieldType = getFieldType(rule.field);
                const ops = OPS_BY_TYPE[fieldType] ?? OPS_BY_TYPE.string;
                return (
                  <div key={i} className="flex items-center gap-2">
                    <select
                      value={rule.field}
                      onChange={(e) => updateRule(i, { field: e.target.value, op: OPS_BY_TYPE[getFieldType(e.target.value)]?.[0]?.value ?? "eq", value: "" })}
                      className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                    >
                      {FIELDS.map((f) => (
                        <option key={f.value} value={f.value}>{f.label}</option>
                      ))}
                    </select>
                    <select
                      value={rule.op}
                      onChange={(e) => updateRule(i, { op: e.target.value })}
                      className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                    >
                      {ops.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                    {fieldType === "boolean" ? (
                      <select
                        value={String(rule.value)}
                        onChange={(e) => updateRule(i, { value: e.target.value === "true" })}
                        className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                      >
                        <option value="true">Sí</option>
                        <option value="false">No</option>
                      </select>
                    ) : (
                      <input
                        type={fieldType === "number" ? "number" : fieldType === "date" ? "date" : "text"}
                        value={String(rule.value ?? "")}
                        onChange={(e) => updateRule(i, { value: fieldType === "number" ? Number(e.target.value) : e.target.value })}
                        className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                    )}
                    <button
                      type="button"
                      onClick={() => setRules((prev) => prev.filter((_, idx) => idx !== i))}
                      disabled={rules.length === 1}
                      className="text-gray-300 hover:text-red-500 transition-colors disabled:opacity-30"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                );
              })}
            </div>
            <button
              type="button"
              onClick={() => setRules((prev) => [...prev, emptyRule()])}
              className="mt-4 flex items-center gap-2 text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              <Plus size={14} /> Agregar condición
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-semibold text-gray-900 mb-4">Contactos específicos</h2>
            <ContactPicker selected={manualContacts} onChange={setManualContacts} />
            {manualContacts.length === 0 && (
              <p className="text-xs text-gray-400 mt-3">Buscá y agregá los contactos que quieras incluir en este segmento.</p>
            )}
          </div>
        )}

        {mutation.isError && (
          <p className="text-red-600 text-sm">Error al crear el segmento. Intenta de nuevo.</p>
        )}

        <div className="flex gap-3">
          <Link href="/segments" className="px-5 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors">
            Cancelar
          </Link>
          <button
            type="submit"
            disabled={mutation.isPending || !name || (mode === "manual" && manualContacts.length === 0)}
            className="px-5 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-60 transition-colors"
          >
            {mutation.isPending ? "Creando..." : "Crear segmento"}
          </button>
        </div>
      </form>
    </div>
  );
}
