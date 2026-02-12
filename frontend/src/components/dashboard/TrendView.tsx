"use client";

import { useState, useEffect } from "react";
import { rankingsApi } from "@/lib/api";

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


const platformLabels: Record<string, string> = {
  youtube: "YT",
  shorts: "S",
  tiktok: "TT",
  facebook: "FB",
  instagram: "IG",
  line: "L",
  yahoo: "Y!",
  x_twitter: "X",
  x: "X",
  pinterest: "Pin",
  smartnews: "SN",
  google_ads: "G",
  gunosy: "Gn",
};

const platformColors: Record<string, string> = {
  youtube: "platform-youtube",
  shorts: "bg-red-400",
  tiktok: "platform-tiktok",
  facebook: "platform-facebook",
  instagram: "platform-instagram",
  line: "platform-line",
  yahoo: "platform-yahoo",
  x_twitter: "platform-x",
  x: "platform-x",
  pinterest: "bg-red-600",
  smartnews: "bg-sky-600",
  google_ads: "bg-blue-500",
  gunosy: "bg-orange-500",
};

const categoryOptions: { value: TrendCategory; label: string }[] = [
  { value: "all", label: "全ジャンル" },
  { value: "ec_d2c", label: "EC・D2C" },
  { value: "app", label: "アプリ" },
  { value: "finance", label: "金融" },
  { value: "education", label: "教育" },
  { value: "beauty", label: "美容・コスメ" },
  { value: "food", label: "食品" },
  { value: "gaming", label: "ゲーム" },
  { value: "health", label: "健康食品" },
  { value: "technology", label: "テクノロジー" },
  { value: "real_estate", label: "不動産" },
  { value: "travel", label: "旅行" },
  { value: "other", label: "その他" },
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
  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTrends = async () => {
      try {
        const params: Record<string, string> = {};
        if (period) params.period = period;
        if (category !== "all") params.genre = category;

        const response = await rankingsApi.getProducts(params as Parameters<typeof rankingsApi.getProducts>[0]);
        const items = response.data?.items || response.data?.rankings || response.data?.results;
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
        console.error("Failed to fetch trends:", error);
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
