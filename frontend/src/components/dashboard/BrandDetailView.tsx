"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

/* ─── Types ─── */

interface BrandInfo {
  brand_id: number;
  brand_name: string;
  canonical_name: string;
  vertical?: string;
  domains?: string[];
  aliases?: string[];
  total_ad_count: number;
  avg_hit_proxy_score?: number;
  active_days?: number;
  hook_distribution?: Record<string, number>;
  ads?: BrandAd[];
}

interface BrandAd {
  ad_id: number;
  product_name?: string;
  platform?: string;
  hit_proxy_score?: number;
  thumbnail_url?: string;
  image_url?: string;
  first_seen?: string;
}

interface BrandListItem {
  brand_id: number;
  brand_name: string;
  canonical_name: string;
  vertical?: string;
  total_ad_count: number;
}

/* ─── Helpers ─── */

function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 40) return "text-amber-500 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}

function scoreBadgeBg(score: number): string {
  if (score >= 70) return "bg-emerald-100 dark:bg-emerald-900/40";
  if (score >= 40) return "bg-amber-100 dark:bg-amber-900/40";
  return "bg-red-100 dark:bg-red-900/40";
}

/* ─── Props ─── */

interface BrandDetailViewProps {
  brandId?: number;
  onAdSelect?: (adId: number) => void;
  onBack?: () => void;
}

/* ─── Component ─── */

