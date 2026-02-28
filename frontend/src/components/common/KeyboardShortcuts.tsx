"use client";

import { useState, useEffect, useCallback } from "react";

interface KeyboardShortcutsProps {
  onToggleSearch?: () => void;
  onNavigate?: (direction: "up" | "down") => void;
  onSelectAd?: () => void;
  onBookmark?: () => void;
}

interface ShortcutDef {
  keys: string[];
  label: string;
}

const SHORTCUTS: ShortcutDef[] = [
  { keys: ["Ctrl", "K"], label: "検索を開く/閉じる" },
  { keys: ["Ctrl", "/"], label: "ショートカット一覧を表示" },
  { keys: ["J"], label: "次の広告へ移動" },
  { keys: ["K"], label: "前の広告へ移動" },
  { keys: ["Enter"], label: "広告を選択" },
  { keys: ["B"], label: "ブックマークに追加" },
  { keys: ["Esc"], label: "閉じる" },
];

export default function KeyboardShortcuts({
  onToggleSearch,
  onNavigate,
  onSelectAd,
  onBookmark,
}: KeyboardShortcutsProps) {
  const [showHelp, setShowHelp] = useState(false);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable;

      // Ctrl+K — toggle search
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        onToggleSearch?.();
        return;
      }

      // Ctrl+/ — show help
      if ((e.ctrlKey || e.metaKey) && e.key === "/") {
        e.preventDefault();
        setShowHelp((v) => !v);
        return;
      }

      // Esc — close help
      if (e.key === "Escape") {
        if (showHelp) {
          setShowHelp(false);
        }
        return;
      }

      // Skip single-key shortcuts when focused on input
      if (isInput) return;

      // j — navigate down
      if (e.key === "j") {
        onNavigate?.("down");
        return;
      }

      // k — navigate up
      if (e.key === "k") {
        onNavigate?.("up");
        return;
      }

      // Enter — select ad
      if (e.key === "Enter") {
        onSelectAd?.();
        return;
      }

      // b — bookmark
      if (e.key === "b") {
        onBookmark?.();
        return;
      }
    },
    [onToggleSearch, onNavigate, onSelectAd, onBookmark, showHelp]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  if (!showHelp) return null;

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={() => setShowHelp(false)}
    >
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-sm p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-[14px] font-bold text-gray-900">キーボードショートカット</h3>
          <button
            onClick={() => setShowHelp(false)}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="space-y-2">
          {SHORTCUTS.map((shortcut, i) => (
            <div key={i} className="flex items-center justify-between py-1.5">
              <span className="text-[11px] text-gray-600">{shortcut.label}</span>
              <div className="flex items-center gap-1">
                {shortcut.keys.map((key, ki) => (
                  <kbd
                    key={ki}
                    className="inline-flex items-center justify-center min-w-[24px] h-6 px-1.5 text-[10px] font-mono font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded shadow-sm"
                  >
                    {key}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 pt-3 border-t border-gray-100">
          <p className="text-[10px] text-gray-400 text-center">
            Ctrl+/ で表示/非表示を切り替え
          </p>
        </div>
      </div>
    </div>
  );
}
