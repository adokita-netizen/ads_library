"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";
import { formatNumber, formatYen } from "@/lib/format";

interface AdvertiserItem {
  name: string;
  advertiser_name?: string;
  ad_count: number;
  hit_rate: number;
  avg_score: number;
  total_spend?: number;
  active_ads?: number;
  hit_count?: number;
  mega_hit_count?: number;
}

interface AdvertiserAd {
  ad_id: number;
  product_name?: string;
  title?: string;
  hit_score?: number;
  hit_level?: string;
  thumbnail?: string;
  image_url?: string;
  platform?: string;
  days_running?: number;
  is_still_running?: boolean;
  spend_increase?: number;
}

type SortKey = "avg_score" | "ad_count" | "hit_rate" | "total_spend";

interface AdvertiserLeaderboardProps {
  genre?: string;
  onAdSelect?: (adId: number) => void;
  onAdvertiserProfile?: (name: string) => void;
}

export default function AdvertiserLeaderboard({ genre, onAdSelect, onAdvertiserProfile }: AdvertiserLeaderboardProps) {
  const [advertisers, setAdvertisers] = useState<AdvertiserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortKey>("avg_score");
  const [expandedName, setExpandedName] = useState<string | null>(null);
  const [expandedAds, setExpandedAds] = useState<AdvertiserAd[]>([]);
  const [expandLoading, setExpandLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, string | number | undefined> = {};
        if (genre && genre !== "all") params.genre = genre;
        const res = await fetchApi<{ items?: AdvertiserItem[]; advertisers?: AdvertiserItem[] }>(
          "/rankings/advertisers",
          { params }
        );
        const items = res?.items || res?.advertisers || (Array.isArray(res) ? res : []);
        setAdvertisers(
          (Array.isArray(items) ? items : []).map((a: AdvertiserItem) => ({
            ...a,
            name: a.name || a.advertiser_name || "不明",
          }))
        );
      } catch {
        setError("広告主データの取得に失敗しました");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [genre]);

  const sorted = useMemo(() => {
    return [...advertisers].sort((a, b) => {
      switch (sortBy) {
        case "avg_score": return (b.avg_score || 0) - (a.avg_score || 0);
        case "ad_count": return (b.ad_count || 0) - (a.ad_count || 0);
        case "hit_rate": {
          const rA = typeof a.hit_rate === "number" ? (a.hit_rate <= 1 ? a.hit_rate * 100 : a.hit_rate) : 0;
          const rB = typeof b.hit_rate === "number" ? (b.hit_rate <= 1 ? b.hit_rate * 100 : b.hit_rate) : 0;
          return rB - rA;
        }
        case "total_spend": return (b.total_spend || 0) - (a.total_spend || 0);
        default: return 0;
      }
    });
  }, [advertisers, sortBy]);

  const handleExpand = useCallback(async (name: string) => {
    if (expandedName === name) {
      setExpandedName(null);
      setExpandedAds([]);
      return;
    }
    setExpandedName(name);
    setExpandLoading(true);
    setExpandedAds([]);
    try {
      const res = await fetchApi<{ items?: AdvertiserAd[]; ads?: AdvertiserAd[] }>(
        `/rankings/advertiser/${encodeURIComponent(name)}/ads`
      );
      const ads = res?.items || res?.ads || (Array.isArray(res) ? res : []);
      setExpandedAds(Array.isArray(ads) ? ads : []);
    } catch {
      setExpandedAds([]);
    } finally {
      setExpandLoading(false);
    }
  }, [expandedName]);

  if (loading) {
    return (
      <div className="card overflow-hidden">
        <div className="px-4 py-3 animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-40 mb-3" />
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 py-2.5 border-b border-gray-50">
              <div className="w-6 h-6 rounded bg-gray-200" />
              <div className="h-3.5 bg-gray-200 rounded w-28" />
              <div className="h-3 bg-gray-100 rounded w-12 ml-auto" />
              <div className="h-3 bg-gray-100 rounded w-12" />
              <div className="h-3 bg-gray-100 rounded w-12" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card px-4 py-6 text-center">
        <p className="text-[12px] text-red-500 mb-2">{error}</p>
        <p className="text-[10px] text-gray-400">データが準備中の可能性があります</p>
      </div>
    );
  }

  if (sorted.length === 0) {
    return (
      <div className="card px-4 py-8 text-center">
        <svg className="w-10 h-10 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
        </svg>
        <p className="text-[12px] text-gray-500 mb-1">広告主データがありません</p>
        <p className="text-[10px] text-gray-400">ランキング計算を実行するとデータが蓄積されます</p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 007.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M7.73 9.728a6.726 6.726 0 002.748 1.35m8.272-6.842V4.5c0 2.108-.966 3.99-2.48 5.228m2.48-5.492a46.32 46.32 0 012.916.52 6.003 6.003 0 01-5.395 4.972m0 0a6.726 6.726 0 01-2.749 1.35m0 0a6.772 6.772 0 01-3.044 0" />
          </svg>
          <h3 className="text-[13px] font-bold text-gray-900">広告主リーダーボード</h3>
          <span className="text-[10px] text-gray-400">{sorted.length}社</span>
        </div>
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
          {([
            { key: "avg_score" as SortKey, label: "スコア" },
            { key: "ad_count" as SortKey, label: "広告数" },
            { key: "hit_rate" as SortKey, label: "HIT率" },
            { key: "total_spend" as SortKey, label: "消化額" },
          ]).map((opt) => (
            <button
              key={opt.key}
              onClick={() => setSortBy(opt.key)}
              className={`px-2 py-1 rounded text-[10px] transition-colors ${sortBy === opt.key ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="divide-y divide-gray-50">
        {sorted.map((adv, i) => {
          const hitRate = typeof adv.hit_rate === "number" ? (adv.hit_rate <= 1 ? adv.hit_rate * 100 : adv.hit_rate) : 0;
          const isExpanded = expandedName === adv.name;
          return (
            <React.Fragment key={adv.name}>
              <div
                className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors ${isExpanded ? "bg-blue-50/50" : "hover:bg-gray-50"}`}
                onClick={() => handleExpand(adv.name)}
              >
                {/* Rank */}
                <span className={`inline-flex items-center justify-center w-6 h-6 rounded text-[11px] font-bold shrink-0 ${
                  i < 3 ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-500"
                }`}>
                  {i + 1}
                </span>
                {/* Name */}
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] font-medium text-gray-900 truncate">{adv.name}</p>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    {(adv.mega_hit_count || 0) > 0 && (
                      <span className="text-[8px] px-1 py-0.5 rounded bg-red-100 text-red-700 font-medium">大HIT {adv.mega_hit_count}</span>
                    )}
                    {(adv.hit_count || 0) > 0 && (
                      <span className="text-[8px] px-1 py-0.5 rounded bg-orange-100 text-orange-700 font-medium">HIT {adv.hit_count}</span>
                    )}
                  </div>
                </div>
                {/* Stats */}
                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-center hidden sm:block">
                    <p className="text-[12px] font-semibold text-gray-700">{adv.ad_count}</p>
                    <p className="text-[8px] text-gray-400">広告数</p>
                  </div>
                  <div className="text-center hidden md:block">
                    <p className="text-[12px] font-semibold" style={{ color: hitRate >= 15 ? "#22c55e" : hitRate >= 5 ? "#f59e0b" : "#6b7280" }}>
                      {hitRate.toFixed(1)}%
                    </p>
                    <p className="text-[8px] text-gray-400">HIT率</p>
                  </div>
                  <div className="text-center">
                    <p className="text-[12px] font-bold text-[#4A7DFF]">{Math.round(adv.avg_score || 0)}</p>
                    <p className="text-[8px] text-gray-400">スコア</p>
                  </div>
                  {adv.total_spend != null && (
                    <div className="text-center hidden lg:block">
                      <p className="text-[12px] font-semibold text-gray-700">{formatYen(adv.total_spend)}</p>
                      <p className="text-[8px] text-gray-400">消化額</p>
                    </div>
                  )}
                </div>
                {/* Profile button */}
                {onAdvertiserProfile && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onAdvertiserProfile(adv.name); }}
                    className="text-[9px] px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors shrink-0"
                  >
                    詳細
                  </button>
                )}
                {/* Expand icon */}
                <svg
                  className={`w-4 h-4 text-gray-400 transition-transform shrink-0 ${isExpanded ? "rotate-180" : ""}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                </svg>
              </div>
              {/* Expanded ads */}
              {isExpanded && (
                <div className="bg-blue-50/30 px-4 py-3">
                  {expandLoading ? (
                    <div className="flex items-center justify-center py-3">
                      <svg className="animate-spin h-4 w-4 text-[#4A7DFF]" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                    </div>
                  ) : expandedAds.length === 0 ? (
                    <p className="text-[11px] text-gray-400 text-center py-2">広告データがありません</p>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2">
                      {expandedAds.slice(0, 12).map((ad) => (
                        <div
                          key={ad.ad_id}
                          className="bg-white rounded-lg p-2.5 cursor-pointer hover:shadow-md transition-shadow border border-gray-100"
                          onClick={(e) => {
                            e.stopPropagation();
                            onAdSelect?.(ad.ad_id);
                          }}
                        >
                          <div className="flex items-center gap-2">
                            {(ad.thumbnail || ad.image_url) && (
                              <img
                                src={ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || ad.image_url || "")}
                                alt=""
                                className="w-10 h-10 rounded object-cover bg-gray-100 shrink-0"
                                loading="lazy"
                                onError={(e) => {
                                  const el = e.target as HTMLImageElement;
                                  if (ad.thumbnail && el.src !== ad.thumbnail) el.src = ad.thumbnail;
                                  else if (ad.image_url && el.src !== ad.image_url) el.src = ad.image_url;
                                  else el.style.display = "none";
                                }}
                              />
                            )}
                            <div className="flex-1 min-w-0">
                              <p className="text-[11px] font-medium text-gray-900 truncate">
                                {ad.product_name || ad.title || `Ad #${ad.ad_id}`}
                              </p>
                              <div className="flex items-center gap-1 mt-0.5">
                                {ad.hit_level === "mega_hit" && (
                                  <span className="text-[8px] px-1 py-0.5 rounded bg-red-100 text-red-700 font-bold">大HIT</span>
                                )}
                                {ad.hit_level === "hit" && (
                                  <span className="text-[8px] px-1 py-0.5 rounded bg-orange-100 text-orange-700 font-bold">HIT</span>
                                )}
                                <span className="text-[10px] font-semibold text-[#4A7DFF]">{ad.hit_score || 0}</span>
                                {ad.is_still_running && (
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" title="配信中" />
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
