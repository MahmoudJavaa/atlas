"use client";

import { useState, useEffect, useMemo, Fragment } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSites, crawlSite, getCrawlResults, getAuditSummary } from "@/lib/api";
import {
  RefreshCw, AlertTriangle, Info, AlertCircle, ExternalLink,
  CheckCircle, ChevronDown, ChevronUp, Download, Search,
  Clock, FileText, BarChart2, Zap, Activity
} from "lucide-react";

// ── Issue metadata ─────────────────────────────────────────────────────────────

const ISSUE_META: Record<string, { label: string; severity: "critical" | "warning" | "info"; description: string; fix: string }> = {
  "Missing title tag": { label: "Missing title tag", severity: "critical", description: "No <title> tag found. Search engines display the title in results and use it as a key ranking signal.", fix: "Add a unique <title> between 30–60 chars with your primary keyword near the start." },
  "Missing H1 tag": { label: "Missing H1", severity: "critical", description: "No H1 heading. H1 tells both users and search engines what this page is about.", fix: "Add exactly one <h1> with your primary keyword. Every page needs one." },
  "404 Not Found": { label: "404 Not Found", severity: "critical", description: "This URL returned a 404. It wastes crawl budget and breaks user experience.", fix: "Set up a 301 redirect to the correct URL, or remove all internal links pointing here." },
  "410 Gone": { label: "410 Gone", severity: "critical", description: "Page permanently no longer exists. Make sure this is intentional.", fix: "Remove all internal links to this page and submit a removal request in Google Search Console." },
  "Noindex tag — page excluded from search": { label: "Noindex", severity: "critical", description: "The noindex meta tag prevents this page from appearing in search results.", fix: "Remove <meta name='robots' content='noindex'> unless you intentionally want this page hidden." },
  "Slow page load": { label: "Slow page (>3s)", severity: "critical", description: "Page took over 3 seconds to load. Page speed is a Google ranking factor.", fix: "Optimise images, enable caching, use a CDN, and minify CSS/JS. Target under 1.5s." },
  "Server error": { label: "Server error", severity: "critical", description: "Server returned a 5xx error — page cannot be crawled or served.", fix: "Check your server logs. Fix the underlying server issue or contact your host." },
  "Title too long": { label: "Title too long", severity: "warning", description: "Title exceeds 60 characters and will be cut off in search results.", fix: "Shorten to under 60 chars. Keep the primary keyword at the front." },
  "Title too short": { label: "Title too short", severity: "warning", description: "Title under 30 characters — missing keyword opportunities.", fix: "Expand to 40–60 chars with a descriptive, keyword-rich title." },
  "Missing meta description": { label: "No meta description", severity: "warning", description: "No meta description. A good description improves click-through rate from results.", fix: "Write 120–155 chars summarising the page. Include a call-to-action." },
  "Meta description too long": { label: "Meta desc too long", severity: "warning", description: "Meta description exceeds 160 chars and will be cut off.", fix: "Shorten to 120–155 chars. Put the most important content first." },
  "Missing canonical tag": { label: "No canonical", severity: "warning", description: "No canonical tag. Without it, search engines may index duplicate versions of this page.", fix: "Add <link rel='canonical' href='...'> pointing to the preferred URL." },
  "Thin content": { label: "Thin content", severity: "warning", description: "Under 300 words. Thin pages are unlikely to rank well.", fix: "Expand to at least 500–800 words of original, helpful content." },
  "Multiple H1 tags": { label: "Multiple H1s", severity: "warning", description: "Multiple H1 tags confuse search engines about the page's main topic.", fix: "Keep only one <h1>. Convert the rest to <h2> or lower." },
  "Nofollow tag — links not passed": { label: "Nofollow", severity: "warning", description: "Nofollow meta tag prevents link equity passing from this page.", fix: "Remove nofollow unless intentional." },
  "Duplicate title tag": { label: "Duplicate title", severity: "warning", description: "Another page shares the same title. Duplicate titles confuse search engines.", fix: "Give every page a unique, descriptive title." },
  "Duplicate meta description": { label: "Duplicate meta desc", severity: "warning", description: "Another page shares the same meta description.", fix: "Write unique meta descriptions for each page." },
  "Page buried deep": { label: "Deep page", severity: "warning", description: "More than 4 clicks from the homepage. Deep pages get less crawl priority.", fix: "Add internal links from shallower pages. Restructure navigation." },
  "Page load slow": { label: "Slow page (1.5–3s)", severity: "warning", description: "Load time is 1.5–3 seconds. Users expect pages under 2 seconds.", fix: "Compress images, enable browser caching, reduce unused JavaScript." },
  "Redirect": { label: "Redirect", severity: "warning", description: "This URL redirects to another URL, wasting crawl budget.", fix: "Update internal links to point directly to the final destination URL." },
  "No structured data (JSON-LD) found": { label: "No structured data", severity: "info", description: "No JSON-LD schema markup found. Structured data enables rich results in Google.", fix: "Add Schema.org JSON-LD markup (Article, Product, FAQ, etc.) relevant to your page type." },
  "Missing Open Graph tags": { label: "Missing OG tags", severity: "info", description: "Open Graph tags control how your page looks when shared on social media.", fix: "Add og:title, og:description, and og:image to the <head>." },
  "image(s) missing alt text": { label: "Images missing alt", severity: "info", description: "Images without alt text are invisible to screen readers and miss keyword opportunities.", fix: "Add descriptive alt attributes to every image." },
  "No H2 subheadings on long page": { label: "No H2 subheadings", severity: "info", description: "Long pages without H2 headings are hard to read.", fix: "Break content into sections with descriptive H2 subheadings." },
  "Canonical points to different URL": { label: "Canonicalized away", severity: "info", description: "The canonical points to a different URL — Google will index that URL instead.", fix: "Ensure this is intentional. If not, update canonical to this page's own URL." },
  "Meta description too short": { label: "Meta desc too short", severity: "info", description: "Meta description under 70 chars — too brief to be compelling.", fix: "Expand to 120–155 chars with a persuasive summary and call-to-action." },
  "Blocked by robots.txt": { label: "Blocked by robots.txt", severity: "info", description: "This URL is disallowed in robots.txt.", fix: "If this page should be indexed, update robots.txt to allow it." },
  "Page served over HTTP (not HTTPS)": { label: "HTTP (not HTTPS)", severity: "critical", description: "Page is served over plain HTTP. HTTPS is a Google ranking signal and required for security.", fix: "Install an SSL certificate and redirect all HTTP traffic to HTTPS." },
  "Missing viewport meta tag (not mobile-friendly)": { label: "No viewport meta tag", severity: "warning", description: "Missing <meta name='viewport'>. Google uses mobile-first indexing — non-mobile-friendly pages rank lower.", fix: "Add <meta name='viewport' content='width=device-width, initial-scale=1'> to the <head>." },
  "Non-HTML response": { label: "Non-HTML response", severity: "info", description: "This URL returns a non-HTML content type (JSON, XML, etc.) — no SEO checks apply.", fix: "Ensure internal links don't point to API or binary endpoints." },
  "Request timeout": { label: "Request timeout", severity: "critical", description: "Page took more than 20 seconds to respond and the request was abandoned.", fix: "Check server performance, reduce server response time, and ensure the URL is reachable." },
  "Connection failed": { label: "Connection failed", severity: "critical", description: "The server could not be reached at all — DNS failure or server offline.", fix: "Verify the domain is live and DNS is configured correctly. Check server uptime." },
  "Request failed": { label: "Request failed", severity: "critical", description: "An unexpected network error prevented this page from being crawled.", fix: "Check SSL certificate validity, server firewall rules, and that the URL is publicly accessible." },
};

