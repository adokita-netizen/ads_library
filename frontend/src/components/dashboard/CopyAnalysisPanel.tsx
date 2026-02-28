"use client";

import React, { useState, useEffect, useMemo } from "react";
import { fetchApi } from "@/lib/api";

// ─── Types ───

interface TextFeature {
  feature: string;
  label?: string;
  hit_rate: number;
  hit_count: number;
  total_count: number;
  non_hit_rate?: number;
}

interface LengthStats {
  avg_hit_length?: number;
  avg_non_hit_length?: number;
  optimal_range?: { min: number; max: number };
}

interface CopyAnalysisData {
  text_features?: TextFeature[];
  length_stats?: LengthStats;
  total_analyzed?: number;
}

// ─── Label map for text features ───

const featureLabels: Record<string, string> = {
  has_numbers: "数字あり",
  has_emoji: "絵文字あり",
  has_testimonial: "体験談あり",
  has_question: "疑問文あり",
  has_urgency: "緊急性あり",
  has_price: "価格表示あり",
  has_comparison: "比較表現あり",
  has_guarantee: "保証あり",
  has_social_proof: "社会的証明あり",
  has_call_to_action: "CTA明確",
  short_text: "短文",
  long_text: "長文",
  medium_text: "中文",
};

const featureIcons: Record<string, string> = {
  has_numbers: "#",
  has_emoji: "E",
  has_testimonial: "T",
  has_question: "?",
  has_urgency: "!",
  has_price: "Y",
  has_comparison: "vs",
  has_guarantee: "G",
  has_social_proof: "S",
  has_call_to_action: "C",
};

function barColor(hitRate: number): string {
  if (hitRate >= 70) return "#22c55e";
  if (hitRate >= 45) return "#f59e0b";
  return "#94a3b8";
}

// ─── Main Component ───

interface CopyAnalysisPanelProps {
  genre?: string;
}

export default function CopyAnalysisPanel({ genre }: CopyAnalysisPanelProps) {
  const [data, setData] = useState<CopyAnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);

    const params: Record<string, string | number | undefined> = {};
    if (genre && genre !== "all") params.genre = genre;

    fetchApi<CopyAnalysisData>("/rankings/copy-analysis", { params })
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [genre]);

  const isEmpty = useMemo(() => {
    if (!data) return true;
    return (data.text_features?.length ?? 0) === 0 && !data.length_stats;
  }, [data]);

  const sortedFeatures = useMemo(() => {
    if (!data?.text_features) return [];
    return [...data.text_features].sort((a, b) => b.hit_rate - a.hit_rate);
  }, [data]);

  if (loading) {
    return (
      <div className="card px-4 py-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
          <span className="text-[11px] text-gray-400">コピー分析中...</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-16 bg-gray-100 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error || isEmpty || !data) {
    return (
      <div className="card px-4 py-4">
        <div className="flex items-center gap-2 mb-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
          </svg>
          <h3 className="text-[13px] font-bold text-gray-900">コピー分析</h3>
        </div>
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <svg className="w-10 h-10 text-gray-200 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
          </svg>
          <p className="text-[12px] text-gray-500 mb-1">データ準備中</p>
          <p className="text-[10px] text-gray-400">テキスト分析データが蓄積されると、コピーの効果が分析されます</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card px-4 py-4">
      <div className="flex items-center gap-2 mb-4">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">コピー分析</h3>
        <span className="text-[10px] text-gray-400">テキスト特徴がヒットに与える影響</span>
        {data?.total_analyzed != null && (
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 ml-auto">{data.total_analyzed}件分析</span>
        )}
      </div>

      {/* Feature stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-4">
        {sortedFeatures.map((feat) => {
          const displayRate = typeof feat.hit_rate === "number" && feat.hit_rate <= 1
            ? Math.round(feat.hit_rate * 100)
            : Math.round(feat.hit_rate);
          const nonHitRate = feat.non_hit_rate != null
            ? (typeof feat.non_hit_rate === "number" && feat.non_hit_rate <= 1
              ? Math.round(feat.non_hit_rate * 100)
              : Math.round(feat.non_hit_rate))
            : null;
          const label = feat.label || featureLabels[feat.feature] || feat.feature;
          const icon = featureIcons[feat.feature] || "?";
          const diff = nonHitRate != null ? displayRate - nonHitRate : null;

          return (
            <div key={feat.feature} className="bg-gray-50 rounded-lg px-3 py-2.5">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="inline-flex items-center justify-center w-5 h-5 rounded bg-[#4A7DFF]/10 text-[#4A7DFF] text-[9px] font-bold shrink-0">
                  {icon}
                </span>
                <span className="text-[10px] text-gray-600 font-medium truncate">{label}</span>
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-[16px] font-bold" style={{ color: barColor(displayRate) }}>
                  {displayRate}%
                </span>
                <span className="text-[9px] text-gray-400">ヒット率</span>
              </div>
              {diff != null && (
                <div className="flex items-center gap-1 mt-1">
                  <span className={`text-[9px] font-medium ${diff > 0 ? "text-emerald-600" : diff < 0 ? "text-red-500" : "text-gray-400"}`}>
                    {diff > 0 ? `+${diff}%` : `${diff}%`}
                  </span>
                  <span className="text-[8px] text-gray-400">vs 非ヒット</span>
                </div>
              )}
              <p className="text-[8px] text-gray-400 mt-0.5">{feat.hit_count}/{feat.total_count}件</p>
            </div>
          );
        })}
      </div>

      {/* Length stats */}
      {data?.length_stats && (
        <div className="bg-gray-50 rounded-lg px-3 py-2.5">
          <p className="text-[10px] text-gray-500 font-medium mb-2">テキスト長さの比較</p>
          <div className="flex items-center gap-6 flex-wrap">
            {data.length_stats.avg_hit_length != null && (
              <div>
                <p className="text-[9px] text-gray-400">ヒット広告の平均文字数</p>
                <p className="text-[14px] font-bold text-emerald-600">{Math.round(data.length_stats.avg_hit_length)}文字</p>
              </div>
            )}
            {data.length_stats.avg_non_hit_length != null && (
              <div>
                <p className="text-[9px] text-gray-400">非ヒットの平均文字数</p>
                <p className="text-[14px] font-bold text-gray-500">{Math.round(data.length_stats.avg_non_hit_length)}文字</p>
              </div>
            )}
            {data.length_stats.optimal_range && (
              <div>
                <p className="text-[9px] text-gray-400">最適文字数</p>
                <p className="text-[14px] font-bold text-[#4A7DFF]">
                  {data.length_stats.optimal_range.min}-{data.length_stats.optimal_range.max}文字
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
