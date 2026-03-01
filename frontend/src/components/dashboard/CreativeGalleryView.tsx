"use client";

import React, { useState, useMemo } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { platformLabels, platformColors, genreOptions } from "@/lib/constants";
import { formatYen } from "@/lib/format";

// ─── Types ───

interface HitAd {
  rank: number;
  ad_id: number;
  product_name: string;
  advertiser_name: string;
  genre: string;
  platform: string;
  view_increase: number;
  spend_increase: number;
  cumulative_views: number;
  cumulative_spend: number;
  is_hit: boolean;
  hit_score: number;
  trend_score: number;
  rank_change: number | null;
  thumbnail: string;
  duration_seconds: number;
  image_url: string;
  snapshot_url: string;
  destination_url: string;
  destination_type: string;
  like_count: number;
  published_date: string;
  description: string;
  title: string;
  video_url?: string;
  creative_type?: string;
  days_running?: number;
  is_still_running?: boolean;
  hit_level?: string;
  estimation_method?: string;
  hook_type?: string;
  offer_type?: string;
}

interface CreativeGalleryViewProps {
  ads: HitAd[];
  onAdSelect: (adId: number) => void;
}

// ─── Label helpers ───

const hookLabels: Record<string, string> = {
  question: "質問型",
  pain_point: "悩み訴求",
  benefit: "ベネフィット",
  curiosity: "好奇心",
  social_proof: "社会的証明",
  urgency: "緊急性",
  storytelling: "ストーリー",
  number: "数字訴求",
  comparison: "比較",
  authority: "権威性",
};

const hookBadgeColors: Record<string, string> = {
  question: "bg-blue-100 text-blue-700",
  pain_point: "bg-red-100 text-red-700",
  benefit: "bg-green-100 text-green-700",
  curiosity: "bg-purple-100 text-purple-700",
  social_proof: "bg-yellow-100 text-yellow-800",
  urgency: "bg-orange-100 text-orange-700",
  storytelling: "bg-pink-100 text-pink-700",
  number: "bg-indigo-100 text-indigo-700",
  comparison: "bg-teal-100 text-teal-700",
  authority: "bg-amber-100 text-amber-800",
};

const genreLabel = (value: string | null | undefined): string => {
  if (!value || value === "未分類") return "未分類";
  return genreOptions.find((g) => g.value === value)?.label || value;
};

// ─── Main Component ───

