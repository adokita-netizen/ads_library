"use client";

import React from "react";

interface SuggestionTypeStat {
  type: "keyword" | "genre" | "product" | "advertiser";
  count: number;
}

interface SearchUxSettingsPanelProps {
  autoOpenDefaultSuggestions: boolean;
  onToggleAutoOpen: () => void;
  showSuggestionWeights: boolean;
  onToggleSuggestionWeights: () => void;
  defaultSuggestionLimit: number;
  allowedSuggestionLimits: number[];
  onChangeSuggestionLimit: (limit: number) => void;
  suggestionTypeStats: SuggestionTypeStat[];
  suggestionTypeWeights: Partial<
    Record<"keyword" | "genre" | "product" | "advertiser", number>
  >;
}

const typeLabelMap: Record<SuggestionTypeStat["type"], string> = {
  keyword: "検索語",
  genre: "ジャンル",
  product: "商材",
  advertiser: "広告主",
};

export default function SearchUxSettingsPanel({
  autoOpenDefaultSuggestions,
  onToggleAutoOpen,
  showSuggestionWeights,
  onToggleSuggestionWeights,
  defaultSuggestionLimit,
  allowedSuggestionLimits,
  onChangeSuggestionLimit,
  suggestionTypeStats,
  suggestionTypeWeights,
}: SearchUxSettingsPanelProps) {
  return (
    <>
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-[10px] font-medium tracking-wide text-gray-400">
          人気の検索候補
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleAutoOpen}
            className="text-[9px] text-gray-400 hover:text-gray-600 transition-colors"
          >
            {autoOpenDefaultSuggestions ? "自動表示ON" : "自動表示OFF"}
          </button>
          {suggestionTypeStats.length > 0 && (
            <button
              type="button"
              onClick={onToggleSuggestionWeights}
              className="text-[9px] text-gray-400 hover:text-gray-600 transition-colors"
            >
              {showSuggestionWeights ? "重みを隠す" : "重み表示"}
            </button>
          )}
        </div>
      </div>

      <div className="mb-2 flex items-center gap-1.5 text-[9px] text-gray-400">
        <span>表示数</span>
        {allowedSuggestionLimits.map((limit) => (
          <button
            key={limit}
            type="button"
            onClick={() => onChangeSuggestionLimit(limit)}
            className={`rounded-full px-1.5 py-0.5 transition-colors ${
              defaultSuggestionLimit === limit
                ? "bg-gray-200 text-gray-700"
                : "bg-gray-100 hover:bg-gray-200"
            }`}
          >
            {limit}
          </button>
        ))}
      </div>

      {suggestionTypeStats.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {suggestionTypeStats.map((item) => (
            <span
              key={item.type}
              className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[9px] text-gray-500"
            >
              <span>{typeLabelMap[item.type]}</span>
              <span className="font-medium text-gray-600">{item.count}</span>
              {showSuggestionWeights &&
                suggestionTypeWeights[item.type] !== undefined && (
                  <span className="text-gray-400">
                    w{Number(suggestionTypeWeights[item.type]).toFixed(2)}
                  </span>
                )}
            </span>
          ))}
        </div>
      )}
    </>
  );
}
