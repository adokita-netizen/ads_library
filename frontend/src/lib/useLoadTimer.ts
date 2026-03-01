import { useState, useEffect, useRef } from "react";

/**
 * Measures time from component mount until loading completes.
 * Returns elapsed milliseconds and a formatted string.
 */
export function useLoadTimer(loading: boolean): {
  elapsedMs: number;
  formatted: string;
} {
  const startRef = useRef(Date.now());
  const [elapsed, setElapsed] = useState(0);

  // Reset timer when loading starts
  useEffect(() => {
    if (loading) {
      startRef.current = Date.now();
      setElapsed(0);
    }
  }, [loading]);

  // Record elapsed time when loading ends
  useEffect(() => {
    if (!loading && startRef.current > 0) {
      setElapsed(Date.now() - startRef.current);
    }
  }, [loading]);

  const formatted =
    elapsed > 0
      ? elapsed < 1000
        ? `${elapsed}ms`
        : `${(elapsed / 1000).toFixed(1)}s`
      : "";

  return { elapsedMs: elapsed, formatted };
}
