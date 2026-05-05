"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSites, crawlSite, getCrawlResults } from "@/lib/api";
import { RefreshCw, AlertTriangle, Info, AlertCircle, X, ExternalLink, CheckCircle, ChevronRight } from "lucide-react";

// ── Issue descriptions & how-to-fix ──────────────────────────────────────────

const ISSUE_META: Record<string, { label: string; severity: string; description: string; fix: string }> = {
  // Critical
  "Missing <title> tag": {
    label: "Missing title tag",
    severity: "critical",
    description: "This page has no <title> tag. Search engines display the title in search results and use it as a primary ranking signal.",
    fix: "Add a unique, descriptive <title> tag between 40–60 characters. Include your primary keyword near the beginning.",
  },
  "No H1 tag": {
    label: "Missing H1",
    severity: "critical",
    description: "The page has no H1 heading. H1 is the main on-page heading and a strong ranking signal for search engines.",
    fix: "Add exactly one <h1> tag containing your primary keyword for this page. It should describe the page's main topic clearly.",
  },
  "Status 4xx": {
    label: "4xx Error",
    severity: "critical",
    description: "This URL returned a 4xx error (not found or forbidden). These pages waste crawl budget and damage user experience.",
    fix: "If the page was moved, set up a 301 redirect to the new URL. If it no longer exists, return a proper 404 and remove internal links pointing to it.",
  },
  "Status 5xx": {
    label: "5xx Server Error",
    severity: "critical",
    description: "The server returned a 5xx error. This indicates a server-side problem that prevents the page from loading.",
    fix: "Check your server logs for errors. Fix the underlying server issue. If the problem persists, contact your hosting provider.",
  },
  "Noindex tag present": {
    label: "Noindex tag",
    severity: "critical",
    description: "A noindex meta tag tells search engines not to index this page. It will not appear in search results.",
    fix: "Remove the <meta name='robots' content='noindex'> tag if you want this page to rank. Only use noindex on pages you intentionally want to hide from search engines.",
  },
  // Warnings
  "Title too short": {
    label: "Title too short",
    severity: "warning",
    description: "The page title is shorter than 30 characters. Short titles miss keyword opportunities and look thin in search results.",
    fix: "Expand the title to 40–60 characters. Include your primary keyword and make it compelling for users to click.",
  },
  "Title too long": {
    label: "Title too long",
    severity: "warning",
    description: "The title exceeds 60 characters and will be cut off in search results, hiding important information from users.",
    fix: "Shorten the title to under 60 characters while keeping the primary keyword at the front.",
  },
  "Thin content": {
    label: "Thin content",
    severity: "warning",
    description: "The page has fewer than 300 words. Thin content pages are unlikely to rank well and may be seen as low quality by Google.",
    fix: "Expand the page with at least 500–800 words of original, helpful content that answers user questions about the topic.",
  },
  "Multiple H1 tags": {
    label: "Multiple H1 tags",
    severity: "warning",
    description: "Multiple H1 tags confuse search engines about the page's main topic. Each page should have exactly one H1.",
    fix: "Keep only one <h1> tag — the most important heading. Convert additional H1s to <h2> or lower.",
  },
  "No meta description": {
    label: "Missing meta description",
    severity: "warning",
    description: "There is no meta description. While not a direct ranking factor, a good description improves click-through rate from search results.",
    fix: "Write a compelling meta description of 120–155 characters that summarises the page and includes a call to action.",
  },
  "Meta description too long": {
    label: "Meta description too long",
    severity: "warning",
    description: "The meta description exceeds 155 characters and will be truncated in search results.",
    fix: "Shorten the description to 120–155 characters. Keep the most important information first.",
  },
  "Meta description too short": {
    label: "Meta description too short",
    severity: "warning",
    description: "The meta description is very short. This is a missed opportunity to attract clicks from search results.",
    fix: "Expand the description to 120–155 characters with a clear summary and a call to action.",
  },
  // Info
  "No structured data (JSON-LD) found": {
    label: "No schema markup",
    severity: "info",
    description: "No JSON-LD structured data was found. Schema markup helps search engines understand your content and can enable rich results (stars, FAQs, breadcrumbs, etc.).",
    fix: "Add relevant JSON-LD schema. For a business: LocalBusiness or Organization. For products: Product schema. For articles: Article schema. Use Google's Structured Data Markup Helper.",
  },
  "Missing alt text on images": {
    label: "Images missing alt text",
    severity: "info",
    description: "Some images have no alt text. Alt text helps search engines understand image content and is essential for accessibility.",
    fix: "Add descriptive alt text to every image. Describe what is in the image and include relevant keywords where natural.",
  },
};

