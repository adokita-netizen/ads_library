"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { fetchApi } from "@/lib/api";

/* ─── Types ─── */

interface DistributionItem {
  value: string;
  count: number;
  share: number;
  avg_hit_proxy_score?: number;
}

interface AppealShareData {
  hook_type: DistributionItem[];
  offer_type: DistributionItem[];
  proof_type: DistributionItem[];
  creative_style: DistributionItem[];
  lp_pattern: DistributionItem[];
  pain_point: DistributionItem[];
  total_ads: number;
  genre?: string;
}

/* ─── Props ─── */

interface AngleFactDashboardProps {
  onAdSelect?: (adId: number) => void;
}

/* ─── Component ─── */

export default function AngleFactDashboard({ onAdSelect }: AngleFactDashboardProps) {
  const [data, setData] = useState<AppealShareData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [genre, setGenre] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined> = {};
      if (genre) params.genre = genre;
      const result = await fetchApi<AppealShareData>("/rankings/appeal-share", { params });
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [genre]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  /* ── Derived stats ── */
  const totalFacts = useMemo(() => {
    if (!data) return 0;
    return (
      (data.hook_type?.length || 0) +
      (data.offer_type?.length || 0) +
      (data.proof_type?.length || 0) +
      (data.creative_style?.length || 0) +
      (data.lp_pattern?.length || 0) +
      (data.pain_point?.length || 0)
    );
  }, [data]);

  /* Top hooks by avg score */
  const topPerformingHooks = useMemo(() => {
    if (!data?.hook_type) return [];
    return [...data.hook_type]
      .filter((h) => h.avg_hit_proxy_score != null)
      .sort((a, b) => (b.avg_hit_proxy_score ?? 0) - (a.avg_hit_proxy_score ?? 0))
      .slice(0, 10);
  }, [data]);

  /* ── CSV export ── */
  const handleExport = useCallback(() => {
    if (!data) return;

    const rows: string[][] = [["カテゴリ", "値", "件数", "シェア", "平均スコア"]];

    const sections: [string, DistributionItem[]][] = [
      ["フックタイプ", data.hook_type || []],
      ["オファータイプ", data.offer_type || []],
      ["証拠タイプ", data.proof_type || []],
      ["クリエイティブスタイル", data.creative_style || []],
      ["LPパターン", data.lp_pattern || []],
      ["ペインポイント", data.pain_point || []],
    ];

    sections.forEach(([label, items]) => {
      items.forEach((item) => {
        rows.push([
          label,
          item.value,
          String(item.count),
          `${(item.share * 100).toFixed(1)}%`,
          item.avg_hit_proxy_score != null ? item.avg_hit_proxy_score.toFixed(1) : "",
        ]);
      });
    });

    const bom = "\uFEFF";
    const csv = bom + rows.map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `angle_facts_${genre || "all"}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [data, genre]);

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
        <button onClick={fetchData} className="mt-3 text-xs text-blue-600 dark:text-blue-400 hover:underline">
          再試行
        </button>
      </div>
    );
  }

  if (!data) return null;

  /* ── Helper: ranked list panel ── */
  const RankedList = ({
    title,
    items,
    color,
  }: {
    title: string;
    items: DistributionItem[];
    color: string;
  }) => {
    const maxCount = items.length > 0 ? Math.max(...items.map((i) => i.count)) : 1;
    return (
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">{title}</h3>
        {items.length === 0 ? (
          <p className="text-xs text-gray-400 dark:text-gray-500">データなし</p>
        ) : (
          <div className="space-y-2">
            {items.slice(0, 8).map((item, idx) => (
              <div key={item.value} className="flex items-center gap-2">
                <span className="text-[11px] font-bold text-gray-400 dark:text-gray-500 w-5 text-right flex-shrink-0">
                  {idx + 1}
                </span>
                <span className="w-24 text-[11px] text-gray-600 dark:text-gray-300 truncate flex-shrink-0">
                  {item.value}
                </span>
                <div className="flex-1 h-4 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${color} rounded-full transition-all duration-500`}
                    style={{ width: `${(item.count / maxCount) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-gray-500 dark:text-gray-400 w-8 text-right flex-shrink-0">
                  {item.count}
                </span>
                <span className="text-[10px] text-gray-400 dark:text-gray-500 w-12 text-right flex-shrink-0">
                  {(item.share * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">アングルファクト探索</h2>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
            訴求パターンの分析とランキング
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
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
          <button
            onClick={handleExport}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            CSV出力
          </button>
        </div>
      </div>

      {/* Overview cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
          <p className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">対象広告数</p>
          <p className="mt-1 text-xl font-bold text-gray-900 dark:text-white">{data.total_ads.toLocaleString()}</p>
        </div>
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
          <p className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">アングル種別数</p>
          <p className="mt-1 text-xl font-bold text-blue-600 dark:text-blue-400">{totalFacts}</p>
        </div>
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
          <p className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">フック種類</p>
          <p className="mt-1 text-xl font-bold text-emerald-600 dark:text-emerald-400">{data.hook_type?.length || 0}</p>
        </div>
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 text-center">
          <p className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">オファー種類</p>
          <p className="mt-1 text-xl font-bold text-amber-500 dark:text-amber-400">{data.offer_type?.length || 0}</p>
        </div>
      </div>

      {/* Top ranked lists */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <RankedList
          title="トップフック"
          items={data.hook_type || []}
          color="bg-blue-500 dark:bg-blue-400"
        />
        <RankedList
          title="トップオファー"
          items={data.offer_type || []}
          color="bg-emerald-500 dark:bg-emerald-400"
        />
        <RankedList
          title="トップ証拠"
          items={data.proof_type || []}
          color="bg-amber-500 dark:bg-amber-400"
        />
      </div>

      {/* Top performing angles (by avg score) */}
      {topPerformingHooks.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
            高パフォーマンスフック (平均ヒットスコア順)
          </h3>
          <div className="space-y-3">
            {topPerformingHooks.map((hook, idx) => {
              const score = hook.avg_hit_proxy_score ?? 0;
              const scoreColorClass =
                score >= 70
                  ? "text-emerald-600 dark:text-emerald-400"
                  : score >= 40
                    ? "text-amber-500 dark:text-amber-400"
                    : "text-red-500 dark:text-red-400";
              const scoreBg =
                score >= 70
                  ? "bg-emerald-500 dark:bg-emerald-400"
                  : score >= 40
                    ? "bg-amber-500 dark:bg-amber-400"
                    : "bg-red-500 dark:bg-red-400";

              return (
                <div key={hook.value} className="flex items-center gap-3">
                  <span className="text-sm font-bold text-gray-300 dark:text-gray-600 w-6 text-right flex-shrink-0">
                    {idx + 1}
                  </span>
                  <span className="w-32 text-sm text-gray-700 dark:text-gray-200 truncate flex-shrink-0 font-medium">
                    {hook.value}
                  </span>
                  <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${scoreBg} rounded-full transition-all duration-500`}
                      style={{ width: `${Math.min(score, 100)}%` }}
                    />
                  </div>
                  <span className={`text-sm font-bold w-12 text-right flex-shrink-0 ${scoreColorClass}`}>
                    {score.toFixed(1)}
                  </span>
                  <span className="text-[10px] text-gray-400 dark:text-gray-500 w-14 text-right flex-shrink-0">
                    ({hook.count}件)
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Additional ranked lists */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <RankedList
          title="クリエイティブスタイル"
          items={data.creative_style || []}
          color="bg-purple-500 dark:bg-purple-400"
        />
        <RankedList
          title="LPパターン"
          items={data.lp_pattern || []}
          color="bg-pink-500 dark:bg-pink-400"
        />
        <RankedList
          title="ペインポイント"
          items={data.pain_point || []}
          color="bg-cyan-500 dark:bg-cyan-400"
        />
      </div>
    </div>
  );
}
