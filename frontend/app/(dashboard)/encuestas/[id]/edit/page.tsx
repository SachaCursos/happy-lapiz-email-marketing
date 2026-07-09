"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Plus, Trash2, ChevronUp, ChevronDown, ArrowLeft, Loader2 } from "lucide-react";

type QuestionType = "text" | "multiple_choice" | "stars" | "nps";

interface Question {
  id?: number;
  question: string;
  type: QuestionType;
  options: string[];
  required: boolean;
  sort_order: number;
}

interface SurveyDetail {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  status: string;
  questions: Question[];
}

const TYPE_LABELS: Record<QuestionType, string> = {
  text: "Texto libre",
  multiple_choice: "Opción múltiple",
  stars: "Estrellas (1-5)",
  nps: "NPS (0-10)",
};

function QuestionCard({
  q, idx, total, onChange, onDelete, onMove,
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
              <button onClick={() => onChange({ options: q.options.filter((_, i) => i !== oi) })} className="text-gray-300 hover:text-red-400">
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
            <button onClick={addOption} className="px-3 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200">
              Agregar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function EditSurveyPage() {
  const params = useParams();
  const router = useRouter();
  const qc = useQueryClient();
  const surveyId = Number(params.id);

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  const { data, isLoading, isError } = useQuery<SurveyDetail>({
    queryKey: ["survey", surveyId],
    queryFn: () => api.get(`/surveys/${surveyId}`).then((r) => r.data),
    enabled: Number.isFinite(surveyId) && surveyId > 0,
  });

  useEffect(() => {
    if (data && !loaded) {
      setName(data.name);
      setSlug(data.slug);
      setDescription(data.description || "");
      setQuestions(data.questions.map((q) => ({ ...q, options: q.options || [] })));
      setLoaded(true);
    }
  }, [data, loaded]);

  const mutation = useMutation({
    mutationFn: () =>
      api.put(`/surveys/${surveyId}`, {
        name,
        slug,
        description: description || null,
        questions: questions.map((q, i) => ({ ...q, sort_order: i })),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["surveys"] });
      qc.invalidateQueries({ queryKey: ["survey", surveyId] });
      router.push(`/encuestas/${surveyId}`);
    },
    onError: (e: { response?: { data?: { detail?: string } } }) => {
      setError(e.response?.data?.detail || "Error al guardar los cambios.");
    },
  });

  function addQuestion() {
    setQuestions((prev) => [...prev, { question: "", type: "text", options: [], required: true, sort_order: prev.length }]);
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

  if (!Number.isFinite(surveyId) || surveyId <= 0) {
    return (
      <div className="p-8 text-sm text-gray-500">
        Encuesta no válida.{" "}
        <button onClick={() => router.push("/encuestas")} className="text-brand-600 hover:underline">
          Volver al listado
        </button>
      </div>
    );
  }

  if (isLoading || (data && !loaded)) {
    return (
      <div className="p-8 flex items-center gap-2 text-gray-400 text-sm">
        <Loader2 size={16} className="animate-spin" /> Cargando encuesta...
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-8 max-w-lg">
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-4 text-sm text-red-700">
          No se pudo cargar la encuesta para editar.
        </div>
        <button
          onClick={() => router.push("/encuestas")}
          className="mt-4 text-sm text-brand-600 hover:underline"
        >
          ← Volver a encuestas
        </button>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => router.push(`/encuestas/${surveyId}`)} className="text-gray-400 hover:text-gray-700">
          <ArrowLeft size={18} />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Editar encuesta</h1>
          <p className="text-gray-500 mt-0.5 text-sm">Los cambios en preguntas no afectan respuestas ya guardadas</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Info básica */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          <h2 className="font-semibold text-gray-900 text-sm">Información básica</h2>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Nombre interno</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Slug (URL)</label>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 shrink-0">/encuesta/</span>
              <input
                value={slug}
                onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
              />
            </div>
            <p className="text-xs text-gray-400 mt-1">Si cambias el slug, los links anteriores dejarán de funcionar.</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Descripción (opcional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
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
            onClick={() => router.push(`/encuestas/${surveyId}`)}
            className="flex-1 border border-gray-200 rounded-lg py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={mutation.isPending}
            className="flex-1 bg-brand-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-brand-700 disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {mutation.isPending && <Loader2 size={14} className="animate-spin" />}
            {mutation.isPending ? "Guardando..." : "Guardar cambios"}
          </button>
        </div>
      </form>
    </div>
  );
}
