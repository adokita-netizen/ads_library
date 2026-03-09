"use client";

import React, { useState, useMemo, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

// ─── Types ───

interface TimelineAd {
  ad_id: number;
  product_name: string;
  advertiser_name: string;
  genre: string;
  score: number;
  cumulative_views: number;
  first_seen: string; // YYYY-MM-DD
  last_seen: string; // YYYY-MM-DD
  is_active: boolean;
}

type ZoomLevel = "week" | "month" | "quarter";

const GENRE_COLORS: Record<string, string> = {
  "美容": "#ec4899",
  "健康": "#22c55e",
  "ダイエット": "#f97316",
  "金融": "#3b82f6",
  "教育": "#a855f7",
  "不動産": "#14b8a6",
  "ビジネス": "#6366f1",
  "その他": "#6b7280",
};

// Map API category values to display labels
const GENRE_MAP: Record<string, string> = {
  beauty: "美容", health: "健康", diet: "ダイエット",
  finance: "金融", education: "教育", real_estate: "不動産",
  business: "ビジネス", other: "その他",
};

// ─── Component ───

export default function AdTimeline() {
  const [zoom, setZoom] = useState<ZoomLevel>("month");
  const [filterGenre, setFilterGenre] = useState<string>("all");
  const [filterAdvertiser, setFilterAdvertiser] = useState<string>("");
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100]);
  const [activeOnly, setActiveOnly] = useState(false);
  const [hoveredAd, setHoveredAd] = useState<TimelineAd | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [allAds, setAllAds] = useState<TimelineAd[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchTimeline = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchApi<{ products?: Array<Record<string, unknown>> }>("/rankings/pro-ranking", {
        params: { sort_by: "score", page_size: 20 },
      });
      const products = res.products || [];
      const mapped: TimelineAd[] = products.map((p: Record<string, unknown>) => {
        const firstSeen = (p.first_seen_at as string) || (p.created_at as string) || new Date().toISOString();
        const lastSeen = (p.last_seen_at as string) || new Date().toISOString();
        const genreKey = (p.category as string) || (p.genre as string) || "other";
        return {
          ad_id: (p.id as number) || 0,
          product_name: (p.title as string) || (p.product_name as string) || "不明",
          advertiser_name: (p.advertiser_name as string) || "不明",
          genre: GENRE_MAP[genreKey] || genreKey,
          score: (p.hit_score as number) || (p.score as number) || 0,
          cumulative_views: (p.cumulative_views as number) || (p.view_count as number) || 0,
          first_seen: firstSeen.split("T")[0],
          last_seen: lastSeen.split("T")[0],
          is_active: (p.is_still_running as boolean) ?? new Date(lastSeen) >= new Date(Date.now() - 7 * 86400000),
        };
      });
      setAllAds(mapped);
    } catch (err) {
      console.error("タイムラインデータ取得失敗", err);
      setAllAds([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTimeline(); }, [fetchTimeline]);

  const filteredAds = useMemo(() => {
    return allAds.filter((ad) => {
      if (filterGenre !== "all" && ad.genre !== filterGenre) return false;
      if (filterAdvertiser && !ad.advertiser_name.includes(filterAdvertiser)) return false;
      if (ad.score < scoreRange[0] || ad.score > scoreRange[1]) return false;
      if (activeOnly && !ad.is_active) return false;
      return true;
    });
  }, [allAds, filterGenre, filterAdvertiser, scoreRange, activeOnly]);

  // Calculate date range
  const { startDate, endDate, totalDays } = useMemo(() => {
    const now = new Date();
    let start: Date;
    if (zoom === "week") {
      start = new Date(now);
      start.setDate(start.getDate() - 7);
    } else if (zoom === "month") {
      start = new Date(now);
      start.setDate(start.getDate() - 30);
    } else {
      start = new Date(now);
      start.setDate(start.getDate() - 90);
    }
    const days = Math.ceil((now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
    return { startDate: start, endDate: now, totalDays: days };
  }, [zoom]);

  const genres = useMemo(() => {
    const set = new Set(allAds.map((a) => a.genre));
    return Array.from(set);
  }, [allAds]);

  // Date tick marks
  const dateTicks = useMemo(() => {
    const ticks: { date: Date; label: string; position: number }[] = [];
    const step = zoom === "week" ? 1 : zoom === "month" ? 5 : 15;
    for (let i = 0; i <= totalDays; i += step) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);
      ticks.push({
        date: d,
        label: `${d.getMonth() + 1}/${d.getDate()}`,
        position: (i / totalDays) * 100,
      });
    }
    return ticks;
  }, [startDate, totalDays, zoom]);

  const getBarStyle = (ad: TimelineAd) => {
    const adStart = new Date(ad.first_seen);
    const adEnd = new Date(ad.last_seen);
    const clampStart = adStart < startDate ? startDate : adStart;
    const clampEnd = adEnd > endDate ? endDate : adEnd;

    if (clampStart > endDate || clampEnd < startDate) return null;

    const leftPct = ((clampStart.getTime() - startDate.getTime()) / (endDate.getTime() - startDate.getTime())) * 100;
    const widthPct = ((clampEnd.getTime() - clampStart.getTime()) / (endDate.getTime() - startDate.getTime())) * 100;

    return {
      left: `${Math.max(0, leftPct)}%`,
      width: `${Math.max(1, widthPct)}%`,
    };
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <h3 className="text-[13px] font-bold text-gray-900">広告タイムライン</h3>
          <div className="flex items-center gap-2">
            {/* Zoom controls */}
            {(["week", "month", "quarter"] as ZoomLevel[]).map((z) => (
              <button
                key={z}
                onClick={() => setZoom(z)}
                className={`px-2 py-1 text-[10px] font-medium rounded ${
                  zoom === z
                    ? "bg-[#4A7DFF] text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {z === "week" ? "週" : z === "month" ? "月" : "四半期"}
              </button>
            ))}
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mt-2">
          <select
            value={filterGenre}
            onChange={(e) => setFilterGenre(e.target.value)}
            className="text-[10px] border border-gray-200 rounded px-2 py-1 text-gray-700 bg-white"
          >
            <option value="all">全ジャンル</option>
            {genres.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>

          <input
            type="text"
            placeholder="広告主で絞り込み"
            value={filterAdvertiser}
            onChange={(e) => setFilterAdvertiser(e.target.value)}
            className="text-[10px] border border-gray-200 rounded px-2 py-1 text-gray-700 w-32"
          />

          <div className="flex items-center gap-1 text-[10px] text-gray-600">
            <span>スコア:</span>
            <input
              type="number"
              min={0}
              max={100}
              value={scoreRange[0]}
              onChange={(e) => setScoreRange([Number(e.target.value), scoreRange[1]])}
              className="w-10 border border-gray-200 rounded px-1 py-0.5 text-[10px]"
            />
            <span>-</span>
            <input
              type="number"
              min={0}
              max={100}
              value={scoreRange[1]}
              onChange={(e) => setScoreRange([scoreRange[0], Number(e.target.value)])}
              className="w-10 border border-gray-200 rounded px-1 py-0.5 text-[10px]"
            />
          </div>

          <label className="flex items-center gap-1 text-[10px] text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(e) => setActiveOnly(e.target.checked)}
              className="w-3 h-3 rounded border-gray-300"
            />
            アクティブ広告のみ
          </label>
        </div>
      </div>

      {/* Timeline */}
      <div className="relative px-4 py-3 overflow-x-auto">
        {/* Date axis */}
        <div className="relative h-6 mb-1 ml-[160px]">
          {dateTicks.map((tick, i) => (
            <div
              key={i}
              className="absolute text-[9px] text-gray-400 -translate-x-1/2"
              style={{ left: `${tick.position}%` }}
            >
              {tick.label}
              <div className="absolute top-4 left-1/2 w-px h-[500px] bg-gray-100 -translate-x-1/2" />
            </div>
          ))}
        </div>

        {/* Ad bars */}
        <div className="space-y-1">
          {loading ? (
            <div className="py-8 text-center">
              <div className="w-6 h-6 border-2 border-[#4A7DFF] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
              <p className="text-[11px] text-gray-400">読み込み中...</p>
            </div>
          ) : filteredAds.length === 0 ? (
            <div className="py-8 text-center text-[11px] text-gray-400">
              条件に一致する広告がありません
            </div>
          ) : (
            filteredAds.map((ad) => {
              const barStyle = getBarStyle(ad);
              if (!barStyle) return null;
              const color = GENRE_COLORS[ad.genre] || GENRE_COLORS["その他"];

              return (
                <div key={ad.ad_id} className="flex items-center h-7">
                  <div className="w-[160px] shrink-0 pr-2">
                    <p className="text-[10px] font-medium text-gray-700 truncate">{ad.product_name}</p>
                  </div>
                  <div className="flex-1 relative h-5">
                    <div
                      className="absolute h-full rounded-full cursor-pointer transition-opacity hover:opacity-80"
                      style={{
                        ...barStyle,
                        backgroundColor: color,
                        opacity: ad.is_active ? 1 : 0.5,
                      }}
                      onMouseEnter={(e) => {
                        setHoveredAd(ad);
                        setTooltipPos({ x: e.clientX, y: e.clientY });
                      }}
                      onMouseMove={(e) => {
                        setTooltipPos({ x: e.clientX, y: e.clientY });
                      }}
                      onMouseLeave={() => setHoveredAd(null)}
                    >
                      {ad.is_active && (
                        <div className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-white border-2" style={{ borderColor: color }} />
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Genre legend */}
        <div className="flex items-center gap-3 mt-4 pt-3 border-t border-gray-100">
          {Object.entries(GENRE_COLORS).map(([genre, color]) => (
            <div key={genre} className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-[9px] text-gray-500">{genre}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Tooltip */}
      {hoveredAd && (
        <div
          className="fixed z-50 bg-gray-900 text-white rounded-lg shadow-lg px-3 py-2 pointer-events-none"
          style={{
            left: tooltipPos.x + 12,
            top: tooltipPos.y - 60,
          }}
        >
          <p className="text-[11px] font-bold">{hoveredAd.product_name}</p>
          <p className="text-[10px] text-gray-300">{hoveredAd.advertiser_name}</p>
          <div className="flex items-center gap-3 mt-1 text-[10px]">
            <span>スコア: {hoveredAd.score}pt</span>
            <span>Views: {(hoveredAd.cumulative_views / 1000).toFixed(0)}K</span>
          </div>
          <p className="text-[9px] text-gray-400 mt-0.5">
            {hoveredAd.first_seen} ~ {hoveredAd.last_seen}
            {hoveredAd.is_active && " (配信中)"}
          </p>
        </div>
      )}
    </div>
  );
}
