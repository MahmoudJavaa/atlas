"use client";

import { useState, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSites, autoResearchKeywords, classifyKeywords, getKeywords } from "@/lib/api";
import {
  Zap, Search, Filter, LayoutGrid, Table2, Loader2, AlertCircle,
  ChevronDown, Plus, X, CheckCircle2, Tag,
} from "lucide-react";

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

export default function KeywordsPage() {
  const qc = useQueryClient();

  // ── Site selection ────────────────────────────────────────────────────────
  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });
  const [siteId, setSiteId] = useState<number | null>(null);

  useEffect(() => {
    const list = sites as any[];
    if (list.length > 0 && !siteId) {
      const complete = list.find((s) => s.onboarding_status === "complete");
      setSiteId((complete ?? list[0]).id);
    }
  }, [sites, siteId]);

  // ── Filters / view ───────────────────────────────────────────────────────
  const [view, setView]               = useState<"cluster" | "table">("cluster");
  const [filterIntent, setFilterIntent] = useState("");
  const [filterCluster, setFilterCluster] = useState("");
  const [search, setSearch]           = useState("");
  const [showSeedPanel, setShowSeedPanel] = useState(false);
  const [seedInput, setSeedInput]     = useState("");

  // ── Data ─────────────────────────────────────────────────────────────────
  const { data: keywords = [], isLoading: kLoading } = useQuery({
    queryKey: ["keywords", siteId],
    queryFn:  () => getKeywords(siteId!),
    enabled:  !!siteId,
  });

  // ── Mutations ─────────────────────────────────────────────────────────────
  const researchMutation = useMutation({
    mutationFn: () => autoResearchKeywords(siteId!),
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

  // ── Derived data ──────────────────────────────────────────────────────────
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
    () => [...new Set(kws.map((k: any) => k.cluster).filter(Boolean))].sort(),
    [kws]
  );

  const filtered = useMemo(() => {
    let list = kws;
    if (filterIntent) list = list.filter((k: any) => k.intent === filterIntent);
    if (filterCluster) list = list.filter((k: any) => k.cluster === filterCluster);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((k: any) => k.keyword?.toLowerCase().includes(q));
    }
    return list;
  }, [kws, filterIntent, filterCluster, search]);

  const clusters = useMemo(() => {
    return filtered.reduce((acc: Record<string, any[]>, kw: any) => {
      const c = kw.cluster || "Unclustered";
      (acc[c] = acc[c] || []).push(kw);
      return acc;
    }, {});
  }, [filtered]);

  const siteList = sites as any[];
  const activeSite = siteList.find((s) => s.id === siteId);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Keyword Intelligence</h1>
          <p className="text-gray-400 text-sm mt-0.5">
            {kws.length > 0
              ? `${kws.length.toLocaleString()} keywords tracked`
              : "Generate keyword research for your site"}
          </p>
        </div>

        {/* Site selector */}
        {siteList.length > 1 && (
          <div className="relative">
            <select
              className="appearance-none bg-gray-800/60 border border-gray-700 text-gray-200 rounded-lg pl-3 pr-8 py-2 text-sm focus:outline-none focus:border-atlas-500 cursor-pointer"
              value={siteId ?? ""}
              onChange={(e) => { setSiteId(Number(e.target.value)); setFilterCluster(""); setFilterIntent(""); }}
            >
              {siteList.map((s: any) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
          </div>
        )}
      </div>

      {/* No site selected */}
      {!siteId && (
        <div className="card text-center py-12">
          <p className="text-gray-400">Select a site to view keyword data.</p>
        </div>
      )}

      {siteId && (
        <>
          {/* Action bar */}
          <div className="card flex flex-wrap gap-3 items-center">
            {/* Auto-research */}
            <button
              className="btn-primary flex items-center gap-2 disabled:opacity-50"
              disabled={researchMutation.isPending || !siteId}
              onClick={() => researchMutation.mutate()}
            >
              {researchMutation.isPending ? (
                <><Loader2 size={15} className="animate-spin" /> Researching…</>
              ) : (
                <><Zap size={15} /> Auto-Research 1000+ Keywords</>
              )}
            </button>

            {/* Manual seed panel toggle */}
            <button
              className="btn-secondary flex items-center gap-2 text-sm"
              onClick={() => setShowSeedPanel((v) => !v)}
            >
              <Plus size={14} /> Add custom keywords
            </button>

            {researchMutation.isSuccess && (
              <div className="flex items-center gap-1.5 text-green-400 text-sm">
                <CheckCircle2 size={14} />
                {(researchMutation.data as any)?.new_keywords_added ?? 0} new keywords added
              </div>
            )}

            {researchMutation.isError && (
              <div className="flex items-center gap-1.5 text-red-400 text-sm">
                <AlertCircle size={14} /> Research failed — run a crawl first
              </div>
            )}
          </div>

          {/* Seed keyword input panel */}
          {showSeedPanel && (
            <div className="card space-y-3 border border-atlas-500/20">
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-white text-sm">Add seed keywords</h3>
                <button onClick={() => setShowSeedPanel(false)} className="text-gray-500 hover:text-gray-300">
                  <X size={14} />
                </button>
              </div>
              <textarea
                className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full h-28 resize-none focus:outline-none focus:border-atlas-500"
                placeholder={"locksmith london\nemergency locksmith\ncar locksmith near me"}
                value={seedInput}
                onChange={(e) => setSeedInput(e.target.value)}
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

              {/* Active filter chips */}
              {(filterIntent || filterCluster || search) && (
                <button
                  onClick={() => { setFilterIntent(""); setFilterCluster(""); setSearch(""); }}
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
              <Tag size={32} className="text-gray-700 mx-auto mb-3" />
              <p className="text-white font-semibold mb-1">No keywords yet</p>
              <p className="text-gray-400 text-sm mb-4">
                Click <strong className="text-atlas-300">Auto-Research 1000+ Keywords</strong> to generate
                a full keyword map from your site's crawl data, or add seeds manually.
              </p>
              <p className="text-gray-600 text-xs">
                Make sure you've run a site crawl first (Technical SEO tab).
              </p>
            </div>
          )}

          {/* Cluster view */}
          {!kLoading && kws.length > 0 && view === "cluster" && (
            <div className="space-y-4">
              {Object.keys(clusters).length === 0 ? (
                <div className="card text-center py-8 text-gray-500 text-sm">No keywords match your filters.</div>
              ) : (
                Object.entries(clusters)
                  .sort(([, a], [, b]) => (b as any[]).length - (a as any[]).length)
                  .map(([cluster, items]) => (
                    <div key={cluster} className="card">
                      <div className="flex items-center gap-2 mb-3">
                        <Tag size={14} className="text-atlas-400" />
                        <h3 className="font-semibold text-white">{cluster}</h3>
                        <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
                          {(items as any[]).length}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {(items as any[]).map((kw: any) => (
                          <span
                            key={kw.id}
                            className={`text-xs px-2.5 py-1 rounded-full border ${
                              INTENT_STYLES[kw.intent] || "bg-gray-700 text-gray-400 border-gray-600"
                            }`}
                            title={`Intent: ${kw.intent ?? "unknown"}`}
                          >
                            {kw.keyword}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))
              )}
            </div>
          )}

          {/* Table view */}
          {!kLoading && kws.length > 0 && view === "table" && (
            <div className="card overflow-hidden p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase tracking-wider">
                      <th className="text-left px-4 py-3 font-medium">Keyword</th>
                      <th className="text-left px-4 py-3 font-medium">Intent</th>
                      <th className="text-left px-4 py-3 font-medium">Cluster</th>
                      <th className="text-right px-4 py-3 font-medium">Volume</th>
                      <th className="text-right px-4 py-3 font-medium">Position</th>
                      <th className="text-right px-4 py-3 font-medium">Clicks</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.slice(0, 500).map((kw: any) => (
                      <tr key={kw.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                        <td className="px-4 py-2.5 text-gray-200">{kw.keyword}</td>
                        <td className="px-4 py-2.5">
                          <span className={`text-xs px-2 py-0.5 rounded-full border ${
                            INTENT_STYLES[kw.intent] || "bg-gray-700 text-gray-400 border-gray-600"
                          }`}>
                            {INTENT_LABELS[kw.intent] ?? kw.intent ?? "—"}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-gray-400 text-xs">{kw.cluster || "—"}</td>
                        <td className="px-4 py-2.5 text-gray-400 text-right">{kw.volume?.toLocaleString() ?? "—"}</td>
                        <td className="px-4 py-2.5 text-gray-400 text-right">{kw.position ?? "—"}</td>
                        <td className="px-4 py-2.5 text-gray-400 text-right">{kw.clicks?.toLocaleString() ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {filtered.length > 500 && (
                  <p className="text-center text-gray-600 text-xs py-3 border-t border-gray-800">
                    Showing first 500 of {filtered.length.toLocaleString()} — use filters to narrow down
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
