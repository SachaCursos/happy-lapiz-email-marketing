"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  LayoutDashboard,
  Users,
  Filter,
  FileText,
  Send,
  Zap,
  MousePointerClick,
  Settings,
  LogOut,
  BarChart2,
  Tag,
} from "lucide-react";
import { clearToken } from "@/lib/auth";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard",    label: "Dashboard",        icon: LayoutDashboard },
  { href: "/contacts",     label: "Contactos",        icon: Users },
  { href: "/segments",     label: "Segmentos",        icon: Filter },
  { href: "/templates",    label: "Plantillas",       icon: FileText },
  { href: "/campaigns",    label: "Campañas",         icon: Send },
  { href: "/automations",  label: "Automatizaciones", icon: Zap },
  { href: "/forms",        label: "Formularios",      icon: MousePointerClick },
  { href: "/asuntos",      label: "Asuntos",          icon: BarChart2 },
  { href: "/coupons",      label: "Cupones",           icon: Tag },
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();

  // Cerrar sidebar al navegar en móvil
  useEffect(() => {
    onClose();
  }, [pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  function logout() {
    clearToken();
    router.push("/login");
  }

  return (
    <aside
      className={cn(
        "w-60 bg-gray-950 border-r border-gray-800 flex flex-col",
        // Móvil: drawer fijo que entra/sale desde la izquierda
        "fixed inset-y-0 left-0 z-30 transition-transform duration-200 ease-in-out",
        // Desktop: vuelve al flujo normal
        "md:static md:inset-auto md:z-auto md:translate-x-0",
        isOpen ? "translate-x-0" : "-translate-x-full"
      )}
    >
      <div className="px-6 py-5 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">H</span>
          </div>
          <div>
            <p className="text-white font-semibold text-sm">Happy Lápiz</p>
            <p className="text-gray-500 text-xs">Email Marketing</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/60"
              )}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="px-3 py-4 border-t border-gray-800 space-y-0.5">
        <Link
          href="/settings"
          className={cn(
            "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
            pathname === "/settings"
              ? "bg-gray-800 text-white"
              : "text-gray-400 hover:text-white hover:bg-gray-800/60"
          )}
        >
          <Settings size={16} />
          Configuración
        </Link>
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800/60 transition-colors"
        >
          <LogOut size={16} />
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}
