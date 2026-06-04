"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Tag, Plus, X, Check, Percent, DollarSign } from "lucide-react";

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
  const [form, setForm] = useState({
    name: "", discount_type: "percentage", discount_value: 10,
    min_purchase: 0, prefix: "HL", expires_at: "",
  });
  const mutation = useMutation({
    mutationFn: () => api.post("/coupons/campaigns", form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["coupon-campaigns"] }); onClose(); },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-5">
          <h3 className="font-bold text-gray-900">Nueva campaña de cupones</h3>
          <button onClick={onClose}><X size={18} className="text-gray-400" /></button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Nombre interno</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Ej: Cyber Day 30% OFF"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Tipo</label>
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
              <label className="block text-xs font-medium text-gray-700 mb-1">Prefijo del código</label>
              <input value={form.prefix} onChange={(e) => setForm({ ...form, prefix: e.target.value.toUpperCase() })}
                placeholder="HL"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Compra mínima (CLP)</label>
              <input type="number" value={form.min_purchase}
                onChange={(e) => setForm({ ...form, min_purchase: Number(e.target.value) })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Vence (opcional)</label>
            <input type="datetime-local" value={form.expires_at}
              onChange={(e) => setForm({ ...form, expires_at: e.target.value })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <p className="text-xs text-blue-700 font-medium mb-1">Ejemplo de código generado:</p>
            <code className="text-sm font-mono font-bold text-blue-800">{form.prefix || "HL"}-ABCD1234</code>
            <p className="text-xs text-blue-500 mt-1">Cada contacto recibe un código único al recibir el email</p>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button onClick={onClose} className="flex-1 border border-gray-200 rounded-lg py-2 text-sm font-medium text-gray-600 hover:bg-gray-50">
            Cancelar
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!form.name || mutation.isPending}
            className="flex-1 bg-brand-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
          >
            {mutation.isPending ? "Creando..." : "Crear campaña"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CouponsPage() {
  const [showNew, setShowNew] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data: campaigns = [] } = useQuery<CouponCampaign[]>({
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
          <h1 className="text-2xl font-bold text-gray-900">Cupones dinámicos</h1>
          <p className="text-gray-500 mt-1 text-sm">Genera códigos únicos por contacto directamente en Shopify</p>
        </div>
        <button onClick={() => setShowNew(true)}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700">
          <Plus size={15} /> Nueva campaña
        </button>
      </div>

      {/* Cómo funciona */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 mb-6">
        <p className="text-sm font-bold text-amber-800 mb-3">¿Cómo funcionan los cupones dinámicos?</p>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs text-amber-700">
          {[
            { n: "1", t: "Creas una campaña aquí", d: "Define descuento, prefijo y vencimiento" },
            { n: "2", t: "Usas {{ coupon_code }} en la plantilla", d: "Pon esta variable en el HTML del email" },
            { n: "3", t: "Al enviar, se genera un código único", d: "HL-XXXXXX distinto para cada persona" },
            { n: "4", t: "Shopify lo activa automáticamente", d: "El cliente lo usa al pagar en la tienda" },
          ].map((s) => (
            <div key={s.n} className="flex gap-2">
              <span className="w-5 h-5 rounded-full bg-amber-800 text-white flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">{s.n}</span>
              <div><p className="font-semibold">{s.t}</p><p className="text-amber-600">{s.d}</p></div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Campañas */}
        <div className="lg:col-span-1 space-y-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Campañas activas</p>
          {campaigns.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center">
              <Tag size={24} className="text-gray-300 mx-auto mb-2" />
              <p className="text-gray-400 text-sm">Sin campañas aún</p>
            </div>
          ) : campaigns.map((c) => (
            <button key={c.id} onClick={() => setSelectedId(c.id === selectedId ? null : c.id)}
              className={`w-full text-left bg-white border rounded-xl p-4 transition-all ${
                selectedId === c.id ? "border-brand-400 ring-2 ring-brand-100" : "border-gray-200 hover:border-gray-300"
              }`}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-gray-900 text-sm">{c.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {c.discount_type === "percentage"
                      ? <span className="flex items-center gap-1"><Percent size={11} />{c.discount_value}% OFF</span>
                      : <span className="flex items-center gap-1"><DollarSign size={11} />${c.discount_value.toLocaleString("es-CL")} CLP</span>
                    }
                  </p>
                </div>
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-mono">{c.prefix}-XXXX</span>
              </div>
              <p className="text-xs text-gray-400 mt-2">{c.codes_sent} códigos enviados</p>
            </button>
          ))}
        </div>

        {/* Códigos enviados */}
        <div className="lg:col-span-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            {selectedId ? "Códigos enviados" : "Todos los códigos"} ({sends.length})
          </p>
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
            {sends.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-sm">
                {selectedId ? "Sin códigos enviados en esta campaña" : "Sin códigos generados aún"}
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
