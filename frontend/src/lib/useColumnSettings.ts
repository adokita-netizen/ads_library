"use client";

import { useState, useCallback } from "react";

export interface ColumnDef {
  key: string;
  label: string;
  /** If true, column cannot be hidden */
  required?: boolean;
  /** Default visibility (default: true) */
  defaultVisible?: boolean;
}

/**
 * Persist column visibility settings to localStorage.
 * Returns a Set of visible column keys and a toggle function.
 */
export function useColumnSettings(
  storageKey: string,
  columns: ColumnDef[]
): {
  visibleColumns: Set<string>;
  toggleColumn: (key: string) => void;
  resetColumns: () => void;
} {
  const getDefaults = () =>
    new Set(
      columns
        .filter((c) => c.defaultVisible !== false)
        .map((c) => c.key)
    );

  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(() => {
    if (typeof window === "undefined") return getDefaults();
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const keys = JSON.parse(stored) as string[];
        // Always include required columns
        const required = columns.filter((c) => c.required).map((c) => c.key);
        return new Set([...required, ...keys]);
      }
    } catch {
      // Ignore parse errors
    }
    return getDefaults();
  });

  const persist = useCallback(
    (cols: Set<string>) => {
      try {
        localStorage.setItem(storageKey, JSON.stringify(Array.from(cols)));
      } catch {
        // Quota exceeded - silently ignore
      }
    },
    [storageKey]
  );

  const toggleColumn = useCallback(
    (key: string) => {
      const col = columns.find((c) => c.key === key);
      if (col?.required) return;
      setVisibleColumns((prev) => {
        const next = new Set(prev);
        if (next.has(key)) {
          next.delete(key);
        } else {
          next.add(key);
        }
        persist(next);
        return next;
      });
    },
    [columns, persist]
  );

  const resetColumns = useCallback(() => {
    const defaults = getDefaults();
    setVisibleColumns(defaults);
    persist(defaults);
  }, [columns, persist]);

  return { visibleColumns, toggleColumn, resetColumns };
}
