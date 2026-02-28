"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

/* ─── Types ─── */

interface FunnelStage {
  label: string;
  count: number;
}

interface FunnelChartProps {
  data?: FunnelStage[];
}

/* ─── Default funnel stages ─── */

const DEFAULT_STAGES: FunnelStage[] = [
  { label: "全広告", count: 12847 },
  { label: "アクティブ", count: 8934 },
  { label: "ヒットライン超え", count: 1523 },
  { label: "メガヒット", count: 287 },
];

const STAGE_COLORS = ["#9ca3af", "#4A7DFF", "#f59e0b", "#ef4444"];

/* ─── Main Component ─── */

export default function FunnelChart({ data: propData }: FunnelChartProps) {
  const [stages, setStages] = useState<FunnelStage[]>(propData || DEFAULT_STAGES);
  const [loading, setLoading] = useState(!propData);

  const loadData = useCallback(async () => {
    if (propData) return;
    setLoading(true);
    try {
      const res = await fetchApi<{ stages?: FunnelStage[]; items?: FunnelStage[] }>(
        "/rankings/funnel-stats"
      );
      const items = res?.stages || res?.items || (Array.isArray(res) ? res : []);
      if (Array.isArray(items) && items.length > 0) {
        setStages(items);
      } else {
        setStages(DEFAULT_STAGES);
      }
    } catch {
      setStages(DEFAULT_STAGES);
    } finally {
      setLoading(false);
    }
  }, [propData]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (propData) setStages(propData);
  }, [propData]);

  const maxCount = Math.max(1, ...stages.map((s) => s.count));

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 px-4 py-4 animate-pulse">
        <div className="h-4 w-32 bg-gray-200 rounded mb-4" />
        <div className="space-y-3">
          {[100, 75, 45, 20].map((w, i) => (
            <div key={i} className="h-8 bg-gray-100 rounded" style={{ width: `${w}%` }} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 px-4 py-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0012 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 01-2.031.352 5.988 5.988 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.971zm-16.5.52c.99-.203 1.99-.377 3-.52m0 0l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.989 5.989 0 01-2.031.352 5.989 5.989 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L5.25 4.971z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">広告ファネル</h3>
        <span className="text-[10px] text-gray-400">ステージ別の広告数</span>
      </div>

      {/* Funnel bars */}
      <div className="space-y-2">
        {stages.map((stage, i) => {
          const widthPct = Math.max((stage.count / maxCount) * 100, 8);
          const dropOff =
            i > 0 && stages[i - 1].count > 0
              ? (((stages[i - 1].count - stage.count) / stages[i - 1].count) * 100).toFixed(1)
              : null;
          const conversionRate =
            i > 0 && stages[0].count > 0
              ? ((stage.count / stages[0].count) * 100).toFixed(1)
              : null;

          return (
            <div key={i}>
              {/* Drop-off indicator */}
              {dropOff && (
                <div className="flex items-center gap-1 mb-1 ml-1">
                  <svg className="w-3 h-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
                  </svg>
                  <span className="text-[9px] text-gray-400">
                    -{dropOff}% 減少
                  </span>
                </div>
              )}
              {/* Bar row */}
              <div className="flex items-center gap-2">
                <div className="w-24 shrink-0">
                  <span className="text-[11px] text-gray-700 font-medium">{stage.label}</span>
                </div>
                <div className="flex-1 relative">
                  <div
                    className="h-8 rounded-md flex items-center transition-all duration-500"
                    style={{
                      width: `${widthPct}%`,
                      backgroundColor: STAGE_COLORS[i % STAGE_COLORS.length],
                    }}
                  >
                    <span className="text-[11px] font-bold text-white px-2 whitespace-nowrap">
                      {stage.count.toLocaleString()}
                    </span>
                  </div>
                </div>
                {conversionRate && (
                  <span className="text-[10px] text-gray-400 shrink-0 w-12 text-right">
                    {conversionRate}%
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
