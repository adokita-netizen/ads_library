"use client";

import { useEffect, useState } from "react";

const SUGGESTION_WEIGHTS_STORAGE_KEY = "smart-search:show-suggestion-weights";
const DEFAULT_SUGGESTION_LIMIT_STORAGE_KEY =
  "smart-search:default-suggestion-limit";
const AUTO_OPEN_DEFAULT_SUGGESTIONS_STORAGE_KEY =
  "smart-search:auto-open-default-suggestions";

const DEFAULT_SUGGESTION_LIMIT = 8;
const ALLOWED_SUGGESTION_LIMITS = [6, 8, 10, 12];

export function useSearchUxSettings() {
  const [showSuggestionWeights, setShowSuggestionWeights] = useState(false);
  const [defaultSuggestionLimit, setDefaultSuggestionLimit] = useState(
    DEFAULT_SUGGESTION_LIMIT
  );
  const [autoOpenDefaultSuggestions, setAutoOpenDefaultSuggestions] =
    useState(true);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const savedWeights = window.localStorage.getItem(
      SUGGESTION_WEIGHTS_STORAGE_KEY
    );
    if (savedWeights === "true") {
      setShowSuggestionWeights(true);
    }

    const savedLimit = Number(
      window.localStorage.getItem(DEFAULT_SUGGESTION_LIMIT_STORAGE_KEY)
    );
    if (ALLOWED_SUGGESTION_LIMITS.includes(savedLimit)) {
      setDefaultSuggestionLimit(savedLimit);
    }

    const savedAutoOpen = window.localStorage.getItem(
      AUTO_OPEN_DEFAULT_SUGGESTIONS_STORAGE_KEY
    );
    if (savedAutoOpen === "false") {
      setAutoOpenDefaultSuggestions(false);
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      SUGGESTION_WEIGHTS_STORAGE_KEY,
      showSuggestionWeights ? "true" : "false"
    );
  }, [showSuggestionWeights]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      DEFAULT_SUGGESTION_LIMIT_STORAGE_KEY,
      String(defaultSuggestionLimit)
    );
  }, [defaultSuggestionLimit]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      AUTO_OPEN_DEFAULT_SUGGESTIONS_STORAGE_KEY,
      autoOpenDefaultSuggestions ? "true" : "false"
    );
  }, [autoOpenDefaultSuggestions]);

  return {
    showSuggestionWeights,
    setShowSuggestionWeights,
    defaultSuggestionLimit,
    setDefaultSuggestionLimit,
    autoOpenDefaultSuggestions,
    setAutoOpenDefaultSuggestions,
    allowedSuggestionLimits: ALLOWED_SUGGESTION_LIMITS,
  };
}
