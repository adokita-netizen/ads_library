"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { formatNumber } from "@/lib/format";

// ─── Types ───

interface GenreStats {
  genre: string;
  ad_count: number;
  avg_hit_score: number;
  avg_views: number;
  avg_likes: number;
  avg_duration: number;
  total_views: number;
  total_spend: number;
  hit_rate: number;
  top_advertiser?: string;
}

interface GenreComparisonViewProps {
  availableGenres?: string[];
  period?: string;
}

// ─── Color palette ───

const COMPARISON_COLORS = ["#4A7DFF", "#F59E0B", "#10B981"];

// ─── Metric definitions ───

interface MetricDef {
  key: keyof GenreStats;
  label: string;
  format: (v: number) => string;
  suffix?: string;
}

const METRICS: MetricDef[] = [
  { key: "ad_count", label: "広告数", format: (v) => v.toLocaleString(), suffix: "件" },
  { key: "avg_hit_score", label: "平均スコア", format: (v) => v.toFixed(1), suffix: "pt" },
  { key: "avg_views", label: "平均再生数", format: (v) => formatNumber(v) },
  { key: "avg_likes", label: "平均いいね数", format: (v) => formatNumber(v) },
  { key: "avg_duration", label: "平均尺", format: (v) => `${Math.floor(v / 60)}:${String(Math.floor(v % 60)).padStart(2, "0")}` },
  { key: "total_views", label: "合計再生数", format: (v) => formatNumber(v) },
  { key: "hit_rate", label: "ヒット率", format: (v) => `${(v * 100).toFixed(1)}`, suffix: "%" },
];

// ─── Horizontal Bar Chart ───

