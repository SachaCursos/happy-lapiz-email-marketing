"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";

function UnsubscribeContent() {
  const params = useSearchParams();
  const email = params.get("email") ?? "";
  const token = params.get("token") ?? "";
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [detail, setDetail] = useState("");

  useEffect(() => {
    if (!email || !token) {
      setStatus("error");
      setDetail("Enlace inválido. Asegúrate de usar el enlace del email.");
      return;
    }
    api
      .get("/contacts/unsubscribe", { params: { email, token } })
      .then(() => setStatus("success"))
      .catch((e) => {
        setStatus("error");
        setDetail(e.response?.data?.detail ?? "No se pudo procesar tu solicitud. Intenta de nuevo.");
      });
  }, [email, token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 max-w-md w-full text-center">
        <img
          src="/logo.png"
          alt=""
          className="h-8 mx-auto mb-8 opacity-60"
          onError={(e) => (e.currentTarget.style.display = "none")}
        />

        {status === "loading" && (
          <p className="text-gray-400 text-sm">Procesando...</p>
        )}

        {status === "success" && (
          <>
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-lg font-semibold text-gray-900 mb-2">Cancelación exitosa</h1>
            <p className="text-sm text-gray-500">
              <span className="font-medium text-gray-700">{email}</span> ha sido eliminado de nuestra lista.
              Ya no recibirás emails de nuestra parte.
            </p>
          </>
        )}

        {status === "error" && (
          <>
            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="text-lg font-semibold text-gray-900 mb-2">Algo salió mal</h1>
            <p className="text-sm text-gray-500">{detail}</p>
          </>
        )}
      </div>
    </div>
  );
}

export default function UnsubscribePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-400 text-sm">Cargando...</p>
      </div>
    }>
      <UnsubscribeContent />
    </Suspense>
  );
}
