"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import toast from "react-hot-toast";
import { adsApi, fetchApi } from "@/lib/api";
import { platformBadgeColors } from "@/lib/constants";
import type { Ad } from "@/types";

interface AdLibraryProps {
  onAdSelect: (adId: number) => void;
}

const platformColors = platformBadgeColors;

const statusColors: Record<string, string> = {
  pending: "badge-yellow",
  processing: "badge-blue",
  analyzed: "badge-green",
  failed: "badge-red",
};

export default function AdLibrary({ onAdSelect }: AdLibraryProps) {
  const [ads, setAds] = useState<Ad[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [platformFilter, setPlatformFilter] = useState("");
  const [showCrawlModal, setShowCrawlModal] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const pageSize = 20;

  useEffect(() => {
    loadAds();
  }, [page, platformFilter]);

  const loadAds = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (platformFilter) params.platform = platformFilter;
      if (searchQuery) params.advertiser = searchQuery;

      const response = await adsApi.list(params);
      setAds(response.data?.ads ?? []);
      setTotal(response.data?.total ?? 0);
    } catch {
      setError("広告データの取得に失敗しました");
      // Keep previous data on error instead of clearing
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadAds();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Ad Library</h2>
          <p className="mt-1 text-sm text-gray-500">
            {total} ads collected across platforms
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowCrawlModal(true)}
            className="btn-primary"
          >
            Crawl Ads
          </button>
          <label className="btn-secondary cursor-pointer">
            Upload Video
            <input
              type="file"
              accept="video/*"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                setUploadStatus("アップロード中...");
                try {
                  await adsApi.upload(file, { auto_analyze: true });
                  setUploadStatus("アップロード完了");
                  loadAds();
                  setTimeout(() => setUploadStatus(null), 3000);
                } catch {
                  setUploadStatus("アップロードに失敗しました");
                  setTimeout(() => setUploadStatus(null), 5000);
                }
              }}
            />
          </label>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {error}
          <button onClick={loadAds} className="ml-2 font-medium underline">再試行</button>
        </div>
      )}

      {uploadStatus && (
        <div className={`rounded-lg p-3 text-sm ${uploadStatus.includes("失敗") ? "border border-red-200 bg-red-50 text-red-800" : "border border-blue-200 bg-blue-50 text-blue-800"}`}>
          {uploadStatus}
        </div>
      )}

      {/* Filters */}
      <div className="card">
        <form onSubmit={handleSearch} className="flex gap-4">
          <input
            type="text"
            placeholder="Search by advertiser..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="input flex-1"
          />
          <select
            value={platformFilter}
            onChange={(e) => {
              setPlatformFilter(e.target.value);
              setPage(1);
            }}
            className="input w-48"
          >
            <option value="">All Platforms</option>
            <option value="meta">Meta (FB/IG)</option>
            <option value="youtube">YouTube</option>
            <option value="tiktok">TikTok</option>
            <option value="instagram">Instagram</option>
            <option value="facebook">Facebook</option>
            <option value="x_twitter">X (Twitter)</option>
            <option value="line">LINE</option>
            <option value="yahoo">Yahoo!</option>
            <option value="pinterest">Pinterest</option>
            <option value="smartnews">SmartNews</option>
            <option value="google_ads">Google Ads</option>
            <option value="gunosy">Gunosy</option>
          </select>
          <button type="submit" className="btn-primary">
            Search
          </button>
        </form>
      </div>

      {/* Ad Grid */}
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
        </div>
      ) : ads.length === 0 ? (
        <div className="card text-center">
          <p className="text-gray-500">
            No ads found. Start by crawling ads or uploading a video.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {ads.map((ad) => (
            <div
              key={ad.id}
              onClick={() => onAdSelect(ad.id)}
              className="card cursor-pointer transition-shadow hover:shadow-md"
            >
              {/* Thumbnail */}
              <div className="mb-3 h-40 rounded-lg bg-gray-100 overflow-hidden">
                {(ad.thumbnail_url || ad.image_url || ad.snapshot_url) ? (
                  <img
                    src={ad.thumbnail_url || ad.image_url || ad.snapshot_url}
                    alt={ad.title || "Ad thumbnail"}
                    className="h-full w-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                      (e.target as HTMLImageElement).parentElement!.classList.add("flex", "items-center", "justify-center");
                      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
                      svg.setAttribute("class", "h-12 w-12 text-gray-300");
                      svg.setAttribute("fill", "none");
                      svg.setAttribute("viewBox", "0 0 24 24");
                      svg.setAttribute("stroke", "currentColor");
                      svg.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />';
                      (e.target as HTMLImageElement).parentElement!.appendChild(svg);
                    }}
                  />
                ) : (
                  <div className="flex h-full items-center justify-center">
                    <svg
                      className="h-12 w-12 text-gray-300"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1}
                        d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                      />
                    </svg>
                  </div>
                )}
              </div>

              {/* Ad Info */}
              <h4 className="truncate font-medium text-gray-900">
                {ad.title || "Untitled Ad"}
              </h4>
              <p className="mt-1 text-sm text-gray-500">
                {ad.advertiser_name || "Unknown Advertiser"}
              </p>

              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <span
                  className={`badge ${platformColors[ad.platform] || "bg-gray-100 text-gray-800"}`}
                >
                  {ad.platform}
                </span>
                <span className={statusColors[ad.status] || "badge"}>
                  {ad.status}
                </span>
                {ad.duration_seconds && (
                  <span className="text-xs text-gray-500">
                    {Math.round(ad.duration_seconds)}s
                  </span>
                )}
              </div>
              {/* Metrics row */}
              {(ad.impressions || ad.spend || ad.view_count) ? (
                <div className="mt-2 flex items-center gap-3 text-[11px] text-gray-400">
                  {ad.impressions != null && ad.impressions > 0 && (
                    <span title="Impressions">{ad.impressions.toLocaleString()} imp</span>
                  )}
                  {ad.spend != null && ad.spend > 0 && (
                    <span title="Spend">&yen;{ad.spend.toLocaleString()}</span>
                  )}
                  {ad.cpc != null && ad.cpc > 0 && (
                    <span title="CPC">CPC &yen;{ad.cpc.toFixed(0)}</span>
                  )}
                  {!ad.impressions && ad.view_count != null && ad.view_count > 0 && (
                    <span title="Views">{ad.view_count.toLocaleString()} views</span>
                  )}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > pageSize && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-secondary"
          >
            Previous
          </button>
          <span className="flex items-center px-4 text-sm text-gray-600">
            Page {page} of {Math.ceil(total / pageSize)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= Math.ceil(total / pageSize)}
            className="btn-secondary"
          >
            Next
          </button>
        </div>
      )}

      {/* Crawl Modal */}
      {showCrawlModal && (
        <CrawlModal
          onClose={() => setShowCrawlModal(false)}
          onSuccess={() => {
            setShowCrawlModal(false);
            loadAds();
          }}
        />
      )}
    </div>
  );
}

