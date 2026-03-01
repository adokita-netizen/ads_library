"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import ErrorBoundary from "@/components/common/ErrorBoundary";

// ─── Types ───

interface GenreData {
  genre: string;
  count: number;
  percentage?: number;
}

interface GenreDistributionChartProps {
  period?: string;
  onGenreClick?: (genre: string) => void;
  mode?: "pie" | "treemap";
}

// ─── Color palette ───

const GENRE_COLORS = [
  "#4A7DFF", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6",
  "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#06B6D4",
  "#84CC16", "#E11D48", "#7C3AED", "#0EA5E9", "#D946EF",
];

function getColor(index: number): string {
  return GENRE_COLORS[index % GENRE_COLORS.length];
}

/** Guard against NaN/Infinity in SVG coordinates */
function safeNum(n: number, fallback = 0): number {
  return Number.isFinite(n) ? n : fallback;
}

// ─── SVG Pie Chart ───

function PieChart({
  data,
  onSliceClick,
  hoveredIndex,
  onHover,
}: {
  data: GenreData[];
  onSliceClick: (genre: string) => void;
  hoveredIndex: number | null;
  onHover: (index: number | null) => void;
}) {
  const total = data.reduce((sum, d) => sum + d.count, 0);
  if (total === 0) return null;

  const cx = 150;
  const cy = 150;
  const radius = 120;
  const innerRadius = 60;

  let currentAngle = -Math.PI / 2;

  const slices = data.map((item, index) => {
    const sliceAngle = (item.count / total) * 2 * Math.PI;
    const startAngle = currentAngle;
    const endAngle = currentAngle + sliceAngle;
    currentAngle = endAngle;

    const isHovered = hoveredIndex === index;
    const expandOffset = isHovered ? 8 : 0;
    const midAngle = (startAngle + endAngle) / 2;
    const offsetX = Math.cos(midAngle) * expandOffset;
    const offsetY = Math.sin(midAngle) * expandOffset;

    const outerStartX = safeNum(cx + offsetX + radius * Math.cos(startAngle));
    const outerStartY = safeNum(cy + offsetY + radius * Math.sin(startAngle));
    const outerEndX = safeNum(cx + offsetX + radius * Math.cos(endAngle));
    const outerEndY = safeNum(cy + offsetY + radius * Math.sin(endAngle));
    const innerStartX = safeNum(cx + offsetX + innerRadius * Math.cos(endAngle));
    const innerStartY = safeNum(cy + offsetY + innerRadius * Math.sin(endAngle));
    const innerEndX = safeNum(cx + offsetX + innerRadius * Math.cos(startAngle));
    const innerEndY = safeNum(cy + offsetY + innerRadius * Math.sin(startAngle));

    const largeArc = sliceAngle > Math.PI ? 1 : 0;

    const pathD = [
      `M ${outerStartX} ${outerStartY}`,
      `A ${radius} ${radius} 0 ${largeArc} 1 ${outerEndX} ${outerEndY}`,
      `L ${innerStartX} ${innerStartY}`,
      `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${innerEndX} ${innerEndY}`,
      "Z",
    ].join(" ");

    return (
      <path
        key={item.genre}
        d={pathD}
        fill={getColor(index)}
        opacity={hoveredIndex !== null && !isHovered ? 0.5 : 1}
        className="cursor-pointer transition-opacity duration-200"
        onClick={() => onSliceClick(item.genre)}
        onMouseEnter={() => onHover(index)}
        onMouseLeave={() => onHover(null)}
        stroke="white"
        strokeWidth={2}
      />
    );
  });

  return (
    <svg viewBox="0 0 300 300" className="w-full max-w-[280px] mx-auto">
      {slices}
      {/* Center label */}
      <text x={cx} y={cy - 8} textAnchor="middle" className="text-[14px] font-bold fill-gray-700">
        {total.toLocaleString()}
      </text>
      <text x={cx} y={cx + 10} textAnchor="middle" className="text-[10px] fill-gray-400">
        広告数合計
      </text>
    </svg>
  );
}

// ─── SVG Treemap ───

