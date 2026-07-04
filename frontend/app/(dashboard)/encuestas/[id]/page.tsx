"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ArrowLeft, Download, Star, Trash2, Users, Pencil } from "lucide-react";
import Link from "next/link";

interface Question {
  id: number;
  question: string;
  type: "text" | "multiple_choice" | "stars" | "nps";
  options: string[] | null;
  sort_order: number;
}

interface Answer {
  question_id: number;
  answer_text: string | null;
  answer_number: number | null;
  answer_choice: string | null;
}

interface SurveyResponse {
  id: number;
  email: string | null;
  submitted_at: string;
  answers: Answer[];
}

interface SurveyData {
  survey: { id: number; name: string; slug: string };
  questions: Question[];
  responses: SurveyResponse[];
}

function StarDisplay({ value }: { value: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star key={n} size={14} className={n <= value ? "fill-yellow-400 text-yellow-400" : "text-gray-200"} />
      ))}
    </div>
  );
}

function NpsBar({ value }: { value: number }) {
  const color = value >= 9 ? "bg-green-500" : value >= 7 ? "bg-yellow-400" : "bg-red-400";
  return (
    <span className={`inline-flex items-center justify-center w-8 h-8 rounded-lg text-white text-sm font-bold ${color}`}>
      {value}
    </span>
  );
}

function getAnswer(q: Question, answers: Answer[]) {
  const a = answers.find((x) => x.question_id === q.id);
  if (!a) return <span className="text-gray-300 text-xs italic">Sin respuesta</span>;

  if (q.type === "text") return <p className="text-sm text-gray-700">{a.answer_text || "—"}</p>;
  if (q.type === "multiple_choice") return <span className="text-sm font-medium text-gray-800">{a.answer_choice || "—"}</span>;
  if (q.type === "stars") return <StarDisplay value={a.answer_number || 0} />;
  if (q.type === "nps") return <NpsBar value={a.answer_number ?? 0} />;
  return null;
}

