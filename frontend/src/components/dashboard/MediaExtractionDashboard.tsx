"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { EmptyState, ErrorState, SkeletonCards, SkeletonRows } from "@/components/common/StateDisplay";

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

interface ExtractionProgress {
  total_ads: number;
  coverage: {
    image: number;
    image_rate: number;
    thumbnail: number;
    thumbnail_rate: number;
    video: number;
  };
  pending_extraction: number;
  recent_extractions_24h: number;
  status_breakdown: Record<string, number>;
  type_breakdown: Record<string, number>;
  auto_schedule: string;
}

interface ExtractionAd {
  id: number;
  title: string;
  advertiser_name: string;
  creative_type: string;
  status: string;
  platform: string;
  genre: string;
  topic_label: string;
  matched_terms: string[];
  has_snapshot: boolean;
  has_image: boolean;
  has_video: boolean;
  has_s3_image: boolean;
  has_s3_thumbnail: boolean;
  needs_media_retry: boolean;
  extract_quality_score: number;
  updated_at: string | null;
}

interface ExtractionDetail {
  ad_id: number;
  creative_urls: {
    thumbnail?: string;
    image?: string;
    video?: string;
    snapshot?: string;
  };
  text_fields: {
    title?: string;
    description?: string;
    ocr?: string[];
    transcript?: string;
  };
  extract_source: string;
  quality_score: number;
  missing_fields: string[];
}

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  enriched: "bg-emerald-100 text-emerald-700",
  pending: "bg-amber-100 text-amber-700",
  pending_heavy: "bg-orange-100 text-orange-700",
  dispatched: "bg-blue-100 text-blue-700",
  failed: "bg-rose-100 text-rose-700",
  skipped: "bg-gray-100 text-gray-500",
};

const QUICK_TAGS = ["GLP-1", "AGA", "脱毛", "クレカ", "不動産"];
const STATUS_ORDER = ["pending", "pending_heavy", "dispatched", "failed", "completed", "enriched", "skipped"];

