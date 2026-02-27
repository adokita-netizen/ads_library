"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { platformLabels, platformColors, genreOptions } from "@/lib/constants";
import { formatNumber, formatYen } from "@/lib/format";

interface HitAd {
  rank: number;
  ad_id: number;
  product_name: string;
  advertiser_name: string;
  genre: string;
  platform: string;
  view_increase: number;
  spend_increase: number;
  cumulative_views: number;
  cumulative_spend: number;
  is_hit: boolean;
  hit_score: number;
  trend_score: number;
  rank_change: number | null;
  previous_rank: number | null;
  thumbnail: string;
  duration_seconds: number;
  image_url: string;
  snapshot_url: string;
}

interface GenreSummary {
  genre: string;
  ad_count: number;
  advertiser_count: number;
  total_views: number;
  total_spend: number;
}

interface HitAdAnalysisViewProps {
  onAdSelect: (adId: number) => void;
}

export default function HitAdAnalysisView({ onAdSelect }: HitAdAnalysisViewProps) {
  const [hitAds, setHitAds] = useState<HitAd[]>([]);
  const [genres, setGenres] = useState<GenreSummary[]>([]);
  const [selectedGenre, setSelectedGenre] = useState("all");
  const [loading, setLoading] = useState(true);
  const [computing, setComputing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEmpty, setIsEmpty] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined> = { limit: 50 };
      if (selectedGenre !== "all") params.genre = selectedGenre;

      const [hitRes, genreRes] = await Promise.all([
        fetchApi<{ total: number; items: HitAd[] }>("/rankings/hit-ads", { params }),
        fetchApi<{ genres: GenreSummary[] }>("/rankings/genre-summary", { params: { period: "weekly" } }),
      ]);

      setHitAds(hitRes.items || []);
      setGenres(genreRes.genres || []);
      setIsEmpty((hitRes.items || []).length === 0 && (genreRes.genres || []).length === 0);
    } catch (err) {
      setError("データの取得に失敗しました");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [selectedGenre]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCompute = async () => {
    setComputing(true);
    try {
      await fetchApi("/rankings/compute", { method: "POST" });
      await fetchData();
    } catch (err) {
      setError("ランキング計算に失敗しました");
      console.error(err);
    } finally {
      setComputing(false);
    }
  };

  // Summary stats
  const totalHits = hitAds.filter((a) => a.is_hit).length;
  const avgHitScore = hitAds.length > 0 ? Math.round(hitAds.reduce((s, a) => s + (a.hit_score || 0), 0) / hitAds.length) : 0;
  const topGenre = genres.length > 0 ? genres[0] : null;
  const totalSpend = genres.reduce((s, g) => s + (g.total_spend || 0), 0);

  const genreLabel = (value: string) => genreOptions.find((g) => g.value === value)?.label || value;

  const renderRankChange = (change: number | null) => {
    if (change === null || change === undefined) return <span className="text-gray-300">-</span>;
    if (change > 0) return <span className="text-emerald-600 text-[11px] font-semibold">↑{change}</span>;
    if (change < 0) return <span className="text-red-500 text-[11px] font-semibold">↓{Math.abs(change)}</span>;
    return <span className="text-gray-400 text-[11px]">→</span>;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <h2 className="text-[15px] font-bold text-gray-900">ヒット広告分析</h2>
          <p className="text-[11px] text-gray-400">高成長・高スコアの広告をリアルタイムで分析</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedGenre}
            onChange={(e) => setSelectedGenre(e.target.value)}
            className="select-filter text-[12px] h-8"
          >
            {genreOptions.map((g) => (
              <option key={g.value} value={g.value}>{g.label}</option>
            ))}
          </select>
          <button
            onClick={handleCompute}
            disabled={computing}
            className="btn-primary text-[12px] px-3 py-1.5 h-8 flex items-center gap-1.5"
          >
            {computing ? (
              <>
                <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                計算中...
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                </svg>
                再計算
              </>
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto custom-scrollbar px-5 py-4 space-y-4">
        {/* Summary Cards */}
        <div className="grid grid-cols-4 gap-3">
          <div className="card px-4 py-3">
            <p className="text-[11px] text-gray-400 font-medium">ヒット広告数</p>
            <p className="text-[22px] font-bold text-gray-900 mt-0.5">{totalHits}<span className="text-[13px] text-gray-400 ml-1">件</span></p>
            <p className="text-[10px] text-gray-400 mt-1">全{hitAds.length}件中</p>
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
            <p className="text-[15px] font-bold text-gray-900 mt-0.5 truncate">{topGenre ? genreLabel(topGenre.genre) : "-"}</p>
            <p className="text-[10px] text-gray-400 mt-1">{topGenre ? `${topGenre.ad_count}件 / ${topGenre.advertiser_count}社` : "データなし"}</p>
          </div>
          <div className="card px-4 py-3">
            <p className="text-[11px] text-gray-400 font-medium">市場推定消化額</p>
            <p className="text-[22px] font-bold text-gray-900 mt-0.5">{formatYen(totalSpend)}</p>
            <p className="text-[10px] text-gray-400 mt-1">{genres.length}ジャンル合計 (週間)</p>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-2 text-[12px] text-red-700">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <svg className="animate-spin h-6 w-6 text-[#4A7DFF]" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="ml-2 text-[13px] text-gray-500">読み込み中...</span>
          </div>
        )}

        {/* Empty State */}
        {!loading && isEmpty && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <svg className="w-12 h-12 text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
            </svg>
            <p className="text-[13px] text-gray-500 mb-1">ランキングデータがありません</p>
            <p className="text-[11px] text-gray-400 mb-4">まずランキングを計算してください</p>
            <button onClick={handleCompute} disabled={computing} className="btn-primary text-[12px] px-4 py-2">
              {computing ? "計算中..." : "ランキングを計算"}
            </button>
          </div>
        )}

        {/* Hit Ads Table */}
        {!loading && !isEmpty && hitAds.length > 0 && (
          <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="w-10">#</th>
                    <th className="w-12">画像</th>
                    <th>商材名</th>
                    <th>広告主</th>
                    <th>ジャンル</th>
                    <th className="w-10">媒体</th>
                    <th>ヒットスコア</th>
                    <th className="text-right">トレンド</th>
                    <th className="text-right">消化増加額</th>
                    <th className="text-right">再生増加数</th>
                    <th className="w-12 text-center">変動</th>
                  </tr>
                </thead>
                <tbody>
                  {hitAds.map((ad) => {
                    const thumbSrc = ad.thumbnail || ad.image_url || ad.snapshot_url || "";
                    const pLabel = platformLabels[ad.platform] || ad.platform;
                    const pColor = platformColors[ad.platform] || "bg-gray-400";
                    return (
                      <tr key={ad.ad_id} onClick={() => onAdSelect(ad.ad_id)}>
                        {/* Rank */}
                        <td>
                          <span className={`inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold ${
                            ad.rank <= 3 ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-500"
                          }`}>
                            {ad.rank}
                          </span>
                        </td>
                        {/* Thumbnail */}
                        <td>
                          {thumbSrc ? (
                            <img
                              src={thumbSrc}
                              alt=""
                              className="w-10 h-10 rounded object-cover bg-gray-100"
                              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                            />
                          ) : (
                            <div className="w-10 h-10 rounded bg-gray-100 flex items-center justify-center">
                              <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                              </svg>
                            </div>
                          )}
                        </td>
                        {/* Product Name + HIT badge */}
                        <td>
                          <div className="flex items-center gap-1.5">
                            <span className="text-[13px] font-medium text-gray-900 truncate max-w-[200px]">
                              {ad.product_name}
                            </span>
                            {ad.is_hit && (
                              <span className="shrink-0 rounded bg-red-500 px-1 py-px text-[8px] font-bold text-white leading-none">
                                HIT
                              </span>
                            )}
                          </div>
                        </td>
                        {/* Advertiser */}
                        <td>
                          <span className="text-[12px] text-gray-600 truncate max-w-[140px] block">{ad.advertiser_name || "-"}</span>
                        </td>
                        {/* Genre */}
                        <td>
                          <span className="badge-blue text-[10px]">{genreLabel(ad.genre)}</span>
                        </td>
                        {/* Platform */}
                        <td>
                          <span className={`platform-icon ${pColor} text-[9px]`}>{pLabel}</span>
                        </td>
                        {/* Hit Score */}
                        <td>
                          <div className="flex items-center gap-2 min-w-[100px]">
                            <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${ad.hit_score || 0}%`,
                                  backgroundColor: (ad.hit_score || 0) >= 80 ? "#ef4444" : (ad.hit_score || 0) >= 50 ? "#f59e0b" : "#4A7DFF",
                                }}
                              />
                            </div>
                            <span className="text-[11px] font-semibold text-gray-700 w-7 text-right">{ad.hit_score || 0}</span>
                          </div>
                        </td>
                        {/* Trend Score */}
                        <td className="text-right">
                          <span className="text-[12px] font-medium text-gray-700">{ad.trend_score || 0}</span>
                        </td>
                        {/* Spend Increase */}
                        <td className="text-right">
                          <span className="text-[13px] font-semibold text-gray-900">{formatYen(ad.spend_increase || 0)}</span>
                        </td>
                        {/* View Increase */}
                        <td className="text-right">
                          <span className="text-[13px] font-medium text-gray-700">{formatNumber(ad.view_increase || 0)}</span>
                        </td>
                        {/* Rank Change */}
                        <td className="text-center">
                          {renderRankChange(ad.rank_change)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* No results after filter */}
        {!loading && !isEmpty && hitAds.length === 0 && (
          <div className="text-center py-12">
            <p className="text-[13px] text-gray-500">選択したジャンルにヒット広告がありません</p>
            <button onClick={() => setSelectedGenre("all")} className="btn-secondary text-[12px] px-3 py-1.5 mt-3">
              全ジャンルを表示
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
