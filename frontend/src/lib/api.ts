import axios from "axios";
import type { AppealShareResponse, AppealTrendsResponse, LPMirrorInfo, LPAssetInfo, LPRedirectStep } from "../types";

const isBrowser = typeof window !== "undefined";
const publicApiUrl = process.env.NEXT_PUBLIC_API_URL;
const localhostHosts = new Set(["localhost", "127.0.0.1", "::1"]);

function resolveApiBase(): string {
  if (isBrowser) {
    const hostname = window.location.hostname.toLowerCase();
    if (publicApiUrl && localhostHosts.has(hostname)) {
      return `${publicApiUrl}/api/v1`;
    }
    return "/api/v1";
  }

  if (publicApiUrl) {
    return `${publicApiUrl}/api/v1`;
  }

  return "/api/v1";
}

// Browser requests should only use localhost API targets when the app itself
// is being served from localhost. Hosted environments must stay same-origin.
const API_BASE = resolveApiBase();

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 55_000, // Match proxy timeout
});

// ─── Retry helper ───

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 1_500;
const RETRYABLE_STATUSES = new Set([502, 503, 504]);

function isRetryable(status: number): boolean {
  return RETRYABLE_STATUSES.has(status);
}

async function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

// ─── Native fetch wrapper (more reliable than axios in some environments) ───

class FetchError extends Error {
  status: number;
  data: unknown;
  constructor(status: number, data: unknown) {
    super(`HTTP ${status}`);
    this.status = status;
    this.data = data;
  }
}

/**
 * Native fetch-based API helper with automatic retry for transient errors.
 */
export async function fetchApi<T = unknown>(
  path: string,
  options?: {
    method?: string;
    body?: unknown;
    params?: Record<string, string | number | undefined>;
    timeoutMs?: number;
  },
): Promise<T> {
  let url = `${API_BASE}${path}`;
  if (options?.params) {
    const qs = Object.entries(options.params)
      .filter(([, v]) => v !== undefined && v !== null)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
      .join("&");
    if (qs) url += `?${qs}`;
  }

  const method = options?.method || "GET";
  const headers: Record<string, string> = { Accept: "application/json" };

  if (options?.body) {
    headers["Content-Type"] = "application/json";
  }

  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const init: RequestInit = {
    method,
    headers,
    // Ranking/crawl data must always reflect latest backend state.
    cache: "no-store",
  };
  if (options?.body) {
    init.body = JSON.stringify(options.body);
  }

  let lastError: FetchError | Error | null = null;
  const timeoutMs = options?.timeoutMs ?? 55_000;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...init, signal: controller.signal });
      clearTimeout(timeoutId);

      // Retry on transient server errors (502/503/504 from Lambda cold start etc.)
      if (isRetryable(res.status) && attempt < MAX_RETRIES) {
        await sleep(RETRY_DELAY_MS * (attempt + 1));
        continue;
      }

      const text = await res.text();
      let data: unknown = null;
      if (text) {
        try { data = JSON.parse(text); } catch { data = null; }
      }

      if (!res.ok) {
        throw new FetchError(res.status, data);
      }
      return data as T;
    } catch (err) {
      clearTimeout(timeoutId);
      lastError = err instanceof Error ? err : new Error(String(err));

      // Don't retry client errors (4xx) or if we're on last attempt
      if (err instanceof FetchError && !isRetryable(err.status)) {
        throw err;
      }
      if (attempt < MAX_RETRIES) {
        await sleep(RETRY_DELAY_MS * (attempt + 1));
        continue;
      }
    }
  }

  throw lastError || new Error("API request failed");
}

// ─── API response type guards ───

export function isApiList<T>(data: unknown): data is { items: T[]; total: number } {
  return data != null && typeof data === "object" && "items" in data && Array.isArray((data as Record<string, unknown>).items);
}

export function assertObject(data: unknown, context: string): asserts data is Record<string, unknown> {
  if (!data || typeof data !== "object") throw new Error(`[${context}] Invalid response: expected object`);
}

