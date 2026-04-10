"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSites, classifyKeywords, getKeywords } from "@/lib/api";

const INTENT_COLORS: Record<string, string> = {
  informational: "bg-blue-900/40 text-blue-400 border-blue-800",
  commercial: "bg-purple-900/40 text-purple-400 border-purple-800",
  transactional: "bg-green-900/40 text-green-400 border-green-800",
  navigational: "bg-gray-700 text-gray-400 border-gray-600",
};

export default function Keywords() {
  const qc = useQueryClient();
  const [siteId, setSiteId] = useState<number | null>(null);
  const [seedInput, setSeedInput] = useState("");
  const [filterIntent, setFilterIntent] = useState("");
  const [view, setView] = useState<"table" | "cluster">("cluster");

  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });
  const { data: keywords = [] } = useQuery({
    queryKey: ["keywords", siteId, filterIntent],
    queryFn: () => getKeywords(siteId!, filterIntent || undefined),
    enabled: !!siteId,
  });

  const classifyMutation = useMutation({
    mutationFn: () =>
      classifyKeywords({
        site_id: siteId!,
        seed_keywords: seedInput.split("\n").map((k) => k.trim()).filter(Boolean),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["keywords"] }),
  });

  const kws = keywords as any[];
  const clusters = kws.reduce((acc: Record<string, any[]>, kw: any) => {
    const c = kw.cluster || "Unclustered";
    (acc[c] = acc[c] || []).push(kw);
    return acc;
  }, {});

  return (
    <div className="space-y-5 max-w-6xl">
      <h1 className="text-2xl font-bold text-white">Keyword Intelligence</h1>

      <div className="card flex flex-wrap gap-3 items-end">
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Site</label>
          <select
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm"
            value={siteId || ""}
            onChange={(e) => setSiteId(Number(e.target.value))}
          >
            <option value="">Select site…</option>
            {sites.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div className="flex-1 min-w-64">
          <label className="text-xs text-gray-400 mb-1 block">Seed Keywords (one per line)</label>
          <textarea
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full h-20 resize-none"
            placeholder="locksmith london&#10;emergency locksmith&#10;car locksmith near me"
            value={seedInput}
            onChange={(e) => setSeedInput(e.target.value)}
          />
        </div>
        <button
          className="btn-primary disabled:opacity-50"
          disabled={!siteId || !seedInput.trim() || classifyMutation.isPending}
          onClick={() => classifyMutation.mutate()}
        >
          {classifyMutation.isPending ? "Classifying…" : "Classify Keywords"}
        </button>
      </div>

      {kws.length > 0 && (
        <>
          <div className="flex items-center gap-3">
            <div className="flex gap-1 bg-gray-800 rounded-lg p-1">
              {["cluster", "table"].map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v as any)}
                  className={`px-3 py-1 rounded-md text-sm capitalize transition-colors ${view === v ? "bg-gray-700 text-white" : "text-gray-400 hover:text-white"}`}
                >
                  {v}
                </button>
              ))}
            </div>
            <select
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-1.5 text-sm"
              value={filterIntent}
              onChange={(e) => setFilterIntent(e.target.value)}
            >
              <option value="">All intents</option>
              {["informational", "commercial", "transactional", "navigational"].map((i) => (
                <option key={i} value={i}>{i}</option>
              ))}
            </select>
            <span className="text-gray-400 text-sm">{kws.length} keywords</span>
          </div>

          {view === "cluster" ? (
            <div className="space-y-4">
              {Object.entries(clusters).map(([cluster, items]) => (
                <div key={cluster} className="card">
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="font-semibold text-white">{cluster}</h3>
                    <span className="text-xs text-gray-500">{(items as any[]).length} keywords</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(items as any[]).map((kw: any) => (
                      <span
                        key={kw.id}
                        className={`text-xs px-2 py-1 rounded-full border ${INTENT_COLORS[kw.intent] || "bg-gray-700 text-gray-400 border-gray-600"}`}
                        title={`Intent: ${kw.intent}`}
                      >
                        {kw.keyword}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card overflow-hidden p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-gray-400">
                    <th className="text-left p-3 font-medium">Keyword</th>
                    <th className="text-left p-3 font-medium">Intent</th>
                    <th className="text-left p-3 font-medium">Cluster</th>
                    <th className="text-left p-3 font-medium">Volume</th>
                    <th className="text-left p-3 font-medium">Position</th>
                  </tr>
                </thead>
                <tbody>
                  {kws.map((kw: any) => (
                    <tr key={kw.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                      <td className="p-3 text-gray-200">{kw.keyword}</td>
                      <td className="p-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${INTENT_COLORS[kw.intent] || ""}`}>
                          {kw.intent}
                        </span>
                      </td>
                      <td className="p-3 text-gray-400">{kw.cluster}</td>
                      <td className="p-3 text-gray-400">{kw.volume ?? "—"}</td>
                      <td className="p-3 text-gray-400">{kw.position ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
