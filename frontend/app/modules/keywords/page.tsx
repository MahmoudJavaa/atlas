"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getSites, autoResearchKeywords, classifyKeywords, getKeywords, deleteKeywords, refreshKeywordVolumes,
} from "@/lib/api";
import {
  Zap, Search, Filter, LayoutGrid, Table2, Loader2, AlertCircle,
  ChevronDown, Plus, X, CheckCircle2, Tag, Download, Trash2,
  Globe, TrendingUp,
} from "lucide-react";

// ── Constants ─────────────────────────────────────────────────────────────────

const INTENT_STYLES: Record<string, string> = {
  informational: "bg-blue-900/40 text-blue-300 border-blue-700/50",
  commercial:    "bg-purple-900/40 text-purple-300 border-purple-700/50",
  transactional: "bg-green-900/40 text-green-300 border-green-700/50",
  navigational:  "bg-gray-700 text-gray-400 border-gray-600",
};

const INTENT_LABELS: Record<string, string> = {
  informational: "Info",
  commercial:    "Commercial",
  transactional: "Buy",
  navigational:  "Nav",
};

const LANG_OPTIONS = [
  { value: "both", label: "EN + AR" },
  { value: "en",   label: "English" },
  { value: "ar",   label: "العربية" },
] as const;

// ── Helpers ───────────────────────────────────────────────────────────────────

function isArabic(text: string) {
  return /[؀-ۿ]/.test(text);
}

function fmtVolume(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toLocaleString();
}

/**
 * Keyword Difficulty bar:
 *  0–30 → green (easy)
 *  31–60 → yellow (medium)
 *  61–100 → red (hard)
 */
