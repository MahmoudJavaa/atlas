import axios from "axios";
import { getToken } from "@/lib/auth";

// In production (Vercel), NEXT_PUBLIC_API_URL is set to the Railway backend URL.
// Locally (Docker), it's empty and the Next.js proxy handles /api/* → backend.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Auth ───────────────────────────────────────────────────────────────────
export const register = (data: { email: string; full_name: string; password: string }) =>
  api.post("/auth/register", data).then((r) => r.data);

export const login = (data: { email: string; password: string }) =>
  api.post("/auth/login", data).then((r) => r.data);

export const getMe = () => api.get("/auth/me").then((r) => r.data);

// ── Sites ──────────────────────────────────────────────────────────────────
export const getSites = () => api.get("/sites/").then((r) => r.data);
export const createSite = (data: { url: string; name: string; cms_type?: string }) =>
  api.post("/sites/", data).then((r) => r.data);
export const deleteSite = (id: number) => api.delete(`/sites/${id}`).then((r) => r.data);

// ── Onboarding ─────────────────────────────────────────────────────────────
export const startOnboarding = (data: { domain: string; name: string; cms_type?: string }) =>
  api.post("/onboarding/start", data).then((r) => r.data);

export const getOnboardingStatus = (analysisId: number) =>
  api.get(`/onboarding/${analysisId}/status`).then((r) => r.data);

// ── Approval Queue ─────────────────────────────────────────────────────────
export const getActions = (siteId: number, status?: string) =>
  api.get(`/actions/${siteId}`, { params: { status } }).then((r) => r.data);

export const getPendingCount = () =>
  api.get("/actions/count/pending").then((r) => r.data);

export const approveAction = (actionId: number, note?: string) =>
  api.patch(`/actions/${actionId}/approve`, { note }).then((r) => r.data);

export const rejectAction = (actionId: number, note?: string) =>
  api.patch(`/actions/${actionId}/reject`, { note }).then((r) => r.data);

export const bulkApprove = (actionIds: number[], note?: string) =>
  api.post("/actions/bulk-approve", { action_ids: actionIds, note }).then((r) => r.data);

export const bulkReject = (actionIds: number[], note?: string) =>
  api.post("/actions/bulk-reject", { action_ids: actionIds, note }).then((r) => r.data);

// ── Technical SEO ──────────────────────────────────────────────────────────
export const crawlSite = (data: { site_id: number; start_url: string; max_pages?: number }) =>
  api.post("/technical-seo/crawl/sync", data).then((r) => r.data);
export const getCrawlResults = (siteId: number) =>
  api.get(`/technical-seo/results/${siteId}`).then((r) => r.data);
export const getCrawlSummary = (siteId: number) =>
  api.get(`/technical-seo/results/${siteId}/summary`).then((r) => r.data);

// ── Keywords ───────────────────────────────────────────────────────────────
export const classifyKeywords = (data: { site_id: number; seed_keywords: string[] }) =>
  api.post("/keywords/classify/sync", data).then((r) => r.data);
export const getKeywords = (siteId: number, intent?: string, cluster?: string) =>
  api.get(`/keywords/${siteId}`, { params: { intent, cluster, limit: 1500 } }).then((r) => r.data);
export const autoResearchKeywords = (siteId: number) =>
  api.post(`/keywords/auto-research/${siteId}`).then((r) => r.data);

// ── Content ────────────────────────────────────────────────────────────────
export const generateContent = (data: {
  site_id: number;
  keyword: string;
  intent: string;
  funnel_stage: string;
  page_type: string;
  location?: string;
}) => api.post("/content/generate", data).then((r) => r.data);

export const generateLocalPage = (data: {
  site_id: number;
  service: string;
  location: string;
  business_name: string;
}) => api.post("/content/local-page", data).then((r) => r.data);

export const getContentPages = (siteId: number, status?: string) =>
  api.get(`/content/${siteId}`, { params: { status } }).then((r) => r.data);

export const publishContent = (contentPageId: number, dryRun: boolean = true) =>
  api.post("/content/publish", { content_page_id: contentPageId, dry_run: dryRun }).then((r) => r.data);

// ── Analytics ──────────────────────────────────────────────────────────────
export const getPerformance = (siteId: number, days?: number) =>
  api.get(`/analytics/performance/${siteId}`, { params: { days } }).then((r) => r.data);
export const forecastRevenue = (data: {
  current_clicks: number;
  target_clicks: number;
  conversion_rate?: number;
  avg_order_value?: number;
}) => api.post("/analytics/forecast", data).then((r) => r.data);

// ── Agent ──────────────────────────────────────────────────────────────────
export const runAgent = (goal: string, siteId: number) =>
  api.post("/agent/run", { goal, site_id: siteId }).then((r) => r.data);
export const getAuditLog = (siteId: number) =>
  api.get(`/agent/audit-log/${siteId}`).then((r) => r.data);
