"use client";

import { useState, useCallback, useEffect } from "react";

/**
 * Sync a single state value with a URL search parameter.
 * Uses replaceState to avoid page reloads and history pollution.
 *
 * Initial render always uses defaultValue (matches SSR) to avoid hydration mismatch.
 * After mount, reads the URL and syncs the value via useEffect.
 */
export function useUrlParam(key: string, defaultValue: string): [string, (value: string) => void] {
  const [value, setValue] = useState(defaultValue);

  // Sync from URL after hydration (client-only)
  useEffect(() => {
    const urlValue = new URLSearchParams(window.location.search).get(key);
    if (urlValue && urlValue !== defaultValue) {
      setValue(urlValue);
    }
  }, [key, defaultValue]);

  const setUrlParam = useCallback(
    (newValue: string) => {
      setValue(newValue);
      if (typeof window === "undefined") return;
      const sp = new URLSearchParams(window.location.search);
      if (newValue === defaultValue || newValue === "") {
        sp.delete(key);
      } else {
        sp.set(key, newValue);
      }
      const qs = sp.toString();
      window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
    },
    [key, defaultValue]
  );

  return [value, setUrlParam];
}

/**
 * Sync a numeric state value with a URL search parameter.
 */
export function useUrlParamNumber(key: string, defaultValue: number): [number, (value: number) => void] {
  const [strValue, setStrValue] = useUrlParam(key, String(defaultValue));
  const numValue = Number(strValue) || defaultValue;

  const setNumValue = useCallback(
    (value: number) => {
      setStrValue(String(value));
    },
    [setStrValue]
  );

  return [numValue, setNumValue];
}
