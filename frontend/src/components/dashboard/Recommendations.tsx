"use client";

import React, { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface RecommendationData {
  winning_formula?: {
    hook_type?: string;
    cta_type?: string;
    offer_type?: string;
    emotion?: string;
    creative_type?: string;
    hit_rate?: number;
  };
  dos?: string[];
  donts?: string[];
  example_ads?: { ad_id: number; product_name?: string; hit_score?: number; thumbnail?: string }[];
  genre_insights?: string;
}

interface RecommendationsProps {
  genre?: string;
  onAdSelect?: (adId: number) => void;
}

const formulaLabels: Record<string, Record<string, string>> = {
  hook_type: {
    question: "質問型", pain_point: "悩み訴求", benefit: "ベネフィット",
    curiosity: "好奇心", social_proof: "社会的証明", urgency: "緊急性",
    storytelling: "ストーリー", number: "数字訴求",
  },
  cta_type: {
    purchase: "購入", signup: "会員登録", download: "ダウンロード",
    inquiry: "問い合わせ", learn_more: "詳しく見る", free_trial: "無料体験",
  },
  offer_type: {
    discount: "割引", free_trial: "無料体験", limited_time: "期間限定",
    bonus: "特典付き", guarantee: "返金保証", comparison: "比較優位",
  },
  emotion: {
    excitement: "ワクワク", fear: "不安", curiosity: "好奇心",
    trust: "安心", urgency: "焦り", empathy: "共感",
  },
};

const formulaBadgeColors: Record<string, string> = {
  hook_type: "bg-blue-100 text-blue-700",
  cta_type: "bg-green-100 text-green-700",
  offer_type: "bg-purple-100 text-purple-700",
  emotion: "bg-amber-100 text-amber-700",
  creative_type: "bg-pink-100 text-pink-700",
};

const formulaCategoryLabels: Record<string, string> = {
  hook_type: "HOOK",
  cta_type: "CTA",
  offer_type: "OFFER",
  emotion: "EMOTION",
  creative_type: "TYPE",
};

export default function Recommendations({ genre, onAdSelect }: RecommendationsProps) {
  const [data, setData] = useState<RecommendationData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (genre) params.genre = genre;
    fetchApi<RecommendationData>("/rankings/recommendations", { params })
      .then((res) => setData(res))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [genre]);

  if (loading) {
    return (
      <div className="card px-4 py-4 animate-pulse space-y-3">
        <div className="h-4 bg-gray-200 rounded w-36" />
        <div className="h-20 bg-gray-100 rounded" />
        <div className="h-16 bg-gray-100 rounded" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="card px-4 py-8 text-center">
        <svg className="w-8 h-8 text-gray-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
        </svg>
        <p className="text-[11px] text-gray-400">レコメンデーションデータがありません</p>
      </div>
    );
  }

  const formula = data.winning_formula;
  const dos = data.dos || [];
  const donts = data.donts || [];
  const examples = data.example_ads || [];

  return (
    <div className="card px-4 py-4 space-y-4">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">レコメンデーション</h3>
      </div>

      {/* Winning Formula */}
      {formula && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-bold text-[#4A7DFF]">勝ちフォーミュラ</span>
            {formula.hit_rate != null && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-white text-[#4A7DFF] font-bold">
                HIT率 {Math.round(formula.hit_rate)}%
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(["hook_type", "cta_type", "offer_type", "emotion", "creative_type"] as const).map((key) => {
              const val = formula[key];
              if (!val) return null;
              const label = formulaLabels[key]?.[val] || val;
              const badgeColor = formulaBadgeColors[key] || "bg-gray-100 text-gray-700";
              const catLabel = formulaCategoryLabels[key] || key;
              return (
                <span key={key} className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium ${badgeColor}`}>
                  <span className="text-[7px] opacity-60">{catLabel}</span>
                  {label}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Genre insights */}
      {data.genre_insights && (
        <div className="bg-gray-50 rounded-lg px-3 py-2">
          <p className="text-[10px] text-gray-600 leading-relaxed">{data.genre_insights}</p>
        </div>
      )}

      {/* Do's and Don'ts */}
      {(dos.length > 0 || donts.length > 0) && (
        <div className="grid grid-cols-2 gap-3">
          {dos.length > 0 && (
            <div>
              <p className="text-[10px] font-bold text-emerald-600 mb-1.5 flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                DO
              </p>
              <ul className="space-y-1">
                {dos.map((item, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="text-[8px] text-emerald-500 mt-0.5 shrink-0">●</span>
                    <span className="text-[10px] text-gray-600 leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {donts.length > 0 && (
            <div>
              <p className="text-[10px] font-bold text-red-500 mb-1.5 flex items-center gap-1">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
                DON'T
              </p>
              <ul className="space-y-1">
                {donts.map((item, i) => (
                  <li key={i} className="flex items-start gap-1.5">
                    <span className="text-[8px] text-red-400 mt-0.5 shrink-0">●</span>
                    <span className="text-[10px] text-gray-600 leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Example winning ads */}
      {examples.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-400 mb-1.5">このジャンルの勝ち広告</p>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {examples.slice(0, 8).map((ad) => {
              const thumbSrc = ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || "");
              return (
                <div
                  key={ad.ad_id}
                  className="shrink-0 w-24 cursor-pointer rounded-lg overflow-hidden border border-gray-200 hover:shadow-md transition-all"
                  onClick={() => onAdSelect?.(ad.ad_id)}
                >
                  <div className="relative aspect-video bg-gray-100">
                    {thumbSrc && (
                      <img
                        src={thumbSrc}
                        alt=""
                        className="w-full h-full object-cover"
                        loading="lazy"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                    )}
                    {ad.hit_score != null && (
                      <span className="absolute top-0.5 right-0.5 text-[7px] px-1 py-0.5 rounded bg-black/60 text-white font-bold">
                        {ad.hit_score}
                      </span>
                    )}
                  </div>
                  <p className="text-[8px] text-gray-700 px-1 py-0.5 truncate">{ad.product_name || "不明"}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
