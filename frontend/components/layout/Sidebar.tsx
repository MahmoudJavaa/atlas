"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard, Search, Globe, MapPin, BarChart2, Bot, Settings,
  CheckSquare, LogOut, User, ChevronDown,
} from "lucide-react";
import { clsx } from "clsx";
import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { getPendingCount } from "@/lib/api";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/modules/technical-seo", label: "Technical SEO", icon: Search },
  { href: "/modules/keywords", label: "Keywords", icon: Globe },
  { href: "/modules/local-seo", label: "Local SEO", icon: MapPin },
  { href: "/modules/analytics", label: "Analytics", icon: BarChart2 },
  { href: "/modules/agent", label: "Atlas Agent", icon: Bot },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout, isAuthenticated } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);

  const { data: countData } = useQuery({
    queryKey: ["pending-count"],
    queryFn: getPendingCount,
    enabled: isAuthenticated,
    refetchInterval: 30000,
  });

  const pendingCount = countData?.count ?? 0;

  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      {/* Logo */}
      <div className="p-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-atlas-500 rounded-lg flex items-center justify-center">
            <Globe size={14} className="text-white" />
          </div>
          <span className="font-bold text-white text-lg">Atlas</span>
        </div>
        <p className="text-gray-500 text-xs mt-1">SEO & GEO Agent</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
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

        {/* Approval Queue with badge */}
        <Link
          href="/approval-queue"
          className={clsx(
            "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
            pathname === "/approval-queue"
              ? "bg-atlas-500/20 text-atlas-400 font-medium"
              : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
          )}
        >
          <CheckSquare size={16} />
          <span className="flex-1">Review Queue</span>
          {pendingCount > 0 && (
            <span className="bg-atlas-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[18px] text-center leading-none">
              {pendingCount > 99 ? "99+" : pendingCount}
            </span>
          )}
        </Link>

        <div className="pt-2 border-t border-gray-800 mt-2">
          <Link
            href="/settings"
            className={clsx(
              "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
              pathname === "/settings" || pathname.startsWith("/settings/")
                ? "bg-atlas-500/20 text-atlas-400 font-medium"
                : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
            )}
          >
            <Settings size={16} />
            Settings
          </Link>
        </div>
      </nav>

      {/* User menu */}
      <div className="p-3 border-t border-gray-800">
        {isAuthenticated && user ? (
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="w-full flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-gray-800 transition-colors text-left"
            >
              <div className="w-7 h-7 bg-atlas-500/20 rounded-full flex items-center justify-center shrink-0">
                <User size={13} className="text-atlas-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white text-xs font-medium truncate">{user.full_name}</p>
                <p className="text-gray-500 text-xs truncate">{user.plan}</p>
              </div>
              <ChevronDown size={12} className="text-gray-600 shrink-0" />
            </button>

            {showUserMenu && (
              <div className="absolute bottom-full left-0 right-0 mb-1 bg-gray-800 border border-gray-700 rounded-xl shadow-xl py-1 z-50">
                <div className="px-3 py-2 border-b border-gray-700">
                  <p className="text-white text-xs font-medium">{user.email}</p>
                  <p className="text-gray-500 text-xs capitalize">{user.plan} plan</p>
                </div>
                <button
                  onClick={() => { setShowUserMenu(false); logout(); }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-gray-400 hover:text-red-400 hover:bg-red-500/10 text-sm transition-colors"
                >
                  <LogOut size={13} />
                  Sign out
                </button>
              </div>
            )}
          </div>
        ) : (
          <p className="text-gray-600 text-xs text-center">Atlas v1.0</p>
        )}
      </div>
    </aside>
  );
}