export function assertHasField<K extends string>(data: Record<string, unknown>, field: K, context: string): asserts data is Record<string, unknown> & Record<K, unknown> {
  if (!(field in data)) throw new Error(`[${context}] Missing required field: ${field}`);
}

// Request interceptor for auth token (guarded for SSR)
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Track retry counts without mutating config objects
const axiosRetryMap = new WeakMap<object, number>();

// Response interceptor: retry on transient errors + handle 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config;
    const status = error.response?.status;

    // Auto-retry on 502/503/504 (サーバー起動待ち)
    if (config && isRetryable(status)) {
      const count = (axiosRetryMap.get(config) || 0) + 1;
      if (count <= MAX_RETRIES) {
        axiosRetryMap.set(config, count);
        await sleep(RETRY_DELAY_MS * count);
        return api(config);
      }
    }

    if (typeof window !== "undefined" && status === 401) {
      localStorage.removeItem("access_token");
      console.warn("401 Unauthorized: auth token missing or expired");
    }
    return Promise.reject(error);
  }
);

// Ads API
export const adsApi = {
  list: (params?: Record<string, unknown>) => api.get("/ads", { params }),
  get: (id: number) => api.get(`/ads/${id}`),
  create: (data: Record<string, unknown>) => api.post("/ads", data),
  upload: (file: File, params?: Record<string, unknown>) => {
    const formData = new FormData();
    formData.append("file", file);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        formData.append(key, String(value));
      });
    }
    return api.post("/ads/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  analyze: (id: number) => api.post(`/ads/${id}/analyze`),
  getAnalysis: (id: number) => api.get(`/ads/${id}/analysis`),
  crawl: (data: Record<string, unknown>) => api.post("/ads/crawl", data),
  crawlStatus: (jobId: string) => fetchApi<{
    job_id: string;
    status: string;
    progress_percent: number;
    total_platforms: number;
    completed_platforms: number;
    current_platform: string | null;
    total_ads_found: number;
    error_message: string | null;
    platforms: string[] | null;
  }>(`/ads/crawl/${jobId}/status`),
  delete: (id: number) => api.delete(`/ads/${id}`),
};

export const dataQualityApi = {
  getCreativeLibraryAudit: (params?: Record<string, string | number | undefined>) =>
    fetchApi("/data-quality/creative-library-audit", { params }),
};

// Creative API
export const creativeApi = {
  generateScript: (data: Record<string, unknown>) =>
    api.post("/creative/script", data),
  generateCopy: (data: Record<string, unknown>) =>
    api.post("/creative/copy", data),
  generateLPCopy: (data: Record<string, unknown>) =>
    api.post("/creative/lp-copy", data),
  generateStoryboard: (data: Record<string, unknown>) =>
    api.post("/creative/storyboard", data),
  getImprovements: (data: Record<string, unknown>) =>
    api.post("/creative/improvements", data),
  getABTestPlan: (data: Record<string, unknown>) =>
    api.post("/creative/ab-test-plan", data),
  rewriteWinningPattern: (data: Record<string, unknown>) =>
    api.post("/creative/winning-pattern", data),
  getStructures: () => api.get("/creative/structures"),
};

// Predictions API
export const predictionsApi = {
  predict: (data: Record<string, unknown>) =>
    api.post("/predictions/performance", data),
  assessFatigue: (data: Record<string, unknown>) =>
    api.post("/predictions/fatigue", data),
  batchFatigue: (data: Record<string, unknown>) =>
    api.post("/predictions/fatigue/batch", data),
};

