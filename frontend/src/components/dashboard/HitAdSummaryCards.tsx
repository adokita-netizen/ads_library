"use client";

import { formatYen } from "@/lib/format";
import { genreOptions } from "@/lib/constants";

interface HitAdSummaryCardsProps {
  megaHitCount: number;
  hitCount: number;
  totalHits: number;
  totalAdsCount: number;
  activeAdsCount: number | null;
  avgHitScore: number;
  topGenreLabel: string;
  topGenreDetail: string;
  topCreativeType: string | null;
  totalSpend: number;
  genreCount: number;
  avgDaysRunning: number;
  stillRunningCount: number;
  realDataPct: number;
  realDataCount: number;
  estimatedCount: number;
}

export function genreLabel(value: string | null | undefined): string {
  if (!value || value === "未分類") return "未分類";
  return genreOptions.find((g) => g.value === value)?.label || value;
}

export default function HitAdSummaryCards({
  megaHitCount,
  hitCount,
  totalHits,
  totalAdsCount,
  activeAdsCount,
  avgHitScore,
  topGenreLabel,
  topGenreDetail,
  topCreativeType,
  totalSpend,
  genreCount,
  avgDaysRunning,
  stillRunningCount,
  realDataPct,
  realDataCount,
  estimatedCount,
}: HitAdSummaryCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <div className="card px-4 py-3">
        <p className="text-[11px] text-gray-400 font-medium">ヒット広告数</p>
        <p className="text-[22px] font-bold text-gray-900 mt-0.5">{totalHits}<span className="text-[13px] text-gray-400 ml-1">件</span></p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          {megaHitCount > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-medium">大HIT {megaHitCount}</span>
          )}
          {hitCount > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 font-medium">HIT {hitCount}</span>
          )}
          <span className="text-[10px] text-gray-400">/ 全{totalAdsCount}件</span>
          {activeAdsCount != null && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-medium">アクティブ {activeAdsCount}</span>
          )}
        </div>
      </div>
      <div className="card px-4 py-3">
        <p className="text-[11px] text-gray-400 font-medium">平均ヒットスコア</p>
        <p className="text-[22px] font-bold text-[#4A7DFF] mt-0.5">{avgHitScore}<span className="text-[13px] text-gray-400 ml-1">/ 100</span></p>
        <div className="mt-1.5 h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div className="h-full rounded-full bg-[#4A7DFF]" style={{ width: `${avgHitScore}%` }} />
        </div>
      </div>
      <div className="card px-4 py-3">
        <p className="text-[11px] text-gray-400 font-medium">トップジャンル</p>
        <p className="text-[15px] font-bold text-gray-900 mt-0.5 truncate">{topGenreLabel}</p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <p className="text-[10px] text-gray-400">{topGenreDetail}</p>
          {topCreativeType && (
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 font-medium">
              {topCreativeType === "video" ? "動画" : topCreativeType === "image" ? "静止画" : topCreativeType}
            </span>
          )}
        </div>
      </div>
      <div className="card px-4 py-3">
        <p className="text-[11px] text-gray-400 font-medium">市場推定消化額</p>
        <p className="text-[22px] font-bold text-gray-900 mt-0.5">{formatYen(totalSpend)}</p>
        <p className="text-[10px] text-gray-400 mt-1">{genreCount}ジャンル合計 (週間)</p>
      </div>
      <div className="card px-4 py-3">
        <p className="text-[11px] text-gray-400 font-medium">平均配信日数</p>
        <p className="text-[22px] font-bold text-gray-900 mt-0.5">
          {avgDaysRunning > 0 ? avgDaysRunning : "-"}
          {avgDaysRunning > 0 && <span className="text-[13px] text-gray-400 ml-1">日</span>}
        </p>
        <p className="text-[10px] text-gray-400 mt-1">
          {stillRunningCount > 0 ? (
            <><span className="text-emerald-600 font-medium">● {stillRunningCount}件</span> 配信中</>
          ) : "配信中なし"}
        </p>
      </div>
      <div className="card px-4 py-3">
        <p className="text-[11px] text-gray-400 font-medium">データ信頼度</p>
        <p className="text-[22px] font-bold mt-0.5" style={{ color: realDataPct >= 50 ? "#10b981" : "#f59e0b" }}>
          {realDataPct}<span className="text-[13px] text-gray-400 ml-1">%</span>
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-green-100 text-green-700">実データ {realDataCount}</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">推定 {estimatedCount}</span>
        </div>
      </div>
    </div>
  );
}
