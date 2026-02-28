"use client";

import React, { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { formatYen } from "@/lib/format";

interface CompetitorData {
  name: string;
  ad_count?: number;
  hit_count?: number;
  hit_rate?: number;
  avg_score?: number;
  total_spend?: number;
  genres?: { genre: string; count: number }[];
  strategy_timeline?: { period: string; hook_type?: string; cta_type?: string; avg_score?: number }[];
  hit_rate_trend?: { period: string; hit_rate: number }[];
  ads?: { ad_id: number; product_name?: string; hit_score?: number; thumbnail?: string; published_date?: string; creative_type?: string }[];
}

interface CompetitorProfileProps {
  name: string;
  onBack: () => void;
  onAdSelect?: (adId: number) => void;
}

const hookLabels: Record<string, string> = {
  question: "質問型", pain_point: "悩み訴求", benefit: "ベネフィット",
  curiosity: "好奇心", social_proof: "社会的証明", urgency: "緊急性",
  storytelling: "ストーリー", number: "数字訴求",
};

const ctaLabels: Record<string, string> = {
  purchase: "購入", signup: "会員登録", download: "ダウンロード",
  inquiry: "問い合わせ", learn_more: "詳しく見る", free_trial: "無料体験",
};

export default function CompetitorProfile({ name, onBack, onAdSelect }: CompetitorProfileProps) {
  const [data, setData] = useState<CompetitorData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchApi<CompetitorData>(`/rankings/competitor/${encodeURIComponent(name)}`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [name]);

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-40" />
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-20 bg-gray-100 rounded-lg" />)}
        </div>
        <div className="h-40 bg-gray-100 rounded-lg" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <button onClick={onBack} className="text-[11px] px-2 py-1 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors flex items-center gap-1">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          戻る
        </button>
        <div className="card px-4 py-8 text-center">
          <p className="text-[11px] text-gray-400">競合データが見つかりませんでした</p>
        </div>
      </div>
    );
  }

  const genres = data.genres || [];
  const maxGenreCount = Math.max(1, ...genres.map((g) => g.count));
  const timeline = data.strategy_timeline || [];
  const hitTrend = data.hit_rate_trend || [];
  const ads = data.ads || [];
  const maxTrend = Math.max(1, ...hitTrend.map((h) => h.hit_rate));

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <button onClick={onBack} className="text-[11px] px-2 py-1 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors flex items-center gap-1">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          戻る
        </button>
        <h3 className="text-[14px] font-bold text-gray-900">{data.name}</h3>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card px-3 py-2.5">
          <p className="text-[9px] text-gray-400">広告数</p>
          <p className="text-[18px] font-bold text-gray-900">{data.ad_count || 0}</p>
        </div>
        <div className="card px-3 py-2.5">
          <p className="text-[9px] text-gray-400">HIT数</p>
          <p className="text-[18px] font-bold text-emerald-600">{data.hit_count || 0}</p>
        </div>
        <div className="card px-3 py-2.5">
          <p className="text-[9px] text-gray-400">HIT率</p>
          <p className="text-[18px] font-bold text-[#4A7DFF]">{data.hit_rate != null ? Math.round(data.hit_rate) : 0}%</p>
        </div>
        <div className="card px-3 py-2.5">
          <p className="text-[9px] text-gray-400">推定消化額</p>
          <p className="text-[14px] font-bold text-gray-900">{data.total_spend != null ? formatYen(data.total_spend) : "-"}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Genre distribution */}
        {genres.length > 0 && (
          <div className="card px-4 py-3">
            <h4 className="text-[11px] font-bold text-gray-900 mb-2">ジャンル分布</h4>
            <div className="space-y-1.5">
              {genres.slice(0, 8).map((g, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-[9px] text-gray-600 w-16 truncate shrink-0">{g.genre}</span>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-[#4A7DFF] transition-all"
                      style={{ width: `${(g.count / maxGenreCount) * 100}%` }}
                    />
                  </div>
                  <span className="text-[9px] text-gray-400 w-6 text-right shrink-0">{g.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Hit rate trend */}
        {hitTrend.length > 0 && (
          <div className="card px-4 py-3">
            <h4 className="text-[11px] font-bold text-gray-900 mb-2">HIT率推移</h4>
            <div className="flex items-end gap-1 h-20">
              {hitTrend.map((h, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                  <span className="text-[7px] text-gray-400">{Math.round(h.hit_rate)}%</span>
                  <div className="w-full bg-gray-100 rounded-t relative" style={{ height: `${(h.hit_rate / maxTrend) * 100}%`, minHeight: "2px" }}>
                    <div className="absolute inset-0 rounded-t bg-[#4A7DFF] opacity-80" />
                  </div>
                  <span className="text-[6px] text-gray-400 truncate w-full text-center">{h.period}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Strategy timeline */}
      {timeline.length > 0 && (
        <div className="card px-4 py-3">
          <h4 className="text-[11px] font-bold text-gray-900 mb-2">戦略タイムライン</h4>
          <div className="space-y-2">
            {timeline.map((t, i) => (
              <div key={i} className="flex items-center gap-3 py-1 border-b border-gray-50 last:border-0">
                <span className="text-[9px] text-gray-400 w-16 shrink-0">{t.period}</span>
                <div className="flex items-center gap-1 flex-wrap flex-1">
                  {t.hook_type && (
                    <span className="text-[8px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
                      {hookLabels[t.hook_type] || t.hook_type}
                    </span>
                  )}
                  {t.cta_type && (
                    <span className="text-[8px] px-1.5 py-0.5 rounded bg-green-100 text-green-700">
                      {ctaLabels[t.cta_type] || t.cta_type}
                    </span>
                  )}
                </div>
                {t.avg_score != null && (
                  <span className="text-[10px] font-medium text-gray-700 shrink-0">{Math.round(t.avg_score)}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ads gallery */}
      {ads.length > 0 && (
        <div>
          <h4 className="text-[11px] font-bold text-gray-900 mb-2">広告一覧 ({ads.length}件)</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {ads.map((ad) => {
              const thumbSrc = ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || "");
              return (
                <div
                  key={ad.ad_id}
                  className="card overflow-hidden cursor-pointer hover:shadow-md transition-all group"
                  onClick={() => onAdSelect?.(ad.ad_id)}
                >
                  <div className="relative aspect-video bg-gray-100 overflow-hidden">
                    {thumbSrc && (
                      <img
                        src={thumbSrc} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform" loading="lazy"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                    )}
                    {ad.hit_score != null && (
                      <span className="absolute top-1 right-1 text-[8px] px-1 py-0.5 rounded bg-black/60 text-white font-bold">{ad.hit_score}</span>
                    )}
                  </div>
                  <div className="px-2 py-1.5">
                    <p className="text-[10px] font-medium text-gray-900 truncate">{ad.product_name || "不明"}</p>
                    {ad.published_date && <p className="text-[8px] text-gray-400">{ad.published_date.slice(0, 10)}</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
