"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getSites, runAgent, getAuditLog } from "@/lib/api";
import { Bot, Loader2, ChevronRight } from "lucide-react";

export default function AgentPage() {
  const [siteId, setSiteId] = useState<number | null>(null);
  const [goal, setGoal] = useState("");
  const [result, setResult] = useState<any>(null);

  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });
  const { data: auditLog = [] } = useQuery({
    queryKey: ["audit-log", siteId],
    queryFn: () => getAuditLog(siteId!),
    enabled: !!siteId,
    refetchInterval: 5000,
  });

  const agentMutation = useMutation({
    mutationFn: () => runAgent(goal, siteId!),
    onSuccess: setResult,
  });

  const examples = [
    "Crawl the site and give me a summary of all critical SEO issues",
    "Classify these keywords: locksmith london, emergency locksmith, car locksmith",
    "Generate a local SEO page for Emergency Locksmith in Manchester",
    "Analyse competitors: checkatrade.com and mybuilder.com",
  ];

  return (
    <div className="space-y-5 max-w-4xl">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 bg-atlas-500/20 rounded-xl flex items-center justify-center">
          <Bot size={18} className="text-atlas-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Atlas Agent</h1>
          <p className="text-gray-400 text-sm">Autonomous SEO orchestration via Claude tool use</p>
        </div>
      </div>

      <div className="card space-y-4">
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

        <div>
          <label className="text-xs text-gray-400 mb-1 block">Goal</label>
          <textarea
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-3 text-sm w-full h-28 resize-none"
            placeholder="e.g. Grow organic traffic for our locksmith service across 20 UK cities"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
        </div>

        <div className="flex flex-wrap gap-2">
          {examples.map((ex) => (
            <button
              key={ex}
              onClick={() => setGoal(ex)}
              className="text-xs text-gray-400 bg-gray-800 hover:bg-gray-700 px-2 py-1 rounded border border-gray-700 transition-colors"
            >
              {ex.slice(0, 50)}…
            </button>
          ))}
        </div>

        <button
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
          disabled={!siteId || !goal.trim() || agentMutation.isPending}
          onClick={() => agentMutation.mutate()}
        >
          {agentMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Bot size={14} />}
          {agentMutation.isPending ? "Agent Running…" : "Run Agent"}
        </button>

        {agentMutation.isPending && (
          <div className="text-sm text-gray-400 animate-pulse">
            Atlas is planning and executing tasks. This may take a minute…
          </div>
        )}
      </div>

      {result && (
        <div className="card space-y-4">
          <h2 className="font-semibold text-white">Agent Report</h2>
          <div className="bg-gray-800 rounded-lg p-4 text-sm text-gray-200 whitespace-pre-wrap">
            {result.final_report}
          </div>
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              Audit Trail ({result.audit_trail?.length} actions)
            </h3>
            <div className="space-y-2">
              {result.audit_trail?.map((entry: any, i: number) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <ChevronRight size={12} className="text-atlas-400 mt-0.5 shrink-0" />
                  <div>
                    <span className="text-atlas-400 font-mono">{entry.tool}</span>
                    <span className="text-gray-500 ml-2">{entry.timestamp}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {(auditLog as any[]).length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-white mb-3">Recent Actions</h2>
          <div className="space-y-1">
            {(auditLog as any[]).slice(0, 20).map((log: any) => (
              <div key={log.id} className="flex items-center justify-between text-xs p-2 bg-gray-800 rounded">
                <div className="flex items-center gap-2">
                  <span className="text-gray-500 font-mono">{log.module}</span>
                  <ChevronRight size={10} className="text-gray-600" />
                  <span className="text-gray-300">{log.action}</span>
                </div>
                <span className="text-gray-500">{new Date(log.created_at).toLocaleTimeString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
