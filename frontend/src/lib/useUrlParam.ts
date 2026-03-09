"use client";

import { useState, useCallback, useEffect } from "react";

export const URL_STATE_CHANGE_EVENT = "vaap:url-state-change";

export function notifyUrlStateChange() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(URL_STATE_CHANGE_EVENT));
}

export function commitUrlSearchParams(
  searchParams: URLSearchParams,
  mode: "replace" | "push" = "replace",
) {
  if (typeof window === "undefined") return;
  const qs = searchParams.toString();
  const nextUrl = qs ? `?${qs}` : window.location.pathname;
  if (mode === "push") {
    window.history.pushState(null, "", nextUrl);
  } else {
    window.history.replaceState(null, "", nextUrl);
  }
  notifyUrlStateChange();
}

function readUrlParamValue(key: string, defaultValue: string) {
  if (typeof window === "undefined") return defaultValue;
  return new URLSearchParams(window.location.search).get(key) || defaultValue;
}

/**
 * Sync a single state value with a URL search parameter.
 * Uses replaceState to avoid page reloads and history pollution.
 *
 * Initial render always uses defaultValue (matches SSR) to avoid hydration mismatch.
 * After mount, reads the URL and syncs the value via useEffect.
 */
export function useUrlParam(key: string, defaultValue: string): [string, (value: string) => void] {
  const [value, setValue] = useState(defaultValue);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const syncFromUrl = () => {
      setValue(readUrlParamValue(key, defaultValue));
    };

    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);
    window.addEventListener(URL_STATE_CHANGE_EVENT, syncFromUrl);
    return () => {
      window.removeEventListener("popstate", syncFromUrl);
      window.removeEventListener(URL_STATE_CHANGE_EVENT, syncFromUrl);
    };
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
      commitUrlSearchParams(sp, "replace");
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
