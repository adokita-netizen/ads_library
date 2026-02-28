"use client";

import React, { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface LPBenchmark {
  genre?: string;
  avg_lp_score?: number;
  avg_alignment?: number;
  top_elements?: { element: string; hit_rate: number }[];
  score_distribution?: { range: string; count: number }[];
}

interface LPAnalysisPanelProps {
  genre?: string;
}

const elementLabels: Record<string, string> = {
  form: "フォーム", cta: "CTA", testimonials: "口コミ", video: "動画",
  price: "価格表示", countdown: "カウントダウン", faq: "FAQ",
  guarantee: "保証", comparison: "比較表", steps: "ステップ説明",
  hero_image: "ヒーロー画像", social_proof: "社会的証明", badge: "バッジ/認証",
};

export default function LPAnalysisPanel({ genre }: LPAnalysisPanelProps) {
  const [data, setData] = useState<LPBenchmark | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (genre) params.genre = genre;
    fetchApi<LPBenchmark>("/rankings/lp-benchmark", { params })
      .then((res) => setData(res))
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
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
        <p className="text-[11px] text-gray-400">LPベンチマークデータがありません</p>
      </div>
    );
  }

  const elements = data.top_elements || [];
  const distribution = data.score_distribution || [];
  const maxDist = Math.max(1, ...distribution.map((d) => d.count));

  return (
    <div className="space-y-4">
      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3">
        <div className="card px-4 py-3">
          <p className="text-[10px] text-gray-400">平均LPスコア</p>
          <p className="text-[20px] font-bold text-gray-900">{data.avg_lp_score != null ? Math.round(data.avg_lp_score) : "-"}</p>
          {genre && <p className="text-[9px] text-gray-400 mt-0.5">ジャンル: {genre}</p>}
        </div>
        <div className="card px-4 py-3">
          <p className="text-[10px] text-gray-400">平均一貫性スコア</p>
          <p className="text-[20px] font-bold text-[#4A7DFF]">{data.avg_alignment != null ? Math.round(data.avg_alignment) : "-"}<span className="text-[11px] text-gray-400">%</span></p>
          <p className="text-[9px] text-gray-400 mt-0.5">広告↔LP整合性</p>
        </div>
      </div>

      {/* Score Distribution */}
      {distribution.length > 0 && (
        <div className="card px-4 py-3">
          <h4 className="text-[11px] font-bold text-gray-900 mb-2">LPスコア分布</h4>
          <div className="space-y-1">
            {distribution.map((d, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-[9px] text-gray-500 w-12 text-right shrink-0">{d.range}</span>
                <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-indigo-400 transition-all"
                    style={{ width: `${(d.count / maxDist) * 100}%` }}
                  />
                </div>
                <span className="text-[9px] text-gray-400 w-6 shrink-0">{d.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top elements correlated with hit */}
      {elements.length > 0 && (
        <div className="card px-4 py-3">
          <h4 className="text-[11px] font-bold text-gray-900 mb-2">HIT率に相関するLP要素</h4>
          <div className="space-y-1.5">
            {elements.map((el, i) => {
              const barColor = el.hit_rate >= 70 ? "#22c55e" : el.hit_rate >= 45 ? "#f59e0b" : "#94a3b8";
              return (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-700 w-24 truncate shrink-0">
                    {elementLabels[el.element] || el.element}
                  </span>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${el.hit_rate}%`, backgroundColor: barColor }}
                    />
                  </div>
                  <span className="text-[9px] font-medium w-8 text-right shrink-0" style={{ color: barColor }}>
                    {Math.round(el.hit_rate)}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
