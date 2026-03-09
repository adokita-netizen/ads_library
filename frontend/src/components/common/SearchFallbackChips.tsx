"use client";

import React from "react";

export interface SearchFallbackSuggestion {
  type: "keyword" | "product" | "advertiser" | "genre";
  label: string;
  value: string;
  count?: number;
}

interface SearchFallbackChipsProps {
  suggestions: SearchFallbackSuggestion[];
  onSelect: (suggestion: SearchFallbackSuggestion) => void;
  align?: "left" | "center";
}

const typeLabelMap: Record<SearchFallbackSuggestion["type"], string> = {
  genre: "ジャンル",
  product: "商材",
  advertiser: "広告主",
  keyword: "検索語",
};

const typeClassMap: Record<SearchFallbackSuggestion["type"], string> = {
  genre: "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100",
  product: "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100",
  advertiser: "border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100",
  keyword: "border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100",
};

const typeCountClassMap: Record<SearchFallbackSuggestion["type"], string> = {
  genre: "text-blue-400",
  product: "text-emerald-400",
  advertiser: "text-violet-400",
  keyword: "text-amber-400",
};

export default function SearchFallbackChips({
  suggestions,
  onSelect,
  align = "left",
}: SearchFallbackChipsProps) {
  if (suggestions.length === 0) return null;

  return (
    <div
      className={`flex flex-wrap gap-1.5 ${
        align === "center" ? "items-center justify-center" : ""
      }`}
    >
      {suggestions.map((suggestion) => (
        <button
          key={`${suggestion.type}-${suggestion.value}`}
          onClick={() => onSelect(suggestion)}
          className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] transition-colors ${typeClassMap[suggestion.type]}`}
        >
          <span>{typeLabelMap[suggestion.type]}</span>
          <span className="font-medium">{suggestion.label}</span>
          {suggestion.count !== undefined && (
            <span className={typeCountClassMap[suggestion.type]}>({suggestion.count})</span>
          )}
        </button>
      ))}
    </div>
  );
}