// Analytics API
export const analyticsApi = {
  getDashboard: () => api.get("/analytics/dashboard"),
  getCompetitor: (name: string) => api.get(`/analytics/competitor/${name}`),
  getTrends: (params?: Record<string, unknown>) =>
    api.get("/analytics/trends", { params }),

  // Appeal Share & Trends
  getAppealShare: (params?: { genre?: string; date_from?: string; date_to?: string }) =>
    fetchApi<AppealShareResponse>(`/rankings/appeal-share?${new URLSearchParams(params as any)}`),

  getAppealTrends: (months?: number, genre?: string) =>
    fetchApi<AppealTrendsResponse>(`/rankings/appeal-trends?months=${months || 6}${genre ? `&genre=${genre}` : ''}`),

  // Brand Registry
  getBrandDetail: (brandId: number) =>
    fetchApi<any>(`/rankings/brand/${brandId}`),

  // Creative Families
  getCreativeFamilies: (params?: { page?: number; page_size?: number; advertiser?: string; genre?: string; min_members?: number }) =>
    fetchApi<any>(`/rankings/creative-families?${new URLSearchParams(Object.fromEntries(Object.entries(params || {}).filter(([_, v]) => v != null).map(([k, v]) => [k, String(v)])))}`),

  getCreativeFamilyDetail: (familyId: number) =>
    fetchApi<any>(`/rankings/creative-family/${familyId}`),

  // LP Snapshots
  getLPSnapshots: (cardId: number) =>
    fetchApi<any>(`/rankings/lp-snapshot/${cardId}`),
};

// Auth API
export const authApi = {
  login: (data: { email: string; password: string }) =>
    api.post("/auth/login", data),
  register: (data: Record<string, unknown>) => api.post("/auth/register", data),
  refresh: (token: string) => api.post("/auth/refresh", { refresh_token: token }),
};

// LP Analysis API
export const lpAnalysisApi = {
  crawl: (data: { url: string; ad_id?: number; genre?: string; product_name?: string; advertiser_name?: string; auto_analyze?: boolean }) =>
    api.post("/lp-analysis/crawl", data),
  batchCrawl: (data: { urls: string[]; genre?: string; auto_analyze?: boolean }) =>
    api.post("/lp-analysis/batch-crawl", data),
  list: (params?: Record<string, unknown>) =>
    api.get("/lp-analysis/list", { params }),
  getDetail: (id: number) =>
    api.get(`/lp-analysis/${id}`),
  getUSPs: (id: number) =>
    api.get(`/lp-analysis/${id}/usps`),
  getAppealAxes: (id: number) =>
    api.get(`/lp-analysis/${id}/appeal-axes`),
  competitorInsight: (data: { genre: string; limit?: number }) =>
    api.post("/lp-analysis/competitor-insight", data),
  uspFlow: (data: { product_name: string; product_description: string; target_audience: string; genre: string; competitor_lp_ids?: number[] }) =>
    api.post("/lp-analysis/usp-flow", data),
  // Own LP management
  importOwn: (data: { label: string; genre: string; product_name: string; url?: string; html_content?: string; text_content?: string; advertiser_name?: string; version?: number; auto_analyze?: boolean }) =>
    api.post("/lp-analysis/own/import", data),
  listOwn: (params?: { genre?: string; search?: string }) =>
    api.get("/lp-analysis/own/list", { params }),
  updateOwn: (id: number, data: { label?: string; url?: string; html_content?: string; text_content?: string; version?: number; auto_analyze?: boolean }) =>
    api.put(`/lp-analysis/own/${id}`, data),
  deleteOwn: (id: number) =>
    api.delete(`/lp-analysis/own/${id}`),
  compareOwn: (data: { own_lp_id: number; competitor_lp_ids?: number[]; genre?: string }) =>
    api.post("/lp-analysis/own/compare", data),
};

// Rankings & Search API
export const rankingsApi = {
  getProducts: (params?: { period?: string; genre?: string; platform?: string; page?: number; page_size?: number }) =>
    api.get("/rankings/products", { params }),
  getHitAds: (params?: { genre?: string; limit?: number }) =>
    api.get("/rankings/hit-ads", { params }),
  getAdvertiser: (name: string, period?: string) =>
    api.get(`/rankings/advertiser/${name}`, { params: { period } }),
  getGenreSummary: (period?: string) =>
    api.get("/rankings/genre-summary", { params: { period } }),
  proSearch: (params: { q: string; search_scope?: string; genre?: string; platform?: string; page?: number }) =>
    api.get("/rankings/search", { params }),
  exportRankingsCSV: (params?: { period?: string; genre?: string }) =>
    api.get("/rankings/export/rankings", { params, responseType: "blob" }),
  exportAdsCSV: (params?: { genre?: string; platform?: string; advertiser?: string }) =>
    api.get("/rankings/export/ads", { params, responseType: "blob" }),
};

