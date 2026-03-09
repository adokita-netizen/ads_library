"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { fetchApi } from "@/lib/api";
import { cachedFetchApi } from "@/lib/prefetch";
import { platformLabels } from "@/lib/constants";
import { DEMO_RANKINGS, isDemoMode, type DemoAdItem } from "@/lib/demoData";
import { formatNumber } from "@/lib/format";
import TrendSparkline from "./TrendSparkline";
import { useColumnSettings, type ColumnDef } from "@/lib/useColumnSettings";
import { useDebounce } from "@/lib/useDebounce";
import { useLoadTimer } from "@/lib/useLoadTimer";
import { useSearchUxSettings } from "@/lib/useSearchUxSettings";
import { commitUrlSearchParams } from "@/lib/useUrlParam";
import { deriveLanguageStatus, LanguageStatusBadges, LanguageStatusWarning } from "../common/LanguageStatus";
import { deriveBedrockStatus, ProvenanceBadge, PriorityBadge, ConfidenceBandBadge, ReviewRequiredBadge } from "../common/BedrockStatus";
import SearchUxSettingsPanel from "../common/SearchUxSettingsPanel";
import SearchFallbackChips, { type SearchFallbackSuggestion } from "../common/SearchFallbackChips";

const getThumbnailCandidates = (item: ProRankingItem): string[] =>
  [
    `/api/v1/media/thumbnail/${item.ad_id}`,
    item.thumbnail_url,
    item.thumbnail,
    item.image_url,
    item.snapshot_url,
  ].filter((value): value is string => Boolean(value));

// ─── Column definitions for column toggle ───
const TABLE_COLUMNS: ColumnDef[] = [
  { key: "rank", label: "順位", required: true },
  { key: "thumbnail", label: "サムネイル" },
  { key: "title", label: "タイトル", required: true },
  { key: "advertiser_name", label: "広告主" },
  { key: "fine_genre", label: "ジャンル" },
  { key: "hit_score", label: "スコア" },
  { key: "comparison", label: "比較基準" },
  { key: "ai_product", label: "AI商材" },
  { key: "priority", label: "priority" },
  { key: "review_required", label: "review_required" },
  { key: "cumulative_views", label: "再生回数" },
  { key: "estimated_spend_increase_jpy", label: "予想消化増加額" },
  { key: "duration_seconds", label: "尺" },
];

const CONDENSED_HIDDEN_COLUMNS = new Set([
  "comparison",
  "ai_product",
  "priority",
  "review_required",
  "duration_seconds",
  "fine_genre",
]);

const CONDENSED_ENTER_OVERFLOW_PX = 160;
const CONDENSED_EXIT_OVERFLOW_PX = 48;

const STICKY_LEFT_OFFSETS: Record<string, number> = {
  rank: 0,
  thumbnail: 56,
  title: 216,
};

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
  ad_format?: string;
  transition_type?: string;
  is_affiliate?: boolean | null;
  comparison?: {
    current_date?: string;
    previous_date?: string | null;
    period_days?: number | null;
  };
  estimated_spend_increase_jpy?: number;
  cpm_jpy?: number;
  cpm_source?: string;
  cpm_confidence?: number;
  days_running?: number;
  is_still_running?: boolean;
  hit_level?: string;
  video_url?: string;
  first_seen_date?: string;
  last_seen_date?: string;
  topic_label?: string;
  topic_confidence?: number;
  matched_field?: string;
  matched_terms?: string[];
  needs_topic_review?: boolean;
  needs_media_retry?: boolean;
  extract_quality_score?: number;
  language?: string;
  language_source?: string;
  exclude_from_analysis?: boolean;
  exclude_reason?: string;
  jp_char_ratio?: number;
  ad_metadata?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  review_required?: boolean;
  review_reason?: string;
  topic_provenance?: string;
  classification_provenance?: string;
  topic_source?: string;
  classification_source?: string;
  priority?: string;
  priority_level?: string;
  priority_score?: number;
  actual_metrics_priority?: string;
  actual_metrics_priority_score?: number;
}

interface ProRankingTableProps {
  genre?: string;
  fineGenre?: string;
  platform?: string;
  searchQuery?: string;
  sortBy?: string;
  period?: string;
  snapshotDate?: string;
  topic?: string;
  transitionType?: string;
  adFormat?: "all" | "video" | "banner" | "carousel";
  isAffiliate?: "all" | "true" | "false";
  advancedFilters?: {
    videoFormat: "all" | "video" | "image" | "carousel";
    excludedAdvertisers: string[];
    excludedDomains: string[];
    dateRange: { from: string | null; to: string | null };
    viewCountMin: number | null;
    viewCountMax: number | null;
    likeCountMin: number | null;
    likeCountMax: number | null;
    destinationType: string | null;
    destinationDomain: string | null;
    spendMin: number | null;
    spendMax: number | null;
  };
  initialTableState?: {
    column_filters?: {
      local_search?: string;
    };
    column_sort?: {
      field?: string;
      direction?: "asc" | "desc";
    };
  };
  onTableStateChange?: (state: {
    column_filters: { local_search: string };
    column_sort: { field: string; direction: "asc" | "desc" };
  }) => void;
  onAdSelect: (adId: number) => void;
  hitLineThreshold?: number;
  viewMode?: "table" | "card" | "gallery";
  scoreRangePreset?: [number, number];
  refreshNonce?: number;
  onSummaryChange?: (summary: { total: number; updatedAt: string }) => void;
  jpOnly?: boolean;
  priorityFilter?: "all" | "high" | "medium" | "low";
  reviewRequiredOnly?: boolean;
  actualMetricsFocus?: boolean;
}

// ─── Sort types ───

type SortField =
  | "rank"
  | "title"
  | "advertiser_name"
  | "fine_genre"
  | "hit_score"
  | "ai_product"
  | "priority"
  | "review_required"
  | "cumulative_views"
  | "estimated_spend_increase_jpy"
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
  "その他": { bg: "bg-gray-50 dark:bg-gray-800", text: "text-gray-600 dark:text-gray-300", border: "border-gray-200 dark:border-gray-700" },
};

