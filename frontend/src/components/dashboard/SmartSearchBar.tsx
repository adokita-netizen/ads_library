"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { useDebounce } from "@/lib/useDebounce";
import { useSearchUxSettings } from "@/lib/useSearchUxSettings";
import SearchUxSettingsPanel from "../common/SearchUxSettingsPanel";
import SearchFallbackChips, {
  type SearchFallbackSuggestion,
} from "../common/SearchFallbackChips";

interface AutocompleteSuggestion {
  type: "all" | "genre" | "product" | "advertiser" | "keyword";
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
  placeholder = "広告・商材・広告主を検索... 例: GLP-1 / マンジャロ / ピラティス / 24時間ジム",
  currentQuery = "",
}: SmartSearchBarProps) {
  const [query, setQuery] = useState(currentQuery);
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [loading, setLoading] = useState(false);
  const [defaultSuggestions, setDefaultSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [suggestionTypeStats, setSuggestionTypeStats] = useState<
    { type: "keyword" | "genre" | "product" | "advertiser"; count: number }[]
  >([]);
  const [suggestionTypeWeights, setSuggestionTypeWeights] = useState<
    Partial<Record<"keyword" | "genre" | "product" | "advertiser", number>>
  >({});
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debouncedQuery = useDebounce(query);
  const {
    showSuggestionWeights,
    setShowSuggestionWeights,
    defaultSuggestionLimit,
    setDefaultSuggestionLimit,
    autoOpenDefaultSuggestions,
    setAutoOpenDefaultSuggestions,
    allowedSuggestionLimits,
  } = useSearchUxSettings();

  const trackSearchInteraction = useCallback(
    async ({
      queryText,
      selectedValue,
      suggestionType,
    }: {
      queryText: string;
      selectedValue?: string;
      suggestionType?: AutocompleteSuggestion["type"] | "text";
    }) => {
      const normalizedQuery = queryText.trim();
      const normalizedSelected = selectedValue?.trim() ?? "";
      if (!normalizedQuery && !normalizedSelected) return;

      try {
        await fetchApi("/rankings/search-analytics/track", {
          method: "POST",
          body: {
            query: normalizedQuery || normalizedSelected,
            selected_value: normalizedSelected || null,
            suggestion_type: suggestionType ?? "text",
          },
        });
      } catch {
        // Ignore analytics failures to keep search responsive.
      }
    },
    []
  );

  const fetchDefaultSuggestions = useCallback(async () => {
    if (defaultSuggestions.length > 0) {
      setSuggestions(defaultSuggestions);
      setShowDropdown(true);
      setActiveIndex(-1);
      return;
    }

    setLoading(true);
    try {
      const data = await fetchApi<{
        default_suggestions?: SearchFallbackSuggestion[];
        default_suggestion_weights?: Partial<
          Record<"keyword" | "genre" | "product" | "advertiser", number>
        >;
        popular_suggestion_types?: {
          type: "keyword" | "genre" | "product" | "advertiser";
          count: number;
        }[];
        popular_keywords?: { keyword: string; count?: number }[];
        popular_genres?: { genre: string; search_count?: number }[];
        popular_products?: { product: string; count?: number }[];
        popular_advertisers?: { advertiser: string; count?: number }[];
      }>("/rankings/search-analytics");

      const items: AutocompleteSuggestion[] = [];

      if (data.default_suggestions?.length) {
        data.default_suggestions.forEach((item) => {
          items.push({
            type: item.type,
            label:
              item.type === "genre"
                ? `${item.label} で絞り込み`
                : `${item.label} で検索`,
            value: item.value,
            count: item.count,
          });
        });
      } else {

        data.popular_keywords?.slice(0, 6).forEach((item) => {
          if (!item.keyword?.trim()) return;
          items.push({
            type: "keyword",
            label: `${item.keyword} で検索`,
            value: item.keyword,
            count: item.count,
          });
        });

        data.popular_genres?.slice(0, 4).forEach((item) => {
          if (!item.genre?.trim()) return;
          items.push({
            type: "genre",
            label: `${item.genre} で絞り込み`,
            value: item.genre,
            count: item.search_count,
          });
        });

        data.popular_products?.slice(0, 3).forEach((item) => {
          if (!item.product?.trim()) return;
          items.push({
            type: "product",
            label: `${item.product} で絞り込み`,
            value: item.product,
            count: item.count,
          });
        });

        data.popular_advertisers?.slice(0, 3).forEach((item) => {
          if (!item.advertiser?.trim()) return;
          items.push({
            type: "advertiser",
            label: `${item.advertiser} で絞り込み`,
            value: item.advertiser,
            count: item.count,
          });
        });
      }

      setDefaultSuggestions(items);
      setSuggestionTypeStats(data.popular_suggestion_types?.slice(0, 4) || []);
      setSuggestionTypeWeights(data.default_suggestion_weights || {});
      setSuggestions(items.slice(0, defaultSuggestionLimit));
      setShowDropdown(items.length > 0);
      setActiveIndex(-1);
    } catch {
      setDefaultSuggestions([]);
      setSuggestionTypeStats([]);
      setSuggestionTypeWeights({});
    } finally {
      setLoading(false);
    }
  }, [defaultSuggestionLimit, defaultSuggestions]);

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
        keywords?: { label: string; value: string; count?: number }[];
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
        if (data.keywords) {
          data.keywords.forEach((k) =>
            items.push({
              type: "keyword",
              label: `${k.label} で検索`,
              value: k.value,
              count: k.count,
            })
          );
        }
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

  // Trigger suggestions fetch on debounced query change
  useEffect(() => {
    fetchSuggestions(debouncedQuery);
  }, [debouncedQuery, fetchSuggestions]);

  // Input handler
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
  };

  // Select a suggestion
  const handleSelect = (item: AutocompleteSuggestion) => {
    setShowDropdown(false);
    void trackSearchInteraction({
      queryText: query,
      selectedValue: item.value,
      suggestionType: item.type === "all" ? "text" : item.type,
    });
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
        void trackSearchInteraction({ queryText: query, suggestionType: "text" });
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
          void trackSearchInteraction({ queryText: query, suggestionType: "text" });
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
      case "keyword":
        return (
          <span className="ml-auto shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-700">
            検索語
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
    <div className="relative flex-1 max-w-full sm:max-w-xl">
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
            if (query.trim() && suggestions.length > 0) {
              setShowDropdown(true);
              return;
            }
            if (!query.trim() && autoOpenDefaultSuggestions) {
              fetchDefaultSuggestions();
            }
          }}
          placeholder={placeholder}
          aria-label="広告・商材・広告主を検索"
          aria-expanded={showDropdown}
          aria-controls="search-suggestions"
          aria-autocomplete="list"
          aria-activedescendant={activeIndex >= 0 ? `suggestion-${activeIndex}` : undefined}
          role="combobox"
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
            aria-label="検索をクリア"
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
          id="search-suggestions"
          ref={dropdownRef}
          role="listbox"
          aria-label="検索候補"
          className="absolute z-50 mt-1 w-full bg-white rounded-lg shadow-lg border border-gray-200 py-1 max-h-72 overflow-y-auto"
        >
          {!query.trim() && defaultSuggestions.length > 0 && (
            <div className="px-3 py-2 border-b border-gray-100">
              <SearchUxSettingsPanel
                autoOpenDefaultSuggestions={autoOpenDefaultSuggestions}
                onToggleAutoOpen={() =>
                  setAutoOpenDefaultSuggestions((prev) => !prev)
                }
                showSuggestionWeights={showSuggestionWeights}
                onToggleSuggestionWeights={() =>
                  setShowSuggestionWeights((prev) => !prev)
                }
                defaultSuggestionLimit={defaultSuggestionLimit}
                allowedSuggestionLimits={allowedSuggestionLimits}
                onChangeSuggestionLimit={setDefaultSuggestionLimit}
                suggestionTypeStats={suggestionTypeStats}
                suggestionTypeWeights={suggestionTypeWeights}
              />
              <SearchFallbackChips
                suggestions={
                  defaultSuggestions.slice(
                    0,
                    defaultSuggestionLimit
                  ) as SearchFallbackSuggestion[]
                }
                onSelect={(suggestion) =>
                  handleSelect({
                    type: suggestion.type,
                    label: suggestion.label,
                    value: suggestion.value,
                    count: suggestion.count,
                  })
                }
              />
            </div>
          )}
          {(query.trim() ? suggestions : []).map((item, idx) => (
            <button
              id={`suggestion-${idx}`}
              key={`${item.type}-${item.value}-${idx}`}
              role="option"
              aria-selected={idx === activeIndex}
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