function getIssueInfo(issueText: string) {
  // Try exact match first, then partial match
  if (ISSUE_META[issueText]) return ISSUE_META[issueText];
  const key = Object.keys(ISSUE_META).find(
    (k) => issueText.toLowerCase().includes(k.toLowerCase()) || k.toLowerCase().includes(issueText.toLowerCase())
  );
  if (key) return ISSUE_META[key];
  return {
    label: issueText,
    severity: "info",
    description: "This issue was detected during the technical SEO audit.",
    fix: "Review this issue and resolve it according to SEO best practices.",
  };
}

// ── Issue modal ───────────────────────────────────────────────────────────────

function IssueModal({ row, onClose }: { row: any; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-gray-800">
          <div className="min-w-0 flex-1 pr-4">
            <a
              href={row.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-atlas-400 hover:underline text-sm font-mono flex items-center gap-1 truncate"
            >
              {row.url} <ExternalLink size={11} className="shrink-0" />
            </a>
            <h2 className="text-white font-semibold mt-1 text-lg leading-tight">
              {row.title || <span className="text-gray-500 italic">No title</span>}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {/* Page stats */}
        <div className="grid grid-cols-4 gap-3 p-5 border-b border-gray-800">
          {[
            { label: "Status", value: row.status_code, color: row.status_code >= 400 ? "text-red-400" : "text-green-400" },
            { label: "Words", value: row.word_count ?? "—", color: "text-white" },
            { label: "Indexable", value: row.indexable ? "Yes" : "No", color: row.indexable ? "text-green-400" : "text-red-400" },
            { label: "Severity", value: row.severity_score ?? "—", color: row.severity_score > 60 ? "text-red-400" : row.severity_score > 30 ? "text-yellow-400" : "text-green-400" },
          ].map((stat) => (
            <div key={stat.label} className="text-center bg-gray-800/50 rounded-xl py-3">
              <p className={`text-lg font-bold ${stat.color}`}>{stat.value}</p>
              <p className="text-gray-500 text-xs mt-0.5">{stat.label}</p>
            </div>
          ))}
        </div>

        {/* Meta info */}
        <div className="p-5 border-b border-gray-800 space-y-2 text-sm">
          {row.canonical && (
            <div className="flex gap-2">
              <span className="text-gray-500 w-28 shrink-0">Canonical:</span>
              <span className="text-gray-300 truncate font-mono text-xs">{row.canonical}</span>
            </div>
          )}
          {row.meta_desc && (
            <div className="flex gap-2">
              <span className="text-gray-500 w-28 shrink-0">Meta desc:</span>
              <span className="text-gray-300 text-xs">{row.meta_desc}</span>
            </div>
          )}
        </div>

        {/* Issues with fix descriptions */}
        <div className="p-5 space-y-3">
          {(["critical", "warning", "info"] as const).map((level) => {
            const issues: string[] = row.issues?.[level] ?? [];
            if (!issues.length) return null;
            return (
              <div key={level}>
                <p className={`text-xs font-bold uppercase tracking-widest mb-2 ${
                  level === "critical" ? "text-red-400" : level === "warning" ? "text-yellow-400" : "text-blue-400"
                }`}>
                  {level === "critical" ? "🔴" : level === "warning" ? "🟡" : "🔵"} {level}
                </p>
                <div className="space-y-2">
                  {issues.map((issue: string, i: number) => {
                    const meta = getIssueInfo(issue);
                    return (
                      <div key={i} className={`rounded-xl p-4 border ${
                        level === "critical"
                          ? "bg-red-500/5 border-red-500/20"
                          : level === "warning"
                          ? "bg-yellow-500/5 border-yellow-500/20"
                          : "bg-blue-500/5 border-blue-500/20"
                      }`}>
                        <div className="flex items-start gap-2 mb-2">
                          {level === "critical" && <AlertCircle size={14} className="text-red-400 shrink-0 mt-0.5" />}
                          {level === "warning" && <AlertTriangle size={14} className="text-yellow-400 shrink-0 mt-0.5" />}
                          {level === "info" && <Info size={14} className="text-blue-400 shrink-0 mt-0.5" />}
                          <p className="text-white font-medium text-sm">{meta.label || issue}</p>
                        </div>
                        <p className="text-gray-400 text-xs mb-3 leading-relaxed">{meta.description}</p>
                        <div className="flex items-start gap-2 bg-green-500/5 border border-green-500/20 rounded-lg p-3">
                          <ChevronRight size={12} className="text-green-400 shrink-0 mt-0.5" />
                          <p className="text-green-300 text-xs leading-relaxed"><span className="font-semibold">How to fix:</span> {meta.fix}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {/* No issues */}
          {!["critical", "warning", "info"].some((l) => (row.issues?.[l]?.length ?? 0) > 0) && (
            <div className="text-center py-6">
              <CheckCircle size={28} className="text-green-400 mx-auto mb-2" />
              <p className="text-gray-300 font-medium">No issues detected</p>
              <p className="text-gray-500 text-sm mt-1">This page passed all SEO checks.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function TechnicalSEO() {
  const qc = useQueryClient();
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null);
  const [maxPages, setMaxPages] = useState(500);
  const [modalRow, setModalRow] = useState<any>(null);
  const [filterLevel, setFilterLevel] = useState<"all" | "critical" | "warning" | "info">("all");

  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });

  // Auto-select first site
  useEffect(() => {
    if (!selectedSiteId && (sites as any[]).length > 0) {
      setSelectedSiteId((sites as any[])[0].id);
    }
  }, [sites, selectedSiteId]);

  const { data: results = [], isLoading: resultsLoading } = useQuery({
    queryKey: ["crawl-results", selectedSiteId],
    queryFn: () => getCrawlResults(selectedSiteId!),
    enabled: !!selectedSiteId,
  });

  const crawlMutation = useMutation({
    mutationFn: () => {
      const site = (sites as any[]).find((s) => s.id === selectedSiteId);
      return crawlSite({ site_id: selectedSiteId!, start_url: site.url, max_pages: maxPages });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crawl-results"] }),
  });

  const activeResults = results as any[];

  // Filter results
  const filteredResults = filterLevel === "all"
    ? activeResults
    : activeResults.filter((r) => (r.issues?.[filterLevel]?.length ?? 0) > 0);

  // Summary counts
  const criticalCount = activeResults.filter((r) => (r.issues?.critical?.length ?? 0) > 0).length;
  const warningCount = activeResults.filter((r) => (r.issues?.warning?.length ?? 0) > 0).length;
  const infoCount = activeResults.filter((r) => (r.issues?.info?.length ?? 0) > 0).length;
  const cleanCount = activeResults.filter((r) =>
    !(r.issues?.critical?.length) && !(r.issues?.warning?.length) && !(r.issues?.info?.length)
  ).length;

  return (
    <div className="space-y-5 max-w-7xl">
      {modalRow && <IssueModal row={modalRow} onClose={() => setModalRow(null)} />}

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Technical SEO</h1>
      </div>

      {/* Controls */}
      <div className="card flex flex-wrap gap-3 items-end">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Site</label>
          <select
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm"
            value={selectedSiteId || ""}
            onChange={(e) => setSelectedSiteId(Number(e.target.value))}
          >
            <option value="">Select site…</option>
            {(sites as any[]).map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Max Pages</label>
          <input
            type="number"
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-28"
            value={maxPages}
            onChange={(e) => setMaxPages(Number(e.target.value))}
            min={1}
            max={5000}
            placeholder="All pages"
          />
        </div>
        <button
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
          disabled={!selectedSiteId || crawlMutation.isPending}
          onClick={() => crawlMutation.mutate()}
        >
          <RefreshCw size={14} className={crawlMutation.isPending ? "animate-spin" : ""} />
          {crawlMutation.isPending ? "Crawling…" : "Run Crawl"}
        </button>
        {crawlMutation.isPending && (
          <p className="text-gray-400 text-sm self-end">Crawling entire site — this may take a few minutes…</p>
        )}
      </div>

      {crawlMutation.isSuccess && (
        <div className="bg-green-900/30 border border-green-800 text-green-400 rounded-lg px-4 py-2 text-sm">
          ✓ Crawl complete — {crawlMutation.data?.pages_crawled} pages audited.
        </div>
      )}

      {/* Summary bar */}
      {activeResults.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Critical", count: criticalCount, level: "critical", color: "text-red-400 bg-red-500/10 border-red-500/20 hover:border-red-500/50" },
            { label: "Warnings", count: warningCount, level: "warning", color: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20 hover:border-yellow-500/50" },
            { label: "Info", count: infoCount, level: "info", color: "text-blue-400 bg-blue-500/10 border-blue-500/20 hover:border-blue-500/50" },
            { label: "Clean", count: cleanCount, level: "all", color: "text-green-400 bg-green-500/10 border-green-500/20 hover:border-green-500/50" },
          ].map((item) => (
            <button
              key={item.label}
              onClick={() => setFilterLevel(filterLevel === item.level as any ? "all" : item.level as any)}
              className={`p-3 rounded-xl border text-left transition-all ${item.color} ${filterLevel === item.level ? "ring-1 ring-current" : ""}`}
            >
              <p className="text-2xl font-bold">{item.count}</p>
              <p className="text-xs mt-0.5 opacity-80">{item.label} pages</p>
            </button>
          ))}
        </div>
      )}

      {/* Results table */}
      {resultsLoading ? (
        <div className="card text-center py-10 text-gray-400">Loading crawl data…</div>
      ) : activeResults.length > 0 ? (
        <div className="card overflow-hidden p-0">
          <div className="p-4 border-b border-gray-800 flex items-center justify-between">
            <h2 className="font-semibold text-white">
              Crawl Results — {filteredResults.length} of {activeResults.length} pages
            </h2>
            <p className="text-xs text-gray-500">Click any row to see issues and fix guidance</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-xs">
                  <th className="text-left p-3 font-medium">URL</th>
                  <th className="text-left p-3 font-medium w-16">Status</th>
                  <th className="text-left p-3 font-medium max-w-[200px]">Title</th>
                  <th className="text-left p-3 font-medium w-16">Words</th>
                  <th className="text-left p-3 font-medium">Issues</th>
                </tr>
              </thead>
              <tbody>
                {filteredResults.map((row: any) => (
                  <tr
                    key={row.id}
                    className="border-b border-gray-800/50 hover:bg-gray-800/60 cursor-pointer transition-colors"
                    onClick={() => setModalRow(row)}
                  >
                    <td className="p-3 text-gray-300 max-w-xs truncate font-mono text-xs">{row.url}</td>
                    <td className="p-3">
                      <span className={`text-xs font-bold ${row.status_code >= 400 ? "text-red-400" : row.status_code >= 300 ? "text-yellow-400" : "text-green-400"}`}>
                        {row.status_code}
                      </span>
                    </td>
                    <td className="p-3 text-gray-300 max-w-[200px] truncate text-xs">{row.title || <span className="text-gray-600 italic">No title</span>}</td>
                    <td className="p-3 text-gray-400 text-xs">{row.word_count ?? "—"}</td>
                    <td className="p-3">
                      <div className="flex gap-1 flex-wrap">
                        {(row.issues?.critical?.length ?? 0) > 0 && (
                          <span className="text-xs px-1.5 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/25">
                            {row.issues.critical.length} critical
                          </span>
                        )}
                        {(row.issues?.warning?.length ?? 0) > 0 && (
                          <span className="text-xs px-1.5 py-0.5 rounded-full bg-yellow-500/15 text-yellow-400 border border-yellow-500/25">
                            {row.issues.warning.length} warning
                          </span>
                        )}
                        {(row.issues?.info?.length ?? 0) > 0 && (
                          <span className="text-xs px-1.5 py-0.5 rounded-full bg-blue-500/15 text-blue-400 border border-blue-500/25">
                            {row.issues.info.length} info
                          </span>
                        )}
                        {!(row.issues?.critical?.length) && !(row.issues?.warning?.length) && !(row.issues?.info?.length) && (
                          <span className="text-xs text-green-400">✓ Clean</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : selectedSiteId ? (
        <div className="card text-center py-12">
          <RefreshCw size={28} className="text-gray-700 mx-auto mb-3" />
          <p className="text-gray-400 font-medium">No crawl data yet</p>
          <p className="text-gray-600 text-sm mt-1">Run a crawl to see technical SEO issues.</p>
        </div>
      ) : null}
    </div>
  );
}
