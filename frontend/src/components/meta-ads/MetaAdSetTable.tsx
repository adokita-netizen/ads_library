"use client";

import type { MetaAdSet } from "@/types";
import { metaMarketingApi } from "@/lib/api";
import StatusToggle from "./StatusToggle";

interface Props {
  adSets: MetaAdSet[];
  onRefresh: () => void;
  refreshing?: boolean;
  page?: number;
  total?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
}

export default function MetaAdSetTable({ adSets, onRefresh, refreshing, page = 1, total = 0, pageSize = 20, onPageChange }: Props) {
  if (adSets.length === 0) {
    return (
      <div className="text-center py-12">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-gray-100 mb-3">
          <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
        </div>
        <p className="text-[13px] text-gray-600 font-medium mb-1">
          広告セットデータがありません
        </p>
        <p className="text-[11px] text-gray-400 mb-4">
          キャンペーンを作成してから広告セットを追加してください
        </p>
        <button onClick={onRefresh} className="btn-secondary text-[11px] px-3 py-1.5">
          データを同期
        </button>
      </div>
    );
  }

  const formatTargeting = (targeting: Record<string, unknown> | undefined): string => {
    if (!targeting) return "-";
    const parts: string[] = [];
    if (targeting.age_min || targeting.age_max) {
      parts.push(`${targeting.age_min || "?"}~${targeting.age_max || "?"}歳`);
    }
    if (targeting.genders && Array.isArray(targeting.genders)) {
      const genderMap: Record<number, string> = { 1: "男性", 2: "女性" };
      parts.push(targeting.genders.map((g: number) => genderMap[g] || "").filter(Boolean).join("/"));
    }
    if (targeting.geo_locations && typeof targeting.geo_locations === "object") {
      const geo = targeting.geo_locations as Record<string, unknown>;
      if (Array.isArray(geo.countries)) {
        parts.push(geo.countries.join(","));
      }
    }
    return parts.join(" / ") || "-";
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[13px] font-bold text-gray-800">広告セット ({adSets.length})</h3>
        <button
          onClick={onRefresh}
          disabled={refreshing}
          className="btn-secondary text-[11px] px-3 py-1 disabled:opacity-50"
        >
          {refreshing ? (
            <span className="inline-flex items-center gap-1">
              <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              更新中...
            </span>
          ) : "更新"}
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[12px]" aria-label="広告セット一覧">
          <thead>
            <tr className="border-b border-gray-200">
              <th scope="col" className="text-left py-2 px-3 text-gray-500 font-medium">名前</th>
              <th scope="col" className="text-left py-2 px-3 text-gray-500 font-medium">ステータス</th>
              <th scope="col" className="text-right py-2 px-3 text-gray-500 font-medium">日予算</th>
              <th scope="col" className="text-left py-2 px-3 text-gray-500 font-medium">入札戦略</th>
              <th scope="col" className="text-left py-2 px-3 text-gray-500 font-medium">最適化目標</th>
              <th scope="col" className="text-left py-2 px-3 text-gray-500 font-medium">ターゲティング</th>
            </tr>
          </thead>
          <tbody>
            {adSets.map((as) => (
              <tr key={as.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-2 px-3">
                  <p className="font-medium text-gray-800">{as.name}</p>
                  <p className="text-[10px] text-gray-400">{as.meta_id}</p>
                </td>
                <td className="py-2 px-3">
                  <StatusToggle
                    currentStatus={as.effective_status}
                    entityType="ad-set"
                    entityName={as.name}
                    onStatusChange={async (newStatus) => {
                      await metaMarketingApi.updateAdSetStatus(as.meta_id, { status: newStatus });
                      onRefresh();
                    }}
                  />
                </td>
                <td className="py-2 px-3 text-right text-gray-600">
                  {as.daily_budget ? `¥${Number(as.daily_budget).toLocaleString()}` : "-"}
                </td>
                <td className="py-2 px-3 text-gray-600">{as.bid_strategy || "-"}</td>
                <td className="py-2 px-3 text-gray-600">{as.optimization_goal || "-"}</td>
                <td className="py-2 px-3 text-gray-500 text-[11px] max-w-[200px] truncate">
                  {formatTargeting(as.targeting)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > pageSize && onPageChange && (
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
          <span className="text-[11px] text-gray-400">
            全{total}件中 {(page - 1) * pageSize + 1}〜{Math.min(page * pageSize, total)}件
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="text-[11px] px-2 py-1 rounded border border-gray-200 disabled:opacity-30 hover:bg-gray-50"
            >
              前へ
            </button>
            <span className="text-[11px] px-2 py-1 text-gray-500">
              {page} / {Math.ceil(total / pageSize)}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= Math.ceil(total / pageSize)}
              className="text-[11px] px-2 py-1 rounded border border-gray-200 disabled:opacity-30 hover:bg-gray-50"
            >
              次へ
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
