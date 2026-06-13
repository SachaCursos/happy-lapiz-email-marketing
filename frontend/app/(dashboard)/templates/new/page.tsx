"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { templatesApi } from "@/lib/api";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TemplateBlockEditor, TemplateEditorSaveData } from "@/components/TemplateBlockEditor";

export default function NewTemplatePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [saved, setSaved] = useState(false);

  const mutation = useMutation({
    mutationFn: (data: TemplateEditorSaveData) =>
      templatesApi.create({
        name: data.name,
        html_content: data.html,
        json_blocks: data.blocks,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates"] });
      router.push("/templates");
    },
  });

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-3 px-6 py-3 border-b border-gray-200 bg-white shrink-0">
        <Link href="/templates" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft size={14} /> Volver
        </Link>
        <h1 className="text-sm font-semibold text-gray-900">Nueva plantilla</h1>
      </div>
      {mutation.isError && (
        <div className="px-6 py-2 bg-red-50 border-b border-red-200 text-red-700 text-sm">
          Error al guardar. Intenta de nuevo.
        </div>
      )}
      <div className="flex-1 overflow-hidden">
        <TemplateBlockEditor
          onSave={(data) => mutation.mutate(data)}
          saving={mutation.isPending}
          saved={saved}
        />
      </div>
    </div>
  );
}
