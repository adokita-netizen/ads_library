"use client";

import React, { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { formatYen } from "@/lib/format";

interface Competitor {
  name: string;
  ad_count: number;
  hit_rate: number;
  avg_score: number;
  top_genre?: string;
  trend?: "up" | "down" | "stable";
  total_spend?: number;
  is_watched?: boolean;
  recent_ads?: { ad_id: number; product_name?: string; hit_score?: number; thumbnail?: string }[];
}

interface CompetitorDashboardProps {
  genre?: string;
  onAdSelect?: (adId: number) => void;
  onCompetitorSelect?: (name: string) => void;
}

type SortKey = "name" | "ad_count" | "hit_rate" | "avg_score" | "total_spend";

const trendIcons: Record<string, { icon: string; color: string }> = {
  up: { icon: "↑", color: "text-emerald-600" },
  down: { icon: "↓", color: "text-red-500" },
  stable: { icon: "→", color: "text-gray-400" },
};

export default function CompetitorDashboard({ genre, onAdSelect, onCompetitorSelect }: CompetitorDashboardProps) {
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<SortKey>("avg_score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [expandedName, setExpandedName] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (genre) params.genre = genre;
      const res = await fetchApi<{ items?: Competitor[]; competitors?: Competitor[] }>("/rankings/competitors", { params });
      const items = res?.items || res?.competitors || (Array.isArray(res) ? res : []);
      setCompetitors(Array.isArray(items) ? items : []);
    } catch {
      setCompetitors([]);
    } finally {
      setLoading(false);
    }
  }, [genre]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSort = (key: SortKey) => {
    if (sortBy === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key);
      setSortDir("desc");
    }
  };

  const sorted = [...competitors].sort((a, b) => {
    const av = a[sortBy] ?? 0;
    const bv = b[sortBy] ?? 0;
    if (typeof av === "string" && typeof bv === "string") {
      return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
    }
    return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
  });

  const toggleWatch = async (name: string, currentlyWatched: boolean) => {
    try {
      await fetchApi("/rankings/competitors/watchlist", {
        method: currentlyWatched ? "DELETE" : "POST",
        body: { name },
      });
      setCompetitors((prev) =>
        prev.map((c) => (c.name === name ? { ...c, is_watched: !currentlyWatched } : c))
      );
      toast.success(currentlyWatched ? "ウォッチリストから削除しました" : "ウォッチリストに追加しました");
    } catch {
      toast.error("操作に失敗しました");
    }
  };

  if (loading) {
    return (
      <div className="card overflow-hidden animate-pulse">
        <div className="px-4 py-3 border-b border-gray-100">
          <div className="h-4 bg-gray-200 rounded w-40" />
        </div>
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="px-4 py-3 border-b border-gray-50 flex gap-3">
            <div className="h-3 bg-gray-200 rounded w-24" />
            <div className="h-3 bg-gray-100 rounded w-12" />
            <div className="h-3 bg-gray-100 rounded w-12" />
            <div className="h-3 bg-gray-100 rounded w-16" />
          </div>
        ))}
      </div>
    );
  }

  if (competitors.length === 0) {
    return (
      <div className="card px-4 py-10 text-center">
        <svg className="w-10 h-10 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
        </svg>
        <p className="text-[12px] text-gray-500">競合データがありません</p>
      </div>
    );
  }

  const SortHeader = ({ label, field }: { label: string; field: SortKey }) => (
    <th
      className="text-[10px] text-gray-400 font-medium text-left pb-2 cursor-pointer hover:text-gray-600 select-none"
      onClick={() => handleSort(field)}
    >
      <span className="flex items-center gap-0.5">
        {label}
        {sortBy === field && <span className="text-[8px]">{sortDir === "desc" ? "▼" : "▲"}</span>}
      </span>
    </th>
  );

  return (
    <div className="card overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">競合リーダーボード</h3>
        <span className="text-[9px] text-gray-400">{competitors.length}社</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-[10px] text-gray-400 font-medium text-left px-4 pb-2 pt-3 w-6"></th>
              <SortHeader label="広告主" field="name" />
              <SortHeader label="広告数" field="ad_count" />
              <SortHeader label="HIT率" field="hit_rate" />
              <SortHeader label="平均スコア" field="avg_score" />
              <SortHeader label="消化額" field="total_spend" />
              <th className="text-[10px] text-gray-400 font-medium text-left pb-2 pt-3">トレンド</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((c, i) => {
              const isExpanded = expandedName === c.name;
              const trend = c.trend ? trendIcons[c.trend] : null;
              return (
                <React.Fragment key={c.name}>
                  <tr
                    className={`border-b border-gray-50 hover:bg-gray-50/50 cursor-pointer transition-colors ${isExpanded ? "bg-blue-50/30" : ""}`}
                    onClick={() => setExpandedName(isExpanded ? null : c.name)}
                  >
                    <td className="px-4 py-2.5">
                      <button
                        className={`transition-colors ${c.is_watched ? "text-amber-500" : "text-gray-300 hover:text-amber-400"}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleWatch(c.name, !!c.is_watched);
                        }}
                        title={c.is_watched ? "ウォッチ解除" : "ウォッチ"}
                      >
                        <svg className="w-3.5 h-3.5" fill={c.is_watched ? "currentColor" : "none"} viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
                        </svg>
                      </button>
                    </td>
                    <td className="py-2.5">
                      <button
                        className="text-[11px] font-medium text-[#4A7DFF] hover:underline"
                        onClick={(e) => {
                          e.stopPropagation();
                          onCompetitorSelect?.(c.name);
                        }}
                      >
                        {c.name}
                      </button>
                      {c.top_genre && <p className="text-[8px] text-gray-400">{c.top_genre}</p>}
                    </td>
                    <td className="py-2.5 text-[11px] text-gray-700">{c.ad_count}</td>
                    <td className="py-2.5">
                      <span className={`text-[11px] font-medium ${c.hit_rate >= 50 ? "text-emerald-600" : c.hit_rate >= 25 ? "text-amber-600" : "text-gray-500"}`}>
                        {Math.round(c.hit_rate)}%
                      </span>
                    </td>
                    <td className="py-2.5 text-[11px] font-medium text-gray-900">{Math.round(c.avg_score)}</td>
                    <td className="py-2.5 text-[11px] text-gray-600">{c.total_spend != null ? formatYen(c.total_spend) : "-"}</td>
                    <td className="py-2.5">
                      {trend && <span className={`text-[12px] font-bold ${trend.color}`}>{trend.icon}</span>}
                    </td>
                  </tr>

                  {/* Expanded row with recent ads */}
                  {isExpanded && c.recent_ads && c.recent_ads.length > 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-3 bg-gray-50/50">
                        <p className="text-[9px] text-gray-400 mb-2">最近の広告</p>
                        <div className="flex gap-2 overflow-x-auto pb-1">
                          {c.recent_ads.slice(0, 8).map((ad) => {
                            const thumbSrc = ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || "");
                            return (
                              <div
                                key={ad.ad_id}
                                className="shrink-0 w-24 cursor-pointer rounded-lg overflow-hidden border border-gray-200 bg-white hover:shadow-md transition-all"
                                onClick={(e) => { e.stopPropagation(); onAdSelect?.(ad.ad_id); }}
                              >
                                <div className="relative aspect-video bg-gray-100">
                                  {thumbSrc && (
                                    <img
                                      src={thumbSrc} alt="" className="w-full h-full object-cover" loading="lazy"
                                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                                    />
                                  )}
                                  {ad.hit_score != null && (
                                    <span className="absolute top-0.5 right-0.5 text-[7px] px-1 py-0.5 rounded bg-black/60 text-white font-bold">{ad.hit_score}</span>
                                  )}
                                </div>
                                <p className="text-[8px] text-gray-700 px-1 py-0.5 truncate">{ad.product_name || "不明"}</p>
                              </div>
                            );
                          })}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
