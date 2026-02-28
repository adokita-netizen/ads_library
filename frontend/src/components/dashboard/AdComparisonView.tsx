"use client";

import React, { useState, useEffect, useMemo } from "react";
import { fetchApi } from "@/lib/api";
import { platformLabels, platformColors } from "@/lib/constants";
import { formatNumber, formatYen } from "@/lib/format";

interface ComparedAd {
  ad_id: number;
  product_name?: string;
  title?: string;
  advertiser_name?: string;
  platform?: string;
  genre?: string;
  hit_score?: number;
  hit_level?: string;
  trend_score?: number;
  days_running?: number;
  is_still_running?: boolean;
  spend_increase?: number;
  cumulative_spend?: number;
  view_increase?: number;
  cumulative_views?: number;
  like_count?: number;
  creative_type?: string;
  hook_type?: string;
  cta_type?: string;
  offer_type?: string;
  emotion?: string;
  thumbnail?: string;
  image_url?: string;
  video_url?: string;
  snapshot_url?: string;
  destination_url?: string;
  description?: string;
}

interface CompareResult {
  ads: ComparedAd[];
  comparison?: {
    best_score_ad?: number;
    best_longevity_ad?: number;
    best_spend_ad?: number;
  };
}

interface AdComparisonViewProps {
  adIds: number[];
  onClose: () => void;
  onAdSelect?: (adId: number) => void;
  inline?: boolean;
}

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

const emotionLabels: Record<string, string> = {
  fear: "不安", hope: "希望", anger: "怒り", joy: "喜び",
  surprise: "驚き", trust: "信頼", desire: "欲望", relief: "安心", curiosity: "好奇心",
};

