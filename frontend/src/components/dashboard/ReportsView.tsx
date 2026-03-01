"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";
import { formatNumber, formatYen } from "@/lib/format";
import { ErrorState, EmptyState } from "@/components/common/StateDisplay";

/* ─── Types ─── */

interface HitAd {
  ad_id: number;
  product_name: string;
  advertiser_name: string;
  genre: string;
  platform: string;
  hit_score: number;
  hit_level?: string;
  creative_type?: string;
  hook_type?: string;
  offer_type?: string;
  cumulative_spend: number;
  spend_increase: number;
  cumulative_views: number;
  is_hit: boolean;
  is_still_running?: boolean;
  published_date: string;
  thumbnail?: string;
  image_url?: string;
}

interface GenreSummary {
  genre: string;
  ad_count: number;
  advertiser_count: number;
  total_views: number;
  total_spend: number;
}

interface ReportsViewProps {
  genre?: string;
  onAdSelect?: (adId: number) => void;
}

type SortKey = "genre" | "ad_count" | "hit_rate" | "avg_score" | "avg_spend";
type SortDir = "asc" | "desc";

/* ─── Component ─── */

export default function ReportsView({ genre, onAdSelect }: ReportsViewProps) {
  const [hitAds, setHitAds] = useState<HitAd[]>([]);
  const [genres, setGenres] = useState<GenreSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [genreSortKey, setGenreSortKey] = useState<SortKey>("hit_rate");
  const [genreSortDir, setGenreSortDir] = useState<SortDir>("desc");
  const [expandedAdvertiser, setExpandedAdvertiser] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const params: Record<string, string | number | undefined> = { limit: 200 };
      if (genre && genre !== "all") params.genre = genre;

      const [hitResult, genreResult] = await Promise.allSettled([
        fetchApi<{ total: number; items: HitAd[] }>("/rankings/hit-ads", { params }),
        fetchApi<{ genres: GenreSummary[] }>("/rankings/genre-summary", { params: { period: "weekly" } }),
      ]);
      const hitRes = hitResult.status === "fulfilled" ? hitResult.value : { total: 0, items: [] as HitAd[] };
      const genreRes = genreResult.status === "fulfilled" ? genreResult.value : { genres: [] as GenreSummary[] };

      if (hitResult.status === "rejected" && genreResult.status === "rejected") {
        setFetchError("レポートデータの取得に失敗しました");
      }

      setHitAds(hitRes.items || []);
      setGenres(genreRes.genres || []);
    } catch {
      setFetchError("レポートデータの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [genre]);

  useEffect(() => { fetchData(); }, [fetchData]);

  /* ─── Computed summaries ─── */

  const totalAds = hitAds.length;
  const hitCount = hitAds.filter((a) => a.is_hit).length;
  const hitRate = totalAds > 0 ? Math.round((hitCount / totalAds) * 100) : 0;
  const totalSpend = hitAds.reduce((s, a) => s + (a.cumulative_spend || 0), 0);
  const avgScore = totalAds > 0 ? Math.round(hitAds.reduce((s, a) => s + (a.hit_score || 0), 0) / totalAds) : 0;
  const topGenreEntry = genres.length > 0 ? [...genres].sort((a, b) => b.ad_count - a.ad_count)[0] : null;

  const genreLabel = (value: string | null | undefined): string => {
    if (!value || value === "未分類") return "未分類";
    return genreOptions.find((g) => g.value === value)?.label || value;
  };

  /* ─── Genre Performance Table (sortable) ─── */

  const genrePerformance = useMemo(() => {
    const map = new Map<string, { genre: string; ad_count: number; hit_count: number; total_score: number; total_spend: number; top_archetype: string }>();

    hitAds.forEach((ad) => {
      const g = ad.genre || "未分類";
      if (!map.has(g)) map.set(g, { genre: g, ad_count: 0, hit_count: 0, total_score: 0, total_spend: 0, top_archetype: "-" });
      const entry = map.get(g)!;
      entry.ad_count++;
      if (ad.is_hit) entry.hit_count++;
      entry.total_score += ad.hit_score || 0;
      entry.total_spend += ad.cumulative_spend || 0;
      if (ad.hook_type && ad.hook_type !== "unknown") entry.top_archetype = ad.hook_type;
    });

    const arr = Array.from(map.values()).map((e) => ({
      ...e,
      hit_rate: e.ad_count > 0 ? Math.round((e.hit_count / e.ad_count) * 100) : 0,
      avg_score: e.ad_count > 0 ? Math.round(e.total_score / e.ad_count) : 0,
      avg_spend: e.ad_count > 0 ? Math.round(e.total_spend / e.ad_count) : 0,
    }));

    arr.sort((a, b) => {
      const mul = genreSortDir === "asc" ? 1 : -1;
      switch (genreSortKey) {
        case "genre": return mul * a.genre.localeCompare(b.genre);
        case "ad_count": return mul * (a.ad_count - b.ad_count);
        case "hit_rate": return mul * (a.hit_rate - b.hit_rate);
        case "avg_score": return mul * (a.avg_score - b.avg_score);
        case "avg_spend": return mul * (a.avg_spend - b.avg_spend);
        default: return 0;
      }
    });

    return arr;
  }, [hitAds, genreSortKey, genreSortDir]);

  const handleGenreSort = (key: SortKey) => {
    if (genreSortKey === key) {
      setGenreSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setGenreSortKey(key);
      setGenreSortDir("desc");
    }
  };

  /* ─── Advertiser Report (top 20) ─── */

  const advertiserReport = useMemo(() => {
    const map = new Map<string, { name: string; ads: HitAd[]; hit_count: number; total_score: number; total_spend: number }>();
    hitAds.forEach((ad) => {
      const name = ad.advertiser_name || "不明";
      if (!map.has(name)) map.set(name, { name, ads: [], hit_count: 0, total_score: 0, total_spend: 0 });
      const entry = map.get(name)!;
      entry.ads.push(ad);
      if (ad.is_hit) entry.hit_count++;
      entry.total_score += ad.hit_score || 0;
      entry.total_spend += ad.cumulative_spend || 0;
    });
    return Array.from(map.values())
      .map((e) => ({
        ...e,
        ad_count: e.ads.length,
        hit_rate: e.ads.length > 0 ? Math.round((e.hit_count / e.ads.length) * 100) : 0,
        avg_score: e.ads.length > 0 ? Math.round(e.total_score / e.ads.length) : 0,
      }))
      .sort((a, b) => b.ad_count - a.ad_count)
      .slice(0, 20);
  }, [hitAds]);

  /* ─── Creative Pattern Report ─── */

  const creativePatterns = useMemo(() => {
    const hookMap = new Map<string, { count: number; total_score: number; hit_count: number }>();
    const ctaMap = new Map<string, { count: number; total_score: number; hit_count: number }>();
    let videoCount = 0;
    let imageCount = 0;
    let videoScore = 0;
    let imageScore = 0;

    hitAds.forEach((ad) => {
      // Hook type
      const hook = ad.hook_type || "不明";
      if (!hookMap.has(hook)) hookMap.set(hook, { count: 0, total_score: 0, hit_count: 0 });
      const hEntry = hookMap.get(hook)!;
      hEntry.count++;
      hEntry.total_score += ad.hit_score || 0;
      if (ad.is_hit) hEntry.hit_count++;

      // CTA / offer type
      const cta = ad.offer_type || "不明";
      if (!ctaMap.has(cta)) ctaMap.set(cta, { count: 0, total_score: 0, hit_count: 0 });
      const cEntry = ctaMap.get(cta)!;
      cEntry.count++;
      cEntry.total_score += ad.hit_score || 0;
      if (ad.is_hit) cEntry.hit_count++;

      // Creative type
      if (ad.creative_type === "video") { videoCount++; videoScore += ad.hit_score || 0; }
      else { imageCount++; imageScore += ad.hit_score || 0; }
    });

    const hookPerformance = Array.from(hookMap.entries())
      .map(([name, v]) => ({ name, ...v, avg_score: v.count > 0 ? Math.round(v.total_score / v.count) : 0 }))
      .sort((a, b) => b.avg_score - a.avg_score);

    const ctaPerformance = Array.from(ctaMap.entries())
      .map(([name, v]) => ({ name, ...v, avg_score: v.count > 0 ? Math.round(v.total_score / v.count) : 0 }))
      .sort((a, b) => b.avg_score - a.avg_score);

    const topCombos = hookPerformance.slice(0, 5);

    const bestCreativeType = videoCount > 0 && imageCount > 0
      ? (videoScore / videoCount > imageScore / imageCount ? "動画" : "静止画")
      : videoCount > 0 ? "動画" : "静止画";

    return { hookPerformance, ctaPerformance, topCombos, videoCount, imageCount, videoScore, imageScore, bestCreativeType };
  }, [hitAds]);

  /* ─── Export Handlers ─── */

  const handleExportCSV = async () => {
    try {
      const params = new URLSearchParams();
      if (genre && genre !== "all") params.set("genre", genre);
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      const url = `/api/v1/rankings/export/csv${params.toString() ? `?${params.toString()}` : ""}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = `report_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(objectUrl);
      toast.success("CSVをダウンロードしました");
    } catch {
      toast.error("CSVエクスポートに失敗しました");
    }
  };

  const handleExportJSON = async () => {
    try {
      const params: Record<string, string | number | undefined> = {};
      if (genre && genre !== "all") params.genre = genre;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const data = await fetchApi("/rankings/export/json", { params });
      const json = JSON.stringify(data, null, 2);
      const blob = new Blob([json], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("JSONをダウンロードしました");
    } catch {
      toast.error("JSONエクスポートに失敗しました");
    }
  };

  const handleExportHTML = () => {
    // Generate a simple HTML report inline
    const html = `<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><title>VAAP レポート</title>
<style>body{font-family:sans-serif;max-width:900px;margin:auto;padding:20px}
table{width:100%;border-collapse:collapse;margin:16px 0}
th,td{border:1px solid #ddd;padding:8px;text-align:left;font-size:13px}
th{background:#f5f5f5}h1{font-size:18px}h2{font-size:15px;margin-top:24px}
.stat{display:inline-block;padding:8px 16px;margin:4px;border:1px solid #ddd;border-radius:8px}</style></head>
<body>
<h1>VAAP 広告分析レポート</h1>
<p>生成日: ${new Date().toLocaleDateString("ja-JP")}</p>
<div>
<div class="stat">総広告数: <strong>${totalAds}</strong></div>
<div class="stat">ヒット率: <strong>${hitRate}%</strong></div>
<div class="stat">平均スコア: <strong>${avgScore}</strong></div>
<div class="stat">推定消化額: <strong>${formatYen(totalSpend)}</strong></div>
</div>
<h2>ジャンル別パフォーマンス</h2>
<table><tr><th>ジャンル</th><th>広告数</th><th>ヒット率</th><th>平均スコア</th><th>平均消化額</th></tr>
${genrePerformance.map((g) => `<tr><td>${genreLabel(g.genre)}</td><td>${g.ad_count}</td><td>${g.hit_rate}%</td><td>${g.avg_score}</td><td>${formatYen(g.avg_spend)}</td></tr>`).join("")}
</table>
<h2>広告主ランキング (上位20)</h2>
<table><tr><th>広告主</th><th>広告数</th><th>ヒット率</th><th>平均スコア</th><th>推定消化額</th></tr>
${advertiserReport.map((a) => `<tr><td>${a.name}</td><td>${a.ad_count}</td><td>${a.hit_rate}%</td><td>${a.avg_score}</td><td>${formatYen(a.total_spend)}</td></tr>`).join("")}
</table>
</body></html>`;
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_${new Date().toISOString().slice(0, 10)}.html`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("HTMLレポートを生成しました");
  };

  const sortIcon = (key: SortKey) => {
    if (genreSortKey !== key) return null;
    return genreSortDir === "asc" ? " ↑" : " ↓";
  };

  /* ─── Loading State ─── */

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="card px-4 py-4">
              <div className="h-3 bg-gray-200 rounded w-20 mb-2" />
              <div className="h-6 bg-gray-200 rounded w-16" />
            </div>
          ))}
        </div>
        <div className="card px-4 py-4">
          <div className="h-4 bg-gray-200 rounded w-40 mb-3" />
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-8 bg-gray-100 rounded" />)}
          </div>
        </div>
      </div>
    );
  }

  /* ─── Error / Empty ─── */

  if (fetchError && hitAds.length === 0) {
    return <ErrorState message={fetchError} onRetry={fetchData} />;
  }

  if (!loading && hitAds.length === 0 && genres.length === 0) {
    return (
      <EmptyState
        icon="chart"
        message="レポートデータがありません"
        description="広告データが収集されると、ここにレポートが表示されます"
      />
    );
  }

  /* ─── Render ─── */

  return (
    <div className="space-y-4">
      {/* Error banner (partial failure) */}
      {fetchError && <ErrorState message={fetchError} onRetry={fetchData} compact />}

      {/* ── Summary Report Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="card px-4 py-3">
          <p className="text-[10px] text-gray-400 font-medium">総広告数</p>
          <p className="text-[20px] font-bold text-gray-900 mt-0.5">{formatNumber(totalAds)}</p>
          <p className="text-[9px] text-gray-400 mt-0.5">ヒット {hitCount}件</p>
        </div>
        <div className="card px-4 py-3">
          <p className="text-[10px] text-gray-400 font-medium">ヒット率</p>
          <p className="text-[20px] font-bold text-[#4A7DFF] mt-0.5">{hitRate}<span className="text-[12px] text-gray-400 ml-0.5">%</span></p>
          <div className="mt-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full rounded-full bg-[#4A7DFF]" style={{ width: `${hitRate}%` }} />
          </div>
        </div>
        <div className="card px-4 py-3">
          <p className="text-[10px] text-gray-400 font-medium">推定消化額</p>
          <p className="text-[20px] font-bold text-gray-900 mt-0.5">{formatYen(totalSpend)}</p>
        </div>
        <div className="card px-4 py-3">
          <p className="text-[10px] text-gray-400 font-medium">平均スコア</p>
          <p className="text-[20px] font-bold text-gray-900 mt-0.5">{avgScore}<span className="text-[12px] text-gray-400 ml-0.5">/ 100</span></p>
          <div className="mt-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full rounded-full bg-emerald-400" style={{ width: `${avgScore}%` }} />
          </div>
        </div>
        <div className="card px-4 py-3">
          <p className="text-[10px] text-gray-400 font-medium">トップジャンル</p>
          <p className="text-[14px] font-bold text-gray-900 mt-0.5 truncate">
            {topGenreEntry ? genreLabel(topGenreEntry.genre) : "-"}
          </p>
          {topGenreEntry && (
            <p className="text-[9px] text-gray-400 mt-0.5">{topGenreEntry.ad_count}件 / {topGenreEntry.advertiser_count}社</p>
          )}
        </div>
      </div>

      {/* ── Genre Performance Table ── */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
          <h3 className="text-[13px] font-bold text-gray-900">ジャンル別パフォーマンス</h3>
        </div>
        {genrePerformance.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-[11px] text-gray-400">ジャンルデータがありません</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="bg-gray-50 text-gray-500">
                  <th className="px-4 py-2 text-left font-medium cursor-pointer hover:text-gray-700" onClick={() => handleGenreSort("genre")}>
                    ジャンル{sortIcon("genre")}
                  </th>
                  <th className="px-3 py-2 text-right font-medium cursor-pointer hover:text-gray-700" onClick={() => handleGenreSort("ad_count")}>
                    広告数{sortIcon("ad_count")}
                  </th>
                  <th className="px-3 py-2 text-right font-medium cursor-pointer hover:text-gray-700" onClick={() => handleGenreSort("hit_rate")}>
                    ヒット率{sortIcon("hit_rate")}
                  </th>
                  <th className="px-3 py-2 text-right font-medium cursor-pointer hover:text-gray-700" onClick={() => handleGenreSort("avg_score")}>
                    平均スコア{sortIcon("avg_score")}
                  </th>
                  <th className="px-3 py-2 text-left font-medium">アーキタイプ</th>
                  <th className="px-3 py-2 text-right font-medium cursor-pointer hover:text-gray-700" onClick={() => handleGenreSort("avg_spend")}>
                    平均消化額{sortIcon("avg_spend")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {genrePerformance.map((g) => (
                  <tr key={g.genre} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-4 py-2.5 font-medium text-gray-900">{genreLabel(g.genre)}</td>
                    <td className="px-3 py-2.5 text-right text-gray-700">{g.ad_count}</td>
                    <td className="px-3 py-2.5 text-right">
                      <span className={g.hit_rate >= 30 ? "text-emerald-600 font-medium" : "text-gray-700"}>
                        {g.hit_rate}%
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <span className={g.avg_score >= 70 ? "text-[#4A7DFF] font-medium" : "text-gray-700"}>
                        {g.avg_score}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-gray-500">{g.top_archetype}</td>
                    <td className="px-3 py-2.5 text-right text-gray-700">{formatYen(g.avg_spend)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Advertiser Report (Top 20) ── */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
          </svg>
          <h3 className="text-[13px] font-bold text-gray-900">広告主レポート</h3>
          <span className="text-[9px] text-gray-400 ml-1">上位20社</span>
        </div>
        {advertiserReport.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-[11px] text-gray-400">広告主データがありません</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {advertiserReport.map((adv, idx) => (
              <div key={adv.name}>
                <div
                  className="px-4 py-2.5 flex items-center gap-3 hover:bg-gray-50/50 transition-colors cursor-pointer"
                  onClick={() => setExpandedAdvertiser(expandedAdvertiser === adv.name ? null : adv.name)}
                >
                  <span className="text-[10px] text-gray-400 w-5 text-right shrink-0">{idx + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-medium text-gray-900 truncate">{adv.name}</p>
                  </div>
                  <span className="text-[10px] text-gray-500 shrink-0">{adv.ad_count}件</span>
                  <span className={`text-[10px] shrink-0 ${adv.hit_rate >= 30 ? "text-emerald-600 font-medium" : "text-gray-500"}`}>
                    {adv.hit_rate}%
                  </span>
                  <span className="text-[10px] text-gray-500 shrink-0 w-12 text-right">{adv.avg_score}pt</span>
                  <span className="text-[10px] text-gray-500 shrink-0 w-16 text-right">{formatYen(adv.total_spend)}</span>
                  <svg className={`w-3.5 h-3.5 text-gray-400 shrink-0 transition-transform ${expandedAdvertiser === adv.name ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                  </svg>
                </div>
                {expandedAdvertiser === adv.name && (
                  <div className="px-4 pb-3 pl-12">
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                      {adv.ads.slice(0, 8).map((ad) => (
                        <div
                          key={ad.ad_id}
                          className="bg-gray-50 rounded-lg p-2 cursor-pointer hover:bg-gray-100 transition-colors"
                          onClick={(e) => { e.stopPropagation(); onAdSelect?.(ad.ad_id); }}
                        >
                          <p className="text-[9px] font-medium text-gray-900 truncate">{ad.product_name || "不明"}</p>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <span className="text-[8px] text-gray-400">{ad.platform}</span>
                            <span className={`text-[8px] font-medium ${(ad.hit_score || 0) >= 70 ? "text-[#4A7DFF]" : "text-gray-500"}`}>
                              {ad.hit_score || 0}pt
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                    {adv.ads.length > 8 && (
                      <p className="text-[9px] text-gray-400 mt-1.5">+{adv.ads.length - 8}件</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Creative Pattern Report ── */}
      <div className="card px-4 py-4 space-y-4">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
          </svg>
          <h3 className="text-[13px] font-bold text-gray-900">クリエイティブパターン分析</h3>
        </div>

        {/* Winning Patterns (Top 5) */}
        <div>
          <p className="text-[10px] text-gray-500 font-medium mb-2">勝ちパターン (上位5)</p>
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
            {creativePatterns.topCombos.length === 0 ? (
              <p className="text-[10px] text-gray-400 col-span-5">データ不足</p>
            ) : (
              creativePatterns.topCombos.map((combo, i) => (
                <div key={combo.name} className="bg-gray-50 rounded-lg px-3 py-2 text-center">
                  <p className="text-[9px] text-gray-400">#{i + 1}</p>
                  <p className="text-[11px] font-medium text-gray-900 mt-0.5">{combo.name}</p>
                  <p className="text-[10px] text-[#4A7DFF] font-medium mt-0.5">{combo.avg_score}pt</p>
                  <p className="text-[8px] text-gray-400">{combo.count}件</p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Hook Type Performance */}
        <div>
          <p className="text-[10px] text-gray-500 font-medium mb-2">フックタイプ別パフォーマンス</p>
          {creativePatterns.hookPerformance.length === 0 ? (
            <p className="text-[10px] text-gray-400">データ不足</p>
          ) : (
            <div className="space-y-1.5">
              {creativePatterns.hookPerformance.slice(0, 8).map((hook) => {
                const barWidth = hook.avg_score;
                return (
                  <div key={hook.name} className="flex items-center gap-2">
                    <span className="text-[10px] text-gray-700 w-20 truncate shrink-0">{hook.name}</span>
                    <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[#4A7DFF]/70"
                        style={{ width: `${barWidth}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-gray-600 w-10 text-right shrink-0">{hook.avg_score}pt</span>
                    <span className="text-[9px] text-gray-400 w-8 text-right shrink-0">{hook.count}件</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* CTA Type Performance */}
        <div>
          <p className="text-[10px] text-gray-500 font-medium mb-2">CTA/オファータイプ別パフォーマンス</p>
          {creativePatterns.ctaPerformance.length === 0 ? (
            <p className="text-[10px] text-gray-400">データ不足</p>
          ) : (
            <div className="space-y-1.5">
              {creativePatterns.ctaPerformance.slice(0, 8).map((cta) => {
                const barWidth = cta.avg_score;
                return (
                  <div key={cta.name} className="flex items-center gap-2">
                    <span className="text-[10px] text-gray-700 w-20 truncate shrink-0">{cta.name}</span>
                    <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-emerald-400/70"
                        style={{ width: `${barWidth}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-gray-600 w-10 text-right shrink-0">{cta.avg_score}pt</span>
                    <span className="text-[9px] text-gray-400 w-8 text-right shrink-0">{cta.count}件</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Creative Type Comparison */}
        <div>
          <p className="text-[10px] text-gray-500 font-medium mb-2">クリエイティブ形式</p>
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-gray-50 rounded-lg px-3 py-2 text-center">
              <p className="text-[10px] text-gray-500">動画</p>
              <p className="text-[16px] font-bold text-gray-900">{creativePatterns.videoCount}</p>
              <p className="text-[9px] text-gray-400">
                平均 {creativePatterns.videoCount > 0 ? Math.round(creativePatterns.videoScore / creativePatterns.videoCount) : 0}pt
              </p>
            </div>
            <div className="bg-gray-50 rounded-lg px-3 py-2 text-center">
              <p className="text-[10px] text-gray-500">静止画</p>
              <p className="text-[16px] font-bold text-gray-900">{creativePatterns.imageCount}</p>
              <p className="text-[9px] text-gray-400">
                平均 {creativePatterns.imageCount > 0 ? Math.round(creativePatterns.imageScore / creativePatterns.imageCount) : 0}pt
              </p>
            </div>
            <div className="bg-[#EEF2FF] rounded-lg px-3 py-2 text-center">
              <p className="text-[10px] text-[#4A7DFF]">ベスト形式</p>
              <p className="text-[16px] font-bold text-[#4A7DFF]">{creativePatterns.bestCreativeType}</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Export Panel ── */}
      <div className="card px-4 py-4 space-y-3">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          <h3 className="text-[13px] font-bold text-gray-900">エクスポート</h3>
        </div>

        {/* Date range selector */}
        <div className="flex items-center gap-2 flex-wrap">
          <label className="text-[10px] text-gray-500">期間:</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="h-7 px-2 rounded-lg border border-gray-200 text-[10px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]"
          />
          <span className="text-[10px] text-gray-400">〜</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="h-7 px-2 rounded-lg border border-gray-200 text-[10px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]"
          />
        </div>

        {/* Export buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleExportCSV}
            className="h-8 px-4 rounded-lg text-[11px] font-medium text-white bg-emerald-500 hover:bg-emerald-600 transition-colors flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            CSV エクスポート
          </button>
          <button
            onClick={handleExportJSON}
            className="h-8 px-4 rounded-lg text-[11px] font-medium text-white bg-blue-500 hover:bg-blue-600 transition-colors flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
            </svg>
            JSON エクスポート
          </button>
          <button
            onClick={handleExportHTML}
            className="h-8 px-4 rounded-lg text-[11px] font-medium text-white bg-purple-500 hover:bg-purple-600 transition-colors flex items-center gap-1.5"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            レポート生成 (HTML)
          </button>
        </div>
      </div>
    </div>
  );
}
