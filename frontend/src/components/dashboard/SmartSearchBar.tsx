"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

interface AutocompleteSuggestion {
  type: "all" | "genre" | "product" | "advertiser";
  label: string;
  value: string;
  count?: number;
}

interface SmartSearchBarProps {
  onSearch: (query: string, scope?: string) => void;
  onGenreFilter: (genre: string) => void;
  onProductFilter: (product: string) => void;
  onAdvertiserFilter: (advertiser: string) => void;
  onSaveCollection?: () => void;
  placeholder?: string;
  currentQuery?: string;
}

export default function SmartSearchBar({
  onSearch,
  onGenreFilter,
  onProductFilter,
  onAdvertiserFilter,
  onSaveCollection,
  placeholder = "広告・商材・広告主を検索...",
  currentQuery = "",
}: SmartSearchBarProps) {
  const [query, setQuery] = useState(currentQuery);
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Fetch autocomplete suggestions
  const fetchSuggestions = useCallback(async (q: string) => {
    if (!q.trim()) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }
    setLoading(true);
    try {
      const data = await fetchApi<{
        suggestions?: AutocompleteSuggestion[];
        genres?: { label: string; value: string; count?: number }[];
        products?: { label: string; value: string; count?: number }[];
        advertisers?: { label: string; value: string; count?: number }[];
      }>("/rankings/smart-autocomplete", {
        params: { query: q },
      });

      const items: AutocompleteSuggestion[] = [];

      // "Search all" option
      items.push({
        type: "all",
        label: `${q} - すべてから検索`,
        value: q,
      });

      if (data.suggestions) {
        items.push(...data.suggestions);
      } else {
        // Build from separate arrays
        if (data.genres) {
          data.genres.forEach((g) =>
            items.push({
              type: "genre",
              label: `${g.label} で絞り込み`,
              value: g.value,
              count: g.count,
            })
          );
        }
        if (data.products) {
          data.products.forEach((p) =>
            items.push({
              type: "product",
              label: `${p.label} で絞り込み`,
              value: p.value,
              count: p.count,
            })
          );
        }
        if (data.advertisers) {
          data.advertisers.forEach((a) =>
            items.push({
              type: "advertiser",
              label: `${a.label} で絞り込み`,
              value: a.value,
              count: a.count,
            })
          );
        }
      }

      setSuggestions(items);
      setShowDropdown(items.length > 0);
      setActiveIndex(-1);
    } catch {
      // On error, just show the "search all" option
      setSuggestions([
        { type: "all", label: `${q} - すべてから検索`, value: q },
      ]);
      setShowDropdown(true);
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced input handler
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(val), 250);
  };

  // Select a suggestion
  const handleSelect = (item: AutocompleteSuggestion) => {
    setShowDropdown(false);
    switch (item.type) {
      case "genre":
        onGenreFilter(item.value);
        setQuery("");
        break;
      case "product":
        onProductFilter(item.value);
        setQuery(item.value);
        break;
      case "advertiser":
        onAdvertiserFilter(item.value);
        setQuery(item.value);
        break;
      default:
        onSearch(item.value);
        setQuery(item.value);
        break;
    }
  };

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showDropdown) {
      if (e.key === "Enter") {
        onSearch(query);
      }
      return;
    }
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : 0
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((prev) =>
          prev > 0 ? prev - 1 : suggestions.length - 1
        );
        break;
      case "Enter":
        e.preventDefault();
        if (activeIndex >= 0 && suggestions[activeIndex]) {
          handleSelect(suggestions[activeIndex]);
        } else {
          onSearch(query);
          setShowDropdown(false);
        }
        break;
      case "Escape":
        setShowDropdown(false);
        break;
    }
  };

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Sync external query changes
  useEffect(() => {
    setQuery(currentQuery);
  }, [currentQuery]);

  const typeTag = (type: string) => {
    switch (type) {
      case "genre":
        return (
          <span className="ml-auto shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700">
            ジャンル
          </span>
        );
      case "product":
        return (
          <span className="ml-auto shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold bg-emerald-100 text-emerald-700">
            商材
          </span>
        );
      case "advertiser":
        return (
          <span className="ml-auto shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold bg-purple-100 text-purple-700">
            広告主
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="relative flex-1 max-w-xl">
      <div className="relative flex items-center">
        {/* Search icon */}
        <svg
          className="absolute left-3 w-4 h-4 text-gray-400 pointer-events-none"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
          />
        </svg>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (query.trim() && suggestions.length > 0) setShowDropdown(true);
          }}
          placeholder={placeholder}
          className="w-full pl-9 pr-20 py-2 text-[13px] border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30 focus:border-[#4A7DFF] placeholder-gray-400 transition-all"
        />
        {/* Loading spinner */}
        {loading && (
          <div className="absolute right-14 w-4 h-4">
            <svg
              className="animate-spin text-gray-400"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="3"
                className="opacity-25"
              />
              <path
                fill="currentColor"
                className="opacity-75"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
          </div>
        )}
        {/* Save collection button */}
        {onSaveCollection && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSaveCollection();
            }}
            className="absolute right-8 p-1 text-gray-400 hover:text-[#4A7DFF] transition-colors"
            title="検索条件を保存"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.8}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
              />
            </svg>
          </button>
        )}
        {/* Clear button */}
        {query && (
          <button
            onClick={() => {
              setQuery("");
              setSuggestions([]);
              setShowDropdown(false);
              onSearch("");
            }}
            className="absolute right-2 p-1 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && suggestions.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-50 mt-1 w-full bg-white rounded-lg shadow-lg border border-gray-200 py-1 max-h-72 overflow-y-auto"
        >
          {suggestions.map((item, idx) => (
            <button
              key={`${item.type}-${item.value}-${idx}`}
              onClick={() => handleSelect(item)}
              className={`w-full flex items-center gap-2 px-3 py-2 text-[13px] text-left transition-colors ${
                idx === activeIndex
                  ? "bg-[#EEF2FF] text-[#4A7DFF]"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              {item.type === "all" ? (
                <svg
                  className="w-3.5 h-3.5 text-gray-400 shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
                  />
                </svg>
              ) : (
                <svg
                  className="w-3.5 h-3.5 text-gray-400 shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z"
                  />
                </svg>
              )}
              <span className="truncate">{item.label}</span>
              {item.count !== undefined && (
                <span className="text-[10px] text-gray-400 shrink-0">
                  ({item.count})
                </span>
              )}
              {typeTag(item.type)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