export default function BrandDetailView({ brandId, onAdSelect, onBack }: BrandDetailViewProps) {
  const [brand, setBrand] = useState<BrandInfo | null>(null);
  const [brands, setBrands] = useState<BrandListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBrandId, setSelectedBrandId] = useState<number | undefined>(brandId);

  /* ── Fetch brand detail ── */
  const fetchBrand = useCallback(async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchApi<BrandInfo>(`/rankings/brand/${id}`);
      setBrand(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, []);

  /* ── Fetch brands list ── */
  const fetchBrands = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchApi<{ items: BrandListItem[]; total: number }>(
        "/rankings/brands",
        { params: { page: 1, page_size: 50, search: searchQuery || undefined } },
      );
      setBrands(data.items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "ブランド一覧の取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    if (selectedBrandId) {
      fetchBrand(selectedBrandId);
    } else {
      fetchBrands();
    }
  }, [selectedBrandId, fetchBrand, fetchBrands]);

  /* ── Loading state ── */
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
        <span className="ml-3 text-sm text-gray-500 dark:text-gray-400">読み込み中...</span>
      </div>
    );
  }

  /* ── Error state ── */
  if (error) {
    return (
      <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-6 text-center">
        <p className="text-red-600 dark:text-red-400 text-sm font-medium">{error}</p>
        <button
          onClick={() => selectedBrandId ? fetchBrand(selectedBrandId) : fetchBrands()}
          className="mt-3 text-xs text-blue-600 dark:text-blue-400 hover:underline"
        >
          再試行
        </button>
      </div>
    );
  }

  /* ── Brand list view (no brand selected) ── */
  if (!selectedBrandId || !brand) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-gray-900 dark:text-white">ブランド一覧</h2>

        {/* Search */}
        <div className="flex gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="ブランド名で検索..."
            className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
          <button
            onClick={fetchBrands}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            検索
          </button>
        </div>

        {/* List */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {brands.map((b) => (
            <button
              key={b.brand_id}
              onClick={() => setSelectedBrandId(b.brand_id)}
              className="text-left rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 hover:shadow-md transition-shadow"
            >
              <p className="font-semibold text-gray-900 dark:text-white truncate">{b.brand_name}</p>
              {b.vertical && (
                <span className="inline-block mt-1 text-[11px] bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 px-2 py-0.5 rounded-full">
                  {b.vertical}
                </span>
              )}
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                広告数: <span className="font-medium text-gray-900 dark:text-white">{b.total_ad_count}</span>
              </p>
            </button>
          ))}
        </div>

        {brands.length === 0 && (
          <p className="text-center text-sm text-gray-400 dark:text-gray-500 py-8">
            該当するブランドが見つかりません
          </p>
        )}
      </div>
    );
  }

  /* ── Brand detail view ── */
  const hookDist = brand.hook_distribution || {};
  const hookEntries = Object.entries(hookDist).sort(([, a], [, b]) => b - a);
  const hookMax = hookEntries.length > 0 ? Math.max(...hookEntries.map(([, v]) => v)) : 1;

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={() => {
          if (onBack) {
            onBack();
          } else {
            setSelectedBrandId(undefined);
            setBrand(null);
          }
        }}
        className="inline-flex items-center text-sm text-blue-600 dark:text-blue-400 hover:underline"
      >
        <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        一覧に戻る
      </button>

      {/* Brand info header */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">{brand.brand_name}</h2>
            {brand.canonical_name !== brand.brand_name && (
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{brand.canonical_name}</p>
            )}
          </div>
          {brand.vertical && (
            <span className="text-xs bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 px-3 py-1 rounded-full font-medium">
              {brand.vertical}
            </span>
          )}
        </div>

        {/* Domains & Aliases */}
        {brand.domains && brand.domains.length > 0 && (
          <div className="mt-3">
            <p className="text-[11px] text-gray-400 dark:text-gray-500 mb-1">ドメイン</p>
            <div className="flex flex-wrap gap-1">
              {brand.domains.map((d) => (
                <span key={d} className="text-[11px] bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-2 py-0.5 rounded">
                  {d}
                </span>
              ))}
            </div>
          </div>
        )}
        {brand.aliases && brand.aliases.length > 0 && (
          <div className="mt-2">
            <p className="text-[11px] text-gray-400 dark:text-gray-500 mb-1">別名</p>
            <div className="flex flex-wrap gap-1">
              {brand.aliases.map((a) => (
                <span key={a} className="text-[11px] bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 px-2 py-0.5 rounded">
                  {a}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5 text-center">
          <p className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">総広告数</p>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
            {brand.total_ad_count.toLocaleString()}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5 text-center">
          <p className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">平均ヒットスコア</p>
          <p className={`mt-1 text-2xl font-bold ${scoreColor(brand.avg_hit_proxy_score ?? 0)}`}>
            {brand.avg_hit_proxy_score != null ? brand.avg_hit_proxy_score.toFixed(1) : "---"}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5 text-center">
          <p className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">アクティブ日数</p>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
            {brand.active_days != null ? `${brand.active_days}日` : "---"}
          </p>
        </div>
      </div>

      {/* Hook distribution */}
      {hookEntries.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">フックタイプ分布</h3>
          <div className="space-y-2">
            {hookEntries.map(([hookType, count]) => {
              const pct = hookMax > 0 ? (count / hookMax) * 100 : 0;
              return (
                <div key={hookType} className="flex items-center gap-3">
                  <span className="w-28 text-xs text-gray-600 dark:text-gray-300 truncate flex-shrink-0">{hookType}</span>
                  <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 dark:bg-blue-400 rounded-full transition-all duration-500"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 dark:text-gray-400 w-10 text-right flex-shrink-0">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Ads grid */}
      {brand.ads && brand.ads.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
            広告一覧 ({brand.ads.length}件)
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {brand.ads.map((ad) => (
              <button
                key={ad.ad_id}
                onClick={() => onAdSelect?.(ad.ad_id)}
                className="text-left rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 overflow-hidden hover:shadow-md transition-shadow"
              >
                {/* Thumbnail */}
                <div className="aspect-video bg-gray-200 dark:bg-gray-700 relative">
                  {(ad.thumbnail_url || ad.image_url) ? (
                    <img
                      src={ad.thumbnail_url || ad.image_url}
                      alt={ad.product_name || ""}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-400 dark:text-gray-500 text-xs">
                      No Image
                    </div>
                  )}
                  {ad.hit_proxy_score != null && (
                    <span className={`absolute top-2 right-2 text-[11px] font-bold px-2 py-0.5 rounded ${scoreBadgeBg(ad.hit_proxy_score)} ${scoreColor(ad.hit_proxy_score)}`}>
                      {ad.hit_proxy_score.toFixed(0)}
                    </span>
                  )}
                </div>
                {/* Info */}
                <div className="p-3">
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                    {ad.product_name || `広告 #${ad.ad_id}`}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    {ad.platform && (
                      <span className="text-[10px] bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-1.5 py-0.5 rounded">
                        {ad.platform}
                      </span>
                    )}
                    {ad.first_seen && (
                      <span className="text-[10px] text-gray-400 dark:text-gray-500">{ad.first_seen}</span>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
