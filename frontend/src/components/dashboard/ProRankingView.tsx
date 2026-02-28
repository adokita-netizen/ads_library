"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";
import SmartSearchBar from "./SmartSearchBar";
import ProRankingTable from "./ProRankingTable";
import AdvancedFilterPanel, { type AdvancedFilters, defaultFilters, getActiveFilterCount } from "./AdvancedFilterPanel";
import DashboardKPI from "./DashboardKPI";
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

interface SearchCollection {
  id: number;
  name: string;
  filters: {
    genre?: string;
    platform?: string;
    query?: string;
    sortBy?: string;
    period?: string;
  };
  created_at?: string;
}

type PeriodType = "daily" | "weekly" | "monthly" | "all";
type SortType =
  | "cumulative_views"
  | "cumulative_spend"
  | "view_increase"
  | "like_increase"
  | "hit_score";
type ViewModeType = "table" | "card" | "gallery";

// ─── Constants ───

const periodOptions: { value: PeriodType; label: string; apiValue: string }[] =
  [
    { value: "daily", label: "日次", apiValue: "1d" },
    { value: "weekly", label: "週次", apiValue: "7d" },
    { value: "monthly", label: "月次", apiValue: "30d" },
    { value: "all", label: "全期間", apiValue: "all" },
  ];

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

// ─── Parent genre groups ───
const genreGroupLabels: Record<string, string> = {
  beauty: "美容系",
  health: "健康系",
  business: "ビジネス系",
  lifestyle: "ライフスタイル系",
  other: "その他",
};

// ─── Main Component ───

interface ProRankingViewProps {
  onAdSelect: (adId: number) => void;
}

