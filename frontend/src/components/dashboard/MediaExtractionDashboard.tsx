"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

interface ExtractionStatus {
  total_ads: number;
  completed: number;
  pending: number;
  pending_heavy: number;
  dispatched: number;
  failed: number;
  skipped: number;
  completion_rate: number;
  status_breakdown: Record<string, number>;
}

interface ExtractionAd {
  id: number;
  title: string;
  advertiser_name: string;
  creative_type: string;
  status: string;
  has_snapshot: boolean;
  has_image: boolean;
  has_video: boolean;
  has_s3_image: boolean;
  has_s3_thumbnail: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-green-100 text-green-700",
  enriched: "bg-green-100 text-green-700",
  pending: "bg-yellow-100 text-yellow-700",
  pending_heavy: "bg-yellow-100 text-yellow-700",
  dispatched: "bg-blue-100 text-blue-700",
  failed: "bg-red-100 text-red-700",
  skipped: "bg-gray-100 text-gray-500",
};

export default function MediaExtractionDashboard() {
  const [status, setStatus] = useState<ExtractionStatus | null>(null);
  const [ads, setAds] = useState<ExtractionAd[]>([]);
  const [filterStatus, setFilterStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await fetchApi<ExtractionStatus>("/rankings/media-extraction-status");
      setStatus(data);
    } catch {
      /* ignore */
    }
  }, []);

  const fetchAds = useCallback(async () => {
    try {
      const data = await fetchApi<{ ads: ExtractionAd[]; total: number }>("/rankings/media-extraction-ads", {
        params: { status: filterStatus, page: String(page), per_page: "20" },
      });
      setAds(data.ads);
      setTotal(data.total);
    } catch {
      /* ignore */
    }
  }, [filterStatus, page]);

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([fetchStatus(), fetchAds()]).finally(() => setLoading(false));
  }, [fetchStatus, fetchAds]);

  const handleBatchExtract = async () => {
    if (!confirm("pending広告のメディアを一括抽出しますか？")) return;
    setActionLoading("extract");
    setActionResult(null);
    try {
      const result = await fetchApi<{ dispatched: number; errors: number }>("/rankings/batch-extract-media", {
        method: "POST",
        params: { limit: "50" },
      });
      setActionResult(`${result.dispatched}件をディスパッチ / ${result.errors}件エラー`);
      fetchStatus();
      fetchAds();
    } catch (e) {
      setActionResult(`Error: ${String(e)}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRetryFailed = async () => {
    if (!confirm("失敗した抽出を再試行しますか？")) return;
    setActionLoading("retry");
    setActionResult(null);
    try {
      const result = await fetchApi<{ retried: number; errors: number }>("/rankings/retry-failed-media", {
        method: "POST",
        params: { limit: "20" },
      });
      setActionResult(`${result.retried}件を再試行 / ${result.errors}件エラー`);
      fetchStatus();
      fetchAds();
    } catch (e) {
      setActionResult(`Error: ${String(e)}`);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading && !status) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 bg-gray-100 rounded animate-pulse w-48" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-24 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
        <div className="h-64 bg-gray-100 rounded-lg animate-pulse" />
      </div>
    );
  }

  const completionRate = status?.completion_rate ?? 0;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">メディア抽出管理</h2>
          <p className="text-[11px] text-gray-400">Playwright メディア抽出パイプラインの進捗管理</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleBatchExtract}
            disabled={!!actionLoading}
            className="px-3 py-1.5 bg-[#4A7DFF] text-white text-[12px] font-medium rounded-lg hover:bg-[#3a6ae8] disabled:opacity-50 transition-colors"
          >
            {actionLoading === "extract" ? "処理中..." : "一括抽出"}
          </button>
          <button
            onClick={handleRetryFailed}
            disabled={!!actionLoading}
            className="px-3 py-1.5 bg-red-500 text-white text-[12px] font-medium rounded-lg hover:bg-red-600 disabled:opacity-50 transition-colors"
          >
            {actionLoading === "retry" ? "処理中..." : "失敗を再試行"}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto custom-scrollbar p-5 space-y-5">
        {/* Action Result */}
        {actionResult && (
          <div className="px-4 py-2 bg-blue-50 border border-blue-200 rounded-lg text-[12px] text-blue-700">
            {actionResult}
          </div>
        )}

        {/* Summary Cards */}
        {status && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4">
              <p className="text-[11px] text-gray-400 mb-1">抽出完了</p>
              <p className="text-2xl font-bold text-green-600">{status.completed}</p>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4">
              <p className="text-[11px] text-gray-400 mb-1">保留中</p>
              <p className="text-2xl font-bold text-yellow-600">{status.pending + status.pending_heavy}</p>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4">
              <p className="text-[11px] text-gray-400 mb-1">実行中</p>
              <p className="text-2xl font-bold text-blue-600">{status.dispatched}</p>
            </div>
            <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4">
              <p className="text-[11px] text-gray-400 mb-1">失敗</p>
              <p className="text-2xl font-bold text-red-600">{status.failed}</p>
            </div>
          </div>
        )}

        {/* Progress Bar */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[12px] font-medium text-gray-700">全体進捗</span>
            <span className="text-[12px] font-bold text-gray-900">{completionRate}%</span>
          </div>
          <div className="bg-gray-200 rounded-full h-2">
            <div
              className="bg-green-500 rounded-full h-2 transition-all"
              style={{ width: `${Math.min(completionRate, 100)}%` }}
            />
          </div>
        </div>

        {/* Status Filter Tabs */}
        <div className="flex gap-2 flex-wrap">
          {["pending", "pending_heavy", "dispatched", "completed", "enriched", "failed", "skipped"].map((s) => (
            <button
              key={s}
              onClick={() => { setFilterStatus(s); setPage(1); }}
              className={`px-3 py-1 rounded-full text-[11px] font-medium transition-colors ${
                filterStatus === s
                  ? "bg-[#4A7DFF] text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {s} ({status?.status_breakdown?.[s] ?? 0})
            </button>
          ))}
        </div>

        {/* Ads Table */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 overflow-hidden">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="bg-gray-50 text-gray-500">
                <th className="px-3 py-2 text-left font-medium">ID</th>
                <th className="px-3 py-2 text-left font-medium">タイトル</th>
                <th className="px-3 py-2 text-left font-medium">広告主</th>
                <th className="px-3 py-2 text-left font-medium">ステータス</th>
                <th className="px-3 py-2 text-left font-medium">種別</th>
                <th className="px-3 py-2 text-center font-medium">画像</th>
                <th className="px-3 py-2 text-center font-medium">動画</th>
                <th className="px-3 py-2 text-center font-medium">S3</th>
              </tr>
            </thead>
            <tbody>
              {ads.map((ad) => (
                <tr key={ad.id} className="border-t border-gray-50 hover:bg-gray-50">
                  <td className="px-3 py-2 text-gray-500">{ad.id}</td>
                  <td className="px-3 py-2 text-gray-900 max-w-[200px] truncate">{ad.title || "-"}</td>
                  <td className="px-3 py-2 text-gray-600 max-w-[120px] truncate">{ad.advertiser_name || "-"}</td>
                  <td className="px-3 py-2">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${STATUS_COLORS[ad.status] || "bg-gray-100 text-gray-500"}`}>
                      {ad.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-gray-600">{ad.creative_type || "-"}</td>
                  <td className="px-3 py-2 text-center">{ad.has_image ? "O" : "-"}</td>
                  <td className="px-3 py-2 text-center">{ad.has_video ? "O" : "-"}</td>
                  <td className="px-3 py-2 text-center">{ad.has_s3_image ? "O" : "-"}</td>
                </tr>
              ))}
              {ads.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-3 py-8 text-center text-gray-400">
                    該当する広告がありません
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > 20 && (
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-gray-400">{total}件中 {(page - 1) * 20 + 1}-{Math.min(page * 20, total)}件</span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-3 py-1 bg-gray-100 text-gray-600 text-[11px] rounded disabled:opacity-50"
              >
                前へ
              </button>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page * 20 >= total}
                className="px-3 py-1 bg-gray-100 text-gray-600 text-[11px] rounded disabled:opacity-50"
              >
                次へ
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
