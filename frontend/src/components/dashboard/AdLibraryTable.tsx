"use client";

import { useState, useEffect, useMemo } from "react";
import { rankingsApi, lpAnalysisApi, adsApi } from "@/lib/api";

interface AdLibraryTableProps {
  onAdSelect: (adId: number) => void;
}

// Filter bar types
type AdType = "all" | "video" | "banner" | "carousel" | "search";
type MediaType = "all" | "youtube" | "shorts" | "facebook" | "instagram" | "tiktok" | "line" | "yahoo" | "x_twitter" | "pinterest" | "smartnews" | "google_ads" | "gunosy";
type GenreType = "all" | "ec_d2c" | "app" | "finance" | "education" | "beauty" | "food" | "gaming" | "health" | "technology" | "real_estate" | "travel" | "other";
type FormatType = "all" | "video" | "banner" | "carousel";
type VersionType = "latest" | "all_versions";
type IntervalType = "2days" | "7days" | "14days" | "30days";
type SortField = "rank" | "play_increase" | "spend_increase" | "total_plays" | "total_spend" | "published" | "duration";

interface FilterState {
  adType: AdType;
  media: MediaType;
  genre: GenreType;
  format: FormatType;
  version: VersionType;
  interval: IntervalType;
  search: string;
}

interface MockAd {
  id: number;
  rank: number;
  thumbnail: string;
  duration: number;
  platform: string;
  managementId: string;
  productName: string;
  genre: string;
  destinationType: string;
  playIncrease: number;
  spendIncrease: number;
  spendBar: number; // 0-100 percentage
  isHit: boolean;
  totalPlays: number;
  totalSpend: number;
  publishedDate: string;
  adUrl: string;
  destination: string;
}


const platformLabels: Record<string, string> = {
  youtube: "YT",
  shorts: "S",
  tiktok: "TT",
  facebook: "FB",
  instagram: "IG",
  line: "L",
  yahoo: "Y!",
  x_twitter: "X",
  x: "X",
  pinterest: "Pin",
  smartnews: "SN",
  google_ads: "G",
  gunosy: "Gn",
};

const platformColors: Record<string, string> = {
  youtube: "platform-youtube",
  shorts: "bg-red-400",
  tiktok: "platform-tiktok",
  facebook: "platform-facebook",
  instagram: "platform-instagram",
  line: "platform-line",
  yahoo: "platform-yahoo",
  x_twitter: "platform-x",
  x: "platform-x",
  pinterest: "bg-red-600",
  smartnews: "bg-sky-600",
  google_ads: "bg-blue-500",
  gunosy: "bg-orange-500",
};

