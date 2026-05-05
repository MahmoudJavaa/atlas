"use client";

import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";

// Pages that should NOT show the sidebar (full-screen / public pages)
const FULL_SCREEN_PATHS = ["/login", "/register", "/onboarding", "/audit", "/"];

export function ConditionalLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isFullScreen = FULL_SCREEN_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));

  if (isFullScreen) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  );
}
