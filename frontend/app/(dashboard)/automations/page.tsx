"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { automationsApi, templatesApi } from "@/lib/api";
import { Automation, AutomationStats, Template } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { Plus, Zap, Play, Pause, Trash2, ChevronDown, ChevronUp, Pencil, Save, X } from "lucide-react";
import Link from "next/link";

const TRIGGER_LABELS: Record<string, { label: string; description: string; color: string }> = {
  abandoned_booking: {
    label: "Reserva abandonada",
    description: "Cuando alguien inicia una reserva pero no la completa",
    color: "bg-orange-100 text-orange-700",
  },
  welcome: {
    label: "Bienvenida",
    description: "Cuando se añade un nuevo contacto",
    color: "bg-blue-100 text-blue-700",
  },
  post_visit: {
    label: "Post-visita",
    description: "Días después de la última experiencia",
    color: "bg-green-100 text-green-700",
  },
  reactivation: {
    label: "Reactivación",
    description: "Clientes sin visitar en mucho tiempo",
    color: "bg-purple-100 text-purple-700",
  },
};

function configSummary(auto: Automation): string {
  const c = auto.trigger_config ?? {};
  switch (auto.trigger_type) {
    case "abandoned_booking":
      return `${c.delay_minutes ?? 5} min después de la reserva pendiente`;
    case "welcome":
      return c.delay_hours ? `${c.delay_hours}h después de registrarse` : "Inmediatamente al registrarse";
    case "post_visit":
      return `${c.delay_days ?? 3} días después de la visita`;
    case "reactivation":
      return `Sin visitar ${c.inactivity_days ?? 90}+ días`;
    default:
      return "";
  }
}

