"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2, XCircle, Loader2, AlertCircle, ChevronDown, ChevronUp,
  CheckSquare, Square, CheckCheck, X, Zap, FileText, Link2, Settings2,
  Globe, MapPin, Code
} from "lucide-react";
import { getSites, getActions, approveAction, rejectAction, bulkApprove, bulkReject } from "@/lib/api";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { clsx } from "clsx";

const ACTION_ICONS: Record<string, React.ReactNode> = {
  publish_content: <FileText size={14} />,
  create_local_page: <MapPin size={14} />,
  add_internal_links: <Link2 size={14} />,
  update_meta: <Settings2 size={14} />,
  fix_technical: <Code size={14} />,
  improve_geo: <Zap size={14} />,
  update_schema: <Code size={14} />,
  fix_canonical: <Globe size={14} />,
  general: <Settings2 size={14} />,
};

const ACTION_LABELS: Record<string, string> = {
  publish_content: "Publish content",
  create_local_page: "Create local page",
  add_internal_links: "Add internal links",
  update_meta: "Update meta",
  fix_technical: "Fix technical issue",
  improve_geo: "Improve GEO",
  update_schema: "Update schema",
  fix_canonical: "Fix canonical",
};

const PRIORITY_COLORS: Record<number, string> = {
  1: "bg-red-500/20 text-red-400 border-red-500/30",
  2: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  3: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  4: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  5: "bg-gray-700 text-gray-400 border-gray-600",
};

const PRIORITY_LABELS: Record<number, string> = {
  1: "Urgent", 2: "High", 3: "Medium", 4: "Low", 5: "Optional"
};

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-500/20 text-amber-400",
  approved: "bg-blue-500/20 text-blue-400",
  executing: "bg-blue-500/20 text-blue-400",
  executed: "bg-green-500/20 text-green-400",
  rejected: "bg-gray-700 text-gray-500",
  failed: "bg-red-500/20 text-red-400",
};

interface Action {
  id: number;
  site_id: number;
  action_type: string;
  title: string;
  description: string | null;
  payload: Record<string, any>;
  diff: Record<string, any> | null;
  status: string;
  priority: number;
  source_module: string;
  created_at: string;
  error_message: string | null;
}

export default function ApprovalQueuePage() {
  return (
    <AuthGuard>
      <ApprovalQueue />
    </AuthGuard>
  );
}

