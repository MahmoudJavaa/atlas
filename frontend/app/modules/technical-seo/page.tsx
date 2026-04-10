"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSites, crawlSite, getCrawlResults } from "@/lib/api";
import { RefreshCw, AlertTriangle, Info, AlertCircle } from "lucide-react";

export default function TechnicalSEO() {
  const qc = useQueryClient();
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null);
  const [maxPages, setMaxPages] = useState(50);
  const [selectedUrl, setSelectedUrl] = useState<any>(null);

  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });

  const { data: results = [], isLoading: resultsLoading } = useQuery({
    queryKey: ["crawl-results", selectedSiteId],
    queryFn: () => getCrawlResults(selectedSiteId!),
    enabled: !!selectedSiteId,
  });

  const crawlMutation = useMutation({
    mutationFn: () => {
      const site = sites.find((s: any) => s.id === selectedSiteId);
      return crawlSite({ site_id: selectedSiteId!, start_url: site.url, max_pages: maxPages });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crawl-results"] }),
  });

  const activeResults = results as any[];

  return (
    <div className="space-y-5 max-w-6xl">
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
            {sites.map((s: any) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Max Pages</label>
          <input
            type="number"
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-24"
            value={maxPages}
            onChange={(e) => setMaxPages(Number(e.target.value))}
            min={1}
            max={500}
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
      </div>

      {crawlMutation.isSuccess && (
        <div className="bg-green-900/30 border border-green-800 text-green-400 rounded-lg px-4 py-2 text-sm">
          Crawl complete — {crawlMutation.data?.pages_crawled} pages audited.
        </div>
      )}

      {/* Results table */}
      {activeResults.length > 0 && (
        <div className="card overflow-hidden p-0">
          <div className="p-4 border-b border-gray-800">
            <h2 className="font-semibold text-white">Crawl Results ({activeResults.length} pages)</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400">
                  <th className="text-left p-3 font-medium">URL</th>
                  <th className="text-left p-3 font-medium">Status</th>
                  <th className="text-left p-3 font-medium">Title</th>
                  <th className="text-left p-3 font-medium">Words</th>
                  <th className="text-left p-3 font-medium">Score</th>
                  <th className="text-left p-3 font-medium">Issues</th>
                </tr>
              </thead>
              <tbody>
                {activeResults.map((row: any) => (
                  <tr
                    key={row.id}
                    className="border-b border-gray-800/50 hover:bg-gray-800/50 cursor-pointer"
                    onClick={() => setSelectedUrl(selectedUrl?.id === row.id ? null : row)}
                  >
                    <td className="p-3 text-gray-300 max-w-xs truncate font-mono text-xs">{row.url}</td>
                    <td className="p-3">
                      <span className={`text-xs font-mono ${row.status_code >= 400 ? "text-red-400" : row.status_code >= 300 ? "text-yellow-400" : "text-green-400"}`}>
                        {row.status_code}
                      </span>
                    </td>
                    <td className="p-3 text-gray-300 max-w-[200px] truncate text-xs">{row.title || "—"}</td>
                    <td className="p-3 text-gray-400 text-xs">{row.word_count}</td>
                    <td className="p-3">
                      <div className={`text-xs font-bold ${row.severity_score > 60 ? "text-red-400" : row.severity_score > 30 ? "text-yellow-400" : "text-green-400"}`}>
                        {row.severity_score}
                      </div>
                    </td>
                    <td className="p-3 flex gap-1 flex-wrap">
                      {row.issues?.critical?.length > 0 && <span className="badge-critical">{row.issues.critical.length} critical</span>}
                      {row.issues?.warning?.length > 0 && <span className="badge-warning">{row.issues.warning.length} warning</span>}
                      {row.issues?.info?.length > 0 && <span className="badge-info">{row.issues.info.length} info</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* URL detail drawer */}
      {selectedUrl && (
        <div className="card border-atlas-500/40">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-white text-sm truncate">{selectedUrl.url}</h3>
            <button onClick={() => setSelectedUrl(null)} className="text-gray-500 hover:text-white text-xs">Close</button>
          </div>
          <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
            <div><span className="text-gray-400">Title:</span> <span className="text-gray-200">{selectedUrl.title || "—"}</span></div>
            <div><span className="text-gray-400">Canonical:</span> <span className="text-gray-200 truncate">{selectedUrl.canonical || "—"}</span></div>
            <div><span className="text-gray-400">Indexable:</span> <span className={selectedUrl.indexable ? "text-green-400" : "text-red-400"}>{selectedUrl.indexable ? "Yes" : "No"}</span></div>
            <div><span className="text-gray-400">Word Count:</span> <span className="text-gray-200">{selectedUrl.word_count}</span></div>
          </div>
          {["critical", "warning", "info"].map((level) => (
            selectedUrl.issues?.[level]?.length > 0 && (
              <div key={level} className="mb-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">{level}</p>
                <ul className="space-y-1">
                  {selectedUrl.issues[level].map((issue: string, i: number) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      {level === "critical" && <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0" />}
                      {level === "warning" && <AlertTriangle size={14} className="text-yellow-400 mt-0.5 shrink-0" />}
                      {level === "info" && <Info size={14} className="text-blue-400 mt-0.5 shrink-0" />}
                      <span className="text-gray-300">{issue}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )
          ))}
        </div>
      )}
    </div>
  );
}
