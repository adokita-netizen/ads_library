"use client";

import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { platformLabels, platformColors, genreOptions } from "@/lib/constants";
import { formatNumber, formatYen } from "@/lib/format";
import { NumericProvenanceBadge, type NumericProvenanceState } from "../common/NumericProvenance";
import { CreativeViewer } from "../common/CreativeViewer";

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
  estimation_method?: string;
  metric_source?: string;
  creative_source?: string;
  lp_source?: string;
  metric_status?: NumericProvenanceState;
  creative_status?: NumericProvenanceState;
  freshness_status?: "fresh" | "missing" | "stale" | string;
  last_meta_success_at?: string;
  meta_quality_state?: NumericProvenanceState;
  meta_recovery_reason?: string;
}

interface HitAdCardViewProps {
  ads: HitAd[];
  onAdSelect: (adId: number) => void;
}

const genreLabel = (value: string | null | undefined): string => {
  if (!value || value === "未分類") return "未分類";
  return genreOptions.find((g) => g.value === value)?.label || value;
};

// B18: Data quality assessment
function getDataQuality(ad: HitAd): "complete" | "partial" | "incomplete" {
  let missing = 0;
  if (!ad.thumbnail && !ad.image_url) missing++;
  if (!ad.genre || ad.genre === "未分類") missing++;
  if (!ad.destination_url) missing++;
  if (!ad.creative_type) missing++;
  if (missing >= 3) return "incomplete";
  if (missing >= 1) return "partial";
  return "complete";
}

const qualityDot: Record<string, string> = {
  complete: "bg-emerald-500",
  partial: "bg-amber-500",
  incomplete: "bg-red-400",
};

function isMetaPlatform(platform: string | undefined): boolean {
  return platform === "facebook" || platform === "instagram" || platform === "meta";
}

function formatMetaSource(value: string | undefined): string {
  const normalized = (value || "missing").replaceAll("_", " ");
  if (normalized === "api") return "API";
  if (normalized === "db") return "DB";
  return normalized;
}

function isFreshMetaAd(lastMetaSuccessAt?: string): boolean {
  if (!lastMetaSuccessAt) return false;
  const ts = Date.parse(lastMetaSuccessAt);
  if (Number.isNaN(ts)) return false;
  return Date.now() - ts <= 1000 * 60 * 60 * 48;
}

