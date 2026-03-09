"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import ErrorBoundary from "@/components/common/ErrorBoundary";

/* ─── Types ─── */

interface AdPoint {
  id: number;
  title: string;
  hit_score: number;
  cumulative_views: number;
  platform: string;
}

interface TooltipState {
  ad: AdPoint;
  x: number;
  y: number;
}

interface ScatterPlotProps {
  onAdSelect?: (adId: number) => void;
}

/* ─── Platform color map ─── */

const PLATFORM_COLORS: Record<string, string> = {
  facebook: "#4A7DFF",
  instagram: "#ec4899",
  tiktok: "#6b7280",
  youtube: "#ef4444",
  meta: "#3b82f6",
  x_twitter: "#1d9bf0",
  line: "#06c755",
};

function getPlatformColor(platform: string): string {
  return PLATFORM_COLORS[platform?.toLowerCase()] || "#9ca3af";
}

/* ─── SVG Constants ─── */

const VB_W = 400;
const VB_H = 300;
const PAD = { top: 20, right: 20, bottom: 35, left: 50 };
const PLOT_W = VB_W - PAD.left - PAD.right;
const PLOT_H = VB_H - PAD.top - PAD.bottom;

/* ─── Main Component ─── */

export default function ScatterPlot({ onAdSelect }: ScatterPlotProps) {
  const [points, setPoints] = useState<AdPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchApi<{ items?: AdPoint[]; ads?: AdPoint[] }>(
        "/rankings/hit-ads",
        { params: { limit: 50 } }
      );
      const items = res?.items || res?.ads || (Array.isArray(res) ? res : []);
      setPoints(Array.isArray(items) && items.length > 0 ? items : []);
    } catch {
      setPoints([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const maxViews = useMemo(() => Math.max(1, ...points.map((p) => p.cumulative_views)), [points]);

  const platforms = useMemo(() => {
    const set = new Set(points.map((p) => p.platform));
    return Array.from(set);
  }, [points]);

  const scaleX = useCallback((score: number) => PAD.left + (score / 100) * PLOT_W, []);
  const scaleY = useCallback(
    (views: number) => PAD.top + PLOT_H - (views / maxViews) * PLOT_H,
    [maxViews]
  );

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 px-4 py-4 animate-pulse">
        <div className="h-4 w-40 bg-gray-200 rounded mb-4" />
        <div className="h-56 bg-gray-100 rounded" />
      </div>
    );
  }

  const formatViews = (v: number): string => {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
    return String(v);
  };

  /* Quadrant dividers */
  const midX = scaleX(50);
  const midY = scaleY(maxViews / 2);

  return (
    <div className="bg-white rounded-xl border border-gray-200 px-4 py-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">スコア vs 再生数 散布図</h3>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 mb-2 flex-wrap">
        {platforms.map((p) => (
          <div key={p} className="flex items-center gap-1">
            <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: getPlatformColor(p) }} />
            <span className="text-[9px] text-gray-500">{p}</span>
          </div>
        ))}
      </div>

      {/* SVG Chart */}
      <ErrorBoundary fallback={<div className="flex items-center justify-center h-56 text-[12px] text-gray-400">グラフの描画に失敗しました</div>}>
      <div className="relative">
        <svg viewBox={`0 0 ${VB_W} ${VB_H}`} className="w-full h-auto">
          {/* Background */}
          <rect x={PAD.left} y={PAD.top} width={PLOT_W} height={PLOT_H} fill="#fafafa" rx="2" />

          {/* Grid lines */}
          {[0, 25, 50, 75, 100].map((v) => (
            <line
              key={`gx-${v}`}
              x1={scaleX(v)}
              y1={PAD.top}
              x2={scaleX(v)}
              y2={PAD.top + PLOT_H}
              stroke="#e5e7eb"
              strokeWidth="0.5"
            />
          ))}
          {[0, 0.25, 0.5, 0.75, 1].map((r) => (
            <line
              key={`gy-${r}`}
              x1={PAD.left}
              y1={scaleY(maxViews * r)}
              x2={PAD.left + PLOT_W}
              y2={scaleY(maxViews * r)}
              stroke="#e5e7eb"
              strokeWidth="0.5"
            />
          ))}

          {/* Quadrant dividers (dashed) */}
          <line x1={midX} y1={PAD.top} x2={midX} y2={PAD.top + PLOT_H} stroke="#d1d5db" strokeWidth="0.8" strokeDasharray="4 3" />
          <line x1={PAD.left} y1={midY} x2={PAD.left + PLOT_W} y2={midY} stroke="#d1d5db" strokeWidth="0.8" strokeDasharray="4 3" />

          {/* Quadrant labels */}
          <text x={PAD.left + 4} y={PAD.top + 12} fontSize="8" fill="#9ca3af">低スコア・高再生</text>
          <text x={PAD.left + PLOT_W - 4} y={PAD.top + 12} fontSize="8" fill="#22c55e" textAnchor="end">高スコア・高再生</text>
          <text x={PAD.left + 4} y={PAD.top + PLOT_H - 4} fontSize="8" fill="#9ca3af">低スコア・低再生</text>
          <text x={PAD.left + PLOT_W - 4} y={PAD.top + PLOT_H - 4} fontSize="8" fill="#f59e0b" textAnchor="end">高スコア・低再生</text>

          {/* X-axis labels */}
          {[0, 25, 50, 75, 100].map((v) => (
            <text key={`xl-${v}`} x={scaleX(v)} y={VB_H - 10} fontSize="9" fill="#9ca3af" textAnchor="middle">
              {v}
            </text>
          ))}
          <text x={PAD.left + PLOT_W / 2} y={VB_H - 1} fontSize="9" fill="#6b7280" textAnchor="middle">
            hit_score
          </text>

          {/* Y-axis labels */}
          {[0, 0.25, 0.5, 0.75, 1].map((r) => (
            <text key={`yl-${r}`} x={PAD.left - 4} y={scaleY(maxViews * r) + 3} fontSize="8" fill="#9ca3af" textAnchor="end">
              {formatViews(maxViews * r)}
            </text>
          ))}
          <text x={12} y={PAD.top + PLOT_H / 2} fontSize="9" fill="#6b7280" textAnchor="middle" transform={`rotate(-90, 12, ${PAD.top + PLOT_H / 2})`}>
            累計再生数
          </text>

          {/* Data points */}
          {points.map((p) => (
            <circle
              key={p.id}
              cx={scaleX(p.hit_score)}
              cy={scaleY(p.cumulative_views)}
              r="4.5"
              fill={getPlatformColor(p.platform)}
              fillOpacity="0.75"
              stroke="white"
              strokeWidth="1"
              className="cursor-pointer transition-all hover:r-[6]"
              onMouseEnter={(e) => {
                const svg = (e.target as SVGElement).closest("svg");
                const rect = svg?.getBoundingClientRect();
                if (!rect) return;
                const ptX = ((scaleX(p.hit_score)) / VB_W) * rect.width;
                const ptY = ((scaleY(p.cumulative_views)) / VB_H) * rect.height;
                setTooltip({ ad: p, x: ptX, y: ptY });
              }}
              onMouseLeave={() => setTooltip(null)}
              onClick={() => onAdSelect?.(p.id)}
            />
          ))}
        </svg>

        {/* Tooltip overlay */}
        {tooltip && (
          <div
            className="absolute z-50 bg-gray-900 text-white rounded-lg px-3 py-2 shadow-lg pointer-events-none"
            style={{
              left: tooltip.x,
              top: tooltip.y,
              transform: "translate(-50%, -110%)",
            }}
          >
            <p className="text-[11px] font-bold truncate max-w-[160px]">{tooltip.ad.title}</p>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[10px] text-gray-300">
                スコア: <span className="text-white font-bold">{tooltip.ad.hit_score}</span>
              </span>
              <span className="text-[10px] text-gray-300">
                再生: <span className="text-white font-bold">{formatViews(tooltip.ad.cumulative_views)}</span>
              </span>
            </div>
            <div className="flex items-center gap-1 mt-0.5">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getPlatformColor(tooltip.ad.platform) }} />
              <span className="text-[9px] text-gray-400">{tooltip.ad.platform}</span>
            </div>
          </div>
        )}
      </div>
      </ErrorBoundary>
    </div>
  );
}