// Notifications & My List API
export const notificationsApi = {
  createConfig: (data: { channel_type: string; webhook_url?: string; api_token?: string; room_id?: string; notify_new_hit_ads?: boolean; notify_competitor_activity?: boolean; watched_genres?: string[]; watched_advertisers?: string[] }) =>
    api.post("/notifications/config", data),
  listConfigs: () =>
    api.get("/notifications/config"),
  deleteConfig: (id: number) =>
    api.delete(`/notifications/config/${id}`),
  testNotification: (configId: number) =>
    api.post("/notifications/test", null, { params: { config_id: configId } }),
  saveItem: (data: { item_type: string; item_id: number; label?: string; notes?: string; folder?: string }) =>
    api.post("/notifications/saved", data),
  listSaved: (params?: { item_type?: string; folder?: string }) =>
    api.get("/notifications/saved", { params }),
  removeSaved: (id: number) =>
    api.delete(`/notifications/saved/${id}`),
};

// Competitive Intelligence API
export const competitiveApi = {
  // Spend estimation
  estimateSpend: (data: { ad_id: number; view_count_increase: number; platform: string; genre?: string }) =>
    api.post("/competitive/spend/estimate", data),
  saveCPMCalibration: (data: { platform: string; genre?: string; actual_cpm: number; actual_cpv?: number; notes?: string }) =>
    api.post("/competitive/spend/calibrate", data),
  listCalibrations: () =>
    api.get("/competitive/spend/calibrations"),

  // Similarity search
  similaritySearch: (data: { ad_id?: number; query_text?: string; limit?: number; embedding_field?: string; min_similarity?: number }) =>
    api.post("/competitive/similarity/search", data),
  generateEmbedding: (adId: number) =>
    api.post(`/competitive/similarity/generate/${adId}`),

  // Destination analytics
  getLPReuse: (params?: { genre?: string; min_advertisers?: number; limit?: number }) =>
    api.get("/competitive/destination/lp-reuse", { params }),
  getCreativeVariation: (lpId: number) =>
    api.get(`/competitive/destination/creative-variation/${lpId}`),
  getAdvertiserDestinations: (advertiserName: string) =>
    api.get(`/competitive/destination/advertiser-portfolio/${advertiserName}`),
  getGenreDestinationOverview: (genre: string, periodDays?: number) =>
    api.get(`/competitive/destination/genre-overview/${genre}`, { params: { period_days: periodDays } }),

  // Alert detection
  runAlertDetection: (watchedAdvertisers?: string[]) =>
    api.post("/competitive/alerts/detect", watchedAdvertisers),
  getAlertHistory: (params?: { alert_type?: string; severity?: string; days?: number; limit?: number }) =>
    api.get("/competitive/alerts/history", { params }),
  dismissAlert: (alertId: number) =>
    api.post(`/competitive/alerts/${alertId}/dismiss`),

  // Two-stage classification
  getClassificationTags: (adId: number) =>
    api.get(`/competitive/classification/tags/${adId}`),
  createClassificationTag: (data: { ad_id: number; field_name: string; value: string; confidence?: number; classified_by?: string }) =>
    api.post("/competitive/classification/tag", data),
  confirmClassification: (data: { tag_id: number; confirmed_value?: string; confirmed_by?: string }) =>
    api.post("/competitive/classification/confirm", data),
  listProvisionalTags: (limit?: number) =>
    api.get("/competitive/classification/provisional", { params: { limit } }),

  // Trend prediction
  getTrendPredictions: (limit?: number) =>
    api.get("/competitive/trends/predictions", { params: { limit } }),
  getEarlyHitCandidates: (params?: { max_days_active?: number; min_momentum?: number }) =>
    api.get("/competitive/trends/early-hits", { params }),

  // LP Funnels
  listFunnels: (params?: { genre?: string; advertiser?: string; limit?: number }) =>
    api.get("/competitive/funnels", { params }),

  // LP Fingerprinting
  getLPFingerprint: (lpId: number) =>
    api.get(`/competitive/fingerprint/lp/${lpId}`),
  getOfferClusters: (params?: { genre?: string; limit?: number }) =>
    api.get("/competitive/fingerprint/clusters", { params }),
};

