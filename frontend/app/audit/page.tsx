"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PageResult {
  url: string;
  status_code: number;
  content_type: string;
  title: string;
  title_length: number;
  meta_description: string;
  meta_description_length: number;
  h1: string;
  h1_count: number;
  h2_count: number;
  word_count: number;
  internal_links: number;
  external_links: number;
  images_total: number;
  images_missing_alt: number;
  response_time_ms: number;
  is_indexable: boolean;
  canonical: string;
  redirect_url: string;
  issues: string[];
}

interface AuditState {
  audit_id: string;
  start_url: string;
  status: "running" | "complete" | "stopped" | "error";
  crawled: number;
  queued: number;
  total_issues: number;
  pages: PageResult[];
  error?: string;
}

type FilterTab = "all" | "ok" | "redirect" | "error" | "issues";

// ─── Helpers ─────────────────────────────────────────────────────────────────

// In production NEXT_PUBLIC_API_URL points to Railway; locally the proxy handles it
const API = `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/audit`;

function statusColor(code: number) {
  if (code === 0) return "text-gray-400";
  if (code < 300) return "text-green-400";
  if (code < 400) return "text-yellow-400";
  return "text-red-400";
}

function statusBg(code: number) {
  if (code === 0) return "bg-gray-800 text-gray-400";
  if (code < 300) return "bg-green-900/40 text-green-300";
  if (code < 400) return "bg-yellow-900/40 text-yellow-300";
  return "bg-red-900/40 text-red-300";
}

function issueLabel(issue: string) {
  const map: Record<string, string> = {
    missing_title: "No Title",
    title_too_short: "Short Title",
    title_too_long: "Long Title",
    missing_meta_description: "No Meta Desc",
    meta_description_too_long: "Long Meta Desc",
    missing_h1: "No H1",
    multiple_h1: "Multiple H1",
    thin_content: "Thin Content",
    noindex: "Noindex",
    timeout: "Timeout",
    crawl_error: "Error",
  };
  if (issue.startsWith("status_")) return `HTTP ${issue.split("_")[1]}`;
  if (issue.startsWith("images_missing_alt_")) return `${issue.split("_").pop()} Imgs No Alt`;
  return map[issue] || issue;
}

function truncate(s: string, n: number) {
  return s && s.length > n ? s.slice(0, n) + "…" : s;
}

