"use client";

import { useMemo } from "react";
import type { MetaInsight } from "@/types";

interface Props {
  insights: MetaInsight[];
  metric?: "spend" | "impressions" | "clicks" | "ctr";
}

export default function MetaInsightsChart({ insights, metric = "spend" }: Props) {
  const chartData = useMemo(() => {
    if (!insights.length) return [];

    // Sort by date
    const sorted = [...insights].sort(
      (a, b) => new Date(a.date_start).getTime() - new Date(b.date_start).getTime()
    );

    // Group by date
    const grouped = new Map<string, { spend: number; impressions: number; clicks: number; ctr: number }>();
    for (const row of sorted) {
      const date = row.date_start;
      const existing = grouped.get(date) || { spend: 0, impressions: 0, clicks: 0, ctr: 0 };
      existing.spend += Number(row.spend) || 0;
      existing.impressions += Number(row.impressions) || 0;
      existing.clicks += Number(row.clicks) || 0;
      grouped.set(date, existing);
    }

    // Calculate CTR
    return Array.from(grouped.entries()).map(([date, vals]) => ({
      date,
      ...vals,
      ctr: vals.impressions > 0 ? (vals.clicks / vals.impressions) * 100 : 0,
    }));
  }, [insights]);

  if (chartData.length === 0) {
    return (
      <div className="text-center py-8 text-[12px] text-gray-400">
        インサイトデータがありません
      </div>
    );
  }

  const metricLabels: Record<string, string> = {
    spend: "消化額 (¥)",
    impressions: "インプレッション",
    clicks: "クリック数",
    ctr: "CTR (%)",
  };

  const maxVal = Math.max(...chartData.map((d) => d[metric]), 1);

  return (
    <div className="card p-4">
      <h3 className="text-[13px] font-bold text-gray-800 mb-3">{metricLabels[metric]} 推移</h3>

      {/* Simple bar chart */}
      <div className="flex items-end gap-1 h-32">
        {chartData.map((d, i) => {
          const height = (d[metric] / maxVal) * 100;
          return (
            <div
              key={i}
              className="flex-1 flex flex-col items-center group relative"
            >
              <div
                className="w-full bg-[#4A7DFF] rounded-t hover:bg-[#3A6DEF] transition-colors"
                style={{ height: `${Math.max(height, 2)}%` }}
                title={`${d.date}: ${metric === "spend" ? `¥${d[metric].toLocaleString()}` : metric === "ctr" ? `${d[metric].toFixed(2)}%` : d[metric].toLocaleString()}`}
              />
            </div>
          );
        })}
      </div>

      {/* X-axis labels (show first, middle, last) */}
      <div className="flex justify-between mt-1 text-[9px] text-gray-400">
        <span>{chartData[0]?.date}</span>
        {chartData.length > 2 && (
          <span>{chartData[Math.floor(chartData.length / 2)]?.date}</span>
        )}
        <span>{chartData[chartData.length - 1]?.date}</span>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-3 mt-3 pt-3 border-t border-gray-100">
        {(["spend", "impressions", "clicks", "ctr"] as const).map((m) => {
          const total = chartData.reduce((sum, d) => sum + d[m], 0);
          const avg = total / chartData.length;
          return (
            <div key={m} className={`text-center ${m === metric ? "opacity-100" : "opacity-60"}`}>
              <p className="text-[10px] text-gray-500">{metricLabels[m]}</p>
              <p className="text-[12px] font-bold text-gray-800">
                {m === "spend"
                  ? `¥${Math.round(total).toLocaleString()}`
                  : m === "ctr"
                  ? `${avg.toFixed(2)}%`
                  : Math.round(total).toLocaleString()}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
