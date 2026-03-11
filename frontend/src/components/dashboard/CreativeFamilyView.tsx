"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

/* ─── Types ─── */

interface FamilyCard {
  family_id: number;
  title: string;
  advertiser_name?: string;
  genre?: string;
  member_count: number;
  variant_count: number;
  active_days?: number;
  hit_proxy_score?: number;
  thumbnail_url?: string;
}

interface FamilyDetail {
  family_id: number;
  title: string;
  advertiser_name?: string;
  genre?: string;
  members: FamilyMember[];
}

interface FamilyMember {
  ad_id: number;
  product_name?: string;
  platform?: string;
  hit_proxy_score?: number;
  thumbnail_url?: string;
  image_url?: string;
  variant_label?: string;
  first_seen?: string;
}

/* ─── Helpers ─── */

function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 40) return "text-amber-500 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}

/* ─── Props ─── */

interface CreativeFamilyViewProps {
  onAdSelect?: (adId: number) => void;
}

/* ─── Component ─── */

export default function CreativeFamilyView({ onAdSelect }: CreativeFamilyViewProps) {
  const [families, setFamilies] = useState<FamilyCard[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* Filters */
  const [advertiserSearch, setAdvertiserSearch] = useState("");
  const [genreFilter, setGenreFilter] = useState("");
  const [minMembers, setMinMembers] = useState(2);
  const [page, setPage] = useState(1);
  const pageSize = 12;

  /* Expanded family */
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [familyDetail, setFamilyDetail] = useState<FamilyDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  /* ── Fetch families ── */
  const fetchFamilies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchApi<{ items: FamilyCard[]; total: number }>(
        "/rankings/creative-families",
        {
          params: {
            page,
            page_size: pageSize,
            advertiser: advertiserSearch || undefined,
            genre: genreFilter || undefined,
            min_members: minMembers,
          },
        },
      );
      setFamilies(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [page, advertiserSearch, genreFilter, minMembers]);

  useEffect(() => {
    fetchFamilies();
  }, [fetchFamilies]);

  /* ── Fetch family detail ── */
  const fetchFamilyDetail = useCallback(async (familyId: number) => {
    setDetailLoading(true);
    try {
      const data = await fetchApi<FamilyDetail>(`/rankings/creative-family/${familyId}`);
      setFamilyDetail(data);
    } catch {
      setFamilyDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const handleExpand = (familyId: number) => {
    if (expandedId === familyId) {
      setExpandedId(null);
      setFamilyDetail(null);
    } else {
      setExpandedId(familyId);
      fetchFamilyDetail(familyId);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  /* ── Loading state ── */
  if (loading && families.length === 0) {
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
        <button onClick={fetchFamilies} className="mt-3 text-xs text-blue-600 dark:text-blue-400 hover:underline">
          再試行
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-gray-900 dark:text-white">クリエイティブファミリー</h2>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
          合計: {total.toLocaleString()}件
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          value={advertiserSearch}
          onChange={(e) => {
            setAdvertiserSearch(e.target.value);
            setPage(1);
          }}
          placeholder="広告主名で検索..."
          className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
        <select
          value={genreFilter}
          onChange={(e) => {
            setGenreFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
        >
          <option value="">全ジャンル</option>
          <option value="health">健康食品</option>
          <option value="cosmetics">化粧品</option>
          <option value="finance">金融</option>
          <option value="education">教育</option>
          <option value="ec">EC</option>
          <option value="saas">SaaS</option>
          <option value="other">その他</option>
        </select>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
            最小メンバー数
          </label>
          <input
            type="range"
            min={1}
            max={20}
            value={minMembers}
            onChange={(e) => {
              setMinMembers(Number(e.target.value));
              setPage(1);
            }}
            className="w-24 accent-blue-600"
          />
          <span className="text-xs font-medium text-gray-900 dark:text-white w-6 text-center">{minMembers}</span>
        </div>
      </div>

      {/* Family grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {families.map((fam) => (
          <div
            key={fam.family_id}
            className={`rounded-xl border bg-white dark:bg-gray-800 overflow-hidden transition-shadow ${
              expandedId === fam.family_id
                ? "border-blue-400 dark:border-blue-500 shadow-lg"
                : "border-gray-200 dark:border-gray-700 hover:shadow-md"
            }`}
          >
            {/* Card header */}
            <button
              onClick={() => handleExpand(fam.family_id)}
              className="w-full text-left p-4"
            >
              <div className="flex items-start gap-3">
                {/* Thumbnail */}
                <div className="w-16 h-16 rounded-lg bg-gray-200 dark:bg-gray-700 flex-shrink-0 overflow-hidden">
                  {fam.thumbnail_url ? (
                    <img src={fam.thumbnail_url} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-400 dark:text-gray-500 text-[10px]">
                      No Img
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">{fam.title}</p>
                  {fam.advertiser_name && (
                    <p className="text-[11px] text-gray-500 dark:text-gray-400 truncate">{fam.advertiser_name}</p>
                  )}
                  {fam.genre && (
                    <span className="inline-block mt-1 text-[10px] bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 px-1.5 py-0.5 rounded-full">
                      {fam.genre}
                    </span>
                  )}
                </div>
              </div>

              {/* Stats row */}
              <div className="mt-3 grid grid-cols-4 gap-2 text-center">
                <div>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500">メンバー</p>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">{fam.member_count}</p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500">バリアント</p>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">{fam.variant_count}</p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500">日数</p>
                  <p className="text-sm font-bold text-gray-900 dark:text-white">
                    {fam.active_days ?? "---"}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-gray-400 dark:text-gray-500">スコア</p>
                  <p className={`text-sm font-bold ${fam.hit_proxy_score != null ? scoreColor(fam.hit_proxy_score) : "text-gray-400"}`}>
                    {fam.hit_proxy_score != null ? fam.hit_proxy_score.toFixed(1) : "---"}
                  </p>
                </div>
              </div>
            </button>

            {/* Expanded detail */}
            {expandedId === fam.family_id && (
              <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 p-4">
                {detailLoading ? (
                  <div className="flex items-center justify-center py-6">
                    <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
                    <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">読み込み中...</span>
                  </div>
                ) : familyDetail && familyDetail.members ? (
                  <div>
                    <p className="text-xs font-medium text-gray-600 dark:text-gray-300 mb-3">
                      メンバーアセット ({familyDetail.members.length}件)
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {familyDetail.members.map((member) => (
                        <button
                          key={member.ad_id}
                          onClick={() => onAdSelect?.(member.ad_id)}
                          className="text-left rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden hover:shadow transition-shadow"
                        >
                          <div className="aspect-video bg-gray-200 dark:bg-gray-700">
                            {(member.thumbnail_url || member.image_url) ? (
                              <img
                                src={member.thumbnail_url || member.image_url}
                                alt=""
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center text-gray-400 text-[9px]">
                                No Image
                              </div>
                            )}
                          </div>
                          <div className="p-2">
                            <p className="text-[11px] font-medium text-gray-900 dark:text-white truncate">
                              {member.product_name || `#${member.ad_id}`}
                            </p>
                            <div className="flex items-center gap-1 mt-0.5">
                              {member.variant_label && (
                                <span className="text-[9px] bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-300 px-1 py-0.5 rounded">
                                  {member.variant_label}
                                </span>
                              )}
                              {member.platform && (
                                <span className="text-[9px] text-gray-400">{member.platform}</span>
                              )}
                              {member.hit_proxy_score != null && (
                                <span className={`text-[9px] font-bold ml-auto ${scoreColor(member.hit_proxy_score)}`}>
                                  {member.hit_proxy_score.toFixed(0)}
                                </span>
                              )}
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-gray-400 dark:text-gray-500 text-center py-4">
                    メンバー情報が見つかりません
                  </p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {families.length === 0 && (
        <p className="text-center text-sm text-gray-400 dark:text-gray-500 py-8">
          該当するファミリーが見つかりません
        </p>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            前へ
          </button>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="px-3 py-1.5 text-xs rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            次へ
          </button>
        </div>
      )}
    </div>
  );
}