function formatDateTime(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("ja-JP", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function qualityTone(score: number): string {
  if (score >= 80) return "bg-emerald-100 text-emerald-700";
  if (score >= 50) return "bg-amber-100 text-amber-700";
  return "bg-rose-100 text-rose-700";
}

function qualityLabel(score: number): string {
  if (score >= 80) return "良好";
  if (score >= 50) return "注意";
  return "要再抽出";
}

function mediaSummary(ad: ExtractionAd): string {
  const parts = [];
  if (ad.has_video) parts.push("動画");
  if (ad.has_image) parts.push("画像");
  if (ad.has_snapshot) parts.push("スナップ");
  return parts.length > 0 ? parts.join(" / ") : "未取得";
}

export default function MediaExtractionDashboard() {
  const [status, setStatus] = useState<ExtractionStatus | null>(null);
  const [ads, setAds] = useState<ExtractionAd[]>([]);
  const [filterStatus, setFilterStatus] = useState("pending");
  const [searchInput, setSearchInput] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [topicFilter, setTopicFilter] = useState("");
  const [retryOnly, setRetryOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tableLoading, setTableLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [selectedAdId, setSelectedAdId] = useState<number | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<ExtractionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ExtractionProgress | null>(null);
  const [autoExtractRunning, setAutoExtractRunning] = useState(false);

  const selectedAd = useMemo(
    () => ads.find((ad) => ad.id === selectedAdId) ?? ads[0] ?? null,
    [ads, selectedAdId],
  );

  const retryCandidateCount = useMemo(
    () => ads.filter((ad) => ad.needs_media_retry).length,
    [ads],
  );

  useEffect(() => {
    if (!selectedAd) {
      setSelectedDetail(null);
      setDetailError(null);
      return;
    }

    let cancelled = false;
    const loadDetail = async () => {
      setDetailLoading(true);
      setDetailError(null);
      try {
        const data = await fetchApi<ExtractionDetail>(`/rankings/meta-extraction/${selectedAd.id}`);
        if (!cancelled) {
          setSelectedDetail(data);
        }
      } catch (error) {
        if (!cancelled) {
          setSelectedDetail(null);
          setDetailError(error instanceof Error ? error.message : "詳細の取得に失敗しました");
        }
      } finally {
        if (!cancelled) {
          setDetailLoading(false);
        }
      }
    };

    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [selectedAd]);

  const fetchStatus = useCallback(async () => {
    const data = await fetchApi<ExtractionStatus>("/rankings/media-extraction-status");
    setStatus(data);
  }, []);

  const fetchAds = useCallback(async (showSkeleton = false) => {
    if (showSkeleton) {
      setTableLoading(true);
    }
    const data = await fetchApi<{ ads: ExtractionAd[]; total: number }>("/rankings/media-extraction-ads", {
      params: {
        status: filterStatus,
        page,
        per_page: 20,
        q: appliedQuery || undefined,
        topic: topicFilter || undefined,
        needs_retry: retryOnly ? "true" : undefined,
      },
    });
    setAds(data.ads);
    setTotal(data.total);
    setLastSyncedAt(new Date().toISOString());
    setSelectedAdId((current) => {
      if (data.ads.length === 0) return null;
      if (current && data.ads.some((ad) => ad.id === current)) return current;
      return data.ads[0].id;
    });
    if (showSkeleton) {
      setTableLoading(false);
    }
  }, [appliedQuery, filterStatus, page, retryOnly, topicFilter]);

  const refreshAll = useCallback(async (showSkeleton = false) => {
    try {
      setLoadError(null);
      if (!status) {
        setLoading(true);
      }
      await Promise.all([fetchStatus(), fetchAds(showSkeleton)]);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "データの取得に失敗しました");
    } finally {
      setLoading(false);
      setTableLoading(false);
    }
  }, [fetchAds, fetchStatus, status]);

  const fetchProgress = useCallback(async () => {
    try {
      const data = await fetchApi<ExtractionProgress>("/media/extraction-progress");
      setProgress(data);
    } catch {
      // Silently fail — progress is supplementary
    }
  }, []);

  const handleAutoExtract = async (limit = 50) => {
    setAutoExtractRunning(true);
    try {
      const result = await fetchApi<{ status: string; message: string; pending_count: number }>(
        "/media/auto-extract",
        { method: "POST", body: { limit, use_playwright: true } },
      );
      if (result.status === "no_pending") {
        toast.success("全広告のCR取得済みです");
      } else {
        toast.success(`自動CR抽出を開始: ${result.pending_count}件が対象`);
      }
      // Refresh progress after short delay
      setTimeout(() => { void fetchProgress(); }, 2000);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "自動CR抽出に失敗しました");
    } finally {
      setAutoExtractRunning(false);
    }
  };

  useEffect(() => {
    void refreshAll(!loading);
    void fetchProgress();
  }, [refreshAll, fetchProgress]);

  // Poll progress every 30s
  useEffect(() => {
    const interval = setInterval(() => { void fetchProgress(); }, 30000);
    return () => clearInterval(interval);
  }, [fetchProgress]);

  useEffect(() => {
    setPage(1);
  }, [filterStatus, appliedQuery, topicFilter, retryOnly]);

  const handleSearchApply = () => {
    setAppliedQuery(searchInput.trim());
  };

  const handleQuickTag = (tag: string) => {
    setTopicFilter((current) => (current === tag ? "" : tag));
    setSearchInput((current) => (current && current !== tag ? current : ""));
    setAppliedQuery("");
  };

  const handleBatchExtract = async () => {
    if (!confirm("保留中広告と再抽出候補を一括投入しますか？")) return;
    setActionLoading("batch");
    try {
      const result = await fetchApi<{ dispatched: number; errors: number; retry_candidates_dispatched?: number }>(
        "/rankings/batch-extract-media",
        { method: "POST", params: { limit: 50 } },
      );
      toast.success(`投入 ${result.dispatched}件 / 再抽出候補 ${result.retry_candidates_dispatched ?? 0}件`);
      await refreshAll(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "一括投入に失敗しました");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRetryFailed = async () => {
    if (!confirm("failed 状態の広告を再試行しますか？")) return;
    setActionLoading("failed");
    try {
      const result = await fetchApi<{ retried: number; errors: number }>("/rankings/retry-failed-media", {
        method: "POST",
        params: { limit: 20 },
      });
      toast.success(`failed 再試行 ${result.retried}件 / エラー ${result.errors}件`);
      await refreshAll(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "failed 再試行に失敗しました");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRetryAd = async (adId: number) => {
    setActionLoading(`retry-${adId}`);
    try {
      const result = await fetchApi<{ dispatched: boolean; failure_reason_code?: string }>(`/rankings/meta-extraction/${adId}/retry`, {
        method: "POST",
      });
      if (result.dispatched) {
        toast.success(`広告 ${adId} を再抽出キューに投入しました`);
      } else {
        toast.error(`広告 ${adId} の再抽出に失敗しました: ${result.failure_reason_code || "dispatch_error"}`);
      }
      await refreshAll(true);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "個別再抽出に失敗しました");
    } finally {
      setActionLoading(null);
    }
  };

  const evidenceBadges = (ad: ExtractionAd, detail: ExtractionDetail | null) => {
    const badges: { label: string; tone: string }[] = [];
    if (ad.extract_quality_score < 50) {
      badges.push({ label: "低品質", tone: "bg-rose-100 text-rose-700" });
    }
    if (!ad.has_image && !ad.has_video && ad.has_snapshot) {
      badges.push({ label: "サムネのみ", tone: "bg-amber-100 text-amber-700" });
    }
    if (ad.creative_type?.toLowerCase().includes("video") && !ad.has_video) {
      badges.push({ label: "動画未取得", tone: "bg-orange-100 text-orange-700" });
    }
    if (detail?.missing_fields?.includes("creative_urls")) {
      badges.push({ label: "URL欠損", tone: "bg-gray-100 text-gray-700" });
    }
    return badges;
  };

  if (loading && !status) {
    return (
      <div className="p-5 space-y-4">
        <SkeletonCards count={4} />
        <div className="grid grid-cols-1 xl:grid-cols-[1.4fr_0.8fr] gap-4">
          <div className="rounded-2xl border border-gray-200 bg-white p-4">
            <table className="w-full text-[12px]">
              <tbody>
                <SkeletonRows rows={8} cols={7} />
              </tbody>
            </table>
          </div>
          <div className="rounded-2xl border border-gray-200 bg-white p-4">
            <div className="h-5 w-1/3 rounded bg-gray-200 animate-pulse mb-3" />
            <div className="space-y-3">
              <div className="h-16 rounded bg-gray-100 animate-pulse" />
              <div className="h-24 rounded bg-gray-100 animate-pulse" />
              <div className="h-32 rounded bg-gray-100 animate-pulse" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#F7F8FC]">
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">メディア抽出管理</h2>
          <p className="text-[11px] text-gray-500">検索 / フィルタ / 一覧 / 詳細の4ブロックで再抽出運用を整理</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { void handleAutoExtract(50); }}
            disabled={autoExtractRunning || !!actionLoading}
            className="px-3 py-2 rounded-xl bg-emerald-600 text-white text-[12px] font-semibold hover:bg-emerald-700 disabled:opacity-50"
          >
            {autoExtractRunning ? "抽出中..." : "自動CR抽出"}
          </button>
          <button
            onClick={handleBatchExtract}
            disabled={!!actionLoading}
            className="px-3 py-2 rounded-xl bg-[#4A7DFF] text-white text-[12px] font-semibold hover:bg-[#3a6ae8] disabled:opacity-50"
          >
            {actionLoading === "batch" ? "投入中..." : "再抽出候補を一括投入"}
          </button>
          <button
            onClick={handleRetryFailed}
            disabled={!!actionLoading}
            className="px-3 py-2 rounded-xl bg-white border border-rose-200 text-rose-600 text-[12px] font-semibold hover:bg-rose-50 disabled:opacity-50"
          >
            {actionLoading === "failed" ? "再試行中..." : "failed を再試行"}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto custom-scrollbar p-5 space-y-4">
        {loadError && <ErrorState compact message={loadError} onRetry={() => { void refreshAll(true); }} />}

        {status && (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="rounded-2xl border border-emerald-100 bg-white p-4">
              <p className="text-[11px] text-gray-500 mb-1">抽出完了</p>
              <p className="text-2xl font-bold text-emerald-600">{status.completed}</p>
              <p className="text-[11px] text-gray-400 mt-1">進捗 {status.completion_rate}%</p>
            </div>
            <div className="rounded-2xl border border-amber-100 bg-white p-4">
              <p className="text-[11px] text-gray-500 mb-1">保留中</p>
              <p className="text-2xl font-bold text-amber-600">{status.pending + status.pending_heavy}</p>
              <p className="text-[11px] text-gray-400 mt-1">heavy {status.pending_heavy}件を含む</p>
            </div>
            <div className="rounded-2xl border border-blue-100 bg-white p-4">
              <p className="text-[11px] text-gray-500 mb-1">実行中</p>
              <p className="text-2xl font-bold text-blue-600">{status.dispatched}</p>
              <p className="text-[11px] text-gray-400 mt-1">キュー投入済み</p>
            </div>
            <div className="rounded-2xl border border-rose-100 bg-white p-4">
              <p className="text-[11px] text-gray-500 mb-1">失敗</p>
              <p className="text-2xl font-bold text-rose-600">{status.failed}</p>
              <p className="text-[11px] text-gray-400 mt-1">一覧内の要再抽出 {retryCandidateCount}件</p>
            </div>
          </div>
        )}

        {progress && (
          <div className="rounded-2xl border border-indigo-100 bg-white p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-[13px] font-semibold text-gray-900">CR取得カバレッジ</h3>
                <p className="text-[11px] text-gray-500">
                  自動スケジュール: {progress.auto_schedule} / 直近24h: {progress.recent_extractions_24h}件抽出
                </p>
              </div>
              {progress.pending_extraction > 0 && (
                <span className="px-3 py-1.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-700">
                  未抽出 {progress.pending_extraction}件
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-gray-600">静止画</span>
                  <span className="text-[11px] font-semibold text-gray-900">{progress.coverage.image}/{progress.total_ads} ({progress.coverage.image_rate}%)</span>
                </div>
                <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
                  <div className="h-full bg-blue-500 transition-all" style={{ width: `${progress.coverage.image_rate}%` }} />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-gray-600">サムネイル</span>
                  <span className="text-[11px] font-semibold text-gray-900">{progress.coverage.thumbnail}/{progress.total_ads} ({progress.coverage.thumbnail_rate}%)</span>
                </div>
                <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
                  <div className="h-full bg-emerald-500 transition-all" style={{ width: `${progress.coverage.thumbnail_rate}%` }} />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-gray-600">動画</span>
                  <span className="text-[11px] font-semibold text-gray-900">{progress.coverage.video}件</span>
                </div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {Object.entries(progress.type_breakdown).map(([type, count]) => (
                    <span key={type} className="px-2 py-0.5 rounded-full bg-gray-100 text-[10px] text-gray-600">
                      {type}: {count}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <div className="flex flex-col lg:flex-row lg:items-end gap-3">
            <div className="flex-1">
              <label className="text-[11px] font-medium text-gray-600">検索</label>
              <div className="mt-1 flex gap-2">
                <input
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSearchApply();
                  }}
                  placeholder="タイトル / 広告主 / 個別ワード 例: GLP-1 / マンジャロ / ピラティス"
                  className="w-full rounded-xl border border-gray-200 px-3 py-2 text-[12px] focus:border-[#4A7DFF] focus:outline-none"
                />
                <button
                  onClick={handleSearchApply}
                  className="px-4 py-2 rounded-xl bg-gray-900 text-white text-[12px] font-medium hover:bg-gray-800"
                >
                  適用
                </button>
              </div>
            </div>
            <div className="lg:w-56">
              <label className="text-[11px] font-medium text-gray-600">更新状況</label>
              <div className="mt-1 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-[12px] text-gray-600">
                {total}件表示 / 更新 {formatDateTime(lastSyncedAt)}
              </div>
            </div>
          </div>

          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap gap-2">
              {STATUS_ORDER.map((key) => (
                <button
                  key={key}
                  onClick={() => setFilterStatus(key)}
                  className={`px-3 py-1.5 rounded-full text-[11px] font-semibold transition-colors ${
                    filterStatus === key ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {key} ({status?.status_breakdown?.[key] ?? 0})
                </button>
              ))}
            </div>

            <div className="flex flex-wrap gap-2 items-center">
              {QUICK_TAGS.map((tag) => (
                <button
                  key={tag}
                  onClick={() => handleQuickTag(tag)}
                  className={`px-3 py-1.5 rounded-full text-[11px] font-medium border transition-colors ${
                    topicFilter === tag
                      ? "border-[#4A7DFF] bg-[#EEF3FF] text-[#2E5BDB]"
                      : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
                  }`}
                >
                  {tag}
                </button>
              ))}
              <label className="ml-auto inline-flex items-center gap-2 text-[12px] text-gray-600">
                <input
                  type="checkbox"
                  checked={retryOnly}
                  onChange={(e) => setRetryOnly(e.target.checked)}
                  className="rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]"
                />
                needs_media_retry のみ
              </label>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-[1.5fr_0.9fr] gap-4">
          <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <div>
                <h3 className="text-[13px] font-semibold text-gray-900">一覧</h3>
                <p className="text-[11px] text-gray-500">媒体 / ジャンル / 取得品質 / 更新日 を優先表示</p>
              </div>
              <button
                onClick={() => { void refreshAll(true); }}
                className="text-[11px] font-medium text-[#4A7DFF] hover:text-[#2E5BDB]"
              >
                再読み込み
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="bg-gray-50 text-gray-500">
                    <th className="px-3 py-2 text-left font-medium">広告</th>
                    <th className="px-3 py-2 text-left font-medium">媒体 / ジャンル</th>
                    <th className="px-3 py-2 text-left font-medium">トピック</th>
                    <th className="px-3 py-2 text-left font-medium">取得品質</th>
                    <th className="px-3 py-2 text-left font-medium">更新</th>
                    <th className="px-3 py-2 text-left font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {tableLoading ? (
                    <SkeletonRows rows={8} cols={6} />
                  ) : ads.length === 0 ? (
                    <tr>
                      <td colSpan={6}>
                        <EmptyState
                          icon="search"
                          message="該当する広告がありません"
                          description="検索語・トピック・再抽出条件を調整してください"
                        />
                      </td>
                    </tr>
                  ) : (
                    ads.map((ad) => (
                      <tr
                        key={ad.id}
                        onClick={() => setSelectedAdId(ad.id)}
                        className={`border-t border-gray-100 cursor-pointer transition-colors ${
                          selectedAd?.id === ad.id ? "bg-[#F3F7FF]" : "hover:bg-gray-50"
                        }`}
                      >
                        <td className="px-3 py-3 align-top">
                          <div className="space-y-1">
                            <p className="font-medium text-gray-900 line-clamp-2">{ad.title || "-"}</p>
                            <p className="text-[11px] text-gray-500">{ad.advertiser_name || "-"}</p>
                            <div className="flex flex-wrap gap-1">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${STATUS_COLORS[ad.status] || "bg-gray-100 text-gray-500"}`}>
                                {ad.status}
                              </span>
                              {ad.needs_media_retry && (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-700">
                                  再抽出推奨
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-3 align-top text-gray-600">
                          <p>{ad.platform || "-"}</p>
                          <p className="mt-1 text-[11px] text-gray-500">{ad.genre || "-"}</p>
                          <p className="mt-1 text-[11px] text-gray-400">{mediaSummary(ad)}</p>
                        </td>
                        <td className="px-3 py-3 align-top">
                          <p className="font-medium text-gray-800">{ad.topic_label || "-"}</p>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {ad.matched_terms.slice(0, 3).map((term) => (
                              <span key={`${ad.id}-${term}`} className="px-2 py-0.5 rounded-full bg-gray-100 text-[10px] text-gray-600">
                                {term}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-3 py-3 align-top">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${qualityTone(ad.extract_quality_score)}`}>
                              {qualityLabel(ad.extract_quality_score)}
                            </span>
                            <span className="text-gray-700">{ad.extract_quality_score}</span>
                          </div>
                        </td>
                        <td className="px-3 py-3 align-top text-gray-600">
                          {formatDateTime(ad.updated_at)}
                        </td>
                        <td className="px-3 py-3 align-top">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              void handleRetryAd(ad.id);
                            }}
                            disabled={!!actionLoading}
                            className="px-3 py-1.5 rounded-lg border border-gray-200 text-[11px] font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                          >
                            {actionLoading === `retry-${ad.id}` ? "処理中..." : "再抽出"}
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {total > 20 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
                <span className="text-[11px] text-gray-500">
                  {total}件中 {(page - 1) * 20 + 1}-{Math.min(page * 20, total)}件
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    disabled={page === 1}
                    className="px-3 py-1.5 rounded-lg bg-gray-100 text-[11px] text-gray-700 disabled:opacity-50"
                  >
                    前へ
                  </button>
                  <button
                    onClick={() => setPage((current) => current + 1)}
                    disabled={page * 20 >= total}
                    className="px-3 py-1.5 rounded-lg bg-gray-100 text-[11px] text-gray-700 disabled:opacity-50"
                  >
                    次へ
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-4">
            <div className="mb-3">
              <h3 className="text-[13px] font-semibold text-gray-900">詳細</h3>
              <p className="text-[11px] text-gray-500">再抽出判断に必要な要素だけを集約表示</p>
            </div>

            {!selectedAd ? (
              <EmptyState
                icon="document"
                message="広告を選択してください"
                description="一覧から1件選ぶと再抽出要否と取得状況を確認できます"
              />
            ) : (
              <div className="space-y-4">
                <div>
                  <p className="text-[11px] text-gray-500">選択中広告</p>
                  <h4 className="mt-1 text-[15px] font-semibold text-gray-900">{selectedAd.title || "-"}</h4>
                  <p className="mt-1 text-[12px] text-gray-500">{selectedAd.advertiser_name || "-"}</p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl bg-gray-50 p-3">
                    <p className="text-[11px] text-gray-500">媒体</p>
                    <p className="mt-1 text-[13px] font-semibold text-gray-900">{selectedAd.platform || "-"}</p>
                  </div>
                  <div className="rounded-xl bg-gray-50 p-3">
                    <p className="text-[11px] text-gray-500">ジャンル</p>
                    <p className="mt-1 text-[13px] font-semibold text-gray-900">{selectedAd.genre || "-"}</p>
                  </div>
                  <div className="rounded-xl bg-gray-50 p-3">
                    <p className="text-[11px] text-gray-500">トピック</p>
                    <p className="mt-1 text-[13px] font-semibold text-gray-900">{selectedAd.topic_label || "-"}</p>
                  </div>
                  <div className="rounded-xl bg-gray-50 p-3">
                    <p className="text-[11px] text-gray-500">更新</p>
                    <p className="mt-1 text-[13px] font-semibold text-gray-900">{formatDateTime(selectedAd.updated_at)}</p>
                  </div>
                </div>

                <div className="rounded-2xl border border-gray-100 bg-[#FBFCFF] p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] font-medium text-gray-700">取得品質</span>
                    <span className={`px-2 py-1 rounded-full text-[10px] font-semibold ${qualityTone(selectedAd.extract_quality_score)}`}>
                      {qualityLabel(selectedAd.extract_quality_score)}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-200 overflow-hidden">
                    <div
                      className={`h-full ${
                        selectedAd.extract_quality_score >= 80
                          ? "bg-emerald-500"
                          : selectedAd.extract_quality_score >= 50
                            ? "bg-amber-500"
                            : "bg-rose-500"
                      }`}
                      style={{ width: `${Math.max(4, Math.min(selectedAd.extract_quality_score, 100))}%` }}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2 text-[11px] text-gray-600">
                    <span className={`px-2 py-1 rounded-full ${selectedAd.has_video ? "bg-blue-50 text-blue-700" : "bg-gray-100 text-gray-500"}`}>動画 {selectedAd.has_video ? "あり" : "なし"}</span>
                    <span className={`px-2 py-1 rounded-full ${selectedAd.has_image ? "bg-blue-50 text-blue-700" : "bg-gray-100 text-gray-500"}`}>画像 {selectedAd.has_image ? "あり" : "なし"}</span>
                    <span className={`px-2 py-1 rounded-full ${selectedAd.has_snapshot ? "bg-blue-50 text-blue-700" : "bg-gray-100 text-gray-500"}`}>スナップ {selectedAd.has_snapshot ? "あり" : "なし"}</span>
                    <span className={`px-2 py-1 rounded-full ${selectedAd.has_s3_image || selectedAd.has_s3_thumbnail ? "bg-indigo-50 text-indigo-700" : "bg-gray-100 text-gray-500"}`}>S3 {selectedAd.has_s3_image || selectedAd.has_s3_thumbnail ? "あり" : "なし"}</span>
                  </div>
                </div>

                <div>
                  <p className="text-[11px] text-gray-500 mb-2">品質バッジ</p>
                  <div className="flex flex-wrap gap-2">
                    {evidenceBadges(selectedAd, selectedDetail).map((badge) => (
                      <span key={badge.label} className={`px-2 py-1 rounded-full text-[11px] font-medium ${badge.tone}`}>
                        {badge.label}
                      </span>
                    ))}
                    {evidenceBadges(selectedAd, selectedDetail).length === 0 && (
                      <span className="text-[12px] text-gray-400">追加警告なし</span>
                    )}
                  </div>
                </div>

                <div>
                  <p className="text-[11px] text-gray-500 mb-2">一致語</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedAd.matched_terms.length > 0 ? selectedAd.matched_terms.map((term) => (
                      <span key={`${selectedAd.id}-${term}`} className="px-2 py-1 rounded-full bg-gray-100 text-[11px] text-gray-600">
                        {term}
                      </span>
                    )) : (
                      <span className="text-[12px] text-gray-400">一致語なし</span>
                    )}
                  </div>
                </div>

                <div className="rounded-2xl border border-gray-100 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-[12px] font-semibold text-gray-900">抽出品質コンソール</p>
                    {detailLoading && <span className="text-[11px] text-gray-400">読込中...</span>}
                  </div>

                  {detailError && (
                    <div className="rounded-lg bg-rose-50 px-3 py-2 text-[11px] text-rose-600">
                      {detailError}
                    </div>
                  )}

                  {selectedDetail && (
                    <>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-xl bg-gray-50 p-3">
                          <p className="text-[11px] text-gray-500">品質スコア</p>
                          <p className="mt-1 text-[13px] font-semibold text-gray-900">{selectedDetail.quality_score}</p>
                        </div>
                        <div className="rounded-xl bg-gray-50 p-3">
                          <p className="text-[11px] text-gray-500">抽出ソース</p>
                          <p className="mt-1 text-[13px] font-semibold text-gray-900 break-all">{selectedDetail.extract_source || "-"}</p>
                        </div>
                      </div>

                      <div>
                        <p className="text-[11px] text-gray-500 mb-2">欠損項目</p>
                        <div className="flex flex-wrap gap-2">
                          {selectedDetail.missing_fields.length > 0 ? selectedDetail.missing_fields.map((field) => (
                            <span key={field} className="px-2 py-1 rounded-full bg-rose-50 text-[11px] text-rose-700">
                              {field}
                            </span>
                          )) : (
                            <span className="text-[12px] text-gray-400">欠損なし</span>
                          )}
                        </div>
                      </div>

                      <div>
                        <p className="text-[11px] text-gray-500 mb-2">取得状態</p>
                        <div className="grid grid-cols-3 gap-2 text-[11px]">
                          <div className={`rounded-lg px-3 py-2 ${selectedDetail.creative_urls.image ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>画像 {selectedDetail.creative_urls.image ? "取得済み" : "欠損"}</div>
                          <div className={`rounded-lg px-3 py-2 ${selectedDetail.creative_urls.video ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>動画 {selectedDetail.creative_urls.video ? "取得済み" : "欠損"}</div>
                          <div className={`rounded-lg px-3 py-2 ${selectedDetail.text_fields.description || selectedDetail.text_fields.transcript ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>本文 {selectedDetail.text_fields.description || selectedDetail.text_fields.transcript ? "取得済み" : "欠損"}</div>
                        </div>
                      </div>

                      <div>
                        <p className="text-[11px] text-gray-500 mb-2">証拠URL</p>
                        <div className="space-y-2">
                          {[
                            ["thumbnail", selectedDetail.creative_urls.thumbnail],
                            ["image", selectedDetail.creative_urls.image],
                            ["video", selectedDetail.creative_urls.video],
                            ["snapshot", selectedDetail.creative_urls.snapshot],
                          ].map(([label, value]) => (
                            <div key={label} className="rounded-lg bg-gray-50 px-3 py-2">
                              <p className="text-[10px] uppercase tracking-wide text-gray-500">{label}</p>
                              {value ? (
                                <a href={value} target="_blank" rel="noreferrer" className="mt-1 block text-[11px] text-[#2E5BDB] break-all hover:underline">
                                  {value}
                                </a>
                              ) : (
                                <p className="mt-1 text-[11px] text-gray-400">未取得</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>

                {selectedAd.needs_media_retry && (
                  <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-3">
                    <p className="text-[12px] font-semibold text-rose-700">再抽出推奨</p>
                    <p className="mt-1 text-[11px] text-rose-600">この広告は再抽出候補です。一括投入か個別再抽出で再処理できます。</p>
                  </div>
                )}

                <div className="flex gap-2">
                  <button
                    onClick={() => { void handleRetryAd(selectedAd.id); }}
                    disabled={!!actionLoading}
                    className="flex-1 px-3 py-2 rounded-xl bg-gray-900 text-white text-[12px] font-semibold hover:bg-gray-800 disabled:opacity-50"
                  >
                    {actionLoading === `retry-${selectedAd.id}` ? "再抽出中..." : "この広告を再抽出"}
                  </button>
                  <button
                    onClick={handleBatchExtract}
                    disabled={!!actionLoading}
                    className="flex-1 px-3 py-2 rounded-xl border border-gray-200 text-[12px] font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                  >
                    候補を一括投入
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
