"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { formatNumber } from "@/lib/format";

// ─── Types ───

interface PatternDistribution {
  name: string;
  count: number;
  percentage: number;
}

interface RepresentativeAd {
  ad_id: number;
  title: string;
  advertiser_name: string;
  hit_score: number;
  thumbnail: string;
  platform: string;
}

interface AnalysisGroup {
  ad_count: number;
  percentage: number;
  avg_views: number;
  avg_spend: number;
  avg_likes: number;
  avg_score: number;
  hook_types: PatternDistribution[];
  cta_types: PatternDistribution[];
  offer_types: PatternDistribution[];
  representative_ads: RepresentativeAd[];
}


// ─── Helper: Horizontal Bar ───

function HorizontalBar({ label, value, maxValue, color }: { label: string; value: number; maxValue: number; color: string }) {
  const width = maxValue > 0 ? Math.min(100, (value / maxValue) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-gray-500 w-24 shrink-0 truncate">{label}</span>
      <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${width}%` }} />
      </div>
      <span className="text-[10px] font-medium text-gray-700 w-10 text-right">{value.toFixed(1)}%</span>
    </div>
  );
}

// ─── Main Component ───

interface SuccessFailureAnalysisProps {
  onAdSelect?: (adId: number) => void;
  genre?: string;
}

export default function SuccessFailureAnalysis({ onAdSelect, genre }: SuccessFailureAnalysisProps) {
  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState<AnalysisGroup | null>(null);
  const [failure, setFailure] = useState<AnalysisGroup | null>(null);

  const [reusePoints, setReusePoints] = useState<string[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchApi<{
        success?: AnalysisGroup;
        failure?: AnalysisGroup;
        reuse_points?: string[];
        hit_ads?: Array<Record<string, unknown>>;
        non_hit_ads?: Array<Record<string, unknown>>;
      }>("/rankings/hit-ads", {
        params: { genre: genre || undefined, analysis: "true" },
      });
      if (data.success && data.failure) {
        setSuccess(data.success);
        setFailure(data.failure);
        setReusePoints(data.reuse_points || []);
      } else {
        // Endpoint returns flat hit_ads list - build groups from it
        setSuccess(null);
        setFailure(null);
      }
    } catch {
      setSuccess(null);
      setFailure(null);
    } finally {
      setLoading(false);
    }
  }, [genre]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
            <div className="h-5 bg-gray-200 rounded w-32 mb-4" />
            <div className="space-y-3">
              <div className="h-4 bg-gray-100 rounded w-full" />
              <div className="h-4 bg-gray-100 rounded w-3/4" />
              <div className="h-4 bg-gray-100 rounded w-1/2" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!success || !failure) return null;

  return (
    <div className="space-y-4">
      {/* Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Success Side */}
        <div className="bg-white rounded-xl border-2 border-green-200">
          <div className="px-5 py-4 border-b border-green-100 bg-green-50 rounded-t-xl">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <h3 className="text-[14px] font-bold text-green-800">成功広告の特徴</h3>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-green-700">
              <span>{success.ad_count}件 ({success.percentage}%)</span>
              <span>平均スコア: {success.avg_score}</span>
            </div>
          </div>
          <div className="p-5 space-y-4">
            {/* Metrics */}
            <div className="grid grid-cols-3 gap-3">
              <div className="text-center p-2 bg-green-50 rounded-lg">
                <div className="text-[10px] text-gray-500">平均再生数</div>
                <div className="text-[14px] font-bold text-gray-900">{formatNumber(success.avg_views)}</div>
              </div>
              <div className="text-center p-2 bg-green-50 rounded-lg">
                <div className="text-[10px] text-gray-500">平均消化額</div>
                <div className="text-[14px] font-bold text-gray-900">{formatNumber(success.avg_spend)}</div>
              </div>
              <div className="text-center p-2 bg-green-50 rounded-lg">
                <div className="text-[10px] text-gray-500">平均いいね</div>
                <div className="text-[14px] font-bold text-gray-900">{formatNumber(success.avg_likes)}</div>
              </div>
            </div>
            {/* Hook distribution */}
            <div>
              <h4 className="text-[11px] font-bold text-gray-700 mb-2">フックタイプ分布</h4>
              <div className="space-y-1.5">
                {success.hook_types.map((h) => (
                  <HorizontalBar key={h.name} label={h.name} value={h.percentage} maxValue={50} color="bg-green-400" />
                ))}
              </div>
            </div>
            {/* CTA distribution */}
            <div>
              <h4 className="text-[11px] font-bold text-gray-700 mb-2">CTAタイプ分布</h4>
              <div className="space-y-1.5">
                {success.cta_types.map((c) => (
                  <HorizontalBar key={c.name} label={c.name} value={c.percentage} maxValue={50} color="bg-green-400" />
                ))}
              </div>
            </div>
            {/* Representative ads */}
            <div>
              <h4 className="text-[11px] font-bold text-gray-700 mb-2">代表的な成功広告</h4>
              <div className="space-y-2">
                {success.representative_ads.map((ad) => (
                  <button
                    key={ad.ad_id}
                    onClick={() => onAdSelect?.(ad.ad_id)}
                    className="w-full flex items-center gap-3 p-2.5 rounded-lg border border-gray-200 hover:border-green-300 hover:bg-green-50 transition-colors text-left"
                  >
                    <div className="w-10 h-10 bg-gray-200 rounded-lg shrink-0 flex items-center justify-center text-[10px] text-gray-400">
                      {ad.platform.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-medium text-gray-900 truncate">{ad.title}</p>
                      <p className="text-[10px] text-gray-400">{ad.advertiser_name}</p>
                    </div>
                    <span className="shrink-0 px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-[10px] font-bold">{ad.hit_score}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Failure Side */}
        <div className="bg-white rounded-xl border-2 border-red-200">
          <div className="px-5 py-4 border-b border-red-100 bg-red-50 rounded-t-xl">
            <div className="flex items-center gap-2 mb-1">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <h3 className="text-[14px] font-bold text-red-800">失敗広告の特徴</h3>
            </div>
            <div className="flex items-center gap-3 text-[11px] text-red-700">
              <span>{failure.ad_count}件 ({failure.percentage}%)</span>
              <span>平均スコア: {failure.avg_score}</span>
            </div>
          </div>
          <div className="p-5 space-y-4">
            {/* Metrics */}
            <div className="grid grid-cols-3 gap-3">
              <div className="text-center p-2 bg-red-50 rounded-lg">
                <div className="text-[10px] text-gray-500">平均再生数</div>
                <div className="text-[14px] font-bold text-gray-900">{formatNumber(failure.avg_views)}</div>
              </div>
              <div className="text-center p-2 bg-red-50 rounded-lg">
                <div className="text-[10px] text-gray-500">平均消化額</div>
                <div className="text-[14px] font-bold text-gray-900">{formatNumber(failure.avg_spend)}</div>
              </div>
              <div className="text-center p-2 bg-red-50 rounded-lg">
                <div className="text-[10px] text-gray-500">平均いいね</div>
                <div className="text-[14px] font-bold text-gray-900">{formatNumber(failure.avg_likes)}</div>
              </div>
            </div>
            {/* Hook distribution */}
            <div>
              <h4 className="text-[11px] font-bold text-gray-700 mb-2">フックタイプ分布</h4>
              <div className="space-y-1.5">
                {failure.hook_types.map((h) => (
                  <HorizontalBar key={h.name} label={h.name} value={h.percentage} maxValue={50} color="bg-red-400" />
                ))}
              </div>
            </div>
            {/* CTA distribution */}
            <div>
              <h4 className="text-[11px] font-bold text-gray-700 mb-2">CTAタイプ分布</h4>
              <div className="space-y-1.5">
                {failure.cta_types.map((c) => (
                  <HorizontalBar key={c.name} label={c.name} value={c.percentage} maxValue={50} color="bg-red-400" />
                ))}
              </div>
            </div>
            {/* Representative ads */}
            <div>
              <h4 className="text-[11px] font-bold text-gray-700 mb-2">代表的な失敗広告</h4>
              <div className="space-y-2">
                {failure.representative_ads.map((ad) => (
                  <button
                    key={ad.ad_id}
                    onClick={() => onAdSelect?.(ad.ad_id)}
                    className="w-full flex items-center gap-3 p-2.5 rounded-lg border border-gray-200 hover:border-red-300 hover:bg-red-50 transition-colors text-left"
                  >
                    <div className="w-10 h-10 bg-gray-200 rounded-lg shrink-0 flex items-center justify-center text-[10px] text-gray-400">
                      {ad.platform.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-medium text-gray-900 truncate">{ad.title}</p>
                      <p className="text-[10px] text-gray-400">{ad.advertiser_name}</p>
                    </div>
                    <span className="shrink-0 px-1.5 py-0.5 bg-red-100 text-red-700 rounded text-[10px] font-bold">{ad.hit_score}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Reuse Points */}
      <div className="bg-white rounded-xl border-2 border-blue-200">
        <div className="px-5 py-4 border-b border-blue-100 bg-blue-50 rounded-t-xl">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
            </svg>
            <h3 className="text-[14px] font-bold text-blue-800">即転用できるポイント</h3>
          </div>
        </div>
        <div className="p-5">
          <div className="space-y-3">
            {reusePoints.map((point, idx) => (
              <div key={idx} className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg">
                <div className="w-6 h-6 rounded-full bg-blue-500 text-white flex items-center justify-center text-[11px] font-bold shrink-0">
                  {idx + 1}
                </div>
                <p className="text-[12px] text-gray-700 leading-relaxed">{point}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
