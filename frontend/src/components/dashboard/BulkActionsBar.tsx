"use client";

import React from "react";

// ─── Types ───

interface BulkActionsBarProps {
  selectedCount: number;
  onAddToCollection: () => void;
  onExport: () => void;
  onCompare: () => void;
  onClearSelection: () => void;
}

// ─── Component ───

export default function BulkActionsBar({
  selectedCount,
  onAddToCollection,
  onExport,
  onCompare,
  onClearSelection,
}: BulkActionsBarProps) {
  if (selectedCount <= 0) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-40"
      style={{ animation: "slideUp 0.25s ease-out" }}
    >
      <style>{`
        @keyframes slideUp {
          from { transform: translateY(100%); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `}</style>

      <div className="mx-auto max-w-4xl px-4 pb-4">
        <div className="bg-gray-900 rounded-xl shadow-2xl px-5 py-3 flex items-center justify-between gap-3">
          {/* Selected count badge */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-[#4A7DFF] text-white text-[11px] font-bold">
              {selectedCount}
            </span>
            <span className="text-[11px] text-gray-300">件選択中</span>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={onAddToCollection}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium text-white bg-[#4A7DFF] rounded-lg hover:bg-[#3d6ce0] transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              コレクションに追加
            </button>

            <button
              onClick={onExport}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium text-gray-300 bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              エクスポート
            </button>

            <button
              onClick={onCompare}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium text-gray-300 bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
              </svg>
              比較
            </button>

            <div className="w-px h-5 bg-gray-600 mx-1" />

            <button
              onClick={onClearSelection}
              className="flex items-center gap-1 px-2.5 py-1.5 text-[10px] font-medium text-gray-400 hover:text-gray-200 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              選択解除
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
