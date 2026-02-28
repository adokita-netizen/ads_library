"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { formatNumber, formatYen } from "@/lib/format";

/* ─── Types ─── */

interface GenreDistribution {
  genre: string;
  count: number;
  percentage: number;
}

interface MonthlyTrend {
  month: string;
  ad_count: number;
  total_spend: number;
  avg_score: number;
}

interface TopAd {
  ad_id: number;
  product_name: string;
  platform: string;
  hit_score: number;
  cumulative_views: number;
  cumulative_spend: number;
  thumbnail?: string;
  image_url?: string;
}

interface AdvertiserProfileData {
  advertiser_name: string;
  total_ads: number;
  hit_rate: number;
  total_spend: number;
  avg_score: number;
  genre_distribution: GenreDistribution[];
  monthly_trends: MonthlyTrend[];
  preferred_hooks: string[];
  preferred_ctas: string[];
  avg_duration_days: number;
  top_ads: TopAd[];
}

/* ─── Mock Data ─── */

// TODO: API実装後に削除
function getMockProfile(name: string): AdvertiserProfileData {
  return {
    advertiser_name: name,
    total_ads: 87,
    hit_rate: 23.0,
    total_spend: 145000000,
    avg_score: 62.5,
    genre_distribution: [
      { genre: "美容", count: 35, percentage: 40.2 },
      { genre: "健康食品", count: 22, percentage: 25.3 },
      { genre: "ダイエット", count: 18, percentage: 20.7 },
      { genre: "スキンケア", count: 12, percentage: 13.8 },
    ],
    monthly_trends: [
      { month: "2025-09", ad_count: 8, total_spend: 12000000, avg_score: 55 },
      { month: "2025-10", ad_count: 12, total_spend: 18000000, avg_score: 58 },
      { month: "2025-11", ad_count: 15, total_spend: 22000000, avg_score: 61 },
      { month: "2025-12", ad_count: 11, total_spend: 19000000, avg_score: 64 },
      { month: "2026-01", ad_count: 18, total_spend: 35000000, avg_score: 67 },
      { month: "2026-02", ad_count: 23, total_spend: 39000000, avg_score: 65 },
    ],
    preferred_hooks: ["問題提起", "権威性", "体験談"],
    preferred_ctas: ["LP誘導", "LINE登録", "無料サンプル"],
    avg_duration_days: 34,
    top_ads: [
      { ad_id: 101, product_name: "美容液プレミアムケア", platform: "instagram", hit_score: 89, cumulative_views: 450000, cumulative_spend: 12000000 },
      { ad_id: 102, product_name: "ダイエットサプリX", platform: "facebook", hit_score: 82, cumulative_views: 380000, cumulative_spend: 9500000 },
      { ad_id: 103, product_name: "育毛トニック", platform: "youtube", hit_score: 76, cumulative_views: 290000, cumulative_spend: 7800000 },
      { ad_id: 104, product_name: "脱毛サロンLP", platform: "tiktok", hit_score: 71, cumulative_views: 210000, cumulative_spend: 5400000 },
      { ad_id: 105, product_name: "プロテインバー", platform: "line", hit_score: 65, cumulative_views: 150000, cumulative_spend: 3200000 },
    ],
  };
}

/* ─── Score color ─── */

function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-600";
  if (score >= 40) return "text-amber-500";
  return "text-red-500";
}

function scoreBg(score: number): string {
  if (score >= 70) return "bg-emerald-100";
  if (score >= 40) return "bg-amber-100";
  return "bg-red-100";
}

/* ─── Genre color ─── */