function ApprovalQueue() {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [rejectNote, setRejectNote] = useState<Record<number, string>>({});
  const [showRejectInput, setShowRejectInput] = useState<number | null>(null);
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null);

  const { data: sites = [] } = useQuery({ queryKey: ["sites"], queryFn: getSites });
  const siteList = sites as any[];

  // Auto-select the first complete site, fallback to first site
  const activeSite = selectedSiteId
    ? siteList.find((s) => s.id === selectedSiteId)
    : siteList.find((s) => s.onboarding_status === "complete") ?? siteList[0];

  const { data: actions = [], isLoading } = useQuery({
    queryKey: ["actions", activeSite?.id, statusFilter],
    queryFn: () => getActions(activeSite.id, statusFilter || undefined),
    enabled: !!activeSite?.id,
    refetchInterval: statusFilter === "pending" ? 10000 : false,
  });

  const approveMutation = useMutation({
    mutationFn: (id: number) => approveAction(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["actions"] });
      qc.invalidateQueries({ queryKey: ["pending-count"] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) => rejectAction(id, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["actions"] });
      qc.invalidateQueries({ queryKey: ["pending-count"] });
      setShowRejectInput(null);
    },
  });

  const bulkApproveMutation = useMutation({
    mutationFn: () => bulkApprove(Array.from(selected)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["actions"] });
      qc.invalidateQueries({ queryKey: ["pending-count"] });
      setSelected(new Set());
    },
  });

  const bulkRejectMutation = useMutation({
    mutationFn: () => bulkReject(Array.from(selected)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["actions"] });
      qc.invalidateQueries({ queryKey: ["pending-count"] });
      setSelected(new Set());
    },
  });

  const pendingActions = (actions as Action[]).filter((a) => a.status === "pending");
  const allSelected = pendingActions.length > 0 && pendingActions.every((a) => selected.has(a.id));

  const toggleSelect = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(pendingActions.map((a) => a.id)));
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Approval Queue</h1>
          {siteList.length > 1 ? (
            <div className="relative mt-1">
              <select
                className="appearance-none bg-gray-800/60 border border-gray-700 text-gray-300 rounded-lg pl-3 pr-8 py-1.5 text-sm focus:outline-none focus:border-atlas-500 cursor-pointer"
                value={activeSite?.id ?? ""}
                onChange={(e) => { setSelectedSiteId(Number(e.target.value)); setSelected(new Set()); }}
              >
                {siteList.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.name} — {s.url}</option>
                ))}
              </select>
              <ChevronDown size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            </div>
          ) : activeSite ? (
            <p className="text-gray-400 text-sm mt-0.5">
              Review and approve every change before it goes live · {activeSite.name}
            </p>
          ) : (
            <p className="text-gray-400 text-sm mt-0.5">Review and approve every change before it goes live</p>
          )}
        </div>
        {pendingActions.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">{pendingActions.length} pending</span>
            <button
              onClick={() => bulkApproveMutation.mutate()}
              disabled={bulkApproveMutation.isPending}
              className="btn-primary flex items-center gap-2 text-sm py-2"
            >
              <CheckCheck size={14} />
              Approve all
            </button>
          </div>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1 bg-gray-900 rounded-xl p-1 w-fit">
        {["pending", "executed", "rejected", ""].map((f) => (
          <button
            key={f}
            onClick={() => { setStatusFilter(f); setSelected(new Set()); }}
            className={clsx(
              "px-4 py-1.5 rounded-lg text-sm transition-colors",
              statusFilter === f
                ? "bg-gray-700 text-white font-medium"
                : "text-gray-500 hover:text-gray-300"
            )}
          >
            {f === "" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 bg-atlas-500/10 border border-atlas-500/30 rounded-xl px-4 py-3">
          <span className="text-atlas-300 text-sm font-medium">{selected.size} selected</span>
          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={() => bulkRejectMutation.mutate()}
              disabled={bulkRejectMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg text-sm transition-colors"
            >
              <X size={13} /> Reject selected
            </button>
            <button
              onClick={() => bulkApproveMutation.mutate()}
              disabled={bulkApproveMutation.isPending}
              className="btn-primary flex items-center gap-1.5 py-1.5 text-sm"
            >
              <CheckCheck size={13} /> Approve selected
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      {!activeSite ? (
        <div className="card text-center py-12">
          <Globe size={32} className="text-gray-700 mx-auto mb-3" />
          <p className="text-gray-400">No site found. Add a site first.</p>
        </div>
      ) : isLoading ? (
        <div className="card flex items-center justify-center py-12 gap-3 text-gray-400">
          <Loader2 size={20} className="animate-spin" />
          Loading actions...
        </div>
      ) : (actions as Action[]).length === 0 ? (
        <div className="card text-center py-12">
          <CheckCircle2 size={32} className="text-gray-700 mx-auto mb-3" />
          <p className="text-gray-400 font-medium">
            {statusFilter === "pending" ? "No pending actions" : "No actions found"}
          </p>
          <p className="text-gray-600 text-sm mt-1">
            {statusFilter === "pending"
              ? "Run an analysis from the dashboard to generate actions."
              : ""}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {/* Select all (only when pending filter) */}
          {statusFilter === "pending" && pendingActions.length > 0 && (
            <div className="flex items-center gap-2 px-1 mb-1">
              <button onClick={toggleAll} className="text-gray-500 hover:text-gray-300">
                {allSelected ? <CheckSquare size={14} /> : <Square size={14} />}
              </button>
              <span className="text-xs text-gray-600">Select all</span>
            </div>
          )}

          {(actions as Action[]).map((action) => (
            <ActionCard
              key={action.id}
              action={action}
              isExpanded={expandedId === action.id}
              isSelected={selected.has(action.id)}
              onToggleExpand={() => setExpandedId(expandedId === action.id ? null : action.id)}
              onToggleSelect={() => toggleSelect(action.id)}
              onApprove={() => approveMutation.mutate(action.id)}
              onReject={(note) => rejectMutation.mutate({ id: action.id, note })}
              isApproving={approveMutation.isPending && approveMutation.variables === action.id}
              isRejecting={rejectMutation.isPending && rejectMutation.variables?.id === action.id}
              showRejectInput={showRejectInput === action.id}
              onShowRejectInput={() => setShowRejectInput(showRejectInput === action.id ? null : action.id)}
              rejectNote={rejectNote[action.id] || ""}
              onRejectNoteChange={(v) => setRejectNote({ ...rejectNote, [action.id]: v })}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ActionCard({
  action, isExpanded, isSelected, onToggleExpand, onToggleSelect,
  onApprove, onReject, isApproving, isRejecting,
  showRejectInput, onShowRejectInput, rejectNote, onRejectNoteChange,
}: {
  action: Action;
  isExpanded: boolean;
  isSelected: boolean;
  onToggleExpand: () => void;
  onToggleSelect: () => void;
  onApprove: () => void;
  onReject: (note?: string) => void;
  isApproving: boolean;
  isRejecting: boolean;
  showRejectInput: boolean;
  onShowRejectInput: () => void;
  rejectNote: string;
  onRejectNoteChange: (v: string) => void;
}) {
  const isPending = action.status === "pending";

  return (
    <div className={clsx(
      "bg-gray-900 border rounded-xl overflow-hidden transition-colors",
      isSelected ? "border-atlas-500/50" : "border-gray-800",
      isExpanded ? "border-gray-700" : ""
    )}>
      {/* Main row */}
      <div className="flex items-start gap-3 p-4">
        {/* Checkbox (only for pending) */}
        {isPending && (
          <button onClick={onToggleSelect} className="mt-0.5 text-gray-500 hover:text-atlas-400 shrink-0">
            {isSelected ? <CheckSquare size={15} className="text-atlas-400" /> : <Square size={15} />}
          </button>
        )}

        {/* Icon */}
        <div className={clsx(
          "w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5",
          "bg-gray-800 text-gray-400"
        )}>
          {ACTION_ICONS[action.action_type] || ACTION_ICONS.general}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-2 flex-wrap">
            <p className="text-white text-sm font-medium leading-tight">{action.title}</p>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <span className={clsx(
                "text-xs px-2 py-0.5 rounded-full border",
                PRIORITY_COLORS[action.priority] || PRIORITY_COLORS[5]
              )}>
                {PRIORITY_LABELS[action.priority] || "P" + action.priority}
              </span>
              <span className={clsx("text-xs px-2 py-0.5 rounded-full", STATUS_STYLES[action.status] || "bg-gray-700 text-gray-400")}>
                {action.status}
              </span>
            </div>
          </div>
          <p className="text-gray-500 text-xs mt-0.5">
            {ACTION_LABELS[action.action_type] || action.action_type} · {action.source_module} ·{" "}
            {new Date(action.created_at).toLocaleDateString()}
          </p>
        </div>

        {/* Actions + expand */}
        <div className="flex items-center gap-2 shrink-0">
          {isPending && (
            <>
              <button
                onClick={onShowRejectInput}
                disabled={isRejecting}
                className="p-1.5 rounded-lg bg-gray-800 hover:bg-red-500/20 text-gray-400 hover:text-red-400 transition-colors"
                title="Reject"
              >
                <XCircle size={16} />
              </button>
              <button
                onClick={onApprove}
                disabled={isApproving}
                className="p-1.5 rounded-lg bg-gray-800 hover:bg-green-500/20 text-gray-400 hover:text-green-400 transition-colors"
                title="Approve"
              >
                {isApproving ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle2 size={16} />}
              </button>
            </>
          )}
          <button onClick={onToggleExpand} className="p-1.5 text-gray-600 hover:text-gray-400 transition-colors">
            {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>
        </div>
      </div>

      {/* Reject input */}
      {showRejectInput && isPending && (
        <div className="px-4 pb-3 flex items-center gap-2">
          <input
            className="flex-1 bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-red-500"
            placeholder="Reason for rejection (optional)"
            value={rejectNote}
            onChange={(e) => onRejectNoteChange(e.target.value)}
            autoFocus
          />
          <button
            onClick={() => onReject(rejectNote || undefined)}
            disabled={isRejecting}
            className="px-3 py-1.5 bg-red-500/20 border border-red-500/30 text-red-400 rounded-lg text-sm hover:bg-red-500/30 transition-colors disabled:opacity-50"
          >
            {isRejecting ? <Loader2 size={14} className="animate-spin" /> : "Reject"}
          </button>
        </div>
      )}

      {/* Expanded detail */}
      {isExpanded && (
        <div className="border-t border-gray-800 p-4 space-y-4">
          {/* Rationale */}
          {action.description && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Why Atlas recommends this</p>
              <p className="text-gray-300 text-sm leading-relaxed">{action.description}</p>
            </div>
          )}

          {/* Payload preview */}
          {action.payload && Object.keys(action.payload).length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Details</p>
              <div className="bg-gray-800/50 rounded-lg p-3 space-y-1">
                {Object.entries(action.payload).map(([k, v]) => (
                  <div key={k} className="flex gap-2 text-sm">
                    <span className="text-gray-500 min-w-[120px] shrink-0">{k.replace(/_/g, " ")}:</span>
                    <span className="text-gray-300 break-all">
                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {action.error_message && (
            <div className="flex items-start gap-2 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
              <AlertCircle size={14} className="text-red-400 shrink-0 mt-0.5" />
              <p className="text-red-400 text-sm">{action.error_message}</p>
            </div>
          )}

          {/* Approve button in expanded view too */}
          {isPending && (
            <div className="flex gap-2 pt-1">
              <button
                onClick={onApprove}
                disabled={isApproving}
                className="btn-primary flex items-center gap-2 text-sm py-2"
              >
                {isApproving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                Approve this action
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
