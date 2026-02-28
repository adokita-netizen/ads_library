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

// ─── Mock Data (TODO: Replace with API calls when endpoints are ready) ───

const MOCK_SUCCESS: AnalysisGroup = {
  ad_count: 127,
  percentage: 32.5,
  avg_views: 285000,
  avg_spend: 1250000,
  avg_likes: 3400,
  avg_score: 82,
  hook_types: [
    { name: "質問型", count: 48, percentage: 37.8 },
    { name: "衝撃型", count: 35, percentage: 27.6 },
    { name: "ベネフィット型", count: 29, percentage: 22.8 },
    { name: "ストーリー型", count: 15, percentage: 11.8 },
  ],
  cta_types: [
    { name: "限定オファー", count: 52, percentage: 40.9 },
    { name: "無料お試し", count: 38, percentage: 29.9 },
    { name: "保証付き", count: 22, percentage: 17.3 },
    { name: "緊急性", count: 15, percentage: 11.8 },
  ],
  offer_types: [
    { name: "割引", count: 55, percentage: 43.3 },
    { name: "無料トライアル", count: 35, percentage: 27.6 },
    { name: "限定品", count: 22, percentage: 17.3 },
    { name: "セット", count: 15, percentage: 11.8 },
  ],
  representative_ads: [
    { ad_id: 1, title: "【驚愕】美容液の実力がヤバい", advertiser_name: "Beauty Corp", hit_score: 95, thumbnail: "", platform: "instagram" },
    { ad_id: 2, title: "1ヶ月で-5kg達成の秘密", advertiser_name: "Health Co", hit_score: 92, thumbnail: "", platform: "facebook" },
    { ad_id: 3, title: "プロが認めた最強サプリ", advertiser_name: "Supplement Inc", hit_score: 88, thumbnail: "", platform: "tiktok" },
    { ad_id: 4, title: "今だけ80%OFF 話題の商品", advertiser_name: "EC Store", hit_score: 85, thumbnail: "", platform: "facebook" },
    { ad_id: 5, title: "知らないと損する美容法", advertiser_name: "Skin Care Ltd", hit_score: 83, thumbnail: "", platform: "instagram" },
  ],
};

const MOCK_FAILURE: AnalysisGroup = {
  ad_count: 264,
  percentage: 67.5,
  avg_views: 15000,
  avg_spend: 85000,
  avg_likes: 120,
  avg_score: 28,
  hook_types: [
    { name: "ベネフィット型", count: 95, percentage: 36.0 },
    { name: "質問型", count: 72, percentage: 27.3 },
    { name: "ストーリー型", count: 55, percentage: 20.8 },
    { name: "衝撃型", count: 42, percentage: 15.9 },
  ],
  cta_types: [
    { name: "緊急性", count: 90, percentage: 34.1 },
    { name: "限定オファー", count: 75, percentage: 28.4 },
    { name: "無料お試し", count: 58, percentage: 22.0 },
    { name: "保証付き", count: 41, percentage: 15.5 },
  ],
  offer_types: [
    { name: "割引", count: 100, percentage: 37.9 },
    { name: "セット", count: 80, percentage: 30.3 },
    { name: "無料トライアル", count: 50, percentage: 18.9 },
    { name: "限定品", count: 34, percentage: 12.9 },
  ],
  representative_ads: [
    { ad_id: 101, title: "商品紹介動画", advertiser_name: "Unknown Corp", hit_score: 15, thumbnail: "", platform: "facebook" },
    { ad_id: 102, title: "新商品のご案内", advertiser_name: "Small Biz", hit_score: 20, thumbnail: "", platform: "instagram" },
    { ad_id: 103, title: "お得なセール開催中", advertiser_name: "Retail Shop", hit_score: 22, thumbnail: "", platform: "facebook" },
    { ad_id: 104, title: "当社サービスについて", advertiser_name: "Service Co", hit_score: 25, thumbnail: "", platform: "tiktok" },
    { ad_id: 105, title: "キャンペーン実施中", advertiser_name: "Campaign Inc", hit_score: 28, thumbnail: "", platform: "instagram" },
  ],
};

const MOCK_REUSE_POINTS = [
  "フックには「質問型」を採用し、視聴者の悩みに直接訴えかける",
  "CTAには「限定オファー」を必ず組み込み、行動を促す",
  "具体的な数字（%、日数、金額）を盛り込んで信頼性を高める",
  "成功広告の93%が最初の3秒で視聴者の注意を引くフックを使用",
  "失敗広告は「緊急性CTA」に偏りすぎている傾向がある",
];

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

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // TODO: Replace with actual API call when endpoint is ready
      // const data = await fetchApi<{ success: AnalysisGroup; failure: AnalysisGroup }>("/rankings/hit-ads", {
      //   params: { genre: genre || undefined },
      // });
      await new Promise((r) => setTimeout(r, 700));
      setSuccess(MOCK_SUCCESS);
      setFailure(MOCK_FAILURE);
    } catch (err) {
      console.error("分析データの取得に失敗しました", err);
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
            {MOCK_REUSE_POINTS.map((point, idx) => (
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
