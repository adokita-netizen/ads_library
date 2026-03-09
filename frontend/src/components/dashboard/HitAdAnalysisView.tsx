"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { normalizeMediaReasons } from "@/lib/media";
import { bulkDownloadCreatives, getDownloadFailureMessage, type MediaStatus } from "@/lib/media";
import { platformLabels, platformColors, genreOptions } from "@/lib/constants";
import { formatNumber, formatYen } from "@/lib/format";
import HitAdCardView from "./HitAdCardView";
import AdDetailModal from "./AdDetailModal";
import CreativeCompareView from "../analysis/CreativeCompareView";
import HitPatternPanel from "./HitPatternPanel";
import CopyAnalysisPanel from "./CopyAnalysisPanel";
import CreativeGalleryView from "./CreativeGalleryView";
import CreativeLibraryRegressionDashboard from "./CreativeLibraryRegressionDashboard";
import CrawlPanel from "./CrawlPanel";
import FreshAdsSection from "./FreshAdsSection";
import AlertsPanel from "./AlertsPanel";
import ProRankingView from "./ProRankingView";
import AdvancedFilterPanel, { type AdvancedFilters, defaultFilters, getActiveFilterCount } from "./AdvancedFilterPanel";
import BulkActionsBar from "./BulkActionsBar";
import SectionTabContent from "./SectionTabContent";
import ThemeToggle from "../common/ThemeToggle";
import HitAdFilterControls, { type FilterState, DEFAULT_FILTERS } from "./HitAdFilterControls";
import HitAdSummaryCards, { genreLabel } from "./HitAdSummaryCards";
import { NumericProvenanceBadge, type NumericProvenanceState } from "../common/NumericProvenance";

// B11-17: Main tab type for analytics navigation
type MainTab = "overview" | "trends" | "market" | "advertisers" | "formulas" | "compare" | "collections" | "ai" | "scenario" | "deep-analysis" | "lp" | "competitors" | "reports" | "calendar" | "team" | "brief" | "analytics" | "genre";

// B4: Signal label & color constants for score breakdown popover
const signalLabels: Record<string, string> = {
  longevity: "配信継続力",
  spend: "消化額",
  active_bonus: "配信中ボーナス",
  creative: "クリエイティブ",
  trend: "トレンド",
};
const signalColors: Record<string, string> = {
  longevity: "#3b82f6",
  spend: "#22c55e",
  active_bonus: "#f97316",
  creative: "#a855f7",
  trend: "#ec4899",
};

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
  destination_url: string;
  destination_type: string;
  like_count: number;
  published_date: string;
  management_id: string;
  ad_url: string;
  description: string;
  title: string;
  days_running?: number;
  is_still_running?: boolean;
  hit_level?: string;
  video_url?: string;
  creative_type?: string;
  estimation_method?: string;
  score_breakdown?: Record<string, number>;
  hook_type?: string;
  emotion?: string;
  offer_type?: string;
  data_quality?: string;
  language?: string;
  is_duplicate?: boolean;
  media_status?: MediaStatus;
  media_cache_status?: string;
  metric_source?: string;
  creative_source?: string;
  lp_source?: string;
  metric_status?: NumericProvenanceState;
  creative_status?: NumericProvenanceState;
  freshness_status?: "fresh" | "missing" | "stale" | string;
  last_meta_success_at?: string;
  meta_quality_state?: NumericProvenanceState;
  meta_recovery_reason?: string;
}

// B18: Data quality assessment helper
function getDataQuality(ad: HitAd): "complete" | "partial" | "incomplete" {
  if (ad.data_quality) {
    if (ad.data_quality === "complete" || ad.data_quality === "high") return "complete";
    if (ad.data_quality === "partial" || ad.data_quality === "medium") return "partial";
    return "incomplete";
  }
  let missing = 0;
  if (!ad.thumbnail && !ad.image_url) missing++;
  if (!ad.genre || ad.genre === "未分類") missing++;
  if (!ad.destination_url) missing++;
  if (!ad.creative_type) missing++;
  if (!ad.hook_type) missing++;
  if (missing >= 3) return "incomplete";
  if (missing >= 1) return "partial";
  return "complete";
}

const qualityConfig = {
  complete: { color: "bg-emerald-500", label: "完全", tooltip: "データ完全" },
  partial: { color: "bg-amber-500", label: "部分的", tooltip: "一部データ不足" },
  incomplete: { color: "bg-red-400", label: "不完全", tooltip: "データ不足" },
};

interface GenreSummary {
  genre: string;
  ad_count: number;
  advertiser_count: number;
  total_views: number;
  total_spend: number;
}

interface ScoreBreakdownDetail {
  signals?: Record<string, { value: number; max: number; detail?: string }>;
  breakdown?: Record<string, number>;
  total?: number;
  hit_score?: number;
  [key: string]: unknown;
}

interface AdvertiserDetailAdItem {
  ad_id: number;
  product_name?: string;
  title?: string;
  hit_score?: number;
}

interface AdvertiserDetailData {
  advertiser_name: string;
  ad_count?: number;
  total_ads?: number;
  active_count?: number;
  active_ads?: number;
  avg_score?: number;
  total_spend?: number;
  estimated_spend?: number;
  hit_ads?: AdvertiserDetailAdItem[];
  non_hit_ads?: AdvertiserDetailAdItem[];
}

interface ScoreDistributionData {
  distribution?: { bucket: string; count: number }[];
  buckets?: { label: string; count: number }[];
  mean?: number;
  median?: number;
  hit_count?: number;
  mega_hit_count?: number;
}

interface DashboardSummaryData {
  mega_hit_count?: number;
  hit_count?: number;
  total_ads?: number;
  active_ads?: number;
  avg_score?: number;
  top_genre?: string;
  top_creative_type?: string;
}

interface GenreComparisonItem {
  genre?: string;
  name?: string;
  ad_count?: number;
  total_ads?: number;
  avg_score?: number;
  avg_hit_score?: number;
  hit_rate?: number;
  [key: string]: string | number | undefined;
}

interface GenreComparisonData {
  genres?: GenreComparisonItem[];
  items?: GenreComparisonItem[];
}

interface BulkDownloadSummary {
  fileCount: number;
  skippedCount: number;
  zipFilename: string;
  totalSizeBytes: number;
}

type RecoveryFilter = "all" | "needs_recovery" | "snapshot_only" | "download_unavailable" | "lp_unresolved";

function getRecoveryState(ad: HitAd): {
  needsRecovery: boolean;
  snapshotOnly: boolean;
  downloadUnavailable: boolean;
  lpUnresolved: boolean;
} {
  const mediaStatus = ad.media_status || {};
  const reasons = normalizeMediaReasons(mediaStatus.missing_reasons);
  const snapshotOnly =
    reasons.includes("snapshot_only") ||
    (mediaStatus.viewable !== false && mediaStatus.downloadable !== true && Boolean(ad.snapshot_url) && !ad.video_url && !ad.image_url);
  const downloadUnavailable = mediaStatus.downloadable === false || reasons.includes("download_unavailable") || reasons.includes("missing_creative");
  const lpUnresolved =
    mediaStatus.has_lp === false ||
    reasons.includes("lp_missing") ||
    reasons.includes("lp_unresolved");
  return {
    needsRecovery: snapshotOnly || downloadUnavailable || lpUnresolved,
    snapshotOnly,
    downloadUnavailable,
    lpUnresolved,
  };
}

function getSpendState(ad: HitAd): NumericProvenanceState {
  if (ad.estimation_method === "audience_based") return "real";
  if ((ad.spend_increase || 0) > 0 || (ad.cumulative_spend || 0) > 0) return "estimated";
  return "missing";
}

