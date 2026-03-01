"use client";

import React, { useState, useEffect, useMemo } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { platformLabels, platformColors, platformBadgeColors, genreOptions } from "@/lib/constants";
import { formatNumber, formatYen, copyToClipboard } from "@/lib/format";
import { CreativeViewer } from "../common/CreativeViewer";
import SimilarAdsPanel from "./SimilarAdsPanel";
import CreativeIntelligence from "./CreativeIntelligence";
import HitPrediction from "./HitPrediction";
import AdAnnotations from "./AdAnnotations";

// Signal label & color constants (shared with HitAdAnalysisView)
const signalLabels: Record<string, string> = {
  longevity: "配信継続力",
  spend: "消化額",
  active_bonus: "配信中ボーナス",
  creative: "クリエイティブ",
  trend: "トレンド",
};
const signalColors: Record<string, string> = {
  longevity: "#3b82f6",
  spend: "#22c55e",
  active_bonus: "#f97316",
  creative: "#a855f7",
  trend: "#ec4899",
};

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
  previous_rank: number | null;
  thumbnail: string;
  duration_seconds: number;
  image_url: string;
  snapshot_url: string;
  destination_url: string;
  destination_type: string;
  like_count: number;
  published_date: string;
  management_id: string;
  ad_url: string;
  description: string;
  title: string;
  days_running?: number;
  is_still_running?: boolean;
  hit_level?: string;
  video_url?: string;
  creative_type?: string;
  estimation_method?: string;
  score_breakdown?: Record<string, number>;
}

interface AdDetailModalProps {
  ad: HitAd;
  onClose: () => void;
  onAdSelect: (adId: number) => void;
}

interface ScoreBreakdownData {
  hit_score?: number;
  signals?: Record<string, { score: number; max: number; detail?: string }>;
}

const genreLabel = (value: string | null | undefined): string => {
  if (!value || value === "未分類") return "未分類";
  return genreOptions.find((g) => g.value === value)?.label || value;
};

// B8: Creative DNA types and labels
interface CreativeDNA {
  ad_id: number;
  hook_type?: string;
  cta_type?: string;
  offer_type?: string;
  emotion?: string;
  text_features?: string[];
  pattern_hit_rate?: number;
  pattern_count?: number;
  similar_hit_ads?: Array<{ ad_id: number; product_name?: string; hit_score?: number }>;
}

const dnaHookLabels: Record<string, string> = {
  question: "質問型", pain_point: "悩み訴求", benefit: "ベネフィット", curiosity: "好奇心",
  social_proof: "社会的証明", urgency: "緊急性", storytelling: "ストーリー", number: "数字訴求",
  comparison: "比較", authority: "権威性", shock: "衝撃・驚き", empathy: "共感型",
};
const dnaCtaLabels: Record<string, string> = {
  purchase: "購入", consultation: "無料相談", free_trial: "無料お試し", line_add: "LINE追加",
  download: "ダウンロード", register: "会員登録", inquiry: "問い合わせ", reserve: "予約", learn_more: "詳しく見る",
};
const dnaOfferLabels: Record<string, string> = {
  discount: "割引", free: "無料", limited_time: "期間限定", bonus: "特典付き",
  guarantee: "返金保証", comparison: "比較", trial: "お試し", bundle: "セット", exclusive: "限定",
};
const dnaEmotionLabels: Record<string, string> = {
  fear: "不安", hope: "希望", anger: "怒り", joy: "喜び", surprise: "驚き",
  trust: "信頼", desire: "欲望", relief: "安心", curiosity: "好奇心",
};
const dnaFeatureLabels: Record<string, string> = {
  has_numbers: "数字あり", has_emoji: "絵文字あり", has_testimonial: "体験談あり",
  has_question: "疑問文あり", has_urgency: "緊急性あり", has_price: "価格表示あり",
  has_comparison: "比較表現", has_guarantee: "保証あり", has_social_proof: "社会的証明",
};

