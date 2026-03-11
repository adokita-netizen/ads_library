"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

/* ─── Types ─── */

interface DistributionItem {
  value: string;
  count: number;
  share: number;
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
  cross_tab?: Record<string, Record<string, number>>;
}

interface TrendMonth {
  month: string;
  distributions: Record<string, Record<string, number>>;
}

interface AppealTrendsData {
  months: TrendMonth[];
}

/* ─── Panel colors ─── */

const PANEL_COLORS = [
  "bg-blue-500 dark:bg-blue-400",
  "bg-emerald-500 dark:bg-emerald-400",
  "bg-amber-500 dark:bg-amber-400",
  "bg-purple-500 dark:bg-purple-400",
  "bg-pink-500 dark:bg-pink-400",
  "bg-cyan-500 dark:bg-cyan-400",
];

const PANEL_LABELS: Record<string, string> = {
  hook_type: "フックタイプ",
  offer_type: "オファータイプ",
  proof_type: "証拠タイプ",
  creative_style: "クリエイティブスタイル",
  lp_pattern: "LPパターン",
  pain_point: "ペインポイント",
};

const PANEL_KEYS = ["hook_type", "offer_type", "proof_type", "creative_style", "lp_pattern", "pain_point"] as const;

/* ─── Props ─── */

interface AppealMapViewProps {}

/* ─── Component ─── */

export default function AppealMapView({}: AppealMapViewProps) {
  const [shareData, setShareData] = useState<AppealShareData | null>(null);
  const [trendsData, setTrendsData] = useState<AppealTrendsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [genre, setGenre] = useState<string>("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number | undefined> = {};
      if (genre) params.genre = genre;

      const [share, trends] = await Promise.all([
        fetchApi<AppealShareData>("/rankings/appeal-share", { params }),
        fetchApi<AppealTrendsData>("/rankings/appeal-trends", { params: { months: 6, ...params } }),
      ]);
      setShareData(share);
      setTrendsData(trends);
    } catch (e) {
      setError(e instanceof Error ? e.message : "データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [genre]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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

  if (!shareData) return null;

  /* ── Cross-tab heat cell data ── */
  const crossTab = shareData.cross_tab || {};
  const hookKeys = Object.keys(crossTab);
  const offerKeysSet = new Set<string>();
  hookKeys.forEach((hk) => Object.keys(crossTab[hk]).forEach((ok) => offerKeysSet.add(ok)));
  const offerKeys = Array.from(offerKeysSet);
  const crossMax = Math.max(1, ...hookKeys.flatMap((hk) => Object.values(crossTab[hk])));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">訴求シェアマップ</h2>
          {shareData.total_ads > 0 && (
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
              対象広告数: {shareData.total_ads.toLocaleString()}件
            </p>
          )}
        </div>

        {/* Genre filter */}
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
      </div>

      {/* 6 Distribution panels */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {PANEL_KEYS.map((key, idx) => {
          const items: DistributionItem[] = (shareData as unknown as Record<string, unknown>)[key] as DistributionItem[] || [];
          const maxCount = items.length > 0 ? Math.max(...items.map((i) => i.count)) : 1;
          const barColor = PANEL_COLORS[idx];

          return (
            <div
              key={key}
              className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5"
            >
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
                {PANEL_LABELS[key]}
              </h3>
              {items.length === 0 ? (
                <p className="text-xs text-gray-400 dark:text-gray-500">データなし</p>
              ) : (
                <div className="space-y-2">
                  {items.slice(0, 10).map((item) => (
                    <div key={item.value} className="flex items-center gap-2">
                      <span className="w-24 text-[11px] text-gray-600 dark:text-gray-300 truncate flex-shrink-0">
                        {item.value}
                      </span>
                      <div className="flex-1 h-4 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${barColor} rounded-full transition-all duration-500`}
                          style={{ width: `${(item.count / maxCount) * 100}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-gray-500 dark:text-gray-400 w-8 text-right flex-shrink-0">
                        {item.count}
                      </span>
                      <span className="text-[10px] text-gray-400 dark:text-gray-500 w-10 text-right flex-shrink-0">
                        {(item.share * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Cross-tab heat cell: hook_type x offer_type */}
      {hookKeys.length > 0 && offerKeys.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
            フックタイプ x オファータイプ クロス集計
          </h3>
          <div className="overflow-x-auto">
            <table className="text-[11px]">
              <thead>
                <tr>
                  <th className="px-2 py-1 text-left text-gray-500 dark:text-gray-400 font-medium">
                    フック \ オファー
                  </th>
                  {offerKeys.map((ok) => (
                    <th key={ok} className="px-2 py-1 text-center text-gray-500 dark:text-gray-400 font-medium max-w-[80px] truncate">
                      {ok}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {hookKeys.map((hk) => (
                  <tr key={hk}>
                    <td className="px-2 py-1 text-gray-600 dark:text-gray-300 font-medium max-w-[100px] truncate">
                      {hk}
                    </td>
                    {offerKeys.map((ok) => {
                      const val = crossTab[hk]?.[ok] || 0;
                      const intensity = val / crossMax;
                      return (
                        <td
                          key={ok}
                          className="px-2 py-1 text-center text-gray-700 dark:text-gray-200"
                          style={{
                            backgroundColor: `rgba(59, 130, 246, ${intensity * 0.6})`,
                          }}
                        >
                          {val > 0 ? val : ""}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Monthly trends */}
      {trendsData && trendsData.months && trendsData.months.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">月別トレンド</h3>
          <div className="space-y-4">
            {PANEL_KEYS.slice(0, 3).map((field) => {
              /* Gather all unique values for this field across months */
              const allValues = new Set<string>();
              trendsData.months.forEach((m) => {
                const dist = m.distributions?.[field];
                if (dist) Object.keys(dist).forEach((v) => allValues.add(v));
              });
              const values = Array.from(allValues).slice(0, 5);
              if (values.length === 0) return null;

              const maxVal = Math.max(
                1,
                ...trendsData.months.flatMap((m) =>
                  values.map((v) => m.distributions?.[field]?.[v] || 0),
                ),
              );

              return (
                <div key={field}>
                  <p className="text-xs font-medium text-gray-600 dark:text-gray-300 mb-2">{PANEL_LABELS[field]}</p>
                  <div className="flex items-end gap-1 h-24">
                    {trendsData.months.map((m) => (
                      <div key={m.month} className="flex-1 flex flex-col items-center gap-0.5">
                        {/* Stacked bars */}
                        <div className="flex-1 w-full flex flex-col justify-end">
                          {values.map((v, vi) => {
                            const count = m.distributions?.[field]?.[v] || 0;
                            const h = (count / maxVal) * 100;
                            return (
                              <div
                                key={v}
                                className={`w-full ${PANEL_COLORS[vi % PANEL_COLORS.length]} opacity-80`}
                                style={{ height: `${h}%`, minHeight: count > 0 ? 2 : 0 }}
                                title={`${v}: ${count}`}
                              />
                            );
                          })}
                        </div>
                        <span className="text-[9px] text-gray-400 dark:text-gray-500 mt-1">{m.month.slice(5)}</span>
                      </div>
                    ))}
                  </div>
                  {/* Legend */}
                  <div className="flex flex-wrap gap-2 mt-2">
                    {values.map((v, vi) => (
                      <span key={v} className="flex items-center gap-1 text-[10px] text-gray-500 dark:text-gray-400">
                        <span className={`w-2 h-2 rounded-full ${PANEL_COLORS[vi % PANEL_COLORS.length]}`} />
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
