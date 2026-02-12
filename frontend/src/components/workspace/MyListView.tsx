"use client";

import { useState } from "react";

type FilterType = "all" | "ad" | "lp" | "creative" | "advertiser";

const mockSaved = [
  { id: 1, type: "ad", label: "セラムV3 動画広告 #1", notes: "ベネフィット訴求が強い", folder: "競合分析", createdAt: "2025-12-22" },
  { id: 2, type: "lp", label: "ダイエットX 記事LP", notes: "記事構成が参考になる", folder: "LP参考", createdAt: "2025-12-21" },
  { id: 3, type: "ad", label: "育毛トニック YouTube 15s", notes: "フックが秀逸", folder: "競合分析", createdAt: "2025-12-20" },
  { id: 4, type: "creative", label: "AI生成台本 - セラム権威性ver", notes: "", folder: "自社制作", createdAt: "2025-12-19" },
  { id: 5, type: "advertiser", label: "ビューティーラボ", notes: "主要競合 - 月次チェック", folder: "競合分析", createdAt: "2025-12-18" },
  { id: 6, type: "lp", label: "アイクリーム 口コミLP", notes: "口コミ構成が参考", folder: "LP参考", createdAt: "2025-12-17" },
];

const typeLabels: Record<string, string> = {
  ad: "広告",
  lp: "LP",
  creative: "クリエイティブ",
  advertiser: "広告主",
};

const typeColors: Record<string, string> = {
  ad: "bg-blue-100 text-blue-700",
  lp: "bg-purple-100 text-purple-700",
  creative: "bg-emerald-100 text-emerald-700",
  advertiser: "bg-amber-100 text-amber-700",
};

export default function MyListView() {
  const [filter, setFilter] = useState<FilterType>("all");

  const filtered = filter === "all" ? mockSaved : mockSaved.filter((s) => s.type === filter);
  const folders = [...new Set(mockSaved.map((s) => s.folder).filter(Boolean))];

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">マイリスト</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">保存した広告・LP・クリエイティブを管理</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-gray-400">{mockSaved.length}件保存</span>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2 px-5 py-2 border-b border-gray-200 bg-[#f8f9fc]">
        {([
          { id: "all" as FilterType, label: "すべて" },
          { id: "ad" as FilterType, label: "広告" },
          { id: "lp" as FilterType, label: "LP" },
          { id: "creative" as FilterType, label: "クリエイティブ" },
          { id: "advertiser" as FilterType, label: "広告主" },
        ]).map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={`px-3 py-1 rounded text-[11px] font-medium transition-colors ${
              filter === f.id
                ? "bg-[#4A7DFF] text-white"
                : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-200"
            }`}
          >
            {f.label}
          </button>
        ))}

        <div className="ml-auto flex items-center gap-2">
          {folders.map((f) => (
            <span key={f} className="text-[9px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
              📁 {f}
            </span>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-2">
        {filtered.map((item) => (
          <div key={item.id} className="card hover:shadow-md transition-shadow cursor-pointer">
            <div className="flex items-center gap-3">
              <span className={`badge text-[9px] ${typeColors[item.type]}`}>
                {typeLabels[item.type]}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-medium text-gray-900 truncate">{item.label}</p>
                {item.notes && (
                  <p className="text-[10px] text-gray-400 truncate">{item.notes}</p>
                )}
              </div>
              {item.folder && (
                <span className="text-[9px] text-gray-400 bg-gray-50 px-2 py-0.5 rounded">
                  {item.folder}
                </span>
              )}
              <span className="text-[10px] text-gray-400 shrink-0">{item.createdAt}</span>
              <button className="text-gray-300 hover:text-red-400 transition-colors shrink-0">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                </svg>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
