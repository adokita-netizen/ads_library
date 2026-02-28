"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { platformLabels, platformColors, genreOptions } from "@/lib/constants";
import { formatYen, formatNumber } from "@/lib/format";

type TrendPeriod = "daily" | "weekly" | "monthly";
type TrendCategory = "all" | "ec_d2c" | "app" | "finance" | "education" | "beauty" | "food" | "gaming" | "health" | "technology" | "real_estate" | "travel" | "other";

interface TrendItem {
  rank: number;
  productName: string;
  platform: string;
  genre: string;
  change: number; // positive = up, negative = down
  spendEstimate: number;
  playCount: number;
  trendScore: number;
}

interface EarlyHitItem {
  ad_id: number;
  title?: string;
  advertiser_name?: string;
  platform?: string;
  genre?: string;
  momentum_score: number;
  hit_probability: number;
  growth_phase: string;
  days_active?: number;
  predicted_peak_spend?: number;
  velocity?: {
    view_1d: number;
    view_7d: number;
    spend_1d: number;
    spend_7d: number;
  };
}

const categoryOptions = genreOptions as { value: TrendCategory; label: string }[];

const growthPhaseLabel: Record<string, { label: string; color: string }> = {
  launch: { label: "ローンチ", color: "bg-blue-100 text-blue-700" },
  growth: { label: "成長中", color: "bg-emerald-100 text-emerald-700" },
  peak: { label: "ピーク", color: "bg-red-100 text-red-700" },
  plateau: { label: "横ばい", color: "bg-amber-100 text-amber-700" },
  decline: { label: "減少", color: "bg-gray-100 text-gray-500" },
};