function downloadCSV(data: SurveyData) {
  const headers = ["Fecha", "Email", ...data.questions.map((q) => q.question)];
  const rows = data.responses.map((r) => [
    new Date(r.submitted_at).toLocaleString("es-CL"),
    r.email || "",
    ...data.questions.map((q) => {
      const a = r.answers.find((x) => x.question_id === q.id);
      if (!a) return "";
      return a.answer_text ?? a.answer_choice ?? String(a.answer_number ?? "");
    }),
  ]);

  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\n");

  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `encuesta-${data.survey.slug}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function aggregateNPS(responses: SurveyResponse[], question: Question) {
  const values = responses
    .map((r) => r.answers.find((a) => a.question_id === question.id)?.answer_number)
    .filter((v): v is number => v != null);
  if (!values.length) return null;
  const promoters = values.filter((v) => v >= 9).length;
  const detractors = values.filter((v) => v <= 6).length;
  return Math.round(((promoters - detractors) / values.length) * 100);
}

function aggregateStars(responses: SurveyResponse[], question: Question) {
  const values = responses
    .map((r) => r.answers.find((a) => a.question_id === question.id)?.answer_number)
    .filter((v): v is number => v != null);
  if (!values.length) return null;
  return (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1);
}

function aggregateChoices(responses: SurveyResponse[], question: Question) {
  const choices: Record<string, number> = {};
  for (const r of responses) {
    const a = r.answers.find((x) => x.question_id === question.id);
    if (a?.answer_choice) choices[a.answer_choice] = (choices[a.answer_choice] || 0) + 1;
  }
  return Object.entries(choices).sort((a, b) => b[1] - a[1]);
}

export default function SurveyResponsesPage() {
  const params = useParams();
  const router = useRouter();
  const qc = useQueryClient();
  const surveyId = Number(params.id);

  const { data, isLoading } = useQuery<SurveyData>({
    queryKey: ["survey-responses", surveyId],
    queryFn: () => api.get(`/surveys/${surveyId}/responses`).then((r) => r.data),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.delete(`/surveys/${surveyId}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["surveys"] }); router.push("/encuestas"); },
  });

  if (isLoading) {
    return <div className="p-8 text-gray-400 text-sm">Cargando...</div>;
  }

  if (!data) {
    return <div className="p-8 text-gray-400 text-sm">Encuesta no encontrada.</div>;
  }

  const { survey, questions, responses } = data;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/encuestas" className="text-gray-400 hover:text-gray-700">
            <ArrowLeft size={18} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{survey.name}</h1>
            <p className="text-xs text-gray-400 font-mono mt-0.5">/encuesta/{survey.slug}</p>
          </div>
        </div>
        <div className="flex gap-2">
          {responses.length > 0 && (
            <button
              onClick={() => downloadCSV(data)}
              className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
            >
              <Download size={14} /> Exportar CSV
            </button>
          )}
          <Link
            href={`/encuestas/${surveyId}/edit`}
            className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
          >
            <Pencil size={14} /> Editar
          </Link>
          <button
            onClick={() => { if (confirm("¿Eliminar esta encuesta y todas sus respuestas?")) deleteMutation.mutate(); }}
            className="flex items-center gap-2 px-3 py-2 border border-red-200 text-red-500 rounded-lg text-sm hover:bg-red-50"
          >
            <Trash2 size={14} /> Eliminar
          </button>
        </div>
      </div>

      {/* Resumen por pregunta */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
        <div className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-3">
          <div className="w-10 h-10 bg-brand-100 rounded-lg flex items-center justify-center shrink-0">
            <Users size={18} className="text-brand-600" />
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-900">{responses.length}</p>
            <p className="text-xs text-gray-400">Respuestas totales</p>
          </div>
        </div>

        {questions.map((q) => {
          if (q.type === "nps") {
            const nps = aggregateNPS(responses, q);
            return (
              <div key={q.id} className="bg-white border border-gray-200 rounded-xl p-4">
                <p className="text-xs text-gray-400 mb-1 truncate">{q.question}</p>
                {nps != null ? (
                  <p className="text-2xl font-bold text-gray-900">NPS {nps > 0 ? "+" : ""}{nps}</p>
                ) : <p className="text-sm text-gray-300">Sin datos</p>}
              </div>
            );
          }
          if (q.type === "stars") {
            const avg = aggregateStars(responses, q);
            return (
              <div key={q.id} className="bg-white border border-gray-200 rounded-xl p-4">
                <p className="text-xs text-gray-400 mb-1 truncate">{q.question}</p>
                {avg != null ? (
                  <div className="flex items-center gap-2">
                    <p className="text-2xl font-bold text-gray-900">{avg}</p>
                    <StarDisplay value={Math.round(Number(avg))} />
                  </div>
                ) : <p className="text-sm text-gray-300">Sin datos</p>}
              </div>
            );
          }
          if (q.type === "multiple_choice") {
            const counts = aggregateChoices(responses, q);
            return (
              <div key={q.id} className="bg-white border border-gray-200 rounded-xl p-4">
                <p className="text-xs text-gray-400 mb-2 truncate">{q.question}</p>
                {counts.length === 0 ? <p className="text-sm text-gray-300">Sin datos</p> : (
                  <div className="space-y-1.5">
                    {counts.map(([opt, count]) => (
                      <div key={opt} className="flex items-center justify-between gap-2">
                        <span className="text-xs text-gray-600 truncate">{opt}</span>
                        <span className="text-xs font-bold text-gray-900 shrink-0">{count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          }
          return null;
        })}
      </div>

      {/* Tabla de respuestas individuales */}
      {responses.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-xl p-12 text-center text-gray-400 text-sm">
          Sin respuestas aún
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-xs text-gray-400 uppercase">
                  <th className="text-left px-4 py-3 whitespace-nowrap">Fecha</th>
                  <th className="text-left px-4 py-3 whitespace-nowrap">Email</th>
                  {questions.map((q) => (
                    <th key={q.id} className="text-left px-4 py-3 max-w-[200px]">
                      <span className="truncate block">{q.question}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {responses.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                      {new Date(r.submitted_at).toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" })}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                      {r.email || <span className="text-gray-300 italic">Anónimo</span>}
                    </td>
                    {questions.map((q) => (
                      <td key={q.id} className="px-4 py-3 max-w-[200px]">
                        {getAnswer(q, r.answers)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
