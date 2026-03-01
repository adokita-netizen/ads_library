"use client";

import { useState, useEffect } from "react";

/**
 * Debounce a value with a consistent delay.
 * Standard delay: 300ms (optimal for search input responsiveness).
 */
export function useDebounce<T>(value: T, delay = 300): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
