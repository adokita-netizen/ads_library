"use client";

import React, { useState, useMemo } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { getMediaReasonMessage, normalizeMediaReasons, openCreativeDownload, type MediaStatus } from "@/lib/media";
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
  media_status?: MediaStatus;
}

interface CreativeGalleryViewProps {
  ads: HitAd[];
  onAdSelect: (adId: number) => void;
  onRecoveryRequest?: (adId: number) => void;
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

const stateBadgeClass = (active: boolean, tone: "emerald" | "blue" | "amber" | "rose") => {
  const map = {
    emerald: active ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-400",
    blue: active ? "bg-blue-50 text-blue-700" : "bg-gray-100 text-gray-400",
    amber: active ? "bg-amber-50 text-amber-700" : "bg-gray-100 text-gray-400",
    rose: active ? "bg-rose-50 text-rose-700" : "bg-gray-100 text-gray-400",
  };
  return map[tone];
};

// ─── Main Component ───

export default function CreativeGalleryView({ ads, onAdSelect, onRecoveryRequest }: CreativeGalleryViewProps) {
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
                {(() => {
                  const mediaStatus = ad.media_status || {};
                  const canView = mediaStatus.viewable !== false;
                  const canDownload = mediaStatus.downloadable === true;
                  const hasLp = mediaStatus.has_lp === true;
                  const reasons = normalizeMediaReasons(mediaStatus.missing_reasons);
                  const shortage = reasons.includes("missing_creative");
                  const snapshotOnly = reasons.includes("snapshot_only") || (!canDownload && !ad.video_url && !ad.image_url && Boolean(ad.snapshot_url));
                  const lpUnresolved = !hasLp || reasons.includes("lp_missing") || reasons.includes("lp_unresolved");
                  const needsRecovery = snapshotOnly || !canDownload || lpUnresolved || shortage;
                  return (
                    <>
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
                    <div className="mt-1.5 pt-1.5 border-t border-gray-100 space-y-1.5">
                      <div className="flex flex-wrap gap-1">
                        <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[8px] font-medium ${stateBadgeClass(canView, "blue")}`}>閲覧可</span>
                        <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[8px] font-medium ${stateBadgeClass(canDownload, "emerald")}`}>DL可</span>
                        <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[8px] font-medium ${stateBadgeClass(hasLp, "amber")}`}>LPあり</span>
                        <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[8px] font-medium ${stateBadgeClass(shortage, "rose")}`}>素材不足</span>
                        {snapshotOnly && (
                          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[8px] font-medium bg-blue-50 text-blue-700">スナップショットのみ</span>
                        )}
                        {lpUnresolved && (
                          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[8px] font-medium bg-amber-50 text-amber-700">LP未解決</span>
                        )}
                      </div>
                      {!canDownload && reasons.length > 0 && (
                        <p className="text-[9px] text-rose-500">{getMediaReasonMessage(reasons[0])}</p>
                      )}
                      {!canDownload && snapshotOnly && reasons.length === 0 && (
                        <p className="text-[9px] text-blue-600">スナップショットのみ確認できます</p>
                      )}
                      {lpUnresolved && (
                        <p className="text-[9px] text-amber-600">
                          {hasLp ? "LPの解決先を確認中です" : "LP遷移先がまだ取得できていません"}
                        </p>
                      )}
                      <div className="flex items-center justify-between">
                        <span className="text-[9px] text-gray-400">{formatYen(ad.cumulative_spend || 0)}</span>
                        {ad.days_running != null && (
                        <span className="text-[9px] text-gray-400">{ad.days_running}日</span>
                      )}
                    </div>
                    <div className={`grid gap-1 ${needsRecovery ? "grid-cols-4" : "grid-cols-3"}`}>
                      <button
                        className="min-h-8 rounded-md bg-gray-900 text-white text-[10px] font-medium hover:bg-gray-800 transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                        onClick={(e) => {
                          e.stopPropagation();
                          onAdSelect(ad.ad_id);
                        }}
                        disabled={!canView}
                      >
                        見る
                      </button>
                      <button
                        className="min-h-8 rounded-md bg-emerald-50 text-emerald-700 text-[10px] font-medium hover:bg-emerald-100 transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!canDownload) {
                            toast.error(getMediaReasonMessage(reasons[0] || "download_unavailable"));
                            return;
                          }
                          openCreativeDownload(ad.ad_id);
                        }}
                        disabled={!canDownload}
                      >
                        DL
                      </button>
                      <button
                        className="min-h-8 rounded-md bg-amber-50 text-amber-700 text-[10px] font-medium hover:bg-amber-100 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          fetchApi("/rankings/bookmarks", { method: "POST", body: { ad_id: ad.ad_id } })
                            .then(() => toast.success("ブックマークに追加しました"))
                            .catch(() => toast.error("ブックマーク追加に失敗しました"));
                        }}
                      >
                        保存
                      </button>
                      {needsRecovery && (
                        <button
                          className="min-h-8 rounded-md bg-sky-50 text-sky-700 text-[10px] font-medium hover:bg-sky-100 transition-colors"
                          onClick={(e) => {
                            e.stopPropagation();
                            (onRecoveryRequest || onAdSelect)(ad.ad_id);
                          }}
                        >
                          再取得
                        </button>
                      )}
                    </div>
                  </div>
                </div>
                    </>
                  );
                })()}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
