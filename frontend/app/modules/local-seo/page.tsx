"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getSites, generateLocalPage, publishContent } from "@/lib/api";
import { Loader2, CheckCircle, XCircle, Send } from "lucide-react";

export default function LocalSEO() {
  const [siteId, setSiteId] = useState<number | null>(null);
  const [service, setService] = useState("");
  const [location, setLocation] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [generated, setGenerated] = useState<any>(null);
  const [publishResult, setPublishResult] = useState<any>(null);

  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });

  const generateMutation = useMutation({
    mutationFn: () =>
      generateLocalPage({ site_id: siteId!, service, location, business_name: businessName }),
    onSuccess: (data) => setGenerated(data),
  });

  const publishMutation = useMutation({
    mutationFn: (dryRun: boolean) =>
      publishContent(generated.content_page_id, dryRun),
    onSuccess: (data) => setPublishResult(data),
  });

  return (
    <div className="space-y-5 max-w-5xl">
      <h1 className="text-2xl font-bold text-white">Local SEO Page Generator</h1>

      <div className="card space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Site</label>
            <select
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full"
              value={siteId || ""}
              onChange={(e) => setSiteId(Number(e.target.value))}
            >
              <option value="">Select site…</option>
              {sites.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Business Name</label>
            <input
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full"
              placeholder="Fantastic Services"
              value={businessName}
              onChange={(e) => setBusinessName(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Service</label>
            <input
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full"
              placeholder="Emergency Locksmith"
              value={service}
              onChange={(e) => setService(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 mb-1 block">Location</label>
            <input
              className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm w-full"
              placeholder="Manchester"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
          </div>
        </div>
        <button
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
          disabled={!siteId || !service || !location || !businessName || generateMutation.isPending}
          onClick={() => generateMutation.mutate()}
        >
          {generateMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : null}
          {generateMutation.isPending ? "Generating…" : "Generate Local Page"}
        </button>
      </div>

      {generated && (
        <div className="space-y-4">
          {/* Doorway check */}
          <div className={`card flex items-center gap-3 ${generated.publish_blocked ? "border-red-700" : "border-green-700"}`}>
            {generated.publish_blocked
              ? <XCircle size={18} className="text-red-400 shrink-0" />
              : <CheckCircle size={18} className="text-green-400 shrink-0" />
            }
            <div>
              <p className="font-semibold text-white text-sm">
                {generated.publish_blocked ? "Doorway Page Check: FAILED" : "Doorway Page Check: PASSED"}
              </p>
              <p className="text-gray-400 text-xs">{generated.publish_blocked_reason || `Score: ${generated.doorway_score}/100`}</p>
            </div>
          </div>

          {/* Meta */}
          <div className="card space-y-2">
            <h2 className="font-semibold text-white mb-2">Page Metadata</h2>
            <div>
              <label className="text-xs text-gray-500">Title Tag</label>
              <p className="text-gray-200 text-sm">{generated.title}</p>
            </div>
            <div>
              <label className="text-xs text-gray-500">Meta Description</label>
              <p className="text-gray-200 text-sm">{generated.meta_desc}</p>
            </div>
            <div>
              <label className="text-xs text-gray-500">Word Count</label>
              <p className="text-gray-200 text-sm">{generated.word_count}</p>
            </div>
          </div>

          {/* Content preview */}
          <div className="card">
            <h2 className="font-semibold text-white mb-3">Content Preview</h2>
            <div
              className="prose prose-invert prose-sm max-w-none text-gray-300 max-h-96 overflow-y-auto border border-gray-800 rounded-lg p-4"
              dangerouslySetInnerHTML={{ __html: generated.post_content || "" }}
            />
          </div>

          {/* Schema */}
          {generated.schema && Object.keys(generated.schema).length > 0 && (
            <div className="card">
              <h2 className="font-semibold text-white mb-2">Schema JSON-LD</h2>
              <pre className="text-xs text-gray-300 bg-gray-800 rounded-lg p-3 overflow-x-auto max-h-48">
                {JSON.stringify(generated.schema, null, 2)}
              </pre>
            </div>
          )}

          {/* Publish */}
          {!generated.publish_blocked && generated.content_page_id && (
            <div className="card space-y-3">
              <h2 className="font-semibold text-white">Publish to CMS</h2>
              <div className="flex gap-2">
                <button
                  className="btn-secondary flex items-center gap-2"
                  onClick={() => publishMutation.mutate(true)}
                  disabled={publishMutation.isPending}
                >
                  Preview Diff
                </button>
                <button
                  className="btn-primary flex items-center gap-2"
                  onClick={() => publishMutation.mutate(false)}
                  disabled={publishMutation.isPending}
                >
                  <Send size={14} />
                  Publish Now
                </button>
              </div>
              {publishResult && (
                <pre className="text-xs text-gray-300 bg-gray-800 rounded p-3 overflow-x-auto">
                  {JSON.stringify(publishResult, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
