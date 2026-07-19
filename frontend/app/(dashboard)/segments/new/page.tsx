"use client";

import { useState, useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { segmentsApi, contactsApi, formsApi, shopifyApi, campaignsApi, ShopifyProduct } from "@/lib/api";
import { Campaign } from "@/lib/types";
import { SegmentConditions, SegmentRule, SignupForm } from "@/lib/types";
import { ArrowLeft, Plus, Trash2, Search, X, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const FAMILY_ROLE_OPTIONS = [
  { value: "madre", label: "Madre" },
  { value: "padre", label: "Padre" },
  { value: "abuela", label: "Abuela" },
  { value: "abuelo", label: "Abuelo" },
  { value: "tia", label: "Tía" },
  { value: "tio", label: "Tío" },
  { value: "madrina", label: "Madrina" },
  { value: "padrino", label: "Padrino" },
  { value: "hermana", label: "Hermana" },
  { value: "hermano", label: "Hermano" },
  { value: "otro", label: "Otro" },
  { value: "no_identificado", label: "No identificado" },
];

const FIELDS = [
  { value: "email",                label: "Email",                  type: "string" },
  { value: "family_role",          label: "Rol familiar",           type: "enum", options: FAMILY_ROLE_OPTIONS },
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
  { value: "has_form_submission",  label: "Rellenó formulario",        type: "form_submission" },
  { value: "campaign_bounce_count", label: "Rebotes en campañas",      type: "number" },
  { value: "no_open_in_last_n_emails", label: "Sin apertura en últimos N correos", type: "last_n_no_open" },
  { value: "opened_email_in_last_n_days", label: "Abrió algún correo en últimos N días", type: "last_n_days_open" },
  { value: "purchased_product",        label: "Producto comprado",                type: "product_shopify" },
  { value: "received_campaign",        label: "Recibió campaña",                  type: "campaign_engagement" },
  { value: "opened_campaign",          label: "Abrió campaña",                    type: "campaign_engagement" },
  { value: "clicked_campaign",         label: "Clickeó campaña",                  type: "campaign_engagement" },
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
  enum: [
    { value: "eq",  label: "es" },
    { value: "neq", label: "no es" },
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

function defaultFormSubmissionValue(formId?: number): { form_id: number; submitted: boolean } {
  return { form_id: formId ?? 1, submitted: false };
}

function parseFormSubmissionValue(
  value: unknown,
  defaultFormId?: number,
): { form_id: number; submitted: boolean } {
  if (value && typeof value === "object" && "form_id" in value) {
    const v = value as { form_id?: unknown; submitted?: unknown };
    return {
      form_id: Number(v.form_id) || defaultFormId || 1,
      submitted: v.submitted === true || v.submitted === "true",
    };
  }
  return defaultFormSubmissionValue(defaultFormId);
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

interface ProductValue { product_id: string; product_title: string; }

function parseProductValue(value: unknown): ProductValue {
  if (value && typeof value === "object" && "product_id" in value) {
    const v = value as { product_id?: unknown; product_title?: unknown };
    return { product_id: String(v.product_id || ""), product_title: String(v.product_title || "") };
  }
  return { product_id: "", product_title: "" };
}

function ShopifyProductPicker({
  value,
  onChange,
}: {
  value: ProductValue;
  onChange: (v: ProductValue) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const { data: products = [], isLoading } = useQuery<ShopifyProduct[]>({
    queryKey: ["shopify-products-segment"],
    queryFn: () => shopifyApi.products().then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    function h(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const filtered = products.filter((p) =>
    p.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-[220px]"
      >
        {value.product_title
          ? <span className="flex-1 text-left truncate text-gray-900">{value.product_title}</span>
          : <span className="flex-1 text-left text-gray-400">Seleccionar producto...</span>}
        <Search size={13} className="text-gray-400 shrink-0" />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-30 w-80">
          <div className="p-2 border-b border-gray-100">
            <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-1.5">
              <Search size={13} className="text-gray-400 shrink-0" />
              <input
                autoFocus
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar producto..."
                className="flex-1 text-sm focus:outline-none"
              />
              {search && (
                <button onClick={() => setSearch("")} className="text-gray-400 hover:text-gray-600">
                  <X size={12} />
                </button>
              )}
            </div>
          </div>
          <div className="max-h-60 overflow-y-auto">
            {isLoading && (
              <div className="px-4 py-6 text-center text-sm text-gray-400">Cargando productos...</div>
            )}
            {!isLoading && filtered.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-gray-400">Sin resultados</div>
            )}
            {filtered.map((prod) => (
              <button
                key={prod.id}
                type="button"
                onClick={() => {
                  onChange({ product_id: prod.id, product_title: prod.title });
                  setOpen(false);
                  setSearch("");
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0 ${value.product_id === prod.id ? "bg-brand-50" : ""}`}
              >
                {prod.image_url
                  ? <img src={prod.image_url} alt="" className="w-10 h-10 object-cover rounded-lg shrink-0" />
                  : <div className="w-10 h-10 bg-gray-100 rounded-lg shrink-0" />}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{prod.title}</p>
                  <p className="text-xs text-gray-400">${parseFloat(prod.price).toLocaleString("es-CL")}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

type CampaignEngagementKind = "received" | "opened" | "clicked";

interface CampaignEngagementValue {
  campaign_id: number;
  campaign_name: string;
  received?: boolean;
  opened?: boolean;
  clicked?: boolean;
}

const ENGAGEMENT_LABELS: Record<CampaignEngagementKind, { yes: string; no: string; key: CampaignEngagementKind }> = {
  received: { key: "received", yes: "Sí, la recibió", no: "No, no la recibió" },
  opened:   { key: "opened",   yes: "Sí, la abrió",   no: "No (la recibió, pero no abrió)" },
  clicked:  { key: "clicked",  yes: "Sí, clickeó",    no: "No (la recibió, pero no clickeó)" },
};

function engagementKindForField(field: string): CampaignEngagementKind {
  if (field === "opened_campaign") return "opened";
  if (field === "clicked_campaign") return "clicked";
  return "received";
}

function defaultCampaignEngagementValue(kind: CampaignEngagementKind): CampaignEngagementValue {
  return {
    campaign_id: 0,
    campaign_name: "",
    [kind]: true,
  };
}

function parseCampaignEngagementValue(value: unknown, kind: CampaignEngagementKind): CampaignEngagementValue {
  if (value && typeof value === "object" && "campaign_id" in value) {
    const v = value as Record<string, unknown>;
    const flag = v[kind];
    return {
      campaign_id: Number(v.campaign_id) || 0,
      campaign_name: String(v.campaign_name || ""),
      [kind]: flag !== false,
    };
  }
  return defaultCampaignEngagementValue(kind);
}

function CampaignEngagementPicker({
  kind,
  value,
  onChange,
}: {
  kind: CampaignEngagementKind;
  value: CampaignEngagementValue;
  onChange: (v: CampaignEngagementValue) => void;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const labels = ENGAGEMENT_LABELS[kind];
  const flag = value[kind] !== false;

  const { data: campaigns = [], isLoading } = useQuery<Campaign[]>({
    queryKey: ["campaigns-segment-picker"],
    queryFn: () => campaignsApi.list().then((r) => r.data),
    staleTime: 2 * 60_000,
  });

  useEffect(() => {
    function h(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const filtered = campaigns.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.subject.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <div className="relative" ref={ref}>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-2 border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-[220px] max-w-[300px]"
        >
          {value.campaign_name
            ? <span className="flex-1 text-left truncate text-gray-900">{value.campaign_name}</span>
            : <span className="flex-1 text-left text-gray-400">Seleccionar campaña...</span>}
          <Search size={13} className="text-gray-400 shrink-0" />
        </button>

        {open && (
          <div className="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-30 w-80">
            <div className="p-2 border-b border-gray-100">
              <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-1.5">
                <Search size={13} className="text-gray-400 shrink-0" />
                <input
                  autoFocus
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Buscar campaña..."
                  className="flex-1 text-sm focus:outline-none"
                />
                {search && <button onClick={() => setSearch("")} className="text-gray-400 hover:text-gray-600"><X size={12} /></button>}
              </div>
            </div>
            <div className="max-h-60 overflow-y-auto">
              {isLoading && <div className="px-4 py-6 text-center text-sm text-gray-400">Cargando campañas...</div>}
              {!isLoading && filtered.length === 0 && <div className="px-4 py-6 text-center text-sm text-gray-400">Sin resultados</div>}
              {filtered.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => {
                    onChange({ ...value, campaign_id: c.id, campaign_name: c.name });
                    setOpen(false);
                    setSearch("");
                  }}
                  className={`w-full flex flex-col px-4 py-2.5 text-left hover:bg-gray-50 transition-colors border-b border-gray-50 last:border-0 ${value.campaign_id === c.id ? "bg-brand-50" : ""}`}
                >
                  <p className="text-sm font-medium text-gray-900 truncate">{c.name}</p>
                  <p className="text-xs text-gray-400 truncate">{c.subject}</p>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <select
        value={flag ? "true" : "false"}
        onChange={(e) => onChange({ ...value, [kind]: e.target.value === "true" })}
        className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
      >
        <option value="true">{labels.yes}</option>
        <option value="false">{labels.no}</option>
      </select>
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
  const { data: signupForms = [] } = useQuery<SignupForm[]>({
    queryKey: ["forms"],
    queryFn: () => formsApi.list().then((r) => r.data),
    staleTime: 60_000,
  });

  const defaultFormId = signupForms[0]?.id;
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

  function getFieldOptions(field: string): { value: string; label: string }[] {
    const def = FIELDS.find((f) => f.value === field) as
      | { value: string; label: string; type: string; options?: { value: string; label: string }[] }
      | undefined;
    return def?.options ?? [];
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
                const formSubmissionValue = parseFormSubmissionValue(rule.value, defaultFormId);
                const productValue = parseProductValue(rule.value);
                const engagementKind = engagementKindForField(rule.field);
                return (
                  <div key={i} className="flex items-center gap-2 flex-wrap">
                    <select
                      value={rule.field}
                      onChange={(e) => {
                        const nextField = e.target.value;
                        const nextType = getFieldType(nextField);
                        const enumOpts = (
                          FIELDS.find((f) => f.value === nextField) as
                            | { options?: { value: string }[] }
                            | undefined
                        )?.options;
                        const nextValue =
                          nextField === "has_form_submission"
                            ? defaultFormSubmissionValue(defaultFormId)
                            : nextField === "no_open_in_last_n_emails"
                              ? 5
                            : nextField === "opened_email_in_last_n_days"
                              ? 90
                            : nextField === "purchased_product"
                              ? { product_id: "", product_title: "" }
                            : nextField === "received_campaign" ||
                                nextField === "opened_campaign" ||
                                nextField === "clicked_campaign"
                              ? defaultCampaignEngagementValue(engagementKindForField(nextField))
                            : nextType === "enum"
                              ? (enumOpts?.[0]?.value ?? "")
                            : nextType === "boolean"
                              ? true
                              : "";
                        updateRule(i, {
                          field: nextField,
                          op: "eq",
                          value: nextValue,
                        });
                      }}
                      className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                    >
                      {FIELDS.map((f) => (
                        <option key={f.value} value={f.value}>{f.label}</option>
                      ))}
                    </select>
                    {fieldType !== "form_submission" && fieldType !== "last_n_no_open" && fieldType !== "last_n_days_open" && fieldType !== "product_shopify" && fieldType !== "campaign_engagement" && (
                      <select
                        value={rule.op}
                        onChange={(e) => updateRule(i, { op: e.target.value })}
                        className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                      >
                        {ops.map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    )}
                    {fieldType === "form_submission" ? (
                      <>
                        <select
                          value={formSubmissionValue.form_id}
                          onChange={(e) =>
                            updateRule(i, {
                              op: "eq",
                              value: {
                                ...formSubmissionValue,
                                form_id: Number(e.target.value),
                              },
                            })
                          }
                          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white min-w-[180px]"
                        >
                          {signupForms.length === 0 ? (
                            <option value={1}>Cargando formularios…</option>
                          ) : (
                            signupForms.map((f) => (
                              <option key={f.id} value={f.id}>{f.name}</option>
                            ))
                          )}
                        </select>
                        <select
                          value={formSubmissionValue.submitted ? "true" : "false"}
                          onChange={(e) =>
                            updateRule(i, {
                              op: "eq",
                              value: {
                                ...formSubmissionValue,
                                submitted: e.target.value === "true",
                              },
                            })
                          }
                          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                        >
                          <option value="true">Sí, lo rellenó</option>
                          <option value="false">No, no lo ha rellenado</option>
                        </select>
                      </>
                    ) : fieldType === "last_n_no_open" ? (
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-500">últimos</span>
                        <input
                          type="number"
                          min={1}
                          value={Number(rule.value) || 5}
                          onChange={(e) =>
                            updateRule(i, { op: "eq", value: Number(e.target.value) || 5 })
                          }
                          className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-20 focus:outline-none focus:ring-2 focus:ring-brand-500"
                        />
                        <span className="text-sm text-gray-500">correos sin abrir</span>
                      </div>
                    ) : fieldType === "last_n_days_open" ? (
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-500">al menos una apertura en los últimos</span>
                        <input
                          type="number"
                          min={1}
                          value={Number(rule.value) || 90}
                          onChange={(e) =>
                            updateRule(i, { op: "eq", value: Number(e.target.value) || 90 })
                          }
                          className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-24 focus:outline-none focus:ring-2 focus:ring-brand-500"
                        />
                        <span className="text-sm text-gray-500">días</span>
                      </div>
                    ) : fieldType === "product_shopify" ? (
                      <ShopifyProductPicker
                        value={productValue}
                        onChange={(v) => updateRule(i, { op: "eq", value: v })}
                      />
                    ) : fieldType === "campaign_engagement" ? (
                      <CampaignEngagementPicker
                        kind={engagementKind}
                        value={parseCampaignEngagementValue(rule.value, engagementKind)}
                        onChange={(v) => updateRule(i, { op: "eq", value: v })}
                      />
                    ) : fieldType === "boolean" ? (
                      <select
                        value={String(rule.value)}
                        onChange={(e) => updateRule(i, { value: e.target.value === "true" })}
                        className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                      >
                        <option value="true">Sí</option>
                        <option value="false">No</option>
                      </select>
                    ) : fieldType === "enum" ? (
                      <select
                        value={String(rule.value ?? "")}
                        onChange={(e) => updateRule(i, { value: e.target.value })}
                        className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white min-w-[140px]"
                      >
                        {getFieldOptions(rule.field).map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
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
