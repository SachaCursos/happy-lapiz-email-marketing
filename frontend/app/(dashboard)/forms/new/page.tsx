"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { formsApi } from "@/lib/api";
import { FormTrigger } from "@/lib/types";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function NewFormPage() {
  const router = useRouter();

  const [name, setName] = useState("Popup principal");
  const [title, setTitle] = useState("¡Únete y recibe ofertas exclusivas!");
  const [description, setDescription] = useState("Suscríbete para ser el primero en enterarte de novedades y descuentos.");
  const [buttonText, setButtonText] = useState("Suscribirme");
  const [successMessage, setSuccessMessage] = useState("¡Gracias! Pronto recibirás noticias nuestras.");
  const [collectName, setCollectName] = useState(true);
  const [collectPhone, setCollectPhone] = useState(false);
  const [trigger, setTrigger] = useState<FormTrigger>("delay");
  const [delaySeconds, setDelaySeconds] = useState(5);
  const [scrollPct, setScrollPct] = useState(50);

  const mutation = useMutation({
    mutationFn: () =>
      formsApi.create({
        name,
        title,
        description: description || null,
        button_text: buttonText,
        success_message: successMessage,
        collect_name: collectName,
        collect_phone: collectPhone,
        popup_trigger: trigger,
        popup_delay_seconds: delaySeconds,
        popup_scroll_pct: scrollPct,
      }),
    onSuccess: (res) => router.push(`/forms/${res.data.id}`),
  });

  const isValid = name && title && buttonText;

  return (
    <div className="p-8 max-w-xl">
      <Link href="/forms" className="inline-flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6">
        <ArrowLeft size={15} /> Volver
      </Link>
      <h1 className="text-2xl font-bold text-gray-900 mb-3">Nuevo formulario de suscripción</h1>
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 mb-8 text-sm text-blue-800">
        <p className="font-semibold mb-1">Paso 1 de 2 — Configuración básica</p>
        <p>Completa el nombre y texto del popup. Una vez creado, entrarás al editor completo donde podrás: <strong>personalizar colores y diseño</strong>, <strong>agregar campos personalizados</strong> (para quién es el regalo, edad, etc.) y configurar <strong>formulario de múltiples pasos</strong>.</p>
      </div>

      {mutation.isError && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          Error al crear. Intenta de nuevo.
        </div>
      )}

      <div className="space-y-5">
        {/* Nombre interno */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Nombre interno *</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ej. Popup principal happylapiz.cl"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        {/* Contenido */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          <p className="text-sm font-semibold text-gray-700">Contenido del popup</p>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Título *</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="ej. ¡Recibe ofertas exclusivas de Happy Lápiz!"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Descripción</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="ej. Suscríbete y sé el primero en enterarte de nuevas experiencias y descuentos."
              rows={2}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Texto del botón *</label>
              <input
                value={buttonText}
                onChange={(e) => setButtonText(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Mensaje de éxito</label>
              <input
                value={successMessage}
                onChange={(e) => setSuccessMessage(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>
        </div>

        {/* Campos */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <p className="text-sm font-semibold text-gray-700">Campos del formulario</p>
          <p className="text-xs text-gray-400">El campo de email siempre se incluye.</p>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={collectName}
              onChange={(e) => setCollectName(e.target.checked)}
              className="w-4 h-4 accent-brand-600"
            />
            <span className="text-sm text-gray-700">Pedir nombre</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={collectPhone}
              onChange={(e) => setCollectPhone(e.target.checked)}
              className="w-4 h-4 accent-brand-600"
            />
            <span className="text-sm text-gray-700">Pedir teléfono</span>
          </label>
        </div>

        {/* Trigger */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          <p className="text-sm font-semibold text-gray-700">¿Cuándo mostrar el popup?</p>
          <div className="space-y-2">
            {([
              { value: "delay", label: "Después de X segundos" },
              { value: "exit_intent", label: "Al intentar salir de la página (exit intent)" },
              { value: "scroll", label: "Al hacer scroll hasta X%" },
            ] as { value: FormTrigger; label: string }[]).map((t) => (
              <label key={t.value} className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                trigger === t.value ? "border-brand-400 bg-brand-50" : "border-gray-200 hover:border-gray-300"
              }`}>
                <input
                  type="radio"
                  name="trigger"
                  value={t.value}
                  checked={trigger === t.value}
                  onChange={() => setTrigger(t.value)}
                  className="accent-brand-600"
                />
                <span className="text-sm text-gray-700">{t.label}</span>
              </label>
            ))}
          </div>

          {trigger === "delay" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Segundos de espera
              </label>
              <input
                type="number"
                min={0}
                value={delaySeconds}
                onChange={(e) => setDelaySeconds(Number(e.target.value))}
                className="w-32 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          )}

          {trigger === "scroll" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Porcentaje de scroll
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min={10}
                  max={90}
                  step={5}
                  value={scrollPct}
                  onChange={(e) => setScrollPct(Number(e.target.value))}
                  className="flex-1 accent-brand-600"
                />
                <span className="text-sm font-semibold text-gray-700 w-10">{scrollPct}%</span>
              </div>
            </div>
          )}
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !isValid}
          className="w-full py-2.5 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-60 transition-colors"
        >
          {mutation.isPending ? "Creando..." : "Crear formulario → ir al editor de diseño"}
        </button>
      </div>
    </div>
  );
}
