"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Plus, Trash2, GripVertical, ChevronDown, ChevronUp } from "lucide-react";

type QuestionType = "text" | "multiple_choice" | "stars" | "nps";

interface Question {
  question: string;
  type: QuestionType;
  options: string[];
  required: boolean;
  sort_order: number;
}

const TYPE_LABELS: Record<QuestionType, string> = {
  text: "Texto libre",
  multiple_choice: "Opción múltiple",
  stars: "Estrellas (1-5)",
  nps: "NPS (0-10)",
};

const TYPE_DESCRIPTIONS: Record<QuestionType, string> = {
  text: "El cliente escribe libremente",
  multiple_choice: "Elige una opción de una lista",
  stars: "Rating visual de 1 a 5 estrellas",
  nps: "¿Qué tan probable es que nos recomienden?",
};

function QuestionCard({
  q, idx, total,
  onChange, onDelete, onMove,
}: {
  q: Question; idx: number; total: number;
  onChange: (patch: Partial<Question>) => void;
  onDelete: () => void;
  onMove: (dir: -1 | 1) => void;
}) {
  const [newOpt, setNewOpt] = useState("");

  function addOption() {
    const opt = newOpt.trim();
    if (!opt || q.options.includes(opt)) return;
    onChange({ options: [...q.options, opt] });
    setNewOpt("");
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="flex flex-col gap-0.5">
          <button onClick={() => onMove(-1)} disabled={idx === 0} className="text-gray-300 hover:text-gray-500 disabled:opacity-30">
            <ChevronUp size={14} />
          </button>
          <button onClick={() => onMove(1)} disabled={idx === total - 1} className="text-gray-300 hover:text-gray-500 disabled:opacity-30">
            <ChevronDown size={14} />
          </button>
        </div>
        <GripVertical size={14} className="text-gray-300 shrink-0" />
        <span className="text-xs font-bold text-gray-400 w-5 shrink-0">{idx + 1}</span>
        <div className="flex-1 min-w-0">
          <input
            value={q.question}
            onChange={(e) => onChange({ question: e.target.value })}
            placeholder="Escribe la pregunta..."
            className="w-full text-sm font-medium border-0 outline-none text-gray-900 placeholder:text-gray-400"
          />
        </div>
        <button onClick={onDelete} className="text-gray-300 hover:text-red-400 transition-colors shrink-0">
          <Trash2 size={14} />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Tipo de pregunta</label>
          <select
            value={q.type}
            onChange={(e) => onChange({ type: e.target.value as QuestionType, options: [] })}
            className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {(Object.keys(TYPE_LABELS) as QuestionType[]).map((t) => (
              <option key={t} value={t}>{TYPE_LABELS[t]}</option>
            ))}
          </select>
          <p className="text-xs text-gray-400 mt-1">{TYPE_DESCRIPTIONS[q.type]}</p>
        </div>

        <div className="flex items-center gap-2 pt-5">
          <input
            type="checkbox"
            id={`req-${idx}`}
            checked={q.required}
            onChange={(e) => onChange({ required: e.target.checked })}
            className="w-4 h-4 rounded text-brand-600 border-gray-300 focus:ring-brand-500"
          />
          <label htmlFor={`req-${idx}`} className="text-sm text-gray-700 cursor-pointer">Obligatoria</label>
        </div>
      </div>

      {q.type === "multiple_choice" && (
        <div className="mt-3 space-y-2">
          <p className="text-xs text-gray-500 font-medium">Opciones de respuesta</p>
          {q.options.map((opt, oi) => (
            <div key={oi} className="flex items-center gap-2">
              <span className="text-xs text-gray-400 w-5">{oi + 1}.</span>
              <span className="flex-1 text-sm text-gray-700 bg-gray-50 rounded-lg px-3 py-1.5">{opt}</span>
              <button
                onClick={() => onChange({ options: q.options.filter((_, i) => i !== oi) })}
                className="text-gray-300 hover:text-red-400"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
          <div className="flex gap-2">
            <input
              value={newOpt}
              onChange={(e) => setNewOpt(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addOption())}
              placeholder="Nueva opción..."
              className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <button
              onClick={addOption}
              className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200"
            >
              Agregar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function NewSurveyPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [questions, setQuestions] = useState<Question[]>([
    { question: "", type: "text", options: [], required: true, sort_order: 0 },
  ]);
  const [error, setError] = useState("");

  function handleNameChange(v: string) {
    setName(v);
    if (!slugEdited) {
      setSlug(v.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""));
    }
  }

  function addQuestion() {
    setQuestions((prev) => [
      ...prev,
      { question: "", type: "text", options: [], required: true, sort_order: prev.length },
    ]);
  }

  function updateQuestion(idx: number, patch: Partial<Question>) {
    setQuestions((prev) => prev.map((q, i) => (i === idx ? { ...q, ...patch } : q)));
  }

  function deleteQuestion(idx: number) {
    setQuestions((prev) => prev.filter((_, i) => i !== idx));
  }

  function moveQuestion(idx: number, dir: -1 | 1) {
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= questions.length) return;
    const arr = [...questions];
    [arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]];
    setQuestions(arr.map((q, i) => ({ ...q, sort_order: i })));
  }

  const mutation = useMutation({
    mutationFn: () =>
      api.post("/surveys", {
        name,
        slug,
        description: description || null,
        questions: questions.map((q, i) => ({ ...q, sort_order: i })),
      }),
    onSuccess: () => router.push("/encuestas"),
    onError: (e: { response?: { data?: { detail?: string } } }) => {
      setError(e.response?.data?.detail || "Error al crear la encuesta.");
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError("El nombre es obligatorio."); return; }
    if (!slug.trim()) { setError("El slug es obligatorio."); return; }
    if (questions.length === 0) { setError("Agrega al menos una pregunta."); return; }
    for (const q of questions) {
      if (!q.question.trim()) { setError("Todas las preguntas deben tener texto."); return; }
      if (q.type === "multiple_choice" && q.options.length < 2) {
        setError(`La pregunta "${q.question}" necesita al menos 2 opciones.`); return;
      }
    }
    setError("");
    mutation.mutate();
  }

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Nueva encuesta</h1>
        <p className="text-gray-500 mt-1 text-sm">Configura las preguntas y comparte el link con tus clientes</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Info básica */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          <h2 className="font-semibold text-gray-900 text-sm">Información básica</h2>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Nombre interno</label>
            <input
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              placeholder="Ej: Encuesta post compra navidad"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Slug (URL)</label>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 shrink-0">/encuestas/</span>
              <input
                value={slug}
                onChange={(e) => { setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "")); setSlugEdited(true); }}
                placeholder="post-compra"
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Descripción (opcional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="Ej: Cuéntanos cómo fue tu experiencia de compra"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>
        </div>

        {/* Preguntas */}
        <div className="space-y-3">
          <h2 className="font-semibold text-gray-900 text-sm">Preguntas</h2>
          {questions.map((q, idx) => (
            <QuestionCard
              key={idx}
              q={q}
              idx={idx}
              total={questions.length}
              onChange={(patch) => updateQuestion(idx, patch)}
              onDelete={() => deleteQuestion(idx)}
              onMove={(dir) => moveQuestion(idx, dir)}
            />
          ))}
          <button
            type="button"
            onClick={addQuestion}
            className="w-full border-2 border-dashed border-gray-200 rounded-xl py-4 text-sm text-gray-400 hover:border-brand-400 hover:text-brand-600 transition-colors flex items-center justify-center gap-2"
          >
            <Plus size={15} /> Agregar pregunta
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => router.push("/encuestas")}
            className="flex-1 border border-gray-200 rounded-lg py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="flex-1 bg-brand-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-60"
          >
            {mutation.isPending ? "Creando..." : "Crear encuesta"}
          </button>
        </div>
      </form>
    </div>
  );
}
