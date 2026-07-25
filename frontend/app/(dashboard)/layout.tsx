"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Menu } from "lucide-react";
import { Sidebar } from "@/components/layout/sidebar";
import { authApi } from "@/lib/api";
import { User } from "@/lib/types";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { data: user } = useQuery<User>({
    queryKey: ["me"],
    queryFn: () => authApi.me().then((r) => r.data),
  });
  const shopName = user?.shop_name || "Email Marketing";

  useEffect(() => {
    const token = localStorage.getItem("hb_token");
    if (!token) router.replace("/login");
  }, [router]);

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Overlay oscuro al abrir el menú en móvil */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <div className="flex-1 flex flex-col min-w-0">
        {/* Barra superior — solo visible en móvil */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 bg-gray-950 border-b border-gray-800 sticky top-0 z-10">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-gray-400 hover:text-white p-1 -ml-1"
            aria-label="Abrir menú"
          >
            <Menu size={22} />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-brand-600 rounded flex items-center justify-center">
              <span className="text-white font-bold text-xs">{shopName.charAt(0).toUpperCase()}</span>
            </div>
            <span className="text-white font-semibold text-sm">{shopName}</span>
          </div>
        </header>

        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