function EditPanel({
  auto,
  templates,
  onSave,
  onCancel,
  saving,
}: {
  auto: Automation;
  templates: Template[];
  onSave: (data: Partial<Automation>) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [form, setForm] = useState({
    name: auto.name,
    subject: auto.subject,
    template_id: auto.template_id,
    trigger_config: auto.trigger_config ?? {},
  });

  function setConfig(key: string, val: string | number) {
    setForm((f) => ({ ...f, trigger_config: { ...f.trigger_config, [key]: val } as Record<string, number> }));
  }

  const cfg = form.trigger_config as Record<string, number>;

  return (
    <div className="border-t border-brand-100 bg-blue-50 px-5 py-4 space-y-3">
      <p className="text-xs font-semibold text-brand-700 uppercase tracking-wider">Editar automatización</p>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Nombre interno</label>
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Asunto del email</label>
          <input
            value={form.subject}
            onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Plantilla de email</label>
        <select
          value={form.template_id}
          onChange={(e) => setForm((f) => ({ ...f, template_id: Number(e.target.value) }))}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
        >
          <option value={0}>— Seleccionar plantilla —</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>

      {/* trigger_config fields */}
      {auto.trigger_type === "welcome" && (
        <div className="max-w-xs">
          <label className="block text-xs font-medium text-gray-600 mb-1">Demora (horas, 0 = inmediato)</label>
          <input
            type="number" min={0} max={72}
            value={cfg.delay_hours ?? 0}
            onChange={(e) => setConfig("delay_hours", Number(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      )}
      {auto.trigger_type === "post_visit" && (
        <div className="max-w-xs">
          <label className="block text-xs font-medium text-gray-600 mb-1">Días después de la visita</label>
          <input
            type="number" min={1} max={30}
            value={cfg.delay_days ?? 3}
            onChange={(e) => setConfig("delay_days", Number(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      )}
      {auto.trigger_type === "reactivation" && (
        <div className="grid grid-cols-2 gap-3 max-w-sm">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Días de inactividad</label>
            <input
              type="number" min={30}
              value={cfg.inactivity_days ?? 90}
              onChange={(e) => setConfig("inactivity_days", Number(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Cooldown (días)</label>
            <input
              type="number" min={30}
              value={cfg.cooldown_days ?? 180}
              onChange={(e) => setConfig("cooldown_days", Number(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        </div>
      )}
      {auto.trigger_type === "abandoned_booking" && (
        <div className="grid grid-cols-2 gap-3 max-w-sm">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Enviar después de (min)</label>
            <input
              type="number" min={1}
              value={cfg.delay_minutes ?? 5}
              onChange={(e) => setConfig("delay_minutes", Number(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Ventana máxima (horas)</label>
            <input
              type="number" min={1}
              value={cfg.lookback_hours ?? 24}
              onChange={(e) => setConfig("lookback_hours", Number(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button
          onClick={() => onSave(form)}
          disabled={saving || !form.template_id || !form.name || !form.subject}
          className="flex items-center gap-1.5 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >
          <Save size={13} /> {saving ? "Guardando..." : "Guardar cambios"}
        </button>
        <button
          onClick={onCancel}
          className="flex items-center gap-1.5 px-3 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm hover:bg-gray-50 transition-colors"
        >
          <X size={13} /> Cancelar
        </button>
      </div>
    </div>
  );
}

function AutomationRow({ auto, templates }: { auto: Automation; templates: Template[] }) {
  const qc = useQueryClient();
  const [showRuns, setShowRuns] = useState(false);
  const [editing, setEditing] = useState(false);

  const { data: stats } = useQuery<AutomationStats>({
    queryKey: ["automation-stats", auto.id],
    queryFn: () => automationsApi.stats(auto.id).then((r) => r.data),
    staleTime: 60_000,
  });

  const toggleMutation = useMutation({
    mutationFn: () => automationsApi.toggle(auto.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automations"] }),
  });

  const updateMutation = useMutation({
    mutationFn: (data: unknown) => automationsApi.update(auto.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["automations"] });
      setEditing(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => automationsApi.delete(auto.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["automations"] }),
  });

  const trigger = TRIGGER_LABELS[auto.trigger_type] ?? {
    label: auto.trigger_type,
    description: "",
    color: "bg-gray-100 text-gray-700",
  };
  const isActive = auto.status === "active";
  const tplName = templates.find((t) => t.id === auto.template_id)?.name;

  return (
    <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
      <div className="p-5 flex items-start gap-4">
        <div className={`mt-0.5 px-2.5 py-1 rounded-full text-xs font-semibold shrink-0 ${trigger.color}`}>
          {trigger.label}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900 truncate">{auto.name}</h3>
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                isActive ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isActive ? "bg-green-500" : "bg-gray-400"}`} />
              {isActive ? "Activa" : "Pausada"}
            </span>
          </div>
          <p className="text-sm text-gray-500 mt-0.5">{configSummary(auto)}</p>
          <p className="text-xs text-gray-400 mt-0.5 truncate">Asunto: {auto.subject}</p>
          {tplName && (
            <p className="text-xs text-gray-400 mt-0.5 truncate">Plantilla: <span className="text-gray-600">{tplName}</span></p>
          )}
        </div>

        <div className="text-right shrink-0">
          <p className="text-2xl font-bold text-gray-900">{stats?.sent ?? "—"}</p>
          <p className="text-xs text-gray-400">enviados</p>
          {stats?.last_run && (
            <p className="text-xs text-gray-400 mt-0.5">Último: {formatDate(stats.last_run)}</p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => { setEditing((v) => !v); setShowRuns(false); }}
            title="Editar"
            className={`p-2 rounded-lg border transition-colors ${editing ? "border-brand-400 bg-brand-50 text-brand-600" : "border-gray-200 text-gray-500 hover:bg-gray-50"}`}
          >
            <Pencil size={14} />
          </button>
          <button
            onClick={() => toggleMutation.mutate()}
            disabled={toggleMutation.isPending}
            title={isActive ? "Pausar" : "Activar"}
            className={`p-2 rounded-lg border transition-colors ${
              isActive
                ? "border-yellow-200 text-yellow-600 hover:bg-yellow-50"
                : "border-green-200 text-green-600 hover:bg-green-50"
            } disabled:opacity-50`}
          >
            {isActive ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button
            onClick={() => {
              if (confirm(`¿Eliminar automatización "${auto.name}"?`)) deleteMutation.mutate();
            }}
            disabled={deleteMutation.isPending}
            className="p-2 rounded-lg border border-red-100 text-red-500 hover:bg-red-50 transition-colors disabled:opacity-50"
          >
            <Trash2 size={14} />
          </button>
          <button
            onClick={() => { setShowRuns((v) => !v); setEditing(false); }}
            className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
            title="Ver historial"
          >
            {showRuns ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {editing && (
        <EditPanel
          auto={auto}
          templates={templates}
          onSave={(data) => updateMutation.mutate(data)}
          onCancel={() => setEditing(false)}
          saving={updateMutation.isPending}
        />
      )}
      {showRuns && <RunsPanel automationId={auto.id} />}
    </div>
  );
}

function RunsPanel({ automationId }: { automationId: number }) {
  const { data: runs = [], isLoading } = useQuery({
    queryKey: ["automation-runs", automationId],
    queryFn: () => automationsApi.runs(automationId).then((r) => r.data),
    staleTime: 30_000,
  });

  return (
    <div className="border-t border-gray-100 bg-gray-50 px-5 py-3">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        Últimos envíos
      </p>
      {isLoading ? (
        <p className="text-xs text-gray-400">Cargando...</p>
      ) : runs.length === 0 ? (
        <p className="text-xs text-gray-400">Aún no hay envíos registrados.</p>
      ) : (
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {runs.map((r: { id: number; contact_email: string; status: string; triggered_at: string; error?: string }) => (
            <div key={r.id} className="flex items-center gap-3 text-xs">
              <span
                className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                  r.status === "sent"
                    ? "bg-green-100 text-green-700"
                    : r.status === "failed"
                    ? "bg-red-100 text-red-700"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                {r.status}
              </span>
              <span className="text-gray-700 font-mono truncate max-w-[200px]">{r.contact_email}</span>
              <span className="text-gray-400 ml-auto shrink-0">{formatDate(r.triggered_at)}</span>
              {r.error && <span className="text-red-500 truncate max-w-[150px]" title={r.error}>{r.error}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AutomationsPage() {
  const { data: automations = [], isLoading } = useQuery<Automation[]>({
    queryKey: ["automations"],
    queryFn: () => automationsApi.list().then((r) => r.data),
    staleTime: 30_000,
  });

  const { data: templates = [] } = useQuery<Template[]>({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list().then((r) => r.data),
    staleTime: 5 * 60_000,
  });

  const active = automations.filter((a) => a.status === "active").length;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Automatizaciones</h1>
          <p className="text-gray-500 mt-1 text-sm">
            {active} activa{active !== 1 ? "s" : ""} de {automations.length}
          </p>
        </div>
        <Link
          href="/automations/new"
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors"
        >
          <Plus size={15} />
          Nueva automatización
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-24 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : automations.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
          <div className="w-14 h-14 bg-gray-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Zap size={24} className="text-gray-300" />
          </div>
          <p className="text-gray-900 font-semibold">Sin automatizaciones</p>
          <p className="text-gray-400 text-sm mt-1 mb-6">
            Crea flujos de email que se disparan automáticamente según el comportamiento de tus clientes.
          </p>
          <Link
            href="/automations/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors"
          >
            <Plus size={15} /> Crear primera automatización
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {automations.map((a) => (
            <AutomationRow key={a.id} auto={a} templates={templates} />
          ))}
        </div>
      )}

      <div className="mt-8 grid grid-cols-2 gap-4">
        {Object.entries(TRIGGER_LABELS).map(([key, { label, description, color }]) => (
          <div key={key} className="bg-white border border-gray-200 rounded-xl p-4 flex gap-3">
            <span className={`mt-0.5 px-2 py-0.5 rounded-full text-xs font-semibold h-fit shrink-0 ${color}`}>
              {label}
            </span>
            <p className="text-sm text-gray-500">{description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