function TreemapChart({
  data,
  onSliceClick,
  hoveredIndex,
  onHover,
}: {
  data: GenreData[];
  onSliceClick: (genre: string) => void;
  hoveredIndex: number | null;
  onHover: (index: number | null) => void;
}) {
  const total = data.reduce((sum, d) => sum + d.count, 0);
  if (total === 0) return null;

  const width = 400;
  const height = 280;
  const padding = 2;

  // Simple squarified treemap layout
  const rects = useMemo(() => {
    const result: {
      x: number;
      y: number;
      w: number;
      h: number;
      item: GenreData;
      index: number;
    }[] = [];

    let x = 0;
    let y = 0;
    let remainingWidth = width;
    let remainingHeight = height;
    let remainingTotal = total;
    let isVertical = true;

    const sorted = [...data].sort((a, b) => b.count - a.count);

    sorted.forEach((item, i) => {
      const ratio = item.count / remainingTotal;

      if (isVertical) {
        const w = remainingWidth * ratio;
        result.push({
          x: x + padding,
          y: y + padding,
          w: Math.max(w - padding * 2, 0),
          h: remainingHeight - padding * 2,
          item,
          index: data.indexOf(item),
        });
        x += w;
        remainingWidth -= w;
      } else {
        const h = remainingHeight * ratio;
        result.push({
          x: x + padding,
          y: y + padding,
          w: remainingWidth - padding * 2,
          h: Math.max(h - padding * 2, 0),
          item,
          index: data.indexOf(item),
        });
        y += h;
        remainingHeight -= h;
      }

      remainingTotal -= item.count;

      // Switch direction every 3 items
      if ((i + 1) % 3 === 0) {
        isVertical = !isVertical;
      }
    });

    return result;
  }, [data, total]);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
      {rects.map(({ x, y, w, h, item, index }) => {
        const isHovered = hoveredIndex === index;
        const pct = total > 0 ? ((item.count / total) * 100).toFixed(1) : "0";
        const showLabel = w > 50 && h > 30;

        return (
          <g
            key={item.genre}
            className="cursor-pointer"
            onClick={() => onSliceClick(item.genre)}
            onMouseEnter={() => onHover(index)}
            onMouseLeave={() => onHover(null)}
          >
            <rect
              x={x}
              y={y}
              width={w}
              height={h}
              fill={getColor(index)}
              rx={4}
              opacity={hoveredIndex !== null && !isHovered ? 0.5 : 1}
              className="transition-opacity duration-200"
              stroke={isHovered ? "#fff" : "none"}
              strokeWidth={isHovered ? 2 : 0}
            />
            {showLabel && (
              <>
                <text
                  x={x + w / 2}
                  y={y + h / 2 - 6}
                  textAnchor="middle"
                  className="text-[10px] font-semibold fill-white pointer-events-none"
                >
                  {item.genre.length > 8 ? item.genre.slice(0, 8) + ".." : item.genre}
                </text>
                <text
                  x={x + w / 2}
                  y={y + h / 2 + 8}
                  textAnchor="middle"
                  className="text-[9px] fill-white/80 pointer-events-none"
                >
                  {pct}%
                </text>
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ─── Main Component ───

export default function GenreDistributionChart({
  period = "7d",
  onGenreClick,
  mode: initialMode = "pie",
}: GenreDistributionChartProps) {
  const [data, setData] = useState<GenreData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [mode, setMode] = useState<"pie" | "treemap">(initialMode);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await fetchApi<{
          genres?: GenreData[];
          items?: GenreData[];
          genre_distribution?: GenreData[];
        }>("/rankings/genre-summary", {
          params: { period },
        });

        const genres = result.genres || result.items || result.genre_distribution || [];
        setData(genres.filter((g) => g.count > 0).sort((a, b) => b.count - a.count));
      } catch {
        setError("ジャンル分布データの取得に失敗しました");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [period]);

  const handleSliceClick = useCallback(
    (genre: string) => {
      if (onGenreClick) {
        onGenreClick(genre);
      }
    },
    [onGenreClick]
  );

  const total = useMemo(() => data.reduce((sum, d) => sum + d.count, 0), [data]);

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="h-5 w-40 bg-gray-200 rounded animate-pulse" />
          <div className="h-6 w-24 bg-gray-200 rounded animate-pulse" />
        </div>
        <div className="flex items-center justify-center h-60">
          <div className="w-48 h-48 rounded-full bg-gray-100 animate-pulse" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6 text-center">
        <p className="text-[13px] text-gray-500">{error}</p>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6 text-center">
        <p className="text-[13px] text-gray-500">ジャンルデータがありません</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10.5 6a7.5 7.5 0 107.5 7.5h-7.5V6z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M13.5 10.5H21A7.5 7.5 0 0013.5 3v7.5z"
            />
          </svg>
          <h3 className="text-[14px] font-bold text-gray-900">ジャンル分布</h3>
          <span className="text-[11px] text-gray-400">({data.length}ジャンル)</span>
        </div>

        {/* Mode toggle */}
        <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
          <button
            onClick={() => setMode("pie")}
            className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-all ${
              mode === "pie"
                ? "bg-white text-[#4A7DFF] shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            円グラフ
          </button>
          <button
            onClick={() => setMode("treemap")}
            className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-all ${
              mode === "treemap"
                ? "bg-white text-[#4A7DFF] shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            ツリーマップ
          </button>
        </div>
      </div>

      {/* Chart */}
      <div className="p-4">
        <div className="flex flex-col lg:flex-row items-start gap-4">
          {/* Chart area */}
          <div className="flex-1 w-full">
            <ErrorBoundary fallback={<div className="flex items-center justify-center h-40 text-[12px] text-gray-400">グラフの描画に失敗しました</div>}>
              {mode === "pie" ? (
                <PieChart
                  data={data}
                  onSliceClick={handleSliceClick}
                  hoveredIndex={hoveredIndex}
                  onHover={setHoveredIndex}
                />
              ) : (
                <TreemapChart
                  data={data}
                  onSliceClick={handleSliceClick}
                  hoveredIndex={hoveredIndex}
                  onHover={setHoveredIndex}
                />
              )}
            </ErrorBoundary>
          </div>

          {/* Legend */}
          <div className="shrink-0 w-full lg:w-48 space-y-1 max-h-60 overflow-y-auto custom-scrollbar">
            {data.map((item, index) => {
              const pct = total > 0 ? ((item.count / total) * 100).toFixed(1) : "0";
              const isHovered = hoveredIndex === index;
              return (
                <button
                  key={item.genre}
                  onClick={() => handleSliceClick(item.genre)}
                  onMouseEnter={() => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  className={`flex items-center gap-2 w-full px-2 py-1.5 rounded-md text-left transition-colors ${
                    isHovered ? "bg-gray-50" : "hover:bg-gray-50"
                  }`}
                >
                  <span
                    className="w-3 h-3 rounded-sm shrink-0"
                    style={{ backgroundColor: getColor(index) }}
                  />
                  <span className="text-[11px] text-gray-700 truncate flex-1">
                    {item.genre}
                  </span>
                  <span className="text-[10px] text-gray-400 tabular-nums shrink-0">
                    {pct}%
                  </span>
                  <span className="text-[10px] text-gray-400 tabular-nums shrink-0 w-10 text-right">
                    {item.count.toLocaleString()}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Tooltip */}
        {hoveredIndex !== null && data[hoveredIndex] && (
          <div className="mt-3 px-3 py-2 bg-gray-50 rounded-lg border border-gray-100">
            <div className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-sm"
                style={{ backgroundColor: getColor(hoveredIndex) }}
              />
              <span className="text-[12px] font-semibold text-gray-800">
                {data[hoveredIndex].genre}
              </span>
            </div>
            <div className="flex items-center gap-4 mt-1">
              <span className="text-[11px] text-gray-500">
                広告数: <strong className="text-gray-700">{data[hoveredIndex].count.toLocaleString()}</strong>
              </span>
              <span className="text-[11px] text-gray-500">
                シェア:{" "}
                <strong className="text-gray-700">
                  {total > 0
                    ? ((data[hoveredIndex].count / total) * 100).toFixed(1)
                    : "0"}
                  %
                </strong>
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
