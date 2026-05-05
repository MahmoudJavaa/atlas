"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Globe, ArrowRight, CheckCircle2, Circle, Loader2, AlertCircle, Zap } from "lucide-react";
import { startOnboarding, getOnboardingStatus } from "@/lib/api";
import { AuthGuard } from "@/components/auth/AuthGuard";

type Step = "domain" | "analyzing" | "plan";

const ANALYSIS_STEPS = [
  { key: "site_crawl", label: "Crawling site pages", icon: "🔍" },
  { key: "keyword_research", label: "Extracting keywords", icon: "🔑" },
  { key: "geo_scoring", label: "Scoring AI visibility (GEO)", icon: "🤖" },
  { key: "competitor_analysis", label: "Analysing competitors", icon: "🏆" },
  { key: "planning", label: "Building SEO action plan", icon: "📋" },
  { key: "complete", label: "Creating approval queue", icon: "✅" },
];

export default function OnboardingPage() {
  return (
    <AuthGuard>
      <OnboardingWizard />
    </AuthGuard>
  );
}

function OnboardingWizard() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("domain");
  const [domain, setDomain] = useState("");
  const [siteName, setSiteName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [analysisId, setAnalysisId] = useState<number | null>(null);
  const [siteId, setSiteId] = useState<number | null>(null);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // Auto-fill site name from domain
  const handleDomainChange = (val: string) => {
    setDomain(val);
    if (!siteName) {
      try {
        const normalized = val.startsWith("http") ? val : `https://${val}`;
        const parsed = new URL(normalized);
        const host = parsed.hostname.replace("www.", "");
        const name = host.split(".")[0];
        setSiteName(name.charAt(0).toUpperCase() + name.slice(1));
      } catch {}
    }
  };

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await startOnboarding({
        domain,
        name: siteName || domain,
        cms_type: "other",
      });
      setAnalysisId(result.analysis_id);
      setSiteId(result.site_id);
      setStep("analyzing");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to start analysis. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // Poll for analysis status
  useEffect(() => {
    if (step !== "analyzing" || !analysisId) return;

    const poll = async () => {
      try {
        const data = await getOnboardingStatus(analysisId);
        setAnalysisData(data);
        if (data.status === "complete") {
          clearInterval(pollRef.current!);
          setTimeout(() => setStep("plan"), 800);
        } else if (data.status === "failed") {
          clearInterval(pollRef.current!);
          setError(data.error || "Analysis failed. Please try again.");
          setStep("domain");
        }
      } catch {}
    };

    poll();
    pollRef.current = setInterval(poll, 3000);
    return () => clearInterval(pollRef.current!);
  }, [step, analysisId]);

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="w-10 h-10 bg-atlas-500 rounded-xl flex items-center justify-center">
            <Globe size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white leading-none">Atlas</h1>
            <p className="text-gray-500 text-xs">SEO & GEO Agent</p>
          </div>
        </div>

        {/* Step: domain input */}
        {step === "domain" && (
          <div className="card space-y-6">
            <div>
              <h2 className="text-xl font-bold text-white">Analyse your website</h2>
              <p className="text-gray-400 text-sm mt-1">
                Enter your domain and Atlas will run a full SEO audit, find keyword opportunities,
                and build you a prioritised action plan — automatically.
              </p>
            </div>

            {error && (
              <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg px-3 py-2 text-sm">
                <AlertCircle size={14} className="shrink-0" />
                {error}
              </div>
            )}

            <form onSubmit={handleStart} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Website URL</label>
                <input
                  type="text"
                  required
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-atlas-500 focus:ring-1 focus:ring-atlas-500 transition-colors"
                  placeholder="https://yoursite.com"
                  value={domain}
                  onChange={(e) => handleDomainChange(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-400 mb-1.5">Site name</label>
                <input
                  type="text"
                  required
                  className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-atlas-500 focus:ring-1 focus:ring-atlas-500 transition-colors"
                  placeholder="My Store"
                  value={siteName}
                  onChange={(e) => setSiteName(e.target.value)}
                />
              </div>

              <div className="pt-1">
                <div className="grid grid-cols-3 gap-3 mb-4">
                  {["🔍 Site audit", "🔑 Keywords", "📋 Action plan"].map((item) => (
                    <div key={item} className="bg-gray-800/50 rounded-lg p-2.5 text-center">
                      <p className="text-gray-300 text-xs">{item}</p>
                    </div>
                  ))}
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full btn-primary py-3 flex items-center justify-center gap-2 disabled:opacity-60 text-base"
                >
                  {loading ? (
                    <><Loader2 size={16} className="animate-spin" /> Starting...</>
                  ) : (
                    <><Zap size={16} /> Analyse my site <ArrowRight size={16} /></>
                  )}
                </button>
              </div>
            </form>

            <p className="text-gray-600 text-xs text-center">
              No changes are made to your site. Read-only analysis only.
            </p>
          </div>
        )}

        {/* Step: analyzing */}
        {step === "analyzing" && (
          <div className="card space-y-6">
            <div className="text-center">
              <div className="w-14 h-14 bg-atlas-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Loader2 size={24} className="text-atlas-400 animate-spin" />
              </div>
              <h2 className="text-xl font-bold text-white">Analysing your site</h2>
              <p className="text-gray-400 text-sm mt-1">This usually takes 1–3 minutes</p>
            </div>

            {/* Progress bar */}
            <div>
              <div className="flex justify-between text-xs text-gray-500 mb-1.5">
                <span>Progress</span>
                <span>{analysisData?.progress ?? 0}%</span>
              </div>
              <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-atlas-500 rounded-full transition-all duration-500"
                  style={{ width: `${analysisData?.progress ?? 0}%` }}
                />
              </div>
            </div>

            {/* Steps */}
            <div className="space-y-2">
              {ANALYSIS_STEPS.map((s) => {
                const completed = analysisData?.steps_completed?.includes(s.key);
                const isCurrent = analysisData?.current_step === s.key;
                return (
                  <div
                    key={s.key}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                      isCurrent ? "bg-atlas-500/10 border border-atlas-500/30" : ""
                    }`}
                  >
                    {completed ? (
                      <CheckCircle2 size={16} className="text-green-400 shrink-0" />
                    ) : isCurrent ? (
                      <Loader2 size={16} className="text-atlas-400 animate-spin shrink-0" />
                    ) : (
                      <Circle size={16} className="text-gray-700 shrink-0" />
                    )}
                    <span className={`text-sm ${completed ? "text-gray-400 line-through" : isCurrent ? "text-atlas-300" : "text-gray-600"}`}>
                      {s.icon} {s.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Step: plan ready */}
        {step === "plan" && (
          <div className="card space-y-6 text-center">
            <div>
              <div className="w-16 h-16 bg-green-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 size={28} className="text-green-400" />
              </div>
              <h2 className="text-xl font-bold text-white">Your action plan is ready!</h2>
              <p className="text-gray-400 text-sm mt-2 max-w-sm mx-auto">
                {analysisData?.final_report || "Atlas has analysed your site and created a prioritised plan."}
              </p>
            </div>

            <div className="bg-gray-800/50 rounded-xl p-4 text-left">
              <p className="text-gray-400 text-xs uppercase tracking-wider font-medium mb-3">What was found</p>
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center">
                  <p className="text-2xl font-bold text-white">{analysisData?.actions_created ?? 0}</p>
                  <p className="text-gray-500 text-xs mt-0.5">Actions</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-white">6</p>
                  <p className="text-gray-500 text-xs mt-0.5">Modules run</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-white">0</p>
                  <p className="text-gray-500 text-xs mt-0.5">Changes made</p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <button
                onClick={() => router.push("/approval-queue")}
                className="w-full btn-primary py-3 flex items-center justify-center gap-2 text-base"
              >
                Review action plan <ArrowRight size={16} />
              </button>
              <button
                onClick={() => router.push("/dashboard")}
                className="w-full bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl px-4 py-2.5 text-sm transition-colors"
              >
                Go to dashboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
