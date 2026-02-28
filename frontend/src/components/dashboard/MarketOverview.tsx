"use client";

import React, { useState, useEffect, useMemo } from "react";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";
import { formatNumber, formatYen } from "@/lib/format";

interface MarketOverviewData {
  total_ads?: number;
  active_ads?: number;
  avg_score?: number;
  hit_rate?: number;
  genre_distribution?: Record<string, number> | Array<{ genre: string; count: number }>;
  creative_type_split?: Record<string, number>;
  total_spend?: number;
  total_views?: number;
}

interface MarketOverviewProps {
  genre?: string;
}

const genreLabel = (value: string): string => {
  return genreOptions.find((g) => g.value === value)?.label || value || "未分類";
};

const GENRE_COLORS = [
  "#4A7DFF", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#06b6d4", "#f97316", "#14b8a6", "#6366f1",
  "#a855f7", "#64748b",
];

export default function MarketOverview({ genre }: MarketOverviewProps) {
  const [data, setData] = useState<MarketOverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, string | number | undefined> = {};
        if (genre && genre !== "all") params.genre = genre;
        const res = await fetchApi<MarketOverviewData>("/rankings/trends/market-overview", { params });
        setData(res || null);
      } catch {
        setError("マーケット概要の取得に失敗しました");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [genre]);

  // Normalize genre distribution
  const genreItems = useMemo(() => {
    if (!data?.genre_distribution) return [];
    if (Array.isArray(data.genre_distribution)) {
      return data.genre_distribution
        .map((g) => ({ genre: g.genre, count: g.count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 8);
    }
    return Object.entries(data.genre_distribution)
      .map(([genre, count]) => ({ genre, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [data]);

  const genreTotal = useMemo(() => genreItems.reduce((s, g) => s + g.count, 0) || 1, [genreItems]);

  // Creative type split
  const creativeItems = useMemo(() => {
    if (!data?.creative_type_split) return [];
    return Object.entries(data.creative_type_split)
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count);
  }, [data]);

  const creativeTotal = useMemo(() => creativeItems.reduce((s, c) => s + c.count, 0) || 1, [creativeItems]);

  const creativeTypeLabels: Record<string, string> = { video: "動画", image: "静止画", carousel: "カルーセル", other: "その他" };
  const creativeTypeColors: Record<string, string> = { video: "#4A7DFF", image: "#22c55e", carousel: "#f59e0b", other: "#94a3b8" };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card px-4 py-4 animate-pulse">
              <div className="h-3 bg-gray-200 rounded w-16 mb-2" />
              <div className="h-7 bg-gray-200 rounded w-20" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {[1, 2].map((i) => (
            <div key={i} className="card px-4 py-4 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-32 mb-3" />
              <div className="h-40 bg-gray-100 rounded" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="card px-4 py-6 text-center">
        <p className="text-[12px] text-red-500 mb-2">{error || "データがありません"}</p>
        <p className="text-[10px] text-gray-400">データが準備中の可能性があります</p>
      </div>
    );
  }

  const hitRate = typeof data.hit_rate === "number" ? (data.hit_rate <= 1 ? data.hit_rate * 100 : data.hit_rate) : 0;

  return (
    <div className="space-y-4">
      {/* Big stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="card px-4 py-4">
          <p className="text-[10px] text-gray-400 font-medium">総広告数</p>
          <p className="text-[26px] font-bold text-gray-900 mt-1">{formatNumber(data.total_ads || 0)}</p>
          <p className="text-[9px] text-gray-400 mt-0.5">全プラットフォーム合計</p>
        </div>
        <div className="card px-4 py-4">
          <p className="text-[10px] text-gray-400 font-medium">アクティブ広告</p>
          <p className="text-[26px] font-bold text-emerald-600 mt-1">{formatNumber(data.active_ads || 0)}</p>
          <p className="text-[9px] text-gray-400 mt-0.5">現在配信中</p>
        </div>
        <div className="card px-4 py-4">
          <p className="text-[10px] text-gray-400 font-medium">平均スコア</p>
          <p className="text-[26px] font-bold text-[#4A7DFF] mt-1">{Math.round(data.avg_score || 0)}<span className="text-[14px] text-gray-400">/100</span></p>
          <div className="mt-1.5 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full rounded-full bg-[#4A7DFF]" style={{ width: `${data.avg_score || 0}%` }} />
          </div>
        </div>
        <div className="card px-4 py-4">
          <p className="text-[10px] text-gray-400 font-medium">ヒット率</p>
          <p className="text-[26px] font-bold mt-1" style={{ color: hitRate >= 10 ? "#22c55e" : hitRate >= 5 ? "#f59e0b" : "#ef4444" }}>
            {hitRate.toFixed(1)}<span className="text-[14px] text-gray-400">%</span>
          </p>
          <p className="text-[9px] text-gray-400 mt-0.5">HIT判定広告の割合</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Genre distribution pie chart (rendered as horizontal bars) */}
        {genreItems.length > 0 && (
          <div className="card px-4 py-4">
            <div className="flex items-center gap-2 mb-3">
              <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6a7.5 7.5 0 107.5 7.5h-7.5V6z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5H21A7.5 7.5 0 0013.5 3v7.5z" />
              </svg>
              <h3 className="text-[13px] font-bold text-gray-900">ジャンル分布</h3>
            </div>
            {/* Donut chart */}
            <div className="flex items-center gap-4">
              <div className="relative w-32 h-32 shrink-0">
                <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                  {(() => {
                    let cumAngle = 0;
                    return genreItems.map((g, i) => {
                      const pct = (g.count / genreTotal) * 100;
                      const dash = `${pct} ${100 - pct}`;
                      const offset = 100 - cumAngle;
                      cumAngle += pct;
                      return (
                        <circle
                          key={g.genre}
                          cx="18" cy="18" r="15.915"
                          fill="none"
                          stroke={GENRE_COLORS[i % GENRE_COLORS.length]}
                          strokeWidth="3.5"
                          strokeDasharray={dash}
                          strokeDashoffset={offset}
                        />
                      );
                    });
                  })()}
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <p className="text-[14px] font-bold text-gray-900">{genreItems.length}</p>
                    <p className="text-[8px] text-gray-400">ジャンル</p>
                  </div>
                </div>
              </div>
              <div className="flex-1 space-y-1.5">
                {genreItems.map((g, i) => {
                  const pct = Math.round((g.count / genreTotal) * 100);
                  return (
                    <div key={g.genre} className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-sm shrink-0" style={{ backgroundColor: GENRE_COLORS[i % GENRE_COLORS.length] }} />
                      <span className="text-[10px] text-gray-600 truncate flex-1">{genreLabel(g.genre)}</span>
                      <span className="text-[10px] text-gray-500 font-medium shrink-0">{pct}%</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Creative type donut chart */}
        {creativeItems.length > 0 && (
          <div className="card px-4 py-4">
            <div className="flex items-center gap-2 mb-3">
              <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h1.5C5.496 19.5 6 18.996 6 18.375m-3.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-1.5A1.125 1.125 0 0118 18.375M20.625 4.5H3.375m17.25 0c.621 0 1.125.504 1.125 1.125M20.625 4.5h-1.5C18.504 4.5 18 5.004 18 5.625m3.75 0v1.5c0 .621-.504 1.125-1.125 1.125M3.375 4.5c-.621 0-1.125.504-1.125 1.125M3.375 4.5h1.5C5.496 4.5 6 5.004 6 5.625m-3.75 0v1.5c0 .621.504 1.125 1.125 1.125m0 0h1.5m-1.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m1.5-3.75C5.496 8.25 6 7.746 6 7.125v-1.5M4.875 8.25C5.496 8.25 6 8.754 6 9.375v1.5m0-5.25v5.25m0-5.25C6 5.004 6.504 4.5 7.125 4.5h9.75c.621 0 1.125.504 1.125 1.125m1.125 2.625h1.5m-1.5 0A1.125 1.125 0 0118 7.125v-1.5m1.125 2.625c-.621 0-1.125.504-1.125 1.125v1.5m2.625-2.625c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125M18 5.625v5.25M7.125 12h9.75m-9.75 0A1.125 1.125 0 016 10.875M7.125 12C6.504 12 6 12.504 6 13.125m0-2.25C6 11.496 5.496 12 4.875 12M18 10.875c0 .621-.504 1.125-1.125 1.125M18 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125m-12 5.25v-5.25m0 5.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125m-12 0v-1.5c0-.621-.504-1.125-1.125-1.125M18 18.375v-5.25m0 5.25v-1.5c0-.621.504-1.125 1.125-1.125M18 13.125v1.5c0 .621.504 1.125 1.125 1.125M18 13.125c0-.621.504-1.125 1.125-1.125M6 13.125v1.5c0 .621-.504 1.125-1.125 1.125M6 13.125C6 12.504 5.496 12 4.875 12m-1.5 0h1.5m-1.5 0c-.621 0-1.125-.504-1.125-1.125v-1.5c0-.621.504-1.125 1.125-1.125m1.5 3.75c-.621 0-1.125-.504-1.125-1.125v-1.5c0-.621.504-1.125 1.125-1.125m0 3.75h1.5" />
              </svg>
              <h3 className="text-[13px] font-bold text-gray-900">クリエイティブタイプ分布</h3>
            </div>
            <div className="flex items-center gap-4">
              <div className="relative w-32 h-32 shrink-0">
                <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                  {(() => {
                    let cumAngle = 0;
                    return creativeItems.map((c) => {
                      const pct = (c.count / creativeTotal) * 100;
                      const dash = `${pct} ${100 - pct}`;
                      const offset = 100 - cumAngle;
                      cumAngle += pct;
                      return (
                        <circle
                          key={c.type}
                          cx="18" cy="18" r="15.915"
                          fill="none"
                          stroke={creativeTypeColors[c.type] || "#94a3b8"}
                          strokeWidth="4.5"
                          strokeDasharray={dash}
                          strokeDashoffset={offset}
                        />
                      );
                    });
                  })()}
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <p className="text-[14px] font-bold text-gray-900">{creativeTotal}</p>
                    <p className="text-[8px] text-gray-400">合計</p>
                  </div>
                </div>
              </div>
              <div className="flex-1 space-y-2.5">
                {creativeItems.map((c) => {
                  const pct = Math.round((c.count / creativeTotal) * 100);
                  return (
                    <div key={c.type}>
                      <div className="flex items-center justify-between mb-0.5">
                        <div className="flex items-center gap-1.5">
                          <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: creativeTypeColors[c.type] || "#94a3b8" }} />
                          <span className="text-[11px] text-gray-700 font-medium">{creativeTypeLabels[c.type] || c.type}</span>
                        </div>
                        <span className="text-[11px] text-gray-600 font-semibold">{pct}%</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${pct}%`, backgroundColor: creativeTypeColors[c.type] || "#94a3b8" }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
