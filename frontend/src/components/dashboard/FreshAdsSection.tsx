"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { platformLabels, platformColors, genreOptions } from "@/lib/constants";
import { formatNumber, formatYen } from "@/lib/format";

// ─── Types ───

interface FreshAd {
  ad_id: number;
  title?: string;
  product_name?: string;
  advertiser_name?: string;
  platform?: string;
  genre?: string;
  hit_score?: number;
  hit_level?: string;
  spend_increase?: number;
  view_increase?: number;
  cumulative_spend?: number;
  cumulative_views?: number;
  thumbnail?: string;
  image_url?: string;
  snapshot_url?: string;
  creative_type?: string;
  destination_url?: string;
  days_running?: number;
  is_still_running?: boolean;
  crawled_at?: string;
  created_at?: string;
}

interface FreshAdsResponse {
  items?: FreshAd[];
  ads?: FreshAd[];
  total?: number;
  page?: number;
  per_page?: number;
}

interface FreshAdsSectionProps {
  refreshKey?: number;
  onAdSelect?: (adId: number) => void;
}

// ─── Helpers ───

const genreLabel = (value: string | null | undefined): string => {
  if (!value || value === "未分類") return "未分類";
  return genreOptions.find((g) => g.value === value)?.label || value;
};

/**
 * Build a proxy thumbnail URL for an ad.
 * Prefer the proxy path /api/v1/media/thumbnail/{ad_id} when possible.
 */
const proxyThumb = (ad: FreshAd): string => {
  // If there is an ad_id, use the thumbnail proxy endpoint
  if (ad.ad_id) {
    return `/api/v1/media/thumbnail/${ad.ad_id}`;
  }
  return ad.thumbnail || ad.image_url || ad.snapshot_url || "";
};

// ─── Component ───

export default function FreshAdsSection({ refreshKey, onAdSelect }: FreshAdsSectionProps) {
  const [ads, setAds] = useState<FreshAd[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const perPage = 20;

  const fetchFreshAds = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchApi<FreshAdsResponse>("/rankings/fresh-ads", {
        params: { page: String(page), per_page: String(perPage) },
      });
      const items = data.items || data.ads || (Array.isArray(data) ? (data as unknown as FreshAd[]) : []);
      setAds(items);
      setTotal(data.total || items.length);
    } catch {
      setAds([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchFreshAds();
  }, [fetchFreshAds, refreshKey]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  if (!loading && ads.length === 0) {
    return null; // Don't show section if no fresh ads
  }

  return (
    <div className="card px-4 py-4">
      <div className="flex items-center gap-2 mb-3">
        <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">最新クロール広告</h3>
        <span className="text-[10px] text-gray-400">直近7日間にクロールされた広告</span>
        {total > 0 && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-medium ml-auto">
            {total}件
          </span>
        )}
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-lg border border-gray-100 p-3">
              <div className="w-full aspect-[4/3] bg-gray-200 rounded mb-2" />
              <div className="h-3.5 bg-gray-200 rounded w-3/4 mb-1.5" />
              <div className="h-2.5 bg-gray-100 rounded w-1/2 mb-1" />
              <div className="h-2.5 bg-gray-100 rounded w-1/3" />
            </div>
          ))}
        </div>
      )}

      {/* Ad cards grid */}
      {!loading && ads.length > 0 && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {ads.map((ad) => {
              const thumbSrc = proxyThumb(ad);
              const pLabel = platformLabels[ad.platform || ""] || ad.platform || "";
              const pColor = platformColors[ad.platform || ""] || "bg-gray-400";

              return (
                <div
                  key={ad.ad_id}
                  className="rounded-lg border border-gray-100 hover:border-gray-200 hover:shadow-sm transition-all cursor-pointer overflow-hidden group"
                  onClick={() => onAdSelect?.(ad.ad_id)}
                >
                  {/* Thumbnail */}
                  <div className="relative w-full aspect-[4/3] bg-gray-100 overflow-hidden">
                    {thumbSrc ? (
                      <img
                        src={thumbSrc}
                        alt=""
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                        loading="lazy"
                        onError={(e) => {
                          const el = e.target as HTMLImageElement;
                          // Fallback: try image_url then snapshot_url
                          if (ad.image_url && el.src !== ad.image_url) {
                            el.src = ad.image_url;
                          } else if (ad.snapshot_url && el.src !== ad.snapshot_url) {
                            el.src = ad.snapshot_url;
                          } else {
                            el.style.display = "none";
                          }
                        }}
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <svg className="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                      </div>
                    )}

                    {/* NEW badge */}
                    <span className="absolute top-1.5 left-1.5 text-[8px] px-1.5 py-0.5 rounded font-bold bg-emerald-500 text-white shadow-sm">
                      NEW
                    </span>

                    {/* Score badge */}
                    {ad.hit_score != null && ad.hit_score > 0 && (
                      <span
                        className="absolute top-1.5 right-1.5 text-[10px] px-1.5 py-0.5 rounded font-bold text-white shadow-sm"
                        style={{
                          backgroundColor:
                            (ad.hit_score || 0) >= 70 ? "#ef4444" : (ad.hit_score || 0) >= 45 ? "#f59e0b" : "#4A7DFF",
                        }}
                      >
                        {ad.hit_score}
                      </span>
                    )}

                    {/* Platform badge */}
                    {pLabel && (
                      <span className={`absolute bottom-1.5 left-1.5 platform-icon ${pColor} text-[8px]`}>
                        {pLabel}
                      </span>
                    )}

                    {/* Running indicator */}
                    {ad.is_still_running && (
                      <span className="absolute bottom-1.5 right-1.5 w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-white" title="配信中" />
                    )}
                  </div>

                  {/* Info */}
                  <div className="px-3 py-2.5">
                    <p className="text-[12px] font-medium text-gray-900 truncate" title={ad.product_name || ad.title || ""}>
                      {ad.product_name || ad.title || `広告 #${ad.ad_id}`}
                    </p>
                    <p className="text-[10px] text-gray-400 truncate mt-0.5">
                      {ad.advertiser_name || "-"}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                      {ad.genre && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600">
                          {genreLabel(ad.genre)}
                        </span>
                      )}
                      {ad.hit_level === "mega_hit" && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-bold">
                          大HIT
                        </span>
                      )}
                      {ad.hit_level === "hit" && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 font-bold">
                          HIT
                        </span>
                      )}
                    </div>
                    {(ad.spend_increase || ad.view_increase) && (
                      <div className="flex items-center gap-3 mt-1.5">
                        {ad.spend_increase != null && ad.spend_increase > 0 && (
                          <span className="text-[10px] text-gray-500">
                            消化 {formatYen(ad.spend_increase)}
                          </span>
                        )}
                        {ad.view_increase != null && ad.view_increase > 0 && (
                          <span className="text-[10px] text-gray-500">
                            再生 {formatNumber(ad.view_increase)}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="text-[11px] px-2.5 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                前へ
              </button>
              <span className="text-[11px] text-gray-500">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="text-[11px] px-2.5 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                次へ
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
