"use client";

import { useEffect, useState } from "react";
import { templatesApi } from "@/lib/api";
import { Template } from "@/lib/types";
import { htmlToBlocks, blocksToHtml } from "@/components/TemplateBlockEditor";

type Status = "pending" | "running" | "ok" | "skip" | "err";
interface Row { id: number; name: string; status: Status; info: string; blocks: number }

export default function SyncTemplatesPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    templatesApi.list().then((r) => {
      const templates: Template[] = r.data;
      setRows(
        templates.map((t) => ({
          id: t.id,
          name: t.name,
          status: "pending",
          info: "",
          blocks: 0,
        }))
      );
    });
  }, []);

  async function runSync() {
    setRunning(true);
    setDone(false);

    const templates: Template[] = (await templatesApi.list()).data as Template[];

    for (const tpl of templates) {
      setRows((prev) =>
        prev.map((r) => (r.id === tpl.id ? { ...r, status: "running", info: "Procesando..." } : r))
      );

      const full = (await templatesApi.get(tpl.id)).data as Template;

      if (!full.html_content?.trim()) {
        setRows((prev) =>
          prev.map((r) => (r.id === tpl.id ? { ...r, status: "skip", info: "Sin HTML" } : r))
        );
        continue;
      }

      try {
        const blocks = htmlToBlocks(full.html_content);

        if (blocks.length === 0) {
          setRows((prev) =>
            prev.map((r) =>
              r.id === tpl.id ? { ...r, status: "skip", info: "No se detectaron bloques (HTML no estándar)" } : r
            )
          );
          continue;
        }

        const newHtml = blocksToHtml(blocks);

        await templatesApi.update(tpl.id, {
          json_blocks: blocks,
          html_content: newHtml,
        });

        setRows((prev) =>
          prev.map((r) =>
            r.id === tpl.id ? { ...r, status: "ok", info: `${blocks.length} bloques guardados`, blocks: blocks.length } : r
          )
        );
      } catch (e) {
        setRows((prev) =>
          prev.map((r) =>
            r.id === tpl.id ? { ...r, status: "err", info: String(e) } : r
          )
        );
      }

      // small delay to avoid hammering the API
      await new Promise((res) => setTimeout(res, 200));
    }

    setRunning(false);
    setDone(true);
  }

  const statusIcon: Record<Status, string> = {
    pending: "⏳",
    running: "🔄",
    ok: "✅",
    skip: "⚠️",
    err: "❌",
  };

  const counts = {
    ok: rows.filter((r) => r.status === "ok").length,
    skip: rows.filter((r) => r.status === "skip").length,
    err: rows.filter((r) => r.status === "err").length,
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-xl font-bold mb-1">Sincronizar plantillas</h1>
      <p className="text-sm text-gray-500 mb-6">
        Convierte el HTML de todas las plantillas a bloques editables usando el parser actualizado.
      </p>

      <button
        onClick={runSync}
        disabled={running || rows.length === 0}
        className="px-5 py-2.5 bg-brand-600 text-white rounded-xl text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors mb-6"
      >
        {running ? "Procesando..." : "▶ Sincronizar todas las plantillas"}
      </button>

      {done && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-xl text-sm">
          <strong>Sincronización completada.</strong> ✅ {counts.ok} actualizadas · ⚠️ {counts.skip} sin cambios · ❌ {counts.err} errores
        </div>
      )}

      <div className="border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            <tr>
              <th className="px-4 py-3 text-left w-10">ID</th>
              <th className="px-4 py-3 text-left">Plantilla</th>
              <th className="px-4 py-3 text-center w-20">Bloques</th>
              <th className="px-4 py-3 text-left">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row) => (
              <tr key={row.id} className={row.status === "running" ? "bg-blue-50" : ""}>
                <td className="px-4 py-3 text-gray-400">{row.id}</td>
                <td className="px-4 py-3 font-medium text-gray-800">{row.name}</td>
                <td className="px-4 py-3 text-center text-gray-500">
                  {row.status === "ok" ? row.blocks : "—"}
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {statusIcon[row.status]} {row.info || row.status}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
