"use client";

import { useState, useMemo } from "react";
import type { LPAssetInfo } from "@/types";

interface LPAssetTableProps {
  assets: LPAssetInfo[];
}

type SortField = "asset_kind" | "content_type" | "byte_size" | "status_code" | "used_in_mirror";
type SortDir = "asc" | "desc";

const KIND_COLORS: Record<string, string> = {
  document: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  stylesheet: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  image: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  font: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300",
  media: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  script: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
};

function getStatusColor(code?: number): string {
  if (!code) return "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400";
  if (code >= 200 && code < 300) return "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300";
  if (code >= 300 && code < 400) return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300";
  return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
}

function formatFileSize(bytes?: number): string {
  if (bytes === undefined || bytes === null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function extractFilename(url: string): string {
  try {
    const u = new URL(url);
    const parts = u.pathname.split("/");
    return parts[parts.length - 1] || u.pathname;
  } catch {
    const parts = url.split("/");
    return parts[parts.length - 1] || url;
  }
}

export default function LPAssetTable({ assets }: LPAssetTableProps) {
  const [sortField, setSortField] = useState<SortField>("asset_kind");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [kindFilter, setKindFilter] = useState<string>("all");

  const uniqueKinds = useMemo(() => {
    const kinds = new Set(assets.map((a) => a.asset_kind));
    return Array.from(kinds).sort();
  }, [assets]);

  const filteredAndSorted = useMemo(() => {
    let filtered = kindFilter === "all" ? assets : assets.filter((a) => a.asset_kind === kindFilter);

    filtered = [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "asset_kind":
          cmp = a.asset_kind.localeCompare(b.asset_kind);
          break;
        case "content_type":
          cmp = (a.content_type || "").localeCompare(b.content_type || "");
          break;
        case "byte_size":
          cmp = (a.byte_size || 0) - (b.byte_size || 0);
          break;
        case "status_code":
          cmp = (a.status_code || 0) - (b.status_code || 0);
          break;
        case "used_in_mirror":
          cmp = (a.used_in_mirror ? 1 : 0) - (b.used_in_mirror ? 1 : 0);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return filtered;
  }, [assets, kindFilter, sortField, sortDir]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => (
    <svg
      className={`w-3 h-3 ml-0.5 inline-block transition-transform ${
        sortField === field ? "text-blue-500" : "text-gray-300 dark:text-gray-600"
      } ${sortField === field && sortDir === "desc" ? "rotate-180" : ""}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
    </svg>
  );

  return (
    <div className="flex flex-col">
      {/* Filter bar */}
      <div className="flex items-center gap-3 px-4 py-2.5 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
        <span className="text-[11px] font-medium text-gray-500 dark:text-gray-400">フィルタ:</span>
        <div className="flex items-center gap-1 flex-wrap">
          <button
            onClick={() => setKindFilter("all")}
            className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
              kindFilter === "all"
                ? "bg-blue-600 text-white"
                : "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700"
            }`}
          >
            すべて ({assets.length})
          </button>
          {uniqueKinds.map((kind) => {
            const count = assets.filter((a) => a.asset_kind === kind).length;
            return (
              <button
                key={kind}
                onClick={() => setKindFilter(kind)}
                className={`px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors ${
                  kindFilter === kind
                    ? "bg-blue-600 text-white"
                    : `${KIND_COLORS[kind] || "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"} hover:opacity-80`
                }`}
              >
                {kind} ({count})
              </button>
            );
          })}
        </div>
        <span className="ml-auto text-[10px] text-gray-400 dark:text-gray-500">
          合計サイズ: {formatFileSize(filteredAndSorted.reduce((sum, a) => sum + (a.byte_size || 0), 0))}
        </span>
      </div>

      {/* Table */}
      <div className="overflow-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
              <th className="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400 w-10">#</th>
              <th
                className="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200"
                onClick={() => handleSort("asset_kind")}
              >
                種類 <SortIcon field="asset_kind" />
              </th>
              <th className="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400 max-w-xs">URL</th>
              <th
                className="px-4 py-2 text-left font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200"
                onClick={() => handleSort("content_type")}
              >
                Content-Type <SortIcon field="content_type" />
              </th>
              <th
                className="px-4 py-2 text-right font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200"
                onClick={() => handleSort("byte_size")}
              >
                サイズ <SortIcon field="byte_size" />
              </th>
              <th
                className="px-4 py-2 text-center font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200"
                onClick={() => handleSort("status_code")}
              >
                ステータス <SortIcon field="status_code" />
              </th>
              <th
                className="px-4 py-2 text-center font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-700 dark:hover:text-gray-200"
                onClick={() => handleSort("used_in_mirror")}
              >
                ミラー使用 <SortIcon field="used_in_mirror" />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {filteredAndSorted.map((asset, i) => (
              <tr key={asset.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors">
                <td className="px-4 py-2 text-gray-400 dark:text-gray-500">{i + 1}</td>
                <td className="px-4 py-2">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold ${KIND_COLORS[asset.asset_kind] || "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400"}`}>
                    {asset.asset_kind}
                  </span>
                </td>
                <td className="px-4 py-2 max-w-xs truncate text-gray-600 dark:text-gray-300" title={asset.original_url}>
                  {extractFilename(asset.original_url)}
                </td>
                <td className="px-4 py-2 text-gray-500 dark:text-gray-400 font-mono text-[10px]">
                  {asset.content_type || "-"}
                </td>
                <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-300 tabular-nums">
                  {formatFileSize(asset.byte_size)}
                </td>
                <td className="px-4 py-2 text-center">
                  {asset.status_code ? (
                    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold ${getStatusColor(asset.status_code)}`}>
                      {asset.status_code}
                    </span>
                  ) : (
                    <span className="text-gray-300 dark:text-gray-600">-</span>
                  )}
                </td>
                <td className="px-4 py-2 text-center">
                  {asset.used_in_mirror ? (
                    <svg className="w-4 h-4 text-green-500 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4 text-gray-300 dark:text-gray-600 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredAndSorted.length === 0 && (
          <div className="flex items-center justify-center py-12 text-[12px] text-gray-400 dark:text-gray-500">
            アセットが見つかりません
          </div>
        )}
      </div>
    </div>
  );
}
