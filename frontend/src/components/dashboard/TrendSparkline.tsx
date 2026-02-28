"use client";

import React from "react";

interface TrendSparklineProps {
  data: number[];
  color?: string;
  showDot?: boolean;
  width?: number;
  height?: number;
}

/**
 * Reusable mini sparkline chart component (pure SVG).
 * Shows trend data as a small line chart.
 */
export default function TrendSparkline({
  data,
  color = "#4A7DFF",
  showDot = true,
  width = 60,
  height = 20,
}: TrendSparklineProps) {
  if (!data || data.length < 2) {
    return (
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <line x1={0} y1={height / 2} x2={width} y2={height / 2} stroke="#e5e7eb" strokeWidth={1} />
      </svg>
    );
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 2;
  const effectiveHeight = height - padding * 2;
  const stepX = (width - padding * 2) / (data.length - 1);

  const points = data.map((val, i) => {
    const x = padding + i * stepX;
    const y = padding + effectiveHeight - ((val - min) / range) * effectiveHeight;
    return { x, y };
  });

  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");

  // Determine if trend is up or down for color hinting
  const lastPoint = points[points.length - 1];

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="inline-block">
      <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
      {showDot && lastPoint && (
        <circle cx={lastPoint.x} cy={lastPoint.y} r={2} fill={color} />
      )}
    </svg>
  );
}