const mediaFilterOptions: { value: MediaType; label: string }[] = [
  { value: "all", label: "全媒体" },
  { value: "youtube", label: "YouTube" },
  { value: "shorts", label: "YouTube Shorts" },
  { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" },
  { value: "tiktok", label: "TikTok" },
  { value: "line", label: "LINE" },
  { value: "yahoo", label: "Yahoo!" },
  { value: "x_twitter", label: "X (Twitter)" },
  { value: "pinterest", label: "Pinterest" },
  { value: "smartnews", label: "SmartNews" },
  { value: "google_ads", label: "Google Ads" },
  { value: "gunosy", label: "Gunosy" },
];

const genreFilterOptions: { value: GenreType; label: string }[] = [
  { value: "all", label: "全ジャンル" },
  { value: "ec_d2c", label: "EC・D2C" },
  { value: "app", label: "アプリ" },
  { value: "finance", label: "金融" },
  { value: "education", label: "教育" },
  { value: "beauty", label: "美容・コスメ" },
  { value: "food", label: "食品" },
  { value: "gaming", label: "ゲーム" },
  { value: "health", label: "健康食品" },
  { value: "technology", label: "テクノロジー" },
  { value: "real_estate", label: "不動産" },
  { value: "travel", label: "旅行" },
  { value: "other", label: "その他" },
];

const adTypeOptions: { value: AdType; label: string }[] = [
  { value: "all", label: "広告の全種類" },
  { value: "video", label: "動画広告" },
  { value: "banner", label: "バナー広告" },
  { value: "carousel", label: "カルーセル広告" },
  { value: "search", label: "検索広告" },
];

const intervalOptions: { value: IntervalType; label: string }[] = [
  { value: "2days", label: "2日間隔の統計" },
  { value: "7days", label: "7日間隔の統計" },
  { value: "14days", label: "14日間隔の統計" },
  { value: "30days", label: "30日間隔の統計" },
];

function formatNumber(n: number): string {
  if (n >= 100000000) return (n / 100000000).toFixed(1) + "億";
  if (n >= 10000) return (n / 10000).toFixed(0) + "万";
  return n.toLocaleString();
}

function formatYen(n: number): string {
  if (n >= 100000000) return "¥" + (n / 100000000).toFixed(1) + "億";
  if (n >= 10000) return "¥" + (n / 10000).toFixed(0) + "万";
  return "¥" + n.toLocaleString();
}

export default function AdLibraryTable({ onAdSelect }: AdLibraryTableProps) {
  const [filters, setFilters] = useState<FilterState>({
    adType: "all",
    media: "all",
    genre: "all",
    format: "all",
    version: "latest",
    interval: "2days",
    search: "",
  });
  const [sortField, setSortField] = useState<SortField>("rank");
  const [sortAsc, setSortAsc] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  const [ads, setAds] = useState<MockAd[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCrawlModal, setShowCrawlModal] = useState(false);
  const [fetchTrigger, setFetchTrigger] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const params: Record<string, string | number | undefined> = {};
        if (filters.media !== "all") params.platform = filters.media;
        if (filters.genre !== "all") params.genre = filters.genre;
        if (filters.interval === "7days") params.period = "weekly";
        else if (filters.interval === "14days") params.period = "biweekly";
        else if (filters.interval === "30days") params.period = "monthly";
        else params.period = "daily";

        const response = await rankingsApi.getProducts(params as Parameters<typeof rankingsApi.getProducts>[0]);
        const items = response.data?.items || response.data?.rankings || response.data?.results;
        if (Array.isArray(items) && items.length > 0) {
          const mapped: MockAd[] = items.map((item: Record<string, unknown>, idx: number) => ({
            id: (item.ad_id as number) || idx + 1,
            rank: (item.rank as number) || idx + 1,
            thumbnail: (item.thumbnail as string) || "",
            duration: (item.duration_seconds as number) || 0,
            platform: (item.platform as string) || "youtube",
            managementId: (item.management_id as string) || `AD-${item.ad_id || idx + 1}`,
            productName: (item.product_name as string) || "不明",
            genre: (item.genre as string) || "",
            destinationType: (item.destination_type as string) || "",
            playIncrease: (item.view_increase as number) || 0,
            spendIncrease: (item.spend_increase as number) || 0,
            spendBar: Math.min(100, Math.round(((item.spend_increase as number) || 0) / 100000)),
            isHit: (item.is_hit as boolean) || false,
            totalPlays: (item.cumulative_views as number) || 0,
            totalSpend: (item.cumulative_spend as number) || 0,
            publishedDate: (item.published_date as string) || (item.created_at as string) || "",
            adUrl: (item.ad_url as string) || "",
            destination: (item.destination_url as string) || "",
          }));
          setAds(mapped);
        }
      } catch (error) {
        console.error("Failed to fetch ad data:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [filters.media, filters.genre, filters.interval, fetchTrigger]);

  const filteredAds = useMemo(() => {
    let result = [...ads];

    // Apply media filter (client-side for additional filtering beyond API)
    if (filters.media !== "all") {
      result = result.filter((a) => a.platform === filters.media);
    }

    // Apply search filter
    if (filters.search) {
      const q = filters.search.toLowerCase();
      result = result.filter(
        (a) =>
          a.productName.toLowerCase().includes(q) ||
          a.managementId.toLowerCase().includes(q) ||
          a.genre.toLowerCase().includes(q)
      );
    }

    // Sort
    result.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "rank": cmp = a.rank - b.rank; break;
        case "play_increase": cmp = a.playIncrease - b.playIncrease; break;
        case "spend_increase": cmp = a.spendIncrease - b.spendIncrease; break;
        case "total_plays": cmp = a.totalPlays - b.totalPlays; break;
        case "total_spend": cmp = a.totalSpend - b.totalSpend; break;
        case "published": cmp = a.publishedDate.localeCompare(b.publishedDate); break;
        case "duration": cmp = a.duration - b.duration; break;
      }
      return sortAsc ? cmp : -cmp;
    });

    return result;
  }, [ads, filters, sortField, sortAsc]);

  const totalPages = Math.ceil(filteredAds.length / pageSize);
  const paginatedAds = filteredAds.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === "rank");
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => (
    <span className={`ml-0.5 inline-block ${sortField === field ? "text-[#4A7DFF]" : "text-gray-300"}`}>
      {sortField === field ? (sortAsc ? "▲" : "▼") : "▼"}
    </span>
  );

  return (
    <div className="flex flex-col h-full">
      {/* Filter Bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-200 bg-white flex-wrap">
        {/* Ad type filter */}
        <select
          className="select-filter"
          value={filters.adType}
          onChange={(e) => setFilters({ ...filters, adType: e.target.value as AdType })}
        >
          {adTypeOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        {/* Media filter */}
        <select
          className="select-filter"
          value={filters.media}
          onChange={(e) => setFilters({ ...filters, media: e.target.value as MediaType })}
        >
          {mediaFilterOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        {/* Genre filter */}
        <select
          className="select-filter"
          value={filters.genre}
          onChange={(e) => setFilters({ ...filters, genre: e.target.value as GenreType })}
        >
          {genreFilterOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        {/* Format filter */}
        <select
          className="select-filter"
          value={filters.format}
          onChange={(e) => setFilters({ ...filters, format: e.target.value as FormatType })}
        >
          <option value="all">動画/バナー/カルーセル</option>
          <option value="video">動画</option>
          <option value="banner">バナー</option>
          <option value="carousel">カルーセル</option>
        </select>

        {/* Version */}
        <select
          className="select-filter"
          value={filters.version}
          onChange={(e) => setFilters({ ...filters, version: e.target.value as VersionType })}
        >
          <option value="latest">最新版</option>
          <option value="all_versions">全バージョン</option>
        </select>

        {/* Interval */}
        <select
          className="select-filter"
          value={filters.interval}
          onChange={(e) => setFilters({ ...filters, interval: e.target.value as IntervalType })}
        >
          {intervalOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

        <div className="flex-1" />

        {/* Crawl button */}
        <button
          className="px-3 py-1.5 rounded-md text-xs font-medium text-white bg-[#4A7DFF] hover:bg-[#3a6dee] transition-colors whitespace-nowrap"
          onClick={() => setShowCrawlModal(true)}
        >
          広告クロール
        </button>

        {/* Search */}
        <div className="relative">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            type="text"
            placeholder="商材名・管理番号で検索"
            className="input pl-8 w-56 text-xs"
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
          />
        </div>

        {/* Results count */}
        <span className="text-[11px] text-gray-400 whitespace-nowrap">
          {filteredAds.length}件の結果
        </span>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto custom-scrollbar">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
            <span className="ml-2 text-xs text-gray-400">読み込み中...</span>
          </div>
        )}
        {!loading && filteredAds.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-gray-400">
            <svg className="w-10 h-10 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m6 4.125l2.25 2.25m0 0l2.25 2.25M12 13.875l2.25-2.25M12 13.875l-2.25 2.25M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
            </svg>
            <p className="text-xs">データがありません</p>
            <p className="text-[10px] mt-1 mb-3">広告をクロールするか、フィルター条件を変更してください</p>
            <button
              className="px-4 py-2 rounded-md text-xs font-medium text-white bg-[#4A7DFF] hover:bg-[#3a6dee] transition-colors"
              onClick={() => setShowCrawlModal(true)}
            >
              広告クロールを開始
            </button>
          </div>
        )}
        <table className="data-table">
          <thead>
            <tr>
              <th className="w-12 text-center cursor-pointer" onClick={() => handleSort("rank")}>
                順位<SortIcon field="rank" />
              </th>
              <th className="w-24">サムネイル</th>
              <th>管理番号</th>
              <th>商材名</th>
              <th>ジャンル</th>
              <th>遷移先タイプ</th>
              <th className="text-right cursor-pointer" onClick={() => handleSort("play_increase")}>
                再生増加数<SortIcon field="play_increase" />
              </th>
              <th className="text-right cursor-pointer min-w-[160px]" onClick={() => handleSort("spend_increase")}>
                予想消化増加額<SortIcon field="spend_increase" />
              </th>
              <th className="text-right cursor-pointer" onClick={() => handleSort("total_plays")}>
                累計再生回数<SortIcon field="total_plays" />
              </th>
              <th className="text-right cursor-pointer" onClick={() => handleSort("total_spend")}>
                累計予想消化額<SortIcon field="total_spend" />
              </th>
              <th className="cursor-pointer" onClick={() => handleSort("published")}>
                公開日<SortIcon field="published" />
              </th>
              <th className="text-center cursor-pointer" onClick={() => handleSort("duration")}>
                秒数<SortIcon field="duration" />
              </th>
              <th>広告URL</th>
              <th>遷移先</th>
            </tr>
          </thead>
          <tbody>
            {paginatedAds.map((ad) => (
              <tr key={ad.id} onClick={() => onAdSelect(ad.id)}>
                {/* Rank */}
                <td className="text-center">
                  <span className={`inline-flex items-center justify-center w-6 h-6 rounded text-xs font-bold ${
                    ad.rank <= 3
                      ? "bg-[#4A7DFF] text-white"
                      : "bg-gray-100 text-gray-500"
                  }`}>
                    {ad.rank}
                  </span>
                </td>

                {/* Thumbnail */}
                <td>
                  <div className="relative w-20 h-12 rounded overflow-hidden bg-gray-100 group">
                    <div className="absolute inset-0 bg-gradient-to-br from-gray-200 to-gray-300 flex items-center justify-center">
                      <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                      </svg>
                    </div>
                    {/* Duration overlay */}
                    <span className="absolute bottom-0.5 right-0.5 bg-black/75 text-white text-[9px] px-1 rounded leading-relaxed">
                      {Math.floor(ad.duration / 60)}:{(ad.duration % 60).toString().padStart(2, "0")}
                    </span>
                    {/* Platform icon */}
                    <span className={`absolute top-0.5 left-0.5 platform-icon ${platformColors[ad.platform]}`}>
                      {platformLabels[ad.platform]}
                    </span>
                  </div>
                </td>

                {/* Management ID */}
                <td className="text-[11px] text-gray-400 font-mono">{ad.managementId}</td>

                {/* Product Name */}
                <td>
                  <span className="text-[13px] font-medium text-gray-900">{ad.productName}</span>
                </td>

                {/* Genre */}
                <td>
                  <span className="badge-blue text-[10px]">{ad.genre}</span>
                </td>

                {/* Destination Type */}
                <td>
                  <span className={`badge text-[10px] ${
                    ad.destinationType === "記事LP"
                      ? "bg-purple-100 text-purple-700"
                      : "bg-emerald-100 text-emerald-700"
                  }`}>
                    {ad.destinationType}
                  </span>
                </td>

                {/* Play Increase */}
                <td className="text-right">
                  <span className="text-[13px] font-semibold text-gray-900">{formatNumber(ad.playIncrease)}</span>
                </td>

                {/* Spend Increase with bar */}
                <td className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div className="flex items-center gap-1.5 flex-1">
                      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full bg-[#4A7DFF]"
                          style={{ width: `${ad.spendBar}%` }}
                        />
                      </div>
                      {ad.isHit && (
                        <span className="shrink-0 rounded bg-red-500 px-1 py-px text-[8px] font-bold text-white leading-none">
                          HIT
                        </span>
                      )}
                    </div>
                    <span className="text-[13px] font-semibold text-gray-900 whitespace-nowrap">
                      {formatYen(ad.spendIncrease)}
                    </span>
                  </div>
                </td>

                {/* Total Plays */}
                <td className="text-right">
                  <span className="text-[12px] text-gray-600">{formatNumber(ad.totalPlays)}</span>
                </td>

                {/* Total Spend */}
                <td className="text-right">
                  <span className="text-[12px] text-gray-600">{formatYen(ad.totalSpend)}</span>
                </td>

                {/* Published Date */}
                <td>
                  <span className="text-[11px] text-gray-500">{ad.publishedDate}</span>
                </td>

                {/* Duration */}
                <td className="text-center">
                  <span className="text-[12px] text-gray-600">{ad.duration}秒</span>
                </td>

                {/* Ad URL */}
                <td>
                  <button
                    className="text-[#4A7DFF] hover:underline text-[11px]"
                    onClick={(e) => { e.stopPropagation(); window.open(ad.adUrl, "_blank"); }}
                  >
                    リンク
                  </button>
                </td>

                {/* Destination */}
                <td>
                  {ad.destination ? (
                    <div className="flex items-center gap-1">
                      <button
                        className="text-[#4A7DFF] hover:underline text-[11px] max-w-[80px] truncate"
                        onClick={(e) => { e.stopPropagation(); window.open(ad.destination, "_blank"); }}
                        title={ad.destination}
                      >
                        遷移先
                      </button>
                      <button
                        className="text-[9px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 hover:bg-purple-100 transition-colors whitespace-nowrap"
                        onClick={(e) => {
                          e.stopPropagation();
                          lpAnalysisApi.crawl({ url: ad.destination, ad_id: ad.id, auto_analyze: true })
                            .then(() => { alert("LP分析を開始しました"); })
                            .catch(() => { alert("LP分析の開始に失敗しました"); });
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
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200 bg-white text-xs text-gray-500">
        <span>
          {filteredAds.length}件中 {(currentPage - 1) * pageSize + 1}-{Math.min(currentPage * pageSize, filteredAds.length)}件を表示
        </span>
        <div className="flex items-center gap-1">
          <button
            className="btn-ghost text-[11px] disabled:opacity-30"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(currentPage - 1)}
          >
            ← 前へ
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
            <button
              key={page}
              className={`w-7 h-7 rounded text-[11px] font-medium ${
                page === currentPage
                  ? "bg-[#4A7DFF] text-white"
                  : "hover:bg-gray-100 text-gray-600"
              }`}
              onClick={() => setCurrentPage(page)}
            >
              {page}
            </button>
          ))}
          <button
            className="btn-ghost text-[11px] disabled:opacity-30"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage(currentPage + 1)}
          >
            次へ →
          </button>
        </div>
      </div>
      {/* Crawl Modal */}
      {showCrawlModal && (
        <CrawlModal
          onClose={() => setShowCrawlModal(false)}
          onSuccess={() => {
            setShowCrawlModal(false);
            setFetchTrigger((n) => n + 1);
          }}
        />
      )}
    </div>
  );
}

const ALL_CRAWL_PLATFORMS = [
  { value: "youtube", label: "YouTube" },
  { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" },
  { value: "tiktok", label: "TikTok" },
  { value: "x_twitter", label: "X (Twitter)" },
  { value: "line", label: "LINE" },
  { value: "yahoo", label: "Yahoo!" },
  { value: "pinterest", label: "Pinterest" },
  { value: "smartnews", label: "SmartNews" },
  { value: "google_ads", label: "Google Ads" },
  { value: "gunosy", label: "Gunosy" },
];

function CrawlModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [query, setQuery] = useState("");
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(
    ALL_CRAWL_PLATFORMS.map((p) => p.value)
  );
  const [category, setCategory] = useState("");
  const [limit, setLimit] = useState(20);
  const [crawling, setCrawling] = useState(false);
  const [message, setMessage] = useState("");

  const togglePlatform = (value: string) => {
    setSelectedPlatforms((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
  };

  const toggleAll = () => {
    if (selectedPlatforms.length === ALL_CRAWL_PLATFORMS.length) {
      setSelectedPlatforms([]);
    } else {
      setSelectedPlatforms(ALL_CRAWL_PLATFORMS.map((p) => p.value));
    }
  };

  const handleCrawl = async () => {
    if (!query.trim()) return;
    if (selectedPlatforms.length === 0) {
      setMessage("媒体を1つ以上選択してください");
      return;
    }
    setCrawling(true);
    setMessage("");
    try {
      const res = await adsApi.crawl({
        query: query.trim(),
        platforms: selectedPlatforms,
        category: category || undefined,
        limit_per_platform: limit,
        auto_analyze: true,
      });
      setMessage(res.data?.message || `クロールを開始しました（${selectedPlatforms.length}媒体）`);
      setTimeout(() => onSuccess(), 2000);
    } catch {
      setMessage("クロールの開始に失敗しました。バックエンドの接続を確認してください。");
      setCrawling(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-base font-semibold text-gray-900">広告クロール</h3>
        <p className="text-[11px] text-gray-400 mt-0.5">各媒体の広告ライブラリから広告データを収集します</p>

        <div className="mt-4 space-y-4">
          {/* Query */}
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              検索キーワード <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="商材名、競合名、カテゴリなど"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF]"
              autoFocus
            />
          </div>

          {/* Platforms */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-gray-700">対象媒体</label>
              <button className="text-[10px] text-[#4A7DFF] hover:underline" onClick={toggleAll}>
                {selectedPlatforms.length === ALL_CRAWL_PLATFORMS.length ? "全解除" : "全選択"}
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {ALL_CRAWL_PLATFORMS.map((p) => (
                <button
                  key={p.value}
                  className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors border ${
                    selectedPlatforms.includes(p.value)
                      ? "bg-[#4A7DFF] text-white border-[#4A7DFF]"
                      : "bg-white text-gray-500 border-gray-200 hover:border-gray-300"
                  }`}
                  onClick={() => togglePlatform(p.value)}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-gray-400 mt-1">{selectedPlatforms.length}媒体を選択中</p>
          </div>

          {/* Category & Limit row */}
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-700 mb-1">ジャンル（任意）</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF]"
              >
                <option value="">指定なし</option>
                {genreFilterOptions.filter((g) => g.value !== "all").map((g) => (
                  <option key={g.value} value={g.value}>{g.label}</option>
                ))}
              </select>
            </div>
            <div className="w-28">
              <label className="block text-xs font-medium text-gray-700 mb-1">取得件数/媒体</label>
              <input
                type="number"
                value={limit}
                onChange={(e) => setLimit(Math.max(1, Math.min(100, Number(e.target.value))))}
                min={1}
                max={100}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF]"
              />
            </div>
          </div>
        </div>

        {/* Message */}
        {message && (
          <p className={`mt-3 text-xs ${message.includes("失敗") ? "text-red-500" : "text-green-600"}`}>
            {message}
          </p>
        )}

        {/* Actions */}
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-100 transition-colors">
            キャンセル
          </button>
          <button
            onClick={handleCrawl}
            disabled={crawling || !query.trim()}
            className="px-4 py-2 rounded-lg text-xs font-medium text-white bg-[#4A7DFF] hover:bg-[#3a6dee] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {crawling ? "クロール中..." : "クロール開始"}
          </button>
        </div>
      </div>
    </div>
  );
}
