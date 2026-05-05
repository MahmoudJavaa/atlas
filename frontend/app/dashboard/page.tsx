"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSites, getCrawlSummary, getContentPages, getPerformance, getActions } from "@/lib/api";
import { StatCard } from "@/components/ui/StatCard";
import { RefreshCw, PlusCircle, ChevronDown, ArrowRight, AlertTriangle, CheckCircle2, Zap } from "lucide-react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth/AuthGuard";

function DashboardContent() {
  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null);

  // Auto-select: prefer first complete site, fallback to first site
  const siteList = sites as any[];
  const activeSite = selectedSiteId
    ? siteList.find((s) => s.id === selectedSiteId)
    : siteList.find((s) => s.onboarding_status === "complete") ?? siteList[0];

  const { data: crawlSummary } = useQuery({
    queryKey: ["crawl-summary", activeSite?.id],
    queryFn: () => getCrawlSummary(activeSite.id),
    enabled: !!activeSite,
  });

  const { data: content = [] } = useQuery({
    queryKey: ["content", activeSite?.id],
    queryFn: () => getContentPages(activeSite.id),
    enabled: !!activeSite,
  });

  const { data: performance } = useQuery({
    queryKey: ["performance", activeSite?.id],
    queryFn: () => getPerformance(activeSite.id),
    enabled: !!activeSite,
  });

  const { data: pendingActions = [] } = useQuery({
    queryKey: ["actions", activeSite?.id, "pending"],
    queryFn: () => getActions(activeSite.id, "pending"),
    enabled: !!activeSite,
    refetchInterval: 15000,
  });

  if (siteList.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center">
        <div className="card max-w-md w-full">
          <h2 className="text-xl font-bold text-white mb-2">Welcome to Atlas</h2>
          <p className="text-gray-400 mb-4">Add your first site to get started with autonomous SEO.</p>
          <Link href="/onboarding" className="btn-primary inline-flex items-center gap-2">
            <PlusCircle size={16} /> Analyse a site
          </Link>
        </div>
      </div>
    );
  }

  const publishedThisWeek = (content as any[]).filter((p: any) => {
    if (!p.published_at) return false;
    return new Date(p.published_at) > new Date(Date.now() - 7 * 86400000);
  }).length;

  const pending = pendingActions as any[];

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header with site selector */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          {/* Site selector dropdown */}
          {siteList.length === 1 ? (
            <p className="text-gray-400 text-sm mt-0.5">{activeSite?.name} — {activeSite?.url}</p>
          ) : (
            <div className="relative mt-1">
              <select
                className="appearance-none bg-gray-800/60 border border-gray-700 text-gray-200 rounded-lg pl-3 pr-8 py-1.5 text-sm focus:outline-none focus:border-atlas-500 cursor-pointer"
                value={activeSite?.id ?? ""}
                onChange={(e) => setSelectedSiteId(Number(e.target.value))}
              >
                {siteList.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.name} — {s.url}</option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <Link href="/modules/technical-seo" className="btn-secondary inline-flex items-center gap-2 text-sm">
            <RefreshCw size={14} /> Run Crawl
          </Link>
          <Link href="/onboarding" className="btn-primary inline-flex items-center gap-2 text-sm">
            <PlusCircle size={14} /> Analyse Site
          </Link>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Pages Crawled"
          value={crawlSummary?.total_pages ?? "—"}
          sub={crawlSummary ? `Avg severity: ${crawlSummary.avg_severity_score}` : "Run a crawl first"}
        />
        <StatCard
          label="Organic Clicks"
          value={performance?.total_clicks?.toLocaleString() ?? "0"}
          sub={performance ? `${performance.keyword_count} keywords` : "Connect Google Search Console"}
          trend="up"
        />
        <StatCard
          label="Avg Position"
          value={performance?.avg_position ?? "—"}
          sub="Last 28 days"
        />
        <StatCard
          label="Published This Week"
          value={publishedThisWeek}
          sub={`${(content as any[]).length} total pages`}
          trend="up"
        />
      </div>

      {/* Pending action plan */}
      {pending.length > 0 && (
        <div className="card border border-atlas-500/30 bg-atlas-500/5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Zap size={16} className="text-atlas-400" />
              <h2 className="font-semibold text-white">Action Plan Ready</h2>
              <span className="text-xs bg-atlas-500/20 text-atlas-300 px-2 py-0.5 rounded-full border border-atlas-500/30">
                {pending.length} pending
              </span>
            </div>
            <Link href="/approval-queue" className="btn-primary flex items-center gap-1.5 text-sm py-1.5">
              Review Plan <ArrowRight size={14} />
            </Link>
          </div>
          <div className="space-y-2">
            {pending.slice(0, 4).map((a: any) => (
              <div key={a.id} className="flex items-center justify-between bg-gray-800/60 rounded-lg px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    a.priority === 1 ? "bg-red-400" : a.priority === 2 ? "bg-orange-400" : "bg-yellow-400"
                  }`} />
                  <p className="text-gray-200 text-sm truncate">{a.title}</p>
                </div>
                <span className="text-xs text-gray-500 shrink-0 ml-2">{a.action_type?.replace(/_/g, " ")}</span>
              </div>
            ))}
            {pending.length > 4 && (
              <p className="text-gray-500 text-xs text-center pt-1">+{pending.length - 4} more actions</p>
            )}
          </div>
        </div>
      )}

      {/* Two-column: crawl issues + sites */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Crawl health */}
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-white">Site Health</h2>
            <Link href="/modules/technical-seo" className="text-atlas-400 text-sm hover:underline">
              Full report →
            </Link>
          </div>
          {crawlSummary ? (
            <div className="space-y-2">
              {[
                { label: "Critical issues", value: crawlSummary.critical_count ?? 0, color: "text-red-400 bg-red-500/10" },
                { label: "Warnings", value: crawlSummary.warning_count ?? 0, color: "text-yellow-400 bg-yellow-500/10" },
                { label: "Info notices", value: crawlSummary.info_count ?? 0, color: "text-blue-400 bg-blue-500/10" },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between p-2.5 bg-gray-800/50 rounded-lg">
                  <span className="text-gray-400 text-sm">{item.label}</span>
                  <span className={`text-sm font-bold px-2.5 py-0.5 rounded-full ${item.color}`}>{item.value}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <AlertTriangle size={24} className="text-gray-700 mx-auto mb-2" />
              <p className="text-gray-500 text-sm">No crawl data yet.</p>
              <Link href="/modules/technical-seo" className="text-atlas-400 text-sm hover:underline mt-1 inline-block">
                Run a crawl →
              </Link>
            </div>
          )}
        </div>

        {/* All sites */}
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-white">Your Sites</h2>
            <Link href="/onboarding" className="text-atlas-400 text-sm hover:underline">+ Add site</Link>
          </div>
          <div className="space-y-2">
            {siteList.map((site: any) => (
              <button
                key={site.id}
                onClick={() => setSelectedSiteId(site.id)}
                className={`w-full flex items-center justify-between p-3 rounded-lg text-left transition-colors ${
                  activeSite?.id === site.id
                    ? "bg-atlas-500/10 border border-atlas-500/30"
                    : "bg-gray-800/50 hover:bg-gray-800"
                }`}
              >
                <div className="min-w-0">
                  <p className="text-white font-medium text-sm truncate">{site.name}</p>
                  <p className="text-gray-500 text-xs truncate">{site.url}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-2">
                  {site.onboarding_status === "complete" && (
                    <CheckCircle2 size={14} className="text-green-400" />
                  )}
                  <span className="text-xs text-gray-400 bg-gray-700 px-2 py-0.5 rounded">
                    {site.cms_type || "other"}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Recent content */}
      {(content as any[]).length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-white">Recent Content</h2>
            <Link href="/modules/local-seo" className="text-atlas-400 text-sm hover:underline">Generate →</Link>
          </div>
          <div className="space-y-2">
            {(content as any[]).slice(0, 5).map((page: any) => (
              <div key={page.id} className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
                <div className="min-w-0">
                  <p className="text-white text-sm font-medium truncate">{page.title || page.keyword}</p>
                  <p className="text-gray-500 text-xs">{page.page_type} · {page.word_count} words</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full border shrink-0 ml-2 ${
                  page.status === "published"
                    ? "bg-green-900/40 text-green-400 border-green-800"
                    : "bg-gray-700 text-gray-400 border-gray-600"
                }`}>
                  {page.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  return <AuthGuard><DashboardContent /></AuthGuard>;
}