function exportCsv(pages: PageResult[]) {
  const headers = [
    "URL","Status","Title","Title Length","Meta Description","Meta Desc Length",
    "H1","H1 Count","H2 Count","Word Count","Internal Links","External Links",
    "Images Total","Images Missing Alt","Response Time (ms)","Indexable","Canonical","Issues"
  ];
  const rows = pages.map(p => [
    p.url, p.status_code, p.title, p.title_length, p.meta_description,
    p.meta_description_length, p.h1, p.h1_count, p.h2_count, p.word_count,
    p.internal_links, p.external_links, p.images_total, p.images_missing_alt,
    p.response_time_ms, p.is_indexable ? "Yes" : "No", p.canonical,
    p.issues.join("; ")
  ]);
  const csv = [headers, ...rows]
    .map(r => r.map(v => `"${String(v ?? "").replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `atlas-audit-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function QuickAuditPage() {
  const [url, setUrl] = useState("");
  const [maxPages, setMaxPages] = useState(200);
  const [audit, setAudit] = useState<AuditState | null>(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<FilterTab>("all");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startAudit = useCallback(async () => {
    if (!url.trim()) return;
    stopPolling();
    setLoading(true);
    setAudit(null);
    setFilter("all");
    setExpandedRow(null);

    try {
      const res = await fetch(`${API}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), max_pages: maxPages }),
      });
      const { audit_id } = await res.json();

      // Poll every 2 s
      pollRef.current = setInterval(async () => {
        try {
          const r = await fetch(`${API}/${audit_id}`);
          const data: AuditState = await r.json();
          setAudit(data);
          if (data.status !== "running") {
            stopPolling();
            setLoading(false);
          }
        } catch {
          stopPolling();
          setLoading(false);
        }
      }, 2000);
    } catch (e) {
      setLoading(false);
    }
  }, [url, maxPages, stopPolling]);

  const stopAudit = useCallback(async () => {
    if (!audit) return;
    stopPolling();
    setLoading(false);
    await fetch(`${API}/${audit.audit_id}/stop`, { method: "POST" });
    setAudit(prev => prev ? { ...prev, status: "stopped" } : null);
  }, [audit, stopPolling]);

  // Filtered pages
  const filtered = (audit?.pages ?? []).filter(p => {
    if (filter === "ok") return p.status_code >= 200 && p.status_code < 300 && p.issues.length === 0;
    if (filter === "redirect") return p.status_code >= 300 && p.status_code < 400;
    if (filter === "error") return p.status_code >= 400 || p.status_code === 0;
    if (filter === "issues") return p.issues.length > 0;
    return true;
  });

  const isRunning = loading || audit?.status === "running";
  const progress = audit
    ? Math.round((audit.crawled / Math.max(audit.crawled + audit.queued, 1)) * 100)
    : 0;

  const okCount = (audit?.pages ?? []).filter(p => p.status_code >= 200 && p.status_code < 300).length;
  const redirectCount = (audit?.pages ?? []).filter(p => p.status_code >= 300 && p.status_code < 400).length;
  const errorCount = (audit?.pages ?? []).filter(p => p.status_code >= 400 || p.status_code === 0).length;
  const issueCount = (audit?.pages ?? []).filter(p => p.issues.length > 0).length;
  const avgTime = audit?.pages?.length
    ? Math.round(audit.pages.reduce((s, p) => s + (p.response_time_ms || 0), 0) / audit.pages.length)
    : 0;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">

      {/* ── Top bar ── */}
      <header className="border-b border-gray-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-white tracking-tight">⚡ Atlas</span>
          <span className="text-gray-500 text-sm">SEO Audit Tool</span>
        </div>
        <Link
          href="/login"
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          Dashboard →
        </Link>
      </header>

      {/* ── URL bar ── */}
      <div className="border-b border-gray-800 bg-gray-900 px-6 py-4">
        <div className="max-w-5xl mx-auto flex gap-3 items-center">
          <div className="flex-1 flex items-center bg-gray-800 border border-gray-700 rounded-lg overflow-hidden focus-within:border-blue-500 transition-colors">
            <span className="pl-4 text-gray-500 text-sm select-none">🔍</span>
            <input
              type="text"
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !isRunning && startAudit()}
              placeholder="Enter website URL — e.g. https://example.com"
              className="flex-1 bg-transparent px-3 py-3 text-white placeholder-gray-500 text-sm outline-none"
              disabled={isRunning}
            />
          </div>

          <div className="flex items-center gap-2">
            <select
              value={maxPages}
              onChange={e => setMaxPages(Number(e.target.value))}
              disabled={isRunning}
              className="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-3 outline-none cursor-pointer"
            >
              <option value={50}>50 pages</option>
              <option value={100}>100 pages</option>
              <option value={200}>200 pages</option>
              <option value={500}>500 pages</option>
            </select>

            {isRunning ? (
              <button
                onClick={stopAudit}
                className="px-5 py-3 bg-red-600 hover:bg-red-500 text-white text-sm font-semibold rounded-lg transition-colors"
              >
                ⏹ Stop
              </button>
            ) : (
              <button
                onClick={startAudit}
                disabled={!url.trim()}
                className="px-5 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-semibold rounded-lg transition-colors"
              >
                ▶ Start
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Stats bar ── */}
      {audit && (
        <div className="border-b border-gray-800 bg-gray-900/50 px-6 py-3">
          <div className="max-w-5xl mx-auto flex items-center gap-6 text-sm flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-gray-500">URLs crawled:</span>
              <span className="text-white font-semibold">{audit.crawled}</span>
              {isRunning && audit.queued > 0 && (
                <span className="text-gray-500">({audit.queued} queued)</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-400" />
              <span className="text-green-400 font-semibold">{okCount}</span>
              <span className="text-gray-500">OK</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-yellow-400" />
              <span className="text-yellow-400 font-semibold">{redirectCount}</span>
              <span className="text-gray-500">Redirects</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-400" />
              <span className="text-red-400 font-semibold">{errorCount}</span>
              <span className="text-gray-500">Errors</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-orange-400" />
              <span className="text-orange-400 font-semibold">{issueCount}</span>
              <span className="text-gray-500">Issues</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Avg response:</span>
              <span className="text-white font-semibold">{avgTime}ms</span>
            </div>
            <div className="ml-auto flex items-center gap-3">
              {audit.status === "complete" && (
                <span className="text-green-400 text-xs font-semibold px-2 py-1 bg-green-900/30 rounded">
                  ✓ Complete
                </span>
              )}
              {audit.status === "stopped" && (
                <span className="text-yellow-400 text-xs font-semibold px-2 py-1 bg-yellow-900/30 rounded">
                  ⏹ Stopped
                </span>
              )}
              {isRunning && (
                <span className="text-blue-400 text-xs font-semibold px-2 py-1 bg-blue-900/30 rounded animate-pulse">
                  ● Crawling…
                </span>
              )}
              {audit.pages.length > 0 && (
                <button
                  onClick={() => exportCsv(audit.pages)}
                  className="text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded px-3 py-1 transition-colors"
                >
                  ↓ Export CSV
                </button>
              )}
            </div>
          </div>

          {/* Progress bar */}
          {isRunning && (
            <div className="max-w-5xl mx-auto mt-2">
              <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all duration-500 rounded-full"
                  style={{ width: `${Math.max(progress, 2)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Filter tabs ── */}
      {audit && audit.pages.length > 0 && (
        <div className="border-b border-gray-800 px-6">
          <div className="max-w-5xl mx-auto flex gap-0">
            {(["all", "ok", "redirect", "error", "issues"] as FilterTab[]).map(tab => (
              <button
                key={tab}
                onClick={() => setFilter(tab)}
                className={`px-4 py-2 text-sm capitalize border-b-2 transition-colors ${
                  filter === tab
                    ? "border-blue-500 text-blue-400"
                    : "border-transparent text-gray-500 hover:text-gray-300"
                }`}
              >
                {tab === "all" && `All (${audit.pages.length})`}
                {tab === "ok" && `OK (${okCount})`}
                {tab === "redirect" && `Redirect (${redirectCount})`}
                {tab === "error" && `Error (${errorCount})`}
                {tab === "issues" && `Issues (${issueCount})`}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Table ── */}
      <div className="flex-1 overflow-auto px-6 py-4">
        <div className="max-w-5xl mx-auto">

          {/* Empty / initial state */}
          {!audit && !loading && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="text-6xl mb-6">🔭</div>
              <h2 className="text-2xl font-bold text-white mb-3">Site Audit</h2>
              <p className="text-gray-400 max-w-md mb-2">
                Enter any website URL above and click <strong>Start</strong>.
              </p>
              <p className="text-gray-500 text-sm max-w-md">
                Atlas will crawl the site and show you every page with its SEO data —
                status codes, titles, meta descriptions, H1s, word counts, and issues —
                just like Screaming Frog, but built into Atlas.
              </p>
              <div className="mt-8 grid grid-cols-3 gap-4 text-sm text-gray-500">
                <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
                  <div className="text-2xl mb-2">🕷</div>
                  <div className="text-gray-300 font-medium mb-1">Full Crawl</div>
                  <div>Follows all internal links automatically</div>
                </div>
                <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
                  <div className="text-2xl mb-2">⚡</div>
                  <div className="text-gray-300 font-medium mb-1">No Setup</div>
                  <div>No login required. No API keys. Type and go.</div>
                </div>
                <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
                  <div className="text-2xl mb-2">📊</div>
                  <div className="text-gray-300 font-medium mb-1">Export CSV</div>
                  <div>Download results as CSV for your reports</div>
                </div>
              </div>
            </div>
          )}

          {/* Results table */}
          {audit && filtered.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-gray-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-900 text-gray-400 text-xs uppercase tracking-wide">
                    <th className="text-left px-3 py-2 w-8">#</th>
                    <th className="text-left px-3 py-2">URL</th>
                    <th className="text-center px-3 py-2 w-16">Status</th>
                    <th className="text-left px-3 py-2 max-w-[180px]">Title</th>
                    <th className="text-left px-3 py-2 max-w-[160px]">H1</th>
                    <th className="text-center px-3 py-2 w-16">Words</th>
                    <th className="text-center px-3 py-2 w-16">Links</th>
                    <th className="text-center px-3 py-2 w-16">Time</th>
                    <th className="text-left px-3 py-2">Issues</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((page, idx) => (
                    <>
                      <tr
                        key={page.url}
                        onClick={() => setExpandedRow(expandedRow === page.url ? null : page.url)}
                        className="border-t border-gray-800 hover:bg-gray-900/60 cursor-pointer transition-colors"
                      >
                        <td className="px-3 py-2 text-gray-600 tabular-nums">{idx + 1}</td>
                        <td className="px-3 py-2 max-w-[240px]">
                          <div className="truncate text-blue-400 hover:text-blue-300 text-xs font-mono">
                            {page.url.replace(/^https?:\/\/[^/]+/, "") || "/"}
                          </div>
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className={`text-xs font-bold px-2 py-0.5 rounded ${statusBg(page.status_code)}`}>
                            {page.status_code || "—"}
                          </span>
                        </td>
                        <td className="px-3 py-2 max-w-[180px]">
                          <div className={`truncate text-xs ${page.title ? "text-gray-200" : "text-gray-600 italic"}`}>
                            {page.title ? truncate(page.title, 50) : "—"}
                          </div>
                          {page.title_length > 0 && (
                            <div className={`text-xs ${page.title_length > 60 ? "text-red-400" : page.title_length < 10 ? "text-yellow-400" : "text-gray-500"}`}>
                              {page.title_length} chars
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-2 max-w-[160px]">
                          <div className={`truncate text-xs ${page.h1 ? "text-gray-200" : "text-gray-600 italic"}`}>
                            {page.h1 ? truncate(page.h1, 40) : "—"}
                          </div>
                          {page.h1_count > 1 && (
                            <div className="text-xs text-orange-400">{page.h1_count} H1s</div>
                          )}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className={`text-xs ${page.word_count < 300 && page.word_count > 0 ? "text-yellow-400" : "text-gray-400"}`}>
                            {page.word_count > 0 ? page.word_count.toLocaleString() : "—"}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-center text-gray-400 text-xs">
                          {page.internal_links > 0 ? (
                            <span title="Internal links">↗{page.internal_links}</span>
                          ) : "—"}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <span className={`text-xs ${page.response_time_ms > 2000 ? "text-red-400" : page.response_time_ms > 800 ? "text-yellow-400" : "text-gray-400"}`}>
                            {page.response_time_ms > 0 ? `${page.response_time_ms}ms` : "—"}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex flex-wrap gap-1">
                            {page.issues.slice(0, 3).map(issue => (
                              <span
                                key={issue}
                                className="text-xs px-1.5 py-0.5 rounded bg-red-900/40 text-red-300 border border-red-900/50"
                              >
                                {issueLabel(issue)}
                              </span>
                            ))}
                            {page.issues.length > 3 && (
                              <span className="text-xs text-gray-500">+{page.issues.length - 3}</span>
                            )}
                          </div>
                        </td>
                      </tr>

                      {/* Expanded detail row */}
                      {expandedRow === page.url && (
                        <tr key={`${page.url}__detail`} className="bg-gray-900/80">
                          <td colSpan={9} className="px-4 py-4">
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                              <div>
                                <div className="text-gray-500 text-xs mb-1">Full URL</div>
                                <a href={page.url} target="_blank" rel="noreferrer"
                                  className="text-blue-400 hover:underline break-all text-xs">
                                  {page.url}
                                </a>
                              </div>
                              <div>
                                <div className="text-gray-500 text-xs mb-1">Meta Description</div>
                                <div className="text-gray-300 text-xs">
                                  {page.meta_description || <span className="text-gray-600 italic">Missing</span>}
                                </div>
                                {page.meta_description_length > 0 && (
                                  <div className={`text-xs mt-1 ${page.meta_description_length > 160 ? "text-red-400" : "text-gray-500"}`}>
                                    {page.meta_description_length} chars
                                  </div>
                                )}
                              </div>
                              <div>
                                <div className="text-gray-500 text-xs mb-1">Canonical</div>
                                <div className="text-gray-300 text-xs break-all">
                                  {page.canonical || <span className="text-gray-600 italic">Not set</span>}
                                </div>
                              </div>
                              <div>
                                <div className="text-gray-500 text-xs mb-1">Images</div>
                                <div className="text-gray-300 text-xs">
                                  {page.images_total} total,{" "}
                                  <span className={page.images_missing_alt > 0 ? "text-orange-400" : "text-green-400"}>
                                    {page.images_missing_alt} missing alt
                                  </span>
                                </div>
                              </div>
                              <div>
                                <div className="text-gray-500 text-xs mb-1">H-Tags</div>
                                <div className="text-gray-300 text-xs">
                                  H1: {page.h1_count} &nbsp; H2: {page.h2_count}
                                </div>
                              </div>
                              <div>
                                <div className="text-gray-500 text-xs mb-1">Links</div>
                                <div className="text-gray-300 text-xs">
                                  {page.internal_links} internal, {page.external_links} external
                                </div>
                              </div>
                              <div>
                                <div className="text-gray-500 text-xs mb-1">Indexable</div>
                                <div className={`text-xs ${page.is_indexable ? "text-green-400" : "text-red-400"}`}>
                                  {page.is_indexable ? "✓ Yes" : "✗ No (noindex)"}
                                </div>
                              </div>
                              {page.redirect_url && (
                                <div>
                                  <div className="text-gray-500 text-xs mb-1">Redirects to</div>
                                  <div className="text-yellow-300 text-xs break-all">{page.redirect_url}</div>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* No results for current filter */}
          {audit && filtered.length === 0 && audit.pages.length > 0 && (
            <div className="text-center py-12 text-gray-500">
              No pages match the &ldquo;{filter}&rdquo; filter.
            </div>
          )}
        </div>
      </div>

      {/* ── Footer ── */}
      <footer className="border-t border-gray-800 px-6 py-2 text-center text-xs text-gray-600">
        Atlas SEO Audit Tool · Click any row to expand details · Export to CSV for full report
      </footer>
    </div>
  );
}