function getIssueInfo(issueText: string) {
  if (ISSUE_META[issueText]) return ISSUE_META[issueText];
  const lower = issueText.toLowerCase();
  for (const [key, meta] of Object.entries(ISSUE_META)) {
    const keyLower = key.toLowerCase();
    if (lower.includes(keyLower) || keyLower.includes(lower.replace(/\s*\(.*\)$/, "").trim())) {
      return meta;
    }
  }
  if (lower.includes("server error") || lower.includes("5xx")) return ISSUE_META["Server error"];
  if (lower.includes("redirect")) return ISSUE_META["Redirect"];
  if (lower.includes("slow") || lower.includes("ms)")) return ISSUE_META["Page load slow"];
  if (lower.includes("alt")) return ISSUE_META["image(s) missing alt text"];
  if (lower.includes("open graph") || lower.includes("og:")) return ISSUE_META["Missing Open Graph tags"];
  return { label: issueText, severity: "info" as const, description: issueText, fix: "Review this issue and consult SEO best practices." };
}

const SEV_STYLE = {
  critical: "bg-red-900/40 text-red-300 border border-red-700/50",
  warning:  "bg-amber-900/40 text-amber-300 border border-amber-700/50",
  info:     "bg-blue-900/40 text-blue-300 border border-blue-700/50",
};
const SEV_ICON = {
  critical: <AlertCircle className="w-3.5 h-3.5" />,
  warning:  <AlertTriangle className="w-3.5 h-3.5" />,
  info:     <Info className="w-3.5 h-3.5" />,
};