export default function AdComparisonView({ adIds, onClose, onAdSelect, inline }: AdComparisonViewProps) {
  const [ads, setAds] = useState<ComparedAd[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchApi<CompareResult | ComparedAd[]>("/rankings/compare", {
          method: "POST",
          body: { ad_ids: adIds },
        });
        if (Array.isArray(res)) {
          setAds(res);
        } else if (res?.ads) {
          setAds(res.ads);
        } else {
          setAds([]);
        }
      } catch {
        setError("比較データの取得に失敗しました");
      } finally {
        setLoading(false);
      }
    };
    if (adIds.length >= 2) load();
  }, [adIds]);

  // Determine best values for highlighting
  const bestScore = useMemo(() => Math.max(...ads.map((a) => a.hit_score || 0)), [ads]);
  const bestDays = useMemo(() => Math.max(...ads.map((a) => a.days_running || 0)), [ads]);
  const bestSpend = useMemo(() => Math.max(...ads.map((a) => a.spend_increase || 0)), [ads]);
  const bestViews = useMemo(() => Math.max(...ads.map((a) => a.view_increase || 0)), [ads]);
  const maxScore = useMemo(() => Math.max(1, ...ads.map((a) => a.hit_score || 0)), [ads]);

  // Detect possible A/B test
  const abTestPairs = useMemo(() => {
    const pairs: Array<{ a: ComparedAd; b: ComparedAd }> = [];
    for (let i = 0; i < ads.length; i++) {
      for (let j = i + 1; j < ads.length; j++) {
        const a = ads[i], b = ads[j];
        if (
          a.advertiser_name && b.advertiser_name &&
          a.advertiser_name === b.advertiser_name
        ) {
          // Same advertiser - possible A/B test
          const titleA = (a.product_name || a.title || "").toLowerCase();
          const titleB = (b.product_name || b.title || "").toLowerCase();
          // Check similarity: same first 5 chars or share 50%+ of words
          const wordsA = titleA.split(/\s+/);
          const wordsB = titleB.split(/\s+/);
          const commonWords = wordsA.filter((w) => wordsB.includes(w));
          const similarity = Math.max(wordsA.length, wordsB.length) > 0
            ? commonWords.length / Math.max(wordsA.length, wordsB.length)
            : 0;
          if (similarity >= 0.3 || titleA.slice(0, 5) === titleB.slice(0, 5)) {
            pairs.push({ a, b });
          }
        }
      }
    }
    return pairs;
  }, [ads]);

  const content = (
    <>
      {/* Header */}
      {!inline && (
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <svg className="w-4.5 h-4.5 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
            </svg>
            <h2 className="text-[15px] font-bold text-gray-900">広告比較</h2>
            <span className="text-[11px] text-gray-400">{adIds.length}件の広告を並列比較</span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors p-1">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

        {/* A/B test detection badges */}
        {abTestPairs.length > 0 && (
          <div className="px-5 py-2 bg-amber-50 border-b border-amber-100">
            {abTestPairs.map((pair, i) => {
              const winner = (pair.a.hit_score || 0) >= (pair.b.hit_score || 0) ? pair.a : pair.b;
              const loser = winner === pair.a ? pair.b : pair.a;
              return (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-200 text-amber-800 font-bold">A/Bテスト検出</span>
                  <span className="text-[10px] text-amber-700">
                    同一広告主「{pair.a.advertiser_name}」 - 勝者:
                    <span className="font-bold text-emerald-700 ml-1">
                      {winner.product_name || winner.title} (スコア {winner.hit_score || 0})
                    </span>
                    <span className="text-gray-500 ml-1">
                      vs {loser.product_name || loser.title} ({loser.hit_score || 0})
                    </span>
                  </span>
                </div>
              );
            })}
          </div>
        )}

      {/* Content */}
      <div className={inline ? "py-2" : "flex-1 overflow-auto px-5 py-4"}>
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <svg className="animate-spin h-6 w-6 text-[#4A7DFF]" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
          ) : error ? (
            <div className="text-center py-16">
              <p className="text-[12px] text-red-500 mb-2">{error}</p>
              <p className="text-[10px] text-gray-400">バックエンドが起動中の可能性があります</p>
            </div>
          ) : ads.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-[12px] text-gray-500">比較データがありません</p>
            </div>
          ) : (
            <div className={`grid gap-4 ${ads.length === 2 ? "grid-cols-2" : ads.length === 3 ? "grid-cols-3" : "grid-cols-2 lg:grid-cols-4"}`}>
              {ads.map((ad) => {
                const isBestScore = (ad.hit_score || 0) === bestScore && bestScore > 0;
                const isBestDays = (ad.days_running || 0) === bestDays && bestDays > 0;
                const isBestSpend = (ad.spend_increase || 0) === bestSpend && bestSpend > 0;
                const isBestViews = (ad.view_increase || 0) === bestViews && bestViews > 0;
                const thumbSrc = ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || ad.image_url || "");

                return (
                  <div key={ad.ad_id} className="border border-gray-200 rounded-xl overflow-hidden">
                    {/* Creative preview */}
                    <div className="relative aspect-video bg-gray-100">
                      {thumbSrc ? (
                        <img
                          src={thumbSrc}
                          alt=""
                          className="w-full h-full object-cover"
                          loading="lazy"
                          onError={(e) => {
                            const el = e.target as HTMLImageElement;
                            if (ad.thumbnail && el.src !== ad.thumbnail) el.src = ad.thumbnail;
                            else if (ad.image_url && el.src !== ad.image_url) el.src = ad.image_url;
                            else if (ad.snapshot_url && el.src !== ad.snapshot_url) el.src = ad.snapshot_url;
                            else el.style.display = "none";
                          }}
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full">
                          <svg className="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                        </div>
                      )}
                      {/* HIT badge */}
                      {ad.hit_level === "mega_hit" && (
                        <span className="absolute top-2 left-2 text-[9px] px-1.5 py-0.5 rounded bg-red-500 text-white font-bold">大HIT</span>
                      )}
                      {ad.hit_level === "hit" && (
                        <span className="absolute top-2 left-2 text-[9px] px-1.5 py-0.5 rounded bg-orange-500 text-white font-bold">HIT</span>
                      )}
                      {/* Creative type */}
                      {ad.creative_type && (
                        <span className="absolute top-2 right-2 text-[8px] px-1.5 py-0.5 rounded bg-black/50 text-white">
                          {ad.creative_type === "video" ? "動画" : "静止画"}
                        </span>
                      )}
                    </div>

                    <div className="px-3 py-3 space-y-2.5">
                      {/* Title */}
                      <div>
                        <p className="text-[12px] font-bold text-gray-900 truncate" title={ad.product_name || ad.title}>
                          {ad.product_name || ad.title || `Ad #${ad.ad_id}`}
                        </p>
                        <p className="text-[10px] text-gray-500 truncate">{ad.advertiser_name || "-"}</p>
                      </div>

                      {/* Score comparison bar */}
                      <div>
                        <div className="flex items-center justify-between mb-0.5">
                          <span className="text-[9px] text-gray-400">ヒットスコア</span>
                          <span className={`text-[14px] font-bold ${isBestScore ? "text-emerald-600" : "text-gray-700"}`}>
                            {ad.hit_score || 0}
                          </span>
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${maxScore > 0 ? ((ad.hit_score || 0) / maxScore) * 100 : 0}%`,
                              backgroundColor: isBestScore ? "#22c55e" : "#4A7DFF",
                            }}
                          />
                        </div>
                      </div>

                      {/* Badges */}
                      <div className="flex flex-wrap gap-1">
                        {ad.hook_type && (
                          <span className="text-[8px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
                            {hookLabels[ad.hook_type] || ad.hook_type}
                          </span>
                        )}
                        {ad.emotion && (
                          <span className="text-[8px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700">
                            {emotionLabels[ad.emotion] || ad.emotion}
                          </span>
                        )}
                        {ad.offer_type && (
                          <span className="text-[8px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                            {ad.offer_type}
                          </span>
                        )}
                        {ad.cta_type && (
                          <span className="text-[8px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">
                            {ad.cta_type}
                          </span>
                        )}
                        {ad.platform && (
                          <span className={`text-[8px] px-1.5 py-0.5 rounded platform-icon ${platformColors[ad.platform] || "bg-gray-400"}`}>
                            {platformLabels[ad.platform] || ad.platform}
                          </span>
                        )}
                      </div>

                      {/* Key metrics */}
                      <div className="grid grid-cols-2 gap-1.5">
                        <MetricCell
                          label="配信日数"
                          value={ad.days_running != null ? `${ad.days_running}日` : "-"}
                          highlight={isBestDays}
                          isRunning={ad.is_still_running}
                        />
                        <MetricCell
                          label="消化額増加"
                          value={formatYen(ad.spend_increase || 0)}
                          highlight={isBestSpend}
                        />
                        <MetricCell
                          label="再生数増加"
                          value={formatNumber(ad.view_increase || 0)}
                          highlight={isBestViews}
                        />
                        <MetricCell
                          label="トレンド"
                          value={String(ad.trend_score || 0)}
                        />
                      </div>

                      {/* View detail button */}
                      {onAdSelect && (
                        <button
                          className="w-full text-center text-[10px] py-1.5 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors font-medium"
                          onClick={() => onAdSelect(ad.ad_id)}
                        >
                          詳細を見る
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </>
  );

  if (inline) {
    return <div className="space-y-3">{content}</div>;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl max-w-[95vw] max-h-[90vh] overflow-hidden flex flex-col"
        style={{ width: ads.length > 2 ? "1200px" : "900px" }}
        onClick={(e) => e.stopPropagation()}
      >
        {content}
      </div>
    </div>
  );
}

function MetricCell({ label, value, highlight, isRunning }: {
  label: string;
  value: string;
  highlight?: boolean;
  isRunning?: boolean;
}) {
  return (
    <div className={`rounded-lg px-2 py-1.5 ${highlight ? "bg-emerald-50 border border-emerald-200" : "bg-gray-50"}`}>
      <p className="text-[8px] text-gray-400">{label}</p>
      <div className="flex items-center gap-1">
        <p className={`text-[11px] font-semibold ${highlight ? "text-emerald-700" : "text-gray-700"}`}>{value}</p>
        {isRunning && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" title="配信中" />}
        {highlight && (
          <svg className="w-3 h-3 text-emerald-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
          </svg>
        )}
      </div>
    </div>
  );
}