export default function HitAdCardView({ ads, onAdSelect }: HitAdCardViewProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {ads.map((ad) => {
        const scoreColor =
          (ad.hit_score || 0) >= 80 ? "#ef4444" : (ad.hit_score || 0) >= 50 ? "#f59e0b" : "#4A7DFF";
        const quality = getDataQuality(ad);
        const isProvisional = ad.days_running != null && ad.days_running < 7;
        const showMeta = isMetaPlatform(ad.platform);
        const metaState = (ad.meta_quality_state || "missing") as NumericProvenanceState;
        const isNewMeta = showMeta && isFreshMetaAd(ad.last_meta_success_at);

        return (
          <div
            key={ad.ad_id}
            onClick={() => onAdSelect(ad.ad_id)}
            className="card cursor-pointer hover:shadow-lg transition-shadow overflow-hidden flex flex-col"
          >
            {/* Creative — B9: prefer proxy thumbnail URL */}
            <div className="max-h-[200px] overflow-hidden rounded-lg mb-3">
              <CreativeViewer
                imageUrl={ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.image_url || ad.thumbnail || null)}
                videoUrl={ad.ad_id ? `/api/v1/media/video/${ad.ad_id}` : (ad.video_url || null)}
                snapshotUrl={ad.snapshot_url || null}
                thumbnailUrl={ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || null)}
                creativeType={ad.creative_type || null}
              />
            </div>

            {/* Header: rank + HIT badge + title */}
            <div className="flex items-start gap-2 mb-2">
              <span
                className={`shrink-0 inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold ${
                  ad.rank <= 3 ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-500"
                }`}
              >
                {ad.rank}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-[13px] font-semibold text-gray-900 truncate">
                    {ad.product_name || ad.title || "不明"}
                  </span>
                  {ad.is_hit && (
                    <span className="shrink-0 rounded bg-red-500 px-1 py-px text-[8px] font-bold text-white leading-none">
                      HIT
                    </span>
                  )}
                  <span className={`shrink-0 w-1.5 h-1.5 rounded-full ${qualityDot[quality]}`} title={quality === "complete" ? "データ完全" : quality === "partial" ? "一部データ不足" : "データ不足"} />
                  {showMeta ? <NumericProvenanceBadge state={metaState} /> : null}
                  {isNewMeta ? (
                    <span className="shrink-0 rounded bg-sky-100 px-1 py-px text-[8px] font-bold leading-none text-sky-700">
                      NEW
                    </span>
                  ) : null}
                </div>
                <p className="text-[10px] text-gray-400 truncate">{ad.advertiser_name || "-"}</p>
              </div>
            </div>

            {/* Hit score bar */}
            <div className="mb-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-gray-400">ヒットスコア</span>
                <span className="flex items-center gap-1">
                  <span className={`text-[11px] font-bold ${isProvisional ? "opacity-60" : ""}`} style={{ color: scoreColor }}>
                    {ad.hit_score || 0}
                  </span>
                  {isProvisional && <span className="text-[7px] text-gray-400">暫定</span>}
                </span>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${ad.hit_score || 0}%`, backgroundColor: scoreColor }}
                />
              </div>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 mb-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-gray-400">推定消化額</span>
                <span className="text-[11px] font-semibold text-gray-900">{formatYen(ad.cumulative_spend || 0)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-gray-400">推定再生数</span>
                <span className="text-[11px] font-semibold text-gray-900">{formatNumber(ad.cumulative_views || 0)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-gray-400">配信日数</span>
                <span className="text-[11px] text-gray-700">
                  {ad.days_running != null ? `${ad.days_running}日` : ad.published_date ? `${Math.max(1, Math.round((Date.now() - new Date(ad.published_date).getTime()) / 86400000))}日` : "-"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-gray-400">ステータス</span>
                {ad.is_still_running !== false ? (
                  <span className="text-[10px] font-semibold text-emerald-600">● 配信中</span>
                ) : (
                  <span className="text-[10px] text-gray-400">○ 終了</span>
                )}
              </div>
            </div>

            {/* Tags row */}
            <div className="flex items-center gap-1.5 flex-wrap mb-3">
              <span className={`platform-icon ${platformColors[ad.platform] || "bg-gray-400"} text-[8px]`}>
                {platformLabels[ad.platform] || ad.platform}
              </span>
              <span className="badge-blue text-[9px]">{genreLabel(ad.genre)}</span>
              {ad.estimation_method === "audience_based" && (
                <span className="badge text-[8px] bg-green-100 text-green-700">実データ</span>
              )}
              {showMeta ? (
                <>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-[9px] text-slate-700">
                    metrics {formatMetaSource(ad.metric_source)}
                  </span>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-[9px] text-slate-700">
                    creative {formatMetaSource(ad.creative_source)}
                  </span>
                  {!ad.destination_url ? (
                    <span className="rounded bg-gray-100 px-2 py-0.5 text-[9px] text-gray-600">LP missing</span>
                  ) : null}
                  {ad.meta_recovery_reason ? (
                    <span className="rounded bg-rose-50 px-2 py-0.5 text-[9px] text-rose-700">
                      {ad.meta_recovery_reason.replaceAll("_", " ")}
                    </span>
                  ) : null}
                </>
              ) : null}
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2 mt-auto pt-2 border-t border-gray-100">
              {ad.destination_url && (
                <>
                  <button
                    className="text-[10px] px-2 py-1 rounded bg-gray-50 text-[#4A7DFF] hover:bg-blue-50 transition-colors"
                    onClick={(e) => {
                      e.stopPropagation();
                      window.open(ad.destination_url, "_blank", "noopener,noreferrer");
                    }}
                  >
                    LP確認
                  </button>
                  <button
                    className="text-[10px] px-2 py-1 rounded bg-purple-50 text-purple-600 hover:bg-purple-100 transition-colors"
                    onClick={(e) => {
                      e.stopPropagation();
                      fetchApi("/lp-analysis/crawl", {
                        method: "POST",
                        body: { url: ad.destination_url, ad_id: ad.ad_id, auto_analyze: true },
                      })
                        .then(() => toast.success("LP分析を開始しました"))
                        .catch(() => toast.error("LP分析の開始に失敗しました"));
                    }}
                  >
                    LP分析
                  </button>
                </>
              )}
              <button
                className="text-[10px] px-1.5 py-1 rounded hover:bg-amber-50 text-gray-400 hover:text-amber-500 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  fetchApi("/rankings/bookmarks", { method: "POST", body: { ad_id: ad.ad_id } })
                    .then(() => toast.success("ブックマークに追加しました"))
                    .catch(() => toast.error("ブックマーク追加に失敗しました"));
                }}
                title="ブックマーク"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
                </svg>
              </button>
              <button
                className="text-[10px] px-2 py-1 rounded bg-emerald-50 text-emerald-600 hover:bg-emerald-100 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(`/api/v1/media/download/${ad.ad_id}`, "_blank", "noopener,noreferrer");
                }}
                title="クリエイティブをダウンロード"
              >
                DL
              </button>
              <button
                className="text-[10px] px-2 py-1 rounded bg-gray-50 text-gray-600 hover:bg-gray-100 transition-colors ml-auto"
                onClick={(e) => {
                  e.stopPropagation();
                  onAdSelect(ad.ad_id);
                }}
              >
                詳細
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
