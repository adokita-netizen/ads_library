"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { fetchApi } from "@/lib/api";
import { cachedFetchApi } from "@/lib/prefetch";
import { platformLabels } from "@/lib/constants";
import { formatNumber } from "@/lib/format";
import TrendSparkline from "./TrendSparkline";
import { useColumnSettings, type ColumnDef } from "@/lib/useColumnSettings";
import { useDebounce } from "@/lib/useDebounce";
import { useLoadTimer } from "@/lib/useLoadTimer";

// ─── Column definitions for column toggle ───
const TABLE_COLUMNS: ColumnDef[] = [
  { key: "rank", label: "順位", required: true },
  { key: "thumbnail", label: "サムネイル" },
  { key: "title", label: "タイトル", required: true },
  { key: "advertiser_name", label: "広告主" },
  { key: "fine_genre", label: "ジャンル" },
  { key: "hit_score", label: "スコア" },
  { key: "cumulative_views", label: "再生回数" },
  { key: "duration_seconds", label: "尺" },
];

// ─── Types ───

export interface ProRankingItem {
  rank: number;
  previous_rank?: number;
  rank_change?: number;
  ad_id: number;
  title?: string;
  product_name?: string;
  description?: string;
  advertiser_name?: string;
  genre?: string;
  fine_genre?: string;
  platform?: string;
  view_increase: number;
  spend_increase: number;
  cumulative_views: number;
  cumulative_spend: number;
  view_count?: number;
  like_increase: number;
  like_count?: number;
  is_hit: boolean;
  is_above_hit_line?: boolean;
  hit_score?: number;
  trend_score?: number;
  thumbnail?: string;
  thumbnail_url?: string;
  image_url?: string;
  snapshot_url?: string;
  duration_seconds?: number;
  destination_url?: string;
  creative_type?: string;
  days_running?: number;
  is_still_running?: boolean;
  hit_level?: string;
  video_url?: string;
  first_seen_date?: string;
  last_seen_date?: string;
}

interface ProRankingTableProps {
  genre?: string;
  fineGenre?: string;
  platform?: string;
  searchQuery?: string;
  sortBy?: string;
  period?: string;
  onAdSelect: (adId: number) => void;
  hitLineThreshold?: number;
  viewMode?: "table" | "card" | "gallery";
}

// ─── Sort types ───

type SortField =
  | "rank"
  | "title"
  | "advertiser_name"
  | "fine_genre"
  | "hit_score"
  | "cumulative_views"
  | "duration_seconds";
type SortDirection = "asc" | "desc";

// ─── Genre color mapping ───

