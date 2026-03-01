"use client";

import React, { useCallback } from "react";

/* ─── Types ─── */

interface QuickFilterChip {
  key: string;
  label: string;
}

interface QuickFilterBarProps {
  activeFilters: string[];
  onChange: (filters: string[]) => void;
}

/* ─── Default chips ─── */

const DEFAULT_CHIPS: QuickFilterChip[] = [
  { key: "hitOnly", label: "HIT広告のみ" },
  { key: "videoOnly", label: "動画のみ" },
  { key: "activeOnly", label: "配信中" },
  { key: "recentOnly", label: "今週の新着" },
  { key: "highScore", label: "スコア70+" },
];

/* ─── Component ─── */

export default function QuickFilterBar({ activeFilters, onChange }: QuickFilterBarProps) {
  const handleToggle = useCallback(
    (key: string) => {
      const isActive = activeFilters.includes(key);
      if (isActive) {
        onChange(activeFilters.filter((f) => f !== key));
      } else {
        onChange([...activeFilters, key]);
      }
    },
    [activeFilters, onChange],
  );

  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {DEFAULT_CHIPS.map((chip) => {
        const isActive = activeFilters.includes(chip.key);
        return (
          <button
            key={chip.key}
            onClick={() => handleToggle(chip.key)}
            className={`shrink-0 rounded-full px-3 py-1 text-[11px] font-medium transition-colors whitespace-nowrap ${
              isActive
                ? "bg-[#4A7DFF] text-white"
                : "bg-gray-100 text-gray-500 hover:bg-gray-200"
            }`}
          >
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}
