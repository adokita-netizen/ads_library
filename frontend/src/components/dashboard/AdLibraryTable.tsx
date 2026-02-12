"use client";

import { useState, useEffect, useMemo } from "react";
import { rankingsApi } from "@/lib/api";

interface AdLibraryTableProps {
  onAdSelect: (adId: number) => void;
}

// Filter bar types
type AdType = "all" | "video" | "banner" | "carousel" | "search";
type MediaType = "all" | "youtube" | "shorts" | "facebook" | "instagram" | "tiktok" | "line" | "yahoo" | "x";
type FormatType = "all" | "video" | "banner" | "carousel";
type VersionType = "latest" | "all_versions";
type IntervalType = "2days" | "7days" | "14days" | "30days";
type SortField = "rank" | "play_increase" | "spend_increase" | "total_plays" | "total_spend" | "published" | "duration";

interface FilterState {
  adType: AdType;
  media: MediaType;
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

// Mock data matching DPro style
const mockAds: MockAd[] = [
  {
    id: 1, rank: 1, thumbnail: "", duration: 30, platform: "youtube",
    managementId: "AD-2025-00147", productName: "スキンケアセラムV3", genre: "美容・コスメ",
    destinationType: "記事LP", playIncrease: 1250000, spendIncrease: 8500000,
    spendBar: 95, isHit: true, totalPlays: 45200000, totalSpend: 128000000,
    publishedDate: "2025-12-15", adUrl: "https://ads.example.com/v/147", destination: "https://lp.example.com/serum-v3"
  },
  {
    id: 2, rank: 2, thumbnail: "", duration: 15, platform: "tiktok",
    managementId: "AD-2025-00283", productName: "ダイエットサプリメントX", genre: "健康食品",
    destinationType: "EC直接", playIncrease: 980000, spendIncrease: 6200000,
    spendBar: 82, isHit: true, totalPlays: 32100000, totalSpend: 95000000,
    publishedDate: "2025-12-18", adUrl: "https://ads.example.com/v/283", destination: "https://shop.example.com/diet-x"
  },
  {
    id: 3, rank: 3, thumbnail: "", duration: 60, platform: "facebook",
    managementId: "AD-2025-00391", productName: "育毛トニックPRO", genre: "ヘアケア",
    destinationType: "記事LP", playIncrease: 720000, spendIncrease: 5100000,
    spendBar: 68, isHit: false, totalPlays: 28500000, totalSpend: 82000000,
    publishedDate: "2025-12-10", adUrl: "https://ads.example.com/v/391", destination: "https://lp.example.com/tonic-pro"
  },
  {
    id: 4, rank: 4, thumbnail: "", duration: 20, platform: "instagram",
    managementId: "AD-2025-00412", productName: "プロテインバーFIT", genre: "健康食品",
    destinationType: "EC直接", playIncrease: 650000, spendIncrease: 4300000,
    spendBar: 58, isHit: false, totalPlays: 22300000, totalSpend: 67000000,
    publishedDate: "2025-12-20", adUrl: "https://ads.example.com/v/412", destination: "https://shop.example.com/fit-bar"
  },
  {
    id: 5, rank: 5, thumbnail: "", duration: 45, platform: "youtube",
    managementId: "AD-2025-00523", productName: "美白クリームルーチェ", genre: "美容・コスメ",
    destinationType: "記事LP", playIncrease: 580000, spendIncrease: 3800000,
    spendBar: 50, isHit: false, totalPlays: 19800000, totalSpend: 58000000,
    publishedDate: "2025-12-08", adUrl: "https://ads.example.com/v/523", destination: "https://lp.example.com/luce"
  },
  {
    id: 6, rank: 6, thumbnail: "", duration: 10, platform: "shorts",
    managementId: "AD-2025-00634", productName: "アイクリームモイスト", genre: "美容・コスメ",
    destinationType: "EC直接", playIncrease: 510000, spendIncrease: 3200000,
    spendBar: 42, isHit: false, totalPlays: 16500000, totalSpend: 45000000,
    publishedDate: "2025-12-22", adUrl: "https://ads.example.com/v/634", destination: "https://shop.example.com/eyecream"
  },
  {
    id: 7, rank: 7, thumbnail: "", duration: 30, platform: "tiktok",
    managementId: "AD-2025-00745", productName: "酵素ドリンクナチュラ", genre: "健康食品",
    destinationType: "記事LP", playIncrease: 430000, spendIncrease: 2800000,
    spendBar: 37, isHit: false, totalPlays: 14200000, totalSpend: 39000000,
    publishedDate: "2025-12-05", adUrl: "https://ads.example.com/v/745", destination: "https://lp.example.com/natura"
  },
  {
    id: 8, rank: 8, thumbnail: "", duration: 25, platform: "facebook",
    managementId: "AD-2025-00856", productName: "CBDオイルリラクス", genre: "健康・リラックス",
    destinationType: "EC直接", playIncrease: 380000, spendIncrease: 2400000,
    spendBar: 32, isHit: false, totalPlays: 12100000, totalSpend: 34000000,
    publishedDate: "2025-12-12", adUrl: "https://ads.example.com/v/856", destination: "https://shop.example.com/cbd"
  },
  {
    id: 9, rank: 9, thumbnail: "", duration: 15, platform: "line",
    managementId: "AD-2025-00967", productName: "マウスウォッシュクリア", genre: "オーラルケア",
    destinationType: "記事LP", playIncrease: 320000, spendIncrease: 2100000,
    spendBar: 28, isHit: false, totalPlays: 10500000, totalSpend: 28000000,
    publishedDate: "2025-12-17", adUrl: "https://ads.example.com/v/967", destination: "https://lp.example.com/mouthwash"
  },
  {
    id: 10, rank: 10, thumbnail: "", duration: 35, platform: "yahoo",
    managementId: "AD-2025-01078", productName: "葉酸サプリママケア", genre: "健康食品",
    destinationType: "EC直接", playIncrease: 280000, spendIncrease: 1800000,
    spendBar: 24, isHit: false, totalPlays: 8900000, totalSpend: 24000000,
    publishedDate: "2025-12-14", adUrl: "https://ads.example.com/v/1078", destination: "https://shop.example.com/mamacare"
  },
  {
    id: 11, rank: 11, thumbnail: "", duration: 20, platform: "x",
    managementId: "AD-2025-01189", productName: "シワ改善クリームリペア", genre: "美容・コスメ",
    destinationType: "記事LP", playIncrease: 240000, spendIncrease: 1500000,
    spendBar: 20, isHit: false, totalPlays: 7600000, totalSpend: 21000000,
    publishedDate: "2025-12-19", adUrl: "https://ads.example.com/v/1189", destination: "https://lp.example.com/repair"
  },
  {
    id: 12, rank: 12, thumbnail: "", duration: 60, platform: "youtube",
    managementId: "AD-2025-01290", productName: "除毛クリームスムース", genre: "美容・コスメ",
    destinationType: "EC直接", playIncrease: 210000, spendIncrease: 1300000,
    spendBar: 17, isHit: false, totalPlays: 6800000, totalSpend: 18000000,
    publishedDate: "2025-12-06", adUrl: "https://ads.example.com/v/1290", destination: "https://shop.example.com/smooth"
  },
];

const platformLabels: Record<string, string> = {
  youtube: "YT",
  shorts: "S",
  tiktok: "TT",
  facebook: "FB",
  instagram: "IG",
  line: "L",
  yahoo: "Y!",
  x: "X",
};

const platformColors: Record<string, string> = {
  youtube: "platform-youtube",
  shorts: "bg-red-400",
  tiktok: "platform-tiktok",
  facebook: "platform-facebook",
  instagram: "platform-instagram",
  line: "platform-line",
  yahoo: "platform-yahoo",
  x: "platform-x",
};

const mediaFilterOptions: { value: MediaType; label: string }[] = [
  { value: "all", label: "媒体を選択" },
  { value: "youtube", label: "YouTube" },
  { value: "shorts", label: "YouTube Shorts" },
  { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" },
  { value: "tiktok", label: "TikTok" },
  { value: "line", label: "LINE" },
  { value: "yahoo", label: "Yahoo!" },
  { value: "x", label: "X (Twitter)" },
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
    format: "all",
    version: "latest",
    interval: "2days",
    search: "",
  });
  const [sortField, setSortField] = useState<SortField>("rank");
  const [sortAsc, setSortAsc] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  const [ads, setAds] = useState<MockAd[]>(mockAds);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const params: Record<string, string | number | undefined> = {};
        if (filters.media !== "all") params.platform = filters.media;
        if (filters.interval === "7days") params.period = "weekly";
        else if (filters.interval === "14days") params.period = "biweekly";
        else if (filters.interval === "30days") params.period = "monthly";
        else params.period = "daily";

        const response = await rankingsApi.getProducts(params as Parameters<typeof rankingsApi.getProducts>[0]);
        const items = response.data?.items || response.data?.results || response.data;
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
        console.warn("API unavailable, using mock data:", error);
        // keep mock data as fallback
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [filters.media, filters.interval]);

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
                  <button
                    className="text-[#4A7DFF] hover:underline text-[11px] max-w-[100px] truncate block"
                    onClick={(e) => { e.stopPropagation(); window.open(ad.destination, "_blank"); }}
                    title={ad.destination}
                  >
                    遷移先
                  </button>
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
    </div>
  );
}