export default function ProRankingView({ onAdSelect }: ProRankingViewProps) {
  // Filter state
  const [selectedGenre, setSelectedGenre] = useState("all");
  const [selectedPlatform, setSelectedPlatform] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortType>("cumulative_views");
  const [period, setPeriod] = useState<PeriodType>("weekly");

  // Genre master data
  const [genreGroups, setGenreGroups] = useState<GenreGroup[]>([]);
  const [genreList, setGenreList] = useState<GenreMasterItem[]>([]);
  const [genreLoading, setGenreLoading] = useState(false);
  const [showGenreSidebar, setShowGenreSidebar] = useState(true);

  // Search collections
  const [collections, setCollections] = useState<SearchCollection[]>([]);
  const [showCollections, setShowCollections] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const collectionsRef = useRef<HTMLDivElement>(null);

  // View mode
  const [viewMode, setViewMode] = useState<ViewModeType>("table");

  // B21: Advanced filter panel
  const [showAdvancedFilter, setShowAdvancedFilter] = useState(false);
  const [advancedFilters, setAdvancedFilters] = useState<AdvancedFilters>(defaultFilters);
  const activeFilterCount = getActiveFilterCount(advancedFilters);

  // Hit line threshold
  const [hitLineThreshold, setHitLineThreshold] = useState<number>(10000);

  // ─── Fetch genre master ───
  useEffect(() => {
    const fetchGenres = async () => {
      setGenreLoading(true);
      try {
        const data = await fetchApi<{
          genres?: GenreMasterItem[];
          groups?: GenreGroup[];
        }>("/rankings/genre-master");

        if (data.groups && data.groups.length > 0) {
          setGenreGroups(data.groups);
          const allItems = data.groups.flatMap((g) => g.items);
          setGenreList(allItems);
        } else if (data.genres && data.genres.length > 0) {
          setGenreList(data.genres);
          // Group by parent category
          const grouped: Record<string, GenreMasterItem[]> = {};
          data.genres.forEach((g) => {
            const parent = g.parent || "other";
            if (!grouped[parent]) grouped[parent] = [];
            grouped[parent].push(g);
          });
          setGenreGroups(
            Object.entries(grouped).map(([parent, items]) => ({
              parent,
              items,
            }))
          );
        }
      } catch {
        // Fall back to static genre options
        setGenreList(
          genreOptions.map((g) => ({
            value: g.value,
            label: g.label,
          }))
        );
      } finally {
        setGenreLoading(false);
      }
    };
    fetchGenres();
  }, []);

  // ─── Fetch search collections ───
  const fetchCollections = useCallback(async () => {
    try {
      const data = await fetchApi<{
        collections?: SearchCollection[];
        items?: SearchCollection[];
      }>("/rankings/search-collections");
      setCollections(data.collections || data.items || []);
    } catch {
      // Silently fail
    }
  }, []);

  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  // ─── Save collection ───
  const handleSaveCollection = async () => {
    if (!saveName.trim()) return;
    try {
      await fetchApi("/rankings/search-collections", {
        method: "POST",
        body: {
          name: saveName,
          filters: {
            genre: selectedGenre,
            platform: selectedPlatform,
            query: searchQuery,
            sortBy,
            period,
          },
        },
      });
      setSaveName("");
      setShowSaveDialog(false);
      fetchCollections();
    } catch {
      // Silently fail
    }
  };

  // ─── Delete collection ───
  const handleDeleteCollection = async (id: number) => {
    try {
      await fetchApi(`/rankings/search-collections/${id}`, {
        method: "DELETE",
      });
      fetchCollections();
    } catch {
      // Silently fail
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
    setShowCollections(false);
  };

  // Close collections dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        collectionsRef.current &&
        !collectionsRef.current.contains(e.target as Node)
      ) {
        setShowCollections(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const currentPeriodApi =
    periodOptions.find((p) => p.value === period)?.apiValue || "7d";

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#f8f9fb]">
      {/* ─── Dashboard KPI Cards ─── */}
      <div className="shrink-0 px-5 pt-4 pb-0 bg-[#f8f9fb]">
        <DashboardKPI />
      </div>

      {/* ─── Top Header Bar ─── */}
      <div className="shrink-0 bg-white border-b border-gray-200">
        <div className="px-5 py-3">
          {/* Title row */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <svg
                  className="w-5 h-5 text-[#4A7DFF]"
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
                <h1 className="text-[16px] font-bold text-gray-900">
                  PRO DATABASE
                </h1>
              </div>
              <span className="text-[11px] text-gray-400">
                広告データベース分析
              </span>
            </div>

            {/* Right: Collections dropdown */}
            <div className="relative" ref={collectionsRef}>
              <button
                onClick={() => setShowCollections(!showCollections)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors"
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
                <div className="absolute right-0 top-full mt-1 w-72 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
                  <div className="p-3 border-b border-gray-100">
                    <p className="text-[12px] font-semibold text-gray-700">
                      保存済み検索条件
                    </p>
                  </div>
                  {collections.length === 0 ? (
                    <div className="p-4 text-center">
                      <p className="text-[11px] text-gray-400">
                        保存された検索条件はありません
                      </p>
                    </div>
                  ) : (
                    <div className="max-h-60 overflow-y-auto">
                      {collections.map((c) => (
                        <div
                          key={c.id}
                          className="flex items-center justify-between px-3 py-2 hover:bg-gray-50 transition-colors"
                        >
                          <button
                            onClick={() => handleApplyCollection(c)}
                            className="flex-1 text-left text-[12px] text-gray-700 font-medium truncate"
                          >
                            {c.name}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteCollection(c.id);
                            }}
                            className="shrink-0 p-1 text-gray-300 hover:text-red-400 transition-colors"
                          >
                            <svg
                              className="w-3.5 h-3.5"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M6 18L18 6M6 6l12 12"
                              />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Search bar + period toggle row */}
          <div className="flex items-center gap-3 flex-wrap">
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
                      ? "bg-white text-[#4A7DFF] shadow-sm"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* View mode toggle */}
            <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => setViewMode("table")}
                className={`p-1.5 rounded-md transition-all ${
                  viewMode === "table"
                    ? "bg-white text-[#4A7DFF] shadow-sm"
                    : "text-gray-400 hover:text-gray-600"
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
                    ? "bg-white text-[#4A7DFF] shadow-sm"
                    : "text-gray-400 hover:text-gray-600"
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
                    ? "bg-white text-[#4A7DFF] shadow-sm"
                    : "text-gray-400 hover:text-gray-600"
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

          {/* Filter chips row */}
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            {/* Platform filter */}
            <select
              value={selectedPlatform}
              onChange={(e) => setSelectedPlatform(e.target.value)}
              className="text-[11px] px-2.5 py-1 bg-gray-50 border border-gray-200 rounded-lg text-gray-600 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/30"
            >
              {platformFilterOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            {/* Sort */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortType)}
              className="text-[11px] px-2.5 py-1 bg-gray-50 border border-gray-200 rounded-lg text-gray-600 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/30"
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
              className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 bg-gray-50 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors"
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
              onClick={() => setShowGenreSidebar(!showGenreSidebar)}
              className="text-[11px] px-2.5 py-1 bg-gray-50 border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-100 transition-colors lg:hidden"
            >
              {showGenreSidebar ? "ジャンルを非表示" : "ジャンル表示"}
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
          </div>
        </div>
      </div>

      {/* ─── Main Content Area ─── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ─── Genre Sidebar ─── */}
        {showGenreSidebar && (
          <aside className="shrink-0 w-52 bg-white border-r border-gray-200 overflow-y-auto custom-scrollbar hidden lg:block">
            <div className="py-3">
              {/* All genres option */}
              <button
                onClick={() => setSelectedGenre("all")}
                className={`w-full flex items-center justify-between px-4 py-2 text-[12px] font-medium transition-colors ${
                  selectedGenre === "all"
                    ? "bg-[#EEF2FF] text-[#4A7DFF] border-r-2 border-[#4A7DFF]"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                <span>すべての広告</span>
              </button>

              {/* Genre groups */}
              {genreGroups.length > 0
                ? genreGroups.map((group) => (
                    <div key={group.parent} className="mt-2">
                      <p className="px-4 py-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                        {genreGroupLabels[group.parent] || group.parent}
                      </p>
                      {group.items.map((g) => (
                        <button
                          key={g.value}
                          onClick={() => setSelectedGenre(g.value)}
                          className={`w-full flex items-center justify-between px-4 py-1.5 text-[12px] transition-colors ${
                            selectedGenre === g.value
                              ? "bg-[#EEF2FF] text-[#4A7DFF] font-medium border-r-2 border-[#4A7DFF]"
                              : "text-gray-600 hover:bg-gray-50"
                          }`}
                        >
                          <span className="truncate">{g.label}</span>
                          {g.count !== undefined && (
                            <span className="ml-1 text-[10px] text-gray-400">
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
                            : "text-gray-600 hover:bg-gray-50"
                        }`}
                      >
                        <span className="truncate">{g.label}</span>
                        {g.count !== undefined && (
                          <span className="ml-1 text-[10px] text-gray-400">
                            {g.count}
                          </span>
                        )}
                      </button>
                    ))}
            </div>
          </aside>
        )}

        {/* ─── Table Content ─── */}
        <div className="flex-1 overflow-auto custom-scrollbar p-4">
          <ProRankingTable
            genre={selectedGenre}
            platform={selectedPlatform}
            searchQuery={searchQuery}
            sortBy={sortBy}
            period={currentPeriodApi}
            onAdSelect={onAdSelect}
            hitLineThreshold={hitLineThreshold}
          />
        </div>
      </div>

      {/* ─── Activity Feed (collapsible bottom bar) ─── */}
      <div className="shrink-0 px-4 pb-3">
        <ActivityFeed onAdSelect={onAdSelect} />
      </div>

      {/* ─── Save Collection Dialog ─── */}
      {showSaveDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
          onClick={() => setShowSaveDialog(false)}
        >
          <div
            className="bg-white rounded-xl shadow-xl border border-gray-200 p-5 w-80"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-[14px] font-bold text-gray-900 mb-3">
              検索条件を保存
            </h3>
            <input
              type="text"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder="検索名を入力..."
              className="w-full px-3 py-2 text-[13px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF] mb-3"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSaveCollection();
              }}
              autoFocus
            />
            <div className="text-[11px] text-gray-400 mb-3 space-y-0.5">
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
              {searchQuery && <p>キーワード: {searchQuery}</p>}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowSaveDialog(false)}
                className="flex-1 px-3 py-1.5 text-[12px] font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                キャンセル
              </button>
              <button
                onClick={handleSaveCollection}
                disabled={!saveName.trim()}
                className="flex-1 px-3 py-1.5 text-[12px] font-medium text-white bg-[#4A7DFF] rounded-lg hover:bg-[#3a6be8] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                保存
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
    </div>
  );
}
