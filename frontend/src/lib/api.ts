import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
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
  delete: (id: number) => api.delete(`/ads/${id}`),
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

export default api;