const genreColors = ["#4A7DFF", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6", "#EC4899", "#06B6D4"];

/* ─── Main Component ─── */

interface AdvertiserProfileProps {
  advertiserName: string;
  onAdSelect?: (adId: number) => void;
  onBack?: () => void;
}

export default function AdvertiserProfile({ advertiserName, onAdSelect, onBack }: AdvertiserProfileProps) {
  const [data, setData] = useState<AdvertiserProfileData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchApi<AdvertiserProfileData>(
        `/rankings/advertiser/${encodeURIComponent(advertiserName)}/profile`
      );
      setData(res);
    } catch {
      // TODO: API未実装時はモックデータを使用
      setData(getMockProfile(advertiserName));
    } finally {
      setLoading(false);
    }
  }, [advertiserName]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  if (loading) {
    return (
      <div className="flex flex-col h-full bg-[#f8f9fb]">
        <div className="p-5 animate-pulse space-y-4">
          <div className="h-8 w-48 bg-gray-200 rounded" />
          <div className="grid grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-20 bg-gray-200 rounded-xl" />
            ))}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="h-48 bg-gray-200 rounded-xl" />
            <div className="h-48 bg-gray-200 rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  // Find max monthly ad count for bar chart scaling
  const maxMonthlyCount = Math.max(...data.monthly_trends.map((t) => t.ad_count), 1);

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#f8f9fb]">
      {/* Header */}
      <div className="shrink-0 bg-white border-b border-gray-200 px-5 py-3">
        <div className="flex items-center gap-3">
          {onBack && (
            <button
              onClick={onBack}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
              </svg>
            </button>
          )}
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-[16px] font-bold text-gray-900">{data.advertiser_name}</h1>
              <span className="text-[11px] text-gray-400">広告主プロフィール</span>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto custom-scrollbar p-5 space-y-5">
        {/* KPI row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 px-4 py-3">
            <p className="text-[10px] text-gray-500 font-medium mb-1">総広告数</p>
            <p className="text-[20px] font-bold text-[#4A7DFF]">{data.total_ads}<span className="text-[11px] text-gray-400 ml-1">件</span></p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 px-4 py-3">
            <p className="text-[10px] text-gray-500 font-medium mb-1">ヒット率</p>
            <p className="text-[20px] font-bold text-orange-500">{data.hit_rate.toFixed(1)}<span className="text-[11px] text-gray-400 ml-1">%</span></p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 px-4 py-3">
            <p className="text-[10px] text-gray-500 font-medium mb-1">推定総消化額</p>
            <p className="text-[20px] font-bold text-teal-600">{formatYen(data.total_spend)}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 px-4 py-3">
            <p className="text-[10px] text-gray-500 font-medium mb-1">平均スコア</p>
            <p className={`text-[20px] font-bold ${scoreColor(data.avg_score)}`}>{data.avg_score.toFixed(1)}<span className="text-[11px] text-gray-400 ml-1">pt</span></p>
          </div>
        </div>

        {/* Genre distribution + Monthly timeline */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Genre distribution */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
              <h3 className="text-[13px] font-bold text-gray-700">ジャンル分布</h3>
            </div>
            <div className="p-4 space-y-3">
              {data.genre_distribution.map((g, idx) => (
                <div key={g.genre} className="flex items-center gap-3">
                  <span className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: genreColors[idx % genreColors.length] }} />
                  <span className="text-[12px] text-gray-700 w-24 truncate">{g.genre}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2">
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{
                        width: `${g.percentage}%`,
                        backgroundColor: genreColors[idx % genreColors.length],
                      }}
                    />
                  </div>
                  <span className="text-[11px] text-gray-500 w-12 text-right">{g.count}件</span>
                  <span className="text-[10px] text-gray-400 w-10 text-right">{g.percentage.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>

          {/* Monthly timeline (CSS bar chart) */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
              <h3 className="text-[13px] font-bold text-gray-700">月別推移</h3>
            </div>
            <div className="p-4">
              <div className="flex items-end gap-2 h-36">
                {data.monthly_trends.map((t) => (
                  <div key={t.month} className="flex-1 flex flex-col items-center gap-1">
                    <span className="text-[9px] text-gray-500 font-medium">{t.ad_count}</span>
                    <div className="w-full bg-gray-50 rounded-t flex flex-col justify-end" style={{ height: "100%" }}>
                      <div
                        className="w-full bg-[#4A7DFF] rounded-t transition-all"
                        style={{ height: `${(t.ad_count / maxMonthlyCount) * 100}%`, minHeight: "4px" }}
                      />
                    </div>
                    <span className="text-[9px] text-gray-400">
                      {t.month.slice(5)}月
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Creative style */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
            <h3 className="text-[13px] font-bold text-gray-700">クリエイティブスタイル</h3>
          </div>
          <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-[10px] text-gray-500 font-medium mb-2">好みのフック</p>
              <div className="flex flex-wrap gap-1.5">
                {data.preferred_hooks.map((h) => (
                  <span key={h} className="px-2 py-1 rounded-lg bg-blue-50 text-blue-700 text-[11px] font-medium">
                    {h}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[10px] text-gray-500 font-medium mb-2">好みのCTA</p>
              <div className="flex flex-wrap gap-1.5">
                {data.preferred_ctas.map((c) => (
                  <span key={c} className="px-2 py-1 rounded-lg bg-green-50 text-green-700 text-[11px] font-medium">
                    {c}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[10px] text-gray-500 font-medium mb-2">平均掲載日数</p>
              <p className="text-[20px] font-bold text-gray-800">
                {data.avg_duration_days}<span className="text-[11px] text-gray-400 ml-1">日</span>
              </p>
            </div>
          </div>
        </div>

        {/* Top ads */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
            <h3 className="text-[13px] font-bold text-gray-700">トップ広告</h3>
          </div>
          <div className="divide-y divide-gray-50">
            {data.top_ads.map((ad, idx) => (
              <button
                key={ad.ad_id}
                onClick={() => onAdSelect?.(ad.ad_id)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors text-left"
              >
                <span className="text-[12px] font-bold text-gray-300 w-6 text-center shrink-0">
                  {idx + 1}
                </span>
                <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center shrink-0">
                  {ad.thumbnail || ad.image_url ? (
                    <img src={ad.thumbnail || ad.image_url} alt="" className="w-full h-full object-cover rounded-lg" />
                  ) : (
                    <svg className="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5a2.25 2.25 0 002.25-2.25V5.25a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 003.75 21z" />
                    </svg>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] font-medium text-gray-800 truncate">{ad.product_name}</p>
                  <p className="text-[10px] text-gray-400">{ad.platform}</p>
                </div>
                <div className="text-right shrink-0">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${scoreBg(ad.hit_score)} ${scoreColor(ad.hit_score)}`}>
                    {ad.hit_score}pt
                  </span>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[11px] text-gray-600">{formatNumber(ad.cumulative_views)}回</p>
                  <p className="text-[10px] text-gray-400">{formatYen(ad.cumulative_spend)}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
