"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import axios from "axios";
import { CheckCircle, Star, Loader2 } from "lucide-react";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL
  ? `${process.env.NEXT_PUBLIC_BACKEND_URL}/api`
  : "/api";

interface Question {
  id: number;
  question: string;
  type: "text" | "multiple_choice" | "stars" | "nps";
  options: string[] | null;
  required: boolean;
  sort_order: number;
}

interface Survey {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  questions: Question[];
}

function StarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const [hovered, setHovered] = useState(0);
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          onMouseEnter={() => setHovered(n)}
          onMouseLeave={() => setHovered(0)}
          className="transition-transform hover:scale-110"
        >
          <Star
            size={32}
            className={`transition-colors ${
              n <= (hovered || value) ? "fill-yellow-400 text-yellow-400" : "text-gray-300"
            }`}
          />
        </button>
      ))}
    </div>
  );
}

function NpsRating({ value, onChange }: { value: number | null; onChange: (v: number) => void }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-1.5 flex-wrap">
        {Array.from({ length: 11 }, (_, i) => (
          <button
            key={i}
            type="button"
            onClick={() => onChange(i)}
            className={`w-10 h-10 rounded-lg text-sm font-bold border-2 transition-all ${
              value === i
                ? "border-brand-500 bg-brand-500 text-white"
                : "border-gray-200 text-gray-600 hover:border-brand-400 hover:text-brand-600"
            }`}
          >
            {i}
          </button>
        ))}
      </div>
      <div className="flex justify-between text-xs text-gray-400">
        <span>Muy improbable</span>
        <span>Muy probable</span>
      </div>
    </div>
  );
}

export default function SurveyPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [survey, setSurvey] = useState<Survey | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // answers keyed by question id
  const [answers, setAnswers] = useState<Record<number, { text?: string; number?: number; choice?: string }>>({});

  useEffect(() => {
    const email = new URLSearchParams(window.location.search).get("email");
    axios.get(`${BASE}/surveys/public/${slug}`)
      .then((r) => {
        setSurvey(r.data);
        if (email) setEmailPrefill(email);
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [slug]);

  const [emailPrefill, setEmailPrefill] = useState("");

  function setAnswer(qid: number, patch: { text?: string; number?: number; choice?: string }) {
    setAnswers((prev) => ({ ...prev, [qid]: { ...prev[qid], ...patch } }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!survey) return;

    // Validate required
    for (const q of survey.questions) {
      if (!q.required) continue;
      const a = answers[q.id];
      if (!a) { setError(`Por favor responde: "${q.question}"`); return; }
      if (q.type === "text" && !a.text?.trim()) { setError(`Por favor responde: "${q.question}"`); return; }
      if (q.type === "multiple_choice" && !a.choice) { setError(`Por favor selecciona una opción en: "${q.question}"`); return; }
      if ((q.type === "stars" || q.type === "nps") && a.number == null) { setError(`Por favor califica: "${q.question}"`); return; }
    }
    setError("");
    setSubmitting(true);

    const payload = {
      respondent_email: emailPrefill || null,
      answers: survey.questions.map((q) => {
        const a = answers[q.id] || {};
        return {
          question_id: q.id,
          answer_text: a.text || null,
          answer_number: a.number ?? null,
          answer_choice: a.choice || null,
        };
      }),
    };

    try {
      await axios.post(`${BASE}/surveys/public/${slug}/submit`, payload);
      setSubmitted(true);
    } catch {
      setError("Ocurrió un error al enviar. Intenta de nuevo.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 size={28} className="animate-spin text-gray-400" />
      </div>
    );
  }

  if (notFound || !survey) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-300">404</p>
          <p className="text-gray-400 mt-2">Encuesta no encontrada</p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle size={32} className="text-green-500" />
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">¡Gracias por tu respuesta!</h2>
          <p className="text-gray-500 text-sm">Tus respuestas han sido registradas correctamente.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-xl mx-auto">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="w-10 h-10 bg-brand-600 rounded-xl flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-sm">H</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{survey.name}</h1>
          {survey.description && (
            <p className="text-gray-500 mt-2 text-sm">{survey.description}</p>
          )}
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {survey.questions.map((q, idx) => (
            <div key={q.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
              <label className="block text-sm font-semibold text-gray-900 mb-4">
                <span className="text-gray-400 font-normal mr-2">{idx + 1}.</span>
                {q.question}
                {q.required && <span className="text-red-500 ml-1">*</span>}
              </label>

              {q.type === "text" && (
                <textarea
                  rows={3}
                  value={answers[q.id]?.text || ""}
                  onChange={(e) => setAnswer(q.id, { text: e.target.value })}
                  placeholder="Escribe tu respuesta aquí..."
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                />
              )}

              {q.type === "multiple_choice" && q.options && (
                <div className="space-y-2">
                  {q.options.map((opt) => (
                    <label key={opt} className="flex items-center gap-3 cursor-pointer group">
                      <input
                        type="radio"
                        name={`q-${q.id}`}
                        value={opt}
                        checked={answers[q.id]?.choice === opt}
                        onChange={() => setAnswer(q.id, { choice: opt })}
                        className="w-4 h-4 text-brand-600 border-gray-300 focus:ring-brand-500"
                      />
                      <span className="text-sm text-gray-700 group-hover:text-gray-900">{opt}</span>
                    </label>
                  ))}
                </div>
              )}

              {q.type === "stars" && (
                <StarRating
                  value={answers[q.id]?.number || 0}
                  onChange={(v) => setAnswer(q.id, { number: v })}
                />
              )}

              {q.type === "nps" && (
                <NpsRating
                  value={answers[q.id]?.number ?? null}
                  onChange={(v) => setAnswer(q.id, { number: v })}
                />
              )}
            </div>
          ))}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-brand-600 text-white rounded-xl py-3 text-sm font-semibold hover:bg-brand-700 disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {submitting && <Loader2 size={16} className="animate-spin" />}
            {submitting ? "Enviando..." : "Enviar respuestas"}
          </button>
        </form>
      </div>
    </div>
  );
}
