"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Tag, Plus, X, Check, Percent, DollarSign, Zap, Hash, Copy } from "lucide-react";

interface CouponCampaign {
  id: number;
  name: string;
  discount_type: "percentage" | "fixed";
  discount_value: number;
  prefix: string;
  expires_at: string | null;
  status: string;
  created_at: string;
  codes_sent: number;
  coupon_mode: "dynamic" | "static";
  static_code: string | null;
}

interface CouponSend {
  code: string;
  email: string;
  used: boolean;
  created_at: string;
  campaign: string;
  value: number;
  type: string;
}

function NewCampaignModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<"dynamic" | "static">("dynamic");
  const [form, setForm] = useState({
    name: "", discount_type: "percentage", discount_value: 10,
    min_purchase: 0, prefix: "HL", expires_at: "", static_code: "",
  });
  const [createdStaticCode, setCreatedStaticCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const mutation = useMutation({
    mutationFn: () => api.post("/coupons/campaigns", { ...form, coupon_mode: mode }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["coupon-campaigns"] });
      if (mode === "static" && res.data.static_code) {
        setCreatedStaticCode(res.data.static_code);
      } else {
        onClose();
      }
    },
  });

  function copyCode(code: string) {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  // After static creation — show the code to copy
  if (createdStaticCode) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6">
          <div className="text-center mb-5">
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <Check size={22} className="text-green-600" />
            </div>
            <h3 className="font-bold text-gray-900">¡Cupón creado!</h3>
            <p className="text-sm text-gray-500 mt-1">Tu código de descuento ya está activo en Shopify</p>
          </div>

          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-center mb-4">
            <p className="text-xs text-gray-500 mb-2">Código de descuento</p>
            <code className="text-2xl font-mono font-bold text-brand-700 tracking-wider">{createdStaticCode}</code>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-5 text-xs text-blue-700 space-y-1">
            <p className="font-semibold">Cómo usarlo en tus emails:</p>
            <p>• Pegarlo directamente en el texto del email</p>
            <p>• En links: <code className="bg-white px-1 rounded border border-blue-200">{"?discount=" + createdStaticCode}</code></p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => copyCode(createdStaticCode)}
              className="flex-1 flex items-center justify-center gap-2 border border-gray-300 rounded-lg py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
              {copied ? "¡Copiado!" : "Copiar código"}
            </button>
            <button onClick={onClose} className="flex-1 bg-brand-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-brand-700">
              Listo
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-bold text-gray-900">Nuevo cupón</h3>
          <button onClick={onClose}><X size={18} className="text-gray-400" /></button>
        </div>

        {/* Type selector */}
        <div className="grid grid-cols-2 gap-2 mb-5">
          <button
            type="button"
            onClick={() => setMode("dynamic")}
            className={`flex flex-col items-start gap-1 p-3 rounded-xl border-2 text-left transition-all ${
              mode === "dynamic" ? "border-brand-500 bg-brand-50" : "border-gray-200 hover:border-gray-300"
            }`}
          >
            <div className="flex items-center gap-2">
              <Zap size={14} className={mode === "dynamic" ? "text-brand-600" : "text-gray-400"} />
              <span className={`text-sm font-semibold ${mode === "dynamic" ? "text-brand-700" : "text-gray-700"}`}>Dinámico</span>
            </div>
            <p className="text-xs text-gray-400">Código único por persona. Usado en automatizaciones.</p>
          </button>
          <button
            type="button"
            onClick={() => setMode("static")}
            className={`flex flex-col items-start gap-1 p-3 rounded-xl border-2 text-left transition-all ${
              mode === "static" ? "border-brand-500 bg-brand-50" : "border-gray-200 hover:border-gray-300"
            }`}
          >
            <div className="flex items-center gap-2">
              <Hash size={14} className={mode === "static" ? "text-brand-600" : "text-gray-400"} />
              <span className={`text-sm font-semibold ${mode === "static" ? "text-brand-700" : "text-gray-700"}`}>Estático</span>
            </div>
            <p className="text-xs text-gray-400">Un código fijo para todos. Pegas en cualquier email.</p>
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Nombre interno</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder={mode === "dynamic" ? "Ej: Carrito abandonado 10%" : "Ej: Verano 2025"}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>

          {mode === "static" && (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Código de descuento</label>
              <input
                value={form.static_code}
                onChange={(e) => setForm({ ...form, static_code: e.target.value.toUpperCase().replace(/\s/g, "") })}
                placeholder="Ej: VERANO25"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono font-bold tracking-wider focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <p className="text-xs text-gray-400 mt-1">El mismo código para todos tus clientes.</p>
            </div>
          )}

          {mode === "dynamic" && (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Prefijo del código</label>
              <input value={form.prefix} onChange={(e) => setForm({ ...form, prefix: e.target.value.toUpperCase() })}
                placeholder="HL"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              <p className="text-xs text-gray-400 mt-1">Cada persona recibirá un código como <code className="bg-gray-100 px-1 rounded">{form.prefix || "HL"}-ABCD1234</code></p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Tipo de descuento</label>
              <select value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
                <option value="percentage">Porcentaje (%)</option>
                <option value="fixed">Monto fijo (CLP)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                {form.discount_type === "percentage" ? "Descuento %" : "Monto CLP"}
              </label>
              <input type="number" value={form.discount_value}
                onChange={(e) => setForm({ ...form, discount_value: Number(e.target.value) })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Compra mínima (CLP)</label>
              <input type="number" value={form.min_purchase}
                onChange={(e) => setForm({ ...form, min_purchase: Number(e.target.value) })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Vence (opcional)</label>
              <input type="datetime-local" value={form.expires_at}
                onChange={(e) => setForm({ ...form, expires_at: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>
        </div>

        {mutation.isError && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">
            {(mutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error al crear el cupón. Intenta de nuevo."}
          </div>
        )}

        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="flex-1 border border-gray-200 rounded-lg py-2 text-sm font-medium text-gray-600 hover:bg-gray-50">
            Cancelar
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!form.name || (mode === "static" && !form.static_code) || mutation.isPending}
            className="flex-1 bg-brand-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
          >
            {mutation.isPending ? "Creando..." : "Crear cupón"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CouponsPage() {
  const [showNew, setShowNew] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data: campaigns = [], isError: listError } = useQuery<CouponCampaign[]>({
    queryKey: ["coupon-campaigns"],
    queryFn: () => api.get("/coupons/campaigns").then((r) => r.data),
  });

  const { data: sends = [] } = useQuery<CouponSend[]>({
    queryKey: ["coupon-sends", selectedId],
    queryFn: () => api.get("/coupons/sends", { params: selectedId ? { campaign_id: selectedId } : {} }).then((r) => r.data),
    enabled: true,
  });

  return (
    <div className="p-8">
      {showNew && <NewCampaignModal onClose={() => setShowNew(false)} />}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cupones</h1>
          <p className="text-gray-500 mt-1 text-sm">Crea descuentos estáticos o dinámicos conectados con Shopify</p>
        </div>
        <button onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700">
          <Plus size={15} /> Nuevo cupón
        </button>
      </div>

      {/* Explicación de tipos */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-xl p-4 flex gap-3">
          <div className="w-9 h-9 bg-brand-100 rounded-lg flex items-center justify-center shrink-0">
            <Zap size={16} className="text-brand-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">Dinámico</p>
            <p className="text-xs text-gray-500 mt-0.5">Código único por persona. Se genera automáticamente al enviar cada email de automatización. Usa <code className="bg-gray-100 px-1 rounded">{"{{ coupon_code }}"}</code> en la plantilla.</p>
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 flex gap-3">
          <div className="w-9 h-9 bg-purple-100 rounded-lg flex items-center justify-center shrink-0">
            <Hash size={16} className="text-purple-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">Estático</p>
            <p className="text-xs text-gray-500 mt-0.5">Un código fijo para todos (ej: <code className="bg-gray-100 px-1 rounded">VERANO25</code>). Lo pegas directamente en el email o en el link: <code className="bg-gray-100 px-1 rounded">?discount=VERANO25</code></p>
          </div>
        </div>
      </div>

      {listError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 text-sm text-red-700">
          Error al cargar los cupones. El backend puede estar iniciando — intenta recargar en unos segundos.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cupones */}
        <div className="lg:col-span-1 space-y-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Cupones creados</p>
          {campaigns.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center">
              <Tag size={24} className="text-gray-300 mx-auto mb-2" />
              <p className="text-gray-400 text-sm">Sin cupones aún</p>
            </div>
          ) : campaigns.map((c) => (
            <button key={c.id} onClick={() => setSelectedId(c.id === selectedId ? null : c.id)}
              className={`w-full text-left bg-white border rounded-xl p-4 transition-all ${
                selectedId === c.id ? "border-brand-400 ring-2 ring-brand-100" : "border-gray-200 hover:border-gray-300"
              }`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    {c.coupon_mode === "static"
                      ? <Hash size={11} className="text-purple-500 shrink-0" />
                      : <Zap size={11} className="text-brand-500 shrink-0" />
                    }
                    <p className="font-semibold text-gray-900 text-sm truncate">{c.name}</p>
                  </div>
                  <p className="text-xs text-gray-500">
                    {c.discount_type === "percentage"
                      ? <span className="flex items-center gap-1"><Percent size={11} />{c.discount_value}% OFF</span>
                      : <span className="flex items-center gap-1"><DollarSign size={11} />${c.discount_value.toLocaleString("es-CL")} CLP</span>
                    }
                  </p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-mono shrink-0 ${
                  c.coupon_mode === "static" ? "bg-purple-50 text-purple-700" : "bg-gray-100 text-gray-600"
                }`}>
                  {c.coupon_mode === "static" ? c.static_code : `${c.prefix}-XXXX`}
                </span>
              </div>
              {c.coupon_mode === "dynamic" && (
                <p className="text-xs text-gray-400 mt-2">{c.codes_sent} códigos enviados</p>
              )}
            </button>
          ))}
        </div>

        {/* Códigos enviados (solo para dinámicos) */}
        <div className="lg:col-span-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {selectedId ? "Códigos enviados" : "Todos los códigos"} ({sends.length})
          </p>
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            {sends.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-sm">
                {selectedId
                  ? campaigns.find(c => c.id === selectedId)?.coupon_mode === "static"
                    ? "Los cupones estáticos no generan códigos individuales."
                    : "Sin códigos enviados en esta campaña"
                  : "Sin códigos generados aún"}
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 text-xs text-gray-400 uppercase">
                    <th className="text-left px-4 py-3">Código</th>
                    <th className="text-left px-4 py-3 hidden md:table-cell">Email</th>
                    <th className="text-center px-4 py-3">Usado</th>
                    <th className="text-left px-4 py-3 hidden lg:table-cell">Campaña</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {sends.slice(0, 50).map((s) => (
                    <tr key={s.code} className="hover:bg-gray-50">
                      <td className="px-4 py-2.5">
                        <code className="text-xs font-mono font-bold text-brand-700 bg-brand-50 px-2 py-0.5 rounded">{s.code}</code>
                      </td>
                      <td className="px-4 py-2.5 hidden md:table-cell">
                        <span className="text-xs text-gray-500">{s.email}</span>
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        {s.used
                          ? <Check size={14} className="text-green-500 mx-auto" />
                          : <span className="text-xs text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-2.5 hidden lg:table-cell">
                        <span className="text-xs text-gray-400 truncate block max-w-[160px]">{s.campaign}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
