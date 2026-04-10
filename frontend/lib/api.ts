import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: { "Content-Type": "application/json" },
});

// Sites
export const getSites = () => api.get("/sites/").then((r) => r.data);
export const createSite = (data: { url: string; name: string; cms_type?: string }) =>
  api.post("/sites/", data).then((r) => r.data);
export const deleteSite = (id: number) => api.delete(`/sites/${id}`).then((r) => r.data);

// Technical SEO
export const crawlSite = (data: { site_id: number; start_url: string; max_pages?: number }) =>
  api.post("/technical-seo/crawl/sync", data).then((r) => r.data);
export const getCrawlResults = (siteId: number) =>
  api.get(`/technical-seo/results/${siteId}`).then((r) => r.data);
export const getCrawlSummary = (siteId: number) =>
  api.get(`/technical-seo/results/${siteId}/summary`).then((r) => r.data);

// Keywords
export const classifyKeywords = (data: { site_id: number; seed_keywords: string[] }) =>
  api.post("/keywords/classify/sync", data).then((r) => r.data);
export const getKeywords = (siteId: number, intent?: string) =>
  api.get(`/keywords/${siteId}`, { params: { intent } }).then((r) => r.data);

// Content
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

// Analytics
export const getPerformance = (siteId: number, days?: number) =>
  api.get(`/analytics/performance/${siteId}`, { params: { days } }).then((r) => r.data);
export const forecastRevenue = (data: {
  current_clicks: number;
  target_clicks: number;
  conversion_rate?: number;
  avg_order_value?: number;
}) => api.post("/analytics/forecast", data).then((r) => r.data);

// Agent
export const runAgent = (goal: string, siteId: number) =>
  api.post("/agent/run", { goal, site_id: siteId }).then((r) => r.data);
export const getAuditLog = (siteId: number) =>
  api.get(`/agent/audit-log/${siteId}`).then((r) => r.data);
