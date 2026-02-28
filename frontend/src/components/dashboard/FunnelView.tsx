"use client";

import React, { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface FunnelData {
  ad_score?: number;
  lp_score?: number;
  funnel_score?: number;
  weak_point?: string;
  ad_id?: number;
  product_name?: string;
}

interface FunnelViewProps {
  adIds: number[];
  onAdSelect?: (adId: number) => void;
}

const weakPointLabels: Record<string, string> = {
  ad: "広告クリエイティブ", lp: "LP", alignment: "広告↔LP一貫性",
  cta: "CTA", offer: "オファー", creative: "クリエイティブ品質",
};

export default function FunnelView({ adIds, onAdSelect }: FunnelViewProps) {
  const [funnels, setFunnels] = useState<FunnelData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (adIds.length === 0) {
      setFunnels([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all(
      adIds.slice(0, 6).map((id) =>
        fetchApi<FunnelData>(`/rankings/lp-analysis/${id}`)
          .then((res) => ({ ...res, ad_id: id }))
          .catch(() => ({ ad_id: id } as FunnelData))
      )
    )
      .then(setFunnels)
      .finally(() => setLoading(false));
  }, [adIds]);

  if (loading) {
    return (
      <div className="card px-4 py-4 animate-pulse space-y-3">
        <div className="h-4 bg-gray-200 rounded w-28" />
        <div className="h-32 bg-gray-100 rounded" />
      </div>
    );
  }

  if (funnels.length === 0) {
    return (
      <div className="card px-4 py-8 text-center">
        <svg className="w-8 h-8 text-gray-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z" />
        </svg>
        <p className="text-[11px] text-gray-400">広告を選択してファネル分析を表示</p>
      </div>
    );
  }

  const getScoreColor = (score: number | undefined) => {
    if (score == null) return "#94a3b8";
    if (score >= 80) return "#22c55e";
    if (score >= 50) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z" />
        </svg>
        <h4 className="text-[12px] font-bold text-gray-900">ファネル分析</h4>
      </div>

      {funnels.map((f) => (
        <div
          key={f.ad_id}
          className="card px-4 py-3 cursor-pointer hover:shadow-md transition-all"
          onClick={() => f.ad_id && onAdSelect?.(f.ad_id)}
        >
          {f.product_name && (
            <p className="text-[10px] font-medium text-gray-700 mb-2 truncate">{f.product_name}</p>
          )}

          {/* Funnel flow */}
          <div className="flex items-center gap-1">
            {/* Ad score */}
            <div className="flex-1 text-center">
              <div
                className="mx-auto w-12 h-12 rounded-full flex items-center justify-center border-2"
                style={{ borderColor: getScoreColor(f.ad_score), color: getScoreColor(f.ad_score) }}
              >
                <span className="text-[13px] font-bold">{f.ad_score ?? "-"}</span>
              </div>
              <p className="text-[8px] text-gray-400 mt-1">広告</p>
            </div>

            {/* Arrow */}
            <svg className="w-5 h-5 text-gray-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>

            {/* LP score */}
            <div className="flex-1 text-center">
              <div
                className="mx-auto w-12 h-12 rounded-full flex items-center justify-center border-2"
                style={{ borderColor: getScoreColor(f.lp_score), color: getScoreColor(f.lp_score) }}
              >
                <span className="text-[13px] font-bold">{f.lp_score ?? "-"}</span>
              </div>
              <p className="text-[8px] text-gray-400 mt-1">LP</p>
            </div>

            {/* Arrow */}
            <svg className="w-5 h-5 text-gray-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>

            {/* Funnel score */}
            <div className="flex-1 text-center">
              <div
                className="mx-auto w-12 h-12 rounded-full flex items-center justify-center border-2 bg-gray-50"
                style={{ borderColor: getScoreColor(f.funnel_score), color: getScoreColor(f.funnel_score) }}
              >
                <span className="text-[13px] font-bold">{f.funnel_score ?? "-"}</span>
              </div>
              <p className="text-[8px] text-gray-400 mt-1">ファネル</p>
            </div>
          </div>

          {/* Weak point */}
          {f.weak_point && (
            <div className="mt-2 flex items-center gap-1.5">
              <svg className="w-3 h-3 text-amber-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              <span className="text-[9px] text-amber-600">
                弱点: {weakPointLabels[f.weak_point] || f.weak_point}
              </span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