// Campaigns API
export const campaignsApi = {
  list: () => api.get("/campaigns"),
  create: (data: { name: string; description?: string }) =>
    api.post("/campaigns", data),
  getDetail: (id: number) => api.get(`/campaigns/${id}`),
  update: (id: number, data: { name?: string; description?: string }) =>
    api.put(`/campaigns/${id}`, data),
  delete: (id: number) => api.delete(`/campaigns/${id}`),
  addAd: (campaignId: number, data: { ad_id: number; notes?: string }) =>
    api.post(`/campaigns/${campaignId}/ads`, data),
  removeAd: (campaignId: number, adId: number) =>
    api.delete(`/campaigns/${campaignId}/ads/${adId}`),
};

// Meta Marketing API
export const metaMarketingApi = {
  // Token
  tokenStatus: () => api.get("/meta-marketing/token-status"),

  // Accounts
  availableAccounts: () => api.get("/meta-marketing/available-accounts"),
  connectAccount: (data: { account_id: string; account_name?: string; business_name?: string; currency?: string; timezone_name?: string }) =>
    api.post("/meta-marketing/accounts/connect", data),
  listAccounts: () => api.get("/meta-marketing/accounts"),
  disconnectAccount: (accountId: string) =>
    api.delete(`/meta-marketing/accounts/${accountId}`),

  // Campaigns (Phase 2)
  listCampaigns: (params?: { account_id?: string; status?: string; page?: number; page_size?: number }) =>
    api.get("/meta-marketing/campaigns", { params }),
  listAdSets: (params?: { account_id?: string; campaign_meta_id?: string; page?: number; page_size?: number }) =>
    api.get("/meta-marketing/ad-sets", { params }),
  listAds: (params?: { account_id?: string; ad_set_meta_id?: string; page?: number; page_size?: number }) =>
    api.get("/meta-marketing/ads", { params }),
  getInsights: (params: { account_id: string; entity_type?: string; entity_id?: string; date_from?: string; date_to?: string; level?: string }) =>
    api.get("/meta-marketing/insights", { params }),
  triggerSync: (accountId: string, data?: { insights_days?: number }) =>
    api.post(`/meta-marketing/accounts/${accountId}/sync`, data),

  // Campaign Management (Phase 3)
  createCampaign: (data: Record<string, unknown>) =>
    api.post("/meta-marketing/campaigns", data),
  updateCampaignStatus: (campaignMetaId: string, data: { status: string }) =>
    api.put(`/meta-marketing/campaigns/${campaignMetaId}/status`, data),
  createAdSet: (data: Record<string, unknown>) =>
    api.post("/meta-marketing/ad-sets", data),
  updateAdSetStatus: (adSetMetaId: string, data: { status: string }) =>
    api.put(`/meta-marketing/ad-sets/${adSetMetaId}/status`, data),
  createAd: (data: Record<string, unknown>) =>
    api.post("/meta-marketing/ads", data),
  updateAdStatus: (adMetaId: string, data: { status: string }) =>
    api.put(`/meta-marketing/ads/${adMetaId}/status`, data),
  createCreative: (data: Record<string, unknown>) =>
    api.post("/meta-marketing/creatives", data),
  uploadImage: (accountId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post(`/meta-marketing/accounts/${accountId}/image-upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  // Creative Analysis (Phase 4)
  analyzeAd: (metaAdId: string) =>
    api.post(`/meta-marketing/ads/${metaAdId}/analyze`),
  getCompetitorComparison: (metaAdId: string, params?: { category?: string }) =>
    api.get(`/meta-marketing/ads/${metaAdId}/competitor-comparison`, { params }),
  getCreativeInsights: (accountId: string) =>
    api.get(`/meta-marketing/accounts/${accountId}/creative-insights`),

  // A/B Testing (Phase 5)
  listExperiments: (params?: { account_id?: string; status?: string }) =>
    api.get("/meta-marketing/ab-tests", { params }),
  createExperiment: (data: Record<string, unknown>) =>
    api.post("/meta-marketing/ab-tests", data),
  getExperiment: (experimentId: number) =>
    api.get(`/meta-marketing/ab-tests/${experimentId}`),
  deployExperiment: (experimentId: number) =>
    api.post(`/meta-marketing/ab-tests/${experimentId}/deploy`),
  updateExperimentMetrics: (experimentId: number) =>
    api.post(`/meta-marketing/ab-tests/${experimentId}/update-metrics`),
  completeExperiment: (experimentId: number) =>
    api.post(`/meta-marketing/ab-tests/${experimentId}/complete`),

  // Optimization (Phase 6)
  listRecommendations: (params?: { account_id?: string; status?: string; severity?: string }) =>
    api.get("/meta-marketing/recommendations", { params }),
  acceptRecommendation: (recommendationId: number) =>
    api.post(`/meta-marketing/recommendations/${recommendationId}/accept`),
  rejectRecommendation: (recommendationId: number) =>
    api.post(`/meta-marketing/recommendations/${recommendationId}/reject`),
  applyRecommendation: (recommendationId: number) =>
    api.post(`/meta-marketing/recommendations/${recommendationId}/apply`),
  getBudgetAllocation: (campaignMetaId: string) =>
    api.get(`/meta-marketing/campaigns/${campaignMetaId}/budget-allocation`),
  getCreativeHealth: (accountId: string) =>
    api.get(`/meta-marketing/accounts/${accountId}/creative-health`),

  // Smart Insights Engine
  getPerformanceSummary: (accountId: string, params?: { days?: number }) =>
    api.get(`/meta-marketing/accounts/${accountId}/performance-summary`, { params }),
  getDailyTrends: (accountId: string, params?: { days?: number; entity_type?: string }) =>
    api.get(`/meta-marketing/accounts/${accountId}/daily-trends`, { params }),
  getCreativePerformance: (accountId: string, params?: { days?: number; sort_by?: string }) =>
    api.get(`/meta-marketing/accounts/${accountId}/creative-performance`, { params }),
  getSmartInsights: (accountId: string) =>
    api.get(`/meta-marketing/accounts/${accountId}/smart-insights`),
};

// Settings API
export const settingsApi = {
  getPlatforms: () => api.get("/settings/api-keys/platforms"),
  listKeys: () => api.get("/settings/api-keys"),
  setKey: (data: { platform: string; key_name: string; key_value: string }) =>
    api.post("/settings/api-keys", data),
  deleteKey: (data: { platform: string; key_name: string }) =>
    api.delete("/settings/api-keys", { data }),
  testKey: (data: { platform: string; key_name: string; key_value: string }) =>
    api.post("/settings/api-keys/test", data),
};

// LP Mirror API
export const lpMirrorApi = {
  getMirror: (snapshotId: number) => fetchApi<LPMirrorInfo>(`/rankings/lp-mirror/${snapshotId}`),
  buildMirror: (snapshotId: number) => fetchApi<{ status: string }>(`/rankings/lp-mirror/${snapshotId}/build`, { method: "POST" }),
  getAssets: (snapshotId: number) => fetchApi<{ assets: LPAssetInfo[] }>(`/rankings/lp-mirror/${snapshotId}/assets`),
  getRedirectChain: (snapshotId: number) => fetchApi<{ chain: LPRedirectStep[] }>(`/rankings/lp-mirror/${snapshotId}/redirect-chain`),
  getSource: (snapshotId: number) => fetchApi<{ html: string }>(`/rankings/lp-mirror/${snapshotId}/source`),
};

export default api;