const ALL_PLATFORMS = ["facebook", "instagram", "youtube", "tiktok", "x_twitter", "line", "yahoo", "pinterest", "smartnews", "google_ads", "gunosy"];

const PLATFORM_LABELS: Record<string, string> = {
  facebook: "Facebook", instagram: "Instagram", youtube: "YouTube",
  tiktok: "TikTok", x_twitter: "X (Twitter)", line: "LINE",
  yahoo: "Yahoo!", pinterest: "Pinterest", smartnews: "SmartNews",
  google_ads: "Google Ads", gunosy: "Gunosy",
};

function CrawlModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [query, setQuery] = useState("");
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [connectedPlatforms, setConnectedPlatforms] = useState<string[]>([]);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(false);
  const [loadingPlatforms, setLoadingPlatforms] = useState(true);
  const [crawlResult, setCrawlResult] = useState<string | null>(null);

  // Progress tracking
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [currentPlatform, setCurrentPlatform] = useState<string | null>(null);
  const [completedPlatforms, setCompletedPlatforms] = useState(0);
  const [totalPlatforms, setTotalPlatforms] = useState(0);
  const [adsFound, setAdsFound] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollCountRef = useRef(0);

  useEffect(() => {
    fetchApi<{ connected: string[] }>("/ads/connected-platforms")
      .then((data) => {
        setConnectedPlatforms(data.connected);
        setPlatforms(data.connected);
      })
      .catch(() => {
        setConnectedPlatforms([]);
      })
      .finally(() => setLoadingPlatforms(false));
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const startPolling = useCallback((id: string) => {
    pollCountRef.current = 0;
    pollRef.current = setInterval(async () => {
      pollCountRef.current += 1;
      if (pollCountRef.current > 60) {
        // Max 3 min polling
        if (pollRef.current) clearInterval(pollRef.current);
        return;
      }
      try {
        const status = await adsApi.crawlStatus(id);
        setProgress(status.progress_percent);
        setCurrentPlatform(status.current_platform);
        setCompletedPlatforms(status.completed_platforms);
        setTotalPlatforms(status.total_platforms);
        setAdsFound(status.total_ads_found);

        if (status.status === "completed") {
          if (pollRef.current) clearInterval(pollRef.current);
          setLoading(false);
          toast.success(`クロール完了: ${status.total_ads_found}件の広告を取得しました`);
          onSuccess();
        } else if (status.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          setLoading(false);
          toast.error(status.error_message || "クロールに失敗しました");
        }
      } catch {
        // Silently continue polling
      }
    }, 3000);
  }, [onSuccess]);

  const handleCrawl = async () => {
    if (!query.trim() || platforms.length === 0) return;
    setLoading(true);
    setCrawlResult(null);
    setProgress(0);
    setAdsFound(0);
    setCurrentPlatform(null);
    setCompletedPlatforms(0);
    setTotalPlatforms(platforms.length);

    try {
      const res = await adsApi.crawl({
        query,
        platforms,
        limit_per_platform: limit,
        auto_analyze: true,
      });
      const data = res?.data as { task_id?: string; status?: string; message?: string } | undefined;
      const taskId = data?.task_id;
      const msg = data?.message;

      if (taskId) {
        setJobId(taskId);
        if (data?.status === "completed") {
          // Inline crawl completed immediately
          setProgress(100);
          setLoading(false);
          if (msg) {
            setCrawlResult(msg);
            toast.success(msg);
          }
          onSuccess();
        } else {
          // Async task dispatched, start polling
          if (msg) setCrawlResult(msg);
          startPolling(taskId);
        }
      } else {
        setLoading(false);
        if (msg) {
          setCrawlResult(msg);
          toast.success(msg);
        }
        onSuccess();
      }
    } catch {
      setLoading(false);
      toast.error("クロールに失敗しました。バックエンド接続を確認してください。");
    }
  };

  const disconnected = ALL_PLATFORMS.filter((p) => !connectedPlatforms.includes(p));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
        <h3 className="text-lg font-semibold">広告クロール</h3>

        <div className="mt-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              検索キーワード
            </label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="例: 競合ブランド名、商品カテゴリ..."
              className="input mt-1"
              onKeyDown={(e) => { if (e.key === "Enter") handleCrawl(); }}
              disabled={loading}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              連携済み媒体 ({connectedPlatforms.length}媒体)
            </label>
            {loadingPlatforms ? (
              <p className="text-xs text-gray-400">読み込み中...</p>
            ) : connectedPlatforms.length === 0 ? (
              <div className="bg-amber-50 border border-amber-200 rounded p-3">
                <p className="text-xs text-amber-700">
                  APIキーが設定されている媒体がありません。
                  <br />設定画面からAPIキーを登録してください。
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-2">
                  {connectedPlatforms.map((p) => (
                    <label key={p} className="flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 rounded px-2.5 py-1.5">
                      <input
                        type="checkbox"
                        checked={platforms.includes(p)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setPlatforms([...platforms, p]);
                          } else {
                            setPlatforms(platforms.filter((x) => x !== p));
                          }
                        }}
                        className="rounded border-gray-300"
                        disabled={loading}
                      />
                      <span className="text-sm font-medium text-emerald-800">{PLATFORM_LABELS[p] || p}</span>
                    </label>
                  ))}
                </div>
                {disconnected.length > 0 && (
                  <p className="text-[10px] text-gray-400 mt-1">
                    未連携: {disconnected.map((p) => PLATFORM_LABELS[p] || p).join(", ")}
                  </p>
                )}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              媒体あたりの取得件数
            </label>
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              min={1}
              max={100}
              className="input mt-1 w-32"
              disabled={loading}
            />
          </div>

          {/* Progress bar */}
          {loading && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-gray-600">
                <span>
                  {currentPlatform
                    ? `処理中: ${PLATFORM_LABELS[currentPlatform] || currentPlatform}`
                    : "クロール中..."}
                </span>
                <span>{completedPlatforms}/{totalPlatforms} 媒体完了</span>
              </div>
              <div className="w-full h-2.5 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${Math.max(progress, 5)}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-gray-400">
                <span>{progress}%</span>
                <span>{adsFound}件の広告を取得済み</span>
              </div>
            </div>
          )}

          {crawlResult && !loading && (
            <div className="bg-blue-50 border border-blue-200 rounded p-3 text-xs text-blue-700">
              {crawlResult}
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} className="btn-secondary">
            閉じる
          </button>
          <button
            onClick={handleCrawl}
            disabled={loading || !query.trim() || platforms.length === 0}
            className="btn-primary"
          >
            {loading ? "クロール中..." : "クロール開始"}
          </button>
        </div>
      </div>
    </div>
  );
}
