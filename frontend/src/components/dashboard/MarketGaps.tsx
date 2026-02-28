"use client";

import React, { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface MarketGapData {
  opportunities?: { genre: string; saturation: number; effectiveness: number; recommendation?: string }[];
  unused_combinations?: { hook_type: string; cta_type: string; predicted_hit_rate: number }[];
  blue_ocean?: { description: string; confidence: number }[];
}

interface MarketGapsProps {
  genre?: string;
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

export default function MarketGaps({ genre }: MarketGapsProps) {
  const [data, setData] = useState<MarketGapData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (genre) params.genre = genre;
    fetchApi<MarketGapData>("/rankings/market-gaps", { params })
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [genre]);

  if (loading) {
    return (
      <div className="card px-4 py-4 animate-pulse space-y-3">
        <div className="h-4 bg-gray-200 rounded w-32" />
        <div className="h-24 bg-gray-100 rounded" />
        <div className="h-20 bg-gray-100 rounded" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="card px-4 py-8 text-center">
        <svg className="w-8 h-8 text-gray-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
        </svg>
        <p className="text-[11px] text-gray-400">マーケットギャップデータがありません</p>
      </div>
    );
  }

  const opportunities = data.opportunities || [];
  const combos = data.unused_combinations || [];
  const blueOcean = data.blue_ocean || [];

  return (
    <div className="space-y-4">
      {/* Opportunity Matrix */}
      {opportunities.length > 0 && (
        <div className="card px-4 py-3">
          <div className="flex items-center gap-2 mb-3">
            <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
            </svg>
            <h4 className="text-[12px] font-bold text-gray-900">ジャンル別チャンスマトリクス</h4>
          </div>

          <div className="space-y-2">
            {opportunities.map((opp, i) => {
              const isOpportunity = opp.saturation < 50 && opp.effectiveness > 50;
              const isOverSaturated = opp.saturation >= 70;
              const bgColor = isOpportunity ? "bg-emerald-50 border-emerald-200" : isOverSaturated ? "bg-red-50 border-red-200" : "bg-gray-50 border-gray-200";
              return (
                <div key={i} className={`rounded-lg px-3 py-2 border ${bgColor}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-medium text-gray-900">{opp.genre}</span>
                    {isOpportunity && (
                      <span className="text-[8px] px-1.5 py-0.5 rounded bg-emerald-500 text-white font-bold">チャンス</span>
                    )}
                    {isOverSaturated && (
                      <span className="text-[8px] px-1.5 py-0.5 rounded bg-red-400 text-white font-bold">飽和</span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-2 mb-1">
                    <div>
                      <p className="text-[8px] text-gray-400">飽和度</p>
                      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-red-400" style={{ width: `${opp.saturation}%` }} />
                      </div>
                      <p className="text-[8px] text-gray-500 text-right">{Math.round(opp.saturation)}%</p>
                    </div>
                    <div>
                      <p className="text-[8px] text-gray-400">効果性</p>
                      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-emerald-400" style={{ width: `${opp.effectiveness}%` }} />
                      </div>
                      <p className="text-[8px] text-gray-500 text-right">{Math.round(opp.effectiveness)}%</p>
                    </div>
                  </div>
                  {opp.recommendation && (
                    <p className="text-[9px] text-gray-500 mt-0.5">{opp.recommendation}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Unused but effective combinations */}
      {combos.length > 0 && (
        <div className="card px-4 py-3">
          <h4 className="text-[12px] font-bold text-gray-900 mb-2">未活用の効果的組み合わせ</h4>
          <div className="space-y-1.5">
            {combos.map((c, i) => (
              <div key={i} className="flex items-center gap-2 py-1 border-b border-gray-50 last:border-0">
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
                  {hookLabels[c.hook_type] || c.hook_type}
                </span>
                <span className="text-[8px] text-gray-300">×</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-green-100 text-green-700">
                  {ctaLabels[c.cta_type] || c.cta_type}
                </span>
                <span className="ml-auto text-[10px] font-bold text-emerald-600">
                  予測HIT率 {Math.round(c.predicted_hit_rate)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Blue Ocean */}
      {blueOcean.length > 0 && (
        <div className="card px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[12px]">🌊</span>
            <h4 className="text-[12px] font-bold text-gray-900">ブルーオーシャン</h4>
          </div>
          <div className="space-y-2">
            {blueOcean.map((item, i) => (
              <div key={i} className="bg-blue-50 rounded-lg px-3 py-2 border border-blue-100">
                <p className="text-[10px] text-blue-800 leading-relaxed">{item.description}</p>
                <div className="flex items-center gap-1 mt-1">
                  <span className="text-[8px] text-blue-500">信頼度:</span>
                  <div className="w-16 h-1 bg-blue-200 rounded-full overflow-hidden">
                    <div className="h-full rounded-full bg-blue-500" style={{ width: `${item.confidence}%` }} />
                  </div>
                  <span className="text-[8px] text-blue-500">{Math.round(item.confidence)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
