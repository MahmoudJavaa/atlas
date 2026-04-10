"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  FileText,
  MapPin,
  BarChart2,
  Link2,
  Bot,
  Settings,
  Globe,
} from "lucide-react";
import { clsx } from "clsx";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/modules/technical-seo", label: "Technical SEO", icon: Search },
  { href: "/modules/keywords", label: "Keywords", icon: Globe },
  { href: "/modules/local-seo", label: "Local SEO", icon: MapPin },
  { href: "/modules/analytics", label: "Analytics", icon: BarChart2 },
  { href: "/modules/agent", label: "Atlas Agent", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      <div className="p-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-atlas-500 rounded-lg flex items-center justify-center">
            <Globe size={14} className="text-white" />
          </div>
          <span className="font-bold text-white text-lg">Atlas</span>
        </div>
        <p className="text-gray-500 text-xs mt-1">SEO & GEO Agent</p>
      </div>

      <nav className="flex-1 p-3 space-y-0.5">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname === href || pathname.startsWith(href + "/")
                ? "bg-atlas-500/20 text-atlas-400 font-medium"
                : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>

      <div className="p-3 border-t border-gray-800">
        <p className="text-gray-600 text-xs text-center">Atlas v1.0</p>
      </div>
    </aside>
  );
}
