"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { fetchApi } from "@/lib/api";

/* ─── Types ─── */

interface WeeklyGenreData {
  genre: string;
  genre_label: string;
  weeks: {
    week: string;
    week_label: string;
    avg_score: number;
    ad_count: number;
  }[];
}

interface TooltipData {
  genre: string;
  week: string;
  avgScore: number;
  adCount: number;
  x: number;
  y: number;
}

interface PerformanceHeatmapProps {
  genre?: string;
}

/* ─── Mock data generator ─── */

const MOCK_GENRES = [
  "美容・コスメ",
  "健康食品",
  "EC・D2C",
  "金融・保険",
  "教育・資格",
  "アプリ",
  "食品・飲料",
  "ゲーム",
  "不動産",
  "旅行・観光",
];

function generateMockData(): WeeklyGenreData[] {
  const now = new Date();
  const weeks: { week: string; week_label: string }[] = [];
  for (let i = 7; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 7 * 86400000);
    const label = `${d.getMonth() + 1}/${d.getDate()}`;
    weeks.push({ week: d.toISOString().slice(0, 10), week_label: label });
  }
  return MOCK_GENRES.map((label, gi) => ({
    genre: label,
    genre_label: label,
    weeks: weeks.map((w, wi) => ({
      ...w,
      avg_score: Math.round(30 + Math.random() * 55 + Math.sin(gi + wi) * 10),
      ad_count: Math.round(5 + Math.random() * 80),
    })),
  }));
}

/* ─── Color helpers ─── */

function scoreToColor(score: number): string {
  if (score >= 70) return "#22c55e";
  if (score >= 55) return "#84cc16";
  if (score >= 45) return "#f59e0b";
  if (score >= 35) return "#f97316";
  return "#ef4444";
}

function scoreToOpacity(score: number): number {
  return 0.3 + (score / 100) * 0.7;
}

/* ─── Main Component ─── */

export default function PerformanceHeatmap({ genre }: PerformanceHeatmapProps) {
  const [data, setData] = useState<WeeklyGenreData[]>([]);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number | undefined> = {};
      if (genre && genre !== "all") params.genre = genre;
      const res = await fetchApi<{ items?: WeeklyGenreData[]; genres?: WeeklyGenreData[] }>(
        "/rankings/trends/weekly",
        { params }
      );
      const items = res?.items || res?.genres || (Array.isArray(res) ? res : []);
      setData(Array.isArray(items) && items.length > 0 ? items.slice(0, 10) : generateMockData());
    } catch {
      setData(generateMockData());
    } finally {
      setLoading(false);
    }
  }, [genre]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const weekLabels = useMemo(() => {
    if (data.length === 0) return [];
    return data[0]?.weeks?.map((w) => w.week_label || w.week?.slice(5) || "") || [];
  }, [data]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 px-4 py-4 animate-pulse">
        <div className="h-4 w-48 bg-gray-200 rounded mb-4" />
        <div className="h-64 bg-gray-100 rounded" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 px-4 py-4 relative">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">ジャンル別パフォーマンスヒートマップ</h3>
        <span className="text-[10px] text-gray-400">上位10ジャンル x 過去8週間</span>
      </div>

      {/* Color legend */}
      <div className="flex items-center gap-3 mb-3">
        <span className="text-[10px] text-gray-500">スコア:</span>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: "#ef4444" }} />
          <span className="text-[9px] text-gray-400">低</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: "#f59e0b" }} />
          <span className="text-[9px] text-gray-400">中</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: "#22c55e" }} />
          <span className="text-[9px] text-gray-400">高</span>
        </div>
      </div>

      {/* Heatmap grid */}
      <div className="overflow-x-auto">
        <div
          className="grid gap-[2px]"
          style={{
            gridTemplateColumns: `100px repeat(${weekLabels.length}, 1fr)`,
          }}
        >
          {/* Column headers (weeks) */}
          <div className="text-[9px] text-gray-400 font-medium" />
          {weekLabels.map((wl, i) => (
            <div key={i} className="text-[9px] text-gray-400 font-medium text-center pb-1">
              {wl}
            </div>
          ))}

          {/* Rows (genres) */}
          {data.map((row) => (
            <React.Fragment key={row.genre}>
              <div className="text-[10px] text-gray-700 font-medium truncate pr-2 flex items-center h-7">
                {row.genre_label || row.genre}
              </div>
              {row.weeks.map((cell, ci) => (
                <div
                  key={ci}
                  className="h-7 rounded-sm cursor-pointer transition-transform hover:scale-110 hover:z-10 relative"
                  style={{
                    backgroundColor: scoreToColor(cell.avg_score),
                    opacity: scoreToOpacity(cell.avg_score),
                  }}
                  onMouseEnter={(e) => {
                    const rect = (e.target as HTMLElement).getBoundingClientRect();
                    const parent = (e.target as HTMLElement).closest(".relative")?.getBoundingClientRect();
                    setTooltip({
                      genre: row.genre_label || row.genre,
                      week: cell.week_label || cell.week,
                      avgScore: cell.avg_score,
                      adCount: cell.ad_count,
                      x: rect.left - (parent?.left || 0) + rect.width / 2,
                      y: rect.top - (parent?.top || 0) - 4,
                    });
                  }}
                  onMouseLeave={() => setTooltip(null)}
                >
                  <span className="text-[8px] text-white font-bold flex items-center justify-center h-full drop-shadow-sm">
                    {cell.avg_score}
                  </span>
                </div>
              ))}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute z-50 bg-gray-900 text-white rounded-lg px-3 py-2 shadow-lg pointer-events-none"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: "translate(-50%, -100%)",
          }}
        >
          <p className="text-[11px] font-bold">{tooltip.genre}</p>
          <p className="text-[10px] text-gray-300">{tooltip.week}</p>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-[10px]">
              平均スコア: <span className="font-bold text-white">{tooltip.avgScore}</span>
            </span>
            <span className="text-[10px]">
              広告数: <span className="font-bold text-white">{tooltip.adCount}</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
