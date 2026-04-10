"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSites, createSite, deleteSite } from "@/lib/api";
import { Trash2, Plus, Save } from "lucide-react";

export default function Settings() {
  const qc = useQueryClient();
  const [newSite, setNewSite] = useState({ url: "", name: "", cms_type: "wordpress" });

  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });

  const createMutation = useMutation({
    mutationFn: () => createSite(newSite),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sites"] });
      setNewSite({ url: "", name: "", cms_type: "wordpress" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteSite(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sites"] }),
  });

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* Site management */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-white">Sites</h2>
        <div className="space-y-2">
          {(sites as any[]).map((site: any) => (
            <div key={site.id} className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
              <div>
                <p className="text-white text-sm font-medium">{site.name}</p>
                <p className="text-gray-400 text-xs">{site.url} · {site.cms_type}</p>
              </div>
              <button
                onClick={() => deleteMutation.mutate(site.id)}
                className="text-gray-500 hover:text-red-400 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>

        <div className="border-t border-gray-800 pt-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-300">Add Site</h3>
          <div className="grid grid-cols-2 gap-3">
            <input
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm col-span-2"
              placeholder="https://example.com"
              value={newSite.url}
              onChange={(e) => setNewSite({ ...newSite, url: e.target.value })}
            />
            <input
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm"
              placeholder="Site name"
              value={newSite.name}
              onChange={(e) => setNewSite({ ...newSite, name: e.target.value })}
            />
            <select
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm"
              value={newSite.cms_type}
              onChange={(e) => setNewSite({ ...newSite, cms_type: e.target.value })}
            >
              <option value="wordpress">WordPress</option>
              <option value="shopify">Shopify</option>
              <option value="other">Other</option>
            </select>
          </div>
          <button
            className="btn-primary flex items-center gap-2 disabled:opacity-50"
            onClick={() => createMutation.mutate()}
            disabled={!newSite.url || !newSite.name || createMutation.isPending}
          >
            <Plus size={14} />
            Add Site
          </button>
        </div>
      </div>

      {/* CMS Credentials info */}
      <div className="card space-y-3">
        <h2 className="font-semibold text-white">CMS Credentials</h2>
        <p className="text-gray-400 text-sm">Configure credentials in your <code className="text-atlas-400">.env</code> file:</p>
        <pre className="bg-gray-800 rounded-lg p-4 text-xs text-gray-300 overflow-x-auto">{`WORDPRESS_URL=https://your-site.com
WORDPRESS_USER=your-username
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx

SHOPIFY_STORE=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxx`}</pre>
      </div>

      <div className="card space-y-3">
        <h2 className="font-semibold text-white">API Keys</h2>
        <p className="text-gray-400 text-sm">Configure in your <code className="text-atlas-400">.env</code> file:</p>
        <pre className="bg-gray-800 rounded-lg p-4 text-xs text-gray-300 overflow-x-auto">{`ANTHROPIC_API_KEY=sk-ant-xxxx
SERPAPI_KEY=xxxx
GOOGLE_CLIENT_ID=xxxx
GOOGLE_CLIENT_SECRET=xxxx`}</pre>
      </div>
    </div>
  );
}
