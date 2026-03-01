"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";

/* ─── Types ─── */

interface SavedView {
  id: string;
  name: string;
  filters: Record<string, string | number | boolean>;
  createdAt: string;
}

interface SavedViewsProps {
  currentFilters: Record<string, unknown>;
  onLoadView: (filters: Record<string, unknown>) => void;
}

/* ─── Constants ─── */

const STORAGE_KEY = "vaap_saved_views";

/* ─── Helpers ─── */

function loadViews(): SavedView[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as SavedView[];
  } catch {
    return [];
  }
}

function persistViews(views: SavedView[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(views));
}

function generateId(): string {
  return `sv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

/* ─── Component ─── */

export default function SavedViews({ currentFilters, onLoadView }: SavedViewsProps) {
  const [views, setViews] = useState<SavedView[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [contextMenu, setContextMenu] = useState<{ viewId: string; x: number; y: number } | null>(null);
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const contextRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load from localStorage on mount
  useEffect(() => {
    setViews(loadViews());
  }, []);

  // Close context menu on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (contextRef.current && !contextRef.current.contains(e.target as Node)) {
        setContextMenu(null);
      }
    }
    if (contextMenu) {
      document.addEventListener("mousedown", handleClick);
      return () => document.removeEventListener("mousedown", handleClick);
    }
  }, [contextMenu]);

  // Focus input when form opens
  useEffect(() => {
    if (showForm && inputRef.current) {
      inputRef.current.focus();
    }
  }, [showForm]);

  const handleLoadView = useCallback(
    (view: SavedView) => {
      setActiveId(view.id);
      onLoadView(view.filters as Record<string, unknown>);
    },
    [onLoadView],
  );

  const handleSave = useCallback(() => {
    const trimmed = newName.trim();
    if (!trimmed) return;

    const sanitizedFilters: Record<string, string | number | boolean> = {};
    for (const [k, v] of Object.entries(currentFilters)) {
      if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
        sanitizedFilters[k] = v;
      }
    }

    const newView: SavedView = {
      id: generateId(),
      name: trimmed,
      filters: sanitizedFilters,
      createdAt: new Date().toISOString(),
    };

    const updated = [...views, newView];
    setViews(updated);
    persistViews(updated);
    setNewName("");
    setShowForm(false);
    setActiveId(newView.id);
  }, [newName, currentFilters, views]);

  const handleDelete = useCallback(
    (viewId: string) => {
      const updated = views.filter((v) => v.id !== viewId);
      setViews(updated);
      persistViews(updated);
      if (activeId === viewId) setActiveId(null);
      setContextMenu(null);
    },
    [views, activeId],
  );

  const handleContextMenu = useCallback((e: React.MouseEvent, viewId: string) => {
    e.preventDefault();
    setContextMenu({ viewId, x: e.clientX, y: e.clientY });
  }, []);

  const handleTouchStart = useCallback((viewId: string) => {
    longPressTimer.current = setTimeout(() => {
      setContextMenu({ viewId, x: 0, y: 0 });
    }, 600);
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        handleSave();
      } else if (e.key === "Escape") {
        setShowForm(false);
        setNewName("");
      }
    },
    [handleSave],
  );

  return (
    <div className="relative flex items-center gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {/* Saved view buttons */}
      {views.map((view) => (
        <button
          key={view.id}
          onClick={() => handleLoadView(view)}
          onContextMenu={(e) => handleContextMenu(e, view.id)}
          onTouchStart={() => handleTouchStart(view.id)}
          onTouchEnd={handleTouchEnd}
          onTouchCancel={handleTouchEnd}
          className={`shrink-0 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors whitespace-nowrap ${
            activeId === view.id
              ? "bg-[#EEF2FF] text-[#4A7DFF]"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          {view.name}
        </button>
      ))}

      {/* Add new view */}
      {showForm ? (
        <div className="flex items-center gap-1.5 shrink-0">
          <input
            ref={inputRef}
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="ビュー名を入力"
            className="w-32 px-2 py-1 text-[12px] border border-gray-300 rounded-lg focus:outline-none focus:border-[#4A7DFF] focus:ring-1 focus:ring-[#4A7DFF]/30"
          />
          <button
            onClick={handleSave}
            disabled={!newName.trim()}
            className="px-2 py-1 text-[11px] font-medium text-white bg-[#4A7DFF] rounded-lg hover:bg-[#3A6DEF] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            保存
          </button>
          <button
            onClick={() => {
              setShowForm(false);
              setNewName("");
            }}
            className="px-1.5 py-1 text-[11px] text-gray-500 hover:text-gray-700 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      ) : (
        <button
          onClick={() => setShowForm(true)}
          className="shrink-0 w-7 h-7 flex items-center justify-center rounded-lg bg-gray-100 text-gray-500 hover:bg-[#EEF2FF] hover:text-[#4A7DFF] transition-colors"
          title="現在のフィルターをビューとして保存"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
        </button>
      )}

      {/* Context menu (delete) */}
      {contextMenu && (
        <div
          ref={contextRef}
          className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[120px]"
          style={{
            top: contextMenu.y === 0 ? "50%" : contextMenu.y,
            left: contextMenu.x === 0 ? "50%" : contextMenu.x,
            transform: contextMenu.x === 0 && contextMenu.y === 0 ? "translate(-50%, -50%)" : undefined,
          }}
        >
          <button
            onClick={() => handleDelete(contextMenu.viewId)}
            className="w-full px-3 py-1.5 text-[12px] text-left text-red-600 hover:bg-red-50 transition-colors flex items-center gap-2"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
            </svg>
            削除
          </button>
        </div>
      )}
    </div>
  );
}
