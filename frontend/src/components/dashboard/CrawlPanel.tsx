"use client";

import React, { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";

// ─── Types ───

interface CrawlJob {
  job_id?: string;
  id?: string;
  job_type?: string;
  job_source?: string;
  query?: string;
  keyword?: string;
  status: string;
  total_ads_found?: number;
  ads_found?: number;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

interface QuickCrawlResponse {
  job_id?: string;
  status?: string;
  message?: string;
  ads_found?: number;
  total_ads_found?: number;
}

interface CrawlDiagnostics {
  summary?: {
    total_jobs?: number;
    success_rate?: number;
    zero_save_completed?: number;
    zero_save_rate_among_completed?: number;
    learned_attempts?: number;
    learned_success_rate?: number;
    platform_expansion_attempts?: number;
    platform_expansion_success_rate?: number;
    learning_entries?: number;
    job_types?: Record<string, number>;
    job_sources?: Record<string, number>;
  };
  zero_save_causes?: Record<string, number>;
  platforms?: Array<{
    platform?: string;
    zero_save_rate?: number;
    failure_rate?: number;
    completed?: number;
  }>;
}

interface CrawlPanelProps {
  onCrawlComplete?: () => void;
}

// ─── Component ───

export default function CrawlPanel({ onCrawlComplete }: CrawlPanelProps) {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(20);
  const [crawling, setCrawling] = useState(false);
  const [crawlResult, setCrawlResult] = useState<QuickCrawlResponse | null>(null);
  const [recentJobs, setRecentJobs] = useState<CrawlJob[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [diagnostics, setDiagnostics] = useState<CrawlDiagnostics | null>(null);

  // Fetch recent crawl jobs
  const fetchJobs = useCallback(async () => {
    setJobsLoading(true);
    try {
      const data = await fetchApi<{ jobs?: CrawlJob[]; items?: CrawlJob[] } | CrawlJob[]>(
        "/rankings/crawl-status"
      );
      const jobs = Array.isArray(data) ? data : (data.jobs || data.items || []);
      setRecentJobs(jobs.slice(0, 5));
      const diag = await fetchApi<CrawlDiagnostics>("/rankings/crawl-status/diagnostics", {
        params: { hours: 24, limit: 200 },
      });
      setDiagnostics(diag);
    } catch {
      // Silently fail -- endpoint may not exist yet
      setRecentJobs([]);
      setDiagnostics(null);
    } finally {
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Trigger crawl
  const handleCrawl = async () => {
    if (!query.trim()) {
      toast.error("検索キーワードを入力してください");
      return;
    }
    setCrawling(true);
    setCrawlResult(null);
    try {
      const res = await fetchApi<QuickCrawlResponse>("/rankings/quick-crawl", {
        method: "POST",
        body: { query: query.trim(), limit },
      });
      setCrawlResult(res);
      const found = res.total_ads_found ?? res.ads_found ?? 0;
      toast.success(`${found}件の広告を取得しました`);
      // Refresh jobs list
      await fetchJobs();
      // Notify parent to refresh data
      if (onCrawlComplete) onCrawlComplete();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "クロールに失敗しました";
      toast.error(msg);
    } finally {
      setCrawling(false);
    }
  };

  const statusLabel = (status: string): { text: string; className: string } => {
    switch (status) {
      case "completed":
      case "done":
        return { text: "完了", className: "bg-emerald-100 text-emerald-700" };
      case "running":
      case "in_progress":
        return { text: "実行中", className: "bg-blue-100 text-blue-700" };
      case "failed":
      case "error":
        return { text: "失敗", className: "bg-red-100 text-red-700" };
      case "queued":
      case "pending":
        return { text: "待機中", className: "bg-yellow-100 text-yellow-700" };
      default:
        return { text: status, className: "bg-gray-100 text-gray-700" };
    }
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return "-";
    try {
      return new Date(dateStr).toLocaleString("ja-JP", {
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const jobTypeLabel = (jobType?: string): { text: string; className: string } | null => {
    switch (jobType) {
      case "quick_crawl":
        return { text: "Quick", className: "bg-indigo-50 text-indigo-700 border border-indigo-200" };
      case "inline":
        return { text: "Inline", className: "bg-orange-50 text-orange-700 border border-orange-200" };
      case "manual":
        return { text: "手動", className: "bg-sky-50 text-sky-700 border border-sky-200" };
      case "scheduled":
        return { text: "定期", className: "bg-slate-100 text-slate-700 border border-slate-200" };
      default:
        return null;
    }
  };

  const jobSourceLabel = (jobSource?: string): string | null => {
    switch (jobSource) {
      case "rankings_quick_crawl":
        return "rankings";
      case "live_ingestion_inline":
        return "live";
      case "ads_inline_fallback":
        return "manual";
      case "crawl_ads_task":
        return "worker";
      default:
        return null;
    }
  };

  const summarizeError = (raw?: string | null): { text: string; className: string } | null => {
    const message = String(raw || "").trim();
    if (!message) return null;

    const normalized = message.toLowerCase();
    if (normalized.includes("timeout")) {
      return { text: "timeout", className: "bg-rose-50 text-rose-700 border border-rose-200" };
    }
    if (normalized.includes("401") || normalized.includes("auth") || normalized.includes("token")) {
      return { text: "auth", className: "bg-amber-50 text-amber-700 border border-amber-200" };
    }
    if (normalized.includes("429") || normalized.includes("rate")) {
      return { text: "rate_limit", className: "bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200" };
    }
    if (normalized.includes("browser") || normalized.includes("chromium") || normalized.includes("playwright")) {
      return { text: "browser", className: "bg-violet-50 text-violet-700 border border-violet-200" };
    }
    if (normalized.includes("network") || normalized.includes("connect") || normalized.includes("dns")) {
      return { text: "network", className: "bg-cyan-50 text-cyan-700 border border-cyan-200" };
    }
    return { text: "error", className: "bg-gray-100 text-gray-700 border border-gray-200" };
  };

  return (
    <div className="card px-4 py-4">
      <div className="flex items-center gap-2 mb-3">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM10.5 7.5v6m3-3h-6" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">新規クロール</h3>
        <span className="text-[10px] text-gray-400">キーワードで広告をクロール</span>
      </div>

      {/* Crawl form */}
      <div className="flex items-end gap-2 flex-wrap">
        <div className="flex-1 min-w-[180px]">
          <label className="text-[10px] text-gray-400 font-medium mb-1 block">検索キーワード</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !crawling) handleCrawl(); }}
            placeholder="例: 美容液、ダイエットサプリ、英語学習"
            className="w-full h-9 px-3 text-[12px] rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF] transition-colors placeholder:text-gray-300"
            disabled={crawling}
          />
        </div>
        <div className="w-20">
          <label className="text-[10px] text-gray-400 font-medium mb-1 block">取得上限</label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="w-full h-9 px-2 text-[12px] rounded-lg border border-gray-200 bg-white focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF] transition-colors"
            disabled={crawling}
          >
            <option value={10}>10件</option>
            <option value={20}>20件</option>
            <option value={50}>50件</option>
            <option value={100}>100件</option>
          </select>
        </div>
        <button
          onClick={handleCrawl}
          disabled={crawling || !query.trim()}
          className="h-9 px-4 rounded-lg text-[12px] font-medium text-white bg-[#4A7DFF] hover:bg-[#3a6de6] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5 whitespace-nowrap"
        >
          {crawling ? (
            <>
              <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              クロール中...
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              クロール実行
            </>
          )}
        </button>
      </div>

      {/* Crawl result */}
      {crawlResult && (
        <div className="mt-3 px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-emerald-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-[12px] text-emerald-700 font-medium">
              {crawlResult.total_ads_found ?? crawlResult.ads_found ?? 0}件の新しい広告を取得しました
            </span>
          </div>
        </div>
      )}

      {/* Recent crawl history */}
      {(recentJobs.length > 0 || jobsLoading) && (
        <div className="mt-4">
          <p className="text-[10px] text-gray-400 font-medium mb-2">最近のクロール</p>
          {jobsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="animate-pulse flex items-center gap-3 py-1.5">
                  <div className="h-3 bg-gray-200 rounded w-24" />
                  <div className="h-3 bg-gray-100 rounded w-12" />
                  <div className="h-3 bg-gray-100 rounded w-16 ml-auto" />
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {recentJobs.map((job, i) => {
                const sl = statusLabel(job.status);
                const jt = jobTypeLabel(job.job_type);
                const sourceLabel = jobSourceLabel(job.job_source);
                const errorSummary = summarizeError(job.error_message);
                return (
                  <div key={job.job_id || job.id || i} className="flex items-center gap-3 py-1.5 border-b border-gray-50 last:border-b-0">
                    <div className="min-w-0 flex items-center gap-1.5">
                      <span className="text-[11px] text-gray-700 font-medium truncate max-w-[140px]">
                        {job.query || job.keyword || "-"}
                      </span>
                      {jt && (
                        <span className={`shrink-0 text-[9px] px-1.5 py-0.5 rounded font-semibold ${jt.className}`}>
                          {jt.text}
                        </span>
                      )}
                      {sourceLabel && (
                        <span className="shrink-0 text-[9px] px-1.5 py-0.5 rounded bg-gray-50 text-gray-500 border border-gray-200">
                          {sourceLabel}
                        </span>
                      )}
                    </div>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${sl.className}`}>
                      {sl.text}
                    </span>
                    {job.status === "failed" && errorSummary && (
                      <span
                        className={`shrink-0 text-[9px] px-1.5 py-0.5 rounded font-medium ${errorSummary.className}`}
                        title={job.error_message || undefined}
                      >
                        {errorSummary.text}
                      </span>
                    )}
                    {(job.total_ads_found != null || job.ads_found != null) && (
                      <span className="text-[10px] text-gray-500">
                        {job.total_ads_found ?? job.ads_found}件
                      </span>
                    )}
                    <span className="text-[10px] text-gray-400 ml-auto">
                      {formatDate(job.completed_at || job.created_at || job.started_at)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {diagnostics?.summary && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
          <p className="text-[10px] font-semibold text-amber-800">クロール健全性 (24h)</p>
          <p className="text-[11px] text-amber-700 mt-0.5">
            成功率 {(Number(diagnostics.summary.success_rate || 0) * 100).toFixed(1)}% / 保存0件率{" "}
            {(Number(diagnostics.summary.zero_save_rate_among_completed || 0) * 100).toFixed(1)}%
          </p>
          <p className="text-[10px] text-amber-700 mt-0.5">
            学習クエリ: {Number(diagnostics.summary.learned_attempts || 0)}回 / 成功率{" "}
            {(Number(diagnostics.summary.learned_success_rate || 0) * 100).toFixed(1)}%
          </p>
          <p className="text-[10px] text-amber-700 mt-0.5">
            媒体拡張: {Number(diagnostics.summary.platform_expansion_attempts || 0)}回 / 成功率{" "}
            {(Number(diagnostics.summary.platform_expansion_success_rate || 0) * 100).toFixed(1)}%
          </p>
          <p className="text-[10px] text-amber-700 mt-0.5">
            学習辞書エントリ: {Number(diagnostics.summary.learning_entries || 0)} 件
          </p>
          {diagnostics.summary.job_types && Object.keys(diagnostics.summary.job_types).length > 0 && (
            <p className="text-[10px] text-amber-700 mt-0.5">
              経路内訳: {Object.entries(diagnostics.summary.job_types)
                .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
                .map(([key, count]) => `${jobTypeLabel(key)?.text || key}:${count}`)
                .join(" / ")}
            </p>
          )}
          {diagnostics.zero_save_causes && Object.keys(diagnostics.zero_save_causes).length > 0 && (
            <p className="text-[10px] text-amber-700 mt-0.5">
              主因: {Object.entries(diagnostics.zero_save_causes).sort((a, b) => b[1] - a[1])[0][0]}
            </p>
          )}
          {diagnostics.platforms && diagnostics.platforms.length > 0 && (
            <p className="text-[10px] text-amber-700 mt-0.5">
              要注意媒体: {diagnostics.platforms
                .filter((p) => Number(p.completed || 0) > 0)
                .sort((a, b) => Number(b.zero_save_rate || 0) - Number(a.zero_save_rate || 0))[0]?.platform || "n/a"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
