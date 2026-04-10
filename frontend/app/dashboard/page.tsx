"use client";

import { useQuery } from "@tanstack/react-query";
import { getSites, getCrawlSummary, getContentPages, getPerformance } from "@/lib/api";
import { StatCard } from "@/components/ui/StatCard";
import { AlertTriangle, CheckCircle, FileText, TrendingUp, RefreshCw, PlusCircle } from "lucide-react";
import Link from "next/link";

export default function Dashboard() {
  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });
  const activeSite = sites[0];

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

  if (sites.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center">
        <div className="card max-w-md w-full">
          <h2 className="text-xl font-bold text-white mb-2">Welcome to Atlas</h2>
          <p className="text-gray-400 mb-4">Add your first site to get started with autonomous SEO.</p>
          <Link href="/settings" className="btn-primary inline-flex items-center gap-2">
            <PlusCircle size={16} />
            Add Site
          </Link>
        </div>
      </div>
    );
  }

  const publishedThisWeek = content.filter((p: any) => {
    if (!p.published_at) return false;
    const pub = new Date(p.published_at);
    const week = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    return pub > week;
  }).length;

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-400 text-sm mt-0.5">{activeSite?.name} — {activeSite?.url}</p>
        </div>
        <div className="flex gap-2">
          <Link href="/modules/technical-seo" className="btn-secondary inline-flex items-center gap-2 text-sm">
            <RefreshCw size={14} />
            Run Crawl
          </Link>
          <Link href="/modules/local-seo" className="btn-primary inline-flex items-center gap-2 text-sm">
            <PlusCircle size={14} />
            Generate Page
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
          value={performance?.total_clicks?.toLocaleString() ?? "—"}
          sub={performance ? `${performance.keyword_count} keywords` : "Connect GSC"}
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
          sub={`${content.length} total pages`}
          trend="up"
        />
      </div>

      {/* Sites */}
      <div className="card">
        <h2 className="font-semibold text-white mb-3">Active Sites</h2>
        <div className="space-y-2">
          {sites.map((site: any) => (
            <div key={site.id} className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
              <div>
                <p className="text-white font-medium text-sm">{site.name}</p>
                <p className="text-gray-500 text-xs">{site.url}</p>
              </div>
              <span className="text-xs text-gray-400 bg-gray-700 px-2 py-0.5 rounded">
                {site.cms_type || "unknown"}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent content */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-white">Recent Content</h2>
          <Link href="/modules/local-seo" className="text-atlas-400 text-sm hover:underline">Generate →</Link>
        </div>
        {content.length === 0 ? (
          <p className="text-gray-500 text-sm">No content pages yet. Generate your first page.</p>
        ) : (
          <div className="space-y-2">
            {content.slice(0, 5).map((page: any) => (
              <div key={page.id} className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
                <div>
                  <p className="text-white text-sm font-medium truncate max-w-xs">{page.title || page.keyword}</p>
                  <p className="text-gray-500 text-xs">{page.page_type} · {page.word_count} words</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full border ${
                  page.status === "published"
                    ? "bg-green-900/40 text-green-400 border-green-800"
                    : "bg-gray-700 text-gray-400 border-gray-600"
                }`}>
                  {page.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
