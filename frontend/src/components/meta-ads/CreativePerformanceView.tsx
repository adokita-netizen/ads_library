"use client";

import { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import type { CreativePerformanceData, CreativePerformanceAd, CreativeTypeSummary } from "@/types";
import { metaMarketingApi } from "@/lib/api";

interface Props {
  accountId: string;
}

type SortField = "spend" | "ctr" | "cpc" | "cpa" | "impressions" | "conversions" | "roas";

export default function CreativePerformanceView({ accountId }: Props) {
  const [data, setData] = useState<CreativePerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);
  const [sortBy, setSortBy] = useState<SortField>("spend");
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await metaMarketingApi.getCreativePerformance(accountId, { days, sort_by: sortBy });
      if (res.data) setData(res.data);
    } catch {
      toast.error("クリエイティブデータの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [accountId, days, sortBy]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return <div className="text-center py-8 text-[12px] text-gray-400">クリエイティブデータを読み込み中...</div>;
  }

  if (!data || data.ads.length === 0) {
    return (
      <div className="text-center py-12 text-[13px] text-gray-400">
        クリエイティブパフォーマンスデータがありません。広告データを同期してください。
      </div>
    );
  }

  const typeSummaryEntries = Object.entries(data.type_summary) as [string, CreativeTypeSummary][];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-[14px] font-bold text-gray-800">
          クリエイティブ×パフォーマンス ({data.ads.length}件)
        </h3>
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
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortField)}
            className="text-[11px] border border-gray-200 rounded-lg px-2 py-1"
            aria-label="ソート順"
          >
            <option value="spend">消化額</option>
            <option value="ctr">CTR</option>
            <option value="cpc">CPC</option>
            <option value="cpa">CPA</option>
            <option value="roas">ROAS</option>
            <option value="impressions">IMP</option>
            <option value="conversions">CV</option>
          </select>
          <div className="flex border border-gray-200 rounded-lg overflow-hidden">
            <button
              onClick={() => setViewMode("cards")}
              className={`px-2 py-1 text-[10px] ${viewMode === "cards" ? "bg-[#4A7DFF] text-white" : "bg-white text-gray-600"}`}
            >
              カード
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`px-2 py-1 text-[10px] ${viewMode === "table" ? "bg-[#4A7DFF] text-white" : "bg-white text-gray-600"}`}
            >
              テーブル
            </button>
          </div>
        </div>
      </div>

      {/* Creative Type Summary */}
      {typeSummaryEntries.length > 1 && (
        <div className="card p-4">
          <h4 className="text-[12px] font-bold text-gray-700 mb-2">クリエイティブタイプ別比較</h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {typeSummaryEntries.map(([type, ts]) => (
              <div key={type} className="bg-gray-50 rounded-lg p-2.5">
                <p className="text-[11px] font-medium text-gray-700 mb-1 capitalize">{type}</p>
                <div className="space-y-0.5">
                  <div className="flex justify-between text-[10px]">
                    <span className="text-gray-500">件数</span>
                    <span className="font-medium">{ts.count}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-gray-500">Avg CTR</span>
                    <span className="font-medium">{ts.avg_ctr}%</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-gray-500">Avg CPC</span>
                    <span className="font-medium">¥{Math.round(ts.avg_cpc).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-[10px]">
                    <span className="text-gray-500">消化額</span>
                    <span className="font-medium">¥{Math.round(ts.spend).toLocaleString()}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ad List */}
      {viewMode === "cards" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {data.ads.map((ad) => (
            <CreativeCard key={ad.meta_id} ad={ad} />
          ))}
        </div>
      ) : (
        <CreativeTable ads={data.ads} />
      )}
    </div>
  );
}

// ── Creative Card ──────────────────────────────────────────────

function CreativeCard({ ad }: { ad: CreativePerformanceAd }) {
  const isFatigued = ad.ctr < 0.5 && ad.impressions > 5000;

  return (
    <div className={`card p-3 ${isFatigued ? "border-red-200" : ""}`}>
      <div className="flex gap-3">
        {/* Thumbnail */}
        <div className="w-16 h-16 bg-gray-100 rounded-lg overflow-hidden shrink-0">
          {(ad.creative_thumbnail_url || ad.creative_image_url) ? (
            <img
              src={ad.creative_thumbnail_url || ad.creative_image_url || ""}
              alt={ad.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-[10px] text-gray-400">
              {ad.creative_type === "VIDEO" ? "Video" : "Img"}
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1">
            <p className="text-[12px] font-medium text-gray-800 truncate">{ad.name}</p>
            <span className="text-[9px] px-1 py-0.5 bg-gray-100 text-gray-500 rounded shrink-0">
              {ad.creative_type}
            </span>
            {isFatigued && (
              <span className="text-[9px] px-1 py-0.5 bg-red-50 text-red-600 rounded shrink-0">
                疲労
              </span>
            )}
          </div>
          {ad.creative_title && (
            <p className="text-[10px] text-gray-500 truncate mb-1">{ad.creative_title}</p>
          )}

          {/* Metrics grid */}
          <div className="grid grid-cols-4 gap-1">
            <MetricCell label="IMP" value={ad.impressions.toLocaleString()} />
            <MetricCell label="CTR" value={`${ad.ctr}%`} highlight={ad.ctr > 2 ? "positive" : ad.ctr < 0.5 ? "negative" : undefined} />
            <MetricCell label="CPC" value={`¥${Math.round(ad.cpc).toLocaleString()}`} />
            <MetricCell label="消化" value={`¥${Math.round(ad.spend).toLocaleString()}`} />
          </div>
          <div className="grid grid-cols-4 gap-1 mt-0.5">
            <MetricCell label="CV" value={String(ad.conversions)} />
            <MetricCell label="CPA" value={ad.cpa > 0 ? `¥${Math.round(ad.cpa).toLocaleString()}` : "-"} />
            <MetricCell label="ROAS" value={ad.roas > 0 ? `${ad.roas}x` : "-"} highlight={ad.roas > 3 ? "positive" : undefined} />
            {ad.video_completion_rate !== null && ad.video_completion_rate !== undefined ? (
              <MetricCell label="完了率" value={`${ad.video_completion_rate}%`} />
            ) : (
              <MetricCell label="CPM" value={`¥${Math.round(ad.cpm).toLocaleString()}`} />
            )}
          </div>
        </div>
      </div>

      {/* Video retention bar */}
      {ad.video_retention && (
        <div className="mt-2 pt-2 border-t border-gray-100">
          <p className="text-[9px] text-gray-500 mb-1">動画視聴維持率</p>
          <div className="flex items-center gap-1">
            {(["p25", "p50", "p75", "p100"] as const).map((key) => {
              const total = ad.video_retention![key];
              const pct = ad.impressions > 0 ? Math.round((total / ad.impressions) * 100) : 0;
              return (
                <div key={key} className="flex-1 text-center">
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div
                      className="bg-[#4A7DFF] h-1.5 rounded-full"
                      style={{ width: `${Math.min(pct, 100)}%` }}
                    />
                  </div>
                  <span className="text-[8px] text-gray-400">{key.replace("p", "")}%: {pct}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Metric Cell ────────────────────────────────────────────────

function MetricCell({ label, value, highlight }: { label: string; value: string; highlight?: "positive" | "negative" }) {
  return (
    <div className="text-center">
      <p className="text-[8px] text-gray-400">{label}</p>
      <p className={`text-[10px] font-medium ${highlight === "positive" ? "text-green-600" : highlight === "negative" ? "text-red-600" : "text-gray-700"}`}>
        {value}
      </p>
    </div>
  );
}

// ── Creative Table ─────────────────────────────────────────────

function CreativeTable({ ads }: { ads: CreativePerformanceAd[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[11px]" aria-label="クリエイティブパフォーマンス">
        <thead>
          <tr className="border-b border-gray-200">
            <th scope="col" className="text-left py-2 px-2 text-gray-500 font-medium">広告名</th>
            <th scope="col" className="text-left py-2 px-1 text-gray-500 font-medium">タイプ</th>
            <th scope="col" className="text-right py-2 px-1 text-gray-500 font-medium">IMP</th>
            <th scope="col" className="text-right py-2 px-1 text-gray-500 font-medium">CTR</th>
            <th scope="col" className="text-right py-2 px-1 text-gray-500 font-medium">CPC</th>
            <th scope="col" className="text-right py-2 px-1 text-gray-500 font-medium">消化額</th>
            <th scope="col" className="text-right py-2 px-1 text-gray-500 font-medium">CV</th>
            <th scope="col" className="text-right py-2 px-1 text-gray-500 font-medium">CPA</th>
            <th scope="col" className="text-right py-2 px-1 text-gray-500 font-medium">ROAS</th>
          </tr>
        </thead>
        <tbody>
          {ads.map((ad) => (
            <tr key={ad.meta_id} className="border-b border-gray-50 hover:bg-gray-50">
              <td className="py-1.5 px-2 truncate max-w-[200px]">{ad.name}</td>
              <td className="py-1.5 px-1">
                <span className="text-[9px] px-1 py-0.5 bg-gray-100 text-gray-500 rounded">{ad.creative_type}</span>
              </td>
              <td className="py-1.5 px-1 text-right">{ad.impressions.toLocaleString()}</td>
              <td className={`py-1.5 px-1 text-right ${ad.ctr > 2 ? "text-green-600 font-medium" : ad.ctr < 0.5 ? "text-red-600" : ""}`}>
                {ad.ctr}%
              </td>
              <td className="py-1.5 px-1 text-right">¥{Math.round(ad.cpc).toLocaleString()}</td>
              <td className="py-1.5 px-1 text-right">¥{Math.round(ad.spend).toLocaleString()}</td>
              <td className="py-1.5 px-1 text-right">{ad.conversions}</td>
              <td className="py-1.5 px-1 text-right">{ad.cpa > 0 ? `¥${Math.round(ad.cpa).toLocaleString()}` : "-"}</td>
              <td className={`py-1.5 px-1 text-right ${ad.roas > 3 ? "text-green-600 font-medium" : ""}`}>
                {ad.roas > 0 ? `${ad.roas}x` : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