function KdBar({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-gray-600 text-xs">—</span>;
  const pct = Math.min(100, Math.max(0, value));
  const color =
    pct <= 30 ? "bg-green-500" : pct <= 60 ? "bg-yellow-500" : "bg-red-500";
  const label =
    pct <= 30 ? "Easy" : pct <= 60 ? "Medium" : "Hard";
  return (
    <div className="flex items-center gap-2 justify-end">
      <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400 w-10 text-right">{pct} <span className="text-gray-600">/ {label}</span></span>
    </div>
  );
}

function exportCsv(keywords: any[]) {
  const header = "Keyword,Intent,Cluster,Language,Volume,Difficulty,Position,Clicks";
  const rows = keywords.map((k) =>
    [
      `"${(k.keyword || "").replace(/"/g, '""')}"`,
      k.intent || "",
      `"${(k.cluster || "").replace(/"/g, '""')}"`,
      k.language || "en",
      k.volume ?? "",
      k.difficulty ?? "",
      k.position ?? "",
      k.clicks ?? "",
    ].join(",")
  );
  const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "keywords.csv";
  a.click();
  URL.revokeObjectURL(url);
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function KeywordsPage() {
  const qc = useQueryClient();

  // ── Site selection ──────────────────────────────────────────────────────────
  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });
  const [siteId, setSiteId] = useState<number | null>(null);

  useEffect(() => {
    const list = sites as any[];
    if (list.length > 0 && !siteId) {
      const complete = list.find((s) => s.onboarding_status === "complete");
      setSiteId((complete ?? list[0]).id);
    }
  }, [sites, siteId]);

  // ── Research language ───────────────────────────────────────────────────────
  const [researchLang, setResearchLang] = useState<"both" | "en" | "ar">("both");

  // ── Filters / view ──────────────────────────────────────────────────────────
  const [view, setView]                 = useState<"cluster" | "table">("cluster");
  const [filterIntent, setFilterIntent] = useState("");
  const [filterCluster, setFilterCluster] = useState("");
  const [filterLang, setFilterLang]     = useState("");
  const [search, setSearch]             = useState("");
  const [showSeedPanel, setShowSeedPanel] = useState(false);
  const [showConfirmClear, setShowConfirmClear] = useState(false);
  const [seedInput, setSeedInput]       = useState("");

  // Reset filters when site changes
  useEffect(() => {
    setFilterIntent("");
    setFilterCluster("");
    setFilterLang("");
    setSearch("");
    setShowSeedPanel(false);
    setShowConfirmClear(false);
  }, [siteId]);

  // ── Data ────────────────────────────────────────────────────────────────────
  const { data: keywords = [], isLoading: kLoading } = useQuery({
    queryKey: ["keywords", siteId],
    queryFn:  () => getKeywords(siteId!),
    enabled:  !!siteId,
    staleTime: 5 * 60 * 1000,
  });

  // ── Mutations ───────────────────────────────────────────────────────────────
  const researchMutation = useMutation({
    mutationFn: () => autoResearchKeywords(siteId!, researchLang),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ["keywords", siteId] }),
  });

  const classifyMutation = useMutation({
    mutationFn: () =>
      classifyKeywords({
        site_id: siteId!,
        seed_keywords: seedInput.split("\n").map((k) => k.trim()).filter(Boolean),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["keywords", siteId] });
      setSeedInput("");
      setShowSeedPanel(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteKeywords(siteId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["keywords", siteId] });
      setShowConfirmClear(false);
    },
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshKeywordVolumes(siteId!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keywords", siteId] }),
  });

  // ── Derived data ─────────────────────────────────────────────────────────────
  const kws = keywords as any[];

  const intentCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const kw of kws) {
      const i = kw.intent || "unknown";
      counts[i] = (counts[i] || 0) + 1;
    }
    return counts;
  }, [kws]);

  const allClusters = useMemo(
    () => Array.from(new Set(kws.map((k: any) => k.cluster).filter(Boolean))).sort() as string[],
    [kws]
  );

  const hasArabic = useMemo(() => kws.some((k: any) => k.language === "ar"), [kws]);
  const hasEnglish = useMemo(() => kws.some((k: any) => k.language !== "ar"), [kws]);

  const filtered = useMemo(() => {
    let list = kws;
    if (filterIntent)  list = list.filter((k: any) => k.intent === filterIntent);
    if (filterCluster) list = list.filter((k: any) => k.cluster === filterCluster);
    if (filterLang)    list = list.filter((k: any) => (k.language || "en") === filterLang);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((k: any) => k.keyword?.toLowerCase().includes(q));
    }
    return list;
  }, [kws, filterIntent, filterCluster, filterLang, search]);

  const clusters = useMemo(() => {
    return filtered.reduce((acc: Record<string, any[]>, kw: any) => {
      const c = kw.cluster || "Unclustered";
      (acc[c] = acc[c] || []).push(kw);
      return acc;
    }, {});
  }, [filtered]);

  const siteList = sites as any[];
  const researchResult = researchMutation.data as any;

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Keyword Intelligence</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            {kws.length > 0
              ? `${kws.length.toLocaleString()} keywords tracked`
              : "Research real keywords with search volume and difficulty"}
          </p>
        </div>

        {/* Site selector */}
        {siteList.length > 1 && (
          <div className="relative">
            <select
              className="appearance-none bg-gray-800/60 border border-gray-700 text-gray-200 rounded-lg pl-3 pr-8 py-2 text-sm focus:outline-none focus:border-atlas-500 cursor-pointer"
              value={siteId ?? ""}
              onChange={(e) => setSiteId(Number(e.target.value))}
            >
              {siteList.map((s: any) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
          </div>
        )}
      </div>

      {!siteId && (
        <div className="card text-center py-12">
          <p className="text-gray-400">Select a site to view keyword data.</p>
        </div>
      )}

      {siteId && (
        <>
          {/* Action bar */}
          <div className="card flex flex-wrap gap-3 items-center">
            {/* Language picker */}
            <div className="flex gap-1 bg-gray-900 rounded-lg p-1 border border-gray-700">
              {LANG_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setResearchLang(opt.value)}
                  className={`px-3 py-1 rounded-md text-xs transition-colors ${
                    researchLang === opt.value
                      ? "bg-atlas-600 text-white"
                      : "text-gray-400 hover:text-white"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Auto-research */}
            <button
              className="btn-primary flex items-center gap-2 disabled:opacity-50"
              disabled={researchMutation.isPending || !siteId}
              onClick={() => researchMutation.mutate()}
            >
              {researchMutation.isPending ? (
                <><Loader2 size={15} className="animate-spin" /> Researching…</>
              ) : (
                <><Zap size={15} /> Auto-Research Keywords</>
              )}
            </button>

            {/* Manual seed panel */}
            <button
              className="btn-secondary flex items-center gap-2 text-sm"
              onClick={() => setShowSeedPanel((v) => !v)}
            >
              <Plus size={14} /> Add keywords
            </button>

            {/* Spacer */}
            <div className="flex-1" />

            {/* CSV Export */}
            {kws.length > 0 && (
              <button
                className="btn-secondary flex items-center gap-2 text-sm"
                onClick={() => exportCsv(filtered)}
                title="Export filtered keywords as CSV"
              >
                <Download size={14} /> Export CSV
              </button>
            )}

            {/* Refresh Volumes */}
            {kws.length > 0 && (
              <button
                className="btn-secondary flex items-center gap-2 text-sm disabled:opacity-50"
                disabled={refreshMutation.isPending}
                onClick={() => refreshMutation.mutate()}
                title="Fetch real search volume + difficulty for all keywords via DataForSEO"
              >
                {refreshMutation.isPending ? (
                  <><Loader2 size={14} className="animate-spin" /> Refreshing…</>
                ) : (
                  <><TrendingUp size={14} /> Refresh Volumes</>
                )}
              </button>
            )}
            {refreshMutation.isSuccess && (
              <span className="text-green-400 text-xs">
                ✓ {(refreshMutation.data as any)?.updated ?? 0} keywords enriched
              </span>
            )}
            {refreshMutation.isError && (
              <span className="text-red-400 text-xs">
                Volume refresh failed — check DataForSEO credentials
              </span>
            )}

            {/* Clear all */}
            {kws.length > 0 && !showConfirmClear && (
              <button
                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-red-400 transition-colors px-2 py-1"
                onClick={() => setShowConfirmClear(true)}
              >
                <Trash2 size={13} /> Clear all
              </button>
            )}
            {showConfirmClear && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-red-400 text-xs">Delete all {kws.length} keywords?</span>
                <button
                  className="text-xs bg-red-600 hover:bg-red-500 text-white px-2.5 py-1 rounded-md disabled:opacity-50"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate()}
                >
                  {deleteMutation.isPending ? <Loader2 size={12} className="animate-spin inline" /> : "Yes, delete"}
                </button>
                <button
                  className="text-xs text-gray-400 hover:text-white px-2 py-1"
                  onClick={() => setShowConfirmClear(false)}
                >
                  Cancel
                </button>
              </div>
            )}

            {/* Status messages */}
            {researchMutation.isSuccess && researchResult && (
              <div className="flex items-center gap-1.5 text-green-400 text-sm">
                <CheckCircle2 size={14} />
                {researchResult.new_keywords_added ?? 0} new keywords added
                {researchResult.used_dataforseo && (
                  <span className="text-xs text-green-600 ml-1">(real data)</span>
                )}
              </div>
            )}
            {researchMutation.isError && (
              <div className="flex items-center gap-1.5 text-red-400 text-sm">
                <AlertCircle size={14} />
                {(researchMutation.error as any)?.response?.data?.detail || "Research failed — run a crawl first"}
              </div>
            )}
          </div>

          {/* Seed keyword panel */}
          {showSeedPanel && (
            <div className="card space-y-3 border border-atlas-500/20">
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-white text-sm">Add seed keywords</h3>
                <button onClick={() => setShowSeedPanel(false)} className="text-gray-500 hover:text-gray-300">
                  <X size={14} />
                </button>
              </div>
              <p className="text-xs text-gray-500">
                One keyword per line. English and Arabic keywords are both supported.
                Real search volume + difficulty will be fetched automatically.
              </p>
              <textarea
                className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full h-28 resize-none focus:outline-none focus:border-atlas-500"
                placeholder={"locksmith london\nemergency locksmith\nفني قفل الرياض"}
                value={seedInput}
                onChange={(e) => setSeedInput(e.target.value)}
                dir="auto"
              />
              <button
                className="btn-primary text-sm disabled:opacity-50"
                disabled={!seedInput.trim() || classifyMutation.isPending}
                onClick={() => classifyMutation.mutate()}
              >
                {classifyMutation.isPending ? (
                  <><Loader2 size={14} className="animate-spin inline mr-1.5" />Classifying…</>
                ) : "Classify & Save"}
              </button>
              {classifyMutation.isError && (
                <p className="text-red-400 text-xs">Classification failed. Try again.</p>
              )}
            </div>
          )}

          {/* Stats bar */}
          {kws.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {(["informational", "commercial", "transactional", "navigational"] as const).map((intent) => (
                <button
                  key={intent}
                  onClick={() => setFilterIntent(filterIntent === intent ? "" : intent)}
                  className={`card text-center py-3 transition-colors border ${
                    filterIntent === intent
                      ? "border-atlas-500/50 bg-atlas-500/10"
                      : "border-gray-800 hover:border-gray-700"
                  }`}
                >
                  <p className="text-xl font-bold text-white">{intentCounts[intent] ?? 0}</p>
                  <p className="text-xs text-gray-400 mt-0.5 capitalize">{intent}</p>
                </button>
              ))}
            </div>
          )}

          {/* Toolbar */}
          {kws.length > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              {/* Search */}
              <div className="relative flex-1 min-w-48">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-atlas-500"
                  placeholder="Search keywords…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  dir="auto"
                />
                {search && (
                  <button onClick={() => setSearch("")} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                    <X size={13} />
                  </button>
                )}
              </div>

              {/* Cluster filter */}
              {allClusters.length > 0 && (
                <div className="relative">
                  <select
                    className="appearance-none bg-gray-800 border border-gray-700 text-gray-300 rounded-lg pl-3 pr-8 py-2 text-sm focus:outline-none focus:border-atlas-500"
                    value={filterCluster}
                    onChange={(e) => setFilterCluster(e.target.value)}
                  >
                    <option value="">All clusters</option>
                    {allClusters.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                </div>
              )}

              {/* Language filter (only show if both EN + AR present) */}
              {hasArabic && hasEnglish && (
                <div className="flex gap-1 bg-gray-800 rounded-lg p-1 border border-gray-700">
                  {[
                    { v: "", label: "All" },
                    { v: "en", label: "EN" },
                    { v: "ar", label: "AR" },
                  ].map((opt) => (
                    <button
                      key={opt.v}
                      onClick={() => setFilterLang(filterLang === opt.v ? "" : opt.v)}
                      className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                        filterLang === opt.v
                          ? "bg-gray-700 text-white"
                          : "text-gray-400 hover:text-white"
                      }`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}

              {/* View toggle */}
              <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
                <button
                  onClick={() => setView("cluster")}
                  className={`px-3 py-1 rounded-md text-sm flex items-center gap-1.5 transition-colors ${
                    view === "cluster" ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
                  }`}
                >
                  <LayoutGrid size={13} /> Clusters
                </button>
                <button
                  onClick={() => setView("table")}
                  className={`px-3 py-1 rounded-md text-sm flex items-center gap-1.5 transition-colors ${
                    view === "table" ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"
                  }`}
                >
                  <Table2 size={13} /> Table
                </button>
              </div>

              {/* Clear filters */}
              {(filterIntent || filterCluster || filterLang || search) && (
                <button
                  onClick={() => { setFilterIntent(""); setFilterCluster(""); setFilterLang(""); setSearch(""); }}
                  className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white bg-gray-800 px-2.5 py-1.5 rounded-lg border border-gray-700"
                >
                  <X size={12} /> Clear filters
                </button>
              )}

              <span className="text-gray-500 text-sm">{filtered.length.toLocaleString()} shown</span>
            </div>
          )}

          {/* Loading */}
          {kLoading && (
            <div className="card flex items-center justify-center py-16 gap-3 text-gray-400">
              <Loader2 size={20} className="animate-spin" />
              Loading keywords…
            </div>
          )}

          {/* Empty state */}
          {!kLoading && kws.length === 0 && (
            <div className="card text-center py-16">
              <TrendingUp size={36} className="text-gray-700 mx-auto mb-3" />
              <p className="text-white font-semibold mb-2">No keywords yet</p>
              <p className="text-gray-400 text-sm mb-2 max-w-md mx-auto">
                Click <strong className="text-atlas-300">Auto-Research Keywords</strong> to discover
                real keywords with search volume and difficulty for your site.
              </p>
              <p className="text-gray-400 text-sm mb-4 max-w-md mx-auto">
                Select <strong className="text-atlas-300">EN + AR</strong> to research both English
                and Arabic keywords simultaneously.
              </p>
              <p className="text-gray-600 text-xs">
                Make sure you've run a site crawl first (Technical SEO tab).
              </p>
            </div>
          )}

          {/* ── Cluster view ────────────────────────────────────────────────── */}
          {!kLoading && kws.length > 0 && view === "cluster" && (
            <div className="space-y-4">
              {Object.keys(clusters).length === 0 ? (
                <div className="card text-center py-8 text-gray-500 text-sm">
                  No keywords match your filters.
                </div>
              ) : (
                Object.entries(clusters)
                  .sort(([, a], [, b]) => (b as any[]).length - (a as any[]).length)
                  .map(([cluster, items]) => {
                    const arr = items as any[];
                    const avgVol = arr.filter(k => k.volume != null).length > 0
                      ? Math.round(arr.filter(k => k.volume != null).reduce((s, k) => s + k.volume, 0) / arr.filter(k => k.volume != null).length)
                      : null;
                    const avgKd = arr.filter(k => k.difficulty != null).length > 0
                      ? Math.round(arr.filter(k => k.difficulty != null).reduce((s, k) => s + k.difficulty, 0) / arr.filter(k => k.difficulty != null).length)
                      : null;
                    return (
                      <div key={cluster} className="card">
                        <div className="flex items-center gap-2 mb-3 flex-wrap">
                          <Tag size={14} className="text-atlas-400 shrink-0" />
                          <h3
                            className="font-semibold text-white"
                            dir={isArabic(cluster) ? "rtl" : "ltr"}
                          >
                            {cluster}
                          </h3>
                          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
                            {arr.length}
                          </span>
                          {avgVol != null && (
                            <span className="text-xs text-gray-500 ml-1">
                              avg vol: <span className="text-gray-300">{fmtVolume(avgVol)}</span>
                            </span>
                          )}
                          {avgKd != null && (
                            <span className={`text-xs px-1.5 py-0.5 rounded ml-1 ${
                              avgKd <= 30
                                ? "bg-green-900/40 text-green-400"
                                : avgKd <= 60
                                ? "bg-yellow-900/40 text-yellow-400"
                                : "bg-red-900/40 text-red-400"
                            }`}>
                              KD {avgKd}
                            </span>
                          )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {arr.map((kw: any) => (
                            <span
                              key={kw.id}
                              className={`text-xs px-2.5 py-1 rounded-full border ${
                                INTENT_STYLES[kw.intent] || "bg-gray-700 text-gray-400 border-gray-600"
                              }`}
                              dir={isArabic(kw.keyword) ? "rtl" : "ltr"}
                              title={[
                                `Intent: ${kw.intent ?? "unknown"}`,
                                kw.volume != null ? `Volume: ${fmtVolume(kw.volume)}` : null,
                                kw.difficulty != null ? `KD: ${kw.difficulty}` : null,
                              ].filter(Boolean).join(" · ")}
                            >
                              {kw.keyword}
                              {kw.volume != null && (
                                <span className="ml-1 opacity-60">{fmtVolume(kw.volume)}</span>
                              )}
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  })
              )}
            </div>
          )}

          {/* ── Table view ──────────────────────────────────────────────────── */}
          {!kLoading && kws.length > 0 && view === "table" && (
            <div className="card overflow-hidden p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wider">
                      <th className="text-left px-4 py-3 font-medium">Keyword</th>
                      <th className="text-left px-4 py-3 font-medium">Intent</th>
                      <th className="text-left px-4 py-3 font-medium">Cluster</th>
                      <th className="text-center px-4 py-3 font-medium">Lang</th>
                      <th className="text-right px-4 py-3 font-medium">Volume</th>
                      <th className="text-right px-4 py-3 font-medium w-40">Difficulty</th>
                      <th className="text-right px-4 py-3 font-medium">Position</th>
                      <th className="text-right px-4 py-3 font-medium">Clicks</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.slice(0, 500).map((kw: any) => (
                      <tr key={kw.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                        <td
                          className="px-4 py-2.5 text-gray-200 max-w-xs"
                          dir={isArabic(kw.keyword) ? "rtl" : "ltr"}
                        >
                          {kw.keyword}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className={`text-xs px-2 py-0.5 rounded-full border ${
                            INTENT_STYLES[kw.intent] || "bg-gray-700 text-gray-400 border-gray-600"
                          }`}>
                            {INTENT_LABELS[kw.intent] ?? kw.intent ?? "—"}
                          </span>
                        </td>
                        <td
                          className="px-4 py-2.5 text-gray-400 text-xs max-w-[180px] truncate"
                          dir={isArabic(kw.cluster || "") ? "rtl" : "ltr"}
                        >
                          {kw.cluster || "—"}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <span className={`text-xs px-1.5 py-0.5 rounded ${
                            kw.language === "ar"
                              ? "bg-amber-900/30 text-amber-400"
                              : "bg-blue-900/20 text-blue-400"
                          }`}>
                            {(kw.language || "en").toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-gray-300 text-right font-mono text-xs">
                          {fmtVolume(kw.volume)}
                        </td>
                        <td className="px-4 py-2.5">
                          <KdBar value={kw.difficulty} />
                        </td>
                        <td className="px-4 py-2.5 text-gray-400 text-right text-xs">
                          {kw.position ?? "—"}
                        </td>
                        <td className="px-4 py-2.5 text-gray-400 text-right text-xs">
                          {kw.clicks?.toLocaleString() ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {filtered.length > 500 && (
                  <p className="text-center text-gray-600 text-xs py-3 border-t border-gray-800">
                    Showing first 500 of {filtered.length.toLocaleString()} — use filters or export CSV to see all
                  </p>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