export default function CreativeGalleryView({ ads, onAdSelect }: CreativeGalleryViewProps) {
  const [typeFilter, setTypeFilter] = useState<"all" | "video" | "image">("all");
  const [hookFilter, setHookFilter] = useState("all");

  // Collect unique hook types for filter
  const availableHooks = useMemo(() => {
    const hooks = new Set<string>();
    ads.forEach((a) => {
      if (a.hook_type) hooks.add(a.hook_type);
    });
    return Array.from(hooks).sort();
  }, [ads]);

  // Filter and sort (score descending, hit ads first)
  const filtered = useMemo(() => {
    let result = [...ads];
    if (typeFilter !== "all") {
      result = result.filter((a) => a.creative_type === typeFilter);
    }
    if (hookFilter !== "all") {
      result = result.filter((a) => a.hook_type === hookFilter);
    }
    result.sort((a, b) => (b.hit_score || 0) - (a.hit_score || 0));
    return result;
  }, [ads, typeFilter, hookFilter]);

  return (
    <div>
      {/* Filters */}
      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <span className="text-[10px] text-gray-400">フィルター:</span>
        {/* Creative type filter */}
        <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5">
          {(["all", "video", "image"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`px-2 py-1 rounded text-[10px] transition-colors ${
                typeFilter === t ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"
              }`}
            >
              {t === "all" ? "全て" : t === "video" ? "動画" : "静止画"}
            </button>
          ))}
        </div>
        {/* Hook type filter */}
        {availableHooks.length > 0 && (
          <select
            value={hookFilter}
            onChange={(e) => setHookFilter(e.target.value)}
            className="select-filter text-[10px] h-7"
          >
            <option value="all">全フック</option>
            {availableHooks.map((h) => (
              <option key={h} value={h}>{hookLabels[h] || h}</option>
            ))}
          </select>
        )}
        <span className="text-[9px] text-gray-400 ml-auto">{filtered.length}件</span>
      </div>

      {/* Gallery grid */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <svg className="w-10 h-10 text-gray-200 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
          </svg>
          <p className="text-[12px] text-gray-500">条件に一致するクリエイティブがありません</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
          {filtered.map((ad) => {
            const thumbSrc = ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || ad.image_url || "");
            const scoreColor =
              (ad.hit_score || 0) >= 80 ? "#ef4444" : (ad.hit_score || 0) >= 50 ? "#f59e0b" : "#4A7DFF";

            return (
              <div
                key={ad.ad_id}
                onClick={() => onAdSelect(ad.ad_id)}
                className="group cursor-pointer rounded-lg overflow-hidden bg-white border border-gray-200 hover:shadow-lg hover:border-gray-300 transition-all"
              >
                {/* Thumbnail area */}
                <div className="relative aspect-[4/3] bg-gray-100 overflow-hidden">
                  {thumbSrc ? (
                    <img
                      src={thumbSrc}
                      alt={ad.product_name || ""}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      loading="lazy"
                      onError={(e) => {
                        const el = e.target as HTMLImageElement;
                        // B9: Fallback chain: proxy -> thumbnail -> image_url -> hide
                        if (ad.thumbnail && el.src !== ad.thumbnail) {
                          el.src = ad.thumbnail;
                        } else if (ad.image_url && el.src !== ad.image_url) {
                          el.src = ad.image_url;
                        } else if (ad.snapshot_url && el.src !== ad.snapshot_url) {
                          el.src = ad.snapshot_url;
                        } else {
                          el.style.display = "none";
                          if (el.nextElementSibling) (el.nextElementSibling as HTMLElement).style.display = "flex";
                        }
                      }}
                    />
                  ) : null}
                  <div className={`absolute inset-0 items-center justify-center bg-gray-100 ${thumbSrc ? "hidden" : "flex"}`}>
                    {ad.creative_type === "video" ? (
                      <svg className="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                      </svg>
                    ) : (
                      <svg className="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                      </svg>
                    )}
                  </div>

                  {/* Score badge (top-right) */}
                  <div className="absolute top-1.5 right-1.5">
                    <span
                      className="inline-flex items-center justify-center min-w-[28px] h-6 rounded-md text-[11px] font-bold text-white shadow-sm"
                      style={{ backgroundColor: scoreColor }}
                    >
                      {ad.hit_score || 0}
                    </span>
                  </div>

                  {/* HIT badge (top-left) */}
                  {ad.hit_level === "mega_hit" && (
                    <span className="absolute top-1.5 left-1.5 rounded bg-red-500 text-white px-1.5 py-0.5 text-[8px] font-bold shadow-sm">
                      大HIT
                    </span>
                  )}
                  {ad.hit_level === "hit" && (
                    <span className="absolute top-1.5 left-1.5 rounded bg-orange-500 text-white px-1.5 py-0.5 text-[8px] font-bold shadow-sm">
                      HIT
                    </span>
                  )}

                  {/* Creative type badge (bottom-left) */}
                  {ad.creative_type && (
                    <span className="absolute bottom-1.5 left-1.5 rounded bg-black/60 text-white px-1.5 py-0.5 text-[8px] font-medium">
                      {ad.creative_type === "video" ? "動画" : "静止画"}
                      {ad.duration_seconds > 0 && ` ${ad.duration_seconds}秒`}
                    </span>
                  )}

                  {/* Running indicator (bottom-right) */}
                  {ad.is_still_running && (
                    <span className="absolute bottom-1.5 right-1.5 w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-white shadow-sm" title="配信中" />
                  )}
                </div>

                {/* Info area */}
                <div className="px-2.5 py-2">
                  <p className="text-[11px] font-semibold text-gray-900 truncate" title={ad.product_name || ad.title || ""}>
                    {ad.product_name || ad.title || "不明"}
                  </p>
                  <p className="text-[9px] text-gray-400 truncate mt-0.5">{ad.advertiser_name || "-"}</p>

                  {/* Badges row */}
                  <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                    <span className={`platform-icon ${platformColors[ad.platform] || "bg-gray-400"} text-[7px]`} style={{ width: "auto", padding: "0 4px", minWidth: "auto" }}>
                      {platformLabels[ad.platform] || ad.platform}
                    </span>
                    {ad.hook_type && (
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[8px] font-medium ${hookBadgeColors[ad.hook_type] || "bg-gray-100 text-gray-600"}`}>
                        {hookLabels[ad.hook_type] || ad.hook_type}
                      </span>
                    )}
                  </div>

                  {/* Quick stats + actions */}
                  <div className="flex items-center justify-between mt-1.5 pt-1.5 border-t border-gray-100">
                    <span className="text-[9px] text-gray-400">{formatYen(ad.cumulative_spend || 0)}</span>
                    <div className="flex items-center gap-1">
                      {ad.days_running != null && (
                        <span className="text-[9px] text-gray-400">{ad.days_running}日</span>
                      )}
                      <button
                        className="text-gray-300 hover:text-amber-500 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          fetchApi("/rankings/bookmarks", { method: "POST", body: { ad_id: ad.ad_id } })
                            .then(() => toast.success("ブックマークに追加しました"))
                            .catch(() => toast.error("ブックマーク追加に失敗しました"));
                        }}
                        title="ブックマーク"
                      >
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
                        </svg>
                      </button>
                      <button
                        className="text-gray-300 hover:text-emerald-500 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          window.open(`/api/v1/media/download/${ad.ad_id}`, "_blank", "noopener,noreferrer");
                        }}
                        title="ダウンロード"
                      >
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
