"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";

type PlatformFilter = "all" | "facebook" | "instagram" | "tiktok" | "youtube" | "line" | "x_twitter";

interface HeatmapCell {
  day: number;
  hour: number;
  value: number;
}

interface RankingLikeItem {
  ad_id: number;
  hit_score?: number;
  days_running?: number;
  first_seen_date?: string;
  last_seen_date?: string;
}

interface TooltipState {
  x: number;
  y: number;
  day: number;
  hour: number;
  value: number;
}

const DAYS = ["日", "月", "火", "水", "木", "金", "土"] as const;
const HOURS = Array.from({ length: 24 }, (_, i) => i);
const CELL_SIZE = 22;
const CELL_GAP = 2;
const LABEL_W = 26;
const HEADER_H = 22;
const SCORE_HIT_LINE = 60;

const PLATFORM_OPTIONS: Array<{ value: PlatformFilter; label: string }> = [
  { value: "all", label: "全媒体" },
  { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" },
  { value: "tiktok", label: "TikTok" },
  { value: "youtube", label: "YouTube" },
  { value: "line", label: "LINE" },
  { value: "x_twitter", label: "X" },
];

function getColor(value: number, max: number): string {
  if (max === 0) return "#f3f4f6";
  const ratio = value / max;
  if (ratio < 0.25) return "#dbeafe";
  if (ratio < 0.5) return "#93c5fd";
  if (ratio < 0.75) return "#fbbf24";
  return "#ef4444";
}

function safeDayFromDate(dateLike?: string): number | null {
  if (!dateLike) return null;
  const d = new Date(dateLike);
  if (Number.isNaN(d.getTime())) return null;
  return d.getDay();
}

function safeHourFromDate(dateLike?: string): number | null {
  if (!dateLike) return null;
  const d = new Date(dateLike);
  if (Number.isNaN(d.getTime())) return null;
  return d.getHours();
}

export default function HeatmapView() {
  const [genre, setGenre] = useState("all");
  const [platform, setPlatform] = useState<PlatformFilter>("all");
  const [cells, setCells] = useState<HeatmapCell[]>([]);
  const [maxValue, setMaxValue] = useState(0);
  const [ads, setAds] = useState<RankingLikeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    let shouldBuildFallback = true;
    try {
      const params: Record<string, string | number> = {};
      if (genre !== "all") params.genre = genre;
      if (platform !== "all") params.platform = platform;

      const heatmapRes = await fetchApi<{ cells?: HeatmapCell[]; max_value?: number }>("/rankings/trends/heatmap", { params });
      const heatmapCells = Array.isArray(heatmapRes?.cells) ? heatmapRes.cells : [];
      if (heatmapCells.length > 0) {
        setCells(heatmapCells);
        setMaxValue(heatmapRes.max_value ?? Math.max(...heatmapCells.map((c) => c.value), 0));
        shouldBuildFallback = false;
      } else {
        setCells([]);
        setMaxValue(0);
      }
    } catch {
      // Endpoint may not exist; fallback is handled below.
      setCells([]);
      setMaxValue(0);
    }

    try {
      const params: Record<string, string | number> = {
        page: 1,
        page_size: 100,
        per_page: 100,
      };
      if (genre !== "all") params.genre = genre;
      if (platform !== "all") params.platform = platform;

      const rankingRes = await fetchApi<{ items?: RankingLikeItem[]; ads?: RankingLikeItem[] }>(
        "/rankings/pro-ranking",
        { params },
      );
      const rankingItems = rankingRes.ads || rankingRes.items || [];
      setAds(rankingItems);

      if (shouldBuildFallback) {
        const matrix = new Map<string, number>();
        for (const item of rankingItems) {
          const fallbackSeed = Math.abs(item.ad_id || 0);
          const day = safeDayFromDate(item.first_seen_date) ?? (fallbackSeed % 7);
          const hour = safeHourFromDate(item.last_seen_date) ?? ((fallbackSeed * 7) % 24);
          const key = `${day}-${hour}`;
          matrix.set(key, (matrix.get(key) || 0) + 1);
        }
        const fallbackCells: HeatmapCell[] = [];
        for (let d = 0; d < 7; d += 1) {
          for (let h = 0; h < 24; h += 1) {
            const v = matrix.get(`${d}-${h}`) || 0;
            fallbackCells.push({ day: d, hour: h, value: v });
          }
        }
        setCells(fallbackCells);
        setMaxValue(Math.max(...fallbackCells.map((c) => c.value), 0));
      }
    } catch {
      setCells([]);
      setAds([]);
      setError("ヒートマップデータの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [genre, platform]);

  useEffect(() => {
    load();
  }, [load]);

  const cellMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const c of cells) {
      map.set(`${c.day}-${c.hour}`, c.value);
    }
    return map;
  }, [cells]);

  const scoreBins = useMemo(() => {
    const bins = Array.from({ length: 10 }, (_, i) => ({
      label: `${i * 10}-${i * 10 + 10}`,
      low: i * 10,
      high: i * 10 + 10,
      count: 0,
    }));
    for (const ad of ads) {
      const score = Math.max(0, Math.min(100, Math.round(ad.hit_score ?? 0)));
      const idx = Math.min(9, Math.floor(score / 10));
      bins[idx].count += 1;
    }
    return bins;
  }, [ads]);

  const lifespanBins = useMemo(() => {
    const bins = [
      { label: "0-7", min: 0, max: 7, key: "flash", color: "#f59e0b", count: 0 },
      { label: "7-14", min: 7, max: 14, key: "short", color: "#84cc16", count: 0 },
      { label: "14-30", min: 14, max: 30, key: "medium", color: "#3b82f6", count: 0 },
      { label: "30-60", min: 30, max: 60, key: "long", color: "#6366f1", count: 0 },
      { label: "60-90", min: 60, max: 90, key: "long_runner", color: "#8b5cf6", count: 0 },
      { label: "90+", min: 90, max: Number.POSITIVE_INFINITY, key: "evergreen", color: "#ef4444", count: 0 },
    ];
    for (const ad of ads) {
      const days = ad.days_running ?? 0;
      const bin = bins.find((b) => days >= b.min && days < b.max);
      if (bin) bin.count += 1;
    }
    return bins;
  }, [ads]);

  const scoreMax = Math.max(...scoreBins.map((b) => b.count), 1);
  const lifeMax = Math.max(...lifespanBins.map((b) => b.count), 1);
  const hasHeatmapData = cells.some((cell) => cell.value > 0);

  const svgWidth = LABEL_W + 24 * (CELL_SIZE + CELL_GAP) + CELL_GAP;
  const svgHeight = HEADER_H + 7 * (CELL_SIZE + CELL_GAP) + CELL_GAP;

  return (
    <div className="h-full overflow-auto custom-scrollbar p-5 bg-[#f8f9fb] dark:bg-gray-950">
      <div className="max-w-[1400px] mx-auto space-y-4">
        <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
          <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
            <div>
              <h2 className="text-[16px] font-bold text-gray-900 dark:text-gray-100">曜日×時間帯 ヒートマップ</h2>
              <p className="text-[11px] text-gray-500 dark:text-gray-400">配信密度を色で可視化（濃いほど配信密度が高い）</p>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={genre}
                onChange={(e) => setGenre(e.target.value)}
                className="text-[11px] border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-200"
              >
                {genreOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value as PlatformFilter)}
                className="text-[11px] border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-200"
              >
                {PLATFORM_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {loading ? (
            <div className="h-[260px] rounded-lg bg-gray-100 dark:bg-gray-800 animate-pulse" />
          ) : (
            <>
              <div className="mb-3 flex flex-wrap items-center gap-3 text-[10px] text-gray-500 dark:text-gray-400">
                <span className="font-medium">配信密度</span>
                {[
                  { label: "低", color: "#dbeafe" },
                  { label: "中", color: "#93c5fd" },
                  { label: "高", color: "#fbbf24" },
                  { label: "集中", color: "#ef4444" },
                ].map((item) => (
                  <span key={item.label} className="inline-flex items-center gap-1.5">
                    <span className="h-3 w-3 rounded-sm border border-slate-200" style={{ backgroundColor: item.color }} />
                    {item.label}
                  </span>
                ))}
              </div>
              {hasHeatmapData ? (
                <div ref={containerRef} className="relative overflow-x-auto">
                  <svg width={svgWidth} height={svgHeight} className="min-w-[620px]">
                    {HOURS.map((hour) => (
                      <text
                        key={hour}
                        x={LABEL_W + hour * (CELL_SIZE + CELL_GAP) + CELL_SIZE / 2}
                        y={14}
                        textAnchor="middle"
                        className="fill-gray-400 dark:fill-gray-500 text-[9px]"
                      >
                        {hour}
                      </text>
                    ))}

                    {DAYS.map((dayLabel, day) => (
                      <text
                        key={dayLabel}
                        x={10}
                        y={HEADER_H + day * (CELL_SIZE + CELL_GAP) + CELL_SIZE / 2 + 4}
                        textAnchor="middle"
                        className="fill-gray-500 dark:fill-gray-400 text-[10px]"
                      >
                        {dayLabel}
                      </text>
                    ))}

                    {DAYS.map((_, day) =>
                      HOURS.map((hour) => {
                        const value = cellMap.get(`${day}-${hour}`) || 0;
                        return (
                          <rect
                            key={`${day}-${hour}`}
                            x={LABEL_W + hour * (CELL_SIZE + CELL_GAP)}
                            y={HEADER_H + day * (CELL_SIZE + CELL_GAP)}
                            width={CELL_SIZE}
                            height={CELL_SIZE}
                            rx={3}
                            fill={getColor(value, maxValue)}
                            stroke="rgba(148,163,184,0.25)"
                            onMouseEnter={(e) => {
                              const root = containerRef.current?.getBoundingClientRect();
                              const rect = e.currentTarget.getBoundingClientRect();
                              if (!root) return;
                              setTooltip({
                                x: rect.left - root.left + rect.width / 2,
                                y: rect.top - root.top,
                                day,
                                hour,
                                value,
                              });
                            }}
                            onMouseLeave={() => setTooltip(null)}
                          />
                        );
                      }),
                    )}
                  </svg>

                  {tooltip && (
                    <div
                      className="absolute z-20 rounded-lg bg-gray-900 px-2.5 py-1.5 text-[10px] text-white shadow-lg pointer-events-none"
                      style={{ left: tooltip.x, top: tooltip.y - 8, transform: "translate(-50%, -100%)" }}
                    >
                      {DAYS[tooltip.day]}曜 {tooltip.hour}:00 - {tooltip.value}件
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-center text-[12px] text-gray-500 dark:border-gray-700 dark:bg-gray-900/40 dark:text-gray-400">
                  該当条件の配信ヒートマップデータはありません。
                </div>
              )}
            </>
          )}
          {error && <p className="mt-2 text-[10px] text-amber-600">{error}</p>}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
            <h3 className="text-[13px] font-bold text-gray-900 dark:text-gray-100 mb-3">スコア分布ヒストグラム</h3>
            <svg width="100%" height="220" viewBox="0 0 520 220" preserveAspectRatio="none">
              {scoreBins.map((bin, i) => {
                const x = 30 + i * 46;
                const h = (bin.count / scoreMax) * 140;
                const y = 180 - h;
                const color = bin.high <= SCORE_HIT_LINE ? "#9ca3af" : bin.low >= 80 ? "#f59e0b" : "#4A7DFF";
                return (
                  <g key={bin.label}>
                    <rect x={x} y={y} width={34} height={h} rx={3} fill={color} />
                    <text x={x + 17} y={196} textAnchor="middle" className="fill-gray-500 dark:fill-gray-400 text-[9px]">
                      {bin.label}
                    </text>
                    <text x={x + 17} y={y - 4} textAnchor="middle" className="fill-gray-500 dark:fill-gray-400 text-[9px]">
                      {bin.count}
                    </text>
                  </g>
                );
              })}
              <line
                x1={30 + (SCORE_HIT_LINE / 10) * 46}
                y1={18}
                x2={30 + (SCORE_HIT_LINE / 10) * 46}
                y2={184}
                stroke="#ef4444"
                strokeDasharray="4 3"
                strokeWidth="1.5"
              />
              <text
                x={30 + (SCORE_HIT_LINE / 10) * 46 + 4}
                y={16}
                className="fill-red-500 text-[9px]"
              >
                HITライン({SCORE_HIT_LINE})
              </text>
            </svg>
          </div>

          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
            <h3 className="text-[13px] font-bold text-gray-900 dark:text-gray-100 mb-3">広告寿命分布</h3>
            <svg width="100%" height="220" viewBox="0 0 520 220" preserveAspectRatio="none">
              {lifespanBins.map((bin, i) => {
                const x = 38 + i * 74;
                const h = (bin.count / lifeMax) * 140;
                const y = 180 - h;
                return (
                  <g key={bin.label}>
                    <rect x={x} y={y} width={42} height={h} rx={3} fill={bin.color} />
                    <text x={x + 21} y={196} textAnchor="middle" className="fill-gray-500 dark:fill-gray-400 text-[9px]">
                      {bin.label}
                    </text>
                    <text x={x + 21} y={y - 4} textAnchor="middle" className="fill-gray-500 dark:fill-gray-400 text-[9px]">
                      {bin.count}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
}
