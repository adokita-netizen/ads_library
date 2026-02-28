"use client";

import React, { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";

// ─── Types ───

interface CrawlJob {
  job_id?: string;
  id?: string;
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

  // Fetch recent crawl jobs
  const fetchJobs = useCallback(async () => {
    setJobsLoading(true);
    try {
      const data = await fetchApi<{ jobs?: CrawlJob[]; items?: CrawlJob[] } | CrawlJob[]>(
        "/rankings/crawl-status"
      );
      const jobs = Array.isArray(data) ? data : (data.jobs || data.items || []);
      setRecentJobs(jobs.slice(0, 5));
    } catch {
      // Silently fail -- endpoint may not exist yet
      setRecentJobs([]);
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
                return (
                  <div key={job.job_id || job.id || i} className="flex items-center gap-3 py-1.5 border-b border-gray-50 last:border-b-0">
                    <span className="text-[11px] text-gray-700 font-medium truncate max-w-[160px]">
                      {job.query || job.keyword || "-"}
                    </span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${sl.className}`}>
                      {sl.text}
                    </span>
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
    </div>
  );
}
