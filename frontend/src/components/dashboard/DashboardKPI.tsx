"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { formatNumber, formatYen } from "@/lib/format";

/* ─── Types ─── */

interface KPIData {
  total_ads: number;
  new_7d: number;
  hit_ads: number;
  hit_percentage: number;
  active_ads: number;
  avg_score: number;
  total_spend: number;
}

/* ─── Skeleton Card ─── */

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 px-4 py-3 animate-pulse">
      <div className="h-3 w-16 bg-gray-200 rounded mb-2" />
      <div className="h-6 w-24 bg-gray-200 rounded" />
    </div>
  );
}

/* ─── Score color helper ─── */

function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-600";
  if (score >= 40) return "text-amber-500";
  return "text-red-500";
}

function scoreBg(score: number): string {
  if (score >= 70) return "bg-emerald-50";
  if (score >= 40) return "bg-amber-50";
  return "bg-red-50";
}

/* ─── Main Component ─── */

export default function DashboardKPI() {
  const [data, setData] = useState<KPIData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchKPI = useCallback(async () => {
    try {
      const res = await fetchApi<KPIData>("/rankings/dashboard-kpi");
      setData(res);
    } catch {
      // TODO: API未実装時はモックデータを使用
      setData({
        total_ads: 12847,
        new_7d: 342,
        hit_ads: 1523,
        hit_percentage: 11.9,
        active_ads: 8934,
        avg_score: 54.2,
        total_spend: 2340000000,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKPI();
    // Pause polling when tab is hidden to reduce API load
    let interval: ReturnType<typeof setInterval> | null = null;
    const startPolling = () => {
      if (interval) clearInterval(interval);
      interval = setInterval(fetchKPI, 60000);
    };
    const stopPolling = () => {
      if (interval) { clearInterval(interval); interval = null; }
    };
    const handleVisibility = () => {
      if (document.hidden) { stopPolling(); }
      else { fetchKPI(); startPolling(); }
    };
    startPolling();
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [fetchKPI]);

  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (!data) return null;

  const cards = [
    {
      label: "総広告数",
      value: formatNumber(data.total_ads),
      suffix: "件",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
        </svg>
      ),
      color: "text-[#4A7DFF]",
      bg: "bg-blue-50",
    },
    {
      label: "新着7日",
      value: `+${formatNumber(data.new_7d)}`,
      suffix: "",
      icon: data.new_7d > 0 ? (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m6-6H6" />
        </svg>
      ),
      color: data.new_7d > 0 ? "text-emerald-600" : "text-gray-500",
      bg: data.new_7d > 0 ? "bg-emerald-50" : "bg-gray-50",
    },
    {
      label: "ヒット広告",
      value: formatNumber(data.hit_ads),
      suffix: "",
      badge: `${data.hit_percentage.toFixed(1)}%`,
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
        </svg>
      ),
      color: "text-orange-500",
      bg: "bg-orange-50",
    },
    {
      label: "アクティブ広告",
      value: formatNumber(data.active_ads),
      suffix: "件",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
        </svg>
      ),
      color: "text-violet-600",
      bg: "bg-violet-50",
    },
    {
      label: "平均スコア",
      value: data.avg_score.toFixed(1),
      suffix: "pt",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
        </svg>
      ),
      color: scoreColor(data.avg_score),
      bg: scoreBg(data.avg_score),
    },
    {
      label: "推定消化額",
      value: formatYen(data.total_spend),
      suffix: "",
      icon: (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      color: "text-teal-600",
      bg: "bg-teal-50",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
      {cards.map((card, i) => (
        <div
          key={i}
          className="bg-white rounded-xl border border-gray-200 px-4 py-3 hover:shadow-sm transition-shadow max-h-[80px] flex flex-col justify-center"
        >
          <div className="flex items-center gap-1.5 mb-1">
            <span className={`${card.bg} ${card.color} p-1 rounded-md`}>
              {card.icon}
            </span>
            <span className="text-[10px] text-gray-500 font-medium">
              {card.label}
            </span>
          </div>
          <div className="flex items-baseline gap-1">
            <span className={`text-[18px] font-bold ${card.color} leading-tight`}>
              {card.value}
            </span>
            {card.suffix && (
              <span className="text-[11px] text-gray-400">{card.suffix}</span>
            )}
            {"badge" in card && card.badge && (
              <span className="ml-1 px-1.5 py-0.5 text-[9px] font-bold bg-orange-100 text-orange-600 rounded-full leading-none">
                {card.badge}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
