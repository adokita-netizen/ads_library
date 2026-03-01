"use client";

import React, { useState, useEffect } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { copyToClipboard } from "@/lib/format";

interface ReportViewerProps {
  reportId: string | number;
  format: string;
  onBack: () => void;
}

export default function ReportViewer({ reportId, format, onBack }: ReportViewerProps) {
  const [content, setContent] = useState<string | null>(null);
  const [jsonData, setJsonData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());

  useEffect(() => {
    setLoading(true);
    fetchApi<Record<string, unknown>>(`/rankings/reports/${reportId}`)
      .then((res) => {
        if (format === "html") {
          setContent(typeof res === "string" ? res : String(res?.html || res?.content || JSON.stringify(res)));
        } else {
          setJsonData(res);
        }
      })
      .catch(() => {
        toast.error("レポートの読み込みに失敗しました");
      })
      .finally(() => setLoading(false));
  }, [reportId, format]);

  const handlePrint = () => window.print();

  const handleShare = () => {
    const url = `${window.location.origin}/api/v1/rankings/reports/${reportId}`;
    copyToClipboard(url).then(() => toast.success("リンクをコピーしました"));
  };

  const toggleKey = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="flex gap-2">
          <div className="h-7 bg-gray-200 rounded w-20" />
          <div className="h-7 bg-gray-200 rounded w-20" />
        </div>
        <div className="h-96 bg-gray-100 rounded-lg" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={onBack}
          className="text-[11px] px-2 py-1 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors flex items-center gap-1"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          戻る
        </button>
        <button
          onClick={handlePrint}
          className="text-[11px] px-3 py-1 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors flex items-center gap-1"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5zm-3 0h.008v.008H15V10.5z" />
          </svg>
          印刷
        </button>
        <button
          onClick={handleShare}
          className="text-[11px] px-3 py-1 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors flex items-center gap-1"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" />
          </svg>
          共有
        </button>
        <button
          className="text-[11px] px-3 py-1 rounded-lg bg-emerald-50 text-emerald-600 hover:bg-emerald-100 transition-colors flex items-center gap-1"
          onClick={() => window.open(`/api/v1/rankings/reports/${reportId}/download`, "_blank", "noopener,noreferrer")}
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          ダウンロード
        </button>
      </div>

      {/* Content */}
      {format === "html" && content ? (
        <div className="card overflow-hidden">
          <iframe
            srcDoc={content}
            className="w-full border-0"
            style={{ minHeight: "600px" }}
            title="Report"
            sandbox="allow-same-origin"
          />
        </div>
      ) : jsonData ? (
        <div className="card px-4 py-3">
          <JsonViewer data={jsonData} path="" expandedKeys={expandedKeys} onToggle={toggleKey} />
        </div>
      ) : (
        <div className="card px-4 py-8 text-center">
          <p className="text-[11px] text-gray-400">レポートコンテンツがありません</p>
        </div>
      )}
    </div>
  );
}

/* ─── JSON Viewer helper ─── */

function JsonViewer({ data, path, expandedKeys, onToggle }: {
  data: any;
  path: string;
  expandedKeys: Set<string>;
  onToggle: (key: string) => void;
}) {
  if (data === null || data === undefined) {
    return <span className="text-[10px] text-gray-400">null</span>;
  }

  if (typeof data === "boolean") {
    return <span className="text-[10px] text-purple-600">{data ? "true" : "false"}</span>;
  }

  if (typeof data === "number") {
    return <span className="text-[10px] text-blue-600">{data}</span>;
  }

  if (typeof data === "string") {
    return <span className="text-[10px] text-emerald-700">&quot;{data}&quot;</span>;
  }

  if (Array.isArray(data)) {
    const isExpanded = expandedKeys.has(path);
    if (data.length === 0) return <span className="text-[10px] text-gray-400">[]</span>;
    return (
      <div>
        <button onClick={() => onToggle(path)} className="text-[10px] text-gray-500 hover:text-gray-700">
          {isExpanded ? "▼" : "▶"} Array[{data.length}]
        </button>
        {isExpanded && (
          <div className="ml-3 border-l border-gray-200 pl-2 space-y-0.5">
            {data.map((item, i) => (
              <div key={i}>
                <span className="text-[9px] text-gray-400">{i}: </span>
                <JsonViewer data={item} path={`${path}[${i}]`} expandedKeys={expandedKeys} onToggle={onToggle} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (typeof data === "object") {
    const keys = Object.keys(data);
    const isExpanded = expandedKeys.has(path);
    if (keys.length === 0) return <span className="text-[10px] text-gray-400">{"{}"}</span>;
    return (
      <div>
        <button onClick={() => onToggle(path)} className="text-[10px] text-gray-500 hover:text-gray-700">
          {isExpanded ? "▼" : "▶"} Object{`{${keys.length}}`}
        </button>
        {isExpanded && (
          <div className="ml-3 border-l border-gray-200 pl-2 space-y-0.5">
            {keys.map((key) => (
              <div key={key}>
                <span className="text-[9px] font-medium text-gray-700">{key}: </span>
                <JsonViewer data={data[key]} path={`${path}.${key}`} expandedKeys={expandedKeys} onToggle={onToggle} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return <span className="text-[10px] text-gray-500">{String(data)}</span>;
}
