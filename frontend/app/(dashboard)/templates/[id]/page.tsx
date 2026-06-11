"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/lib/api";
import { Template } from "@/lib/types";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import {
  TemplateBlockEditor,
  TemplateEditorSaveData,
  parseEditorState,
  Block,
} from "@/components/TemplateBlockEditor";

export default function EditTemplatePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const tplId = Number(id);

  const { data: tpl, isLoading, isError } = useQuery<Template>({
    queryKey: ["template", tplId],
    queryFn: () => templatesApi.get(tplId).then((r) => r.data),
    staleTime: 0,
  });

  const [initialBlocks, setInitialBlocks] = useState<Block[]>([]);
  const [initialPlainText, setInitialPlainText] = useState("");
  const [initialMode, setInitialMode] = useState<"blocks" | "plain">("blocks");
  const [initialHtmlOverride, setInitialHtmlOverride] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (tpl) {
      const state = parseEditorState(tpl.json_blocks);
      setInitialBlocks(state.blocks);
      setInitialPlainText(state.plainText);
      setInitialMode(state.mode);

      // If there are no saved blocks and no plain-text state, the template was created
      // without the block editor. Load html_content as the HTML override so the content
      // is visible and editable in the "HTML" tab without corruption on save.
      const hasNoBlockData = !state.blocks.length && !state.plainText;
      setInitialHtmlOverride(hasNoBlockData && tpl.html_content ? tpl.html_content : null);

      setReady(true);
    }
  }, [tpl]);

  const mutation = useMutation({
    mutationFn: (data: TemplateEditorSaveData) =>
      templatesApi.update(tplId, {
        name: data.name,
        subject_default: data.subject,
        preview_text: data.previewText || null,
        html_content: data.html,
        json_blocks: data.blocks,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates"] });
      qc.invalidateQueries({ queryKey: ["template", tplId] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="h-5 bg-gray-200 rounded w-40 animate-pulse mb-6" />
        <div className="h-8 bg-gray-200 rounded w-64 animate-pulse" />
      </div>
    );
  }

  if (isError || !tpl) {
    return (
      <div className="p-8">
        <Link href="/templates" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-4">
          <ArrowLeft size={15} /> Volver
        </Link>
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          No se encontró la plantilla.
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-3 px-6 py-3 border-b border-gray-200 bg-white shrink-0">
        <Link href="/templates" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft size={14} /> Volver
        </Link>
        <h1 className="text-sm font-semibold text-gray-900 truncate">{tpl.name}</h1>
      </div>
      {mutation.isError && (
        <div className="px-6 py-2 bg-red-50 border-b border-red-200 text-red-700 text-sm">
          Error al guardar. Intenta de nuevo.
        </div>
      )}
      {ready && (
        <div className="flex-1 overflow-hidden">
          <TemplateBlockEditor
            initialBlocks={initialBlocks}
            initialPlainText={initialPlainText}
            initialMode={initialMode}
            initialHtmlOverride={initialHtmlOverride}
            initialName={tpl.name}
            initialSubject={tpl.subject_default}
            initialPreviewText={tpl.preview_text ?? ""}
            onSave={(data) => mutation.mutate(data)}
            saving={mutation.isPending}
            saved={saved}
          />
        </div>
      )}
    </div>
  );
}