function exportCSV(rows: any[]) {
  const headers = ["URL","Status","Title","Words","H1","Response(ms)","Depth","Score","Critical Issues","Warning Issues","Info Issues"];
  const escape = (v: any) => `"${String(v ?? "").replace(/"/g, "'")}"`;
  const lines = rows.map((r: any) => [
    escape(r.url), r.status_code ?? "", escape(r.title ?? ""),
    r.word_count ?? "", r.h1_count ?? "", r.response_time_ms ?? "", r.page_depth ?? "", r.severity_score ?? "",
    escape((r.issues?.critical || []).join("; ")),
    escape((r.issues?.warning || []).join("; ")),
    escape((r.issues?.info || []).join("; ")),
  ].join(","));
  const blob = new Blob([[headers.join(","), ...lines].join("\n")], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `atlas-seo-audit-${Date.now()}.csv`;
  a.click();
}

export default function TechnicalSEOPage() {
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null);
  const [maxPages, setMaxPages] = useState(500);
  const [filter, setFilter] = useState<"all" | "critical" | "warning" | "info" | "clean">("all");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"score" | "url" | "words" | "speed">("score");
  const [sortAsc, setSortAsc] = useState(false);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<"pages" | "issues">("pages");
  const queryClient = useQueryClient();

  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });

  useEffect(() => {
    if (sites.length && !selectedSiteId) {
      const complete = (sites as any[]).find((s: any) => s.onboarding_status === "complete") || (sites as any[])[0];
      setSelectedSiteId(complete.id);
    }
  }, [sites, selectedSiteId]);

  // Reset UI state when switching sites
  useEffect(() => {
    setSearch("");
    setExpandedRow(null);
    setFilter("all");
  }, [selectedSiteId]);

  const selectedSite = (sites as any[]).find((s: any) => s.id === selectedSiteId);

  const { data: summary } = useQuery({
    queryKey: ["audit-summary", selectedSiteId],
    queryFn: () => getAuditSummary(selectedSiteId!),
    enabled: !!selectedSiteId,
  });

  const { data: allResults = [], isLoading: loadingResults } = useQuery({
    queryKey: ["crawl-results", selectedSiteId],
    queryFn: () => getCrawlResults(selectedSiteId!),
    enabled: !!selectedSiteId,
  });

  const crawlMutation = useMutation({
    mutationFn: () => crawlSite(selectedSiteId!, selectedSite?.url || "", maxPages),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crawl-results", selectedSiteId] });
      queryClient.invalidateQueries({ queryKey: ["audit-summary", selectedSiteId] });
      // Reset stale UI state so results are shown cleanly
      setFilter("all");
      setExpandedRow(null);
      setSearch("");
      setActiveTab("pages");
    },
  });

  const filtered = useMemo(() => {
    let rows = [...(allResults as any[])];
    if (filter === "critical") rows = rows.filter((r: any) => r.issues?.critical?.length > 0);
    else if (filter === "warning") rows = rows.filter((r: any) => r.issues?.warning?.length > 0);
    else if (filter === "info") rows = rows.filter((r: any) => r.issues?.info?.length > 0);
    else if (filter === "clean") rows = rows.filter((r: any) => !r.issues?.critical?.length && !r.issues?.warning?.length && !r.issues?.info?.length);
    if (search) rows = rows.filter((r: any) => r.url.toLowerCase().includes(search.toLowerCase()) || (r.title || "").toLowerCase().includes(search.toLowerCase()));
    rows.sort((a: any, b: any) => {
      if (sortBy === "score") return sortAsc ? a.severity_score - b.severity_score : b.severity_score - a.severity_score;
      if (sortBy === "words") return sortAsc ? (a.word_count || 0) - (b.word_count || 0) : (b.word_count || 0) - (a.word_count || 0);
      if (sortBy === "speed") return sortAsc ? (a.response_time_ms || 0) - (b.response_time_ms || 0) : (b.response_time_ms || 0) - (a.response_time_ms || 0);
      return sortAsc ? a.url.localeCompare(b.url) : b.url.localeCompare(a.url);
    });
    return rows;
  }, [allResults, filter, search, sortBy, sortAsc]);

  function toggleSort(col: typeof sortBy) {
    if (sortBy === col) setSortAsc(!sortAsc);
    else { setSortBy(col); setSortAsc(false); }
  }

  const SortIcon = ({ col }: { col: typeof sortBy }) =>
    sortBy === col ? (sortAsc ? <ChevronUp className="w-3 h-3 inline ml-1" /> : <ChevronDown className="w-3 h-3 inline ml-1" />) : null;

  return (
    <div className="p-6 space-y-6 max-w-screen-xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Technical SEO</h1>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <p className="text-zinc-400 text-sm">Full-site crawl with 20+ SEO checks per page</p>
            {(summary as any)?.last_crawled && (
              <span className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded-full">
                Last crawled: {new Date((summary as any).last_crawled).toLocaleString()}
              </span>
            )}
            {(summary as any)?.total_pages > 0 && (() => {
              const avg = (summary as any).avg_severity_score ?? 0;
              const grade = avg <= 5 ? "A" : avg <= 15 ? "B" : avg <= 30 ? "C" : avg <= 50 ? "D" : "F";
              const color = grade === "A" ? "bg-emerald-900/40 text-emerald-300 border-emerald-700/40"
                : grade === "B" ? "bg-green-900/40 text-green-300 border-green-700/40"
                : grade === "C" ? "bg-amber-900/40 text-amber-300 border-amber-700/40"
                : grade === "D" ? "bg-orange-900/40 text-orange-300 border-orange-700/40"
                : "bg-red-900/40 text-red-300 border-red-700/40";
              return (
                <span className={`text-xs px-2.5 py-0.5 rounded-full flex items-center gap-1.5 border ${color}`}>
                  <Activity className="w-3 h-3" />
                  Health Grade: <strong>{grade}</strong>
                  <span className="opacity-60">({avg}/100 avg score)</span>
                </span>
              );
            })()}
          </div>
        </div>
        {(allResults as any[]).length > 0 && (
          <button onClick={() => exportCSV(allResults as any[])} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm transition-colors border border-zinc-700">
            <Download className="w-4 h-4" /> Export CSV
          </button>
        )}
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-end bg-zinc-900 rounded-xl p-4 border border-zinc-800">
        <div className="flex-1 min-w-[200px]">
          <label className="text-xs text-zinc-400 mb-1 block">Site</label>
          <select value={selectedSiteId || ""} onChange={e => setSelectedSiteId(Number(e.target.value))}
            className="w-full bg-zinc-800 border border-zinc-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            {(sites as any[]).map((s: any) => <option key={s.id} value={s.id}>{s.name || s.url}</option>)}
          </select>
        </div>
        <div className="w-32">
          <label className="text-xs text-zinc-400 mb-1 block">Max Pages</label>
          <input type="number" min={10} max={2000} value={maxPages} onChange={e => setMaxPages(Number(e.target.value))}
            className="w-full bg-zinc-800 border border-zinc-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <button onClick={() => crawlMutation.mutate()} disabled={!selectedSiteId || crawlMutation.isPending}
          className="flex items-center gap-2 px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium text-sm transition-colors">
          <RefreshCw className={`w-4 h-4 ${crawlMutation.isPending ? "animate-spin" : ""}`} />
          {crawlMutation.isPending ? "Crawling…" : "Run Crawl"}
        </button>
      </div>

      {crawlMutation.isPending && (
        <div className="bg-blue-950/40 border border-blue-800/50 rounded-xl p-4 flex items-center gap-3">
          <RefreshCw className="w-5 h-5 text-blue-400 animate-spin flex-shrink-0" />
          <div>
            <p className="text-blue-300 font-medium text-sm">Crawl in progress…</p>
            <p className="text-blue-400/70 text-xs mt-0.5">Analysing up to {maxPages} pages — checking titles, meta, speed, headings, structured data, OG tags, duplicates + more. Large sites may take a few minutes.</p>
          </div>
        </div>
      )}

      {crawlMutation.isError && (
        <div className="bg-red-950/40 border border-red-800/50 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-red-300 font-medium text-sm">Crawl failed</p>
            <p className="text-red-400/70 text-xs mt-0.5">
              {(crawlMutation.error as any)?.response?.data?.detail || (crawlMutation.error as any)?.message || "An unexpected error occurred. Check that the site URL is correct and the server is reachable."}
            </p>
          </div>
        </div>
      )}

      {/* Summary cards */}
      {(summary as any) && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {([
            { label: "Total Pages", value: (summary as any).total_pages, icon: <FileText className="w-4 h-4" />, color: "text-zinc-300", bg: "bg-zinc-800/60 border border-zinc-700/40" },
            { label: "Critical", value: (summary as any).critical_count, icon: <AlertCircle className="w-4 h-4" />, color: "text-red-400", bg: "bg-red-900/20 border border-red-800/40", f: "critical" },
            { label: "Warnings", value: (summary as any).warning_count, icon: <AlertTriangle className="w-4 h-4" />, color: "text-amber-400", bg: "bg-amber-900/20 border border-amber-800/40", f: "warning" },
            { label: "Info", value: (summary as any).info_count, icon: <Info className="w-4 h-4" />, color: "text-blue-400", bg: "bg-blue-900/20 border border-blue-800/40", f: "info" },
            { label: "Clean", value: (summary as any).clean_count ?? 0, icon: <CheckCircle className="w-4 h-4" />, color: "text-emerald-400", bg: "bg-emerald-900/20 border border-emerald-800/40", f: "clean" },
          ] as any[]).map((card: any) => (
            <button key={card.label} onClick={() => card.f && setFilter(filter === card.f ? "all" : card.f)}
              className={`rounded-xl p-4 text-left transition-all ${card.bg} ${card.f && filter === card.f ? "ring-2 ring-white/20" : ""} ${card.f ? "hover:opacity-80 cursor-pointer" : ""}`}>
              <div className={`flex items-center gap-2 ${card.color} mb-2`}>{card.icon}<span className="text-xs font-medium">{card.label}</span></div>
              <div className={`text-2xl font-bold ${card.color}`}>{card.value}</div>
            </button>
          ))}
        </div>
      )}

      {/* Tabs */}
      {(allResults as any[]).length > 0 && (
        <>
          <div className="flex gap-1 bg-zinc-900 rounded-lg p-1 w-fit border border-zinc-800">
            {([["pages", "Pages Table", <FileText className="w-4 h-4" key="f" />], ["issues", "Issues Breakdown", <BarChart2 className="w-4 h-4" key="b" />]] as [string, string, any][]).map(([tab, label, icon]) => (
              <button key={tab} onClick={() => setActiveTab(tab as any)}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === tab ? "bg-zinc-700 text-white" : "text-zinc-400 hover:text-zinc-200"}`}>
                {icon}{label}
              </button>
            ))}
          </div>

          {/* Issues Breakdown */}
          {activeTab === "issues" && (
            <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden">
              <div className="p-4 border-b border-zinc-800">
                <h2 className="text-white font-semibold">Most Common Issues</h2>
                <p className="text-zinc-400 text-xs mt-0.5">Sorted by pages affected — fix the top issues for maximum impact</p>
              </div>
              {!(summary as any)?.top_issues?.length && (
                <div className="py-12 text-center text-zinc-500 text-sm">
                  {!(summary as any) ? "Loading…" : "No issues found — all pages are clean!"}
                </div>
              )}
              <div className="divide-y divide-zinc-800">
                {((summary as any)?.top_issues || []).map((item: any, i: number) => {
                  const meta = getIssueInfo(item.issue);
                  const pct = Math.round((item.pages_affected / ((summary as any).total_pages || 1)) * 100);
                  return (
                    <div key={i} className="p-4 hover:bg-zinc-800/40 transition-colors">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-start gap-3 flex-1 min-w-0">
                          <span className={`mt-0.5 flex-shrink-0 flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${SEV_STYLE[meta.severity]}`}>
                            {SEV_ICON[meta.severity]}{meta.severity}
                          </span>
                          <div className="min-w-0">
                            <p className="text-white text-sm font-medium">{meta.label || item.issue}</p>
                            <p className="text-zinc-400 text-xs mt-0.5 line-clamp-1">{meta.fix}</p>
                          </div>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="text-white font-bold text-sm">{item.pages_affected}</p>
                          <p className="text-zinc-400 text-xs">{pct}% of pages</p>
                        </div>
                      </div>
                      <div className="mt-2 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full transition-all ${meta.severity === "critical" ? "bg-red-500" : meta.severity === "warning" ? "bg-amber-500" : "bg-blue-500"}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Pages Table */}
          {activeTab === "pages" && (
            <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden">
              <div className="p-4 border-b border-zinc-800 flex flex-wrap gap-3 items-center">
                <div className="relative flex-1 min-w-[200px]">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                  <input type="text" placeholder="Search URL or title…" value={search} onChange={e => setSearch(e.target.value)}
                    className="w-full bg-zinc-800 border border-zinc-700 text-white rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <p className="text-zinc-500 text-xs">{filtered.length} of {(allResults as any[]).length} pages</p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-800 text-zinc-400 text-xs">
                      <th className="text-left px-4 py-3 font-medium cursor-pointer hover:text-white select-none" onClick={() => toggleSort("url")}>URL <SortIcon col="url" /></th>
                      <th className="text-center px-3 py-3 font-medium">Status</th>
                      <th className="text-left px-3 py-3 font-medium cursor-pointer hover:text-white select-none" onClick={() => toggleSort("words")}>Words <SortIcon col="words" /></th>
                      <th className="text-center px-3 py-3 font-medium cursor-pointer hover:text-white select-none" onClick={() => toggleSort("speed")}><Clock className="w-3 h-3 inline mr-1" />Speed <SortIcon col="speed" /></th>
                      <th className="text-left px-3 py-3 font-medium">Issues</th>
                      <th className="text-center px-3 py-3 font-medium cursor-pointer hover:text-white select-none" onClick={() => toggleSort("score")}>Score <SortIcon col="score" /></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60">
                    {filtered.slice(0, 500).map((r: any) => {
                      const critCount = r.issues?.critical?.length || 0;
                      const warnCount = r.issues?.warning?.length || 0;
                      const infoCount = r.issues?.info?.length || 0;
                      const isExpanded = expandedRow === r.id;
                      const allIssues = [
                        ...(r.issues?.critical || []).map((t: string) => ({ text: t, sev: "critical" })),
                        ...(r.issues?.warning || []).map((t: string) => ({ text: t, sev: "warning" })),
                        ...(r.issues?.info || []).map((t: string) => ({ text: t, sev: "info" })),
                      ];
                      return (
                        <Fragment key={r.id}>
                          <tr onClick={() => setExpandedRow(isExpanded ? null : r.id)}
                            className="hover:bg-zinc-800/40 cursor-pointer transition-colors group">
                            <td className="px-4 py-3 max-w-[280px]">
                              <div className="truncate text-zinc-200 group-hover:text-white text-xs font-mono">{r.url.replace(/^https?:\/\//, "")}</div>
                              {r.title && <div className="truncate text-zinc-500 text-xs mt-0.5">{r.title}</div>}
                            </td>
                            <td className="px-3 py-3 text-center">
                              <span className={`text-xs font-mono font-semibold ${r.status_code >= 400 ? "text-red-400" : r.status_code >= 300 ? "text-amber-400" : "text-emerald-400"}`}>{r.status_code || "—"}</span>
                            </td>
                            <td className="px-3 py-3 text-zinc-400 text-xs">{r.word_count?.toLocaleString() || "—"}</td>
                            <td className="px-3 py-3 text-center">
                              <span className={`text-xs ${(r.response_time_ms || 0) > 3000 ? "text-red-400" : (r.response_time_ms || 0) > 1500 ? "text-amber-400" : "text-zinc-400"}`}>
                                {r.response_time_ms ? `${r.response_time_ms}ms` : "—"}
                              </span>
                            </td>
                            <td className="px-3 py-3">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                {critCount > 0 && <span className="flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-red-900/40 text-red-300 border border-red-700/40"><AlertCircle className="w-3 h-3" />{critCount}</span>}
                                {warnCount > 0 && <span className="flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-amber-900/40 text-amber-300 border border-amber-700/40"><AlertTriangle className="w-3 h-3" />{warnCount}</span>}
                                {infoCount > 0 && <span className="flex items-center gap-1 text-xs px-1.5 py-0.5 rounded-full bg-blue-900/40 text-blue-300 border border-blue-700/40"><Info className="w-3 h-3" />{infoCount}</span>}
                                {!critCount && !warnCount && !infoCount && <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle className="w-3 h-3" />Clean</span>}
                              </div>
                            </td>
                            <td className="px-3 py-3 text-center">
                              <span className={`text-xs font-bold ${r.severity_score >= 50 ? "text-red-400" : r.severity_score >= 20 ? "text-amber-400" : r.severity_score > 0 ? "text-blue-400" : "text-emerald-400"}`}>{r.severity_score}</span>
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr className="bg-zinc-800/30">
                              <td colSpan={6} className="px-6 py-5">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                  <div className="space-y-3">
                                    <h3 className="text-white font-semibold text-sm">Page Details</h3>
                                    <div className="space-y-1.5 text-xs">
                                      {([["URL", r.url, true], ["Title", r.title || "—", false], ["Meta Desc", r.meta_desc || "—", false], ["Canonical", r.canonical || "—", false], ["Redirect to", r.redirect_url || "—", !!r.redirect_url], ["Word Count", r.word_count ? `${r.word_count} words` : "—", false], ["H1 Count", r.h1_count !== null ? String(r.h1_count) : "—", false], ["Response Time", r.response_time_ms ? `${r.response_time_ms}ms` : "—", false], ["Page Depth", r.page_depth !== null ? `${r.page_depth} clicks from home` : "—", false], ["Indexable", r.indexable ? "Yes" : "No", false]] as [string, string, boolean][]).map(([k, v, link]) => (
                                        <div key={k} className="flex gap-2">
                                          <span className="text-zinc-500 w-28 flex-shrink-0">{k}</span>
                                          {link && v !== "—" ? (
                                            <a href={v} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline truncate flex items-center gap-1">{v}<ExternalLink className="w-3 h-3 flex-shrink-0" /></a>
                                          ) : (
                                            <span className="text-zinc-300 break-all">{v}</span>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                  <div className="space-y-3">
                                    <h3 className="text-white font-semibold text-sm">Issues & Fixes ({allIssues.length})</h3>
                                    {allIssues.length === 0 ? (
                                      <div className="flex items-center gap-2 text-emerald-400 text-sm"><CheckCircle className="w-4 h-4" />No issues — this page is clean!</div>
                                    ) : (
                                      <div className="space-y-2">
                                        {allIssues.map(({ text, sev }: any, i: number) => {
                                          const meta = getIssueInfo(text);
                                          return (
                                            <div key={i} className={`rounded-lg p-3 ${sev === "critical" ? "bg-red-950/40 border border-red-800/40" : sev === "warning" ? "bg-amber-950/40 border border-amber-800/40" : "bg-blue-950/40 border border-blue-800/40"}`}>
                                              <div className="flex items-center gap-2 mb-1">{SEV_ICON[sev as keyof typeof SEV_ICON]}<span className={`text-xs font-semibold ${sev === "critical" ? "text-red-300" : sev === "warning" ? "text-amber-300" : "text-blue-300"}`}>{meta.label}</span></div>
                                              <p className="text-zinc-300 text-xs mb-1">{meta.description}</p>
                                              <p className="text-xs font-medium text-zinc-100">✦ {meta.fix}</p>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>

                {filtered.length === 0 && !loadingResults && !crawlMutation.isPending && (
                  <div className="text-center py-16 text-zinc-500">
                    <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
                    <p>{(allResults as any[]).length === 0 ? "No crawl data yet — run a crawl to get started." : "No pages match this filter."}</p>
                  </div>
                )}
                {filtered.length > 500 && (
                  <div className="px-4 py-3 bg-zinc-800/40 border-t border-zinc-800 text-zinc-500 text-xs text-center">
                    Showing first 500 of {filtered.length} pages. Export CSV to see all results.
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {!(allResults as any[]).length && !crawlMutation.isPending && !loadingResults && (
        <div className="text-center py-20 text-zinc-500">
          <Zap className="w-12 h-12 mx-auto mb-4 opacity-20" />
          <p className="text-lg font-medium text-zinc-400 mb-2">No crawl data yet</p>
          <p className="text-sm">Select a site and click <strong className="text-white">Run Crawl</strong> to analyse up to {maxPages} pages.</p>
        </div>
      )}
    </div>
  );
}
