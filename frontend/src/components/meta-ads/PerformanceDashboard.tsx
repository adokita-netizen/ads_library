"use client";

import { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import type {
  PerformanceSummary,
  DailyTrendsData,
  DailyTrendPoint,
  SmartInsight,
} from "@/types";
import { metaMarketingApi } from "@/lib/api";

interface Props {
  accountId: string;
}

const SEVERITY_STYLES: Record<string, { bg: string; border: string; icon: string }> = {
  critical: { bg: "bg-red-50", border: "border-red-200", icon: "!!" },
  negative: { bg: "bg-orange-50", border: "border-orange-200", icon: "↓" },
  warning: { bg: "bg-amber-50", border: "border-amber-200", icon: "⚠" },
  positive: { bg: "bg-green-50", border: "border-green-200", icon: "↑" },
};

export default function PerformanceDashboard({ accountId }: Props) {
  const [summary, setSummary] = useState<PerformanceSummary | null>(null);
  const [trends, setTrends] = useState<DailyTrendsData | null>(null);
  const [smartInsights, setSmartInsights] = useState<SmartInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);
  const [trendMetric, setTrendMetric] = useState<keyof DailyTrendPoint>("spend");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [summaryRes, trendsRes, insightsRes] = await Promise.all([
        metaMarketingApi.getPerformanceSummary(accountId, { days }).catch(() => null),
        metaMarketingApi.getDailyTrends(accountId, { days: 30 }).catch(() => null),
        metaMarketingApi.getSmartInsights(accountId).catch(() => null),
      ]);
      if (summaryRes?.data) setSummary(summaryRes.data);
      if (trendsRes?.data) setTrends(trendsRes.data);
      if (insightsRes?.data) setSmartInsights(Array.isArray(insightsRes.data) ? insightsRes.data : []);
    } catch {
      toast.error("パフォーマンスデータの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [accountId, days]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return <div className="text-center py-8 text-[12px] text-gray-400">パフォーマンスデータを読み込み中...</div>;
  }

  const kpiCards = summary ? [
    { label: "インプレッション", value: summary.current_period.impressions.toLocaleString(), delta: summary.deltas.impressions },
    { label: "クリック", value: summary.current_period.clicks.toLocaleString(), delta: summary.deltas.clicks },
    { label: "消化額", value: `¥${Math.round(summary.current_period.spend).toLocaleString()}`, delta: summary.deltas.spend },
    { label: "CTR", value: `${summary.current_period.ctr}%`, delta: summary.deltas.ctr },
    { label: "CPC", value: `¥${summary.current_period.cpc.toLocaleString()}`, delta: summary.deltas.cpc, invert: true },
    { label: "CV", value: summary.current_period.conversions.toLocaleString(), delta: summary.deltas.conversions },
    { label: "CPA", value: summary.current_period.cpa > 0 ? `¥${Math.round(summary.current_period.cpa).toLocaleString()}` : "-", delta: summary.deltas.cpa, invert: true },
    { label: "ROAS", value: summary.current_period.roas > 0 ? `${summary.current_period.roas}x` : "-", delta: summary.deltas.roas },
  ] : [];

  // Trend chart: simple CSS bar chart
  const trendPoints = trends?.trends || [];
  const maxTrendVal = Math.max(...trendPoints.map((t) => Number(t[trendMetric]) || 0), 1);

  return (
    <div className="space-y-5">
      {/* Period selector + refresh */}
      <div className="flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-gray-800">パフォーマンスダッシュボード</h3>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="text-[11px] border border-gray-200 rounded-lg px-2 py-1"
            aria-label="集計期間"
          >
            <option value={7}>直近7日</option>
            <option value={14}>直近14日</option>
            <option value={30}>直近30日</option>
          </select>
          <button onClick={loadData} className="btn-secondary text-[11px] px-3 py-1">
            更新
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {kpiCards.map((kpi) => {
            const delta = kpi.delta;
            const isPositive = kpi.invert ? (delta !== null && delta !== undefined && delta < 0) : (delta !== null && delta !== undefined && delta > 0);
            const isNegative = kpi.invert ? (delta !== null && delta !== undefined && delta > 0) : (delta !== null && delta !== undefined && delta < 0);
            return (
              <div key={kpi.label} className="card p-3">
                <p className="text-[10px] text-gray-500 mb-1">{kpi.label}</p>
                <p className="text-[16px] font-bold text-gray-800">{kpi.value}</p>
                {delta !== null && delta !== undefined && (
                  <p className={`text-[10px] mt-0.5 ${isPositive ? "text-green-600" : isNegative ? "text-red-600" : "text-gray-400"}`}>
                    {delta > 0 ? "+" : ""}{delta}% vs 前期間
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Smart Insights */}
      {smartInsights.length > 0 && (
        <div className="card p-4">
          <h4 className="text-[13px] font-bold text-gray-800 mb-3">AIインサイト</h4>
          <div className="space-y-2">
            {smartInsights.map((insight, idx) => {
              const style = SEVERITY_STYLES[insight.severity] || SEVERITY_STYLES.warning;
              return (
                <div key={idx} className={`${style.bg} border ${style.border} rounded-lg p-3`}>
                  <div className="flex items-start gap-2">
                    <span className="text-[12px] font-bold shrink-0">{style.icon}</span>
                    <div>
                      <p className="text-[12px] font-medium text-gray-800">{insight.title}</p>
                      <p className="text-[11px] text-gray-600 mt-0.5">{insight.description}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Trend Chart */}
      {trendPoints.length > 0 && (
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-[13px] font-bold text-gray-800">日別トレンド</h4>
            <select
              value={trendMetric}
              onChange={(e) => setTrendMetric(e.target.value as keyof DailyTrendPoint)}
              className="text-[11px] border border-gray-200 rounded-lg px-2 py-1"
              aria-label="トレンド指標"
            >
              <option value="spend">消化額</option>
              <option value="impressions">IMP</option>
              <option value="clicks">クリック</option>
              <option value="ctr">CTR</option>
              <option value="conversions">CV</option>
              <option value="cpa">CPA</option>
            </select>
          </div>
          <div className="flex items-end gap-[2px] h-32">
            {trendPoints.map((point, idx) => {
              const val = Number(point[trendMetric]) || 0;
              const heightPct = maxTrendVal > 0 ? (val / maxTrendVal) * 100 : 0;
              const dateStr = typeof point.date === "string" ? point.date.slice(5) : "";
              return (
                <div key={idx} className="flex-1 flex flex-col items-center justify-end h-full group relative">
                  <div
                    className="w-full bg-[#4A7DFF] rounded-t-sm transition-all hover:bg-[#3A6DEF] min-h-[2px]"
                    style={{ height: `${Math.max(heightPct, 1)}%` }}
                    title={`${dateStr}: ${trendMetric === "spend" || trendMetric === "cpa" ? "¥" : ""}${typeof val === "number" ? val.toLocaleString() : val}${trendMetric === "ctr" ? "%" : ""}`}
                  />
                  {trendPoints.length <= 14 && (
                    <span className="text-[8px] text-gray-400 mt-0.5">{dateStr}</span>
                  )}
                </div>
              );
            })}
          </div>
          {trendPoints.length > 14 && (
            <div className="flex justify-between mt-1">
              <span className="text-[8px] text-gray-400">{typeof trendPoints[0]?.date === "string" ? trendPoints[0].date.slice(5) : ""}</span>
              <span className="text-[8px] text-gray-400">{typeof trendPoints[trendPoints.length - 1]?.date === "string" ? trendPoints[trendPoints.length - 1].date.slice(5) : ""}</span>
            </div>
          )}
        </div>
      )}

      {!summary && smartInsights.length === 0 && trendPoints.length === 0 && (
        <div className="text-center py-12 text-[13px] text-gray-400">
          パフォーマンスデータがありません。データを同期してください。
        </div>
      )}
    </div>
  );
}
