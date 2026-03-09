"use client";

import React, { useState, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { formatNumber, formatYen } from "@/lib/format";
import { useSearchUxSettings } from "@/lib/useSearchUxSettings";
import SearchUxSettingsPanel from "../common/SearchUxSettingsPanel";
import SearchFallbackChips, { type SearchFallbackSuggestion } from "../common/SearchFallbackChips";

/* ─── Types ─── */

interface CompareAd {
  ad_id: number;
  product_name: string;
  title: string;
  description: string;
  advertiser_name: string;
  genre: string;
  fine_genre: string;
  platform: string;
  thumbnail?: string;
  thumbnail_url?: string;
  image_url?: string;
  video_url?: string;
  snapshot_url?: string;
  hit_score: number;
  cumulative_views: number;
  cumulative_spend: number;
  longevity_days: number;
  first_seen_date?: string;
  last_seen_date?: string;
  is_still_running?: boolean;
  hook_type?: string;
  cta_type?: string;
  creative_type?: string;
  destination_url?: string;
  percentile_rank?: number;
}

interface CompareResult {
  ads: CompareAd[];
  winner_id: number | null;
  insights: string[];
}

interface SearchResult {
  ad_id: number;
  product_name: string;
  title: string;
  advertiser_name: string;
  platform: string;
  thumbnail?: string;
  image_url?: string;
  fine_genre?: string;
  hit_score?: number;
  matched_field?: string;
  matched_terms?: string[];
}

/* ─── Creative Viewer (inline for comparison) ─── */

function CompareCreativeViewer({ ad }: { ad: CompareAd }) {
  const [imgError, setImgError] = useState(false);
  const videoUrl = ad.video_url;
  const thumbnailUrl = ad.thumbnail || ad.thumbnail_url || `/api/v1/media/thumbnail/${ad.ad_id}`;

  if (videoUrl) {
    return (
      <div className="w-full aspect-[9/16] max-h-[400px] bg-black rounded-lg overflow-hidden">
        <video
          src={videoUrl}
          controls
          playsInline
          muted
          preload="metadata"
          poster={thumbnailUrl}
          className="w-full h-full object-contain"
        />
      </div>
    );
  }

  if (!imgError) {
    return (
      <div className="w-full aspect-video bg-gray-100 rounded-lg overflow-hidden">
        <img
          src={thumbnailUrl}
          alt={ad.title}
          className="w-full h-full object-cover"
          onError={() => setImgError(true)}
        />
      </div>
    );
  }

  // Fallback: snapshot link
  if (ad.snapshot_url) {
    return (
      <a
        href={ad.snapshot_url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center justify-center w-full aspect-video bg-gray-50 rounded-lg border-2 border-dashed border-gray-200 hover:border-blue-300 transition-colors"
      >
        <div className="text-center p-4">
          <svg className="w-8 h-8 mx-auto text-gray-300 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
          </svg>
          <p className="text-[11px] text-gray-500">Ad Libraryで確認</p>
        </div>
      </a>
    );
  }

  return (
    <div className="flex items-center justify-center w-full aspect-video bg-gray-50 rounded-lg">
      <svg className="w-10 h-10 text-gray-200" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5a2.25 2.25 0 002.25-2.25V5.25a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 003.75 21z" />
      </svg>
    </div>
  );
}

/* ─── Score Badge ─── */

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 80 ? "bg-red-500" : score >= 60 ? "bg-amber-500" : score >= 40 ? "bg-blue-500" : "bg-gray-400";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-white text-[11px] font-bold ${color}`}>
      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" />
      </svg>
      {score}
    </span>
  );
}

/* ─── Radar Chart (SVG) ─── */

function RadarChart({ ads }: { ads: CompareAd[] }) {
  const metrics = [
    { key: "hit_score", label: "スコア", max: 100 },
    { key: "cumulative_views", label: "再生数", max: Math.max(...ads.map(a => a.cumulative_views), 1) },
    { key: "cumulative_spend", label: "消化額", max: Math.max(...ads.map(a => a.cumulative_spend), 1) },
    { key: "longevity_days", label: "掲載日数", max: Math.max(...ads.map(a => a.longevity_days), 1) },
    { key: "percentile_rank", label: "順位", max: 100 },
  ];

  const colors = ["#4A7DFF", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6"];
  const cx = 120, cy = 120, r = 85;

  function polarToCartesian(angle: number, radius: number) {
    const radian = ((angle - 90) * Math.PI) / 180;
    return { x: cx + radius * Math.cos(radian), y: cy + radius * Math.sin(radian) };
  }

  const angleStep = 360 / metrics.length;
  const rings = [0.2, 0.4, 0.6, 0.8, 1.0];

  return (
    <svg viewBox="0 0 240 240" className="w-full max-w-[220px] mx-auto">
      {rings.map(ring => (
        <polygon key={ring} points={metrics.map((_, i) => { const pt = polarToCartesian(i * angleStep, r * ring); return `${pt.x},${pt.y}`; }).join(" ")} fill="none" stroke="#e5e7eb" strokeWidth={0.5} />
      ))}
      {metrics.map((_, i) => { const pt = polarToCartesian(i * angleStep, r); return <line key={i} x1={cx} y1={cy} x2={pt.x} y2={pt.y} stroke="#e5e7eb" strokeWidth={0.5} />; })}
      {metrics.map((m, i) => { const pt = polarToCartesian(i * angleStep, r + 16); return <text key={m.key} x={pt.x} y={pt.y} textAnchor="middle" dominantBaseline="middle" className="text-[8px] fill-gray-500">{m.label}</text>; })}
      {ads.map((ad, adIdx) => {
        const points = metrics.map((m, i) => {
          const val = (ad as unknown as Record<string, unknown>)[m.key] as number || 0;
          const normalized = Math.min(val / m.max, 1);
          const pt = polarToCartesian(i * angleStep, r * normalized);
          return `${pt.x},${pt.y}`;
        }).join(" ");
        return <polygon key={ad.ad_id} points={points} fill={colors[adIdx % colors.length]} fillOpacity={0.15} stroke={colors[adIdx % colors.length]} strokeWidth={1.5} />;
      })}
    </svg>
  );
}

/* ─── Main Component ─── */

interface AdComparisonToolProps {
  onAdSelect?: (adId: number) => void;
}

export default function AdComparisonTool({ onAdSelect }: AdComparisonToolProps) {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selectedInfo, setSelectedInfo] = useState<Map<number, SearchResult>>(new Map());
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [relatedSuggestions, setRelatedSuggestions] = useState<SearchFallbackSuggestion[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const {
    showSuggestionWeights,
    setShowSuggestionWeights,
    defaultSuggestionLimit,
    setDefaultSuggestionLimit,
    autoOpenDefaultSuggestions,
    setAutoOpenDefaultSuggestions,
    allowedSuggestionLimits,
  } = useSearchUxSettings();

  const colors = ["#4A7DFF", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6"];

  // Search ads from real API
  const handleSearch = useCallback(async (q: string) => {
    setSearchQuery(q);
    if (!q.trim()) {
      setSearchResults([]);
      setRelatedSuggestions([]);
      return;
    }
    setSearchLoading(true);
    try {
      const res = await fetchApi<{ items?: SearchResult[]; related_suggestions?: SearchFallbackSuggestion[] }>("/rankings/search-simple", {
        params: { q, page_size: defaultSuggestionLimit },
      });
      setSearchResults(res.items || []);
      setRelatedSuggestions(res.related_suggestions || []);
    } catch {
      setSearchResults([]);
      setRelatedSuggestions([]);
    } finally {
      setSearchLoading(false);
    }
  }, [defaultSuggestionLimit]);

  // Load initial results when search opens
  const openSearch = useCallback(async () => {
    setShowSearch(true);
    if (
      autoOpenDefaultSuggestions &&
      searchResults.length === 0 &&
      !searchQuery
    ) {
      setSearchLoading(true);
      try {
        const res = await fetchApi<{ items?: SearchResult[]; related_suggestions?: SearchFallbackSuggestion[] }>("/rankings/search-simple", {
          params: { q: "", page_size: defaultSuggestionLimit },
        });
        setSearchResults(res.items || []);
        setRelatedSuggestions(res.related_suggestions || []);
      } catch { /* ignore */ }
      finally { setSearchLoading(false); }
    }
  }, [
    autoOpenDefaultSuggestions,
    defaultSuggestionLimit,
    searchResults.length,
    searchQuery,
  ]);

  // Add ad to comparison
  const addAd = (result: SearchResult) => {
    if (selectedIds.length >= 5 || selectedIds.includes(result.ad_id)) return;
    setSelectedIds(prev => [...prev, result.ad_id]);
    setSelectedInfo(prev => new Map(prev).set(result.ad_id, result));
    setShowSearch(false);
    setSearchQuery("");
    setSearchResults([]);
    setRelatedSuggestions([]);
    setResult(null);
  };

  // Remove ad
  const removeAd = (adId: number) => {
    setSelectedIds(prev => prev.filter(id => id !== adId));
    setSelectedInfo(prev => { const m = new Map(prev); m.delete(adId); return m; });
    setResult(null);
  };

  // Run comparison with real API
  const runComparison = async () => {
    if (selectedIds.length < 2) return;
    setLoading(true);
    try {
      const res = await fetchApi<CompareResult>("/rankings/compare-ads", {
        method: "POST",
        body: { ad_ids: selectedIds },
      });
      setResult(res);
    } catch (err) {
      console.error("Compare failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#f8f9fb]">
      {/* Header */}
      <div className="shrink-0 bg-white border-b border-gray-200 px-5 py-3">
        <div className="flex items-center gap-3 mb-3">
          <svg className="w-5 h-5 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
          </svg>
          <h1 className="text-[16px] font-bold text-gray-900">クリエイティブ比較</h1>
          <span className="text-[11px] text-gray-400">広告のクリエイティブとメトリクスを並べて比較</span>
        </div>

        {/* Ad selection strip */}
        <div className="flex items-center gap-2 flex-wrap">
          {selectedIds.map((id, idx) => {
            const info = selectedInfo.get(id);
            return (
              <div
                key={id}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-medium border"
                style={{
                  borderColor: colors[idx % colors.length],
                  backgroundColor: `${colors[idx % colors.length]}10`,
                  color: colors[idx % colors.length],
                }}
              >
                {info?.thumbnail && (
                  <img src={info.thumbnail || `/api/v1/media/thumbnail/${id}`} alt="" className="w-5 h-5 rounded object-cover" onError={(e) => { e.currentTarget.style.display = "none"; }} />
                )}
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: colors[idx % colors.length] }} />
                {info?.product_name || info?.title || `Ad #${id}`}
                {info?.hit_score !== undefined && (
                  <span className="text-[9px] opacity-70">({info.hit_score}pt)</span>
                )}
                <button onClick={() => removeAd(id)} className="ml-0.5 hover:opacity-70">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            );
          })}

          {selectedIds.length < 5 && (
            <div className="relative">
              <button
                onClick={openSearch}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium text-gray-500 border border-dashed border-gray-300 hover:border-[#4A7DFF] hover:text-[#4A7DFF] transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                広告を追加
              </button>

              {showSearch && (
                <div className="absolute left-0 top-full mt-1 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
                  <div className="p-2">
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => handleSearch(e.target.value)}
                      placeholder="商品名・広告主名・個別ワードで検索... 例: GLP-1 / ピラティス"
                      className="w-full px-3 py-1.5 text-[12px] border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/30"
                      autoFocus
                    />
                  </div>
                  {!searchQuery && (
                    <div className="px-3 pb-2 border-b border-gray-100">
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
                  )}
                  <div className="max-h-64 overflow-y-auto">
                    {searchLoading ? (
                      <div className="flex items-center justify-center py-6">
                        <svg className="w-5 h-5 animate-spin text-gray-400" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                      </div>
                    ) : searchResults.length === 0 ? (
                      <div className="px-3 py-4">
                        <p className="text-[11px] text-gray-400 text-center">
                          {searchQuery ? "結果が見つかりません" : "GLP-1、マンジャロ、ピラティスなどで検索"}
                        </p>
                        {searchQuery && relatedSuggestions.length > 0 && (
                          <div className="mt-3">
                            <SearchFallbackChips
                              suggestions={relatedSuggestions}
                              onSelect={(suggestion) => handleSearch(suggestion.value)}
                            />
                          </div>
                        )}
                      </div>
                    ) : (
                      searchResults.filter(s => !selectedIds.includes(s.ad_id)).map(s => (
                        <button
                          key={s.ad_id}
                          onClick={() => addAd(s)}
                          className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-gray-50 transition-colors text-left"
                        >
                          <div className="w-10 h-10 bg-gray-100 rounded overflow-hidden shrink-0">
                            <img
                              src={s.thumbnail || s.image_url || `/api/v1/media/thumbnail/${s.ad_id}`}
                              alt=""
                              className="w-full h-full object-cover"
                              onError={(e) => { e.currentTarget.style.display = "none"; }}
                            />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-[12px] font-medium text-gray-700 truncate">{s.product_name || s.title}</p>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-[10px] text-gray-400">{s.advertiser_name}</span>
                              {s.fine_genre && (
                                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500">{s.fine_genre}</span>
                              )}
                              {s.hit_score !== undefined && (
                                <span className={`text-[9px] font-bold ${s.hit_score >= 80 ? "text-red-500" : s.hit_score >= 60 ? "text-amber-500" : "text-gray-400"}`}>
                                  {s.hit_score}pt
                                </span>
                              )}
                            </div>
                            {!!s.matched_terms?.length && (
                              <div className="mt-1 flex items-center gap-1 flex-wrap">
                                <span className="text-[9px] text-gray-400">
                                  {s.matched_field || "一致"}:
                                </span>
                                {s.matched_terms.slice(0, 2).map((term) => (
                                  <span
                                    key={`${s.ad_id}-${term}`}
                                    className="inline-flex items-center px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-[9px] leading-none"
                                  >
                                    {term}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </button>
                      ))
                    )}
                  </div>
                  <div className="px-3 py-2 border-t border-gray-100">
                    <button onClick={() => setShowSearch(false)} className="text-[11px] text-gray-400 hover:text-gray-600">
                      閉じる
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {selectedIds.length >= 2 && (
            <button
              onClick={runComparison}
              disabled={loading}
              className="ml-auto inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-[12px] font-medium text-white bg-[#4A7DFF] hover:bg-[#3a6be8] disabled:opacity-50 transition-colors"
            >
              {loading ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  比較中...
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                  </svg>
                  比較実行
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto custom-scrollbar p-5">
        {!result ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <svg className="w-20 h-20 text-gray-200 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={0.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
            </svg>
            <p className="text-[15px] font-medium text-gray-500 mb-1">
              広告を選択してクリエイティブを比較
            </p>
            <p className="text-[12px] text-gray-400 max-w-md">
              2件以上の広告を追加してから「比較実行」を押してください。<br />
              クリエイティブ（動画・画像）とヒットスコアを並べて比較できます。
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* ── Creative Side-by-Side ── */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
                <h3 className="text-[13px] font-bold text-gray-700">クリエイティブ比較</h3>
              </div>
              <div className={`grid gap-4 p-4 ${result.ads.length === 2 ? "grid-cols-2" : result.ads.length === 3 ? "grid-cols-3" : result.ads.length === 4 ? "grid-cols-4" : "grid-cols-5"}`}>
                {result.ads.map((ad, idx) => (
                  <div key={ad.ad_id} className="space-y-2">
                    {/* Header with color indicator */}
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: colors[idx % colors.length] }} />
                      <span className="text-[12px] font-semibold text-gray-800 truncate" style={{ color: colors[idx % colors.length] }}>
                        {ad.product_name || ad.title}
                      </span>
                      {result.winner_id === ad.ad_id && (
                        <span className="shrink-0 px-1.5 py-0.5 text-[9px] font-bold bg-yellow-100 text-yellow-700 rounded-full leading-none">
                          勝者
                        </span>
                      )}
                    </div>

                    {/* Creative viewer */}
                    <div
                      className="cursor-pointer hover:ring-2 hover:ring-blue-300 rounded-lg transition-all"
                      onClick={() => onAdSelect?.(ad.ad_id)}
                    >
                      <CompareCreativeViewer ad={ad} />
                    </div>

                    {/* Score + key metrics */}
                    <div className="space-y-1.5 pt-1">
                      <div className="flex items-center justify-between">
                        <ScoreBadge score={ad.hit_score} />
                        <span className="text-[10px] text-gray-400">
                          {ad.creative_type || "動画"}
                        </span>
                      </div>
                      <div className="text-[11px] text-gray-600 space-y-0.5">
                        <div className="flex justify-between">
                          <span className="text-gray-400">再生数</span>
                          <span className="font-medium">{formatNumber(ad.cumulative_views)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">消化額</span>
                          <span className="font-medium">{formatYen(ad.cumulative_spend)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">掲載日数</span>
                          <span className="font-medium">{ad.longevity_days}日</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">ジャンル</span>
                          <span className="font-medium truncate ml-2">{ad.fine_genre}</span>
                        </div>
                      </div>
                      <p className="text-[10px] text-gray-400 truncate">{ad.advertiser_name}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* ── Metrics Table ── */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
                <h3 className="text-[13px] font-bold text-gray-700">メトリクス詳細比較</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="border-b border-gray-100">
                      <th className="px-4 py-2.5 text-left text-gray-500 font-medium w-32">項目</th>
                      {result.ads.map((ad, idx) => (
                        <th key={ad.ad_id} className="px-4 py-2.5 text-left font-medium" style={{ color: colors[idx % colors.length] }}>
                          <div className="flex items-center gap-1.5">
                            {ad.product_name || ad.title}
                            {result.winner_id === ad.ad_id && (
                              <span className="px-1.5 py-0.5 text-[9px] font-bold bg-yellow-100 text-yellow-700 rounded-full leading-none">
                                勝者
                              </span>
                            )}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {[
                      { label: "スコア", fn: (a: CompareAd) => `${a.hit_score}pt` },
                      { label: "再生数", fn: (a: CompareAd) => formatNumber(a.cumulative_views) },
                      { label: "消化額", fn: (a: CompareAd) => formatYen(a.cumulative_spend) },
                      { label: "掲載日数", fn: (a: CompareAd) => `${a.longevity_days}日` },
                      { label: "ジャンル", fn: (a: CompareAd) => a.fine_genre || "-" },
                      { label: "フック", fn: (a: CompareAd) => a.hook_type || "-" },
                      { label: "CTA", fn: (a: CompareAd) => a.cta_type || "-" },
                      { label: "フォーマット", fn: (a: CompareAd) => a.creative_type || "-" },
                      { label: "ステータス", fn: (a: CompareAd) => a.is_still_running ? "配信中" : "終了" },
                    ].map(row => (
                      <tr key={row.label}>
                        <td className="px-4 py-2 text-gray-500">{row.label}</td>
                        {result.ads.map(ad => (
                          <td key={ad.ad_id} className="px-4 py-2 font-medium">{row.fn(ad)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* ── Radar + Insights ── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
                  <h3 className="text-[13px] font-bold text-gray-700">レーダーチャート</h3>
                </div>
                <div className="p-4">
                  <RadarChart ads={result.ads} />
                  <div className="flex flex-wrap gap-3 mt-3 justify-center">
                    {result.ads.map((ad, idx) => (
                      <div key={ad.ad_id} className="flex items-center gap-1.5 text-[10px] text-gray-600">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: colors[idx % colors.length] }} />
                        {ad.product_name || ad.title}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
                  <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                    </svg>
                    <h3 className="text-[13px] font-bold text-gray-700">分析インサイト</h3>
                  </div>
                </div>
                <div className="p-4 space-y-3">
                  {result.insights.length > 0 ? (
                    result.insights.map((insight, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <span className="w-5 h-5 rounded-full bg-purple-50 text-purple-600 text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                          {i + 1}
                        </span>
                        <p className="text-[12px] text-gray-600 leading-relaxed">{insight}</p>
                      </div>
                    ))
                  ) : (
                    <p className="text-[12px] text-gray-400">インサイトを生成中...</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
