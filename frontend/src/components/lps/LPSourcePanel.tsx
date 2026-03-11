"use client";

import { useState, useMemo, useCallback, useRef, useEffect } from "react";

interface LPSourcePanelProps {
  sourceHtml: string;
}

function highlightHtml(line: string): JSX.Element {
  // Simple regex-based HTML syntax highlighting
  const parts: JSX.Element[] = [];
  let remaining = line;
  let key = 0;

  const tagRegex = /(<\/?)([\w-]+)((?:\s+[\w-]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*))?)*\s*)(\/?>)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tagRegex.exec(remaining)) !== null) {
    // Text before tag
    if (match.index > lastIndex) {
      parts.push(<span key={key++}>{remaining.slice(lastIndex, match.index)}</span>);
    }

    const [, bracket, tagName, attrs, closeBracket] = match;

    // Highlight attributes
    const attrParts: JSX.Element[] = [];
    const attrRegex = /([\w-]+)(\s*=\s*)((?:"[^"]*"|'[^']*'|[^\s>]*))/g;
    let attrMatch: RegExpExecArray | null;
    let attrLastIndex = 0;
    while ((attrMatch = attrRegex.exec(attrs)) !== null) {
      if (attrMatch.index > attrLastIndex) {
        attrParts.push(<span key={key++}>{attrs.slice(attrLastIndex, attrMatch.index)}</span>);
      }
      attrParts.push(
        <span key={key++}>
          <span className="text-orange-400">{attrMatch[1]}</span>
          <span>{attrMatch[2]}</span>
          <span className="text-green-400">{attrMatch[3]}</span>
        </span>
      );
      attrLastIndex = attrMatch.index + attrMatch[0].length;
    }
    if (attrLastIndex < attrs.length) {
      attrParts.push(<span key={key++}>{attrs.slice(attrLastIndex)}</span>);
    }

    parts.push(
      <span key={key++}>
        <span className="text-gray-400">{bracket}</span>
        <span className="text-blue-400">{tagName}</span>
        {attrParts}
        <span className="text-gray-400">{closeBracket}</span>
      </span>
    );

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < remaining.length) {
    parts.push(<span key={key++}>{remaining.slice(lastIndex)}</span>);
  }

  return <>{parts}</>;
}

export default function LPSourcePanel({ sourceHtml }: LPSourcePanelProps) {
  const [copied, setCopied] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchVisible, setSearchVisible] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const lines = useMemo(() => sourceHtml.split("\n"), [sourceHtml]);

  const matchingLines = useMemo(() => {
    if (!searchQuery.trim()) return new Set<number>();
    const q = searchQuery.toLowerCase();
    const matches = new Set<number>();
    lines.forEach((line, i) => {
      if (line.toLowerCase().includes(q)) matches.add(i);
    });
    return matches;
  }, [lines, searchQuery]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(sourceHtml);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const ta = document.createElement("textarea");
      ta.value = sourceHtml;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [sourceHtml]);

  const toggleSearch = useCallback(() => {
    setSearchVisible((prev) => {
      if (!prev) {
        setTimeout(() => searchInputRef.current?.focus(), 100);
      } else {
        setSearchQuery("");
      }
      return !prev;
    });
  }, []);

  // Keyboard shortcut: Ctrl+F for search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "f") {
        // Only intercept if focus is within our component
        const panel = document.getElementById("lp-source-panel");
        if (panel?.contains(document.activeElement) || panel === document.activeElement) {
          e.preventDefault();
          toggleSearch();
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [toggleSearch]);

  return (
    <div id="lp-source-panel" className="flex flex-col h-full" tabIndex={-1}>
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shrink-0">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 border border-gray-200 dark:border-gray-700 transition-colors"
        >
          <svg className={`w-3.5 h-3.5 transition-transform ${collapsed ? "" : "rotate-90"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          {collapsed ? "展開" : "折りたたむ"}
        </button>

        <button
          onClick={toggleSearch}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors border ${
            searchVisible
              ? "border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400"
              : "border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
          }`}
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          検索
        </button>

        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 border border-gray-200 dark:border-gray-700 transition-colors"
        >
          {copied ? (
            <>
              <svg className="w-3.5 h-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
              コピー済み
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
              </svg>
              コピー
            </>
          )}
        </button>

        <span className="ml-auto text-[10px] text-gray-400 dark:text-gray-500">
          {lines.length} 行
          {matchingLines.size > 0 && ` / ${matchingLines.size} 件マッチ`}
        </span>
      </div>

      {/* Search bar */}
      {searchVisible && (
        <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 shrink-0">
          <svg className="w-4 h-4 text-gray-400 dark:text-gray-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            ref={searchInputRef}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="ソース内を検索..."
            className="flex-1 bg-transparent text-[12px] text-gray-700 dark:text-gray-200 placeholder:text-gray-400 dark:placeholder:text-gray-500 outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="p-0.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      )}

      {/* Source code display */}
      {!collapsed && (
        <div className="flex-1 overflow-auto bg-gray-900 dark:bg-gray-950">
          <pre className="text-[12px] leading-5 font-mono">
            {lines.map((line, i) => {
              const isMatch = matchingLines.has(i);
              return (
                <div
                  key={i}
                  className={`flex ${
                    isMatch
                      ? "bg-yellow-900/30 border-l-2 border-yellow-400"
                      : "border-l-2 border-transparent hover:bg-gray-800/50"
                  }`}
                >
                  <span className="w-12 shrink-0 text-right pr-3 py-px text-gray-500 dark:text-gray-600 select-none">
                    {i + 1}
                  </span>
                  <code className="flex-1 py-px pr-4 text-gray-200 whitespace-pre-wrap break-all">
                    {highlightHtml(line)}
                  </code>
                </div>
              );
            })}
          </pre>
        </div>
      )}

      {collapsed && (
        <div className="flex-1 flex items-center justify-center bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-500 text-[12px]">
          ソースコードは折りたたまれています。「展開」をクリックして表示。
        </div>
      )}
    </div>
  );
}
