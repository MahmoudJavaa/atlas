"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getSites, getPerformance, forecastRevenue } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export default function Analytics() {
  const [siteId, setSiteId] = useState<number | null>(null);
  const [days, setDays] = useState(28);
  const [forecastInput, setForecastInput] = useState({ current: 1000, target: 2000, cr: 0.02, aov: 100 });
  const [forecastResult, setForecastResult] = useState<any>(null);

  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });
  const { data: performance } = useQuery({
    queryKey: ["performance", siteId, days],
    queryFn: () => getPerformance(siteId!, days),
    enabled: !!siteId,
  });

  const forecastMutation = useMutation({
    mutationFn: () =>
      forecastRevenue({
        current_clicks: forecastInput.current,
        target_clicks: forecastInput.target,
        conversion_rate: forecastInput.cr,
        avg_order_value: forecastInput.aov,
      }),
    onSuccess: setForecastResult,
  });

  return (
    <div className="space-y-5 max-w-5xl">
      <h1 className="text-2xl font-bold text-white">Analytics & Attribution</h1>

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
        <div>
          <label className="text-xs text-gray-400 mb-1 block">Period</label>
          <select
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={28}>Last 28 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
        <a
          href={`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/analytics/oauth/callback`}
          className="btn-secondary text-sm"
          target="_blank"
          rel="noopener noreferrer"
        >
          Connect GSC
        </a>
      </div>

      {performance && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Total Clicks", value: performance.total_clicks?.toLocaleString() },
            { label: "Impressions", value: performance.total_impressions?.toLocaleString() },
            { label: "Avg Position", value: performance.avg_position },
            { label: "Keywords", value: performance.keyword_count },
          ].map(({ label, value }) => (
            <div key={label} className="card">
              <p className="text-gray-400 text-xs mb-1">{label}</p>
              <p className="text-xl font-bold text-white">{value ?? "—"}</p>
            </div>
          ))}
        </div>
      )}

      {/* Revenue Forecast */}
      <div className="card">
        <h2 className="font-semibold text-white mb-4">Revenue Impact Forecast</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Current Clicks</label>
            <input
              type="number"
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full"
              value={forecastInput.current}
              onChange={(e) => setForecastInput({ ...forecastInput, current: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Target Clicks</label>
            <input
              type="number"
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full"
              value={forecastInput.target}
              onChange={(e) => setForecastInput({ ...forecastInput, target: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Conversion Rate</label>
            <input
              type="number"
              step="0.001"
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full"
              value={forecastInput.cr}
              onChange={(e) => setForecastInput({ ...forecastInput, cr: Number(e.target.value) })}
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Avg Order Value (£)</label>
            <input
              type="number"
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full"
              value={forecastInput.aov}
              onChange={(e) => setForecastInput({ ...forecastInput, aov: Number(e.target.value) })}
            />
          </div>
        </div>
        <button className="btn-primary" onClick={() => forecastMutation.mutate()}>Calculate Forecast</button>

        {forecastResult && (
          <div className="mt-4 grid grid-cols-3 gap-3">
            <div className="bg-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-400">Current Revenue</p>
              <p className="text-lg font-bold text-white">£{forecastResult.current_estimated_revenue?.toLocaleString()}</p>
            </div>
            <div className="bg-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-400">Target Revenue</p>
              <p className="text-lg font-bold text-white">£{forecastResult.target_estimated_revenue?.toLocaleString()}</p>
            </div>
            <div className="bg-green-900/40 border border-green-800 rounded-lg p-3">
              <p className="text-xs text-green-400">Revenue Uplift</p>
              <p className="text-lg font-bold text-green-300">+£{forecastResult.revenue_uplift?.toLocaleString()}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
