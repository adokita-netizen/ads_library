"use client";

import React, { useState, useEffect, useMemo } from "react";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";
import { formatNumber } from "@/lib/format";

interface WeeklyTrendItem {
  week: string;
  week_label?: string;
  ad_count: number;
  hit_count: number;
  hit_rate: number;
  hook_types?: Record<string, number>;
}

interface TrendChartsProps {
  genre?: string;
}

const hookTypeLabels: Record<string, string> = {
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

const hookTypeColors: Record<string, string> = {
  question: "#3b82f6",
  pain_point: "#ef4444",
  benefit: "#22c55e",
  curiosity: "#f59e0b",
  social_proof: "#8b5cf6",
  urgency: "#f97316",
  storytelling: "#ec4899",
  number: "#06b6d4",
  comparison: "#14b8a6",
  authority: "#6366f1",
};

export default function TrendCharts({ genre }: TrendChartsProps) {
  const [data, setData] = useState<WeeklyTrendItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, string | number | undefined> = {};
        if (genre && genre !== "all") params.genre = genre;
        const res = await fetchApi<{ items?: WeeklyTrendItem[]; weeks?: WeeklyTrendItem[]; trends?: WeeklyTrendItem[] }>(
          "/rankings/trends/weekly",
          { params }
        );
        const items = res?.items || res?.weeks || res?.trends || (Array.isArray(res) ? res : []);
        setData(Array.isArray(items) ? items : []);
      } catch {
        setError("トレンドデータの取得に失敗しました");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [genre]);

  // Computed chart values
  const maxAdCount = useMemo(() => Math.max(1, ...data.map((d) => d.ad_count || 0)), [data]);
  const maxHitRate = useMemo(() => Math.max(1, ...data.map((d) => (typeof d.hit_rate === "number" ? (d.hit_rate <= 1 ? d.hit_rate * 100 : d.hit_rate) : 0))), [data]);

  // All hook types across weeks
  const allHookTypes = useMemo(() => {
    const types = new Set<string>();
    data.forEach((d) => {
      if (d.hook_types) Object.keys(d.hook_types).forEach((t) => types.add(t));
    });
    return Array.from(types).slice(0, 6);
  }, [data]);

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card px-4 py-4 animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-32 mb-3" />
            <div className="h-32 bg-gray-100 rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="card px-4 py-6 text-center">
        <p className="text-[12px] text-red-500 mb-2">{error}</p>
        <p className="text-[10px] text-gray-400">データが準備中の可能性があります</p>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="card px-4 py-8 text-center">
        <svg className="w-10 h-10 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
        <p className="text-[12px] text-gray-500 mb-1">週次トレンドデータがありません</p>
        <p className="text-[10px] text-gray-400">ランキング計算を実行するとデータが蓄積されます</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Weekly ad volume bar chart */}
      <div className="card px-4 py-4">
        <div className="flex items-center gap-2 mb-3">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
          <h3 className="text-[13px] font-bold text-gray-900">週次広告ボリューム</h3>
          <span className="text-[10px] text-gray-400">過去{data.length}週間の出稿数推移</span>
        </div>
        <div className="flex items-end gap-1 h-36">
          {data.map((week, i) => {
            const pct = maxAdCount > 0 ? ((week.ad_count || 0) / maxAdCount) * 100 : 0;
            return (
              <div key={week.week || i} className="flex-1 flex flex-col items-center justify-end h-full gap-1">
                <span className="text-[8px] text-gray-500 font-medium">{week.ad_count || 0}</span>
                <div
                  className="w-full rounded-t bg-[#4A7DFF] transition-all hover:bg-[#3a6de8]"
                  style={{ height: `${Math.max(pct, 2)}%`, minHeight: "2px" }}
                  title={`${week.week_label || week.week}: ${week.ad_count}件`}
                />
                <span className="text-[7px] text-gray-400 truncate w-full text-center">
                  {week.week_label || (week.week ? week.week.slice(5) : `W${i + 1}`)}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Hit rate trend line */}
      <div className="card px-4 py-4">
        <div className="flex items-center gap-2 mb-3">
          <svg className="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
          </svg>
          <h3 className="text-[13px] font-bold text-gray-900">ヒット率推移</h3>
          <span className="text-[10px] text-gray-400">週次HIT広告の検出率</span>
        </div>
        <div className="relative h-32">
          {/* Y-axis labels */}
          <div className="absolute left-0 top-0 bottom-4 flex flex-col justify-between text-[8px] text-gray-400 w-8">
            <span>{Math.round(maxHitRate)}%</span>
            <span>{Math.round(maxHitRate / 2)}%</span>
            <span>0%</span>
          </div>
          {/* Line chart area */}
          <div className="ml-9 h-full relative">
            <svg className="w-full h-[calc(100%-16px)]" viewBox={`0 0 ${data.length * 40} 100`} preserveAspectRatio="none">
              {/* Grid lines */}
              <line x1="0" y1="0" x2={data.length * 40} y2="0" stroke="#e5e7eb" strokeWidth="0.5" />
              <line x1="0" y1="50" x2={data.length * 40} y2="50" stroke="#e5e7eb" strokeWidth="0.5" />
              <line x1="0" y1="100" x2={data.length * 40} y2="100" stroke="#e5e7eb" strokeWidth="0.5" />
              {/* Area fill */}
              <path
                d={data.map((d, i) => {
                  const rate = typeof d.hit_rate === "number" ? (d.hit_rate <= 1 ? d.hit_rate * 100 : d.hit_rate) : 0;
                  const x = i * 40 + 20;
                  const y = maxHitRate > 0 ? 100 - (rate / maxHitRate) * 100 : 100;
                  return `${i === 0 ? "M" : "L"}${x},${y}`;
                }).join(" ") + ` L${(data.length - 1) * 40 + 20},100 L20,100 Z`}
                fill="rgba(16,185,129,0.1)"
              />
              {/* Line */}
              <polyline
                points={data.map((d, i) => {
                  const rate = typeof d.hit_rate === "number" ? (d.hit_rate <= 1 ? d.hit_rate * 100 : d.hit_rate) : 0;
                  const x = i * 40 + 20;
                  const y = maxHitRate > 0 ? 100 - (rate / maxHitRate) * 100 : 100;
                  return `${x},${y}`;
                }).join(" ")}
                fill="none"
                stroke="#10b981"
                strokeWidth="2"
              />
              {/* Dots */}
              {data.map((d, i) => {
                const rate = typeof d.hit_rate === "number" ? (d.hit_rate <= 1 ? d.hit_rate * 100 : d.hit_rate) : 0;
                const x = i * 40 + 20;
                const y = maxHitRate > 0 ? 100 - (rate / maxHitRate) * 100 : 100;
                return <circle key={i} cx={x} cy={y} r="3" fill="#10b981" stroke="white" strokeWidth="1.5" />;
              })}
            </svg>
            {/* X-axis labels */}
            <div className="flex justify-between text-[7px] text-gray-400 h-4">
              {data.map((d, i) => (
                <span key={i} className="text-center" style={{ width: `${100 / data.length}%` }}>
                  {d.week_label || (d.week ? d.week.slice(5) : `W${i + 1}`)}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Hook type popularity stacked area (simplified as stacked bars) */}
      {allHookTypes.length > 0 && (
        <div className="card px-4 py-4">
          <div className="flex items-center gap-2 mb-3">
            <svg className="w-4 h-4 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z" />
            </svg>
            <h3 className="text-[13px] font-bold text-gray-900">フックタイプ推移</h3>
            <span className="text-[10px] text-gray-400">週次のフックタイプ構成比</span>
          </div>
          {/* Legend */}
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            {allHookTypes.map((type) => (
              <div key={type} className="flex items-center gap-1">
                <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: hookTypeColors[type] || "#6b7280" }} />
                <span className="text-[9px] text-gray-500">{hookTypeLabels[type] || type}</span>
              </div>
            ))}
          </div>
          {/* Stacked bars */}
          <div className="flex items-end gap-1 h-32">
            {data.map((week, i) => {
              const hooks = week.hook_types || {};
              const total = Object.values(hooks).reduce((s, v) => s + (v || 0), 0) || 1;
              return (
                <div key={week.week || i} className="flex-1 flex flex-col items-center justify-end h-full gap-1">
                  <div className="w-full flex flex-col-reverse rounded-t overflow-hidden" style={{ height: "90%" }}>
                    {allHookTypes.map((type) => {
                      const val = hooks[type] || 0;
                      const pct = (val / total) * 100;
                      return (
                        <div
                          key={type}
                          style={{ height: `${pct}%`, backgroundColor: hookTypeColors[type] || "#6b7280" }}
                          title={`${hookTypeLabels[type] || type}: ${val}件 (${Math.round(pct)}%)`}
                        />
                      );
                    })}
                  </div>
                  <span className="text-[7px] text-gray-400 truncate w-full text-center">
                    {week.week_label || (week.week ? week.week.slice(5) : `W${i + 1}`)}
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