function getViewState(ad: HitAd): NumericProvenanceState {
  if ((ad.view_increase || 0) > 0 || (ad.cumulative_views || 0) > 0) return "real";
  return "missing";
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
  const [viewMode, setViewMode] = useState<"pro" | "table" | "card" | "advertiser" | "gallery">("pro");
  const [sectionTab, setSectionTab] = useState<MainTab>("overview");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkDownloading, setBulkDownloading] = useState(false);
  const [bulkDownloadSummary, setBulkDownloadSummary] = useState<BulkDownloadSummary | null>(null);
  const [recoveryFilter, setRecoveryFilter] = useState<RecoveryFilter>("all");
  const [showCompare, setShowCompare] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [detailAd, setDetailAd] = useState<HitAd | null>(null);

  // B5: Responsive — auto-switch to card view on small screens
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 768px)");
    const handler = (e: MediaQueryListEvent | MediaQueryList) => {
      if (e.matches) setViewMode("card");
    };
    handler(mql);
    mql.addEventListener("change", handler as (e: MediaQueryListEvent) => void);
    return () => mql.removeEventListener("change", handler as (e: MediaQueryListEvent) => void);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // B4-1: Score breakdown popover state
  const [scoreDetail, setScoreDetail] = useState<ScoreBreakdownDetail | null>(null);
  const [scoreDetailAdId, setScoreDetailAdId] = useState<number | null>(null);
  const [scoreDetailLoading, setScoreDetailLoading] = useState(false);
  const scorePopoverRef = useRef<HTMLDivElement>(null);

  // B4-2: Advertiser detail inline expansion state
  const [advertiserDetail, setAdvertiserDetail] = useState<AdvertiserDetailData | null>(null);
  const [selectedAdvertiser, setSelectedAdvertiser] = useState<string | null>(null);
  const [advertiserExpandAdId, setAdvertiserExpandAdId] = useState<number | null>(null);
  const [advertiserLoading, setAdvertiserLoading] = useState(false);

  // B4-3: Score distribution from API
  const [scoreDistribution, setScoreDistribution] = useState<ScoreDistributionData | null>(null);

  // B6-3: Dashboard summary from API
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummaryData | null>(null);
  // B6-4: Genre comparison from API
  const [genreComparison, setGenreComparison] = useState<GenreComparisonData | null>(null);

  // B9: Fresh ads refresh key (incremented after crawl completes)
  const [freshAdsKey, setFreshAdsKey] = useState(0);

  // B10: Export dropdown state
  const [showExport, setShowExport] = useState(false);



  // B19: Period for genre tab components
  const [proPeriod, setProPeriod] = useState<string | undefined>(undefined);



  // B21: Advanced filter panel state
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [advancedFilters, setAdvancedFilters] = useState<AdvancedFilters>(defaultFilters);
  const advFilterCount = getActiveFilterCount(advancedFilters);



  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);

  const abortRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    // Abort any in-flight request before starting a new one
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined> = { limit: 50 };
      if (selectedGenre !== "all") params.genre = selectedGenre;

      // Critical path: hit-ads and genre-summary (needed for main table)
      const [hitRes, genreRes] = await Promise.allSettled([
        fetchApi<{ total: number; items: HitAd[] }>("/rankings/hit-ads", { params }),
        fetchApi<{ genres: GenreSummary[] }>("/rankings/genre-summary", { params: { period: "weekly" } }),
      ]);

      // Skip state updates if request was aborted (user changed genre quickly)
      if (controller.signal.aborted) return;

      const hits = hitRes.status === "fulfilled" ? (hitRes.value.items || []) : [];
      const genreList = genreRes.status === "fulfilled" ? (genreRes.value.genres || []) : [];
      setHitAds(hits);
      setGenres(genreList);
      setIsEmpty(hits.length === 0 && genreList.length === 0);

      // Log critical failures
      if (hitRes.status === "rejected" && genreRes.status === "rejected") {
        toast.error("データの取得に失敗しました");
      }

      // Secondary data: load in background after main table is rendered
      Promise.allSettled([
        fetchApi<ScoreDistributionData>("/rankings/score-distribution"),
        fetchApi<DashboardSummaryData>("/rankings/dashboard-summary"),
        fetchApi<GenreComparisonData>("/rankings/genre-comparison"),
      ]).then(([distRes, summaryRes, genreCompRes]) => {
        if (controller.signal.aborted) return;
        setScoreDistribution(distRes.status === "fulfilled" ? distRes.value : null);
        setDashboardSummary(summaryRes.status === "fulfilled" ? summaryRes.value : null);
        setGenreComparison(genreCompRes.status === "fulfilled" ? genreCompRes.value : null);
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      setError("データの取得に失敗しました");
      console.error(err);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [selectedGenre]);

  useEffect(() => {
    fetchData();
    return () => { if (abortRef.current) abortRef.current.abort(); };
  }, [fetchData]);

  // BUG-2: Clear selected IDs when genre changes to avoid stale references
  useEffect(() => {
    setSelectedIds([]);
  }, [selectedGenre]);

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

  // B10: Export handler
  const handleExport = async (format: "csv" | "json" | "report") => {
    try {
      const params: Record<string, string | number | undefined> = {};
      if (selectedGenre !== "all") params.genre = selectedGenre;
      if (format === "csv") {
        const blob = await fetchApi<Blob>("/rankings/export/rankings", { params: { ...params, format: "csv" } });
        if (blob instanceof Blob) {
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `rankings_${new Date().toISOString().slice(0, 10)}.csv`;
          a.click();
          URL.revokeObjectURL(url);
        }
        toast.success("CSVをダウンロードしました");
      } else if (format === "json") {
        const data = await fetchApi("/rankings/hit-ads", { params: { ...params, limit: 100 } });
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `hit_ads_${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success("JSONをダウンロードしました");
      } else {
        toast("レポート機能は準備中です");
      }
    } catch {
      toast.error("エクスポートに失敗しました");
    }
  };

  // Summary stats (BUG-4: separate mega_hit and hit counts) -- B6-3: API data preferred
  const ds = dashboardSummary;
  const megaHitCount = ds?.mega_hit_count ?? hitAds.filter((a) => a.hit_level === "mega_hit").length;
  const hitCount = ds?.hit_count ?? hitAds.filter((a) => a.hit_level === "hit").length;
  const totalHits = megaHitCount + hitCount;
  const totalAdsCount = ds?.total_ads ?? hitAds.length;
  const avgHitScore = ds?.avg_score != null ? Math.round(ds.avg_score) : (hitAds.length > 0 ? Math.round(hitAds.reduce((s, a) => s + (a.hit_score || 0), 0) / hitAds.length) : 0);
  const topGenre = genres.length > 0 ? genres[0] : null;
  const topGenreFromApi = ds?.top_genre || null;
  const topCreativeType = ds?.top_creative_type || null;
  const totalSpend = genres.reduce((s, g) => s + (g.total_spend || 0), 0);
  const activeAdsCount = ds?.active_ads ?? null;

  // genreLabel imported from HitAdSummaryCards

  // BUG-3: Memoize winning pattern analysis to avoid recalculating on every render
  const { hitOnly, genreDistribution, platformDistribution, sortedGenres, sortedPlatforms, avgSpendIncrease, avgViewIncrease } = useMemo(() => {
    const hitOnly = hitAds.filter((a) => a.is_hit);
    const genreDistribution = hitOnly.reduce<Record<string, number>>((acc, a) => {
      const g = a.genre || "未分類";
      acc[g] = (acc[g] || 0) + 1;
      return acc;
    }, {});
    const platformDistribution = hitOnly.reduce<Record<string, number>>((acc, a) => {
      const p = a.platform || "unknown";
      acc[p] = (acc[p] || 0) + 1;
      return acc;
    }, {});
    const sortedGenres = Object.entries(genreDistribution).sort((a, b) => b[1] - a[1]);
    const sortedPlatforms = Object.entries(platformDistribution).sort((a, b) => b[1] - a[1]);
    const avgSpendIncrease = hitOnly.length > 0 ? Math.round(hitOnly.reduce((s, a) => s + (a.spend_increase || 0), 0) / hitOnly.length) : 0;
    const avgViewIncrease = hitOnly.length > 0 ? Math.round(hitOnly.reduce((s, a) => s + (a.view_increase || 0), 0) / hitOnly.length) : 0;
    return { hitOnly, genreDistribution, platformDistribution, sortedGenres, sortedPlatforms, avgSpendIncrease, avgViewIncrease };
  }, [hitAds]);

  // Phase 4: Delivery & confidence stats (memoized to avoid recalculation on every render)
  const { adsWithDays, avgDaysRunning, stillRunningCount, realDataCount, estimatedCount, realDataPct } = useMemo(() => {
    const adsWithDays = hitAds.filter((a) => a.days_running != null && a.days_running > 0);
    const avgDaysRunning = adsWithDays.length > 0 ? Math.round(adsWithDays.reduce((s, a) => s + (a.days_running || 0), 0) / adsWithDays.length) : 0;
    const stillRunningCount = hitAds.filter((a) => a.is_still_running === true).length;
    const realDataCount = hitAds.filter((a) => a.estimation_method === "audience_based").length;
    const estimatedCount = hitAds.length - realDataCount;
    const realDataPct = hitAds.length > 0 ? Math.round((realDataCount / hitAds.length) * 100) : 0;
    return { adsWithDays, avgDaysRunning, stillRunningCount, realDataCount, estimatedCount, realDataPct };
  }, [hitAds]);
  const missingNumericCount = useMemo(
    () => hitAds.filter((ad) => getSpendState(ad) === "missing" && getViewState(ad) === "missing").length,
    [hitAds],
  );

  // B3-2: Filtered & sorted ads (B10: added emotion + date range)
  const filteredAds = useMemo(() => {
    const q = filters.searchText.toLowerCase().trim();
    const dateFromTs = filters.dateFrom ? new Date(filters.dateFrom).getTime() : 0;
    const dateToTs = filters.dateTo ? new Date(filters.dateTo + "T23:59:59").getTime() : Infinity;
    let result = hitAds.filter((ad) => {
      if ((ad.hit_score || 0) < filters.scoreMin || (ad.hit_score || 0) > filters.scoreMax) return false;
      if ((ad.days_running || 0) < filters.daysMin) return false;
      if (filters.daysMax < 9999 && (ad.days_running || 0) > filters.daysMax) return false;
      if (filters.runningStatus === "running" && !ad.is_still_running) return false;
      if (filters.runningStatus === "stopped" && ad.is_still_running) return false;
      if (filters.creativeType !== "all" && ad.creative_type !== filters.creativeType) return false;
      if (filters.hookType !== "all" && ad.hook_type !== filters.hookType) return false;
      if (filters.emotion !== "all" && ad.emotion !== filters.emotion) return false;
      if (filters.platform !== "all" && ad.platform !== filters.platform) return false;
      // B10: Date range filter
      if (dateFromTs > 0 || dateToTs < Infinity) {
        const pubDate = ad.published_date ? new Date(ad.published_date).getTime() : 0;
        if (pubDate < dateFromTs || pubDate > dateToTs) return false;
      }
      if (q) {
        const hay = `${ad.product_name || ""} ${ad.title || ""} ${ad.advertiser_name || ""} ${ad.description || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      // B18: Language filter (detect Japanese by checking for CJK characters)
      if (filters.japaneseOnly) {
        const text = ad.product_name || ad.title || "";
        if (ad.language && ad.language !== "ja" && ad.language !== "jp") return false;
        if (!ad.language && text && !/[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]/.test(text)) return false;
      }
      // B18: Duplicate filter
      if (filters.hideDuplicates && ad.is_duplicate) return false;
      const recoveryState = getRecoveryState(ad);
      if (recoveryFilter === "needs_recovery" && !recoveryState.needsRecovery) return false;
      if (recoveryFilter === "snapshot_only" && !recoveryState.snapshotOnly) return false;
      if (recoveryFilter === "download_unavailable" && !recoveryState.downloadUnavailable) return false;
      if (recoveryFilter === "lp_unresolved" && !recoveryState.lpUnresolved) return false;
      return true;
    });
    switch (filters.sortBy) {
      case "score": result.sort((a, b) => (b.hit_score || 0) - (a.hit_score || 0)); break;
      case "days": result.sort((a, b) => (b.days_running || 0) - (a.days_running || 0)); break;
      case "spend": result.sort((a, b) => (b.spend_increase || 0) - (a.spend_increase || 0)); break;
      case "recent": result.sort((a, b) => new Date(b.published_date || 0).getTime() - new Date(a.published_date || 0).getTime()); break;
    }
    return result;
  }, [hitAds, filters, recoveryFilter]);

  const activeFilterCount = (filters.scoreMin > 0 ? 1 : 0) + (filters.scoreMax < 100 ? 1 : 0) + (filters.daysMin > 0 ? 1 : 0) + (filters.daysMax < 9999 ? 1 : 0) + (filters.runningStatus !== "all" ? 1 : 0) + (filters.sortBy !== "score" ? 1 : 0) + (filters.searchText ? 1 : 0) + (filters.creativeType !== "all" ? 1 : 0) + (filters.hookType !== "all" ? 1 : 0) + (filters.emotion !== "all" ? 1 : 0) + (filters.platform !== "all" ? 1 : 0) + (filters.dateFrom ? 1 : 0) + (filters.dateTo ? 1 : 0) + (!filters.japaneseOnly ? 1 : 0) + (!filters.hideDuplicates ? 1 : 0) + (recoveryFilter !== "all" ? 1 : 0);

  const recoveryCounts = useMemo(() => {
    const initial = {
      needsRecovery: 0,
      snapshotOnly: 0,
      downloadUnavailable: 0,
      lpUnresolved: 0,
    };
    return hitAds.reduce((acc, ad) => {
      const state = getRecoveryState(ad);
      if (state.needsRecovery) acc.needsRecovery += 1;
      if (state.snapshotOnly) acc.snapshotOnly += 1;
      if (state.downloadUnavailable) acc.downloadUnavailable += 1;
      if (state.lpUnresolved) acc.lpUnresolved += 1;
      return acc;
    }, initial);
  }, [hitAds]);

  // B3-3: Score distribution buckets
  const scoreBuckets = useMemo(() => {
    const buckets = Array.from({ length: 10 }, (_, i) => ({ range: i * 10, count: 0 }));
    hitAds.forEach((ad) => {
      const idx = Math.min(9, Math.floor((ad.hit_score || 0) / 10));
      buckets[idx].count++;
    });
    return buckets;
  }, [hitAds]);
  const maxBucketCount = Math.max(1, ...scoreBuckets.map((b) => b.count));

  // B3-4: Advertiser aggregation
  const advertiserStats = useMemo(() => {
    const map = new Map<string, { name: string; ads: HitAd[]; avgScore: number; megaHits: number; hits: number; totalSpend: number }>();
    filteredAds.forEach((ad) => {
      const name = ad.advertiser_name || "不明";
      if (!map.has(name)) map.set(name, { name, ads: [], avgScore: 0, megaHits: 0, hits: 0, totalSpend: 0 });
      const entry = map.get(name)!;
      entry.ads.push(ad);
      if (ad.hit_level === "mega_hit") entry.megaHits++;
      if (ad.hit_level === "hit") entry.hits++;
      entry.totalSpend += ad.spend_increase || 0;
    });
    map.forEach((entry) => {
      entry.avgScore = entry.ads.length > 0 ? Math.round(entry.ads.reduce((s, a) => s + (a.hit_score || 0), 0) / entry.ads.length) : 0;
    });
    return Array.from(map.values()).sort((a, b) => b.avgScore - a.avgScore);
  }, [filteredAds]);

  // B4-1: Handle score click for popover
  const handleScoreClick = async (e: React.MouseEvent, adId: number) => {
    e.stopPropagation();
    if (scoreDetailAdId === adId) {
      setScoreDetailAdId(null);
      setScoreDetail(null);
      return;
    }
    setScoreDetailLoading(true);
    setScoreDetailAdId(adId);
    try {
      const data = await fetchApi<ScoreBreakdownDetail>(`/rankings/score-breakdown/${adId}`);
      setScoreDetail(data);
    } catch {
      setScoreDetail(null);
      setScoreDetailAdId(null);
      toast.error("スコア内訳の取得に失敗しました");
    } finally {
      setScoreDetailLoading(false);
    }
  };

  // B4-2: Handle advertiser name click for inline expansion
  const handleAdvertiserClick = async (e: React.MouseEvent, name: string, adId: number) => {
    e.stopPropagation();
    if (advertiserExpandAdId === adId) {
      setSelectedAdvertiser(null);
      setAdvertiserDetail(null);
      setAdvertiserExpandAdId(null);
      return;
    }
    setAdvertiserLoading(true);
    setSelectedAdvertiser(name);
    setAdvertiserExpandAdId(adId);
    try {
      const data = await fetchApi<AdvertiserDetailData>(`/rankings/advertiser-detail`, { params: { advertiser_name: name } });
      setAdvertiserDetail(data);
    } catch {
      setAdvertiserDetail(null);
      setSelectedAdvertiser(null);
      setAdvertiserExpandAdId(null);
      toast.error("広告主詳細の取得に失敗しました");
    } finally {
      setAdvertiserLoading(false);
    }
  };

  // Close score popover on outside click
  useEffect(() => {
    if (!scoreDetailAdId) return;
    const handler = (e: MouseEvent) => {
      if (scorePopoverRef.current && !scorePopoverRef.current.contains(e.target as Node)) {
        setScoreDetailAdId(null);
        setScoreDetail(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [scoreDetailAdId]);

  // B4-3: Build score distribution buckets from API data (fallback to local computation)
  const apiBuckets = useMemo(() => {
    if (scoreDistribution?.distribution) {
      return scoreDistribution.distribution.map((b: { range_start?: number; range?: number; count?: number }) => ({
        range: b.range_start ?? b.range ?? 0,
        count: b.count ?? 0,
      }));
    }
    if (scoreDistribution?.buckets) {
      return scoreDistribution.buckets.map((b: { range_start?: number; range?: number; count?: number }) => ({
        range: b.range_start ?? b.range ?? 0,
        count: b.count ?? 0,
      }));
    }
    return null;
  }, [scoreDistribution]);

  const effectiveBuckets: { range: number; count: number }[] = apiBuckets || scoreBuckets;
  const effectiveMaxCount = Math.max(1, ...effectiveBuckets.map((b) => b.count));

  // B5-1: Open ad detail modal on row click
  const handleAdClick = useCallback((adId: number) => {
    const ad = hitAds.find((a) => a.ad_id === adId);
    if (ad) setDetailAd(ad);
    else onAdSelect(adId); // fallback to parent handler
  }, [hitAds, onAdSelect]);

  const renderRankChange = (change: number | null) => {
    if (change === null || change === undefined) return <span className="text-gray-300">-</span>;
    if (change > 0) return <span className="text-emerald-600 text-[11px] font-semibold">↑{change}</span>;
    if (change < 0) return <span className="text-red-500 text-[11px] font-semibold">↓{Math.abs(change)}</span>;
    return <span className="text-gray-400 dark:text-gray-500 text-[11px]">→</span>;
  };

  useEffect(() => {
    if (!detailAd) return;
    const latest = hitAds.find((ad) => ad.ad_id === detailAd.ad_id);
    if (latest && latest !== detailAd) {
      setDetailAd(latest);
    }
  }, [detailAd, hitAds]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between px-5 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 gap-2">
        <div className="flex items-center gap-3">
          <h2 className="text-[15px] font-bold text-gray-900 dark:text-gray-100 whitespace-nowrap">ヒット広告分析</h2>
          <p className="text-[11px] text-gray-400 dark:text-gray-500 hidden sm:block">高成長・高スコアの広告をリアルタイムで分析</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Compare button — B12: navigate to compare tab */}
          {selectedIds.length >= 2 && (
            <button
              onClick={() => setSectionTab("compare")}
              className="btn-primary text-[11px] px-3 py-1.5 h-8 flex items-center gap-1"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
              </svg>
              {selectedIds.length}件を比較
            </button>
          )}
          {/* B10-2: Bulk download */}
          {selectedIds.length >= 1 && (
            <button
              onClick={async () => {
                if (bulkDownloading) return;
                setBulkDownloading(true);
                try {
                  const result = await bulkDownloadCreatives(selectedIds);
                  const skipped = result.skipped_ids?.length || 0;
                  setBulkDownloadSummary({
                    fileCount: result.file_count,
                    skippedCount: skipped,
                    zipFilename: result.zip_filename,
                    totalSizeBytes: result.total_size_bytes,
                  });
                  toast.success(skipped > 0 ? `${result.file_count}件をDL、${skipped}件をスキップしました` : `${result.file_count}件をZIPでダウンロード`);
                } catch (error) {
                  toast.error(getDownloadFailureMessage(error));
                } finally {
                  setBulkDownloading(false);
                }
              }}
              disabled={bulkDownloading}
              className="h-8 px-3 rounded-lg text-[11px] font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 transition-colors flex items-center gap-1 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {bulkDownloading ? (
                <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-emerald-600/30 border-t-emerald-600" />
              ) : (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
              )}
              {bulkDownloading ? "ZIP作成中..." : `${selectedIds.length}件ZIP`}
            </button>
          )}

          {/* View mode toggle */}
          <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode("pro")}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${viewMode === "pro" ? "bg-white dark:bg-gray-900 shadow-sm text-gray-900 dark:text-gray-100 font-medium" : "text-gray-500 dark:text-gray-400 dark:text-gray-500"}`}
            >
              PRO
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${viewMode === "table" ? "bg-white dark:bg-gray-900 shadow-sm text-gray-900 dark:text-gray-100 font-medium" : "text-gray-500 dark:text-gray-400 dark:text-gray-500"}`}
            >
              テーブル
            </button>
            <button
              onClick={() => setViewMode("card")}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${viewMode === "card" ? "bg-white dark:bg-gray-900 shadow-sm text-gray-900 dark:text-gray-100 font-medium" : "text-gray-500 dark:text-gray-400 dark:text-gray-500"}`}
            >
              カード
            </button>
            <button
              onClick={() => setViewMode("advertiser")}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${viewMode === "advertiser" ? "bg-white dark:bg-gray-900 shadow-sm text-gray-900 dark:text-gray-100 font-medium" : "text-gray-500 dark:text-gray-400 dark:text-gray-500"}`}
            >
              広告主別
            </button>
            <button
              onClick={() => setViewMode("gallery")}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${viewMode === "gallery" ? "bg-white dark:bg-gray-900 shadow-sm text-gray-900 dark:text-gray-100 font-medium" : "text-gray-500 dark:text-gray-400 dark:text-gray-500"}`}
            >
              ギャラリー
            </button>
          </div>

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

          {/* B29: Dark mode toggle */}
          <ThemeToggle compact />

          {/* B13: Alerts bell */}
          <AlertsPanel onAdSelect={(adId) => {
            const ad = hitAds.find((a) => a.ad_id === adId);
            if (ad) setDetailAd(ad);
            else onAdSelect(adId);
          }} />

          {/* B10-1: Export dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowExport((v) => !v)}
              className="h-8 px-3 rounded-lg text-[11px] font-medium text-gray-600 dark:text-gray-300 bg-gray-100 hover:bg-gray-200 transition-colors flex items-center gap-1.5"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              エクスポート
            </button>
            {showExport && (
              <div className="absolute right-0 top-full mt-1 bg-white dark:bg-gray-900 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-20 min-w-[140px]">
                <button
                  onClick={() => { handleExport("csv"); setShowExport(false); }}
                  className="w-full text-left px-3 py-1.5 text-[11px] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 transition-colors"
                >
                  CSV エクスポート
                </button>
                <button
                  onClick={() => { handleExport("json"); setShowExport(false); }}
                  className="w-full text-left px-3 py-1.5 text-[11px] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 transition-colors"
                >
                  JSON エクスポート
                </button>
                <button
                  onClick={() => { handleExport("report"); setShowExport(false); }}
                  className="w-full text-left px-3 py-1.5 text-[11px] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 transition-colors"
                >
                  レポート出力
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto custom-scrollbar px-5 py-4 space-y-4">
        {bulkDownloadSummary && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[12px] font-semibold text-emerald-800">一括ダウンロード結果</p>
                <p className="mt-0.5 text-[11px] text-emerald-700">
                  {bulkDownloadSummary.fileCount}件をZIP化
                  {bulkDownloadSummary.skippedCount > 0 ? ` / ${bulkDownloadSummary.skippedCount}件スキップ` : ""}
                </p>
                <p className="mt-0.5 text-[10px] text-emerald-700">
                  {bulkDownloadSummary.zipFilename} / {(bulkDownloadSummary.totalSizeBytes / 1024 / 1024).toFixed(1)} MB
                </p>
              </div>
              <button
                onClick={() => setBulkDownloadSummary(null)}
                className="rounded-md px-2 py-1 text-[10px] font-medium text-emerald-700 hover:bg-emerald-100"
              >
                閉じる
              </button>
            </div>
          </div>
        )}

        {/* B11: Section tabs */}
        <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5 w-fit max-w-full overflow-x-auto scrollbar-none">
          {([
            { key: "overview" as const, label: "概要" },
            { key: "trends" as const, label: "トレンド" },
            { key: "market" as const, label: "マーケット" },
            { key: "advertisers" as const, label: "広告主" },
            { key: "formulas" as const, label: "勝ちパターン" },
            { key: "compare" as const, label: "比較" },
            { key: "collections" as const, label: "コレクション" },
            { key: "ai" as const, label: "AI分析" },
            { key: "scenario" as const, label: "シナリオ" },
            { key: "deep-analysis" as const, label: "詳細分析" },
            { key: "lp" as const, label: "LP分析" },
            { key: "competitors" as const, label: "競合" },
            { key: "reports" as const, label: "レポート" },
            { key: "calendar" as const, label: "カレンダー" },
            { key: "team" as const, label: "チーム" },
            { key: "brief" as const, label: "ブリーフ" },
            { key: "analytics" as const, label: "分析ダッシュボード" },
            { key: "genre" as const, label: "ジャンル分析" },
          ]).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setSectionTab(tab.key)}
              className={`px-3 py-1.5 rounded-md text-[11px] font-medium transition-colors ${
                sectionTab === tab.key ? "bg-white dark:bg-gray-900 shadow-sm text-gray-900 dark:text-gray-100" : "text-gray-500 dark:text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 dark:text-gray-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Non-overview tab content */}
        <SectionTabContent
          sectionTab={sectionTab}
          setSectionTab={setSectionTab}
          selectedGenre={selectedGenre}
          setSelectedGenre={setSelectedGenre}
          selectedIds={selectedIds}
          hitAds={hitAds}
          filteredAds={filteredAds}
          onAdSelect={onAdSelect}
          onDetailAd={setDetailAd}
          period={proPeriod}
        />

        {/* Overview tab content (existing) */}
        {sectionTab === "overview" && <>
        {/* Summary Cards */}
        <HitAdSummaryCards
          megaHitCount={megaHitCount}
          hitCount={hitCount}
          totalHits={totalHits}
          totalAdsCount={totalAdsCount}
          activeAdsCount={activeAdsCount}
          avgHitScore={avgHitScore}
          topGenreLabel={topGenreFromApi ? genreLabel(topGenreFromApi) : topGenre ? genreLabel(topGenre.genre) : "-"}
          topGenreDetail={topGenre ? `${topGenre.ad_count}件 / ${topGenre.advertiser_count}社` : "データなし"}
          topCreativeType={topCreativeType}
          totalSpend={totalSpend}
          genreCount={genres.length}
          avgDaysRunning={avgDaysRunning}
          stillRunningCount={stillRunningCount}
          realDataPct={realDataPct}
          realDataCount={realDataCount}
          estimatedCount={estimatedCount}
        />

        {/* B9: Crawl Panel — trigger new crawls from dashboard */}
        {!loading && (
          <CrawlPanel
            onCrawlComplete={() => {
              setFreshAdsKey((k) => k + 1);
              fetchData();
            }}
          />
        )}

        {/* B9: Fresh Ads Section — recently crawled ads */}
        {!loading && (
          <FreshAdsSection
            refreshKey={freshAdsKey}
            onAdSelect={handleAdClick}
          />
        )}

        {/* Score Distribution Chart (B3-3 → B4-3: API data) */}
        {!loading && (hitAds.length > 0 || scoreDistribution) && (
          <div className="card px-4 py-3">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[11px] text-gray-400 dark:text-gray-500 font-medium">スコア分布</p>
              {scoreDistribution && (
                <div className="flex items-center gap-3">
                  {scoreDistribution.mean != null && (
                    <span className="text-[9px] text-gray-500 dark:text-gray-400 dark:text-gray-500">平均: <span className="font-medium text-gray-700 dark:text-gray-300">{Math.round(scoreDistribution.mean)}</span></span>
                  )}
                  {scoreDistribution.median != null && (
                    <span className="text-[9px] text-gray-500 dark:text-gray-400 dark:text-gray-500">中央値: <span className="font-medium text-gray-700 dark:text-gray-300">{scoreDistribution.median}</span></span>
                  )}
                  {scoreDistribution.hit_count != null && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700">HIT {scoreDistribution.hit_count}</span>
                  )}
                  {scoreDistribution.mega_hit_count != null && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-100 text-red-700">大HIT {scoreDistribution.mega_hit_count}</span>
                  )}
                </div>
              )}
            </div>
            <div className="flex items-end gap-px h-14">
              {effectiveBuckets.map((bucket, i) => (
                <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                  <div
                    className={`w-full rounded-t-sm ${bucket.range >= 70 ? "bg-red-400" : bucket.range >= 45 ? "bg-orange-400" : "bg-gray-300"}`}
                    style={{ height: `${(bucket.count / effectiveMaxCount) * 100}%`, minHeight: bucket.count > 0 ? "2px" : "0" }}
                    title={`${bucket.range}-${bucket.range + 9}: ${bucket.count}件`}
                  />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-[8px] text-gray-400 dark:text-gray-500 mt-1">
              <span>0</span><span>25</span><span>50</span><span>75</span><span>100</span>
            </div>
            {apiBuckets && (
              <p className="text-[8px] text-gray-300 mt-1 text-right">全広告ベース (APIデータ)</p>
            )}
          </div>
        )}

        {/* Filter Bar (B3-2) */}
        {!loading && !isEmpty && hitAds.length > 0 && (
          <div className="space-y-2">
            <CreativeLibraryRegressionDashboard onAdSelect={handleAdClick} />

            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
              <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-[12px] font-semibold text-amber-800">復旧待ちキュー</p>
                  <p className="text-[10px] text-amber-700">DL不可 / スナップショットのみ / LP未解決 を一覧から直接絞り込めます。</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <button
                    onClick={() => setRecoveryFilter("all")}
                    className={`rounded px-2.5 py-1 text-[10px] font-medium ${recoveryFilter === "all" ? "bg-amber-700 text-white" : "bg-white text-amber-700"}`}
                  >
                    全て
                  </button>
                  <button
                    onClick={() => setRecoveryFilter("needs_recovery")}
                    className={`rounded px-2.5 py-1 text-[10px] font-medium ${recoveryFilter === "needs_recovery" ? "bg-amber-700 text-white" : "bg-white text-amber-700"}`}
                  >
                    復旧待ち {recoveryCounts.needsRecovery}
                  </button>
                  <button
                    onClick={() => setRecoveryFilter("snapshot_only")}
                    className={`rounded px-2.5 py-1 text-[10px] font-medium ${recoveryFilter === "snapshot_only" ? "bg-blue-700 text-white" : "bg-white text-blue-700"}`}
                  >
                    snapshot only {recoveryCounts.snapshotOnly}
                  </button>
                  <button
                    onClick={() => setRecoveryFilter("download_unavailable")}
                    className={`rounded px-2.5 py-1 text-[10px] font-medium ${recoveryFilter === "download_unavailable" ? "bg-rose-700 text-white" : "bg-white text-rose-700"}`}
                  >
                    DL不可 {recoveryCounts.downloadUnavailable}
                  </button>
                  <button
                    onClick={() => setRecoveryFilter("lp_unresolved")}
                    className={`rounded px-2.5 py-1 text-[10px] font-medium ${recoveryFilter === "lp_unresolved" ? "bg-gray-700 text-white" : "bg-white text-gray-700"}`}
                  >
                    LP未解決 {recoveryCounts.lpUnresolved}
                  </button>
                </div>
              </div>
            </div>
            {(estimatedCount > 0 || missingNumericCount > 0) && (
              <div className={`rounded-lg border px-4 py-3 ${realDataCount === 0 ? "border-rose-200 bg-rose-50" : "border-amber-200 bg-amber-50"}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <p className={`text-[12px] font-semibold ${realDataCount === 0 ? "text-rose-800" : "text-amber-800"}`}>
                    {realDataCount === 0 ? "実データ未取得" : "数値 provenance"}
                  </p>
                  <NumericProvenanceBadge state="real" />
                  <span className="text-[10px] text-gray-600">{realDataCount}件</span>
                  <NumericProvenanceBadge state="estimated" />
                  <span className="text-[10px] text-gray-600">{estimatedCount}件</span>
                  {missingNumericCount > 0 && (
                    <>
                      <NumericProvenanceBadge state="missing" />
                      <span className="text-[10px] text-gray-600">{missingNumericCount}件</span>
                    </>
                  )}
                </div>
                <p className={`mt-1 text-[10px] ${realDataCount === 0 ? "text-rose-700" : "text-amber-700"}`}>
                  {realDataCount === 0
                    ? "estimated_only / 実データ未取得。消化額は推定表示です。"
                    : estimatedCount > 0
                      ? "推定値を含みます。実測バッジのない spend は比較時に注意してください。"
                      : "一部数値は backfill 中です。"}
                  {missingNumericCount > 0 ? " missing_numeric_count > 0 / backfill待ち。" : ""}
                </p>
              </div>
            )}

            <HitAdFilterControls
              filters={filters}
              setFilters={setFilters}
              showFilters={showFilters}
              setShowFilters={setShowFilters}
              activeFilterCount={activeFilterCount}
              filteredCount={filteredAds.length}
              totalCount={hitAds.length}
            />
          </div>
        )}

        {/* Winning Pattern Analysis */}
        {!loading && hitOnly.length > 0 && (
          <div className="card px-4 py-4">
            <div className="flex items-center gap-2 mb-3">
              <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
              </svg>
              <h3 className="text-[13px] font-bold text-gray-900 dark:text-gray-100">勝ちパターン分析</h3>
              <span className="text-[10px] text-gray-400 dark:text-gray-500">ヒット広告{hitOnly.length}件の共通傾向</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Genre breakdown */}
              <div>
                <p className="text-[10px] text-gray-400 dark:text-gray-500 font-medium mb-2">ジャンル分布</p>
                <div className="space-y-1.5">
                  {sortedGenres.slice(0, 4).map(([genre, count]) => {
                    const pct = Math.round((count / hitOnly.length) * 100);
                    return (
                      <div key={genre} className="flex items-center gap-2">
                        <span className="text-[10px] text-gray-600 dark:text-gray-300 w-16 truncate" title={genreLabel(genre)}>{genreLabel(genre)}</span>
                        <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div className="h-full rounded-full bg-[#4A7DFF]" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500 w-8 text-right">{pct}%</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Platform breakdown */}
              <div>
                <p className="text-[10px] text-gray-400 dark:text-gray-500 font-medium mb-2">媒体分布</p>
                <div className="space-y-1.5">
                  {sortedPlatforms.slice(0, 4).map(([plat, count]) => {
                    const pct = Math.round((count / hitOnly.length) * 100);
                    return (
                      <div key={plat} className="flex items-center gap-2">
                        <span className={`platform-icon ${platformColors[plat] || "bg-gray-400"} text-[8px] w-8`}>
                          {platformLabels[plat] || plat}
                        </span>
                        <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div className="h-full rounded-full bg-emerald-400" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500 w-8 text-right">{pct}%</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Key metrics */}
              <div>
                <p className="text-[10px] text-gray-400 dark:text-gray-500 font-medium mb-2">ヒット広告の平均値</p>
                <div className="space-y-2">
                  <div className="flex items-center justify-between py-1 border-b border-gray-50">
                    <span className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500">消化額増加/週</span>
                    <span className="text-[11px] font-semibold text-gray-900 dark:text-gray-100">{formatYen(avgSpendIncrease)}</span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-gray-50">
                    <span className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500">再生数増加/週</span>
                    <span className="text-[11px] font-semibold text-gray-900 dark:text-gray-100">{formatNumber(avgViewIncrease)}</span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-gray-50">
                    <span className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500">平均ヒットスコア</span>
                    <span className="text-[11px] font-semibold text-[#4A7DFF]">{avgHitScore}/100</span>
                  </div>
                  <div className="flex items-center justify-between py-1">
                    <span className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500">トップジャンル</span>
                    <span className="badge-blue text-[9px]">{sortedGenres[0] ? genreLabel(sortedGenres[0][0]) : "-"}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* B6-4: Genre Comparison Chart (horizontal bar chart from API) */}
        {!loading && genreComparison && (() => {
          type GenreItem = Record<string, string | number | undefined>;
          const items: GenreItem[] = genreComparison.genres || genreComparison.items || (Array.isArray(genreComparison) ? genreComparison : []);
          if (!Array.isArray(items) || items.length === 0) return null;
          const sorted = [...items].sort((a, b) => ((b.ad_count as number) || (b.total_ads as number) || 0) - ((a.ad_count as number) || (a.total_ads as number) || 0)).slice(0, 10);
          const maxCount = Math.max(1, ...sorted.map((g) => (g.ad_count as number) || (g.total_ads as number) || 0));
          const maxScore = Math.max(1, ...sorted.map((g) => (g.avg_score as number) || (g.avg_hit_score as number) || 0));
          return (
            <div className="card px-4 py-4">
              <div className="flex items-center gap-2 mb-3">
                <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                </svg>
                <h3 className="text-[13px] font-bold text-gray-900 dark:text-gray-100">ジャンル比較</h3>
                <span className="text-[10px] text-gray-400 dark:text-gray-500">{sorted.length}ジャンルの広告数・平均スコア比較</span>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Ad count bar chart */}
                <div>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500 font-medium mb-2">広告数</p>
                  <div className="space-y-1.5">
                    {sorted.map((g, i) => {
                      const count = Number(g.ad_count || g.total_ads || 0);
                      const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
                      return (
                        <div key={String(g.genre) || i} className="flex items-center gap-2">
                          <span className="text-[10px] text-gray-600 dark:text-gray-300 w-20 truncate shrink-0" title={genreLabel(g.genre as string)}>
                            {genreLabel(g.genre as string)}
                          </span>
                          <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden relative">
                            <div
                              className="h-full rounded bg-[#4A7DFF] transition-all"
                              style={{ width: `${pct}%` }}
                            />
                            <span className="absolute inset-y-0 right-1.5 flex items-center text-[9px] font-medium text-gray-600 dark:text-gray-300">
                              {count}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
                {/* Average score bar chart */}
                <div>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500 font-medium mb-2">平均スコア</p>
                  <div className="space-y-1.5">
                    {sorted.map((g, i) => {
                      const score = Math.round(Number(g.avg_score || g.avg_hit_score || 0));
                      const pct = maxScore > 0 ? (score / maxScore) * 100 : 0;
                      const rawHitRate = g.hit_rate != null ? Number(g.hit_rate) : null;
                      const hitRate = rawHitRate != null ? Math.round(rawHitRate <= 1 ? rawHitRate * 100 : rawHitRate) : null;
                      return (
                        <div key={String(g.genre) || i} className="flex items-center gap-2">
                          <span className="text-[10px] text-gray-600 dark:text-gray-300 w-20 truncate shrink-0" title={genreLabel(g.genre as string)}>
                            {genreLabel(g.genre as string)}
                          </span>
                          <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden relative">
                            <div
                              className="h-full rounded transition-all"
                              style={{
                                width: `${pct}%`,
                                backgroundColor: score >= 70 ? "#ef4444" : score >= 45 ? "#f59e0b" : "#4A7DFF",
                              }}
                            />
                            <span className="absolute inset-y-0 right-1.5 flex items-center text-[9px] font-medium text-gray-600 dark:text-gray-300">
                              {score}
                              {hitRate != null && (
                                <span className="ml-1 text-[8px] text-gray-400 dark:text-gray-500">({hitRate}%HIT)</span>
                              )}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* B8: Hit Pattern Analysis Panel */}
        {!loading && !isEmpty && (
          <HitPatternPanel genre={selectedGenre !== "all" ? selectedGenre : undefined} />
        )}

        {/* B8: Copy Analysis Panel */}
        {!loading && !isEmpty && (
          <CopyAnalysisPanel genre={selectedGenre !== "all" ? selectedGenre : undefined} />
        )}

        {/* Error — B5-2: Retry button */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              <span className="text-[12px] text-red-700">{error}</span>
            </div>
            <button
              onClick={fetchData}
              className="shrink-0 px-3 py-1.5 rounded-lg text-[11px] font-medium text-white bg-red-500 hover:bg-red-600 transition-colors"
            >
              再試行
            </button>
          </div>
        )}

        {/* Loading — B5-2: Skeleton UI */}
        {loading && (
          <div className="space-y-4">
            {/* Skeleton summary cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="card px-4 py-3 animate-pulse">
                  <div className="h-3 bg-gray-200 rounded w-20 mb-2" />
                  <div className="h-6 bg-gray-200 rounded w-28 mb-1" />
                  <div className="h-2 bg-gray-100 rounded w-16" />
                </div>
              ))}
            </div>
            {/* Skeleton table rows */}
            <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden bg-white dark:bg-gray-900">
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th className="w-10">#</th>
                      <th className="w-12">画像</th>
                      <th>商材名</th>
                      <th>広告主</th>
                      <th>ヒットスコア</th>
                      <th className="text-right">消化増加額</th>
                      <th className="text-right">累計消化額</th>
                      <th>配信日数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i} className="animate-pulse">
                        <td><div className="w-6 h-6 rounded bg-gray-200" /></td>
                        <td><div className="w-10 h-10 rounded bg-gray-200" /></td>
                        <td>
                          <div className="h-4 bg-gray-200 rounded w-32 mb-1" />
                          <div className="h-2.5 bg-gray-100 rounded w-20" />
                        </td>
                        <td><div className="h-3.5 bg-gray-200 rounded w-24" /></td>
                        <td>
                          <div className="h-1.5 bg-gray-200 rounded-full w-24" />
                        </td>
                        <td className="text-right"><div className="h-4 bg-gray-200 rounded w-16 ml-auto" /></td>
                        <td className="text-right"><div className="h-3.5 bg-gray-100 rounded w-14 ml-auto" /></td>
                        <td><div className="h-3.5 bg-gray-200 rounded w-12" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Empty State — B5-2: More descriptive */}
        {!loading && isEmpty && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <svg className="w-14 h-14 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
            </svg>
            <p className="text-[14px] font-medium text-gray-600 dark:text-gray-300 mb-1">ランキングデータがありません</p>
            <p className="text-[12px] text-gray-400 dark:text-gray-500 mb-2 max-w-sm">
              広告データをクロールしてから、ランキングを計算するとヒット広告が自動で検出されます。
            </p>
            <p className="text-[10px] text-gray-300 mb-5">ランキング計算には通常1-2分かかります</p>
            <button onClick={handleCompute} disabled={computing} className="btn-primary text-[12px] px-5 py-2.5">
              {computing ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  計算中...
                </span>
              ) : "ランキングを計算"}
            </button>
          </div>
        )}

        {/* B31: Pro Ranking View (full-featured with genre sidebar, search collections, filters) */}
        {!loading && viewMode === "pro" && (
          <ProRankingView onAdSelect={handleAdClick} />
        )}

        {/* Hit Ads — Card View */}
        {!loading && !isEmpty && filteredAds.length > 0 && viewMode === "card" && (
          <HitAdCardView ads={filteredAds} onAdSelect={handleAdClick} />
        )}

        {/* B8: Hit Ads — Gallery View */}
        {!loading && !isEmpty && filteredAds.length > 0 && viewMode === "gallery" && (
          <CreativeGalleryView ads={filteredAds} onAdSelect={handleAdClick} onRecoveryRequest={handleAdClick} />
        )}

        {/* Hit Ads — Table View */}
        {!loading && !isEmpty && filteredAds.length > 0 && viewMode === "table" && (
          <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden bg-white dark:bg-gray-900">
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="w-8">
                      <input
                        type="checkbox"
                        className="rounded border-gray-300"
                        checked={filteredAds.length > 0 && selectedIds.length === filteredAds.length}
                        onChange={() => {
                          if (selectedIds.length === filteredAds.length) {
                            setSelectedIds([]);
                          } else {
                            setSelectedIds(filteredAds.map((a) => a.ad_id));
                          }
                        }}
                      />
                    </th>
                    <th className="w-10">#</th>
                    <th className="w-12">画像</th>
                    <th>商材名</th>
                    <th>広告主</th>
                    <th>ジャンル</th>
                    <th className="w-10">媒体</th>
                    <th>ヒットスコア</th>
                    <th className="min-w-[120px]">スコア内訳</th>
                    <th className="text-right">トレンド</th>
                    <th className="text-right">消化増加額</th>
                    <th className="text-right">累計消化額</th>
                    <th className="text-right">再生増加数</th>
                    <th className="text-right">累計再生数</th>
                    <th className="text-right">いいね</th>
                    <th>掲載開始</th>
                    <th>配信日数</th>
                    <th>遷移先</th>
                    <th className="w-12 text-center">変動</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAds.map((ad) => {
                    // B9: Prefer proxy URL for thumbnails; fallback to raw URL
                    const thumbSrc = ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || ad.image_url || "");
                    const pLabel = platformLabels[ad.platform] || ad.platform;
                    const pColor = platformColors[ad.platform] || "bg-gray-400";
                    const sb = ad.score_breakdown;
                    const isAdvExpanded = advertiserExpandAdId === ad.ad_id && (advertiserDetail || advertiserLoading);
                    return (
                      <React.Fragment key={ad.ad_id}>
                      <tr onClick={() => handleAdClick(ad.ad_id)} className="cursor-pointer">
                        {/* Checkbox */}
                        <td>
                          <input
                            type="checkbox"
                            className="rounded border-gray-300"
                            checked={selectedIds.includes(ad.ad_id)}
                            onChange={() => {
                              setSelectedIds((prev) =>
                                prev.includes(ad.ad_id) ? prev.filter((id) => id !== ad.ad_id) : [...prev, ad.ad_id]
                              );
                            }}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </td>
                        {/* Rank */}
                        <td>
                          <span className={`inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold ${
                            ad.rank <= 3 ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-500 dark:text-gray-400 dark:text-gray-500"
                          }`}>
                            {ad.rank}
                          </span>
                        </td>
                        {/* Thumbnail — B7: fallback chain + lazy loading */}
                        <td>
                          {thumbSrc ? (
                            <img
                              src={thumbSrc}
                              alt=""
                              className="w-10 h-10 rounded object-cover bg-gray-100"
                              loading="lazy"
                              onError={(e) => {
                                const el = e.target as HTMLImageElement;
                                // B9: Fallback chain: proxy -> thumbnail -> image_url -> hide
                                if (ad.thumbnail && el.src !== ad.thumbnail) {
                                  el.src = ad.thumbnail;
                                } else if (ad.image_url && el.src !== ad.image_url) {
                                  el.src = ad.image_url;
                                } else if (ad.snapshot_url && el.src !== ad.snapshot_url) {
                                  el.src = ad.snapshot_url;
                                } else {
                                  el.style.display = "none";
                                  if (el.nextElementSibling) (el.nextElementSibling as HTMLElement).style.display = "flex";
                                }
                              }}
                            />
                          ) : null}
                          <div className={`w-10 h-10 rounded bg-gray-100 items-center justify-center ${thumbSrc ? "hidden" : "flex"}`}>
                            {ad.creative_type === "video" ? (
                              <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                              </svg>
                            ) : (
                              <svg className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                              </svg>
                            )}
                          </div>
                        </td>
                        {/* Product Name + HIT badge + description */}
                        <td>
                          <div className="flex items-center gap-1.5">
                            <span className="text-[13px] font-medium text-gray-900 dark:text-gray-100 truncate max-w-[200px]">
                              {ad.product_name}
                            </span>
                            {ad.hit_level === "mega_hit" ? (
                              <span className="shrink-0 rounded bg-red-100 text-red-700 px-1.5 py-0.5 text-[9px] font-bold">
                                大HIT
                              </span>
                            ) : ad.hit_level === "hit" ? (
                              <span className="shrink-0 rounded bg-orange-100 text-orange-700 px-1.5 py-0.5 text-[9px] font-bold">
                                HIT
                              </span>
                            ) : null}
                          </div>
                          {ad.description && (
                            <p className="text-[10px] text-gray-400 dark:text-gray-500 truncate max-w-[240px] mt-0.5" title={ad.description}>
                              {ad.description}
                            </p>
                          )}
                        </td>
                        {/* Advertiser — B4-2: clickable for detail expansion */}
                        <td>
                          <span
                            className="text-[12px] text-[#4A7DFF] cursor-pointer hover:underline truncate max-w-[140px] block"
                            onClick={(e) => handleAdvertiserClick(e, ad.advertiser_name, ad.ad_id)}
                          >
                            {ad.advertiser_name || "-"}
                          </span>
                        </td>
                        {/* Genre */}
                        <td>
                          <span className="badge-blue text-[10px]">{genreLabel(ad.genre)}</span>
                        </td>
                        {/* Platform */}
                        <td>
                          <span className={`platform-icon ${pColor} text-[9px]`}>{pLabel}</span>
                        </td>
                        {/* Hit Score — B4-1: clickable with popover */}
                        <td>
                          <div className="relative">
                            <div
                              className="flex items-center gap-2 min-w-[100px] cursor-pointer hover:opacity-80 transition-opacity"
                              onClick={(e) => handleScoreClick(e, ad.ad_id)}
                            >
                              <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                  className="h-full rounded-full"
                                  style={{
                                    width: `${ad.hit_score || 0}%`,
                                    backgroundColor: (ad.hit_score || 0) >= 80 ? "#ef4444" : (ad.hit_score || 0) >= 50 ? "#f59e0b" : "#4A7DFF",
                                  }}
                                />
                              </div>
                              <span className="text-[11px] font-semibold text-gray-700 dark:text-gray-300 w-7 text-right">{ad.hit_score || 0}</span>
                            </div>
                            {/* Score breakdown popover */}
                            {scoreDetailAdId === ad.ad_id && (
                              <div ref={scorePopoverRef} className="absolute z-50 right-0 top-full mt-1 w-64 card shadow-lg p-3" onClick={(e) => e.stopPropagation()}>
                                {scoreDetailLoading ? (
                                  <div className="flex items-center justify-center py-3">
                                    <svg className="animate-spin h-4 w-4 text-[#4A7DFF]" viewBox="0 0 24 24" fill="none">
                                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                  </div>
                                ) : scoreDetail ? (
                                  <>
                                    <p className="text-[12px] font-bold mb-2">スコア内訳 ({scoreDetail.hit_score ?? (ad.hit_score || 0)}/100)</p>
                                    {scoreDetail.signals && Object.entries(scoreDetail.signals).map(([key, sig]: [string, any]) => (
                                      <div key={key} className="mb-1.5">
                                        <div className="flex items-center gap-2">
                                          <span className="text-[9px] w-16 text-gray-500 dark:text-gray-400 dark:text-gray-500">{signalLabels[key] || key}</span>
                                          <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                            <div
                                              className="h-full rounded-full"
                                              style={{ width: `${sig.max > 0 ? (sig.score / sig.max) * 100 : 0}%`, backgroundColor: signalColors[key] || "#6b7280" }}
                                            />
                                          </div>
                                          <span className="text-[9px] text-gray-600 dark:text-gray-300 w-10 text-right">{sig.score}/{sig.max}</span>
                                        </div>
                                        {sig.detail && (
                                          <p className="text-[8px] text-gray-400 dark:text-gray-500 ml-[72px] mt-0.5">{sig.detail}</p>
                                        )}
                                      </div>
                                    ))}
                                  </>
                                ) : (
                                  <p className="text-[11px] text-gray-400 dark:text-gray-500">データなし</p>
                                )}
                              </div>
                            )}
                          </div>
                        </td>
                        {/* Score Breakdown (B3-1) */}
                        <td>
                          {sb ? (
                            <div>
                              <div className="flex items-center gap-px h-3 min-w-[100px]">
                                {sb.longevity != null && sb.longevity > 0 && (
                                  <div className="h-full bg-blue-400 rounded-sm" style={{ width: `${(sb.longevity / 40) * 100}%` }} title={`配信継続力: ${sb.longevity}/40`} />
                                )}
                                {sb.spend != null && sb.spend > 0 && (
                                  <div className="h-full bg-green-400 rounded-sm" style={{ width: `${(sb.spend / 20) * 100}%` }} title={`消化額: ${sb.spend}/20`} />
                                )}
                                {sb.active_bonus != null && sb.active_bonus > 0 && (
                                  <div className="h-full bg-orange-400 rounded-sm" style={{ width: `${(sb.active_bonus / 20) * 100}%` }} title={`継続ボーナス: ${sb.active_bonus}/20`} />
                                )}
                                {sb.creative != null && sb.creative > 0 && (
                                  <div className="h-full bg-purple-400 rounded-sm" style={{ width: `${(sb.creative / 10) * 100}%` }} title={`クリエイティブ: ${sb.creative}/10`} />
                                )}
                                {sb.trend != null && sb.trend > 0 && (
                                  <div className="h-full bg-pink-400 rounded-sm" style={{ width: `${(sb.trend / 10) * 100}%` }} title={`トレンド: ${sb.trend}/10`} />
                                )}
                              </div>
                              <p className="text-[8px] text-gray-400 dark:text-gray-500 mt-0.5">{ad.hit_score}/100</p>
                            </div>
                          ) : (
                            <span className="text-[10px] text-gray-300">-</span>
                          )}
                        </td>
                        {/* Trend Score */}
                        <td className="text-right">
                          <span className="text-[12px] font-medium text-gray-700 dark:text-gray-300">{ad.trend_score || 0}</span>
                        </td>
                        {/* Spend Increase */}
                        <td className="text-right">
                          <div className="flex flex-col items-end gap-1">
                            <span className="text-[13px] font-semibold text-gray-900 dark:text-gray-100">{formatYen(ad.spend_increase || 0)}</span>
                            <NumericProvenanceBadge state={getSpendState(ad)} />
                          </div>
                        </td>
                        {/* Cumulative Spend */}
                        <td className="text-right">
                          <div className="flex flex-col items-end gap-1">
                            <span className="text-[12px] text-gray-500 dark:text-gray-400 dark:text-gray-500">{formatYen(ad.cumulative_spend || 0)}</span>
                            <NumericProvenanceBadge state={getSpendState(ad)} />
                          </div>
                        </td>
                        {/* View Increase */}
                        <td className="text-right">
                          <div className="flex flex-col items-end gap-1">
                            <span className="text-[13px] font-medium text-gray-700 dark:text-gray-300">{formatNumber(ad.view_increase || 0)}</span>
                            <NumericProvenanceBadge state={getViewState(ad)} />
                          </div>
                        </td>
                        {/* Cumulative Views */}
                        <td className="text-right">
                          <span className="text-[12px] text-gray-500 dark:text-gray-400 dark:text-gray-500">{formatNumber(ad.cumulative_views || 0)}</span>
                        </td>
                        {/* Like Count */}
                        <td className="text-right">
                          <span className="text-[12px] text-gray-600 dark:text-gray-300">{formatNumber(ad.like_count || 0)}</span>
                        </td>
                        {/* Published Date */}
                        <td>
                          <span className="text-[11px] text-gray-500 dark:text-gray-400 dark:text-gray-500 whitespace-nowrap">
                            {ad.published_date ? new Date(ad.published_date).toLocaleDateString("ja-JP") : "-"}
                          </span>
                        </td>
                        {/* Days Running */}
                        <td>
                          <div className="flex items-center gap-1">
                            <span className="text-[12px] font-medium text-gray-700 dark:text-gray-300">
                              {ad.days_running || "-"}
                              {ad.days_running != null && (
                                <span className="text-[10px] text-gray-400 dark:text-gray-500 ml-0.5">日</span>
                              )}
                            </span>
                            {ad.is_still_running && (
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" title="配信中" />
                            )}
                          </div>
                        </td>
                        {/* Destination URL */}
                        <td>
                          {ad.destination_url ? (
                            <div className="flex flex-col gap-0.5">
                              <button
                                className="inline-flex items-center gap-1 text-[#4A7DFF] hover:underline text-[11px] max-w-[120px] group"
                                onClick={(e) => { e.stopPropagation(); window.open(ad.destination_url, "_blank", "noopener,noreferrer"); }}
                                title={ad.destination_url}
                              >
                                <span className="truncate">{(() => { try { return new URL(ad.destination_url).hostname.replace(/^www\./, ""); } catch { return ad.destination_url; } })()}</span>
                                <svg className="w-3 h-3 shrink-0 opacity-50 group-hover:opacity-100 transition-opacity" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                                </svg>
                              </button>
                              <button
                                className="text-[9px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 hover:bg-purple-100 transition-colors whitespace-nowrap w-fit"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  fetchApi("/lp-analysis/crawl", {
                                    method: "POST",
                                    body: { url: ad.destination_url, ad_id: ad.ad_id, auto_analyze: true },
                                  })
                                    .then(() => { toast.success("LP分析を開始しました"); })
                                    .catch(() => { toast.error("LP分析の開始に失敗しました"); });
                                }}
                                title="遷移先LPを分析"
                              >
                                LP分析
                              </button>
                            </div>
                          ) : (
                            <span className="text-[10px] text-gray-300">-</span>
                          )}
                        </td>
                        {/* Rank Change */}
                        <td className="text-center">
                          {renderRankChange(ad.rank_change)}
                        </td>
                      </tr>
                      {/* B4-2: Advertiser detail inline expansion */}
                      {isAdvExpanded && (
                        <tr className="bg-blue-50/50">
                          <td colSpan={19} className="p-0">
                            <div className="px-4 py-3 space-y-2" onClick={(e) => e.stopPropagation()}>
                              <div className="flex items-center justify-between">
                                <p className="text-[12px] font-bold text-gray-900 dark:text-gray-100">
                                  {advertiserDetail?.advertiser_name || ad.advertiser_name} の広告分析
                                </p>
                                <button
                                  className="text-[10px] text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-200 dark:text-gray-300 transition-colors"
                                  onClick={(e) => { e.stopPropagation(); setSelectedAdvertiser(null); setAdvertiserDetail(null); setAdvertiserExpandAdId(null); }}
                                >
                                  閉じる
                                </button>
                              </div>
                              {advertiserLoading ? (
                                <div className="flex items-center justify-center py-2">
                                  <svg className="animate-spin h-4 w-4 text-[#4A7DFF]" viewBox="0 0 24 24" fill="none">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                  </svg>
                                </div>
                              ) : advertiserDetail ? (
                                <>
                                  {/* Stats row */}
                                  <div className="flex items-center gap-4">
                                    {advertiserDetail.total_ads != null && (
                                      <div className="text-center">
                                        <p className="text-[16px] font-bold text-gray-900 dark:text-gray-100">{advertiserDetail.total_ads}</p>
                                        <p className="text-[9px] text-gray-400 dark:text-gray-500">広告数</p>
                                      </div>
                                    )}
                                    {advertiserDetail.active_count != null && (
                                      <div className="text-center">
                                        <p className="text-[16px] font-bold text-emerald-600">{advertiserDetail.active_count}</p>
                                        <p className="text-[9px] text-gray-400 dark:text-gray-500">アクティブ</p>
                                      </div>
                                    )}
                                    {advertiserDetail.avg_score != null && (
                                      <div className="text-center">
                                        <p className="text-[16px] font-bold text-[#4A7DFF]">{Math.round(advertiserDetail.avg_score)}</p>
                                        <p className="text-[9px] text-gray-400 dark:text-gray-500">平均スコア</p>
                                      </div>
                                    )}
                                    {advertiserDetail.total_spend != null && (
                                      <div className="text-center">
                                        <p className="text-[16px] font-bold text-gray-900 dark:text-gray-100">{formatYen(advertiserDetail.total_spend)}</p>
                                        <p className="text-[9px] text-gray-400 dark:text-gray-500">推定消化額</p>
                                      </div>
                                    )}
                                  </div>
                                  {/* Hit ads list */}
                                  {advertiserDetail.hit_ads && advertiserDetail.hit_ads.length > 0 && (
                                    <div>
                                      <p className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500 font-medium mb-1">ヒット広告</p>
                                      <div className="flex flex-wrap gap-1.5">
                                        {advertiserDetail.hit_ads.slice(0, 8).map((ha: { ad_id: number; product_name?: string; title?: string; hit_score?: number }) => (
                                          <button
                                            key={ha.ad_id}
                                            className="text-[9px] px-2 py-1 rounded bg-orange-50 text-orange-700 hover:bg-orange-100 transition-colors truncate max-w-[160px]"
                                            onClick={(e) => { e.stopPropagation(); onAdSelect(ha.ad_id); }}
                                            title={ha.product_name || ha.title}
                                          >
                                            {ha.product_name || ha.title || `#${ha.ad_id}`} ({ha.hit_score ?? "-"})
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                  {/* Non-hit ads list */}
                                  {advertiserDetail.non_hit_ads && advertiserDetail.non_hit_ads.length > 0 && (
                                    <div>
                                      <p className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500 font-medium mb-1">その他の広告</p>
                                      <div className="flex flex-wrap gap-1.5">
                                        {advertiserDetail.non_hit_ads.slice(0, 6).map((na: { ad_id: number; product_name?: string; title?: string; hit_score?: number }) => (
                                          <button
                                            key={na.ad_id}
                                            className="text-[9px] px-2 py-1 rounded bg-gray-100 text-gray-600 dark:text-gray-300 hover:bg-gray-200 transition-colors truncate max-w-[160px]"
                                            onClick={(e) => { e.stopPropagation(); onAdSelect(na.ad_id); }}
                                            title={na.product_name || na.title}
                                          >
                                            {na.product_name || na.title || `#${na.ad_id}`} ({na.hit_score ?? "-"})
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </>
                              ) : null}
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
        )}

        {/* Advertiser View (B3-4) */}
        {!loading && !isEmpty && filteredAds.length > 0 && viewMode === "advertiser" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {advertiserStats.map((adv) => (
              <div key={adv.name} className="card px-4 py-3 cursor-pointer hover:shadow-md transition-shadow"
                onClick={() => { const first = adv.ads[0]; if (first) handleAdClick(first.ad_id); }}>
                <p className="text-[13px] font-bold text-gray-900 dark:text-gray-100 truncate">{adv.name}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[22px] font-bold text-[#4A7DFF]">{adv.avgScore}</span>
                  <span className="text-[10px] text-gray-400 dark:text-gray-500">avg score</span>
                </div>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <span className="text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500">{adv.ads.length}件</span>
                  {adv.megaHits > 0 && <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-100 text-red-700">大HIT {adv.megaHits}</span>}
                  {adv.hits > 0 && <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700">HIT {adv.hits}</span>}
                </div>
                <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-1">週間消化額増加 {formatYen(adv.totalSpend)}</p>
              </div>
            ))}
          </div>
        )}

        {/* No results after filter — B5-2: More descriptive empty */}
        {!loading && !isEmpty && filteredAds.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <svg className="w-10 h-10 text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <p className="text-[13px] text-gray-500 dark:text-gray-400 dark:text-gray-500 mb-1">条件に一致する広告がありません</p>
            <p className="text-[11px] text-gray-400 dark:text-gray-500 mb-4">フィルター条件を変更するか、全ジャンルを表示してください</p>
            <div className="flex items-center gap-2 flex-wrap justify-center">
              <button onClick={() => setSelectedGenre("all")} className="btn-secondary text-[12px] px-3 py-1.5">
                全ジャンルを表示
              </button>
              {showFilters && (
                <button
                  onClick={() => setFilters(DEFAULT_FILTERS)}
                  className="btn-secondary text-[12px] px-3 py-1.5"
                >
                  フィルターをリセット
                </button>
              )}
            </div>
          </div>
        )}
        </>}
      </div>

      {/* B26: Bulk Actions Bar */}
      <BulkActionsBar
        selectedCount={selectedIds.length}
        onAddToCollection={() => toast.success("コレクションに追加しました")}
        onExport={() => handleExport("csv")}
        onCompare={() => { if (selectedIds.length >= 2) setShowCompare(true); else toast.error("比較には2件以上選択してください"); }}
        onClearSelection={() => setSelectedIds([])}
      />

      {/* B21: Advanced Filter Panel */}
      <AdvancedFilterPanel
        isOpen={showAdvancedFilters}
        onClose={() => setShowAdvancedFilters(false)}
        filters={advancedFilters}
        onApply={(f) => { setAdvancedFilters(f); setShowAdvancedFilters(false); }}
      />

      {/* Compare Modal */}
      {showCompare && selectedIds.length >= 2 && (
        <CreativeCompareView
          adIds={selectedIds.slice(0, 3)}
          onClose={() => setShowCompare(false)}
          onAdSelect={(adId) => {
            setShowCompare(false);
            onAdSelect(adId);
          }}
        />
      )}

      {/* B5-1: Ad Detail Modal */}
      {detailAd && (
        <AdDetailModal
          ad={detailAd}
          onClose={() => setDetailAd(null)}
          onRecoveryQueued={() => {
            void fetchData();
          }}
          onAdSelect={(adId) => {
            setDetailAd(null);
            onAdSelect(adId);
          }}
        />
      )}
    </div>
  );
}