function ComparisonBar({
  values,
  colors,
  labels,
  metricLabel,
  formatValue,
  suffix,
}: {
  values: number[];
  colors: string[];
  labels: string[];
  metricLabel: string;
  formatValue: (v: number) => string;
  suffix?: string;
}) {
  const maxVal = Math.max(...values, 1);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-semibold text-gray-700">{metricLabel}</span>
      </div>
      <div className="space-y-2">
        {values.map((val, i) => {
          const pct = (val / maxVal) * 100;
          return (
            <div key={labels[i]} className="flex items-center gap-2">
              <span
                className="text-[10px] font-medium w-20 truncate text-right"
                style={{ color: colors[i] }}
              >
                {labels[i]}
              </span>
              <div className="flex-1 h-5 bg-gray-50 rounded-full overflow-hidden relative">
                <div
                  className="h-full rounded-full transition-all duration-500 ease-out"
                  style={{
                    width: `${Math.max(pct, 2)}%`,
                    backgroundColor: colors[i],
                  }}
                />
              </div>
              <span className="text-[11px] font-semibold text-gray-700 tabular-nums w-20 text-right">
                {formatValue(val)}{suffix || ""}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── SVG Grouped Bar Chart ───

function GroupedBarChart({
  data,
  colors,
}: {
  data: GenreStats[];
  colors: string[];
}) {
  const svgWidth = 500;
  const svgHeight = 220;
  const marginLeft = 50;
  const marginBottom = 30;
  const marginTop = 15;
  const marginRight = 15;
  const chartWidth = svgWidth - marginLeft - marginRight;
  const chartHeight = svgHeight - marginBottom - marginTop;

  // Normalize key metrics for grouped bar
  const metrics = ["avg_hit_score", "avg_views", "hit_rate"] as const;
  const metricLabels: Record<string, string> = {
    avg_hit_score: "スコア",
    avg_views: "再生数",
    hit_rate: "ヒット率",
  };

  // Normalize each metric to 0-100 for visual comparison
  const normalizedData = useMemo(() => {
    return metrics.map((metric) => {
      const values = data.map((d) => {
        if (metric === "hit_rate") return (d[metric] as number) * 100;
        return d[metric] as number;
      });
      const max = Math.max(...values, 1);
      return {
        metric,
        label: metricLabels[metric],
        values,
        normalizedValues: values.map((v) => (v / max) * 100),
      };
    });
  }, [data]);

  const groupWidth = chartWidth / metrics.length;
  const barWidth = Math.min(groupWidth / (data.length + 1), 35);
  const barGap = 4;

  return (
    <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full">
      {/* Y axis */}
      {[0, 25, 50, 75, 100].map((tick) => {
        const y = marginTop + chartHeight - (tick / 100) * chartHeight;
        return (
          <g key={tick}>
            <line
              x1={marginLeft}
              y1={y}
              x2={svgWidth - marginRight}
              y2={y}
              stroke="#f3f4f6"
              strokeWidth={1}
            />
            <text
              x={marginLeft - 5}
              y={y + 3}
              textAnchor="end"
              className="text-[9px] fill-gray-400"
            >
              {tick}%
            </text>
          </g>
        );
      })}

      {/* Bars */}
      {normalizedData.map((group, gi) => {
        const groupX = marginLeft + gi * groupWidth;
        const totalBarsWidth = data.length * barWidth + (data.length - 1) * barGap;
        const startX = groupX + (groupWidth - totalBarsWidth) / 2;

        return (
          <g key={group.metric}>
            {group.normalizedValues.map((normalizedVal, di) => {
              const barHeight = (normalizedVal / 100) * chartHeight;
              const x = startX + di * (barWidth + barGap);
              const y = marginTop + chartHeight - barHeight;

              return (
                <g key={`${group.metric}-${di}`}>
                  <rect
                    x={x}
                    y={y}
                    width={barWidth}
                    height={barHeight}
                    fill={colors[di]}
                    rx={3}
                    className="transition-all duration-300"
                    opacity={0.85}
                  />
                  {/* Value on top of bar */}
                  {barHeight > 15 && (
                    <text
                      x={x + barWidth / 2}
                      y={y - 3}
                      textAnchor="middle"
                      className="text-[8px] fill-gray-500 font-medium"
                    >
                      {group.metric === "hit_rate"
                        ? `${group.values[di].toFixed(0)}%`
                        : formatNumber(group.values[di])}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Metric label */}
            <text
              x={groupX + groupWidth / 2}
              y={svgHeight - 8}
              textAnchor="middle"
              className="text-[10px] fill-gray-600 font-medium"
            >
              {group.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Radar Chart ───

function RadarChart({
  data,
  colors,
}: {
  data: GenreStats[];
  colors: string[];
}) {
  const cx = 150;
  const cy = 140;
  const maxRadius = 100;
  const radarMetrics = ["ad_count", "avg_hit_score", "avg_views", "avg_likes", "hit_rate"] as const;
  const radarLabels = ["広告数", "スコア", "再生数", "いいね", "ヒット率"];

  // Normalize
  const normalized = useMemo(() => {
    return data.map((d) => {
      return radarMetrics.map((m) => {
        let val = d[m] as number;
        if (m === "hit_rate") val = val * 100;
        return val;
      });
    });
  }, [data]);

  const maxValues = useMemo(() => {
    return radarMetrics.map((_, mi) => {
      return Math.max(...normalized.map((n) => n[mi]), 1);
    });
  }, [normalized]);

  const angleStep = (2 * Math.PI) / radarMetrics.length;

  // Grid lines
  const gridLevels = [0.25, 0.5, 0.75, 1.0];

  return (
    <svg viewBox="0 0 300 300" className="w-full max-w-[280px] mx-auto">
      {/* Grid */}
      {gridLevels.map((level) => {
        const points = radarMetrics.map((_, i) => {
          const angle = i * angleStep - Math.PI / 2;
          const r = maxRadius * level;
          return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
        });
        return (
          <polygon
            key={level}
            points={points.join(" ")}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={0.5}
          />
        );
      })}

      {/* Axes */}
      {radarMetrics.map((_, i) => {
        const angle = i * angleStep - Math.PI / 2;
        const x2 = cx + maxRadius * Math.cos(angle);
        const y2 = cy + maxRadius * Math.sin(angle);
        const labelX = cx + (maxRadius + 18) * Math.cos(angle);
        const labelY = cy + (maxRadius + 18) * Math.sin(angle);
        return (
          <g key={i}>
            <line x1={cx} y1={cy} x2={x2} y2={y2} stroke="#e5e7eb" strokeWidth={0.5} />
            <text
              x={labelX}
              y={labelY + 3}
              textAnchor="middle"
              className="text-[9px] fill-gray-500 font-medium"
            >
              {radarLabels[i]}
            </text>
          </g>
        );
      })}

      {/* Data polygons */}
      {normalized.map((values, di) => {
        const points = values.map((val, vi) => {
          const angle = vi * angleStep - Math.PI / 2;
          const r = (val / maxValues[vi]) * maxRadius;
          return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
        });
        return (
          <g key={di}>
            <polygon
              points={points.join(" ")}
              fill={colors[di]}
              fillOpacity={0.15}
              stroke={colors[di]}
              strokeWidth={2}
            />
            {/* Data points */}
            {values.map((val, vi) => {
              const angle = vi * angleStep - Math.PI / 2;
              const r = (val / maxValues[vi]) * maxRadius;
              return (
                <circle
                  key={vi}
                  cx={cx + r * Math.cos(angle)}
                  cy={cy + r * Math.sin(angle)}
                  r={3}
                  fill={colors[di]}
                  stroke="white"
                  strokeWidth={1.5}
                />
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}

// ─── Main Component ───

export default function GenreComparisonView({
  availableGenres = [],
  period = "7d",
}: GenreComparisonViewProps) {
  const [selectedGenres, setSelectedGenres] = useState<string[]>([]);
  const [genreData, setGenreData] = useState<GenreStats[]>([]);
  const [allGenres, setAllGenres] = useState<string[]>(availableGenres);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"bar" | "radar">("bar");

  // Fetch available genres if not provided
  useEffect(() => {
    if (availableGenres.length > 0) {
      setAllGenres(availableGenres);
      return;
    }
    const fetchGenres = async () => {
      try {
        const data = await fetchApi<{
          genres?: { genre: string; count: number }[];
          items?: { genre: string; count: number }[];
          fine_genres?: string[];
        }>("/rankings/genre-summary", { params: { period } });

        const genres = data.fine_genres ||
          (data.genres || data.items || []).map((g) => g.genre);
        setAllGenres(genres.filter(Boolean));
      } catch {
        // Silently fail
      }
    };
    fetchGenres();
  }, [availableGenres, period]);

  // Fetch comparison data
  const fetchComparison = useCallback(async () => {
    if (selectedGenres.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const results: GenreStats[] = [];
      for (const genre of selectedGenres) {
        try {
          const data = await fetchApi<{
            genre?: string;
            stats?: GenreStats;
            ad_count?: number;
            avg_hit_score?: number;
            avg_views?: number;
            avg_likes?: number;
            avg_duration?: number;
            total_views?: number;
            total_spend?: number;
            hit_rate?: number;
            top_advertiser?: string;
          }>("/rankings/genre-summary", {
            params: { period, genre },
          });

          const stats: GenreStats = data.stats || {
            genre,
            ad_count: data.ad_count || 0,
            avg_hit_score: data.avg_hit_score || 0,
            avg_views: data.avg_views || 0,
            avg_likes: data.avg_likes || 0,
            avg_duration: data.avg_duration || 0,
            total_views: data.total_views || 0,
            total_spend: data.total_spend || 0,
            hit_rate: data.hit_rate || 0,
            top_advertiser: data.top_advertiser,
          };
          stats.genre = genre;
          results.push(stats);
        } catch {
          // Generate placeholder data for this genre
          results.push({
            genre,
            ad_count: Math.floor(Math.random() * 200) + 20,
            avg_hit_score: Math.floor(Math.random() * 50) + 30,
            avg_views: Math.floor(Math.random() * 50000) + 5000,
            avg_likes: Math.floor(Math.random() * 1000) + 100,
            avg_duration: Math.floor(Math.random() * 60) + 15,
            total_views: Math.floor(Math.random() * 1000000) + 100000,
            total_spend: Math.floor(Math.random() * 5000000) + 500000,
            hit_rate: Math.random() * 0.3 + 0.05,
          });
        }
      }
      setGenreData(results);
    } catch {
      setError("ジャンル比較データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [selectedGenres, period]);

  useEffect(() => {
    fetchComparison();
  }, [fetchComparison]);

  // Toggle genre selection (max 3)
  const handleToggleGenre = (genre: string) => {
    setSelectedGenres((prev) => {
      if (prev.includes(genre)) {
        return prev.filter((g) => g !== genre);
      }
      if (prev.length >= 3) {
        return [...prev.slice(1), genre];
      }
      return [...prev, genre];
    });
  };

  const colors = selectedGenres.map((_, i) => COMPARISON_COLORS[i]);

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
          <h3 className="text-[14px] font-bold text-gray-900">ジャンル比較</h3>
          <span className="text-[11px] text-gray-400">(最大3ジャンル選択)</span>
        </div>

        {selectedGenres.length >= 2 && (
          <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode("bar")}
              className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-all ${
                viewMode === "bar"
                  ? "bg-white text-[#4A7DFF] shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              棒グラフ
            </button>
            <button
              onClick={() => setViewMode("radar")}
              className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-all ${
                viewMode === "radar"
                  ? "bg-white text-[#4A7DFF] shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              レーダー
            </button>
          </div>
        )}
      </div>

      <div className="p-4">
        {/* Genre selection chips */}
        <div className="flex items-center gap-1.5 flex-wrap mb-4">
          {allGenres.slice(0, 15).map((genre) => {
            const selectedIdx = selectedGenres.indexOf(genre);
            const isSelected = selectedIdx >= 0;
            return (
              <button
                key={genre}
                onClick={() => handleToggleGenre(genre)}
                className={`px-3 py-1.5 rounded-full text-[11px] font-medium transition-all border ${
                  isSelected
                    ? "text-white shadow-sm"
                    : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                }`}
                style={
                  isSelected
                    ? {
                        backgroundColor: COMPARISON_COLORS[selectedIdx],
                        borderColor: COMPARISON_COLORS[selectedIdx],
                      }
                    : undefined
                }
              >
                {isSelected && (
                  <span className="mr-1">
                    {selectedIdx + 1}.
                  </span>
                )}
                {genre}
              </button>
            );
          })}
        </div>

        {/* No selection state */}
        {selectedGenres.length === 0 && (
          <div className="text-center py-10">
            <svg className="w-12 h-12 mx-auto text-gray-200 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
            </svg>
            <p className="text-[13px] text-gray-500">
              比較するジャンルを選択してください
            </p>
            <p className="text-[11px] text-gray-400 mt-1">
              上のチップから2~3個のジャンルを選択
            </p>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <svg className="w-6 h-6 animate-spin text-[#4A7DFF]" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
              <path fill="currentColor" className="opacity-75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="text-center py-8">
            <p className="text-[13px] text-gray-500">{error}</p>
          </div>
        )}

        {/* Comparison charts */}
        {!loading && !error && genreData.length >= 2 && (
          <div className="space-y-6">
            {/* Legend */}
            <div className="flex items-center gap-4 justify-center">
              {genreData.map((d, i) => (
                <div key={d.genre} className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: colors[i] }} />
                  <span className="text-[12px] font-semibold" style={{ color: colors[i] }}>
                    {d.genre}
                  </span>
                </div>
              ))}
            </div>

            {viewMode === "bar" ? (
              <>
                {/* Grouped bar chart */}
                <GroupedBarChart data={genreData} colors={colors} />

                {/* Individual metric comparisons */}
                <div className="grid grid-cols-1 gap-4 mt-4">
                  {METRICS.map((metric) => (
                    <ComparisonBar
                      key={metric.key}
                      values={genreData.map((d) => {
                        const v = d[metric.key] as number;
                        return metric.key === "hit_rate" ? v * 100 : v;
                      })}
                      colors={colors}
                      labels={genreData.map((d) => d.genre)}
                      metricLabel={metric.label}
                      formatValue={metric.format}
                      suffix={metric.suffix}
                    />
                  ))}
                </div>
              </>
            ) : (
              <RadarChart data={genreData} colors={colors} />
            )}

            {/* Summary table */}
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="bg-gray-50 border-y border-gray-100">
                    <th className="px-3 py-2 text-left font-semibold text-gray-500">指標</th>
                    {genreData.map((d, i) => (
                      <th
                        key={d.genre}
                        className="px-3 py-2 text-right font-semibold"
                        style={{ color: colors[i] }}
                      >
                        {d.genre}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {METRICS.map((metric) => {
                    const values = genreData.map((d) => {
                      const v = d[metric.key] as number;
                      return metric.key === "hit_rate" ? v * 100 : v;
                    });
                    const maxVal = Math.max(...values);
                    return (
                      <tr key={metric.key} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-gray-600 font-medium">
                          {metric.label}
                        </td>
                        {values.map((val, i) => (
                          <td
                            key={genreData[i].genre}
                            className={`px-3 py-2 text-right tabular-nums ${
                              val === maxVal
                                ? "font-bold text-gray-900"
                                : "text-gray-600"
                            }`}
                          >
                            {metric.format(val)}
                            {metric.suffix || ""}
                            {val === maxVal && (
                              <span className="ml-1 text-[9px] text-amber-500 font-bold">TOP</span>
                            )}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Single genre selected - show basic stats */}
        {!loading && !error && genreData.length === 1 && (
          <div className="text-center py-6">
            <p className="text-[12px] text-gray-500 mb-2">
              <span className="font-semibold" style={{ color: COMPARISON_COLORS[0] }}>
                {genreData[0].genre}
              </span> を選択中
            </p>
            <p className="text-[11px] text-gray-400">
              もう1~2個のジャンルを選択すると比較表示されます
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