export default function TrendView() {
  const [period, setPeriod] = useState<TrendPeriod>("daily");
  const [category, setCategory] = useState<TrendCategory>("all");
  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [earlyHits, setEarlyHits] = useState<EarlyHitItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTrends = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (period) params.period = period;
      if (category !== "all") params.genre = category;

      const [rankData, earlyData] = await Promise.allSettled([
        fetchApi<{ items?: Record<string, unknown>[]; rankings?: Record<string, unknown>[]; results?: Record<string, unknown>[] }>("/rankings/products", { params }),
        fetchApi<{ items?: EarlyHitItem[]; candidates?: EarlyHitItem[] }>("/competitive/trends/early-hits", { params: { max_days_active: "14", min_momentum: "30" } }),
      ]);

      if (rankData.status === "fulfilled") {
        const data = rankData.value;
        const items = data?.items || data?.rankings || data?.results;
        if (Array.isArray(items) && items.length > 0) {
          const mapped: TrendItem[] = items.map((item: Record<string, unknown>, idx: number) => ({
            rank: (item.rank as number) || idx + 1,
            productName: (item.product_name as string) || "不明",
            platform: ((item.platform as string) || "").toLowerCase() || "youtube",
            genre: (item.genre as string) || "",
            change: (item.rank_change as number) || 0,
            spendEstimate: (item.spend_increase as number) || 0,
            playCount: (item.view_increase as number) || 0,
            trendScore: (item.trend_score as number) || 0,
          }));
          setTrends(mapped);
        } else {
          setTrends([]);
        }
      }

      if (earlyData.status === "fulfilled") {
        const data = earlyData.value;
        const items = data?.items || data?.candidates || [];
        setEarlyHits(Array.isArray(items) ? items.slice(0, 6) : []);
      }
    } catch (err) {
      console.error("Failed to fetch trends:", err);
      setError("データ取得に失敗しました。バックエンドが起動中の可能性があります。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrends();
  }, [period, category]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">トレンド</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">広告市場のトレンド動向をリアルタイムで把握</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="select-filter text-xs"
            value={category}
            onChange={(e) => setCategory(e.target.value as TrendCategory)}
          >
            {categoryOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <div className="flex rounded-md border border-gray-300 overflow-hidden">
            {(["daily", "weekly", "monthly"] as TrendPeriod[]).map((p) => (
              <button
                key={p}
                className={`px-3 py-1.5 text-[11px] font-medium transition-colors ${
                  period === p
                    ? "bg-[#4A7DFF] text-white"
                    : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
                onClick={() => setPeriod(p)}
              >
                {p === "daily" ? "日次" : p === "weekly" ? "週次" : "月次"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-3 px-5 py-3 bg-[#f8f9fc]">
        <div className="card py-3">
          <p className="text-[10px] text-gray-400 font-medium">急上昇商材</p>
          <p className="text-xl font-bold text-gray-900 mt-1">
            {trends.filter((t) => t.change > 0).length}
          </p>
        </div>
        <div className="card py-3">
          <p className="text-[10px] text-gray-400 font-medium">トラッキング中</p>
          <p className="text-xl font-bold text-gray-900 mt-1">{trends.length}</p>
        </div>
        <div className="card py-3">
          <p className="text-[10px] text-gray-400 font-medium">市場推定消化額</p>
          <p className="text-xl font-bold text-gray-900 mt-1">
            {formatYen(trends.reduce((sum, t) => sum + t.spendEstimate, 0))}
          </p>
        </div>
        <div className="card py-3">
          <p className="text-[10px] text-gray-400 font-medium">トレンドスコア平均</p>
          <p className="text-xl font-bold text-gray-900 mt-1">
            {trends.length > 0
              ? (trends.reduce((sum, t) => sum + t.trendScore, 0) / trends.length).toFixed(1)
              : "-"}
          </p>
        </div>
      </div>

      {/* Emerging Trend Radar */}
      {earlyHits.length > 0 && (
        <div className="px-5 py-3 bg-[#f8f9fc] border-b border-gray-200">
          <div className="flex items-center gap-2 mb-3">
            <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
            </svg>
            <h3 className="text-[13px] font-bold text-gray-900">注目の急上昇広告</h3>
            <span className="text-[10px] text-gray-400">直近14日以内に急成長している広告を自動検出</span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {earlyHits.map((hit) => {
              const phase = growthPhaseLabel[hit.growth_phase] || growthPhaseLabel.launch;
              return (
                <div key={hit.ad_id} className="card px-4 py-3 hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-semibold text-gray-900 truncate" title={hit.title || ""}>
                        {hit.title || "不明な広告"}
                      </p>
                      <p className="text-[10px] text-gray-400 truncate">{hit.advertiser_name || "-"}</p>
                    </div>
                    <span className={`badge text-[9px] shrink-0 ml-2 ${phase.color}`}>{phase.label}</span>
                  </div>

                  {/* Momentum meter */}
                  <div className="mb-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] text-gray-400">モメンタム</span>
                      <span className={`text-[11px] font-bold ${
                        hit.momentum_score >= 80 ? "text-emerald-600" : hit.momentum_score >= 60 ? "text-[#4A7DFF]" : "text-amber-500"
                      }`}>{Math.round(hit.momentum_score)}</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          hit.momentum_score >= 80 ? "bg-emerald-500" : hit.momentum_score >= 60 ? "bg-[#4A7DFF]" : "bg-amber-400"
                        }`}
                        style={{ width: `${Math.min(hit.momentum_score, 100)}%` }}
                      />
                    </div>
                  </div>

                  {/* Stats row */}
                  <div className="flex items-center justify-between text-[10px]">
                    <div className="flex items-center gap-2">
                      {hit.platform && (
                        <span className={`platform-icon ${platformColors[hit.platform] || ""} text-[8px]`}>
                          {platformLabels[hit.platform] || hit.platform}
                        </span>
                      )}
                      {hit.days_active != null && (
                        <span className="text-gray-400">{hit.days_active}日目</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-gray-400">HIT確率</span>
                      <span className={`font-bold ${hit.hit_probability >= 70 ? "text-red-500" : hit.hit_probability >= 40 ? "text-amber-500" : "text-gray-500"}`}>
                        {Math.round(hit.hit_probability)}%
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="mx-5 mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3 flex items-center justify-between">
          <span className="text-sm text-amber-800">{error}</span>
          <button onClick={fetchTrends} className="text-sm font-medium text-amber-900 underline ml-3">再試行</button>
        </div>
      )}

      {/* Trend Table */}
      <div className="flex-1 overflow-auto custom-scrollbar px-5 py-3">
        <table className="data-table">
          <thead>
            <tr>
              <th className="w-12 text-center">順位</th>
              <th>商材名</th>
              <th>媒体</th>
              <th>ジャンル</th>
              <th className="text-center">変動</th>
              <th className="text-right">推定消化額</th>
              <th className="text-right">再生数</th>
              <th className="text-right">トレンドスコア</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={8} className="text-center py-8">
                  <div className="inline-flex items-center gap-2">
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
                    <span className="text-xs text-gray-400">読み込み中...</span>
                  </div>
                </td>
              </tr>
            )}
            {!loading && trends.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center py-12">
                  <p className="text-xs text-gray-400">トレンドデータがありません</p>
                </td>
              </tr>
            )}
            {trends.map((item) => (
              <tr key={item.rank}>
                <td className="text-center">
                  <span className={`inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold ${
                    item.rank <= 3 ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-500"
                  }`}>
                    {item.rank}
                  </span>
                </td>
                <td>
                  <span className="text-[13px] font-medium text-gray-900">{item.productName}</span>
                </td>
                <td>
                  <span className={`platform-icon ${platformColors[item.platform]}`}>
                    {platformLabels[item.platform]}
                  </span>
                </td>
                <td>
                  <span className="badge-blue text-[10px]">{item.genre}</span>
                </td>
                <td className="text-center">
                  {item.change > 0 ? (
                    <span className="text-emerald-600 text-xs font-semibold">↑{item.change}</span>
                  ) : item.change < 0 ? (
                    <span className="text-red-500 text-xs font-semibold">↓{Math.abs(item.change)}</span>
                  ) : (
                    <span className="text-gray-400 text-xs">→</span>
                  )}
                </td>
                <td className="text-right">
                  <span className="text-[13px] font-semibold text-gray-900">{formatYen(item.spendEstimate)}</span>
                </td>
                <td className="text-right">
                  <span className="text-[12px] text-gray-600">{formatNumber(item.playCount)}</span>
                </td>
                <td className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          item.trendScore >= 80 ? "bg-[#4A7DFF]" : item.trendScore >= 60 ? "bg-amber-400" : "bg-gray-300"
                        }`}
                        style={{ width: `${item.trendScore}%` }}
                      />
                    </div>
                    <span className="text-[12px] font-semibold text-gray-700 w-8 text-right">{item.trendScore}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