export default function AdDetailModal({ ad, onClose, onAdSelect }: AdDetailModalProps) {
  const [scoreBreakdown, setScoreBreakdown] = useState<ScoreBreakdownData | null>(null);
  const [scoreLoading, setScoreLoading] = useState(false);

  // B8: Creative DNA state
  const [creativeDna, setCreativeDna] = useState<CreativeDNA | null>(null);
  const [dnaLoading, setDnaLoading] = useState(false);

  // Fetch score breakdown + creative DNA on mount
  useEffect(() => {
    let cancelled = false;
    setScoreLoading(true);
    fetchApi<ScoreBreakdownData>(`/rankings/score-breakdown/${ad.ad_id}`)
      .then((data) => {
        if (!cancelled) setScoreBreakdown(data);
      })
      .catch(() => {
        if (!cancelled) setScoreBreakdown(null);
      })
      .finally(() => {
        if (!cancelled) setScoreLoading(false);
      });

    // B8: Fetch creative DNA
    setDnaLoading(true);
    fetchApi<CreativeDNA>(`/rankings/creative-dna/${ad.ad_id}`)
      .then((data) => {
        if (!cancelled) setCreativeDna(data);
      })
      .catch(() => {
        if (!cancelled) setCreativeDna(null);
      })
      .finally(() => {
        if (!cancelled) setDnaLoading(false);
      });

    return () => { cancelled = true; };
  }, [ad.ad_id]);

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const scoreColor =
    (ad.hit_score || 0) >= 80 ? "#ef4444" : (ad.hit_score || 0) >= 50 ? "#f59e0b" : "#4A7DFF";

  const pLabel = platformLabels[ad.platform] || ad.platform;
  const pBadge = platformBadgeColors[ad.platform] || "bg-gray-100 text-gray-800";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl max-h-[90vh] rounded-xl bg-white shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <span
              className={`shrink-0 inline-flex items-center justify-center w-7 h-7 rounded text-xs font-bold ${
                ad.rank <= 3 ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-500"
              }`}
            >
              {ad.rank}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-[15px] font-bold text-gray-900 truncate">
                  {ad.product_name || ad.title || "不明"}
                </h2>
                {ad.hit_level === "mega_hit" ? (
                  <span className="shrink-0 rounded bg-red-100 text-red-700 px-1.5 py-0.5 text-[9px] font-bold">
                    大HIT
                  </span>
                ) : ad.hit_level === "hit" ? (
                  <span className="shrink-0 rounded bg-orange-100 text-orange-700 px-1.5 py-0.5 text-[9px] font-bold">
                    HIT
                  </span>
                ) : null}
              </div>
              <p className="text-[11px] text-gray-400 truncate">{ad.advertiser_name || "-"}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-100 transition-colors text-gray-400 hover:text-gray-600"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-5">
          {/* Creative + Score Side by Side on desktop, stacked on mobile */}
          <div className="flex flex-col md:flex-row gap-5">
            {/* Creative viewer */}
            <div className="w-full md:w-1/2">
              <CreativeViewer
                imageUrl={ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.image_url || ad.thumbnail || null)}
                videoUrl={ad.ad_id ? `/api/v1/media/video/${ad.ad_id}` : (ad.video_url || null)}
                snapshotUrl={ad.snapshot_url || null}
                thumbnailUrl={ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || null)}
                creativeType={ad.creative_type || null}
              />
            </div>

            {/* Score & Key Info */}
            <div className="w-full md:w-1/2 space-y-4">
              {/* Hit Score */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[11px] text-gray-400 font-medium">ヒットスコア</span>
                  <span className="text-[18px] font-bold" style={{ color: scoreColor }}>
                    {ad.hit_score || 0}<span className="text-[11px] text-gray-400 ml-1">/ 100</span>
                  </span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${ad.hit_score || 0}%`, backgroundColor: scoreColor }}
                  />
                </div>
              </div>

              {/* Score Breakdown */}
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-[11px] text-gray-500 font-medium mb-2">スコア内訳</p>
                {scoreLoading ? (
                  <div className="flex items-center justify-center py-3">
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
                    <span className="ml-2 text-[10px] text-gray-400">読み込み中...</span>
                  </div>
                ) : scoreBreakdown?.signals ? (
                  <div className="space-y-2">
                    {Object.entries(scoreBreakdown.signals).map(([key, sig]) => (
                      <div key={key}>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] w-20 text-gray-500 shrink-0">{signalLabels[key] || key}</span>
                          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${sig.max > 0 ? (sig.score / sig.max) * 100 : 0}%`,
                                backgroundColor: signalColors[key] || "#6b7280",
                              }}
                            />
                          </div>
                          <span className="text-[10px] text-gray-600 w-10 text-right shrink-0">
                            {sig.score}/{sig.max}
                          </span>
                        </div>
                        {sig.detail && (
                          <p className="text-[9px] text-gray-400 ml-[88px] mt-0.5">{sig.detail}</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : ad.score_breakdown ? (
                  <div className="space-y-2">
                    {Object.entries(ad.score_breakdown).map(([key, val]) => {
                      const maxMap: Record<string, number> = { longevity: 40, spend: 20, active_bonus: 20, creative: 10, trend: 10 };
                      const mx = maxMap[key] || 20;
                      return (
                        <div key={key} className="flex items-center gap-2">
                          <span className="text-[10px] w-20 text-gray-500 shrink-0">{signalLabels[key] || key}</span>
                          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${mx > 0 ? (val / mx) * 100 : 0}%`,
                                backgroundColor: signalColors[key] || "#6b7280",
                              }}
                            />
                          </div>
                          <span className="text-[10px] text-gray-600 w-10 text-right shrink-0">
                            {val}/{mx}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-[10px] text-gray-400">内訳データなし</p>
                )}
              </div>

              {/* Tags */}
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ${pBadge}`}>
                  {pLabel}
                </span>
                <span className="badge-blue text-[10px]">{genreLabel(ad.genre)}</span>
                {ad.creative_type && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] bg-gray-100 text-gray-600">
                    {ad.creative_type === "video" ? "動画" : ad.creative_type === "image" ? "静止画" : ad.creative_type}
                  </span>
                )}
                {ad.estimation_method === "audience_based" && (
                  <span className="badge text-[9px] bg-green-100 text-green-700">実データ</span>
                )}
              </div>
            </div>
          </div>

          {/* Full description */}
          {(ad.title || ad.description) && (
            <div className="bg-gray-50 rounded-lg p-4">
              {ad.title && (
                <h3 className="text-[13px] font-semibold text-gray-900 mb-1">{ad.title}</h3>
              )}
              {ad.description && (
                <p className="text-[12px] text-gray-600 leading-relaxed whitespace-pre-wrap">
                  {ad.description}
                </p>
              )}
            </div>
          )}

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <MetricCard label="消化額増加 (週)" value={formatYen(ad.spend_increase || 0)} />
            <MetricCard label="累計推定消化額" value={formatYen(ad.cumulative_spend || 0)} />
            <MetricCard label="再生数増加 (週)" value={formatNumber(ad.view_increase || 0)} />
            <MetricCard label="累計再生数" value={formatNumber(ad.cumulative_views || 0)} />
            <MetricCard label="いいね数" value={formatNumber(ad.like_count || 0)} />
            <MetricCard label="トレンドスコア" value={String(ad.trend_score || 0)} />
          </div>

          {/* Meta Information */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <MetaItem label="配信日数">
              <div className="flex items-center gap-1.5">
                <span className="text-[13px] font-semibold text-gray-900">
                  {ad.days_running != null ? `${ad.days_running}日` : "-"}
                </span>
                {ad.is_still_running && (
                  <span className="text-[10px] text-emerald-600 font-medium">● 配信中</span>
                )}
                {ad.is_still_running === false && (
                  <span className="text-[10px] text-gray-400">○ 終了</span>
                )}
              </div>
            </MetaItem>
            <MetaItem label="クリエイティブタイプ">
              <span className="text-[13px] text-gray-900">
                {ad.creative_type === "video" ? "動画" : ad.creative_type === "image" ? "静止画" : ad.creative_type || "-"}
              </span>
            </MetaItem>
            <MetaItem label="秒数">
              <span className="text-[13px] text-gray-900">
                {ad.duration_seconds > 0 ? `${ad.duration_seconds}秒` : "-"}
              </span>
            </MetaItem>
            <MetaItem label="掲載開始">
              <span className="text-[13px] text-gray-900">
                {ad.published_date ? new Date(ad.published_date).toLocaleDateString("ja-JP") : "-"}
              </span>
            </MetaItem>
            <MetaItem label="遷移先タイプ">
              <span className="text-[13px] text-gray-900">
                {ad.destination_type || "-"}
              </span>
            </MetaItem>
            <MetaItem label="管理番号">
              <span className="text-[13px] text-gray-900 font-mono">
                {ad.management_id || "-"}
              </span>
            </MetaItem>
          </div>

          {/* B6-2: LP Destination Info Section (enhanced) */}
          {ad.destination_url && (
            <div className="bg-blue-50/60 rounded-lg px-4 py-3 space-y-2">
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-[#4A7DFF] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                </svg>
                <p className="text-[12px] font-bold text-gray-900">LP遷移先</p>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-medium">
                  {(() => { try { return new URL(ad.destination_url).hostname.replace(/^www\./, ""); } catch { return "-"; } })()}
                </span>
                {ad.destination_type && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">{ad.destination_type}</span>
                )}
              </div>
              {/* Full URL */}
              <a
                href={ad.destination_url}
                target="_blank"
                rel="noopener noreferrer"
                className="block text-[11px] text-[#4A7DFF] hover:underline break-all leading-relaxed"
                onClick={(e) => e.stopPropagation()}
              >
                {ad.destination_url}
              </a>
              {/* Action buttons row */}
              <div className="flex items-center gap-2 pt-0.5">
                <button
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#4A7DFF] text-white text-[11px] font-medium hover:bg-[#3a6ae8] transition-colors"
                  onClick={(e) => { e.stopPropagation(); window.open(ad.destination_url, "_blank", "noopener,noreferrer"); }}
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                  </svg>
                  LPを開く
                </button>
                <button
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-50 text-purple-600 text-[11px] font-medium hover:bg-purple-100 transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    fetchApi("/lp-analysis/crawl", {
                      method: "POST",
                      body: { url: ad.destination_url, ad_id: ad.ad_id, auto_analyze: true },
                    })
                      .then(() => { toast.success("LP分析を開始しました"); })
                      .catch(() => { toast.error("LP分析の開始に失敗しました"); });
                  }}
                >
                  LP分析を実行
                </button>
                <button
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-white/80 text-gray-600 text-[11px] hover:bg-white transition-colors border border-gray-200"
                  onClick={(e) => {
                    e.stopPropagation();
                    copyToClipboard(ad.destination_url).then(() => toast.success("URLをコピーしました"));
                  }}
                  title="URLをコピー"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                  </svg>
                  コピー
                </button>
              </div>
            </div>
          )}

          {/* B15: LP Screenshot Preview */}
          {ad.destination_url && (
            <div className="space-y-2">
              <p className="text-[10px] text-gray-400">LPプレビュー</p>
              <div className="relative aspect-[3/2] bg-gray-100 rounded-lg overflow-hidden group cursor-pointer"
                onClick={() => window.open(`/api/v1/media/lp-screenshot/${ad.ad_id}`, "_blank", "noopener,noreferrer")}
              >
                <img
                  src={`/api/v1/media/lp-screenshot/${ad.ad_id}`}
                  alt="LP Screenshot"
                  className="w-full h-full object-cover object-top group-hover:opacity-90 transition-opacity"
                  loading="lazy"
                  onError={(e) => { (e.target as HTMLImageElement).parentElement!.style.display = "none"; }}
                />
                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/10">
                  <svg className="w-6 h-6 text-white drop-shadow" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM10.5 7.5v6m3-3h-6" />
                  </svg>
                </div>
              </div>
            </div>
          )}

          {/* Rank Change */}
          {ad.rank_change !== null && ad.rank_change !== undefined && (
            <div className="flex items-center gap-3 bg-gray-50 rounded-lg px-4 py-2">
              <span className="text-[11px] text-gray-400">順位変動</span>
              {ad.rank_change > 0 ? (
                <span className="text-emerald-600 text-[13px] font-semibold">
                  ↑{ad.rank_change} ランクアップ
                </span>
              ) : ad.rank_change < 0 ? (
                <span className="text-red-500 text-[13px] font-semibold">
                  ↓{Math.abs(ad.rank_change)} ランクダウン
                </span>
              ) : (
                <span className="text-gray-400 text-[13px]">→ 変動なし</span>
              )}
              {ad.previous_rank != null && (
                <span className="text-[10px] text-gray-400 ml-auto">前回: {ad.previous_rank}位</span>
              )}
            </div>
          )}

          {/* B8: Creative DNA Section */}
          {dnaLoading ? (
            <div className="bg-indigo-50/50 rounded-lg px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
                <span className="text-[11px] text-gray-400">クリエイティブ分析を読み込み中...</span>
              </div>
            </div>
          ) : creativeDna && (creativeDna.hook_type || creativeDna.cta_type || creativeDna.offer_type || creativeDna.emotion || (creativeDna.text_features && creativeDna.text_features.length > 0)) ? (
            <div className="bg-indigo-50/50 rounded-lg px-4 py-3 space-y-3">
              <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-indigo-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
                </svg>
                <p className="text-[12px] font-bold text-gray-900">クリエイティブ分析</p>
              </div>

              {/* DNA badges */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {creativeDna.hook_type && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 text-blue-700">
                    フック: {dnaHookLabels[creativeDna.hook_type] || creativeDna.hook_type}
                  </span>
                )}
                {creativeDna.cta_type && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-green-100 text-green-700">
                    CTA: {dnaCtaLabels[creativeDna.cta_type] || creativeDna.cta_type}
                  </span>
                )}
                {creativeDna.offer_type && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-orange-100 text-orange-700">
                    オファー: {dnaOfferLabels[creativeDna.offer_type] || creativeDna.offer_type}
                  </span>
                )}
                {creativeDna.emotion && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-pink-100 text-pink-700">
                    感情: {dnaEmotionLabels[creativeDna.emotion] || creativeDna.emotion}
                  </span>
                )}
              </div>

              {/* Text features */}
              {creativeDna.text_features && creativeDna.text_features.length > 0 && (
                <div className="flex items-center gap-1 flex-wrap">
                  {creativeDna.text_features.map((feat) => (
                    <span key={feat} className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] bg-gray-100 text-gray-600">
                      {dnaFeatureLabels[feat] || feat}
                    </span>
                  ))}
                </div>
              )}

              {/* Pattern hit rate */}
              {creativeDna.pattern_hit_rate != null && (
                <div className="flex items-center gap-3 bg-white/70 rounded-lg px-3 py-2">
                  <span className="text-[10px] text-gray-500">このパターンのヒット率</span>
                  <span className="text-[15px] font-bold" style={{
                    color: (typeof creativeDna.pattern_hit_rate === "number" && creativeDna.pattern_hit_rate <= 1
                      ? creativeDna.pattern_hit_rate * 100
                      : creativeDna.pattern_hit_rate) >= 70
                      ? "#22c55e"
                      : (typeof creativeDna.pattern_hit_rate === "number" && creativeDna.pattern_hit_rate <= 1
                        ? creativeDna.pattern_hit_rate * 100
                        : creativeDna.pattern_hit_rate) >= 45
                        ? "#f59e0b"
                        : "#4A7DFF",
                  }}>
                    {typeof creativeDna.pattern_hit_rate === "number" && creativeDna.pattern_hit_rate <= 1
                      ? Math.round(creativeDna.pattern_hit_rate * 100)
                      : Math.round(creativeDna.pattern_hit_rate)}%
                  </span>
                  {creativeDna.pattern_count != null && (
                    <span className="text-[9px] text-gray-400">{creativeDna.pattern_count}件中</span>
                  )}
                </div>
              )}

              {/* Similar hit ads */}
              {creativeDna.similar_hit_ads && creativeDna.similar_hit_ads.length > 0 && (
                <div>
                  <p className="text-[10px] text-gray-500 font-medium mb-1.5">同パターンのヒット広告</p>
                  <div className="flex flex-wrap gap-1.5">
                    {creativeDna.similar_hit_ads.slice(0, 6).map((sim) => (
                      <button
                        key={sim.ad_id}
                        className="text-[9px] px-2 py-1 rounded bg-white text-indigo-600 hover:bg-indigo-50 transition-colors truncate max-w-[180px] border border-indigo-200"
                        onClick={(e) => {
                          e.stopPropagation();
                          onAdSelect(sim.ad_id);
                        }}
                        title={sim.product_name || `#${sim.ad_id}`}
                      >
                        {sim.product_name || `#${sim.ad_id}`}
                        {sim.hit_score != null && ` (${sim.hit_score})`}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* B14: AI Creative Intelligence */}
        <div className="px-5 pb-2">
          <CreativeIntelligence adId={ad.ad_id} />
        </div>

        {/* B14: Hit Prediction */}
        <div className="px-5 pb-2">
          <HitPrediction adId={ad.ad_id} />
        </div>

        {/* B12: Similar Ads Panel */}
        <div className="px-5 pb-2">
          <SimilarAdsPanel adId={ad.ad_id} onAdSelect={onAdSelect} />
        </div>

        {/* B26: Ad Annotations */}
        <div className="px-5 pb-2">
          <AdAnnotations adId={ad.ad_id} />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-gray-200 bg-gray-50 shrink-0 flex-wrap gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            {ad.destination_url && (
              <button
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#4A7DFF] text-white text-[12px] font-medium hover:bg-[#3a6ae8] transition-colors"
                onClick={() => window.open(ad.destination_url, "_blank", "noopener,noreferrer")}
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                </svg>
                LPを見る
              </button>
            )}
            {ad.ad_url && (
              <button
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 text-[12px] font-medium hover:bg-gray-200 transition-colors"
                onClick={() => window.open(ad.ad_url, "_blank", "noopener,noreferrer")}
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                </svg>
                広告を確認
              </button>
            )}
            {ad.destination_url && (
              <button
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-50 text-purple-600 text-[12px] font-medium hover:bg-purple-100 transition-colors"
                onClick={() => {
                  fetchApi("/lp-analysis/crawl", {
                    method: "POST",
                    body: { url: ad.destination_url, ad_id: ad.ad_id, auto_analyze: true },
                  }).catch(() => {});
                }}
              >
                LP分析
              </button>
            )}
            {/* B13: Bookmark button */}
            <button
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-50 text-amber-600 text-[12px] font-medium hover:bg-amber-100 transition-colors"
              onClick={() => {
                fetchApi("/rankings/bookmarks", { method: "POST", body: { ad_id: ad.ad_id } })
                  .then(() => toast.success("ブックマークに追加しました"))
                  .catch(() => toast.error("ブックマーク追加に失敗しました"));
              }}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
              </svg>
              ブックマーク
            </button>
            {/* B10-2: Download button */}
            <button
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-600 text-[12px] font-medium hover:bg-emerald-100 transition-colors"
              onClick={() => window.open(`/api/v1/media/download/${ad.ad_id}`, "_blank", "noopener,noreferrer")}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              ダウンロード
            </button>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg text-[12px] font-medium text-gray-600 hover:bg-gray-200 transition-colors"
          >
            閉じる
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Sub-components ─── */

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-50 rounded-lg px-3 py-2.5">
      <p className="text-[10px] text-gray-400 font-medium">{label}</p>
      <p className="text-[15px] font-bold text-gray-900 mt-0.5">{value}</p>
    </div>
  );
}

function MetaItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="px-3 py-2">
      <p className="text-[10px] text-gray-400 mb-0.5">{label}</p>
      {children}
    </div>
  );
}
