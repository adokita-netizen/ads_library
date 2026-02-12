"use client";

import { useState, useEffect } from "react";
import { analyticsApi } from "@/lib/api";

type TrendPeriod = "daily" | "weekly" | "monthly";
type TrendCategory = "all" | "beauty" | "health" | "diet" | "haircare" | "oral";

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

const mockTrends: TrendItem[] = [
  { rank: 1, productName: "スキンケアセラムV3", platform: "youtube", genre: "美容・コスメ", change: 2, spendEstimate: 8500000, playCount: 1250000, trendScore: 98 },
  { rank: 2, productName: "ダイエットサプリメントX", platform: "tiktok", genre: "健康食品", change: 5, spendEstimate: 6200000, playCount: 980000, trendScore: 94 },
  { rank: 3, productName: "育毛トニックPRO", platform: "facebook", genre: "ヘアケア", change: -1, spendEstimate: 5100000, playCount: 720000, trendScore: 88 },
  { rank: 4, productName: "プロテインバーFIT", platform: "instagram", genre: "健康食品", change: 0, spendEstimate: 4300000, playCount: 650000, trendScore: 82 },
  { rank: 5, productName: "美白クリームルーチェ", platform: "youtube", genre: "美容・コスメ", change: 3, spendEstimate: 3800000, playCount: 580000, trendScore: 78 },
  { rank: 6, productName: "アイクリームモイスト", platform: "tiktok", genre: "美容・コスメ", change: 12, spendEstimate: 3200000, playCount: 510000, trendScore: 75 },
  { rank: 7, productName: "酵素ドリンクナチュラ", platform: "line", genre: "健康食品", change: -3, spendEstimate: 2800000, playCount: 430000, trendScore: 70 },
  { rank: 8, productName: "CBDオイルリラクス", platform: "facebook", genre: "健康・リラックス", change: 1, spendEstimate: 2400000, playCount: 380000, trendScore: 66 },
];

const platformLabels: Record<string, string> = {
  youtube: "YT",
  shorts: "S",
  tiktok: "TT",
  facebook: "FB",
  instagram: "IG",
  line: "L",
  yahoo: "Y!",
  x: "X",
};

const platformColors: Record<string, string> = {
  youtube: "platform-youtube",
  shorts: "bg-red-400",
  tiktok: "platform-tiktok",
  facebook: "platform-facebook",
  instagram: "platform-instagram",
  line: "platform-line",
  yahoo: "platform-yahoo",
  x: "platform-x",
};

const categoryOptions: { value: TrendCategory; label: string }[] = [
  { value: "all", label: "全ジャンル" },
  { value: "beauty", label: "美容・コスメ" },
  { value: "health", label: "健康食品" },
  { value: "diet", label: "ダイエット" },
  { value: "haircare", label: "ヘアケア" },
  { value: "oral", label: "オーラルケア" },
];

function formatYen(n: number): string {
  if (n >= 100000000) return "¥" + (n / 100000000).toFixed(1) + "億";
  if (n >= 10000) return "¥" + (n / 10000).toFixed(0) + "万";
  return "¥" + n.toLocaleString();
}

function formatNumber(n: number): string {
  if (n >= 100000000) return (n / 100000000).toFixed(1) + "億";
  if (n >= 10000) return (n / 10000).toFixed(0) + "万";
  return n.toLocaleString();
}

export default function TrendView() {
  const [period, setPeriod] = useState<TrendPeriod>("daily");
  const [category, setCategory] = useState<TrendCategory>("all");
  const [trends, setTrends] = useState<TrendItem[]>(mockTrends);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTrends = async () => {
      try {
        const params: Record<string, string> = {};
        if (period) params.period = period;
        if (category !== "all") params.genre = category;

        const response = await analyticsApi.getTrends(params);
        const items = response.data?.items || response.data?.results || response.data;
        if (Array.isArray(items) && items.length > 0) {
          const mapped: TrendItem[] = items.map((item: Record<string, unknown>, idx: number) => ({
            rank: (item.rank as number) || idx + 1,
            productName: (item.product_name as string) || "不明",
            platform: (item.platform as string) || "youtube",
            genre: (item.genre as string) || "",
            change: (item.rank_change as number) || (item.change as number) || 0,
            spendEstimate: (item.spend_estimate as number) || (item.spend_increase as number) || 0,
            playCount: (item.play_count as number) || (item.view_increase as number) || 0,
            trendScore: (item.trend_score as number) || 0,
          }));
          setTrends(mapped);
        }
      } catch (error) {
        console.warn("API unavailable, using mock data:", error);
        // keep mock data as fallback
      } finally {
        setLoading(false);
      }
    };
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
          <p className="text-xl font-bold text-gray-900 mt-1">24</p>
          <p className="text-[10px] text-emerald-600 mt-0.5">+8 vs 前期</p>
        </div>
        <div className="card py-3">
          <p className="text-[10px] text-gray-400 font-medium">新規出稿</p>
          <p className="text-xl font-bold text-gray-900 mt-1">156</p>
          <p className="text-[10px] text-emerald-600 mt-0.5">+23 vs 前期</p>
        </div>
        <div className="card py-3">
          <p className="text-[10px] text-gray-400 font-medium">市場推定消化額</p>
          <p className="text-xl font-bold text-gray-900 mt-1">¥4.2億</p>
          <p className="text-[10px] text-emerald-600 mt-0.5">+12% vs 前期</p>
        </div>
        <div className="card py-3">
          <p className="text-[10px] text-gray-400 font-medium">トレンドスコア平均</p>
          <p className="text-xl font-bold text-gray-900 mt-1">76.4</p>
          <p className="text-[10px] text-red-500 mt-0.5">-2.1 vs 前期</p>
        </div>
      </div>

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
