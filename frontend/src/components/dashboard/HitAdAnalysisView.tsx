"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { platformLabels, platformColors, genreOptions } from "@/lib/constants";
import { formatNumber, formatYen } from "@/lib/format";
import HitAdCardView from "./HitAdCardView";
import AdDetailModal from "./AdDetailModal";
import CreativeCompareView from "../analysis/CreativeCompareView";
import HitPatternPanel from "./HitPatternPanel";
import CopyAnalysisPanel from "./CopyAnalysisPanel";
import CreativeGalleryView from "./CreativeGalleryView";
import CrawlPanel from "./CrawlPanel";
import FreshAdsSection from "./FreshAdsSection";
import TrendCharts from "./TrendCharts";
import MarketOverview from "./MarketOverview";
import AdvertiserLeaderboard from "./AdvertiserLeaderboard";
import WinningFormulas from "./WinningFormulas";
import AdComparisonView from "./AdComparisonView";
import SimilarAdsPanel from "./SimilarAdsPanel";
import AlertsPanel from "./AlertsPanel";
import CollectionsView from "./CollectionsView";
import CreativePlanner from "./CreativePlanner";
import Recommendations from "./Recommendations";
import ScenarioBuilder from "./ScenarioBuilder";
import SavedScenarios from "./SavedScenarios";
import SuccessFailureAnalysis from "./SuccessFailureAnalysis";
import ElementAnalysis from "./ElementAnalysis";
import LPAnalysisPanel from "./LPAnalysisPanel";
import FunnelView from "./FunnelView";
import LPComparison from "./LPComparison";
import CompetitorDashboard from "./CompetitorDashboard";
import CompetitorProfile from "./CompetitorProfile";
import MarketGaps from "./MarketGaps";
import ReportGenerator from "./ReportGenerator";
import ReportsView from "./ReportsView";
import ReportViewer from "./ReportViewer";
import ProRankingTable from "./ProRankingTable";
import ProRankingView from "./ProRankingView";
import SmartSearchBar from "./SmartSearchBar";
import AdvancedFilterPanel, { type AdvancedFilters, defaultFilters, getActiveFilterCount } from "./AdvancedFilterPanel";
import DashboardKPI from "./DashboardKPI";
import ActivityFeed from "./ActivityFeed";
import GenreDistributionChart from "./GenreDistributionChart";
import GenreComparisonView from "./GenreComparisonView";
import GenreTrendChart from "./GenreTrendChart";
import AdComparisonTool from "./AdComparisonTool";
import AdvertiserProfile from "./AdvertiserProfile";
import CalendarView from "./CalendarView";
import AdTimeline from "./AdTimeline";
import AdAnnotations from "./AdAnnotations";
import TeamActivity from "./TeamActivity";
import BulkActionsBar from "./BulkActionsBar";
import CreativeBriefGenerator from "./CreativeBriefGenerator";
import TemplateLibrary from "./TemplateLibrary";
import CopyVariations from "./CopyVariations";
import AnalyticsDashboard from "./AnalyticsDashboard";
import { DarkModeToggle } from "../common/ThemeProvider";

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
  const [scoreDetail, setScoreDetail] = useState<any>(null);
  const [scoreDetailAdId, setScoreDetailAdId] = useState<number | null>(null);
  const [scoreDetailLoading, setScoreDetailLoading] = useState(false);
  const scorePopoverRef = useRef<HTMLDivElement>(null);

  // B4-2: Advertiser detail inline expansion state
  const [advertiserDetail, setAdvertiserDetail] = useState<any>(null);
  const [selectedAdvertiser, setSelectedAdvertiser] = useState<string | null>(null);
  const [advertiserExpandAdId, setAdvertiserExpandAdId] = useState<number | null>(null);
  const [advertiserLoading, setAdvertiserLoading] = useState(false);

  // B4-3: Score distribution from API
  const [scoreDistribution, setScoreDistribution] = useState<any>(null);

  // B6-3: Dashboard summary from API
  const [dashboardSummary, setDashboardSummary] = useState<any>(null);
  // B6-4: Genre comparison from API
  const [genreComparison, setGenreComparison] = useState<any>(null);

  // B8: Creative analysis data
  const [hitFactors, setHitFactors] = useState<any>(null);
  const [copyAnalysis, setCopyAnalysis] = useState<any>(null);

  // B9: Fresh ads refresh key (incremented after crawl completes)
  const [freshAdsKey, setFreshAdsKey] = useState(0);

  // B10: Export dropdown state
  const [showExport, setShowExport] = useState(false);

  // B16: Competitor profile drill-down state
  const [competitorName, setCompetitorName] = useState<string | null>(null);

  // B19: Smart search state for ProRankingTable
  const [proSearchQuery, setProSearchQuery] = useState("");
  const [proPlatformFilter, setProPlatformFilter] = useState<string | undefined>(undefined);
  const [proSortBy, setProSortBy] = useState<string | undefined>(undefined);
  const [proPeriod, setProPeriod] = useState<string | undefined>(undefined);

  // B24: Advertiser profile drill-down state
  const [profileAdvertiser, setProfileAdvertiser] = useState<string | null>(null);

  // B21: Advanced filter panel state
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  const [advancedFilters, setAdvancedFilters] = useState<AdvancedFilters>(defaultFilters);
  const advFilterCount = getActiveFilterCount(advancedFilters);

  // B17: Report viewer state
  const [viewingReport, setViewingReport] = useState<{ id: string | number; format: string } | null>(null);

  const [filters, setFilters] = useState({
    scoreMin: 0,
    scoreMax: 100,
    daysMin: 0,
    daysMax: 9999,
    runningStatus: "all" as "all" | "running" | "stopped",
    sortBy: "score" as "score" | "days" | "spend" | "recent",
    searchText: "",
    creativeType: "all" as "all" | "video" | "image",
    hookType: "all",
    emotion: "all",
    platform: "all",
    dateFrom: "",
    dateTo: "",
    japaneseOnly: true,
    hideDuplicates: true,
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined> = { limit: 50 };
      if (selectedGenre !== "all") params.genre = selectedGenre;

      const [hitRes, genreRes, distRes, summaryRes, genreCompRes, hitFactorsRes, copyRes] = await Promise.all([
        fetchApi<{ total: number; items: HitAd[] }>("/rankings/hit-ads", { params }),
        fetchApi<{ genres: GenreSummary[] }>("/rankings/genre-summary", { params: { period: "weekly" } }),
        fetchApi<any>("/rankings/score-distribution").catch(() => null),
        fetchApi<any>("/rankings/dashboard-summary").catch(() => null),
        fetchApi<any>("/rankings/genre-comparison").catch(() => null),
        fetchApi<any>("/rankings/hit-factors").catch(() => null),
        fetchApi<any>("/rankings/copy-analysis").catch(() => null),
      ]);

      setHitAds(hitRes.items || []);
      setGenres(genreRes.genres || []);
      setScoreDistribution(distRes);
      setDashboardSummary(summaryRes);
      setGenreComparison(genreCompRes);
      setHitFactors(hitFactorsRes);
      setCopyAnalysis(copyRes);
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

  const genreLabel = (value: string | null | undefined): string => {
    if (!value || value === "未分類") return "未分類";
    return genreOptions.find((g) => g.value === value)?.label || value;
  };

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

  // Phase 4: Delivery & confidence stats
  const adsWithDays = hitAds.filter((a) => a.days_running != null && a.days_running > 0);
  const avgDaysRunning = adsWithDays.length > 0 ? Math.round(adsWithDays.reduce((s, a) => s + (a.days_running || 0), 0) / adsWithDays.length) : 0;
  const stillRunningCount = hitAds.filter((a) => a.is_still_running === true).length;
  const realDataCount = hitAds.filter((a) => a.estimation_method === "audience_based").length;
  const estimatedCount = hitAds.length - realDataCount;
  const realDataPct = hitAds.length > 0 ? Math.round((realDataCount / hitAds.length) * 100) : 0;

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
      return true;
    });
    switch (filters.sortBy) {
      case "score": result.sort((a, b) => (b.hit_score || 0) - (a.hit_score || 0)); break;
      case "days": result.sort((a, b) => (b.days_running || 0) - (a.days_running || 0)); break;
      case "spend": result.sort((a, b) => (b.spend_increase || 0) - (a.spend_increase || 0)); break;
      case "recent": result.sort((a, b) => new Date(b.published_date || 0).getTime() - new Date(a.published_date || 0).getTime()); break;
    }
    return result;
  }, [hitAds, filters]);

  const activeFilterCount = (filters.scoreMin > 0 ? 1 : 0) + (filters.scoreMax < 100 ? 1 : 0) + (filters.daysMin > 0 ? 1 : 0) + (filters.daysMax < 9999 ? 1 : 0) + (filters.runningStatus !== "all" ? 1 : 0) + (filters.sortBy !== "score" ? 1 : 0) + (filters.searchText ? 1 : 0) + (filters.creativeType !== "all" ? 1 : 0) + (filters.hookType !== "all" ? 1 : 0) + (filters.emotion !== "all" ? 1 : 0) + (filters.platform !== "all" ? 1 : 0) + (filters.dateFrom ? 1 : 0) + (filters.dateTo ? 1 : 0) + (!filters.japaneseOnly ? 1 : 0) + (!filters.hideDuplicates ? 1 : 0);

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
      const data = await fetchApi(`/rankings/score-breakdown/${adId}`);
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
      const data = await fetchApi(`/rankings/advertiser-detail`, { params: { advertiser_name: name } });
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
      return scoreDistribution.distribution.map((b: any) => ({
        range: b.range_start ?? b.range ?? 0,
        count: b.count ?? 0,
      }));
    }
    if (scoreDistribution?.buckets) {
      return scoreDistribution.buckets.map((b: any) => ({
        range: b.range_start ?? b.range ?? 0,
        count: b.count ?? 0,
      }));
    }
    return null;
  }, [scoreDistribution]);

  const effectiveBuckets = apiBuckets || scoreBuckets;
  const effectiveMaxCount = Math.max(1, ...effectiveBuckets.map((b: any) => b.count));

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
    return <span className="text-gray-400 text-[11px]">→</span>;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between px-5 py-3 border-b border-gray-200 bg-white gap-2">
        <div className="flex items-center gap-3">
          <h2 className="text-[15px] font-bold text-gray-900 whitespace-nowrap">ヒット広告分析</h2>
          <p className="text-[11px] text-gray-400 hidden sm:block">高成長・高スコアの広告をリアルタイムで分析</p>
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
              onClick={() => {
                selectedIds.forEach((id) => {
                  window.open(`/api/v1/media/download/${id}`, "_blank");
                });
                toast.success(`${selectedIds.length}件のダウンロードを開始`);
              }}
              className="h-8 px-3 rounded-lg text-[11px] font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 transition-colors flex items-center gap-1"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              {selectedIds.length}件DL
            </button>
          )}

          {/* View mode toggle */}
          <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode("pro")}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${viewMode === "pro" ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"}`}
            >
              PRO
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${viewMode === "table" ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"}`}
            >
              テーブル
            </button>
            <button
              onClick={() => setViewMode("card")}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${viewMode === "card" ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"}`}
            >
              カード
            </button>
            <button
              onClick={() => setViewMode("advertiser")}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${viewMode === "advertiser" ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"}`}
            >
              広告主別
            </button>
            <button
              onClick={() => setViewMode("gallery")}
              className={`px-2 py-1 rounded text-[11px] transition-colors ${viewMode === "gallery" ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"}`}
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
          <DarkModeToggle />

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
              className="h-8 px-3 rounded-lg text-[11px] font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors flex items-center gap-1.5"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              エクスポート
            </button>
            {showExport && (
              <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-20 min-w-[140px]">
                <button
                  onClick={() => { handleExport("csv"); setShowExport(false); }}
                  className="w-full text-left px-3 py-1.5 text-[11px] text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  CSV エクスポート
                </button>
                <button
                  onClick={() => { handleExport("json"); setShowExport(false); }}
                  className="w-full text-left px-3 py-1.5 text-[11px] text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  JSON エクスポート
                </button>
                <button
                  onClick={() => { handleExport("report"); setShowExport(false); }}
                  className="w-full text-left px-3 py-1.5 text-[11px] text-gray-700 hover:bg-gray-50 transition-colors"
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
        {/* B11: Section tabs */}
        <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5 w-fit">
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
                sectionTab === tab.key ? "bg-white shadow-sm text-gray-900" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* B11: Trends tab */}
        {sectionTab === "trends" && (
          <div className="space-y-4">
            <MarketOverview genre={selectedGenre !== "all" ? selectedGenre : undefined} />
            <TrendCharts genre={selectedGenre !== "all" ? selectedGenre : undefined} />
          </div>
        )}

        {/* B11/B24: Advertisers tab with profile drill-down */}
        {sectionTab === "advertisers" && (
          profileAdvertiser ? (
            <AdvertiserProfile
              advertiserName={profileAdvertiser}
              onAdSelect={(adId) => {
                const ad = hitAds.find((a) => a.ad_id === adId);
                if (ad) setDetailAd(ad);
                else onAdSelect(adId);
              }}
              onBack={() => setProfileAdvertiser(null)}
            />
          ) : (
            <AdvertiserLeaderboard
              genre={selectedGenre !== "all" ? selectedGenre : undefined}
              onAdSelect={onAdSelect}
              onAdvertiserProfile={setProfileAdvertiser}
            />
          )
        )}

        {/* B11: Formulas tab */}
        {sectionTab === "formulas" && (
          <WinningFormulas
            genre={selectedGenre !== "all" ? selectedGenre : undefined}
            onAdSelect={onAdSelect}
          />
        )}

        {/* B11: Market overview tab */}
        {sectionTab === "market" && (
          <MarketOverview genre={selectedGenre !== "all" ? selectedGenre : undefined} />
        )}

        {/* B12: Compare tab */}
        {sectionTab === "compare" && (
          <div className="space-y-4">
            {selectedIds.length < 2 ? (
              <div className="card px-4 py-10 text-center">
                <svg className="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                </svg>
                <p className="text-[13px] font-medium text-gray-600 mb-1">比較する広告を選択してください</p>
                <p className="text-[11px] text-gray-400 mb-3">概要タブのテーブルまたはカードビューで2-4件の広告にチェックを入れてください</p>
                <button
                  onClick={() => setSectionTab("overview")}
                  className="btn-primary text-[12px] px-4 py-2"
                >
                  概要タブに戻る
                </button>
              </div>
            ) : (
              <AdComparisonView
                adIds={selectedIds.slice(0, 4)}
                onClose={() => setSectionTab("overview")}
                onAdSelect={(adId) => {
                  const ad = hitAds.find((a) => a.ad_id === adId);
                  if (ad) setDetailAd(ad);
                  else onAdSelect(adId);
                }}
                inline
              />
            )}
            {/* B24: Standalone comparison tool */}
            <AdComparisonTool onAdSelect={(adId) => {
              const ad = hitAds.find((a) => a.ad_id === adId);
              if (ad) setDetailAd(ad);
              else onAdSelect(adId);
            }} />
          </div>
        )}

        {/* B13: Collections tab */}
        {sectionTab === "collections" && (
          <CollectionsView onAdSelect={(adId) => {
            const ad = hitAds.find((a) => a.ad_id === adId);
            if (ad) setDetailAd(ad);
            else onAdSelect(adId);
          }} />
        )}

        {/* B14: AI Insights tab */}
        {sectionTab === "ai" && (
          <div className="space-y-4">
            <CreativePlanner
              genre={selectedGenre !== "all" ? selectedGenre : undefined}
              onAdSelect={(adId) => {
                const ad = hitAds.find((a) => a.ad_id === adId);
                if (ad) setDetailAd(ad);
                else onAdSelect(adId);
              }}
            />
            <Recommendations
              genre={selectedGenre !== "all" ? selectedGenre : undefined}
              onAdSelect={(adId) => {
                const ad = hitAds.find((a) => a.ad_id === adId);
                if (ad) setDetailAd(ad);
                else onAdSelect(adId);
              }}
            />
          </div>
        )}

        {/* B20: Scenario tab */}
        {sectionTab === "scenario" && (
          <div className="space-y-4">
            <ScenarioBuilder />
            <SavedScenarios onLoad={(id) => { /* TODO: load scenario into builder */ }} />
          </div>
        )}

        {/* B21: Deep Analysis tab */}
        {sectionTab === "deep-analysis" && (
          <div className="space-y-4">
            <SuccessFailureAnalysis
              genre={selectedGenre !== "all" ? selectedGenre : undefined}
              onAdSelect={(adId) => {
                const ad = hitAds.find((a) => a.ad_id === adId);
                if (ad) setDetailAd(ad);
                else onAdSelect(adId);
              }}
            />
            <ElementAnalysis
              genre={selectedGenre !== "all" ? selectedGenre : undefined}
              onElementFilter={(category, element) => {
                /* TODO: Apply element filter to ad list */
              }}
            />
          </div>
        )}

        {/* B15: LP Analysis tab */}
        {sectionTab === "lp" && (
          <div className="space-y-4">
            <LPAnalysisPanel genre={selectedGenre !== "all" ? selectedGenre : undefined} />
            <FunnelView
              adIds={selectedIds.length > 0 ? selectedIds : filteredAds.slice(0, 6).map((a) => a.ad_id)}
              onAdSelect={(adId) => {
                const ad = hitAds.find((a) => a.ad_id === adId);
                if (ad) setDetailAd(ad);
                else onAdSelect(adId);
              }}
            />
            {selectedIds.length >= 2 && (
              <LPComparison adIds={selectedIds.slice(0, 3)} />
            )}
          </div>
        )}

        {/* B16: Competitors tab */}
        {sectionTab === "competitors" && (
          competitorName ? (
            <CompetitorProfile
              name={competitorName}
              onBack={() => setCompetitorName(null)}
              onAdSelect={(adId) => {
                const ad = hitAds.find((a) => a.ad_id === adId);
                if (ad) setDetailAd(ad);
                else onAdSelect(adId);
              }}
            />
          ) : (
            <div className="space-y-4">
              <CompetitorDashboard
                genre={selectedGenre !== "all" ? selectedGenre : undefined}
                onAdSelect={(adId) => {
                  const ad = hitAds.find((a) => a.ad_id === adId);
                  if (ad) setDetailAd(ad);
                  else onAdSelect(adId);
                }}
                onCompetitorSelect={(name) => setCompetitorName(name)}
              />
              <MarketGaps genre={selectedGenre !== "all" ? selectedGenre : undefined} />
            </div>
          )
        )}

        {/* B17/B22: Reports tab — ReportsView dashboard + ReportGenerator */}
        {sectionTab === "reports" && (
          viewingReport ? (
            <ReportViewer
              reportId={viewingReport.id}
              format={viewingReport.format}
              onBack={() => setViewingReport(null)}
            />
          ) : (
            <div className="space-y-4">
              <ReportsView
                genre={selectedGenre !== "all" ? selectedGenre : undefined}
                onAdSelect={(adId) => {
                  const ad = hitAds.find((a) => a.ad_id === adId);
                  if (ad) setDetailAd(ad);
                  else onAdSelect(adId);
                }}
              />
              <ReportGenerator
                genre={selectedGenre !== "all" ? selectedGenre : undefined}
                onViewReport={(report) => setViewingReport({ id: report.id, format: report.format })}
              />
            </div>
          )
        )}

        {/* B25: Calendar tab */}
        {sectionTab === "calendar" && (
          <div className="space-y-4">
            <CalendarView />
            <AdTimeline />
          </div>
        )}

        {/* B26: Team tab */}
        {sectionTab === "team" && (
          <TeamActivity />
        )}

        {/* B28: Creative Brief tab */}
        {sectionTab === "brief" && (
          <div className="space-y-4">
            <CreativeBriefGenerator genre={selectedGenre !== "all" ? selectedGenre : undefined} />
            <TemplateLibrary />
            <CopyVariations />
          </div>
        )}

        {/* B30: Analytics Dashboard tab */}
        {sectionTab === "analytics" && (
          <AnalyticsDashboard
            genre={selectedGenre !== "all" ? selectedGenre : undefined}
            onAdSelect={(adId) => {
              const ad = hitAds.find((a) => a.ad_id === adId);
              if (ad) setDetailAd(ad);
              else onAdSelect(adId);
            }}
          />
        )}

        {/* B32: Genre analysis tab */}
        {sectionTab === "genre" && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <GenreDistributionChart
                period={proPeriod || "7d"}
                onGenreClick={(genre) => setSelectedGenre(genre)}
              />
              <GenreComparisonView period={proPeriod || "7d"} />
            </div>
            <GenreTrendChart
              period={proPeriod || "30d"}
              onGenreClick={(genre) => setSelectedGenre(genre)}
            />
          </div>
        )}

        {/* Overview tab content (existing) */}
        {sectionTab === "overview" && <>
        {/* Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <div className="card px-4 py-3">
            <p className="text-[11px] text-gray-400 font-medium">ヒット広告数</p>
            <p className="text-[22px] font-bold text-gray-900 mt-0.5">{totalHits}<span className="text-[13px] text-gray-400 ml-1">件</span></p>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              {megaHitCount > 0 && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-medium">大HIT {megaHitCount}</span>
              )}
              {hitCount > 0 && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 font-medium">HIT {hitCount}</span>
              )}
              <span className="text-[10px] text-gray-400">/ 全{totalAdsCount}件</span>
              {activeAdsCount != null && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-medium">アクティブ {activeAdsCount}</span>
              )}
            </div>
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
            <p className="text-[15px] font-bold text-gray-900 mt-0.5 truncate">
              {topGenreFromApi ? genreLabel(topGenreFromApi) : topGenre ? genreLabel(topGenre.genre) : "-"}
            </p>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <p className="text-[10px] text-gray-400">{topGenre ? `${topGenre.ad_count}件 / ${topGenre.advertiser_count}社` : "データなし"}</p>
              {topCreativeType && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 font-medium">
                  {topCreativeType === "video" ? "動画" : topCreativeType === "image" ? "静止画" : topCreativeType}
                </span>
              )}
            </div>
          </div>
          <div className="card px-4 py-3">
            <p className="text-[11px] text-gray-400 font-medium">市場推定消化額</p>
            <p className="text-[22px] font-bold text-gray-900 mt-0.5">{formatYen(totalSpend)}</p>
            <p className="text-[10px] text-gray-400 mt-1">{genres.length}ジャンル合計 (週間)</p>
          </div>
          <div className="card px-4 py-3">
            <p className="text-[11px] text-gray-400 font-medium">平均配信日数</p>
            <p className="text-[22px] font-bold text-gray-900 mt-0.5">
              {avgDaysRunning > 0 ? avgDaysRunning : "-"}
              {avgDaysRunning > 0 && <span className="text-[13px] text-gray-400 ml-1">日</span>}
            </p>
            <p className="text-[10px] text-gray-400 mt-1">
              {stillRunningCount > 0 ? (
                <><span className="text-emerald-600 font-medium">● {stillRunningCount}件</span> 配信中</>
              ) : "配信中なし"}
            </p>
          </div>
          <div className="card px-4 py-3">
            <p className="text-[11px] text-gray-400 font-medium">データ信頼度</p>
            <p className="text-[22px] font-bold mt-0.5" style={{ color: realDataPct >= 50 ? "#10b981" : "#f59e0b" }}>
              {realDataPct}<span className="text-[13px] text-gray-400 ml-1">%</span>
            </p>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-green-100 text-green-700">実データ {realDataCount}</span>
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">推定 {estimatedCount}</span>
            </div>
          </div>
        </div>

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
              <p className="text-[11px] text-gray-400 font-medium">スコア分布</p>
              {scoreDistribution && (
                <div className="flex items-center gap-3">
                  {scoreDistribution.mean != null && (
                    <span className="text-[9px] text-gray-500">平均: <span className="font-medium text-gray-700">{Math.round(scoreDistribution.mean)}</span></span>
                  )}
                  {scoreDistribution.median != null && (
                    <span className="text-[9px] text-gray-500">中央値: <span className="font-medium text-gray-700">{scoreDistribution.median}</span></span>
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
              {effectiveBuckets.map((bucket: any, i: number) => (
                <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                  <div
                    className={`w-full rounded-t-sm ${bucket.range >= 70 ? "bg-red-400" : bucket.range >= 45 ? "bg-orange-400" : "bg-gray-300"}`}
                    style={{ height: `${(bucket.count / effectiveMaxCount) * 100}%`, minHeight: bucket.count > 0 ? "2px" : "0" }}
                    title={`${bucket.range}-${bucket.range + 9}: ${bucket.count}件`}
                  />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-[8px] text-gray-400 mt-1">
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
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowFilters(!showFilters)}
                className="text-[11px] px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors flex items-center gap-1"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z" />
                </svg>
                フィルター {showFilters ? "▲" : "▼"}
              </button>
              {activeFilterCount > 0 && (
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#4A7DFF] text-white font-medium">{activeFilterCount}</span>
              )}
              <span className="text-[10px] text-gray-400 ml-auto">{filteredAds.length}件表示 / 全{hitAds.length}件</span>
            </div>
            {showFilters && (
              <div className="card px-4 py-3 space-y-3">
                {/* B10-3: Search input */}
                <div className="relative">
                  <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                  </svg>
                  <input
                    type="text"
                    placeholder="商材名、広告主、テキストで検索..."
                    value={filters.searchText}
                    onChange={(e) => setFilters((f) => ({ ...f, searchText: e.target.value }))}
                    className="w-full h-8 pl-8 pr-3 rounded-lg border border-gray-200 text-[11px] text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF] focus:border-[#4A7DFF]"
                  />
                  {filters.searchText && (
                    <button
                      onClick={() => setFilters((f) => ({ ...f, searchText: "" }))}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                {/* Score range presets + slider */}
                <div>
                  <p className="text-[10px] text-gray-400 font-medium mb-1.5">
                    スコア範囲
                    {(filters.scoreMin > 0 || filters.scoreMax < 100) && (
                      <span className="ml-1 text-[#4A7DFF] font-bold">{filters.scoreMin}-{filters.scoreMax}</span>
                    )}
                  </p>
                  <div className="flex flex-wrap gap-1 mb-1.5">
                    {([
                      { label: "全て", min: 0, max: 100 },
                      { label: "大HIT (70+)", min: 70, max: 100 },
                      { label: "HIT (45+)", min: 45, max: 100 },
                      { label: "低スコア", min: 0, max: 44 },
                    ]).map((p) => (
                      <button
                        key={p.label}
                        onClick={() => setFilters((f) => ({ ...f, scoreMin: p.min, scoreMax: p.max }))}
                        className={`text-[9px] px-2 py-1 rounded transition-colors ${filters.scoreMin === p.min && filters.scoreMax === p.max ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={filters.scoreMin}
                      onChange={(e) => setFilters((f) => ({ ...f, scoreMin: Math.min(Number(e.target.value), f.scoreMax) }))}
                      className="flex-1 h-1 accent-[#4A7DFF]"
                    />
                    <input
                      type="range"
                      min={0}
                      max={100}
                      value={filters.scoreMax}
                      onChange={(e) => setFilters((f) => ({ ...f, scoreMax: Math.max(Number(e.target.value), f.scoreMin) }))}
                      className="flex-1 h-1 accent-[#4A7DFF]"
                    />
                  </div>
                </div>
                {/* Days range presets */}
                <div>
                  <p className="text-[10px] text-gray-400 font-medium mb-1.5">配信日数</p>
                  <div className="flex flex-wrap gap-1">
                    {([
                      { label: "全期間", min: 0, max: 9999 },
                      { label: "30日+", min: 30, max: 9999 },
                      { label: "60日+", min: 60, max: 9999 },
                      { label: "90日+", min: 90, max: 9999 },
                    ]).map((p) => (
                      <button
                        key={p.label}
                        onClick={() => setFilters((f) => ({ ...f, daysMin: p.min, daysMax: p.max }))}
                        className={`text-[9px] px-2 py-1 rounded transition-colors ${filters.daysMin === p.min && filters.daysMax === p.max ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Running status */}
                <div>
                  <p className="text-[10px] text-gray-400 font-medium mb-1.5">配信状態</p>
                  <select
                    value={filters.runningStatus}
                    onChange={(e) => setFilters((f) => ({ ...f, runningStatus: e.target.value as "all" | "running" | "stopped" }))}
                    className="select-filter text-[11px] h-7 w-full"
                  >
                    <option value="all">全て</option>
                    <option value="running">配信中</option>
                    <option value="stopped">停止済み</option>
                  </select>
                </div>
                {/* Sort */}
                <div>
                  <p className="text-[10px] text-gray-400 font-medium mb-1.5">ソート順</p>
                  <select
                    value={filters.sortBy}
                    onChange={(e) => setFilters((f) => ({ ...f, sortBy: e.target.value as "score" | "days" | "spend" | "recent" }))}
                    className="select-filter text-[11px] h-7 w-full"
                  >
                    <option value="score">スコア順</option>
                    <option value="days">配信日数順</option>
                    <option value="spend">消化額順</option>
                    <option value="recent">最新順</option>
                  </select>
                </div>
                {/* B10-3: Creative type filter */}
                <div>
                  <p className="text-[10px] text-gray-400 font-medium mb-1.5">クリエイティブ</p>
                  <select
                    value={filters.creativeType}
                    onChange={(e) => setFilters((f) => ({ ...f, creativeType: e.target.value as "all" | "video" | "image" }))}
                    className="select-filter text-[11px] h-7 w-full"
                  >
                    <option value="all">全て</option>
                    <option value="video">動画</option>
                    <option value="image">静止画</option>
                  </select>
                </div>
                {/* B10-3: Platform filter */}
                <div>
                  <p className="text-[10px] text-gray-400 font-medium mb-1.5">媒体</p>
                  <select
                    value={filters.platform}
                    onChange={(e) => setFilters((f) => ({ ...f, platform: e.target.value }))}
                    className="select-filter text-[11px] h-7 w-full"
                  >
                    <option value="all">全媒体</option>
                    {Object.entries(platformLabels).map(([k, v]) => (
                      <option key={k} value={k}>{v}</option>
                    ))}
                  </select>
                </div>
                </div>
                {/* B10: Additional filters row */}
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 pt-2 border-t border-gray-100">
                  {/* Hook type filter */}
                  <div>
                    <p className="text-[10px] text-gray-400 font-medium mb-1.5">フックタイプ</p>
                    <select
                      value={filters.hookType}
                      onChange={(e) => setFilters((f) => ({ ...f, hookType: e.target.value }))}
                      className="select-filter text-[11px] h-7 w-full"
                    >
                      <option value="all">全フック</option>
                      <option value="question">質問型</option>
                      <option value="pain_point">悩み訴求</option>
                      <option value="benefit">ベネフィット</option>
                      <option value="curiosity">好奇心</option>
                      <option value="social_proof">社会的証明</option>
                      <option value="urgency">緊急性</option>
                      <option value="storytelling">ストーリー</option>
                      <option value="number">数字訴求</option>
                      <option value="comparison">比較</option>
                      <option value="authority">権威性</option>
                    </select>
                  </div>
                  {/* Emotion filter */}
                  <div>
                    <p className="text-[10px] text-gray-400 font-medium mb-1.5">感情訴求</p>
                    <select
                      value={filters.emotion}
                      onChange={(e) => setFilters((f) => ({ ...f, emotion: e.target.value }))}
                      className="select-filter text-[11px] h-7 w-full"
                    >
                      <option value="all">全て</option>
                      <option value="fear">不安</option>
                      <option value="hope">希望</option>
                      <option value="anger">怒り</option>
                      <option value="joy">喜び</option>
                      <option value="surprise">驚き</option>
                      <option value="trust">信頼</option>
                      <option value="desire">欲望</option>
                      <option value="relief">安心</option>
                      <option value="curiosity">好奇心</option>
                    </select>
                  </div>
                  {/* Date range: from */}
                  <div>
                    <p className="text-[10px] text-gray-400 font-medium mb-1.5">掲載開始日（から）</p>
                    <input
                      type="date"
                      value={filters.dateFrom}
                      onChange={(e) => setFilters((f) => ({ ...f, dateFrom: e.target.value }))}
                      className="w-full h-7 px-2 rounded-lg border border-gray-200 text-[11px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF] focus:border-[#4A7DFF]"
                    />
                  </div>
                  {/* Date range: to */}
                  <div>
                    <p className="text-[10px] text-gray-400 font-medium mb-1.5">掲載開始日（まで）</p>
                    <input
                      type="date"
                      value={filters.dateTo}
                      onChange={(e) => setFilters((f) => ({ ...f, dateTo: e.target.value }))}
                      className="w-full h-7 px-2 rounded-lg border border-gray-200 text-[11px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF] focus:border-[#4A7DFF]"
                    />
                  </div>
                  {/* B18: Language & duplicate toggles */}
                  <div>
                    <label className="flex items-center gap-1.5 cursor-pointer mt-1">
                      <input
                        type="checkbox"
                        checked={filters.japaneseOnly}
                        onChange={(e) => setFilters((f) => ({ ...f, japaneseOnly: e.target.checked }))}
                        className="w-3 h-3 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]"
                      />
                      <span className="text-[10px] text-gray-600">日本語のみ</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer mt-1">
                      <input
                        type="checkbox"
                        checked={filters.hideDuplicates}
                        onChange={(e) => setFilters((f) => ({ ...f, hideDuplicates: e.target.checked }))}
                        className="w-3 h-3 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]"
                      />
                      <span className="text-[10px] text-gray-600">重複を非表示</span>
                    </label>
                  </div>
                  {/* Reset all filters */}
                  <div className="flex items-end">
                    <button
                      onClick={() => setFilters({ scoreMin: 0, scoreMax: 100, daysMin: 0, daysMax: 9999, runningStatus: "all", sortBy: "score", searchText: "", creativeType: "all", hookType: "all", emotion: "all", platform: "all", dateFrom: "", dateTo: "", japaneseOnly: true, hideDuplicates: true })}
                      className="h-7 px-3 rounded-lg text-[10px] font-medium text-gray-500 bg-gray-100 hover:bg-gray-200 transition-colors w-full"
                    >
                      リセット
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Winning Pattern Analysis */}
        {!loading && hitOnly.length > 0 && (
          <div className="card px-4 py-4">
            <div className="flex items-center gap-2 mb-3">
              <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
              </svg>
              <h3 className="text-[13px] font-bold text-gray-900">勝ちパターン分析</h3>
              <span className="text-[10px] text-gray-400">ヒット広告{hitOnly.length}件の共通傾向</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Genre breakdown */}
              <div>
                <p className="text-[10px] text-gray-400 font-medium mb-2">ジャンル分布</p>
                <div className="space-y-1.5">
                  {sortedGenres.slice(0, 4).map(([genre, count]) => {
                    const pct = Math.round((count / hitOnly.length) * 100);
                    return (
                      <div key={genre} className="flex items-center gap-2">
                        <span className="text-[10px] text-gray-600 w-16 truncate" title={genreLabel(genre)}>{genreLabel(genre)}</span>
                        <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div className="h-full rounded-full bg-[#4A7DFF]" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="text-[10px] text-gray-500 w-8 text-right">{pct}%</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Platform breakdown */}
              <div>
                <p className="text-[10px] text-gray-400 font-medium mb-2">媒体分布</p>
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
                        <span className="text-[10px] text-gray-500 w-8 text-right">{pct}%</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Key metrics */}
              <div>
                <p className="text-[10px] text-gray-400 font-medium mb-2">ヒット広告の平均値</p>
                <div className="space-y-2">
                  <div className="flex items-center justify-between py-1 border-b border-gray-50">
                    <span className="text-[10px] text-gray-500">消化額増加/週</span>
                    <span className="text-[11px] font-semibold text-gray-900">{formatYen(avgSpendIncrease)}</span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-gray-50">
                    <span className="text-[10px] text-gray-500">再生数増加/週</span>
                    <span className="text-[11px] font-semibold text-gray-900">{formatNumber(avgViewIncrease)}</span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-gray-50">
                    <span className="text-[10px] text-gray-500">平均ヒットスコア</span>
                    <span className="text-[11px] font-semibold text-[#4A7DFF]">{avgHitScore}/100</span>
                  </div>
                  <div className="flex items-center justify-between py-1">
                    <span className="text-[10px] text-gray-500">トップジャンル</span>
                    <span className="badge-blue text-[9px]">{sortedGenres[0] ? genreLabel(sortedGenres[0][0]) : "-"}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* B6-4: Genre Comparison Chart (horizontal bar chart from API) */}
        {!loading && genreComparison && (() => {
          const items: any[] = genreComparison.genres || genreComparison.items || (Array.isArray(genreComparison) ? genreComparison : []);
          if (!Array.isArray(items) || items.length === 0) return null;
          const sorted = [...items].sort((a: any, b: any) => (b.ad_count || b.total_ads || 0) - (a.ad_count || a.total_ads || 0)).slice(0, 10);
          const maxCount = Math.max(1, ...sorted.map((g: any) => g.ad_count || g.total_ads || 0));
          const maxScore = Math.max(1, ...sorted.map((g: any) => g.avg_score || g.avg_hit_score || 0));
          return (
            <div className="card px-4 py-4">
              <div className="flex items-center gap-2 mb-3">
                <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                </svg>
                <h3 className="text-[13px] font-bold text-gray-900">ジャンル比較</h3>
                <span className="text-[10px] text-gray-400">{sorted.length}ジャンルの広告数・平均スコア比較</span>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Ad count bar chart */}
                <div>
                  <p className="text-[10px] text-gray-400 font-medium mb-2">広告数</p>
                  <div className="space-y-1.5">
                    {sorted.map((g: any, i: number) => {
                      const count = g.ad_count || g.total_ads || 0;
                      const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
                      return (
                        <div key={g.genre || i} className="flex items-center gap-2">
                          <span className="text-[10px] text-gray-600 w-20 truncate shrink-0" title={genreLabel(g.genre)}>
                            {genreLabel(g.genre)}
                          </span>
                          <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden relative">
                            <div
                              className="h-full rounded bg-[#4A7DFF] transition-all"
                              style={{ width: `${pct}%` }}
                            />
                            <span className="absolute inset-y-0 right-1.5 flex items-center text-[9px] font-medium text-gray-600">
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
                  <p className="text-[10px] text-gray-400 font-medium mb-2">平均スコア</p>
                  <div className="space-y-1.5">
                    {sorted.map((g: any, i: number) => {
                      const score = Math.round(g.avg_score || g.avg_hit_score || 0);
                      const pct = maxScore > 0 ? (score / maxScore) * 100 : 0;
                      const hitRate = g.hit_rate != null ? Math.round((typeof g.hit_rate === "number" && g.hit_rate <= 1 ? g.hit_rate * 100 : g.hit_rate)) : null;
                      return (
                        <div key={g.genre || i} className="flex items-center gap-2">
                          <span className="text-[10px] text-gray-600 w-20 truncate shrink-0" title={genreLabel(g.genre)}>
                            {genreLabel(g.genre)}
                          </span>
                          <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden relative">
                            <div
                              className="h-full rounded transition-all"
                              style={{
                                width: `${pct}%`,
                                backgroundColor: score >= 70 ? "#ef4444" : score >= 45 ? "#f59e0b" : "#4A7DFF",
                              }}
                            />
                            <span className="absolute inset-y-0 right-1.5 flex items-center text-[9px] font-medium text-gray-600">
                              {score}
                              {hitRate != null && (
                                <span className="ml-1 text-[8px] text-gray-400">({hitRate}%HIT)</span>
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
            <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
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
            <p className="text-[14px] font-medium text-gray-600 mb-1">ランキングデータがありません</p>
            <p className="text-[12px] text-gray-400 mb-2 max-w-sm">
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
          <CreativeGalleryView ads={filteredAds} onAdSelect={handleAdClick} />
        )}

        {/* Hit Ads — Table View */}
        {!loading && !isEmpty && filteredAds.length > 0 && viewMode === "table" && (
          <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
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
                            ad.rank <= 3 ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-500"
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
                            <span className="text-[13px] font-medium text-gray-900 truncate max-w-[200px]">
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
                            <p className="text-[10px] text-gray-400 truncate max-w-[240px] mt-0.5" title={ad.description}>
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
                              <span className="text-[11px] font-semibold text-gray-700 w-7 text-right">{ad.hit_score || 0}</span>
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
                                          <span className="text-[9px] w-16 text-gray-500">{signalLabels[key] || key}</span>
                                          <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                                            <div
                                              className="h-full rounded-full"
                                              style={{ width: `${sig.max > 0 ? (sig.score / sig.max) * 100 : 0}%`, backgroundColor: signalColors[key] || "#6b7280" }}
                                            />
                                          </div>
                                          <span className="text-[9px] text-gray-600 w-10 text-right">{sig.score}/{sig.max}</span>
                                        </div>
                                        {sig.detail && (
                                          <p className="text-[8px] text-gray-400 ml-[72px] mt-0.5">{sig.detail}</p>
                                        )}
                                      </div>
                                    ))}
                                  </>
                                ) : (
                                  <p className="text-[11px] text-gray-400">データなし</p>
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
                              <p className="text-[8px] text-gray-400 mt-0.5">{ad.hit_score}/100</p>
                            </div>
                          ) : (
                            <span className="text-[10px] text-gray-300">-</span>
                          )}
                        </td>
                        {/* Trend Score */}
                        <td className="text-right">
                          <span className="text-[12px] font-medium text-gray-700">{ad.trend_score || 0}</span>
                        </td>
                        {/* Spend Increase */}
                        <td className="text-right">
                          <span className="text-[13px] font-semibold text-gray-900">{formatYen(ad.spend_increase || 0)}</span>
                        </td>
                        {/* Cumulative Spend */}
                        <td className="text-right">
                          <span className="text-[12px] text-gray-500">{formatYen(ad.cumulative_spend || 0)}</span>
                        </td>
                        {/* View Increase */}
                        <td className="text-right">
                          <span className="text-[13px] font-medium text-gray-700">{formatNumber(ad.view_increase || 0)}</span>
                        </td>
                        {/* Cumulative Views */}
                        <td className="text-right">
                          <span className="text-[12px] text-gray-500">{formatNumber(ad.cumulative_views || 0)}</span>
                        </td>
                        {/* Like Count */}
                        <td className="text-right">
                          <span className="text-[12px] text-gray-600">{formatNumber(ad.like_count || 0)}</span>
                        </td>
                        {/* Published Date */}
                        <td>
                          <span className="text-[11px] text-gray-500 whitespace-nowrap">
                            {ad.published_date ? new Date(ad.published_date).toLocaleDateString("ja-JP") : "-"}
                          </span>
                        </td>
                        {/* Days Running */}
                        <td>
                          <div className="flex items-center gap-1">
                            <span className="text-[12px] font-medium text-gray-700">
                              {ad.days_running || "-"}
                              {ad.days_running != null && (
                                <span className="text-[10px] text-gray-400 ml-0.5">日</span>
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
                                <p className="text-[12px] font-bold text-gray-900">
                                  {advertiserDetail.advertiser_name || ad.advertiser_name} の広告分析
                                </p>
                                <button
                                  className="text-[10px] text-gray-400 hover:text-gray-600 transition-colors"
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
                              ) : (
                                <>
                                  {/* Stats row */}
                                  <div className="flex items-center gap-4">
                                    {advertiserDetail.total_ads != null && (
                                      <div className="text-center">
                                        <p className="text-[16px] font-bold text-gray-900">{advertiserDetail.total_ads}</p>
                                        <p className="text-[9px] text-gray-400">広告数</p>
                                      </div>
                                    )}
                                    {advertiserDetail.active_ads != null && (
                                      <div className="text-center">
                                        <p className="text-[16px] font-bold text-emerald-600">{advertiserDetail.active_ads}</p>
                                        <p className="text-[9px] text-gray-400">アクティブ</p>
                                      </div>
                                    )}
                                    {advertiserDetail.avg_score != null && (
                                      <div className="text-center">
                                        <p className="text-[16px] font-bold text-[#4A7DFF]">{Math.round(advertiserDetail.avg_score)}</p>
                                        <p className="text-[9px] text-gray-400">平均スコア</p>
                                      </div>
                                    )}
                                    {advertiserDetail.total_spend != null && (
                                      <div className="text-center">
                                        <p className="text-[16px] font-bold text-gray-900">{formatYen(advertiserDetail.total_spend)}</p>
                                        <p className="text-[9px] text-gray-400">推定消化額</p>
                                      </div>
                                    )}
                                    {advertiserDetail.estimated_spend != null && advertiserDetail.total_spend == null && (
                                      <div className="text-center">
                                        <p className="text-[16px] font-bold text-gray-900">{formatYen(advertiserDetail.estimated_spend)}</p>
                                        <p className="text-[9px] text-gray-400">推定消化額</p>
                                      </div>
                                    )}
                                  </div>
                                  {/* Hit ads list */}
                                  {advertiserDetail.hit_ads && advertiserDetail.hit_ads.length > 0 && (
                                    <div>
                                      <p className="text-[10px] text-gray-500 font-medium mb-1">ヒット広告</p>
                                      <div className="flex flex-wrap gap-1.5">
                                        {advertiserDetail.hit_ads.slice(0, 8).map((ha: any) => (
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
                                      <p className="text-[10px] text-gray-500 font-medium mb-1">その他の広告</p>
                                      <div className="flex flex-wrap gap-1.5">
                                        {advertiserDetail.non_hit_ads.slice(0, 6).map((na: any) => (
                                          <button
                                            key={na.ad_id}
                                            className="text-[9px] px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors truncate max-w-[160px]"
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
                              )}
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
                <p className="text-[13px] font-bold text-gray-900 truncate">{adv.name}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[22px] font-bold text-[#4A7DFF]">{adv.avgScore}</span>
                  <span className="text-[10px] text-gray-400">avg score</span>
                </div>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <span className="text-[10px] text-gray-500">{adv.ads.length}件</span>
                  {adv.megaHits > 0 && <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-100 text-red-700">大HIT {adv.megaHits}</span>}
                  {adv.hits > 0 && <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700">HIT {adv.hits}</span>}
                </div>
                <p className="text-[10px] text-gray-400 mt-1">週間消化額増加 {formatYen(adv.totalSpend)}</p>
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
            <p className="text-[13px] text-gray-500 mb-1">条件に一致する広告がありません</p>
            <p className="text-[11px] text-gray-400 mb-4">フィルター条件を変更するか、全ジャンルを表示してください</p>
            <div className="flex items-center gap-2 flex-wrap justify-center">
              <button onClick={() => setSelectedGenre("all")} className="btn-secondary text-[12px] px-3 py-1.5">
                全ジャンルを表示
              </button>
              {showFilters && (
                <button
                  onClick={() => setFilters({ scoreMin: 0, scoreMax: 100, daysMin: 0, daysMax: 9999, runningStatus: "all", sortBy: "score", searchText: "", creativeType: "all", hookType: "all", emotion: "all", platform: "all", dateFrom: "", dateTo: "", japaneseOnly: true, hideDuplicates: true })}
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
          onAdSelect={(adId) => {
            setDetailAd(null);
            onAdSelect(adId);
          }}
        />
      )}
    </div>
  );
}