function getGenreColor(genre?: string) {
  if (!genre) return { bg: "bg-gray-50 dark:bg-gray-800", text: "text-gray-500 dark:text-gray-400 dark:text-gray-500", border: "border-gray-200 dark:border-gray-700" };
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

function transitionTypeLabel(v?: string): string {
  const key = (v || "").toLowerCase();
  if (key === "article_lp") return "記事LP";
  if (key === "survey_lp") return "アンケートLP";
  if (key === "manga_lp") return "漫画記事LP";
  if (!key || key === "other") return "その他";
  return "その他";
}

function cpmSourceLabel(v?: string): string {
  const key = (v || "").toLowerCase();
  if (key === "metadata_estimated_cpm") return "算出済みCPM";
  if (key === "platform_observed_cpm") return "媒体観測CPM";
  if (key === "platform_season_category_model") return "推定モデルCPM";
  return "推定CPM";
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

  const bg = colorMap[p] || "bg-gray-50 dark:bg-gray-8000";

  return (
    <span
      className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-white text-[9px] font-bold ${bg}`}
      title={platform}
    >
      {label.charAt(0)}
    </span>
  );
}

function mapDemoItemToRanking(item: DemoAdItem): ProRankingItem {
  return {
    rank: item.rank,
    ad_id: item.ad_id,
    title: item.product_name,
    product_name: item.product_name,
    advertiser_name: item.advertiser_name,
    genre: item.genre,
    fine_genre: item.genre,
    platform: item.platform,
    hit_score: item.hit_score,
    trend_score: item.trend_score,
    cumulative_views: item.cumulative_views,
    cumulative_spend: item.cumulative_spend,
    estimated_spend_increase_jpy: item.cumulative_spend,
    view_increase: Math.round(item.cumulative_views * 0.12),
    spend_increase: Math.round(item.cumulative_spend * 0.1),
    like_increase: Math.round(item.cumulative_views * 0.02),
    is_hit: item.hit_score >= 70,
    is_above_hit_line: item.hit_score >= 70,
    days_running: item.days_running,
    is_still_running: item.is_still_running,
    creative_type: item.creative_type,
  };
}

// Sort indicator arrow
function SortArrow({ direction, active }: { direction: SortDirection; active: boolean }) {
  return (
    <span className={`inline-flex flex-col ml-1 ${active ? "opacity-100" : "opacity-0 group-hover:opacity-40"}`}>
      <svg
        className={`w-2.5 h-2.5 ${active && direction === "asc" ? "text-[#4A7DFF]" : "text-gray-400 dark:text-gray-500"}`}
        viewBox="0 0 10 6"
        fill="currentColor"
      >
        <path d="M5 0L10 6H0L5 0Z" />
      </svg>
      <svg
        className={`w-2.5 h-2.5 -mt-0.5 ${active && direction === "desc" ? "text-[#4A7DFF]" : "text-gray-400 dark:text-gray-500"}`}
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
const TABLE_VIRTUAL_THRESHOLD = 80;
const TABLE_VIRTUAL_ROW_HEIGHT = 66;
const TABLE_VIRTUAL_VIEWPORT_HEIGHT = 560;
const TABLE_VIRTUAL_OVERSCAN = 8;

// ─── Component ───

export default function ProRankingTable({
  genre,
  fineGenre,
  platform,
  searchQuery,
  sortBy = "cumulative_views",
  period = "7d",
  snapshotDate,
  topic,
  transitionType = "all",
  adFormat = "all",
  isAffiliate = "all",
  advancedFilters,
  initialTableState,
  onTableStateChange,
  onAdSelect,
  hitLineThreshold,
  viewMode = "table",
  scoreRangePreset,
  refreshNonce,
  onSummaryChange,
  jpOnly = false,
  priorityFilter = "all",
  reviewRequiredOnly = false,
  actualMetricsFocus = false,
}: ProRankingTableProps) {
  const readUrlState = useCallback(() => {
    if (typeof window === "undefined") {
      return {
        page: 1,
        sortField: ((initialTableState?.column_sort?.field as SortField) || "rank") as SortField,
        sortDirection: ((initialTableState?.column_sort?.direction as SortDirection) || "asc") as SortDirection,
      };
    }
    const params = new URLSearchParams(window.location.search);
    const pageValue = Math.max(1, Number(params.get("page") || "1") || 1);
    const rawSortField = (params.get("table_sort") || initialTableState?.column_sort?.field || "rank") as SortField;
    const sortFieldValue = ([
      "rank",
      "title",
      "advertiser_name",
      "fine_genre",
      "hit_score",
      "ai_product",
      "priority",
      "review_required",
      "cumulative_views",
      "estimated_spend_increase_jpy",
      "duration_seconds",
    ] as SortField[]).includes(rawSortField)
      ? rawSortField
      : "rank";
    const rawDirection = params.get("order");
    const sortDirectionValue: SortDirection = rawDirection === "asc" || rawDirection === "desc"
      ? rawDirection
      : ((initialTableState?.column_sort?.direction as SortDirection) || "asc");
    return { page: pageValue, sortField: sortFieldValue, sortDirection: sortDirectionValue };
  }, [initialTableState]);

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
  const [page, setPage] = useState(() => readUrlState().page);
  const [perPage, setPerPage] = useState<number>(50);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRowId, setSelectedRowId] = useState<number | null>(null);
  const [isPageTransitioning, setIsPageTransitioning] = useState(false);
  const { formatted: loadTime } = useLoadTimer(loading);
  const tableScrollRef = useRef<HTMLDivElement>(null);
  const [tableScrollTop, setTableScrollTop] = useState(0);

  // Column visibility (persisted to localStorage)
  const { visibleColumns, toggleColumn, resetColumns } = useColumnSettings("pro_ranking_columns", TABLE_COLUMNS);
  const [showColumnMenu, setShowColumnMenu] = useState(false);
  const [tableViewportWidth, setTableViewportWidth] = useState(0);
  const [tableHorizontalOverflow, setTableHorizontalOverflow] = useState(0);
  const [shouldCondenseTable, setShouldCondenseTable] = useState(false);

  // Genre filter chips from API
  const [fineGenres, setFineGenres] = useState<string[]>([]);
  const [selectedGenreChip, setSelectedGenreChip] = useState<string | null>(null);

  // Score range slider
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100]);
  useEffect(() => {
    setScoreRange(scoreRangePreset || [0, 100]);
  }, [scoreRangePreset]);

  // Local text search (title/advertiser) with debounce for API calls
  const [localSearch, setLocalSearch] = useState(initialTableState?.column_filters?.local_search || "");
  const debouncedSearch = useDebounce(localSearch);
  const [emptyStateSuggestions, setEmptyStateSuggestions] = useState<SearchFallbackSuggestion[]>([]);
  const {
    showSuggestionWeights,
    setShowSuggestionWeights,
    defaultSuggestionLimit,
    setDefaultSuggestionLimit,
    autoOpenDefaultSuggestions,
    setAutoOpenDefaultSuggestions,
    allowedSuggestionLimits,
  } = useSearchUxSettings();

  // Column header sort
  const initialUrlState = readUrlState();
  const [sortField, setSortField] = useState<SortField>(initialUrlState.sortField);
  const [sortDirection, setSortDirection] = useState<SortDirection>(initialUrlState.sortDirection);

  // Hit line
  const [hitLine, setHitLine] = useState<number>(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const node = tableScrollRef.current;
    const target = node?.parentElement ?? node;
    if (!target) return;
    let frameId = 0;

    const updateWidth = () => {
      const viewportWidth = target.clientWidth || window.innerWidth || 0;
      const overflowWidth = node ? Math.max(0, node.scrollWidth - node.clientWidth) : 0;
      setTableViewportWidth(viewportWidth);
      setTableHorizontalOverflow(overflowWidth);
      setShouldCondenseTable((prev) => {
        if (effectiveViewMode !== "table" || viewportWidth <= 0 || visibleColumns.size < 8) {
          return false;
        }
        const threshold = prev ? CONDENSED_EXIT_OVERFLOW_PX : CONDENSED_ENTER_OVERFLOW_PX;
        return overflowWidth > threshold;
      });
    };

    const scheduleUpdate = () => {
      if (frameId) window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(updateWidth);
    };

    scheduleUpdate();

    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", scheduleUpdate);
      return () => {
        if (frameId) window.cancelAnimationFrame(frameId);
        window.removeEventListener("resize", scheduleUpdate);
      };
    }

    const observer = new ResizeObserver(() => scheduleUpdate());
    observer.observe(target);
    if (node && node !== target) observer.observe(node);
    window.addEventListener("resize", scheduleUpdate);
    return () => {
      if (frameId) window.cancelAnimationFrame(frameId);
      observer.disconnect();
      window.removeEventListener("resize", scheduleUpdate);
    };
  }, [effectiveViewMode, shouldCondenseTable, visibleColumns]);

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
        refresh_nonce: refreshNonce,
      };
      if (snapshotDate) params.snapshot_date = snapshotDate;
      if (genre && genre !== "all") params.genre = genre;
      if (fineGenre) params.fine_genre = fineGenre;
      if (selectedGenreChip) params.fine_genre = selectedGenreChip;
      if (platform && platform !== "all") params.platform = platform;
      if (topic && topic !== "all") params.topic = topic;
      if (searchQuery) params.q = searchQuery;
      if (debouncedSearch.trim()) params.q = debouncedSearch.trim();
      if (scoreRange[0] > 0) params.min_score = scoreRange[0];
      if (scoreRange[1] < 100) params.max_score = scoreRange[1];
      if (adFormat !== "all") params.ad_format = adFormat;
      if (transitionType !== "all") params.transition_type = transitionType;
      if (isAffiliate !== "all") params.is_affiliate = isAffiliate;
      if (jpOnly) params.jp_only = "true";
      if (priorityFilter !== "all") params.priority_filter = priorityFilter;
      if (reviewRequiredOnly) params.review_required_only = "true";
      if (actualMetricsFocus) params.actual_metrics_focus = "true";
      if (advancedFilters) {
        if (!params.ad_format && advancedFilters.videoFormat !== "all") params.ad_format = advancedFilters.videoFormat === "image" ? "banner" : advancedFilters.videoFormat;
        if (advancedFilters.destinationType) params.destination_type = advancedFilters.destinationType;
        if (advancedFilters.destinationDomain) params.destination_domain = advancedFilters.destinationDomain;
        if (advancedFilters.viewCountMin !== null) params.view_count_min = advancedFilters.viewCountMin;
        if (advancedFilters.viewCountMax !== null) params.view_count_max = advancedFilters.viewCountMax;
        if (advancedFilters.likeCountMin !== null) params.like_count_min = advancedFilters.likeCountMin;
        if (advancedFilters.likeCountMax !== null) params.like_count_max = advancedFilters.likeCountMax;
        if (advancedFilters.spendMin !== null) params.spend_min_jpy = advancedFilters.spendMin;
        if (advancedFilters.spendMax !== null) params.spend_max_jpy = advancedFilters.spendMax;
        if (advancedFilters.excludedAdvertisers.length > 0) params.exclude_advertisers = advancedFilters.excludedAdvertisers.join(",");
        if (advancedFilters.excludedDomains.length > 0) params.exclude_domains = advancedFilters.excludedDomains.join(",");
        if (advancedFilters.dateRange.from) params.date_from = advancedFilters.dateRange.from;
        if (advancedFilters.dateRange.to) params.date_to = advancedFilters.dateRange.to;
      }

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
      const totalCount = data.total || 0;
      if (totalCount === 0 && isDemoMode()) {
        const demoItems = DEMO_RANKINGS.items.map(mapDemoItemToRanking);
        setItems(demoItems);
        setTotal(DEMO_RANKINGS.total);
        onSummaryChange?.({ total: DEMO_RANKINGS.total, updatedAt: new Date().toISOString() });
      } else {
        setItems(resultItems);
        setTotal(totalCount);
        onSummaryChange?.({ total: totalCount, updatedAt: new Date().toISOString() });
      }
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
        const totalCount = fallback.total || 0;
        setTotal(totalCount);
        onSummaryChange?.({ total: totalCount, updatedAt: new Date().toISOString() });
      } catch {
        if (isDemoMode()) {
          const demoItems = DEMO_RANKINGS.items.map(mapDemoItemToRanking);
          setItems(demoItems);
          setTotal(DEMO_RANKINGS.total);
          onSummaryChange?.({ total: DEMO_RANKINGS.total, updatedAt: new Date().toISOString() });
        } else {
          setError("ランキングデータの取得に失敗しました");
        }
      }
    } finally {
      setLoading(false);
    }
  }, [genre, fineGenre, platform, topic, searchQuery, sortBy, period, snapshotDate, transitionType, adFormat, isAffiliate, page, perPage, selectedGenreChip, debouncedSearch, scoreRange, advancedFilters, refreshNonce, onSummaryChange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (!loading) setIsPageTransitioning(false);
  }, [loading]);

  useEffect(() => {
    if (!initialTableState) return;
    if (initialTableState.column_filters?.local_search !== undefined) {
      setLocalSearch(initialTableState.column_filters.local_search || "");
    }
  }, [initialTableState]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (page <= 1) params.delete("page");
    else params.set("page", String(page));
    if (sortField === "rank") params.delete("table_sort");
    else params.set("table_sort", sortField);
    if (sortDirection === "asc") params.delete("order");
    else params.set("order", sortDirection);
    commitUrlSearchParams(params, "push");
  }, [page, sortField, sortDirection]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onPopState = () => {
      const next = readUrlState();
      setPage(next.page);
      setSortField(next.sortField);
      setSortDirection(next.sortDirection);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [readUrlState]);

  useEffect(() => {
    if (!onTableStateChange) return;
    onTableStateChange({
      column_filters: { local_search: localSearch },
      column_sort: { field: sortField, direction: sortDirection },
    });
  }, [localSearch, sortField, sortDirection, onTableStateChange]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [genre, fineGenre, platform, topic, searchQuery, sortBy, period, snapshotDate, transitionType, adFormat, isAffiliate, perPage, selectedGenreChip, debouncedSearch, scoreRange, advancedFilters]);

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

    if (jpOnly) {
      result = result.filter((item) => deriveLanguageStatus(item as unknown as Record<string, unknown>).kind === "jp");
    }

    if (priorityFilter !== "all") {
      result = result.filter((item) => deriveBedrockStatus(item as unknown as Record<string, unknown>).priority === priorityFilter);
    }

    if (reviewRequiredOnly) {
      result = result.filter((item) => deriveBedrockStatus(item as unknown as Record<string, unknown>).reviewRequired);
    }

    // Column sort
    result.sort((a, b) => {
      let valA: string | number = 0;
      let valB: string | number = 0;
      const bedrockA = deriveBedrockStatus(a as unknown as Record<string, unknown>);
      const bedrockB = deriveBedrockStatus(b as unknown as Record<string, unknown>);

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
        case "ai_product":
          valA = bedrockA.aiProduct || "";
          valB = bedrockB.aiProduct || "";
          break;
        case "priority":
          valA = bedrockA.priorityScore;
          valB = bedrockB.priorityScore;
          break;
        case "review_required":
          valA = bedrockA.reviewRequired ? 1 : 0;
          valB = bedrockB.reviewRequired ? 1 : 0;
          break;
        case "cumulative_views":
          valA = a.cumulative_views || a.view_count || 0;
          valB = b.cumulative_views || b.view_count || 0;
          break;
        case "estimated_spend_increase_jpy":
          valA = a.estimated_spend_increase_jpy ?? a.spend_increase ?? 0;
          valB = b.estimated_spend_increase_jpy ?? b.spend_increase ?? 0;
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

    if (actualMetricsFocus && sortField === "rank") {
      result.sort((a, b) => {
        const bedrockA = deriveBedrockStatus(a as unknown as Record<string, unknown>);
        const bedrockB = deriveBedrockStatus(b as unknown as Record<string, unknown>);
        const scoreA = (bedrockA.priority === "high" ? 100 : bedrockA.priority === "medium" ? 50 : 0) + (bedrockA.reviewRequired ? 25 : 0);
        const scoreB = (bedrockB.priority === "high" ? 100 : bedrockB.priority === "medium" ? 50 : 0) + (bedrockB.reviewRequired ? 25 : 0);
        return scoreB - scoreA;
      });
    }

    return result;
  }, [items, selectedGenreChip, scoreRange, localSearch, sortField, sortDirection, jpOnly, priorityFilter, reviewRequiredOnly, actualMetricsFocus]);

  useEffect(() => {
    const activeQuery = (localSearch || searchQuery || "").trim();
    if (
      !activeQuery ||
      !autoOpenDefaultSuggestions ||
      loading ||
      filteredAndSortedItems.length > 0
    ) {
      setEmptyStateSuggestions([]);
      return;
    }

    let cancelled = false;
    const loadSuggestions = async () => {
      try {
        const [related, analytics] = await Promise.all([
          fetchApi<{ related_suggestions?: SearchFallbackSuggestion[] }>("/rankings/search-simple", {
            params: { q: activeQuery, page_size: defaultSuggestionLimit },
          }),
          fetchApi<{ popular_genres?: { genre: string; search_count?: number }[] }>("/rankings/search-analytics"),
        ]);

        if (cancelled) return;

        const items: SearchFallbackSuggestion[] = [];
        const seen = new Set<string>();
        (related.related_suggestions || []).forEach((item) => {
          const key = `${item.type}:${item.value}`;
          if (seen.has(key)) return;
          seen.add(key);
          items.push(item);
        });
        analytics.popular_genres?.slice(0, 4).forEach((item) => {
          const genre = item.genre?.trim();
          if (!genre) return;
          const key = `genre:${genre}`;
          if (seen.has(key)) return;
          seen.add(key);
          items.push({
            type: "genre",
            label: genre,
            value: genre,
            count: item.search_count,
          });
        });

        setEmptyStateSuggestions(items.slice(0, 8));
      } catch {
        if (!cancelled) setEmptyStateSuggestions([]);
      }
    };

    void loadSuggestions();
    return () => {
      cancelled = true;
    };
  }, [
    autoOpenDefaultSuggestions,
    defaultSuggestionLimit,
    filteredAndSortedItems.length,
    localSearch,
    searchQuery,
    loading,
  ]);

  const effectiveVisibleColumns = useMemo(() => {
    if (!shouldCondenseTable) return visibleColumns;
    const next = new Set(visibleColumns);
    CONDENSED_HIDDEN_COLUMNS.forEach((key) => next.delete(key));
    return next;
  }, [shouldCondenseTable, visibleColumns]);
  const visibleColumnCount = Math.max(effectiveVisibleColumns.size, 1);
  const getStickyColumnProps = useCallback((columnKey: string) => {
    if (!shouldCondenseTable || !(columnKey in STICKY_LEFT_OFFSETS)) {
      return { className: "", style: undefined as React.CSSProperties | undefined };
    }
    return {
      className: "sticky z-[2]",
      style: { left: `${STICKY_LEFT_OFFSETS[columnKey]}px` } as React.CSSProperties,
    };
  }, [shouldCondenseTable]);
  const shouldVirtualizeTable = effectiveViewMode === "table" && filteredAndSortedItems.length > TABLE_VIRTUAL_THRESHOLD;
  const virtualWindowRows = Math.ceil(TABLE_VIRTUAL_VIEWPORT_HEIGHT / TABLE_VIRTUAL_ROW_HEIGHT);
  const virtualStartIndex = shouldVirtualizeTable
    ? Math.max(0, Math.floor(tableScrollTop / TABLE_VIRTUAL_ROW_HEIGHT) - TABLE_VIRTUAL_OVERSCAN)
    : 0;
  const virtualEndIndex = shouldVirtualizeTable
    ? Math.min(filteredAndSortedItems.length, virtualStartIndex + virtualWindowRows + TABLE_VIRTUAL_OVERSCAN * 2)
    : filteredAndSortedItems.length;
  const tableRenderItems = shouldVirtualizeTable
    ? filteredAndSortedItems.slice(virtualStartIndex, virtualEndIndex)
    : filteredAndSortedItems;
  const tableTopSpacerHeight = shouldVirtualizeTable ? virtualStartIndex * TABLE_VIRTUAL_ROW_HEIGHT : 0;
  const tableBottomSpacerHeight = shouldVirtualizeTable
    ? Math.max(0, (filteredAndSortedItems.length - virtualEndIndex) * TABLE_VIRTUAL_ROW_HEIGHT)
    : 0;

  const handleTableScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setTableScrollTop(e.currentTarget.scrollTop);
  }, []);

  const changePage = useCallback((nextPage: number) => {
    if (isPageTransitioning || loading) return;
    setIsPageTransitioning(true);
    setPage(Math.max(1, nextPage));
  }, [isPageTransitioning, loading]);

  useEffect(() => {
    setTableScrollTop(0);
    if (tableScrollRef.current) {
      tableScrollRef.current.scrollTop = 0;
    }
  }, [page, perPage, sortField, sortDirection, selectedGenreChip, localSearch, scoreRange, items, shouldVirtualizeTable]);

  // Toggle column sort
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection(field === "rank" ? "asc" : "desc");
    }
    setPage(1);
  };

  // Sortable header component
  const SortableHeader = ({
    field,
    label,
    className = "",
    align = "left",
    style,
  }: {
    field: SortField;
    label: string;
    className?: string;
    align?: "left" | "right" | "center";
    style?: React.CSSProperties;
  }) => (
    <th
      scope="col"
      aria-sort={sortField === field ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
      className={`px-3 py-2.5 text-${align} text-[11px] font-semibold text-gray-500 dark:text-gray-400 dark:text-gray-500 uppercase tracking-wider whitespace-nowrap cursor-pointer select-none group hover:text-gray-700 dark:hover:text-gray-200 dark:text-gray-300 transition-colors ${className}`}
      style={style}
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
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                {["順位", "サムネイル", "タイトル", "広告主", "ジャンル", "スコア", "再生回数", "尺"].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-3 py-2.5 text-left text-[11px] font-semibold text-gray-500 dark:text-gray-400 dark:text-gray-500 uppercase tracking-wider whitespace-nowrap"
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
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
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
        <p className="text-[13px] text-gray-500 dark:text-gray-400 dark:text-gray-500 mb-3">{error}</p>
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
      <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
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
        <p className="text-[13px] text-gray-500 dark:text-gray-400 dark:text-gray-500">
          該当するデータが見つかりませんでした
        </p>
        <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-1">
          フィルター条件を変更してお試しください
        </p>
        <div className="mx-auto mt-4 max-w-sm rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-left">
          <SearchUxSettingsPanel
            autoOpenDefaultSuggestions={autoOpenDefaultSuggestions}
            onToggleAutoOpen={() =>
              setAutoOpenDefaultSuggestions((prev) => !prev)
            }
            showSuggestionWeights={showSuggestionWeights}
            onToggleSuggestionWeights={() =>
              setShowSuggestionWeights((prev) => !prev)
            }
            defaultSuggestionLimit={defaultSuggestionLimit}
            allowedSuggestionLimits={allowedSuggestionLimits}
            onChangeSuggestionLimit={setDefaultSuggestionLimit}
            suggestionTypeStats={[]}
            suggestionTypeWeights={{}}
          />
        </div>
        {emptyStateSuggestions.length > 0 && (
          <div className="mt-4">
            <SearchFallbackChips
              suggestions={emptyStateSuggestions}
              align="center"
              onSelect={(suggestion) => {
                if (suggestion.type === "genre") {
                  setSelectedGenreChip(suggestion.value);
                  setLocalSearch("");
                  return;
                }
                setLocalSearch(suggestion.value);
              }}
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* ─── Filter bar: genre chips + score slider + text search ─── */}
      <div className="px-4 py-3 border-b border-gray-100 space-y-3">
        {/* Text search */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <svg
              className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 dark:text-gray-500"
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
              placeholder="タイトル・広告主・個別ワードで絞り込み... 例: GLP-1 / マンジャロ / ピラティス"
              value={localSearch}
              onChange={(e) => setLocalSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-[12px] border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/40 focus:border-[#4A7DFF] bg-gray-50 dark:bg-gray-800 placeholder-gray-400"
            />
            {localSearch && (
              <button
                onClick={() => setLocalSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-200 dark:text-gray-300"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          {/* Score range slider */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-gray-500 dark:text-gray-400 dark:text-gray-500 whitespace-nowrap">スコア範囲:</span>
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
              <span className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500 tabular-nums w-8 text-center">
                {scoreRange[0]}
              </span>
              <span className="text-[10px] text-gray-400 dark:text-gray-500">-</span>
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
              <span className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500 tabular-nums w-8 text-center">
                {scoreRange[1]}
              </span>
            </div>
            {(scoreRange[0] > 0 || scoreRange[1] < 100) && (
              <button
                onClick={() => setScoreRange([0, 100])}
                className="text-[10px] text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-200 dark:text-gray-300"
                title="リセット"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          <div className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2 py-1 dark:border-gray-700 dark:bg-gray-900">
            <span className="text-[10px] font-medium text-gray-500 dark:text-gray-400">実績指標</span>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${actualMetricsFocus ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-500"}`}>
              {actualMetricsFocus ? "優先取得" : "通常"}
            </span>
          </div>

          {/* Column toggle */}
          <div className="relative ml-auto">
            {shouldCondenseTable && (
              <span className="mr-2 inline-flex items-center gap-1 rounded-full border border-[#4A7DFF]/15 bg-[#EEF2FF] px-2 py-1 text-[10px] font-semibold text-[#4A7DFF]">
                Condensed
              </span>
            )}
            <button
              onClick={() => setShowColumnMenu(!showColumnMenu)}
              className="flex items-center gap-1 px-2 py-1 text-[11px] text-gray-500 dark:text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 dark:text-gray-300 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 transition-colors"
              title="表示カラムを設定"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75" />
              </svg>
              カラム
            </button>
            {showColumnMenu && (
              <div className="absolute right-0 top-full mt-1 z-50 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1 w-40">
                {TABLE_COLUMNS.map((col) => (
                  <label
                    key={col.key}
                    className={`flex items-center gap-2 px-3 py-1.5 text-[11px] cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 ${col.required ? "text-gray-400 dark:text-gray-500" : "text-gray-700 dark:text-gray-300"}`}
                  >
                    <input
                      type="checkbox"
                      checked={visibleColumns.has(col.key)}
                      onChange={() => toggleColumn(col.key)}
                      disabled={col.required}
                      className="w-3.5 h-3.5 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]/30"
                    />
                    {col.label}
                    {col.required && <span className="text-[9px] text-gray-400 dark:text-gray-500 ml-auto">固定</span>}
                  </label>
                ))}
                <div className="border-t border-gray-100 mt-1 pt-1">
                  <button
                    onClick={resetColumns}
                    className="w-full text-left px-3 py-1.5 text-[11px] text-gray-500 dark:text-gray-400 dark:text-gray-500 hover:text-[#4A7DFF] hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800"
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
            <span className="text-[11px] text-gray-500 dark:text-gray-400 dark:text-gray-500 mr-1">ジャンル:</span>
            <button
              onClick={() => setSelectedGenreChip(null)}
              className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors border ${
                selectedGenreChip === null
                  ? "bg-[#4A7DFF] text-white border-[#4A7DFF]"
                  : "bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800"
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
                      : `bg-white dark:bg-gray-900 text-gray-500 dark:text-gray-400 dark:text-gray-500 border-gray-200 dark:border-gray-700 hover:${color.bg} hover:${color.text}`
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
        <div
          ref={tableScrollRef}
          onScroll={handleTableScroll}
          className="overflow-x-auto max-h-[calc(100vh-280px)] overflow-y-auto"
        >
          <table className="min-w-[1520px] w-max table-auto text-[12px]" aria-label="広告ランキング">
            <thead className="sticky top-0 z-10 bg-gray-50 dark:bg-gray-900 shadow-sm">
              <tr className="border-b border-gray-200 dark:border-gray-700">
                {effectiveVisibleColumns.has("rank") && (
                  <SortableHeader
                    field="rank"
                    label="順位"
                    align="center"
                    className={`w-14 bg-gray-50 dark:bg-gray-900 ${getStickyColumnProps("rank").className}`}
                    style={getStickyColumnProps("rank").style}
                  />
                )}
                {effectiveVisibleColumns.has("thumbnail") && (
                  <th
                    className={`px-2 py-2.5 text-left text-[11px] font-semibold text-gray-500 dark:text-gray-400 dark:text-gray-500 min-w-[152px] w-40 bg-gray-50 dark:bg-gray-900 ${getStickyColumnProps("thumbnail").className}`}
                    style={getStickyColumnProps("thumbnail").style}
                  >
                    サムネイル
                  </th>
                )}
                {effectiveVisibleColumns.has("title") && (
                  <SortableHeader
                    field="title"
                    label="タイトル"
                    className={`min-w-[240px] bg-gray-50 dark:bg-gray-900 ${getStickyColumnProps("title").className}`}
                    style={getStickyColumnProps("title").style}
                  />
                )}
                {effectiveVisibleColumns.has("advertiser_name") && <SortableHeader field="advertiser_name" label="広告主" className="w-32" />}
                {effectiveVisibleColumns.has("fine_genre") && <SortableHeader field="fine_genre" label="ジャンル" className="w-28" />}
                {effectiveVisibleColumns.has("hit_score") && <SortableHeader field="hit_score" label="スコア" align="right" className="w-20" />}
                {effectiveVisibleColumns.has("comparison") && (
                  <th className="px-3 py-2.5 text-left text-[11px] font-semibold text-gray-500 dark:text-gray-400 dark:text-gray-500 w-44">
                    比較基準
                  </th>
                )}
                {effectiveVisibleColumns.has("ai_product") && <SortableHeader field="ai_product" label="AI商材" className="w-32" />}
                {effectiveVisibleColumns.has("priority") && <SortableHeader field="priority" label="priority" className="w-28" />}
                {effectiveVisibleColumns.has("review_required") && <SortableHeader field="review_required" label="review_required" className="w-28" />}
                {effectiveVisibleColumns.has("cumulative_views") && <SortableHeader field="cumulative_views" label="再生回数" align="right" className="w-28" />}
                {effectiveVisibleColumns.has("estimated_spend_increase_jpy") && <SortableHeader field="estimated_spend_increase_jpy" label="予想消化増加額" align="right" className="w-32" />}
                {effectiveVisibleColumns.has("duration_seconds") && <SortableHeader field="duration_seconds" label="尺" align="right" className="w-20" />}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tableTopSpacerHeight > 0 && (
                <tr aria-hidden="true">
                  <td colSpan={visibleColumnCount} style={{ height: tableTopSpacerHeight, padding: 0, border: 0 }} />
                </tr>
              )}
              {tableRenderItems.map((item) => {
                const isAboveHitLine =
                  item.is_above_hit_line ||
                  (item.cumulative_views || 0) >= effectiveHitLine;
                const thumbnailCandidates = getThumbnailCandidates(item);
                const thumbnailSrc = thumbnailCandidates[0] || "";
                const displayTitle = item.title || item.product_name || `Ad #${item.ad_id}`;
                const displayViews = item.cumulative_views || item.view_count || 0;
                const genreLabel = item.fine_genre || item.genre;
                const genreColor = getGenreColor(genreLabel);
                const languageInfo = deriveLanguageStatus(item as unknown as Record<string, unknown>);
                const bedrockInfo = deriveBedrockStatus(item as unknown as Record<string, unknown>);
                const comparisonLabel =
                  item.comparison?.period_days && item.comparison?.current_date && item.comparison?.previous_date
                    ? `${item.comparison.period_days}日: ${item.comparison.current_date} vs ${item.comparison.previous_date}`
                    : "--";
                const estimatedSpendIncrease =
                  item.estimated_spend_increase_jpy ?? item.spend_increase ?? 0;
                const stickyCellTone =
                  selectedRowId === item.ad_id
                    ? "bg-blue-50 dark:bg-blue-900/30"
                    : isAboveHitLine
                    ? "bg-amber-50/95"
                    : "bg-white dark:bg-gray-900 group-hover:bg-gray-50 dark:group-hover:bg-gray-800";

                return (
                  <tr
                    key={item.ad_id}
                    className={`group transition-colors cursor-pointer ${
                      selectedRowId === item.ad_id
                        ? "bg-blue-50 dark:bg-blue-900/30 ring-1 ring-blue-300 dark:ring-blue-700"
                        : isAboveHitLine
                        ? "bg-amber-50/40 hover:bg-amber-50/70"
                        : "hover:bg-gray-50 dark:hover:bg-gray-800"
                    }`}
                    onClick={() => {
                      setSelectedRowId(item.ad_id);
                      onAdSelect(item.ad_id);
                    }}
                  >
                    {/* Rank */}
                    {effectiveVisibleColumns.has("rank") && <td
                      className={`px-2 py-2.5 text-center ${stickyCellTone} ${getStickyColumnProps("rank").className}`}
                      style={getStickyColumnProps("rank").style}
                    >
                      <div className="flex flex-col items-center gap-0.5">
                        <span
                          className={`text-[14px] font-bold ${
                            item.rank <= 3 ? "text-amber-500" : "text-gray-700 dark:text-gray-300"
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
                    {effectiveVisibleColumns.has("thumbnail") && <td
                      className={`px-2 py-2 ${stickyCellTone} ${getStickyColumnProps("thumbnail").className}`}
                      style={getStickyColumnProps("thumbnail").style}
                    >
                      <div className="relative w-28 h-16 rounded-lg overflow-hidden bg-gray-100 shadow-sm group-hover:ring-2 group-hover:ring-[#4A7DFF]/30 transition-all">
                        <img
                          src={thumbnailSrc}
                          alt={displayTitle}
                          className="w-full h-full object-cover"
                          loading="lazy"
                          onError={(e) => {
                            const target = e.currentTarget;
                            const currentIndex = thumbnailCandidates.findIndex((candidate) => target.src.includes(candidate));
                            const nextCandidate = thumbnailCandidates[currentIndex >= 0 ? currentIndex + 1 : 1];
                            if (nextCandidate) {
                              target.src = nextCandidate;
                              return;
                            }
                            target.style.display = "none";
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
                    {effectiveVisibleColumns.has("title") && <td
                      className={`px-3 py-2 ${stickyCellTone} ${getStickyColumnProps("title").className}`}
                      style={getStickyColumnProps("title").style}
                    >
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
                          {item.needs_media_retry && (
                            <span className="shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-100 text-rose-700 border border-rose-200 leading-none mt-0.5">
                              再抽出
                            </span>
                          )}
                        </div>
                        {(item.topic_label || item.needs_topic_review) && (
                          <div className="mt-1 flex items-center gap-1.5 flex-wrap">
                            {item.topic_label && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200 leading-none">
                                {item.topic_label}
                                {typeof item.topic_confidence === "number" && (
                                  <span className="text-indigo-500">{Math.round(item.topic_confidence * 100)}%</span>
                                )}
                              </span>
                            )}
                            {item.needs_topic_review && (
                              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-amber-50 text-amber-700 border border-amber-200 leading-none">
                                要確認
                              </span>
                            )}
                          </div>
                        )}
                        {!!item.matched_terms?.length && (
                          <div className="mt-1 flex items-center gap-1.5 flex-wrap">
                            <span className="text-[9px] text-gray-400">
                              {item.matched_field || "一致"}:
                            </span>
                            {item.matched_terms.slice(0, 2).map((term) => (
                              <span
                                key={`${item.ad_id}-${term}`}
                                className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-sky-50 text-sky-700 border border-sky-200 leading-none"
                              >
                                {term}
                              </span>
                            ))}
                          </div>
                        )}
                        <div className="mt-1.5">
                          <LanguageStatusBadges info={languageInfo} />
                        </div>
                        {languageInfo.excluded ? (
                          <div className="mt-1.5">
                            <LanguageStatusWarning info={languageInfo} />
                          </div>
                        ) : null}
                      </div>
                    </td>}

                    {/* Advertiser */}
                    {effectiveVisibleColumns.has("advertiser_name") && <td className="px-3 py-2">
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
                          className="text-[11px] text-gray-600 dark:text-gray-300 truncate max-w-[120px]"
                          title={item.advertiser_name || "不明"}
                        >
                          {item.advertiser_name || "不明"}
                        </span>
                      </div>
                    </td>}

                    {/* Genre (colored badge) */}
                    {effectiveVisibleColumns.has("fine_genre") && <td className="px-2 py-2">
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
                    {effectiveVisibleColumns.has("hit_score") && <td className="px-3 py-2 text-right">
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
                                : "text-gray-500 dark:text-gray-400 dark:text-gray-500"
                            }`}
                          >
                            {item.hit_score}
                          </span>
                        </div>
                      ) : (
                        <span className="text-[11px] text-gray-300">--</span>
                      )}
                    </td>}

                    {effectiveVisibleColumns.has("comparison") && <td className="px-3 py-2">
                      <div className="text-[11px] text-gray-700 dark:text-gray-300">{comparisonLabel}</div>
                      <div className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500">
                        遷移先: {transitionTypeLabel(item.transition_type)}
                        {item.is_affiliate === false ? " / PR" : item.is_affiliate === true ? " / アフィリ" : ""}
                      </div>
                      {item.cpm_jpy !== undefined && item.cpm_jpy !== null && (
                        <div className="text-[10px] text-gray-400 dark:text-gray-500">
                          CPM: ¥{formatNumber(Math.round(item.cpm_jpy))}
                          {item.cpm_source ? ` (${cpmSourceLabel(item.cpm_source)})` : ""}
                          {typeof item.cpm_confidence === "number" ? ` / 信頼度 ${Math.round(item.cpm_confidence * 100)}%` : ""}
                        </div>
                      )}
                    </td>}

                    {effectiveVisibleColumns.has("ai_product") && <td className="px-3 py-2">
                      <div className="space-y-1">
                        <div className="text-[11px] font-medium text-gray-800 dark:text-gray-200">{bedrockInfo.aiProduct || "未分類"}</div>
                        <div className="flex flex-wrap gap-1">
                          <ProvenanceBadge provenance={bedrockInfo.provenance} />
                          <ConfidenceBandBadge band={bedrockInfo.confidenceBand} />
                        </div>
                      </div>
                    </td>}

                    {effectiveVisibleColumns.has("priority") && <td className="px-3 py-2">
                      <div className="space-y-1">
                        <div className="flex flex-wrap gap-1">
                          <PriorityBadge priority={bedrockInfo.priority} />
                          {bedrockInfo.priorityScore > 0 ? <span className="text-[10px] text-gray-500 dark:text-gray-400">score {Math.round(bedrockInfo.priorityScore)}</span> : null}
                        </div>
                        {actualMetricsFocus && bedrockInfo.priority === "high" ? <p className="text-[10px] text-amber-700">実績指標を優先取得</p> : null}
                      </div>
                    </td>}

                    {effectiveVisibleColumns.has("review_required") && <td className="px-3 py-2">
                      <div className="space-y-1">
                        <ReviewRequiredBadge required={bedrockInfo.reviewRequired} />
                        <div className="text-[10px] text-gray-500 dark:text-gray-400">{bedrockInfo.reviewReason || "reasonなし"}</div>
                      </div>
                    </td>}

                    {/* Views */}
                    {effectiveVisibleColumns.has("cumulative_views") && <td className="px-3 py-2 text-right">
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
                        <span className="text-[12px] font-semibold tabular-nums text-gray-900 dark:text-gray-100">
                          {formatNumber(displayViews)}
                        </span>
                      </div>
                      {(item.view_increase || 0) > 0 && (
                        <span className="text-[10px] text-emerald-500 font-medium">
                          +{formatNumber(item.view_increase)}
                        </span>
                      )}
                    </td>}

                    {effectiveVisibleColumns.has("estimated_spend_increase_jpy") && <td className="px-3 py-2 text-right">
                      <div className="text-[12px] font-semibold text-gray-800">
                        ¥{formatNumber(Math.round(estimatedSpendIncrease))}
                      </div>
                      {(item.view_increase || 0) > 0 && (
                        <div className="text-[10px] text-gray-400 dark:text-gray-500">
                          再生増加 {formatNumber(item.view_increase || 0)}
                        </div>
                      )}
                    </td>}

                    {/* Duration */}
                    {effectiveVisibleColumns.has("duration_seconds") && <td className="px-3 py-2 text-right">
                      <span className="text-[12px] text-gray-600 dark:text-gray-300 tabular-nums">
                        {formatDuration(item.duration_seconds)}
                      </span>
                    </td>}
                  </tr>
                );
              })}
              {tableBottomSpacerHeight > 0 && (
                <tr aria-hidden="true">
                  <td colSpan={visibleColumnCount} style={{ height: tableBottomSpacerHeight, padding: 0, border: 0 }} />
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        /* ─── Card / Gallery Grid ─── */
        <div className={`p-4 grid gap-3 ${effectiveViewMode === "gallery" ? "grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5" : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"}`}>
          {filteredAndSortedItems.map((item) => {
            const isAboveHitLine = item.is_above_hit_line || (item.cumulative_views || 0) >= effectiveHitLine;
            const thumbnailCandidates = getThumbnailCandidates(item);
            const thumbnailSrc = thumbnailCandidates[0] || "";
            const displayTitle = item.title || item.product_name || `Ad #${item.ad_id}`;
            const displayViews = item.cumulative_views || item.view_count || 0;
            const genreLabel = item.fine_genre || item.genre;
            const genreColor = getGenreColor(genreLabel);
            const languageInfo = deriveLanguageStatus(item as unknown as Record<string, unknown>);
            const bedrockInfo = deriveBedrockStatus(item as unknown as Record<string, unknown>);

            return (
              <div
                key={item.ad_id}
                onClick={() => onAdSelect(item.ad_id)}
                className={`group rounded-lg border overflow-hidden cursor-pointer transition-all hover:shadow-md ${
                  isAboveHitLine ? "border-amber-200 bg-amber-50/30" : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 hover:border-[#4A7DFF]/30"
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
                      const currentIndex = thumbnailCandidates.findIndex((candidate) => target.src.includes(candidate));
                      const nextCandidate = thumbnailCandidates[currentIndex >= 0 ? currentIndex + 1 : 1];
                      if (nextCandidate) {
                        target.src = nextCandidate;
                        return;
                      }
                      target.style.display = "none";
                    }}
                  />
                  {/* Rank badge */}
                  <span className={`absolute top-2 left-2 inline-flex items-center justify-center w-7 h-7 rounded-full text-[12px] font-bold shadow-sm ${
                    item.rank <= 3 ? "bg-gradient-to-br from-amber-400 to-orange-400 text-white" : "bg-white dark:bg-gray-900/90 text-gray-700 dark:text-gray-300"
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
                    {item.needs_media_retry && (
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-100 text-rose-700 border border-rose-200">再抽出</span>
                    )}
                  </div>
                </div>
                {/* Card body */}
                <div className="p-3">
                  <h3 className="text-[12px] font-semibold text-gray-900 dark:text-gray-100 line-clamp-2 leading-tight mb-1.5 group-hover:text-[#4A7DFF] transition-colors" title={displayTitle}>
                    {displayTitle}
                  </h3>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400 dark:text-gray-500 truncate mb-2">{item.advertiser_name || "不明"}</p>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500 mb-2">
                    {transitionTypeLabel(item.transition_type)}
                    {item.is_affiliate === false ? " / PR" : item.is_affiliate === true ? " / アフィリ" : ""}
                  </p>
                  {(item.topic_label || item.needs_topic_review) && (
                    <div className="mb-2 flex items-center gap-1.5 flex-wrap">
                      {item.topic_label && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200 leading-none">
                          {item.topic_label}
                          {typeof item.topic_confidence === "number" && (
                            <span className="text-indigo-500">{Math.round(item.topic_confidence * 100)}%</span>
                          )}
                        </span>
                      )}
                      {item.needs_topic_review && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-amber-50 text-amber-700 border border-amber-200 leading-none">
                          要確認
                        </span>
                      )}
                    </div>
                  )}
                  <div className="mb-2 flex flex-wrap gap-1.5">
                    <span className="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700">
                      AI商材 {bedrockInfo.aiProduct || "未分類"}
                    </span>
                    <ProvenanceBadge provenance={bedrockInfo.provenance} />
                    <PriorityBadge priority={bedrockInfo.priority} />
                    <ReviewRequiredBadge required={bedrockInfo.reviewRequired} />
                  </div>
                  {bedrockInfo.reviewReason ? <p className="mb-2 text-[10px] text-gray-500 dark:text-gray-400">review: {bedrockInfo.reviewReason}</p> : null}
                  <div className="mb-2">
                    <LanguageStatusBadges info={languageInfo} />
                  </div>
                  {languageInfo.excluded ? (
                    <div className="mb-2">
                      <LanguageStatusWarning info={languageInfo} />
                    </div>
                  ) : null}
                  {item.cpm_jpy !== undefined && item.cpm_jpy !== null && (
                    <p className="text-[10px] text-gray-400 dark:text-gray-500 -mt-1 mb-2">
                      CPM ¥{formatNumber(Math.round(item.cpm_jpy))}
                      {item.cpm_source ? ` (${cpmSourceLabel(item.cpm_source)})` : ""}
                    </p>
                  )}
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
                        item.hit_score >= 80 ? "text-red-500" : item.hit_score >= 60 ? "text-amber-500" : item.hit_score >= 40 ? "text-[#4A7DFF]" : "text-gray-500 dark:text-gray-400 dark:text-gray-500"
                      }`}>
                        {item.hit_score}pt
                      </span>
                    )}
                  </div>
                  {effectiveViewMode === "card" && (
                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-100">
                      <div className="flex flex-col">
                        <span className="text-[11px] text-gray-600 dark:text-gray-300 font-medium tabular-nums">{formatNumber(displayViews)} 再生</span>
                        <span className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500">
                          ¥{formatNumber(Math.round(item.estimated_spend_increase_jpy ?? item.spend_increase ?? 0))} 増加
                        </span>
                      </div>
                      <div className="flex flex-col items-end">
                        {(item.view_increase || 0) > 0 && (
                          <span className="text-[10px] text-emerald-500 font-medium">+{formatNumber(item.view_increase)}</span>
                        )}
                        {item.comparison?.period_days && (
                          <span className="text-[9px] text-gray-400 dark:text-gray-500">{item.comparison.period_days}日比較</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ─── Enhanced Pagination ─── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 px-4 py-2.5 border-t border-gray-100 bg-gray-50 dark:bg-gray-800/50">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-[11px] text-gray-500 dark:text-gray-400 dark:text-gray-500">
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
          {(selectedGenreChip || localSearch || scoreRange[0] > 0 || scoreRange[1] < 100 || jpOnly || priorityFilter !== "all" || reviewRequiredOnly || actualMetricsFocus) && (
            <span className="text-[10px] text-gray-400 dark:text-gray-500">
              (フィルター適用: {filteredAndSortedItems.length}件)
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Page size selector (hidden on mobile) */}
          <div className="hidden sm:flex items-center gap-1.5">
            <span className="text-[11px] text-gray-500 dark:text-gray-400 dark:text-gray-500">表示件数:</span>
            <select
              value={perPage}
              onChange={(e) => setPerPage(Number(e.target.value))}
              className="text-[11px] px-2 py-1 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-md text-gray-600 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/30"
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size}件
                </option>
              ))}
            </select>
          </div>

          {/* Page info + load time */}
          <span className="text-[11px] text-gray-500 dark:text-gray-400 dark:text-gray-500">
            {page} / {totalPages || 1} ページ
            {loadTime && <span className="ml-2 text-[10px] text-gray-400 dark:text-gray-500">({loadTime})</span>}
          </span>

          {/* Page navigation */}
          <div className="flex items-center gap-1">
            {/* First page */}
            <button
              onClick={() => changePage(1)}
              disabled={page === 1 || isPageTransitioning || loading}
              className="px-1.5 py-1 text-[11px] font-medium rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="最初のページ"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.75 19.5l-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5" />
              </svg>
            </button>
            <button
              onClick={() => changePage(Math.max(1, page - 1))}
              disabled={page === 1 || isPageTransitioning || loading}
              className="px-2.5 py-1 text-[11px] font-medium rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
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
                    onClick={() => changePage(pageNum)}
                    className={`w-7 h-7 text-[11px] font-medium rounded transition-colors ${
                      page === pageNum
                        ? "bg-[#4A7DFF] text-white"
                        : "text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                    }`}
                    disabled={isPageTransitioning || loading}
                  >
                    {pageNum}
                  </button>
                );
              })}
            <button
              onClick={() => changePage(Math.min(totalPages, page + 1))}
              disabled={page === totalPages || totalPages === 0 || isPageTransitioning || loading}
              className="px-2.5 py-1 text-[11px] font-medium rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              次へ
            </button>
            {/* Last page */}
            <button
              onClick={() => changePage(totalPages)}
              disabled={page === totalPages || totalPages === 0 || isPageTransitioning || loading}
              className="px-1.5 py-1 text-[11px] font-medium rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
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
        <div className="absolute inset-0 bg-white dark:bg-gray-900/50 flex items-center justify-center">
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
