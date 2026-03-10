"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { cachedFetchApi } from "@/lib/prefetch";
import { useUrlParam } from "@/lib/useUrlParam";
import { genreOptions } from "@/lib/constants";
import SmartSearchBar from "./SmartSearchBar";
import ProRankingTable from "./ProRankingTable";
import AdvancedFilterPanel, { type AdvancedFilters, defaultFilters, getActiveFilterCount } from "./AdvancedFilterPanel";
import SavedViews from "../common/SavedViews";
import QuickFilterBar, { type QuickFilterKey } from "../common/QuickFilterBar";
import CustomKPICards from "./CustomKPICards";
import ActivityFeed from "./ActivityFeed";

// ─── Types ───

interface GenreMasterItem {
  value: string;
  label: string;
  parent?: string;
  count?: number;
}

interface GenreGroup {
  parent: string;
  items: GenreMasterItem[];
}

interface FacetItem {
  name: string;
  count: number;
}

interface SearchCollection {
  id: number;
  name: string;
  filters: {
    genre?: string;
    platform?: string;
    query?: string;
    sortBy?: string;
    period?: string;
    snapshotDate?: string;
    topic?: string;
    transitionType?: string;
    adFormat?: "all" | "video" | "banner" | "carousel";
    isAffiliate?: "all" | "true" | "false";
    column_filters?: {
      local_search?: string;
    };
    column_sort?: {
      field?: string;
      direction?: "asc" | "desc";
    };
    advancedFilters?: AdvancedFilters;
  };
  created_at?: string;
  updated_at?: string;
  last_used_at?: string;
}

interface PendingImport {
  name: string;
  filters: Record<string, unknown>;
  normalizationNotes?: Array<{ key: string; before: string; after: string }>;
}

interface FilterDiffItem {
  key: string;
  label: string;
  before: string;
  after: string;
}

type PeriodType = "2d" | "7d" | "14d" | "30d" | "all";
type SortType =
  | "cumulative_views"
  | "cumulative_spend"
  | "view_increase"
  | "like_increase"
  | "hit_score";
type ViewModeType = "table" | "card" | "gallery";

// ─── Constants ───

const periodOptions: { value: PeriodType; label: string }[] =
  [
    { value: "2d", label: "2日間" },
    { value: "7d", label: "1週間" },
    { value: "14d", label: "2週間" },
    { value: "30d", label: "1ヶ月" },
    { value: "all", label: "全期間" },
  ];
const periodLabelMap: Record<PeriodType, string> = {
  "2d": "2日間",
  "7d": "1週間",
  "14d": "2週間",
  "30d": "1ヶ月",
  "all": "全期間",
};

const sortOptions: { value: SortType; label: string }[] = [
  { value: "cumulative_views", label: "再生数順" },
  { value: "cumulative_spend", label: "消化額順" },
  { value: "like_increase", label: "いいね順" },
  { value: "hit_score", label: "スコア順" },
];