const genreColorMap: Record<string, { bg: string; text: string; border: string }> = {
  "美容・コスメ": { bg: "bg-pink-50", text: "text-pink-700", border: "border-pink-200" },
  "健康食品": { bg: "bg-green-50", text: "text-green-700", border: "border-green-200" },
  "EC・D2C": { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200" },
  "金融": { bg: "bg-yellow-50", text: "text-yellow-700", border: "border-yellow-200" },
  "教育": { bg: "bg-indigo-50", text: "text-indigo-700", border: "border-indigo-200" },
  "食品": { bg: "bg-orange-50", text: "text-orange-700", border: "border-orange-200" },
  "ゲーム": { bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200" },
  "テクノロジー": { bg: "bg-cyan-50", text: "text-cyan-700", border: "border-cyan-200" },
  "不動産": { bg: "bg-amber-50", text: "text-amber-700", border: "border-amber-200" },
  "旅行": { bg: "bg-teal-50", text: "text-teal-700", border: "border-teal-200" },
  "アプリ": { bg: "bg-violet-50", text: "text-violet-700", border: "border-violet-200" },
  "その他": { bg: "bg-gray-50", text: "text-gray-600", border: "border-gray-200" },
};

function getGenreColor(genre?: string) {
  if (!genre) return { bg: "bg-gray-50", text: "text-gray-500", border: "border-gray-200" };
  // Check exact match
  if (genreColorMap[genre]) return genreColorMap[genre];
  // Check partial match
  for (const [key, val] of Object.entries(genreColorMap)) {
    if (genre.includes(key) || key.includes(genre)) return val;
  }
  // Hash-based fallback color
  const colors = [
    { bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200" },
    { bg: "bg-sky-50", text: "text-sky-700", border: "border-sky-200" },
    { bg: "bg-lime-50", text: "text-lime-700", border: "border-lime-200" },
    { bg: "bg-fuchsia-50", text: "text-fuchsia-700", border: "border-fuchsia-200" },
    { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
  ];
  let hash = 0;
  for (let i = 0; i < genre.length; i++) {
    hash = genre.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

// ─── Helpers ───

function formatDuration(seconds?: number): string {
  if (!seconds || seconds <= 0) return "--";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function platformIcon(platform?: string): React.ReactNode {
  if (!platform) return null;
  const p = platform.toLowerCase();
  const label = platformLabels[p] || p.substring(0, 2).toUpperCase();

  const colorMap: Record<string, string> = {
    facebook: "bg-blue-600",
    meta: "bg-blue-600",
    instagram: "bg-gradient-to-tr from-purple-600 via-pink-500 to-orange-400",
    tiktok: "bg-gray-900",
    youtube: "bg-red-600",
    shorts: "bg-red-500",
    x_twitter: "bg-gray-800",
    x: "bg-gray-800",
    line: "bg-green-500",
  };

  const bg = colorMap[p] || "bg-gray-500";

  return (
    <span
      className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-white text-[9px] font-bold ${bg}`}
      title={platform}
    >
      {label.charAt(0)}
    </span>
  );
}

// Sort indicator arrow
function SortArrow({ direction, active }: { direction: SortDirection; active: boolean }) {
  return (
    <span className={`inline-flex flex-col ml-1 ${active ? "opacity-100" : "opacity-0 group-hover:opacity-40"}`}>
      <svg
        className={`w-2.5 h-2.5 ${active && direction === "asc" ? "text-[#4A7DFF]" : "text-gray-400"}`}
        viewBox="0 0 10 6"
        fill="currentColor"
      >
        <path d="M5 0L10 6H0L5 0Z" />
      </svg>
      <svg
        className={`w-2.5 h-2.5 -mt-0.5 ${active && direction === "desc" ? "text-[#4A7DFF]" : "text-gray-400"}`}
        viewBox="0 0 10 6"
        fill="currentColor"
      >
        <path d="M5 6L0 0H10L5 6Z" />
      </svg>
    </span>
  );
}

// ─── Page size options ───
const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;

// ─── Component ───

export default function ProRankingTable({
  genre,
  fineGenre,
  platform,
  searchQuery,
  sortBy = "cumulative_views",
  period = "7d",
  onAdSelect,
  hitLineThreshold,
  viewMode = "table",
}: ProRankingTableProps) {
  // Auto-switch to card view on mobile (<768px)
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 767px)");
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  const effectiveViewMode = isMobile && viewMode === "table" ? "card" : viewMode;

  const [items, setItems] = useState<ProRankingItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState<number>(50);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { formatted: loadTime } = useLoadTimer(loading);

  // Column visibility (persisted to localStorage)
  const { visibleColumns, toggleColumn, resetColumns } = useColumnSettings("pro_ranking_columns", TABLE_COLUMNS);
  const [showColumnMenu, setShowColumnMenu] = useState(false);

  // Genre filter chips from API
  const [fineGenres, setFineGenres] = useState<string[]>([]);
  const [selectedGenreChip, setSelectedGenreChip] = useState<string | null>(null);

  // Score range slider
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100]);

  // Local text search (title/advertiser) with debounce for API calls
  const [localSearch, setLocalSearch] = useState("");
  const debouncedSearch = useDebounce(localSearch);

  // Column header sort
  const [sortField, setSortField] = useState<SortField>("rank");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  // Hit line
  const [hitLine, setHitLine] = useState<number>(0);

  // Fetch data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined> = {
        page,
        page_size: perPage,
        per_page: perPage,
        sort_by: sortBy,
        period,
      };
      if (genre && genre !== "all") params.genre = genre;
      if (fineGenre) params.fine_genre = fineGenre;
      if (selectedGenreChip) params.fine_genre = selectedGenreChip;
      if (platform && platform !== "all") params.platform = platform;
      if (searchQuery) params.q = searchQuery;
      if (debouncedSearch.trim()) params.q = debouncedSearch.trim();
      if (scoreRange[0] > 0) params.min_score = scoreRange[0];
      if (scoreRange[1] < 100) params.max_score = scoreRange[1];

      const data = await cachedFetchApi<{
        items?: ProRankingItem[];
        ads?: ProRankingItem[];
        total: number;
        page?: number;
        per_page?: number;
        total_pages?: number;
        hit_line?: number;
        hit_line_threshold?: number;
        fine_genres?: string[];
      }>("/rankings/pro-ranking", { params });

      const resultItems = data.ads || data.items || [];
      setItems(resultItems);
      setTotal(data.total || 0);
      if (data.hit_line) setHitLine(data.hit_line);
      if (data.hit_line_threshold) setHitLine(data.hit_line_threshold);
      if (data.fine_genres && data.fine_genres.length > 0) {
        setFineGenres(data.fine_genres);
      }
    } catch {
      // Fallback: try existing hit-ads endpoint
      try {
        const params: Record<string, string | number | undefined> = {
          limit: perPage,
        };
        if (genre && genre !== "all") params.genre = genre;
        const fallback = await fetchApi<{
          items: ProRankingItem[];
          total: number;
        }>("/rankings/hit-ads", { params });
        setItems(
          (fallback.items || []).map((item, idx) => ({
            ...item,
            rank: item.rank || idx + 1,
            view_increase: item.view_increase || 0,
            spend_increase: item.spend_increase || 0,
            cumulative_views: item.cumulative_views || 0,
            cumulative_spend: item.cumulative_spend || 0,
            like_increase:
              item.like_increase ??
              (item.like_count ?? 0),
          }))
        );
        setTotal(fallback.total || 0);
      } catch {
        setError("ランキングデータの取得に失敗しました");
      }
    } finally {
      setLoading(false);
    }
  }, [genre, fineGenre, platform, searchQuery, sortBy, period, page, perPage, selectedGenreChip, debouncedSearch, scoreRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [genre, fineGenre, platform, searchQuery, sortBy, period, perPage, selectedGenreChip, debouncedSearch, scoreRange]);

  const effectiveHitLine = hitLineThreshold || hitLine || 10000;
  const totalPages = Math.ceil(total / perPage);

  // ─── Client-side filtering + sorting ───

  const filteredAndSortedItems = useMemo(() => {
    let result = [...items];

    // Genre chip filter
    if (selectedGenreChip) {
      result = result.filter(
        (item) =>
          (item.fine_genre || item.genre || "") === selectedGenreChip
      );
    }

    // Score range filter
    result = result.filter((item) => {
      const score = item.hit_score ?? 0;
      return score >= scoreRange[0] && score <= scoreRange[1];
    });

    // Local text search
    if (localSearch.trim()) {
      const q = localSearch.trim().toLowerCase();
      result = result.filter(
        (item) =>
          (item.title || item.product_name || "").toLowerCase().includes(q) ||
          (item.advertiser_name || "").toLowerCase().includes(q)
      );
    }

    // Column sort
    result.sort((a, b) => {
      let valA: string | number = 0;
      let valB: string | number = 0;

      switch (sortField) {
        case "rank":
          valA = a.rank;
          valB = b.rank;
          break;
        case "title":
          valA = (a.title || a.product_name || "").toLowerCase();
          valB = (b.title || b.product_name || "").toLowerCase();
          break;
        case "advertiser_name":
          valA = (a.advertiser_name || "").toLowerCase();
          valB = (b.advertiser_name || "").toLowerCase();
          break;
        case "fine_genre":
          valA = (a.fine_genre || a.genre || "").toLowerCase();
          valB = (b.fine_genre || b.genre || "").toLowerCase();
          break;
        case "hit_score":
          valA = a.hit_score ?? 0;
          valB = b.hit_score ?? 0;
          break;
        case "cumulative_views":
          valA = a.cumulative_views || a.view_count || 0;
          valB = b.cumulative_views || b.view_count || 0;
          break;
        case "duration_seconds":
          valA = a.duration_seconds ?? 0;
          valB = b.duration_seconds ?? 0;
          break;
      }

      if (typeof valA === "string" && typeof valB === "string") {
        const cmp = valA.localeCompare(valB);
        return sortDirection === "asc" ? cmp : -cmp;
      }
      const diff = (valA as number) - (valB as number);
      return sortDirection === "asc" ? diff : -diff;
    });

    return result;
  }, [items, selectedGenreChip, scoreRange, localSearch, sortField, sortDirection]);

  // Toggle column sort
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection(field === "rank" ? "asc" : "desc");
    }
  };

  // Sortable header component
  const SortableHeader = ({
    field,
    label,
    className = "",
    align = "left",
  }: {
    field: SortField;
    label: string;
    className?: string;
    align?: "left" | "right" | "center";
  }) => (
    <th
      scope="col"
      aria-sort={sortField === field ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
      className={`px-3 py-2.5 text-${align} text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap cursor-pointer select-none group hover:text-gray-700 transition-colors ${className}`}
      onClick={() => handleSort(field)}
    >
      <span className={`inline-flex items-center ${align === "right" ? "justify-end" : ""}`}>
        {label}
        <SortArrow direction={sortDirection} active={sortField === field} />
      </span>
    </th>
  );

  // ─── Loading skeleton ───
  if (loading && items.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                {["順位", "サムネイル", "タイトル", "広告主", "ジャンル", "スコア", "再生回数", "尺"].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-3 py-2.5 text-left text-[11px] font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap"
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 10 }).map((_, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="px-3 py-3">
                    <div className="h-4 w-6 bg-gray-200 rounded animate-pulse" />
                  </td>
                  <td className="px-3 py-3">
                    <div className="h-12 w-20 bg-gray-200 rounded animate-pulse" />
                  </td>
                  <td className="px-3 py-3">
                    <div className="h-4 w-32 bg-gray-200 rounded animate-pulse mb-1" />
                    <div className="h-3 w-20 bg-gray-100 rounded animate-pulse" />
                  </td>
                  <td className="px-3 py-3">
                    <div className="h-4 w-20 bg-gray-200 rounded animate-pulse" />
                  </td>
                  <td className="px-3 py-3">
                    <div className="h-5 w-16 bg-gray-200 rounded-full animate-pulse" />
                  </td>
                  {Array.from({ length: 3 }).map((_, j) => (
                    <td key={j} className="px-3 py-3">
                      <div className="h-4 w-16 bg-gray-200 rounded animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // ─── Error state ───
  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
        <svg
          className="w-10 h-10 mx-auto text-gray-300 mb-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
          />
        </svg>
        <p className="text-[13px] text-gray-500 mb-3">{error}</p>
        <button
          onClick={fetchData}
          className="text-[12px] font-medium text-[#4A7DFF] hover:underline"
        >
          再試行
        </button>
      </div>
    );
  }

  // ─── Empty state ───
  if (!loading && items.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
        <svg
          className="w-10 h-10 mx-auto text-gray-300 mb-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
          />
        </svg>
        <p className="text-[13px] text-gray-500">
          該当するデータが見つかりませんでした
        </p>
        <p className="text-[11px] text-gray-400 mt-1">
          フィルター条件を変更してお試しください
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* ─── Filter bar: genre chips + score slider + text search ─── */}
      <div className="px-4 py-3 border-b border-gray-100 space-y-3">
        {/* Text search */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <svg
              className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
              />
            </svg>
            <input
              type="text"
              placeholder="タイトル・広告主で絞り込み..."
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-[12px] border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/40 focus:border-[#4A7DFF] bg-gray-50 placeholder-gray-400"
            />
            {localSearch && (
              <button
                onClick={() => setLocalSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Score range slider */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-gray-500 whitespace-nowrap">スコア範囲:</span>
            <div className="flex items-center gap-1.5">
              <input
                type="range"
                min={0}
                max={100}
                value={scoreRange[0]}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setScoreRange(([, max]) => [Math.min(v, max), max]);
                }}
                className="w-16 h-1 accent-[#4A7DFF]"
              />
              <span className="text-[10px] text-gray-500 tabular-nums w-8 text-center">
                {scoreRange[0]}
              </span>
              <span className="text-[10px] text-gray-400">-</span>
              <input
                type="range"
                min={0}
                max={100}
                value={scoreRange[1]}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setScoreRange(([min]) => [min, Math.max(v, min)]);
                }}
                className="w-16 h-1 accent-[#4A7DFF]"
              />
              <span className="text-[10px] text-gray-500 tabular-nums w-8 text-center">
                {scoreRange[1]}
              </span>
            </div>
            {(scoreRange[0] > 0 || scoreRange[1] < 100) && (
              <button
                onClick={() => setScoreRange([0, 100])}
                className="text-[10px] text-gray-400 hover:text-gray-600"
                title="リセット"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Column toggle */}
          <div className="relative ml-auto">
            <button
              onClick={() => setShowColumnMenu(!showColumnMenu)}
              className="flex items-center gap-1 px-2 py-1 text-[11px] text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              title="表示カラムを設定"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
              </svg>
              カラム
            </button>
            {showColumnMenu && (
              <div className="absolute right-0 top-full mt-1 z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 w-40">
                {TABLE_COLUMNS.map((col) => (
                  <label
                    key={col.key}
                    className={`flex items-center gap-2 px-3 py-1.5 text-[11px] cursor-pointer hover:bg-gray-50 ${col.required ? "text-gray-400" : "text-gray-700"}`}
                  >
                    <input
                      type="checkbox"
                      checked={visibleColumns.has(col.key)}
                      onChange={() => toggleColumn(col.key)}
                      disabled={col.required}
                      className="w-3.5 h-3.5 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]/30"
                    />
                    {col.label}
                    {col.required && <span className="text-[9px] text-gray-400 ml-auto">固定</span>}
                  </label>
                ))}
                <div className="border-t border-gray-100 mt-1 pt-1">
                  <button
                    onClick={resetColumns}
                    className="w-full text-left px-3 py-1.5 text-[11px] text-gray-500 hover:text-[#4A7DFF] hover:bg-gray-50"
                  >
                    デフォルトに戻す
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Genre filter chips */}
        {fineGenres.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] text-gray-500 mr-1">ジャンル:</span>
            <button
              onClick={() => setSelectedGenreChip(null)}
              className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors border ${
                selectedGenreChip === null
                  ? "bg-[#4A7DFF] text-white border-[#4A7DFF]"
                  : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
              }`}
            >
              すべて
            </button>
            {fineGenres.map((g) => {
              const color = getGenreColor(g);
              const isActive = selectedGenreChip === g;
              return (
                <button
                  key={g}
                  onClick={() =>
                    setSelectedGenreChip(isActive ? null : g)
                  }
                  className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors border ${
                    isActive
                      ? `${color.bg} ${color.text} ${color.border} ring-1 ring-offset-1 ring-current`
                      : `bg-white text-gray-500 border-gray-200 hover:${color.bg} hover:${color.text}`
                  }`}
                >
                  {g}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Hit line indicator banner */}
      {hitLineThreshold && hitLineThreshold > 0 && (
        <div className="flex items-center gap-2 px-4 py-1.5 bg-amber-50 border-b border-amber-100 text-[11px] text-amber-700">
          <svg className="w-3.5 h-3.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" />
          </svg>
          <span>
            ヒットライン: 累計再生 <strong>{effectiveHitLine.toLocaleString()}</strong>回以上
          </span>
        </div>
      )}

      {/* ─── Content: Table / Card / Gallery ─── */}
      {effectiveViewMode === "table" ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]" aria-label="広告ランキング">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                {visibleColumns.has("rank") && <SortableHeader field="rank" label="順位" align="center" className="w-14" />}
                {visibleColumns.has("thumbnail") && (
                  <th className="px-2 py-2.5 text-left text-[11px] font-semibold text-gray-500 w-24">
                    サムネイル
                  </th>
                )}
                {visibleColumns.has("title") && <SortableHeader field="title" label="タイトル" className="min-w-[200px]" />}
                {visibleColumns.has("advertiser_name") && <SortableHeader field="advertiser_name" label="広告主" className="w-32" />}
                {visibleColumns.has("fine_genre") && <SortableHeader field="fine_genre" label="ジャンル" className="w-28" />}
                {visibleColumns.has("hit_score") && <SortableHeader field="hit_score" label="スコア" align="right" className="w-20" />}
                {visibleColumns.has("cumulative_views") && <SortableHeader field="cumulative_views" label="再生回数" align="right" className="w-28" />}
                {visibleColumns.has("duration_seconds") && <SortableHeader field="duration_seconds" label="尺" align="right" className="w-20" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredAndSortedItems.map((item) => {
                const isAboveHitLine =
                  item.is_above_hit_line ||
                  (item.cumulative_views || 0) >= effectiveHitLine;
                const thumbnailSrc =
                  `/api/v1/media/thumbnail/${item.ad_id}`;
                const displayTitle = item.title || item.product_name || `Ad #${item.ad_id}`;
                const displayViews = item.cumulative_views || item.view_count || 0;
                const genreLabel = item.fine_genre || item.genre;
                const genreColor = getGenreColor(genreLabel);

                return (
                  <tr
                    key={item.ad_id}
                    className={`group transition-colors cursor-pointer ${
                      isAboveHitLine
                        ? "bg-amber-50/40 hover:bg-amber-50/70"
                        : "hover:bg-gray-50"
                    }`}
                    onClick={() => onAdSelect(item.ad_id)}
                  >
                    {/* Rank */}
                    {visibleColumns.has("rank") && <td className="px-2 py-2.5 text-center">
                      <div className="flex flex-col items-center gap-0.5">
                        <span
                          className={`text-[14px] font-bold ${
                            item.rank <= 3 ? "text-amber-500" : "text-gray-700"
                          }`}
                        >
                          {item.rank <= 3 ? (
                            <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-gradient-to-br from-amber-400 to-orange-400 text-white text-[13px] font-bold shadow-sm">
                              {item.rank}
                            </span>
                          ) : (
                            item.rank
                          )}
                        </span>
                        {item.rank_change !== undefined &&
                          item.rank_change !== null &&
                          item.rank_change !== 0 && (
                            <span
                              className={`text-[9px] font-semibold flex items-center gap-0.5 ${
                                item.rank_change > 0
                                  ? "text-emerald-500"
                                  : "text-red-500"
                              }`}
                            >
                              <svg className="w-2 h-2" viewBox="0 0 8 6" fill="currentColor">
                                {item.rank_change > 0 ? (
                                  <path d="M4 0L8 6H0L4 0Z" />
                                ) : (
                                  <path d="M4 6L0 0H8L4 6Z" />
                                )}
                              </svg>
                              {Math.abs(item.rank_change)}
                            </span>
                          )}
                      </div>
                    </td>}

                    {/* Thumbnail */}
                    {visibleColumns.has("thumbnail") && <td className="px-2 py-2">
                      <div className="relative w-20 h-12 rounded overflow-hidden bg-gray-100 group-hover:ring-2 group-hover:ring-[#4A7DFF]/30 transition-all">
                        <img
                          src={thumbnailSrc}
                          alt={displayTitle}
                          className="w-full h-full object-cover"
                          loading="lazy"
                          onError={(e) => {
                            const target = e.currentTarget;
                            if (item.thumbnail_url && target.src !== item.thumbnail_url) {
                              target.src = item.thumbnail_url;
                            } else if (item.thumbnail && target.src !== item.thumbnail) {
                              target.src = item.thumbnail;
                            } else if (item.image_url && target.src !== item.image_url) {
                              target.src = item.image_url;
                            } else {
                              target.style.display = "none";
                            }
                          }}
                        />
                        {/* Duration badge on thumbnail */}
                        {item.duration_seconds && item.duration_seconds > 0 && (
                          <span className="absolute bottom-0.5 left-0.5 bg-black/70 text-white text-[9px] font-medium px-1 py-0.5 rounded leading-none">
                            {formatDuration(item.duration_seconds)}
                          </span>
                        )}
                        {/* Platform icon */}
                        <span className="absolute bottom-0.5 right-0.5">
                          {platformIcon(item.platform)}
                        </span>
                      </div>
                    </td>}

                    {/* Title (max 2 lines with tooltip) */}
                    {visibleColumns.has("title") && <td className="px-3 py-2">
                      <div className="min-w-0">
                        <div className="flex items-start gap-1.5">
                          <span
                            className="text-[12px] font-semibold text-[#4A7DFF] hover:underline line-clamp-2 leading-tight"
                            title={displayTitle}
                            style={{
                              display: "-webkit-box",
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: "vertical",
                              overflow: "hidden",
                            }}
                          >
                            {displayTitle}
                          </span>
                          {isAboveHitLine && (
                            <span className="shrink-0 inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-gradient-to-r from-amber-400 to-orange-400 text-white leading-none mt-0.5">
                              <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" />
                              </svg>
                              HIT
                            </span>
                          )}
                          {item.hit_level === "mega_hit" && (
                            <span className="shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-500 text-white leading-none mt-0.5">
                              MEGA
                            </span>
                          )}
                        </div>
                      </div>
                    </td>}

                    {/* Advertiser */}
                    {visibleColumns.has("advertiser_name") && <td className="px-3 py-2">
                      <div className="flex items-center gap-1.5">
                        <svg
                          className="w-3 h-3 text-gray-300 shrink-0"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                          strokeWidth={1.5}
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z"
                          />
                        </svg>
                        <span
                          className="text-[11px] text-gray-600 truncate max-w-[120px]"
                          title={item.advertiser_name || "不明"}
                        >
                          {item.advertiser_name || "不明"}
                        </span>
                      </div>
                    </td>}

                    {/* Genre (colored badge) */}
                    {visibleColumns.has("fine_genre") && <td className="px-2 py-2">
                      {genreLabel ? (
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium border whitespace-nowrap ${genreColor.bg} ${genreColor.text} ${genreColor.border}`}
                        >
                          {genreLabel}
                        </span>
                      ) : (
                        <span className="text-[11px] text-gray-300">--</span>
                      )}
                    </td>}

                    {/* Hit Score */}
                    {visibleColumns.has("hit_score") && <td className="px-3 py-2 text-right">
                      {item.hit_score !== undefined && item.hit_score !== null ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <div className="w-10 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-300"
                              style={{
                                width: `${Math.min(item.hit_score, 100)}%`,
                                backgroundColor:
                                  item.hit_score >= 80
                                    ? "#ef4444"
                                    : item.hit_score >= 60
                                    ? "#f59e0b"
                                    : item.hit_score >= 40
                                    ? "#4A7DFF"
                                    : "#9ca3af",
                              }}
                            />
                          </div>
                          <span
                            className={`text-[12px] font-bold tabular-nums ${
                              item.hit_score >= 80
                                ? "text-red-500"
                                : item.hit_score >= 60
                                ? "text-amber-500"
                                : item.hit_score >= 40
                                ? "text-[#4A7DFF]"
                                : "text-gray-500"
                            }`}
                          >
                            {item.hit_score}
                          </span>
                        </div>
                      ) : (
                        <span className="text-[11px] text-gray-300">--</span>
                      )}
                    </td>}

                    {/* Views */}
                    {visibleColumns.has("cumulative_views") && <td className="px-3 py-2 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <TrendSparkline
                          data={[
                            Math.max(0, displayViews - (item.view_increase || 0) * 4),
                            Math.max(0, displayViews - (item.view_increase || 0) * 3),
                            Math.max(0, displayViews - (item.view_increase || 0) * 2),
                            Math.max(0, displayViews - (item.view_increase || 0)),
                            displayViews,
                          ]}
                          color={(item.view_increase || 0) > 0 ? "#22c55e" : "#9ca3af"}
                        />
                        <span className="text-[12px] font-semibold tabular-nums text-gray-900">
                          {formatNumber(displayViews)}
                        </span>
                      </div>
                      {(item.view_increase || 0) > 0 && (
                        <span className="text-[10px] text-emerald-500 font-medium">
                          +{formatNumber(item.view_increase)}
                        </span>
                      )}
                    </td>}

                    {/* Duration */}
                    {visibleColumns.has("duration_seconds") && <td className="px-3 py-2 text-right">
                      <span className="text-[12px] text-gray-600 tabular-nums">
                        {formatDuration(item.duration_seconds)}
                      </span>
                    </td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        /* ─── Card / Gallery Grid ─── */
        <div className={`p-4 grid gap-3 ${effectiveViewMode === "gallery" ? "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5" : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"}`}>
          {filteredAndSortedItems.map((item) => {
            const isAboveHitLine = item.is_above_hit_line || (item.cumulative_views || 0) >= effectiveHitLine;
            const thumbnailSrc = `/api/v1/media/thumbnail/${item.ad_id}`;
            const displayTitle = item.title || item.product_name || `Ad #${item.ad_id}`;
            const displayViews = item.cumulative_views || item.view_count || 0;
            const genreLabel = item.fine_genre || item.genre;
            const genreColor = getGenreColor(genreLabel);

            return (
              <div
                key={item.ad_id}
                onClick={() => onAdSelect(item.ad_id)}
                className={`group rounded-lg border overflow-hidden cursor-pointer transition-all hover:shadow-md ${
                  isAboveHitLine ? "border-amber-200 bg-amber-50/30" : "border-gray-200 bg-white hover:border-[#4A7DFF]/30"
                }`}
              >
                {/* Thumbnail */}
                <div className={`relative bg-gray-100 ${effectiveViewMode === "gallery" ? "aspect-video" : "h-36"}`}>
                  <img
                    src={thumbnailSrc}
                    alt={displayTitle}
                    className="w-full h-full object-cover"
                    loading="lazy"
                    onError={(e) => {
                      const target = e.currentTarget;
                      if (item.thumbnail_url && target.src !== item.thumbnail_url) target.src = item.thumbnail_url;
                      else if (item.thumbnail && target.src !== item.thumbnail) target.src = item.thumbnail;
                      else if (item.image_url && target.src !== item.image_url) target.src = item.image_url;
                      else target.style.display = "none";
                    }}
                  />
                  {/* Rank badge */}
                  <span className={`absolute top-2 left-2 inline-flex items-center justify-center w-7 h-7 rounded-full text-[12px] font-bold shadow-sm ${
                    item.rank <= 3 ? "bg-gradient-to-br from-amber-400 to-orange-400 text-white" : "bg-white/90 text-gray-700"
                  }`}>
                    {item.rank}
                  </span>
                  {/* Duration */}
                  {item.duration_seconds && item.duration_seconds > 0 && (
                    <span className="absolute bottom-1.5 left-1.5 bg-black/70 text-white text-[10px] font-medium px-1.5 py-0.5 rounded">
                      {formatDuration(item.duration_seconds)}
                    </span>
                  )}
                  {/* Platform */}
                  <span className="absolute bottom-1.5 right-1.5">{platformIcon(item.platform)}</span>
                  {/* Hit badges */}
                  <div className="absolute top-2 right-2 flex gap-1">
                    {isAboveHitLine && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-gradient-to-r from-amber-400 to-orange-400 text-white">
                        <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" />
                        </svg>
                        HIT
                      </span>
                    )}
                    {item.hit_level === "mega_hit" && (
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-red-500 text-white">MEGA</span>
                    )}
                  </div>
                </div>
                {/* Card body */}
                <div className="p-3">
                  <h3 className="text-[12px] font-semibold text-gray-900 line-clamp-2 leading-tight mb-1.5 group-hover:text-[#4A7DFF] transition-colors" title={displayTitle}>
                    {displayTitle}
                  </h3>
                  <p className="text-[11px] text-gray-500 truncate mb-2">{item.advertiser_name || "不明"}</p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {genreLabel && (
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${genreColor.bg} ${genreColor.text} ${genreColor.border}`}>
                          {genreLabel}
                        </span>
                      )}
                    </div>
                    {item.hit_score !== undefined && item.hit_score !== null && (
                      <span className={`text-[12px] font-bold tabular-nums ${
                        item.hit_score >= 80 ? "text-red-500" : item.hit_score >= 60 ? "text-amber-500" : item.hit_score >= 40 ? "text-[#4A7DFF]" : "text-gray-500"
                      }`}>
                        {item.hit_score}pt
                      </span>
                    )}
                  </div>
                  {effectiveViewMode === "card" && (
                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">
                      <span className="text-[11px] text-gray-600 font-medium tabular-nums">{formatNumber(displayViews)} 再生</span>
                      {(item.view_increase || 0) > 0 && (
                        <span className="text-[10px] text-emerald-500 font-medium">+{formatNumber(item.view_increase)}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ─── Enhanced Pagination ─── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 px-4 py-2.5 border-t border-gray-100 bg-gray-50/50">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[11px] text-gray-500">
            {total.toLocaleString()}件中{" "}
            {total > 0
              ? `${((page - 1) * perPage + 1).toLocaleString()}-${Math.min(
                  page * perPage,
                  total
                ).toLocaleString()}件`
              : "0件"}
            を表示
          </span>
          {/* Filtered count */}
          {(selectedGenreChip || localSearch || scoreRange[0] > 0 || scoreRange[1] < 100) && (
            <span className="text-[10px] text-gray-400">
              (フィルター適用: {filteredAndSortedItems.length}件)
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Page size selector (hidden on mobile) */}
          <div className="hidden sm:flex items-center gap-1.5">
            <span className="text-[11px] text-gray-500">表示件数:</span>
            <select
              value={perPage}
              onChange={(e) => setPerPage(Number(e.target.value))}
              className="text-[11px] px-2 py-1 bg-white border border-gray-200 rounded-md text-gray-600 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/30"
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}件
                </option>
              ))}
            </select>
          </div>

          {/* Page info + load time */}
          <span className="text-[11px] text-gray-500">
            {page} / {totalPages || 1} ページ
            {loadTime && <span className="ml-2 text-[10px] text-gray-400">({loadTime})</span>}
          </span>

          {/* Page navigation */}
          <div className="flex items-center gap-1">
            {/* First page */}
            <button
              onClick={() => setPage(1)}
              disabled={page === 1}
              className="px-1.5 py-1 text-[11px] font-medium rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="最初のページ"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.75 19.5l-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5" />
              </svg>
            </button>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-2.5 py-1 text-[11px] font-medium rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              前へ
            </button>
            {/* Page numbers */}
            {totalPages > 0 &&
              Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                let pageNum: number;
                if (totalPages <= 7) {
                  pageNum = i + 1;
                } else if (page <= 4) {
                  pageNum = i + 1;
                } else if (page >= totalPages - 3) {
                  pageNum = totalPages - 6 + i;
                } else {
                  pageNum = page - 3 + i;
                }
                return (
                  <button
                    key={pageNum}
                    onClick={() => setPage(pageNum)}
                    className={`w-7 h-7 text-[11px] font-medium rounded transition-colors ${
                      page === pageNum
                        ? "bg-[#4A7DFF] text-white"
                        : "text-gray-600 hover:bg-gray-100"
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages || totalPages === 0}
              className="px-2.5 py-1 text-[11px] font-medium rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              次へ
            </button>
            {/* Last page */}
            <button
              onClick={() => setPage(totalPages)}
              disabled={page === totalPages || totalPages === 0}
              className="px-1.5 py-1 text-[11px] font-medium rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="最後のページ"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 4.5l7.5 7.5-7.5 7.5m6-15l7.5 7.5-7.5 7.5" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Loading overlay when paginating */}
      {loading && items.length > 0 && (
        <div className="absolute inset-0 bg-white/50 flex items-center justify-center">
          <svg
            className="w-6 h-6 animate-spin text-[#4A7DFF]"
            viewBox="0 0 24 24"
            fill="none"
          >
            <circle
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="3"
              className="opacity-25"
            />
            <path
              fill="currentColor"
              className="opacity-75"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        </div>
      )}
    </div>
  );
}
