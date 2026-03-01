"use client";

import React, { useMemo } from "react";
import ErrorBoundary from "@/components/common/ErrorBoundary";

/* ─── Types ─── */

interface DistributionChartProps {
  data: number[];
  label?: string;
  color?: string;
  bins?: number;
}

/* ─── SVG Constants ─── */

const VB_W = 400;
const VB_H = 240;
const PAD = { top: 15, right: 15, bottom: 30, left: 40 };
const PLOT_W = VB_W - PAD.left - PAD.right;
const PLOT_H = VB_H - PAD.top - PAD.bottom;

/* ─── Main Component ─── */

export default function DistributionChart({
  data,
  label = "スコア分布",
  color = "#4A7DFF",
  bins: binCount = 10,
}: DistributionChartProps) {
  const { binEdges, binCounts, maxCount, mean, median } = useMemo(() => {
    if (!data || data.length === 0) {
      return { binEdges: [], binCounts: [], maxCount: 0, mean: 0, median: 0 };
    }

    const sorted = [...data].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const range = max - min || 1;
    const step = range / binCount;

    const edges: number[] = [];
    const counts: number[] = new Array(binCount).fill(0);

    for (let i = 0; i <= binCount; i++) {
      edges.push(min + step * i);
    }

    for (const v of sorted) {
      let idx = Math.floor((v - min) / step);
      if (idx >= binCount) idx = binCount - 1;
      counts[idx]++;
    }

    const mc = Math.max(1, ...counts);
    const sum = sorted.reduce((a, b) => a + b, 0);
    const m = sum / sorted.length;
    const mid =
      sorted.length % 2 === 0
        ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
        : sorted[Math.floor(sorted.length / 2)];

    return { binEdges: edges, binCounts: counts, maxCount: mc, mean: m, median: mid };
  }, [data, binCount]);

  if (!data || data.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 px-4 py-6 text-center">
        <p className="text-[11px] text-gray-400">データがありません</p>
      </div>
    );
  }

  const barW = PLOT_W / binCount - 2;
  const scaleY = (count: number) => PAD.top + PLOT_H - (count / maxCount) * PLOT_H;
  const scaleX = (val: number) => {
    const min = binEdges[0];
    const max = binEdges[binEdges.length - 1];
    const range = max - min || 1;
    return PAD.left + ((val - min) / range) * PLOT_W;
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 px-4 py-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <svg className="w-4 h-4" style={{ color }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">{label}</h3>
        <span className="text-[10px] text-gray-400">n={data.length}</span>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mb-1">
        <div className="flex items-center gap-1">
          <div className="w-4 h-[2px] bg-red-500" style={{ borderTop: "2px dashed #ef4444" }} />
          <span className="text-[9px] text-gray-500">平均 ({mean.toFixed(1)})</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-[2px] bg-blue-500" style={{ borderTop: "2px dashed #3b82f6" }} />
          <span className="text-[9px] text-gray-500">中央値 ({median.toFixed(1)})</span>
        </div>
      </div>

      {/* SVG Histogram */}
      <ErrorBoundary fallback={<div className="flex items-center justify-center h-40 text-[12px] text-gray-400">グラフの描画に失敗しました</div>}>
      <svg viewBox={`0 0 ${VB_W} ${VB_H}`} className="w-full h-auto">
        {/* Background */}
        <rect x={PAD.left} y={PAD.top} width={PLOT_W} height={PLOT_H} fill="#fafafa" rx="2" />

        {/* Horizontal grid */}
        {[0.25, 0.5, 0.75, 1].map((r) => (
          <line
            key={r}
            x1={PAD.left}
            y1={scaleY(maxCount * r)}
            x2={PAD.left + PLOT_W}
            y2={scaleY(maxCount * r)}
            stroke="#e5e7eb"
            strokeWidth="0.5"
          />
        ))}

        {/* Bars */}
        {binCounts.map((count, i) => {
          const x = PAD.left + i * (PLOT_W / binCount) + 1;
          const h = (count / maxCount) * PLOT_H;
          const y = PAD.top + PLOT_H - h;
          return (
            <rect
              key={i}
              x={x}
              y={y}
              width={barW}
              height={h}
              fill={color}
              fillOpacity="0.7"
              rx="1"
            >
              <title>{`${binEdges[i].toFixed(0)}-${binEdges[i + 1].toFixed(0)}: ${count}件`}</title>
            </rect>
          );
        })}

        {/* Mean line (dashed red) */}
        <line
          x1={scaleX(mean)}
          y1={PAD.top}
          x2={scaleX(mean)}
          y2={PAD.top + PLOT_H}
          stroke="#ef4444"
          strokeWidth="1.5"
          strokeDasharray="4 3"
        />

        {/* Median line (dashed blue) */}
        <line
          x1={scaleX(median)}
          y1={PAD.top}
          x2={scaleX(median)}
          y2={PAD.top + PLOT_H}
          stroke="#3b82f6"
          strokeWidth="1.5"
          strokeDasharray="4 3"
        />

        {/* X-axis labels */}
        {binEdges.filter((_, i) => i % 2 === 0 || i === binEdges.length - 1).map((edge, i) => (
          <text
            key={i}
            x={scaleX(edge)}
            y={VB_H - 8}
            fontSize="8"
            fill="#9ca3af"
            textAnchor="middle"
          >
            {edge.toFixed(0)}
          </text>
        ))}

        {/* Y-axis labels */}
        {[0, 0.5, 1].map((r) => (
          <text
            key={r}
            x={PAD.left - 4}
            y={scaleY(maxCount * r) + 3}
            fontSize="8"
            fill="#9ca3af"
            textAnchor="end"
          >
            {Math.round(maxCount * r)}
          </text>
        ))}
      </svg>
      </ErrorBoundary>
    </div>
  );
}