const platformFilterOptions = [
  { value: "all", label: "全媒体" },
  { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" },
  { value: "tiktok", label: "TikTok" },
  { value: "youtube", label: "YouTube" },
  { value: "line", label: "LINE" },
  { value: "x_twitter", label: "X" },
];

const topicFilterOptions = [
  { value: "all", label: "全トピック" },
  { value: "medical_diet", label: "医療ダイエット" },
  { value: "aga", label: "AGA" },
  { value: "beauty", label: "美容" },
  { value: "finance", label: "金融" },
  { value: "education", label: "教育" },
];

const quickTopicOptions = [
  { value: "medical_diet", label: "GLP-1/医療" },
  { value: "aga", label: "AGA" },
  { value: "beauty", label: "美容" },
  { value: "finance", label: "金融" },
];

// ─── Parent genre groups ───
const genreGroupLabels: Record<string, string> = {
  beauty: "美容系",
  health: "健康系",
  business: "ビジネス系",
  lifestyle: "ライフスタイル系",
  other: "その他",
};

const normalizeTransitionFilter = (v: string | undefined): string => {
  const key = (v || "").toLowerCase();
  if (key === "article_lp" || key === "survey_lp" || key === "manga_lp" || key === "other") return key;
  return "all";
};

const normalizeAdFormatFilter = (v: string | undefined): "all" | "video" | "banner" | "carousel" => {
  const key = (v || "").toLowerCase();
  if (key === "video" || key === "banner" || key === "carousel") return key;
  return "all";
};

const normalizeAffiliateFilter = (v: string | undefined): "all" | "true" | "false" => {
  const key = (v || "").toLowerCase();
  if (key === "true" || key === "false") return key;
  return "all";
};

const normalizeTopicFilter = (v: string | undefined): string => {
  const key = (v || "").trim().toLowerCase();
  if (!key) return "all";
  if (key === "all") return "all";
  if (key === "medical_diet" || key === "aga" || key === "beauty" || key === "finance" || key === "education") {
    return key;
  }
  if (["glp", "glp-1", "glp1", "medical", "medicaldiet", "medical_diet_glp1"].includes(key)) {
    return "medical_diet";
  }
  return key;
};

const normalizePeriodFilter = (v: string | undefined): PeriodType => {
  const key = (v || "").toLowerCase();
  if (key === "2d" || key === "7d" || key === "14d" || key === "30d" || key === "all") return key;
  if (key === "daily" || key === "1d") return "2d";
  if (key === "weekly") return "7d";
  if (key === "monthly") return "30d";
  return "all";
};

const diffLabelMap: Record<string, string> = {
  period: "区切り",
  snapshotDate: "version",
  platform: "媒体",
  genre: "ジャンル",
  topic: "トピック",
  transitionType: "遷移先タイプ",
  adFormat: "形式",
  isAffiliate: "PR/アフィリ",
  query: "キーワード",
  sortBy: "並び順",
};
const normalizationLabelMap: Record<string, string> = {
  period: "区切り",
  transitionType: "遷移先タイプ",
  adFormat: "形式",
  isAffiliate: "PR/アフィリ",
  topic: "トピック",
};

const normalizationValueLabel = (key: string, raw: string): string => {
  const v = (raw || "").toLowerCase();
  if (key === "period") {
    if (v === "2d") return "2日間";
    if (v === "7d") return "1週間";
    if (v === "14d") return "2週間";
    if (v === "30d") return "1ヶ月";
    if (v === "all") return "全期間";
  }
  if (key === "transitionType") {
    if (v === "article_lp") return "記事LP";
    if (v === "survey_lp") return "アンケートLP";
    if (v === "manga_lp") return "漫画記事LP";
    if (v === "other") return "その他";
    if (v === "all") return "すべて";
  }
  if (key === "adFormat") {
    if (v === "video") return "動画";
    if (v === "banner") return "バナー";
    if (v === "carousel") return "カルーセル";
    if (v === "all") return "すべて";
  }
  if (key === "isAffiliate") {
    if (v === "false") return "PR広告";
    if (v === "true") return "アフィリエイト";
    if (v === "all") return "すべて";
  }
  return raw;
};

const toDisplay = (v: unknown): string => {
  if (v === null || v === undefined) return "(なし)";
  if (typeof v === "string") return v === "" ? "(なし)" : v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
};

const safeAdvancedFilterCount = (v: unknown): number => {
  if (!v || typeof v !== "object") return 0;
  const raw = v as Partial<AdvancedFilters>;
  const merged: AdvancedFilters = {
    ...defaultFilters,
    ...raw,
    dateRange: {
      ...defaultFilters.dateRange,
      ...(raw.dateRange || {}),
    },
    excludedAdvertisers: Array.isArray(raw.excludedAdvertisers) ? raw.excludedAdvertisers : [],
    excludedDomains: Array.isArray(raw.excludedDomains) ? raw.excludedDomains : [],
  };
  return getActiveFilterCount(merged);
};

// ─── Main Component ───

interface ProRankingViewProps {
  onAdSelect: (adId: number) => void;
}

export default function ProRankingView({ onAdSelect }: ProRankingViewProps) {
  // Filter state (synced to URL params)
  const [selectedGenre, setSelectedGenre] = useUrlParam("genre", "all");
  const [selectedPlatform, setSelectedPlatform] = useUrlParam("platform", "all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useUrlParam("sort", "cumulative_views") as [SortType, (v: string) => void];
  const [period, setPeriod] = useUrlParam("period", "7d") as [PeriodType, (v: string) => void];
  const [snapshotDate, setSnapshotDate] = useUrlParam("snapshot_date", "");
  const [selectedTopic, setSelectedTopic] = useUrlParam("topic", "all");
  const [transitionType, setTransitionType] = useUrlParam("transition_type", "all");
  const [adFormat, setAdFormat] = useUrlParam("ad_format", "all") as ["all" | "video" | "banner" | "carousel", (v: string) => void];
  const [isAffiliate, setIsAffiliate] = useUrlParam("is_affiliate", "all") as ["all" | "true" | "false", (v: string) => void];
  const [jpOnlyParam, setJpOnlyParam] = useUrlParam("jp_only", "true");
  const [priorityFilter, setPriorityFilter] = useUrlParam("priority", "all") as ["all" | "high" | "medium" | "low", (v: string) => void];
  const [reviewRequiredParam, setReviewRequiredParam] = useUrlParam("review_required", "false");
  const [actualMetricsParam, setActualMetricsParam] = useUrlParam("actual_metrics_focus", "false");
  const [operationViewParam, setOperationViewParam] = useUrlParam("ops_view", "false");
  const [evidenceMode] = useUrlParam("evidence", "");
  const jpOnly = jpOnlyParam !== "false";
  const reviewRequiredOnly = reviewRequiredParam === "true";
  const actualMetricsFocus = actualMetricsParam === "true";
  const operationView = operationViewParam === "true";
  const resultsAnchorRef = useRef<HTMLDivElement>(null);

  // Genre master data
  const [genreGroups, setGenreGroups] = useState<GenreGroup[]>([]);
  const [genreList, setGenreList] = useState<GenreMasterItem[]>([]);
  const [genreLoading, setGenreLoading] = useState(false);
  const [showGenreSidebar, setShowGenreSidebar] = useState(false);
  const [showGenreDrawer, setShowGenreDrawer] = useState(false);
  const [genreSidebarCollapsed, setGenreSidebarCollapsed] = useState(false);
  const [genreSearch, setGenreSearch] = useState("");
  const [expandedParents, setExpandedParents] = useState<Set<string>>(new Set());

  // Search collections
  const [collections, setCollections] = useState<SearchCollection[]>([]);
  const [showCollections, setShowCollections] = useState(false);
  const [activeCollectionId, setActiveCollectionId] = useState<number | null>(null);
  const [saveName, setSaveName] = useState("");
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [savingCollection, setSavingCollection] = useState(false);
  const [deletingCollection, setDeletingCollection] = useState(false);
  const [duplicatingCollection, setDuplicatingCollection] = useState(false);
  const [editingCollectionId, setEditingCollectionId] = useState<number | null>(null);
  const [collectionActionMenuId, setCollectionActionMenuId] = useState<number | null>(null);
  const [pendingImport, setPendingImport] = useState<PendingImport | null>(null);
  const [importOverwrite, setImportOverwrite] = useState(false);
  const collectionsRef = useRef<HTMLDivElement>(null);
  const importFileInputRef = useRef<HTMLInputElement>(null);

  // View mode
  const [viewMode, setViewMode] = useState<ViewModeType>("table");

  // B21: Advanced filter panel
  const [showAdvancedFilter, setShowAdvancedFilter] = useState(false);
  const [advancedFilters, setAdvancedFilters] = useState<AdvancedFilters>(defaultFilters);
  const activeFilterCount = getActiveFilterCount(advancedFilters);

  // Hit line threshold
  const [hitLineThreshold, setHitLineThreshold] = useState<number>(10000);
  const [showMetricGuide, setShowMetricGuide] = useState(false);
  const [tableState, setTableState] = useState<{
    column_filters: { local_search: string };
    column_sort: { field: string; direction: "asc" | "desc" };
  }>({
    column_filters: { local_search: "" },
    column_sort: { field: "rank", direction: "asc" },
  });
  const [transitionFacetOptions, setTransitionFacetOptions] = useState<FacetItem[]>([]);
  const [adFormatFacetOptions, setAdFormatFacetOptions] = useState<FacetItem[]>([]);
  const [affiliateFacetOptions, setAffiliateFacetOptions] = useState<FacetItem[]>([]);
  const [topicFacetOptions, setTopicFacetOptions] = useState<FacetItem[]>([]);
  const [quickFilters, setQuickFilters] = useState<QuickFilterKey[]>([]);
  const [retryingMedia, setRetryingMedia] = useState(false);
  const [collectionTopicFilter, setCollectionTopicFilter] = useState("all");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [retryFeedback, setRetryFeedback] = useState<{ count: number; at: string } | null>(null);
  const [tableSummary, setTableSummary] = useState<{ total: number; updatedAt: string } | null>(null);
  const [showHeaderControls, setShowHeaderControls] = useState(false);

  useEffect(() => {
    if (!operationView) return;
    if (!jpOnly) setJpOnlyParam("true");
    if (priorityFilter !== "high") setPriorityFilter("high");
    if (!reviewRequiredOnly) setReviewRequiredParam("true");
    if (!actualMetricsFocus) setActualMetricsParam("true");
  }, [operationView, jpOnly, priorityFilter, reviewRequiredOnly, actualMetricsFocus, setActualMetricsParam, setJpOnlyParam, setPriorityFilter, setReviewRequiredParam]);

  useEffect(() => {
    if (evidenceMode !== "results") return;
    setViewMode("gallery");
    const timer = window.setTimeout(() => {
      resultsAnchorRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [evidenceMode]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const syncHeaderDensity = () => {
      setShowHeaderControls(window.innerHeight >= 940 && window.innerWidth >= 1440);
    };
    syncHeaderDensity();
    window.addEventListener("resize", syncHeaderDensity);
    return () => window.removeEventListener("resize", syncHeaderDensity);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const syncGenreDensity = () => {
      setGenreSidebarCollapsed(window.innerWidth < 1400 || window.innerHeight < 860);
      setShowGenreSidebar(window.innerWidth >= 1536);
    };
    syncGenreDensity();
    window.addEventListener("resize", syncGenreDensity);
    return () => window.removeEventListener("resize", syncGenreDensity);
  }, []);

  // ─── Fetch genre master + search collections in parallel ───
  const fetchCollections = useCallback(async () => {
    try {
      const data = await fetchApi<{
        collections?: SearchCollection[];
        items?: SearchCollection[];
      }>("/rankings/search-collections");
      setCollections(data.collections || data.items || []);
    } catch (err) {
      console.warn("Search collections API failed", err);
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      setGenreLoading(true);
      const [genreResult] = await Promise.allSettled([
        cachedFetchApi<{ genres?: GenreMasterItem[]; groups?: GenreGroup[] }>("/rankings/genre-master"),
        fetchCollections(),
      ]);

      if (genreResult.status === "fulfilled") {
        const data = genreResult.value;
        if (data.groups && data.groups.length > 0) {
          setGenreGroups(data.groups);
          setGenreList(data.groups.flatMap((g) => g.items));
        } else if (data.genres && data.genres.length > 0) {
          setGenreList(data.genres);
          const grouped: Record<string, GenreMasterItem[]> = {};
          data.genres.forEach((g) => {
            const parent = g.parent || "other";
            if (!grouped[parent]) grouped[parent] = [];
            grouped[parent].push(g);
          });
          setGenreGroups(
            Object.entries(grouped).map(([parent, items]) => ({ parent, items }))
          );
        }
      } else {
        console.warn("Genre master API failed, using static options", genreResult.reason);
        setGenreList(genreOptions.map((g) => ({ value: g.value, label: g.label })));
      }
      setGenreLoading(false);
    };
    init();
  }, [fetchCollections]);

  useEffect(() => {
    if (genreGroups.length > 0) {
      setExpandedParents(new Set(genreGroups.map((g) => g.parent)));
    }
  }, [genreGroups]);

  const filteredGenreGroups = useMemo(() => {
    if (!genreSearch.trim()) return genreGroups;
    const q = genreSearch.trim().toLowerCase();
    return genreGroups
      .map((group) => ({
        ...group,
        items: group.items.filter(
          (item) =>
            item.label.toLowerCase().includes(q) ||
            item.value.toLowerCase().includes(q) ||
            group.parent.toLowerCase().includes(q)
        ),
      }))
      .filter((group) => group.items.length > 0);
  }, [genreGroups, genreSearch]);

  const selectedGenreMeta = useMemo(
    () => genreList.find((g) => g.value === selectedGenre),
    [genreList, selectedGenre]
  );
  const selectedParent = selectedGenreMeta?.parent;
  const selectedParentLabel = selectedParent
    ? genreGroupLabels[selectedParent] || selectedParent
    : null;
  const matchedGenreCount = useMemo(
    () => filteredGenreGroups.reduce((sum, group) => sum + group.items.length, 0),
    [filteredGenreGroups],
  );
  const selectedGenreCount = selectedGenreMeta?.count ?? tableSummary?.total ?? 0;

  const toggleParent = (parent: string) => {
    setExpandedParents((prev) => {
      const next = new Set(prev);
      if (next.has(parent)) {
        next.delete(parent);
      } else {
        next.add(parent);
      }
      return next;
    });
  };

  useEffect(() => {
    const loadTransitionFacets = async () => {
      try {
        const data = await fetchApi<{
          transition_types?: FacetItem[];
          ad_formats?: FacetItem[];
          is_affiliate?: FacetItem[];
          topics?: FacetItem[];
        }>("/rankings/search/facets", {
          params: {
            platform: selectedPlatform !== "all" ? selectedPlatform : undefined,
            period,
            q: searchQuery || undefined,
          },
        });
        const items = (data.transition_types || [])
          .filter((it) => ["article_lp", "survey_lp", "manga_lp", "other"].includes((it.name || "").toLowerCase()));
        const transitionOrder = ["article_lp", "survey_lp", "manga_lp", "other"];
        const transitionMap = new Map(items.map((it) => [it.name.toLowerCase(), it.count]));
        setTransitionFacetOptions(
          transitionOrder.map((name) => ({ name, count: transitionMap.get(name) || 0 }))
        );
        const formatItems = (data.ad_formats || [])
          .filter((it) => ["video", "banner", "carousel"].includes((it.name || "").toLowerCase()));
        const formatOrder = ["video", "banner", "carousel"];
        const formatMap = new Map(formatItems.map((it) => [it.name.toLowerCase(), it.count]));
        setAdFormatFacetOptions(
          formatOrder.map((name) => ({ name, count: formatMap.get(name) || 0 }))
        );
        const affiliateItems = (data.is_affiliate || [])
          .filter((it) => ["true", "false", "unknown"].includes((it.name || "").toLowerCase()));
        const affOrder = ["false", "true", "unknown"];
        const affMap = new Map(affiliateItems.map((it) => [it.name.toLowerCase(), it.count]));
        setAffiliateFacetOptions(
          affOrder.map((name) => ({ name, count: affMap.get(name) || 0 }))
        );
        const topicItems = data.topics || [];
        const topicMap = new Map(topicItems.map((it) => [(it.name || "").toLowerCase(), it.count]));
        const knownTopicOrder = topicFilterOptions
          .map((o) => o.value)
          .filter((v) => v !== "all");
        const knownFacets = knownTopicOrder.map((name) => ({ name, count: topicMap.get(name) || 0 }));
        const extraFacets = topicItems
          .filter((it) => !knownTopicOrder.includes((it.name || "").toLowerCase()))
          .map((it) => ({ name: (it.name || "").toLowerCase(), count: it.count }))
          .sort((a, b) => b.count - a.count);
        setTopicFacetOptions([...knownFacets, ...extraFacets]);
      } catch (err) {
        console.warn("Failed to load transition facets", err);
      }
    };
    loadTransitionFacets();
  }, [selectedPlatform, period, searchQuery]);

  // ─── Copy share link ─── (B72: filter preset sharing)
  const handleCopyShareLink = () => {
    const sp = new URLSearchParams();
    sp.set("view", "pro-database");
    if (selectedGenre !== "all") sp.set("genre", selectedGenre);
    if (selectedPlatform !== "all") sp.set("platform", selectedPlatform);
    if (sortBy !== "cumulative_views") sp.set("sort", sortBy);
    if (period !== "7d") sp.set("period", period);
    if (searchQuery) sp.set("q", searchQuery);
    if (selectedTopic !== "all") sp.set("topic", selectedTopic);
    if (snapshotDate) sp.set("snapshot_date", snapshotDate);
    if (transitionType !== "all") sp.set("transition_type", transitionType);
    if (adFormat !== "all") sp.set("ad_format", adFormat);
    if (isAffiliate !== "all") sp.set("is_affiliate", isAffiliate);
    if (advancedFilters.videoFormat !== "all") sp.set("ad_format", advancedFilters.videoFormat);
    if (advancedFilters.destinationType) sp.set("destination_type", advancedFilters.destinationType);
    if (advancedFilters.destinationDomain) sp.set("destination_domain", advancedFilters.destinationDomain);
    const url = `${window.location.origin}${window.location.pathname}?${sp.toString()}`;
    navigator.clipboard.writeText(url).then(
      () => toast.success("共有リンクをコピーしました"),
      () => toast.error("コピーに失敗しました"),
    );
  };

  // ─── Save collection ─── (B84: max 20 limit)
  const MAX_COLLECTIONS = 20;
  const buildCurrentFiltersPayload = () => ({
    genre: selectedGenre,
    platform: selectedPlatform,
    query: searchQuery,
    topic: selectedTopic,
    sortBy,
    period,
    snapshotDate,
    transitionType,
    adFormat,
    isAffiliate,
    column_filters: tableState.column_filters,
    column_sort: tableState.column_sort,
    advancedFilters,
  });

  const handleSaveCollection = async () => {
    if (!saveName.trim() || savingCollection) return;
    const trimmedName = saveName.trim();
    const existing = collections.find((c) => c.name.trim().toLowerCase() === trimmedName.toLowerCase());
    const isEditMode = editingCollectionId !== null;
    if (!isEditMode && collections.length >= MAX_COLLECTIONS) {
      toast.error(`保存上限（${MAX_COLLECTIONS}件）に達しました。不要な条件を削除してください`);
      return;
    }
    if (!isEditMode && existing) {
      toast.error("同じ名前の検索条件が既に存在します");
      return;
    }
    setSavingCollection(true);
    try {
      const body = {
        name: trimmedName,
        filters: buildCurrentFiltersPayload(),
      };
      if (isEditMode) {
        await fetchApi(`/rankings/search-collections/${editingCollectionId}`, {
          method: "PUT",
          body,
        });
      } else {
        await fetchApi("/rankings/search-collections", {
          method: "POST",
          body,
        });
      }
      setSaveName("");
      setEditingCollectionId(null);
      setShowSaveDialog(false);
      fetchCollections();
      toast.success(isEditMode ? "検索条件を更新しました" : "検索条件を保存しました");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("collection limit reached")) {
        toast.error(`保存上限（${MAX_COLLECTIONS}件）に達しました。不要な条件を削除してください`);
      } else if (msg.includes("collection name already exists")) {
        toast.error("同じ名前の検索条件が既に存在します");
      } else if (msg.includes("name is required")) {
        toast.error("検索条件の名前を入力してください");
      } else {
        toast.error("検索条件の保存に失敗しました");
      }
    } finally {
      setSavingCollection(false);
    }
  };
  const saveNameTrimmed = saveName.trim();
  const duplicateCollection = collections.find((c) => c.name.trim().toLowerCase() === saveNameTrimmed.toLowerCase());
  const isEditMode = editingCollectionId !== null;

  // ─── Delete collection ───
  const handleDeleteCollection = async (id: number) => {
    if (deletingCollection) return;
    setDeletingCollection(true);
    try {
      await fetchApi(`/rankings/search-collections/${id}`, {
        method: "DELETE",
      });
      fetchCollections();
      toast.success("検索条件を削除しました");
    } catch {
      toast.error("検索条件の削除に失敗しました");
    } finally {
      setDeletingCollection(false);
    }
  };

  // ─── Apply collection ───
  const handleApplyCollection = (collection: SearchCollection) => {
    const f = collection.filters;
    if (f.genre) setSelectedGenre(f.genre);
    if (f.platform) setSelectedPlatform(f.platform);
    if (f.query !== undefined) setSearchQuery(f.query);
    if (f.sortBy) setSortBy(f.sortBy as SortType);
    if (f.period) setPeriod(f.period as PeriodType);
    if (f.topic) setSelectedTopic(normalizeTopicFilter(f.topic));
    if (f.snapshotDate !== undefined) setSnapshotDate(f.snapshotDate);
    if (f.transitionType) setTransitionType(normalizeTransitionFilter(f.transitionType));
    if (f.adFormat) setAdFormat(normalizeAdFormatFilter(f.adFormat));
    if (f.isAffiliate) setIsAffiliate(normalizeAffiliateFilter(f.isAffiliate));
    if (f.column_filters || f.column_sort) {
      setTableState({
        column_filters: { local_search: f.column_filters?.local_search || "" },
        column_sort: {
          field: f.column_sort?.field || "rank",
          direction: (f.column_sort?.direction || "asc") as "asc" | "desc",
        },
      });
    }
    if (f.advancedFilters) setAdvancedFilters(f.advancedFilters);
    setQuickFilters([]);
    setActiveCollectionId(collection.id);
    setShowCollections(false);
    setCollectionActionMenuId(null);
    // Best-effort usage tracking for "most recently used" ordering.
    fetchApi(`/rankings/search-collections/${collection.id}/touch`, { method: "POST" })
      .then(() => fetchCollections())
      .catch(() => {});
  };

  const handleDuplicateCollection = async (collection: SearchCollection) => {
    if (duplicatingCollection) return;
    if (collections.length >= MAX_COLLECTIONS) {
      toast.error(`保存上限（${MAX_COLLECTIONS}件）に達しました。不要な条件を削除してください`);
      return;
    }
    setDuplicatingCollection(true);
    try {
      const existingNames = new Set(collections.map((c) => c.name.trim().toLowerCase()));
      const base = `${collection.name} コピー`.trim();
      let candidate = base;
      let i = 2;
      while (existingNames.has(candidate.toLowerCase())) {
        candidate = `${base} ${i}`;
        i += 1;
      }
      await fetchApi("/rankings/search-collections", {
        method: "POST",
        body: {
          name: candidate,
          filters: collection.filters || {},
        },
      });
      await fetchCollections();
      toast.success("検索条件を複製しました");
    } catch {
      toast.error("検索条件の複製に失敗しました");
    } finally {
      setDuplicatingCollection(false);
    }
  };

  const handleOpenUpdateDialog = (collection: SearchCollection) => {
    setEditingCollectionId(collection.id);
    setSaveName(collection.name);
    setShowCollections(false);
    setCollectionActionMenuId(null);
    setShowSaveDialog(true);
  };

  const handleBatchRetryMedia = async () => {
    if (retryingMedia) return;
    setRetryingMedia(true);
    try {
      const result = await fetchApi<{
        dispatched: number;
        errors: number;
        retry_candidates_dispatched?: number;
      }>("/rankings/batch-extract-media", {
        method: "POST",
        params: { limit: 50 },
      });
      const now = new Date().toISOString();
      setRetryFeedback({ count: result.dispatched, at: now });
      setRefreshNonce((n) => n + 1);
      toast.success(
        `再抽出キュー投入: ${result.dispatched}件（低品質再抽出 ${result.retry_candidates_dispatched || 0}件）`
      );
    } catch {
      toast.error("再抽出キュー投入に失敗しました");
    } finally {
      setRetryingMedia(false);
    }
  };

  const handleExportCollection = (collection: SearchCollection) => {
    try {
      const topicKey = String(collection.filters?.topic || "all");
      const topicLabel =
        topicFilterOptions.find((t) => t.value === topicKey)?.label || topicKey;
      const payload = {
        exported_at: new Date().toISOString(),
        export_meta: {
          name: collection.name,
          topic: topicKey,
          topic_label: topicLabel,
          period: collection.filters?.period || "all",
          platform: collection.filters?.platform || "all",
          genre: collection.filters?.genre || "all",
          query: collection.filters?.query || "",
        },
        collection,
      };
      const json = JSON.stringify(payload, null, 2);
      const blob = new Blob([json], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const safeName = (collection.name || "search_collection")
        .replace(/[\\/:*?"<>|]/g, "_")
        .replace(/\s+/g, "_")
        .slice(0, 80);
      a.href = url;
      a.download = `${safeName || "search_collection"}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("検索条件をJSONでエクスポートしました");
    } catch {
      toast.error("JSONエクスポートに失敗しました");
    }
  };

  const handleImportCollectionFile = async (file: File) => {
    if (!file) return;
    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as unknown;
      const exportMeta = (parsed && typeof parsed === "object" && "export_meta" in parsed)
        ? ((parsed as { export_meta?: unknown }).export_meta as Record<string, unknown> | undefined)
        : undefined;
      const raw = (parsed && typeof parsed === "object" && "collection" in parsed)
        ? (parsed as { collection?: unknown }).collection
        : parsed;
      if (!raw || typeof raw !== "object") {
        toast.error("JSON形式が不正です");
        return;
      }
      const incoming = raw as Partial<SearchCollection>;
      const baseName = (incoming.name || "").trim();
      if (!baseName) {
        toast.error("インポートデータに name がありません");
        return;
      }
      const filters = (incoming.filters && typeof incoming.filters === "object")
        ? (incoming.filters as Record<string, unknown>)
        : {};
      const normalizedFilters: Record<string, unknown> = { ...filters };
      const normalizationNotes: Array<{ key: string; before: string; after: string }> = [];
      if (typeof normalizedFilters.period === "string") {
        const before = normalizedFilters.period;
        const after = normalizePeriodFilter(normalizedFilters.period);
        normalizedFilters.period = after;
        if (before !== after) normalizationNotes.push({ key: "period", before, after });
      }
      if (typeof normalizedFilters.transitionType === "string") {
        const before = normalizedFilters.transitionType;
        const after = normalizeTransitionFilter(normalizedFilters.transitionType);
        normalizedFilters.transitionType = after;
        if (before !== after) normalizationNotes.push({ key: "transitionType", before, after });
      }
      if (typeof normalizedFilters.adFormat === "string") {
        const before = normalizedFilters.adFormat;
        const after = normalizeAdFormatFilter(normalizedFilters.adFormat);
        normalizedFilters.adFormat = after;
        if (before !== after) normalizationNotes.push({ key: "adFormat", before, after });
      }
      if (typeof normalizedFilters.isAffiliate === "string") {
        const before = normalizedFilters.isAffiliate;
        const after = normalizeAffiliateFilter(normalizedFilters.isAffiliate);
        normalizedFilters.isAffiliate = after;
        if (before !== after) normalizationNotes.push({ key: "isAffiliate", before, after });
      }
      // Export互換補完:
      // filters.topic が欠損している旧JSONでも、export_meta.topic があれば採用する。
      if (
        (normalizedFilters.topic === undefined || normalizedFilters.topic === null || normalizedFilters.topic === "") &&
        exportMeta &&
        typeof exportMeta.topic === "string" &&
        exportMeta.topic.trim() !== ""
      ) {
        normalizedFilters.topic = exportMeta.topic.trim().toLowerCase();
      }
      if (typeof normalizedFilters.topic === "string") {
        const before = normalizedFilters.topic;
        const after = normalizeTopicFilter(normalizedFilters.topic);
        normalizedFilters.topic = after;
        if (before !== after) normalizationNotes.push({ key: "topic", before, after });
      }
      setPendingImport({ name: baseName, filters: normalizedFilters, normalizationNotes });
      setImportOverwrite(false);
      setShowCollections(false);
    } catch {
      toast.error("JSONインポートに失敗しました");
    }
  };

  const getNextImportName = (baseName: string): string => {
    const existingNames = new Set(collections.map((c) => c.name.trim().toLowerCase()));
    let candidate = baseName;
    let i = 2;
    while (existingNames.has(candidate.toLowerCase())) {
      candidate = `${baseName} ${i}`;
      i += 1;
    }
    return candidate;
  };

  const handleConfirmImport = async () => {
    if (!pendingImport) return;
    if (collections.length >= MAX_COLLECTIONS) {
      toast.error(`保存上限（${MAX_COLLECTIONS}件）に達しました。不要な条件を削除してください`);
      setPendingImport(null);
      return;
    }
    try {
      const baseName = pendingImport.name.trim();
      const exact = collections.find((c) => c.name.trim().toLowerCase() === baseName.toLowerCase());
      if (importOverwrite && exact) {
        await fetchApi(`/rankings/search-collections/${exact.id}`, {
          method: "PUT",
          body: {
            name: exact.name,
            filters: pendingImport.filters,
          },
        });
      } else {
        const candidate = getNextImportName(baseName);
        await fetchApi("/rankings/search-collections", {
          method: "POST",
          body: {
            name: candidate,
            filters: pendingImport.filters,
          },
        });
      }
      await fetchCollections();
      setPendingImport(null);
      setImportOverwrite(false);
      toast.success(importOverwrite && exact ? "検索条件を上書きインポートしました" : "検索条件をJSONからインポートしました");
    } catch {
      toast.error("JSONインポートに失敗しました");
    }
  };

  const sortedCollections = useMemo(() => {
    const ts = (c: SearchCollection): number => {
      const s = c.last_used_at || c.updated_at || c.created_at || "";
      const t = Date.parse(s);
      return Number.isNaN(t) ? 0 : t;
    };
    const topicKey = (c: SearchCollection): string =>
      String(c.filters?.topic || "all").trim().toLowerCase();
    const selectedTopicKey = String(selectedTopic || "all").trim().toLowerCase();

    return [...collections].sort((a, b) => {
      if (selectedTopicKey !== "all") {
        const aMatch = topicKey(a) === selectedTopicKey;
        const bMatch = topicKey(b) === selectedTopicKey;
        if (aMatch !== bMatch) return aMatch ? -1 : 1;
      }
      const tDiff = ts(b) - ts(a);
      if (tDiff !== 0) return tDiff;
      return a.name.localeCompare(b.name, "ja");
    });
  }, [collections, selectedTopic]);

  const collectionTopicOptions = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const c of sortedCollections) {
      const key = String(c.filters?.topic || "all").trim().toLowerCase();
      if (!key || key === "all") continue;
      counts[key] = (counts[key] || 0) + 1;
    }
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [sortedCollections]);

  const filteredCollections = useMemo(() => {
    if (collectionTopicFilter === "all") return sortedCollections;
    return sortedCollections.filter(
      (c) => String(c.filters?.topic || "all").trim().toLowerCase() === collectionTopicFilter
    );
  }, [sortedCollections, collectionTopicFilter]);

  const formatCollectionTime = (c: SearchCollection): string => {
    const s = c.last_used_at || c.updated_at || c.created_at;
    if (!s) return "";
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString("ja-JP", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const importDiffs = useMemo<FilterDiffItem[]>(() => {
    if (!pendingImport || !importOverwrite) return [];
    const baseName = pendingImport.name.trim().toLowerCase();
    const target = collections.find((c) => c.name.trim().toLowerCase() === baseName);
    if (!target) return [];
    const beforeFilters = (target.filters || {}) as Record<string, unknown>;
    const afterFilters = (pendingImport.filters || {}) as Record<string, unknown>;
    const keys = Object.keys(diffLabelMap);
    const diffs: FilterDiffItem[] = [];
    for (const key of keys) {
      const b = toDisplay(beforeFilters[key]);
      const a = toDisplay(afterFilters[key]);
      if (b !== a) {
        diffs.push({
          key,
          label: diffLabelMap[key] || key,
          before: b,
          after: a,
        });
      }
    }
    return diffs;
  }, [pendingImport, importOverwrite, collections]);

  const importAdvancedDiff = useMemo(() => {
    if (!pendingImport || !importOverwrite) return null;
    const baseName = pendingImport.name.trim().toLowerCase();
    const target = collections.find((c) => c.name.trim().toLowerCase() === baseName);
    if (!target) return null;
    const beforeCount = safeAdvancedFilterCount((target.filters as Record<string, unknown> | undefined)?.advancedFilters);
    const afterCount = safeAdvancedFilterCount((pendingImport.filters as Record<string, unknown> | undefined)?.advancedFilters);
    return { beforeCount, afterCount };
  }, [pendingImport, importOverwrite, collections]);

  const importDeltaSummary = useMemo(() => {
    if (!importOverwrite) return null;
    const advBefore = importAdvancedDiff?.beforeCount ?? 0;
    const advAfter = importAdvancedDiff?.afterCount ?? 0;
    const increased = advAfter > advBefore ? advAfter - advBefore : 0;
    const decreased = advBefore > advAfter ? advBefore - advAfter : 0;
    return {
      changedMainFields: importDiffs.length,
      increasedAdvanced: increased,
      decreasedAdvanced: decreased,
    };
  }, [importOverwrite, importDiffs, importAdvancedDiff]);

  const scoreRangePreset = useMemo<[number, number] | undefined>(() => {
    if (quickFilters.includes("score_70_plus")) return [70, 100];
    return undefined;
  }, [quickFilters]);

  const handleToggleQuickFilter = useCallback((key: QuickFilterKey) => {
    const isActive = quickFilters.includes(key);
    let next = isActive ? quickFilters.filter((k) => k !== key) : [...quickFilters, key];
    if (!isActive && key === "active_only") next = next.filter((k) => k !== "new_week");
    if (!isActive && key === "new_week") next = next.filter((k) => k !== "active_only");
    setQuickFilters(next);
    setActiveCollectionId(null);

    if (key === "video_only") {
      setAdFormat(isActive ? "all" : "video");
      return;
    }
    if (key === "hit_only") {
      if (!isActive) {
        setSortBy("hit_score");
        setAdvancedFilters((prev) => ({ ...prev, viewCountMin: prev.viewCountMin ?? hitLineThreshold }));
      } else {
        setAdvancedFilters((prev) => ({
          ...prev,
          viewCountMin: prev.viewCountMin === hitLineThreshold ? null : prev.viewCountMin,
        }));
      }
      return;
    }
    if (key === "active_only") {
      setPeriod(isActive ? "7d" : "2d");
      return;
    }
    if (key === "new_week") {
      setPeriod(isActive ? "all" : "7d");
      return;
    }
    if (key === "score_70_plus" && !isActive) {
      setSortBy("hit_score");
    }
  }, [quickFilters, setAdFormat, setAdvancedFilters, setPeriod, setSortBy, hitLineThreshold]);

  // Close collections dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        collectionsRef.current &&
        !collectionsRef.current.contains(e.target as Node)
      ) {
        setShowCollections(false);
        setCollectionActionMenuId(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  if (evidenceMode === "results") {
    return (
      <div className="flex h-full min-h-0 flex-col bg-[#f8f9fb] dark:bg-gray-950">
        <div className="shrink-0 border-b border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-900">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h1 className="text-[14px] font-bold text-gray-900 dark:text-gray-100">検索結果証跡モード</h1>
              <p className="text-[11px] text-gray-500 dark:text-gray-400">
                日本語広告のみ / ギャラリー表示 / サムネイル確認用
              </p>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-gray-600 dark:text-gray-300">
              <span className="rounded-full bg-blue-50 px-2 py-1 text-blue-700">JP only</span>
              <span className="rounded-full bg-indigo-50 px-2 py-1 text-indigo-700">gallery</span>
              <span className="rounded-full bg-gray-100 px-2 py-1 text-gray-700">
                {tableSummary?.total ?? 0}件
              </span>
            </div>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-4">
          <div ref={resultsAnchorRef} data-evidence-results-anchor="true" />
          <ProRankingTable
            genre={selectedGenre}
            platform={selectedPlatform}
            topic={selectedTopic}
            searchQuery={searchQuery}
            sortBy={sortBy}
            period={period}
            snapshotDate={snapshotDate || undefined}
            transitionType={transitionType}
            adFormat={adFormat}
            isAffiliate={isAffiliate}
            advancedFilters={advancedFilters}
            initialTableState={tableState}
            onTableStateChange={setTableState}
            onAdSelect={onAdSelect}
            hitLineThreshold={hitLineThreshold}
            viewMode={viewMode}
            scoreRangePreset={scoreRangePreset}
            refreshNonce={refreshNonce}
            onSummaryChange={setTableSummary}
            jpOnly={jpOnly}
            priorityFilter={priorityFilter}
            reviewRequiredOnly={reviewRequiredOnly}
            actualMetricsFocus={actualMetricsFocus}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-full flex-col bg-[#f8f9fb] dark:bg-gray-950">
      {/* ─── Dashboard KPI Cards ─── */}
      <div className="shrink-0 bg-[#f8f9fb] px-3 pt-2 pb-0 dark:bg-gray-950 md:px-4">
        <CustomKPICards />
      </div>

      {/* ─── Top Header Bar ─── */}
      <div className="shrink-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
        <div className="px-3 py-2 md:px-4">
          {/* Title row */}
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <svg
                  className="h-4 w-4 text-[#4A7DFF]"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
                  />
                </svg>
                <h1 className="text-[15px] font-bold text-gray-900 dark:text-gray-100">
                  PRO DATABASE
                </h1>
              </div>
              <span className={`text-[11px] text-gray-400 dark:text-gray-500 ${showHeaderControls ? "" : "hidden xl:inline"}`}>
                広告データベース分析
              </span>
            </div>

            {/* Right: Share link + Collections dropdown */}
            <div className="flex flex-wrap items-center justify-end gap-1.5">
            <button
              onClick={() => setShowGenreSidebar((v) => !v)}
              className={`rounded-lg border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                showGenreSidebar
                  ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                  : "border-gray-200 bg-gray-50 text-gray-600 hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              }`}
              title="ジャンルサイドバーの表示を切り替え"
            >
              {showGenreSidebar ? "ジャンル非表示" : "ジャンル表示"}
            </button>
            <button
              onClick={() => setShowHeaderControls((v) => !v)}
              className="rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] font-medium text-gray-600 transition-colors hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              title="ヘッダー領域の表示を切り替え"
            >
              {showHeaderControls ? "コンパクト" : "詳細表示"}
            </button>
            <button
              onClick={handleCopyShareLink}
              className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] font-medium text-gray-600 transition-colors hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              title="フィルタ条件の共有リンクをコピー"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-3.06a4.5 4.5 0 00-1.242-7.244l-4.5-4.5a4.5 4.5 0 00-6.364 6.364L4.25 8.81" />
              </svg>
              <span className="hidden sm:inline">共有</span>
            </button>
            <div className="relative" ref={collectionsRef}>
              <button
                onClick={() => setShowCollections(!showCollections)}
                className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 text-[11px] font-medium text-gray-600 transition-colors hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              >
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.8}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
                  />
                </svg>
                保存済み検索
                {collections.length > 0 && (
                  <span className="ml-1 px-1.5 py-0.5 text-[9px] font-bold bg-[#4A7DFF] text-white rounded-full leading-none">
                    {collections.length}
                  </span>
                )}
              </button>

              {showCollections && (
                <div className="absolute right-0 top-full mt-1 w-72 bg-white dark:bg-gray-900 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50">
                  <div className="p-3 border-b border-gray-100 flex items-center justify-between gap-2">
                    <p className="text-[12px] font-semibold text-gray-700 dark:text-gray-300">保存済み検索条件</p>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        importFileInputRef.current?.click();
                      }}
                      className="px-2 py-0.5 text-[10px] text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800"
                    >
                      JSON取込
                    </button>
                    <input
                      ref={importFileInputRef}
                      type="file"
                      accept=".json,application/json"
                      className="hidden"
                      onChange={async (e) => {
                        const f = e.target.files?.[0];
                        if (f) await handleImportCollectionFile(f);
                        e.currentTarget.value = "";
                      }}
                    />
                  </div>
                  {collectionTopicOptions.length > 0 && (
                    <div className="px-3 py-2 border-b border-gray-100 flex items-center gap-1 flex-wrap">
                      <button
                        onClick={() => setCollectionTopicFilter("all")}
                        className={`px-2 py-0.5 rounded text-[10px] border ${
                          collectionTopicFilter === "all"
                            ? "bg-indigo-100 text-indigo-700 border-indigo-200"
                            : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                        }`}
                      >
                        すべて ({sortedCollections.length})
                      </button>
                      {collectionTopicOptions.map((t) => (
                        <button
                          key={t.name}
                          onClick={() => setCollectionTopicFilter(t.name)}
                          className={`px-2 py-0.5 rounded text-[10px] border ${
                            collectionTopicFilter === t.name
                              ? "bg-indigo-100 text-indigo-700 border-indigo-200"
                              : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                          }`}
                        >
                          {(topicFilterOptions.find((opt) => opt.value === t.name)?.label || t.name) + ` (${t.count})`}
                        </button>
                      ))}
                    </div>
                  )}
                  {filteredCollections.length === 0 ? (
                    <div className="p-4 text-center">
                      <p className="text-[11px] text-gray-400 dark:text-gray-500">
                        該当する検索条件はありません
                      </p>
                    </div>
                  ) : (
                    <div className="max-h-60 overflow-y-auto">
                      {filteredCollections.map((c) => (
                        <div
                          key={c.id}
                          className="flex items-center justify-between px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 transition-colors"
                        >
                          <button
                            onClick={() => handleApplyCollection(c)}
                            className="flex-1 text-left min-w-0"
                          >
                            <div className="text-[12px] text-gray-700 dark:text-gray-300 font-medium truncate">{c.name}</div>
                            {typeof c.filters?.topic === "string" && c.filters.topic !== "" && c.filters.topic !== "all" && (
                              <div className="mt-0.5">
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
                                  {topicFilterOptions.find((t) => t.value === c.filters.topic)?.label || c.filters.topic}
                                </span>
                              </div>
                            )}
                            {formatCollectionTime(c) && (
                              <div className="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">
                                最終利用: {formatCollectionTime(c)}
                              </div>
                            )}
                          </button>
                          <div className="relative shrink-0 ml-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setCollectionActionMenuId((prev) => (prev === c.id ? null : c.id));
                              }}
                              className="px-1.5 py-0.5 text-[12px] text-gray-500 dark:text-gray-400 dark:text-gray-500 border border-gray-200 dark:border-gray-700 rounded hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800 transition-colors"
                              aria-label="コレクション操作"
                            >
                              ⋯
                            </button>
                            {collectionActionMenuId === c.id && (
                              <div className="absolute right-0 top-full mt-1 z-50 w-28 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDuplicateCollection(c);
                                    setCollectionActionMenuId(null);
                                  }}
                                  className="w-full text-left px-3 py-1.5 text-[11px] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800"
                                >
                                  複製
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleExportCollection(c);
                                    setCollectionActionMenuId(null);
                                  }}
                                  className="w-full text-left px-3 py-1.5 text-[11px] text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800"
                                >
                                  JSON出力
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleOpenUpdateDialog(c);
                                  }}
                                  className="w-full text-left px-3 py-1.5 text-[11px] text-blue-600 hover:bg-blue-50"
                                >
                                  更新
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteCollection(c.id);
                                    setCollectionActionMenuId(null);
                                  }}
                                  className="w-full text-left px-3 py-1.5 text-[11px] text-red-600 hover:bg-red-50"
                                >
                                  削除
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            </div>
          </div>

          {showHeaderControls && (
            <SavedViews
              views={sortedCollections.map((c) => ({ id: c.id, name: c.name }))}
              activeViewId={activeCollectionId}
              onSelect={(id) => {
                const target = sortedCollections.find((c) => c.id === id);
                if (target) handleApplyCollection(target);
              }}
              onCreate={() => {
                setEditingCollectionId(null);
                setSaveName("");
                setShowSaveDialog(true);
              }}
            />
          )}

          {showHeaderControls && (
            <>
          {/* Search bar + period toggle row */}
          <QuickFilterBar active={quickFilters} onToggle={handleToggleQuickFilter} />
          <div className="flex flex-wrap items-center gap-2">
            <SmartSearchBar
              currentQuery={searchQuery}
              onSearch={(q) => setSearchQuery(q)}
              onGenreFilter={(g) => setSelectedGenre(g)}
              onProductFilter={(p) => setSearchQuery(p)}
              onAdvertiserFilter={(a) => setSearchQuery(a)}
              onSaveCollection={() => setShowSaveDialog(true)}
            />

            {/* Period toggle */}
            <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
              {periodOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setPeriod(opt.value)}
                  className={`px-3 py-1.5 text-[11px] font-medium rounded-md transition-all ${
                    period === opt.value
                      ? "bg-white dark:bg-gray-900 text-[#4A7DFF] shadow-sm"
                      : "text-gray-500 dark:text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 dark:text-gray-300"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] text-gray-500 dark:text-gray-400 dark:text-gray-500">version</span>
              <input
                type="date"
                value={snapshotDate}
                onChange={(e) => setSnapshotDate(e.target.value)}
                className="px-2 py-1.5 text-[11px] border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300"
                title="履歴基準日"
              />
              {snapshotDate && (
                <button
                  onClick={() => setSnapshotDate("")}
                  className="px-2 py-1 text-[10px] text-gray-500 dark:text-gray-400 dark:text-gray-500 bg-gray-100 rounded-md hover:bg-gray-200"
                >
                  最新版
                </button>
              )}
            </div>

            <select
              value={adFormat}
              onChange={(e) => setAdFormat(e.target.value)}
              className="px-2 py-1.5 text-[11px] border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300"
              title="形式"
            >
              <option value="all">形式: すべて</option>
              {(adFormatFacetOptions.length > 0 ? adFormatFacetOptions : [
                { name: "video", count: 0 },
                { name: "banner", count: 0 },
                { name: "carousel", count: 0 },
              ]).map((opt) => (
                <option key={opt.name} value={opt.name}>
                  {opt.name === "video" ? "形式: 動画" : opt.name === "banner" ? "形式: バナー" : "形式: カルーセル"}
                  {opt.count > 0 ? ` (${opt.count})` : ""}
                </option>
              ))}
            </select>

            <select
              value={transitionType}
              onChange={(e) => setTransitionType(e.target.value)}
              className="px-2 py-1.5 text-[11px] border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300"
              title="遷移先タイプ"
            >
              <option value="all">遷移先: すべて</option>
              {(transitionFacetOptions.length > 0 ? transitionFacetOptions : [
                { name: "article_lp", count: 0 },
                { name: "survey_lp", count: 0 },
                { name: "manga_lp", count: 0 },
                { name: "other", count: 0 },
              ]).map((opt) => (
                <option key={opt.name} value={opt.name}>
                  {opt.name === "article_lp" ? "記事LP" : opt.name === "survey_lp" ? "アンケートLP" : opt.name === "manga_lp" ? "漫画記事LP" : "その他"}
                  {opt.count > 0 ? ` (${opt.count})` : ""}
                </option>
              ))}
            </select>

            <select
              value={isAffiliate}
              onChange={(e) => setIsAffiliate(e.target.value)}
              className="px-2 py-1.5 text-[11px] border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300"
              title="PR広告絞り込み"
            >
              <option value="all">PR/アフィリ: すべて</option>
              {(affiliateFacetOptions.length > 0 ? affiliateFacetOptions : [
                { name: "false", count: 0 },
                { name: "true", count: 0 },
                { name: "unknown", count: 0 },
              ])
                .filter((opt) => opt.name !== "unknown")
                .map((opt) => (
                  <option key={opt.name} value={opt.name}>
                    {opt.name === "false" ? "PR広告のみ" : "アフィリエイトのみ"}
                    {opt.count > 0 ? ` (${opt.count})` : ""}
                  </option>
                ))}
            </select>

            <label className="inline-flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5">
              <input
                type="checkbox"
                checked={jpOnly}
                onChange={(e) => setJpOnlyParam(e.target.checked ? "true" : "false")}
                className="h-3.5 w-3.5 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]/30"
              />
              <span className="text-[11px] font-medium text-gray-700 dark:text-gray-300">日本語広告のみ</span>
            </label>

            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="px-2 py-1.5 text-[11px] border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300"
              title="priority絞り込み"
            >
              <option value="all">優先度: すべて</option>
              <option value="high">高優先</option>
              <option value="medium">中優先</option>
              <option value="low">低優先</option>
            </select>

            <label className="inline-flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5">
              <input
                type="checkbox"
                checked={reviewRequiredOnly}
                onChange={(e) => setReviewRequiredParam(e.target.checked ? "true" : "false")}
                className="h-3.5 w-3.5 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]/30"
              />
              <span className="text-[11px] font-medium text-gray-700 dark:text-gray-300">要確認のみ</span>
            </label>

            <label className="inline-flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5">
              <input
                type="checkbox"
                checked={actualMetricsFocus}
                onChange={(e) => setActualMetricsParam(e.target.checked ? "true" : "false")}
                className="h-3.5 w-3.5 rounded border-amber-300 text-amber-600 focus:ring-amber-300/40"
              />
              <span className="text-[11px] font-medium text-amber-800">実績指標を優先取得</span>
            </label>

            <button
              onClick={() => setOperationViewParam(operationView ? "false" : "true")}
              className={`px-2.5 py-1.5 text-[11px] rounded-lg border transition-colors ${
                operationView
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
              title="JP only + high priority + review_required"
            >
              運用ビュー
            </button>

            <button
              onClick={() => setShowMetricGuide((v) => !v)}
              className="px-2.5 py-1.5 text-[11px] border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 dark:bg-gray-800"
              title="指標ガイド"
            >
              指標ガイド
            </button>

            {/* View mode toggle */}
            <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => setViewMode("table")}
                className={`p-1.5 rounded-md transition-all ${
                  viewMode === "table"
                    ? "bg-white dark:bg-gray-900 text-[#4A7DFF] shadow-sm"
                    : "text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-200 dark:text-gray-300"
                }`}
                title="テーブル表示"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z"
                  />
                </svg>
              </button>
              <button
                onClick={() => setViewMode("card")}
                className={`p-1.5 rounded-md transition-all ${
                  viewMode === "card"
                    ? "bg-white dark:bg-gray-900 text-[#4A7DFF] shadow-sm"
                    : "text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-200 dark:text-gray-300"
                }`}
                title="カード表示"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
                  />
                </svg>
              </button>
              <button
                onClick={() => setViewMode("gallery")}
                className={`p-1.5 rounded-md transition-all ${
                  viewMode === "gallery"
                    ? "bg-white dark:bg-gray-900 text-[#4A7DFF] shadow-sm"
                    : "text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-200 dark:text-gray-300"
                }`}
                title="ギャラリー表示"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5a2.25 2.25 0 002.25-2.25V5.25a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 003.75 21z"
                  />
                </svg>
              </button>
            </div>
          </div>

          {showMetricGuide && (
            <div className="mt-2 rounded-lg border border-blue-100 bg-blue-50/70 px-3 py-2 text-[11px] text-gray-700 dark:text-gray-300 space-y-1">
              <p><strong>再生増加数</strong>: 指定区切り期間における再生回数の増加分です。</p>
              <p><strong>予想消化額（増加）</strong>: 再生増加数 × CPM（内部で1,000再生単位換算）で算出します。</p>
              <p><strong>CPM注記</strong>: CPMは媒体・時期で変動する推測値であり、絶対額保証ではありません。主用途は相対比較です。</p>
              <p><strong>区切り × version</strong>: version日付を基準日にして、区切り（2日/1週間/2週間/1ヶ月）差分を比較します。</p>
            </div>
          )}

          <div className="mt-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-1.5 text-[11px] text-gray-600 dark:text-gray-300">
            比較条件: {snapshotDate ? `version ${snapshotDate}` : "最新版"} / 区切り {periodLabelMap[period]}
          </div>
          <div className="mt-2 rounded-lg border border-indigo-100 bg-indigo-50/70 px-3 py-1.5 text-[11px] text-indigo-700">
            表示件数: {tableSummary?.total ?? 0}件 / 最終更新:{" "}
            {tableSummary?.updatedAt
              ? new Date(tableSummary.updatedAt).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
              : "-"}
            <span className="ml-2 text-indigo-500">/ table sort・page URL同期</span>
            {retryFeedback && (
              <span className="ml-2">
                / 再抽出投入: {retryFeedback.count}件（{new Date(retryFeedback.at).toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}）
              </span>
            )}
          </div>

          {/* Filter chips row */}
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {selectedGenre !== "all" && (
              <div className="inline-flex items-center gap-1 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-[11px] text-gray-600 dark:text-gray-300">
                <button onClick={() => setSelectedGenre("all")} className="hover:text-[#4A7DFF]">
                  All
                </button>
                <span>/</span>
                {selectedParentLabel && (
                  <>
                    <span>{selectedParentLabel}</span>
                    <span>/</span>
                  </>
                )}
                <span className="font-medium text-gray-900 dark:text-gray-100">
                  {selectedGenreMeta?.label || selectedGenre}
                </span>
              </div>
            )}

            {/* Platform filter */}
            <select
              value={selectedPlatform}
              onChange={(e) => setSelectedPlatform(e.target.value)}
              className="text-[11px] px-2.5 py-1 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/30"
            >
              {platformFilterOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            <select
              value={selectedTopic}
              onChange={(e) => setSelectedTopic(e.target.value)}
              className="text-[11px] px-2.5 py-1 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/30"
            >
              {topicFilterOptions.map((opt) => {
                if (opt.value === "all") {
                  return <option key={opt.value} value={opt.value}>{opt.label}</option>;
                }
                const count = topicFacetOptions.find((t) => t.name === opt.value)?.count ?? 0;
                return (
                  <option key={opt.value} value={opt.value}>
                    {`${opt.label} (${count})`}
                  </option>
                );
              })}
              {topicFacetOptions
                .filter((t) => !topicFilterOptions.some((opt) => opt.value === t.name))
                .map((t) => (
                  <option key={t.name} value={t.name}>
                    {`${t.name} (${t.count})`}
                  </option>
                ))}
            </select>

            <div className="inline-flex items-center gap-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-1 py-1">
              {quickTopicOptions.map((opt) => {
                const active = selectedTopic === opt.value;
                const count = topicFacetOptions.find((t) => t.name === opt.value)?.count ?? 0;
                return (
                  <button
                    key={opt.value}
                    onClick={() => setSelectedTopic(active ? "all" : opt.value)}
                    className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                      active
                        ? "bg-indigo-100 text-indigo-700"
                        : "text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                    }`}
                    title={`${opt.label}で絞り込み`}
                  >
                    {`${opt.label} ${count}`}
                  </button>
                );
              })}
            </div>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortType)}
              className="text-[11px] px-2.5 py-1 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-300 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/30"
            >
              {sortOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            {/* B21: Advanced Filter button */}
            <button
              onClick={() => setShowAdvancedFilter(true)}
              className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z" />
              </svg>
              フィルター
              {activeFilterCount > 0 && (
                <span className="px-1.5 py-0.5 text-[9px] font-bold bg-[#4A7DFF] text-white rounded-full leading-none">
                  {activeFilterCount}
                </span>
              )}
            </button>

            {/* Genre sidebar toggle (small screens) */}
            <button
              onClick={() => setShowGenreDrawer(true)}
              className="text-[11px] px-2.5 py-1 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors lg:hidden"
            >
              ジャンル選択
            </button>

            <button
              onClick={handleBatchRetryMedia}
              disabled={retryingMedia}
              className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 hover:bg-rose-100 transition-colors disabled:opacity-60"
              title="低品質素材の再抽出を一括キュー投入"
            >
              {retryingMedia ? "投入中..." : "低品質を再抽出"}
            </button>

            {/* Active filters */}
            {selectedGenre !== "all" && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-[11px] font-medium">
                {genreList.find((g) => g.value === selectedGenre)?.label ||
                  selectedGenre}
                <button
                  onClick={() => setSelectedGenre("all")}
                  className="hover:text-blue-900 transition-colors"
                >
                  <svg
                    className="w-3 h-3"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </span>
            )}
            {searchQuery && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 text-[11px] font-medium">
                &quot;{searchQuery}&quot;
                <button
                  onClick={() => setSearchQuery("")}
                  className="hover:text-purple-900 transition-colors"
                >
                  <svg
                    className="w-3 h-3"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </span>
            )}
            {selectedTopic !== "all" && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-[11px] font-medium">
                {topicFilterOptions.find((t) => t.value === selectedTopic)?.label || selectedTopic}
                <button
                  onClick={() => setSelectedTopic("all")}
                  className="hover:text-indigo-900 transition-colors"
                >
                  <svg
                    className="w-3 h-3"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </span>
            )}
          </div>
            </>
          )}

          {!showHeaderControls && (
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <SmartSearchBar
                currentQuery={searchQuery}
                onSearch={(q) => setSearchQuery(q)}
                onGenreFilter={(g) => setSelectedGenre(g)}
                onProductFilter={(p) => setSearchQuery(p)}
                onAdvertiserFilter={(a) => setSearchQuery(a)}
                onSaveCollection={() => setShowSaveDialog(true)}
              />
              <button
                onClick={() => setShowSaveDialog(true)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-[11px] font-medium text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                検索保存
              </button>
              <button
                onClick={() => setShowAdvancedFilter(true)}
                className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-[11px] font-medium text-gray-600 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                フィルター
              </button>
              <div className="rounded-lg border border-indigo-100 bg-indigo-50/70 px-2.5 py-1 text-[11px] text-indigo-700">
                {periodLabelMap[period]} / {tableSummary?.total ?? 0}件 / {selectedTopic === "all" ? "全トピック" : selectedTopic}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ─── Main Content Area ─── */}
      <div className="flex flex-1">
        {showGenreDrawer && (
          <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setShowGenreDrawer(false)}>
            <aside
              className="absolute left-0 top-0 h-full w-72 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 overflow-y-auto custom-scrollbar"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                <p className="text-[13px] font-semibold text-gray-900 dark:text-gray-100">ジャンル</p>
                <button onClick={() => setShowGenreDrawer(false)} className="text-[12px] text-gray-500 dark:text-gray-400">閉じる</button>
              </div>
              <div className="px-3 py-3">
                <input
                  type="text"
                  value={genreSearch}
                  onChange={(e) => setGenreSearch(e.target.value)}
                  placeholder="Search genres..."
                  className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-1.5 text-[12px] text-gray-800 dark:text-gray-200"
                />
                <div className="mt-2 flex items-center justify-between text-[10px] text-gray-500 dark:text-gray-400">
                  <span>一致ジャンル {matchedGenreCount}件</span>
                  <span>表示広告 {selectedGenre === "all" ? tableSummary?.total ?? 0 : selectedGenreCount}件</span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <button
                    onClick={() => setExpandedParents(new Set(filteredGenreGroups.map((g) => g.parent)))}
                    className="text-[10px] px-2 py-1 rounded border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    全展開
                  </button>
                  <button
                    onClick={() => setExpandedParents(new Set())}
                    className="text-[10px] px-2 py-1 rounded border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    全折りたたみ
                  </button>
                </div>
              </div>
              <div className="px-3 pb-3">
                <button
                  onClick={() => {
                    setSelectedGenre("all");
                    setShowGenreDrawer(false);
                  }}
                  className={`w-full text-left rounded-md px-3 py-2 text-[12px] ${
                    selectedGenre === "all"
                      ? "bg-[#EEF2FF] text-[#4A7DFF]"
                      : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                  }`}
                >
                  すべての広告
                </button>
                {filteredGenreGroups.map((group) => {
                  const open = expandedParents.has(group.parent);
                  return (
                    <div key={`drawer-${group.parent}`} className="mt-2">
                      <button
                        onClick={() => toggleParent(group.parent)}
                        className="flex w-full items-center justify-between px-3 py-1.5 text-[11px] font-semibold text-gray-500 dark:text-gray-400"
                      >
                        <span>{genreGroupLabels[group.parent] || group.parent}</span>
                        <span>{open ? "−" : "+"}</span>
                      </button>
                      {open && group.items.map((g) => (
                        <button
                          key={`drawer-item-${g.value}`}
                          onClick={() => {
                            setSelectedGenre(g.value);
                            setShowGenreDrawer(false);
                          }}
                          className={`mt-0.5 flex w-full items-center justify-between rounded-md px-3 py-1.5 text-[12px] ${
                            selectedGenre === g.value
                              ? "bg-[#EEF2FF] text-[#4A7DFF] font-medium"
                              : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                          }`}
                        >
                          <span className="truncate">{g.label}</span>
                          {g.count !== undefined && <span className="text-[10px] text-gray-400 dark:text-gray-500">{g.count}</span>}
                        </button>
                      ))}
                    </div>
                  );
                })}
              </div>
            </aside>
          </div>
        )}

        {/* ─── Genre Sidebar ─── */}
        {showGenreSidebar && (
          <aside className={`hidden lg:block shrink-0 self-start bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 transition-all ${genreSidebarCollapsed ? "w-[72px]" : "w-52"}`}>
            <div className="py-3">
              <div className="px-3 pb-2 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  {!genreSidebarCollapsed && (
                    <input
                      value={genreSearch}
                      onChange={(e) => setGenreSearch(e.target.value)}
                      placeholder="ジャンル検索..."
                      className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-2.5 py-1.5 text-[12px] text-gray-700 dark:text-gray-200 placeholder:text-gray-400 dark:placeholder:text-gray-500"
                    />
                  )}
                  <button
                    onClick={() => setGenreSidebarCollapsed((v) => !v)}
                    className="shrink-0 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-2 py-1 text-[10px] text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                    title="ジャンル欄の表示切替"
                  >
                    {genreSidebarCollapsed ? "展開" : "縮小"}
                  </button>
                </div>
                {!genreSidebarCollapsed && (
                  <>
                    <div className="flex items-center justify-between text-[10px] text-gray-500 dark:text-gray-400">
                      <span>一致ジャンル {matchedGenreCount}件</span>
                      <span>表示広告 {selectedGenre === "all" ? tableSummary?.total ?? 0 : selectedGenreCount}件</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setExpandedParents(new Set(filteredGenreGroups.map((g) => g.parent)))}
                        className="text-[10px] px-2 py-1 rounded border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                      >
                        全展開
                      </button>
                      <button
                        onClick={() => setExpandedParents(new Set())}
                        className="text-[10px] px-2 py-1 rounded border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                      >
                        全折りたたみ
                      </button>
                    </div>
                  </>
                )}
              </div>
              {/* All genres option */}
              <button
                onClick={() => setSelectedGenre("all")}
                className={`w-full flex items-center justify-between px-4 py-2 text-[12px] font-medium transition-colors ${
                  selectedGenre === "all"
                    ? "bg-[#EEF2FF] text-[#4A7DFF] border-r-2 border-[#4A7DFF]"
                    : "text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                }`}
                title="すべての広告"
              >
                <span className={genreSidebarCollapsed ? "mx-auto" : ""}>{genreSidebarCollapsed ? "全" : "すべての広告"}</span>
              </button>

              {/* Genre groups */}
              {filteredGenreGroups.length > 0
                ? filteredGenreGroups.map((group) => (
                    <div key={group.parent} className="mt-2">
                      <button
                        onClick={() => toggleParent(group.parent)}
                        className="w-full px-4 py-1 text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800"
                        title={genreGroupLabels[group.parent] || group.parent}
                      >
                        <span className={genreSidebarCollapsed ? "mx-auto" : ""}>
                          {genreSidebarCollapsed
                            ? (genreGroupLabels[group.parent] || group.parent).slice(0, 2)
                            : (genreGroupLabels[group.parent] || group.parent)}
                        </span>
                        {!genreSidebarCollapsed && (
                          <span className="text-[9px] text-gray-400 dark:text-gray-500">
                            {group.items.reduce((s, g) => s + (g.count || 0), 0)}
                          </span>
                        )}
                      </button>
                      {expandedParents.has(group.parent) &&
                        group.items.map((g) => (
                          <button
                            key={g.value}
                            onClick={() => setSelectedGenre(g.value)}
                            className={`w-full flex items-center justify-between px-4 py-1.5 text-[12px] transition-colors ${
                              selectedGenre === g.value
                                ? "bg-[#EEF2FF] text-[#4A7DFF] font-medium border-r-2 border-[#4A7DFF]"
                                : "text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                            }`}
                            title={g.label}
                          >
                            <span className={`truncate ${genreSidebarCollapsed ? "mx-auto max-w-full text-center" : ""}`}>
                              {genreSidebarCollapsed ? g.label.slice(0, 4) : g.label}
                            </span>
                            {!genreSidebarCollapsed && g.count !== undefined && (
                              <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400">
                                {g.count}
                              </span>
                            )}
                          </button>
                        ))}
                    </div>
                  ))
                : // Fallback to flat list
                  genreList
                    .filter((g) => g.value !== "all")
                    .map((g) => (
                      <button
                        key={g.value}
                        onClick={() => setSelectedGenre(g.value)}
                        className={`w-full flex items-center justify-between px-4 py-1.5 text-[12px] transition-colors ${
                          selectedGenre === g.value
                            ? "bg-[#EEF2FF] text-[#4A7DFF] font-medium border-r-2 border-[#4A7DFF]"
                            : "text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                        }`}
                      >
                        <span className="truncate">{g.label}</span>
                        {g.count !== undefined && (
                          <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500">
                            {g.count}
                          </span>
                        )}
                      </button>
                    ))}
            </div>
          </aside>
        )}

        {/* ─── Table Content ─── */}
        <div className="min-w-0 flex-1 p-3 md:p-4">
          {selectedGenre !== "all" && (
            <div className="mb-2 flex items-center gap-1 text-[11px] text-gray-500 dark:text-gray-400">
              <button onClick={() => setSelectedGenre("all")} className="hover:text-[#4A7DFF] transition-colors">
                All
              </button>
              {selectedParentLabel && (
                <>
                  <span>/</span>
                  <button
                    onClick={() => {
                      const parentGroup = genreGroups.find((g) => g.parent === selectedParent);
                      const fallback = parentGroup?.items[0]?.value || "all";
                      setSelectedGenre(fallback);
                    }}
                    className="hover:text-[#4A7DFF] transition-colors"
                  >
                    {selectedParentLabel}
                  </button>
                </>
              )}
              <span>/</span>
              <span className="text-gray-900 dark:text-gray-100 font-medium">
                {selectedGenreMeta?.label || selectedGenre}
              </span>
              <button
                onClick={() => setSelectedGenre("all")}
                className="ml-1 text-gray-400 dark:text-gray-500 hover:text-red-500 transition-colors"
              >
                ×
              </button>
            </div>
          )}
          <div ref={resultsAnchorRef} data-evidence-results-anchor="true" />
          <ProRankingTable
            genre={selectedGenre}
            platform={selectedPlatform}
            topic={selectedTopic}
            searchQuery={searchQuery}
            sortBy={sortBy}
            period={period}
            snapshotDate={snapshotDate || undefined}
            transitionType={transitionType}
            adFormat={adFormat}
            isAffiliate={isAffiliate}
            advancedFilters={advancedFilters}
            initialTableState={tableState}
            onTableStateChange={setTableState}
            onAdSelect={onAdSelect}
            hitLineThreshold={hitLineThreshold}
            viewMode={viewMode}
            scoreRangePreset={scoreRangePreset}
            refreshNonce={refreshNonce}
            onSummaryChange={setTableSummary}
            jpOnly={jpOnly}
            priorityFilter={priorityFilter}
            reviewRequiredOnly={reviewRequiredOnly}
            actualMetricsFocus={actualMetricsFocus}
          />
        </div>
      </div>

      {/* ─── Activity Feed (collapsible bottom bar) ─── */}
      <div className="shrink-0 px-3 pb-3 md:px-4">
        <ActivityFeed onAdSelect={onAdSelect} />
      </div>

      {/* ─── Save Collection Dialog ─── */}
      {showSaveDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => {
            setShowSaveDialog(false);
            setEditingCollectionId(null);
          }}
        >
          <div
            className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 p-5 w-80"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-[14px] font-bold text-gray-900 dark:text-gray-100 mb-3">
              {isEditMode ? "検索条件を更新" : "検索条件を保存"}
            </h3>
            <input
              type="text"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder="検索名を入力..."
              className="w-full px-3 py-2 text-[13px] border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF] mb-3"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSaveCollection();
              }}
              autoFocus
            />
            <div className="text-[11px] text-gray-400 dark:text-gray-500 mb-3 space-y-0.5">
              <p>
                ジャンル:{" "}
                {genreList.find((g) => g.value === selectedGenre)?.label ||
                  selectedGenre}
              </p>
              <p>
                媒体:{" "}
                {platformFilterOptions.find((p) => p.value === selectedPlatform)
                  ?.label || selectedPlatform}
              </p>
              {selectedTopic !== "all" && (
                <p>
                  トピック:{" "}
                  {topicFilterOptions.find((t) => t.value === selectedTopic)?.label || selectedTopic}
                </p>
              )}
              {duplicateCollection && (
                <p className="text-amber-600">
                  同名の保存条件があります。別名で保存してください。
                </p>
              )}
              {isEditMode && (
                <p className="text-blue-600">
                  現在の画面条件でこの検索条件を更新します。
                </p>
              )}
              {searchQuery && <p>キーワード: {searchQuery}</p>}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setShowSaveDialog(false);
                  setEditingCollectionId(null);
                }}
                className="flex-1 px-3 py-1.5 text-[12px] font-medium text-gray-600 dark:text-gray-300 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                キャンセル
              </button>
              <button
                onClick={handleSaveCollection}
                disabled={!saveName.trim()}
                className="flex-1 px-3 py-1.5 text-[12px] font-medium text-white bg-[#4A7DFF] rounded-lg hover:bg-[#3a6be8] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {isEditMode ? "更新" : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* B21: Advanced Filter Panel */}
      <AdvancedFilterPanel
        isOpen={showAdvancedFilter}
        onClose={() => setShowAdvancedFilter(false)}
        filters={advancedFilters}
        onApply={(f) => setAdvancedFilters(f)}
      />

      {pendingImport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => { setPendingImport(null); setImportOverwrite(false); }}>
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 p-5 w-[360px]" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-[14px] font-bold text-gray-900 dark:text-gray-100 mb-3">JSONインポート確認</h3>
            <label className="mb-3 flex items-center gap-2 text-[11px] text-gray-700 dark:text-gray-300">
              <input
                type="checkbox"
                checked={importOverwrite}
                onChange={(e) => setImportOverwrite(e.target.checked)}
                className="w-3.5 h-3.5 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]/30"
              />
              同名がある場合は上書きする
            </label>
            <div className="mb-3 p-2 rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-[11px] text-gray-700 dark:text-gray-300">
              {(() => {
                const baseName = pendingImport.name.trim();
                const exact = collections.find((c) => c.name.trim().toLowerCase() === baseName.toLowerCase());
                const finalName = importOverwrite && exact ? exact.name : getNextImportName(baseName);
                return <>保存名: <span className="font-semibold">{finalName}</span></>;
              })()}
            </div>
            <div className="text-[12px] text-gray-700 dark:text-gray-300 space-y-1 mb-3">
              <p><span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">名前:</span> {pendingImport.name}</p>
              {"period" in pendingImport.filters && <p><span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">区切り:</span> {String(pendingImport.filters.period)}</p>}
              {typeof pendingImport.filters.snapshotDate === "string" && pendingImport.filters.snapshotDate !== "" && (
                <p><span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">version:</span> {String(pendingImport.filters.snapshotDate)}</p>
              )}
              {typeof pendingImport.filters.platform === "string" && pendingImport.filters.platform !== "" && (
                <p><span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">媒体:</span> {String(pendingImport.filters.platform)}</p>
              )}
              {typeof pendingImport.filters.genre === "string" && pendingImport.filters.genre !== "" && (
                <p><span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">ジャンル:</span> {String(pendingImport.filters.genre)}</p>
              )}
              {typeof pendingImport.filters.topic === "string" && pendingImport.filters.topic !== "" && (
                <p><span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">トピック:</span> {String(pendingImport.filters.topic)}</p>
              )}
            </div>
            {pendingImport.normalizationNotes && pendingImport.normalizationNotes.length > 0 && (
              <div className="mb-3 p-2 rounded-lg border border-indigo-200 bg-indigo-50 text-[11px] text-gray-700 dark:text-gray-300">
                <p className="font-semibold mb-1">正規化補正</p>
                <div className="space-y-1">
                  {pendingImport.normalizationNotes.map((n) => (
                    <p key={`${n.key}-${n.before}-${n.after}`}>
                      <span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">{normalizationLabelMap[n.key] || n.key}:</span>{" "}
                      {normalizationValueLabel(n.key, n.before)} → {normalizationValueLabel(n.key, n.after)}
                    </p>
                  ))}
                </div>
              </div>
            )}
            {importOverwrite && (
              <div className="mb-3 p-2 rounded-lg border border-amber-200 bg-amber-50 text-[11px] text-gray-700 dark:text-gray-300">
                <p className="font-semibold mb-1">上書き時の変更点</p>
                {importDiffs.length === 0 ? (
                  <p className="text-gray-500 dark:text-gray-400 dark:text-gray-500">主要フィルタの差分はありません。</p>
                ) : (
                  <div className="space-y-1 max-h-28 overflow-auto">
                    {importDiffs.map((d) => (
                      <p key={d.key}>
                        <span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">{d.label}:</span> {d.before} → {d.after}
                      </p>
                    ))}
                  </div>
                )}
                {importAdvancedDiff && (
                  <p className="mt-1">
                    <span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">詳細フィルタ有効数:</span>{" "}
                    {importAdvancedDiff.beforeCount} → {importAdvancedDiff.afterCount}
                  </p>
                )}
                {importDeltaSummary && (
                  <p className="mt-1">
                    <span className="text-gray-500 dark:text-gray-400 dark:text-gray-500">差分サマリー:</span>{" "}
                    主要変更 {importDeltaSummary.changedMainFields}件 / 詳細 +{importDeltaSummary.increasedAdvanced} / -{importDeltaSummary.decreasedAdvanced}
                  </p>
                )}
              </div>
            )}
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setPendingImport(null);
                  setImportOverwrite(false);
                }}
                className="flex-1 px-3 py-1.5 text-[12px] font-medium text-gray-600 dark:text-gray-300 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                キャンセル
              </button>
              <button
                onClick={handleConfirmImport}
                className="flex-1 px-3 py-1.5 text-[12px] font-medium text-white bg-[#4A7DFF] rounded-lg hover:bg-[#3a6be8] transition-colors"
              >
                取り込む
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
