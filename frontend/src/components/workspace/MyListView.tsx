"use client";

import { useState, useEffect } from "react";
import { notificationsApi } from "@/lib/api";

type FilterType = "all" | "ad" | "lp" | "creative" | "advertiser";


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
  const [savedItems, setSavedItems] = useState<Array<{ id: number; type: string; label: string; notes: string; folder: string; createdAt: string }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSaved = async () => {
      try {
        const response = await notificationsApi.listSaved();
        const items = response.data?.items || response.data?.results || response.data;
        if (Array.isArray(items)) {
          const mapped = items.map((item: Record<string, unknown>) => ({
            id: (item.id as number) || 0,
            type: (item.item_type as string) || "ad",
            label: (item.label as string) || "",
            notes: (item.notes as string) || "",
            folder: (item.folder as string) || "",
            createdAt: (item.created_at as string) || "",
          }));
          setSavedItems(mapped);
        }
      } catch (error) {
        console.error("Failed to fetch saved items:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchSaved();
  }, []);

  const handleRemoveSaved = async (id: number) => {
    try {
      await notificationsApi.removeSaved(id);
      setSavedItems((prev) => prev.filter((item) => item.id !== id));
    } catch (error) {
      console.warn("Failed to remove saved item:", error);
    }
  };

  const filtered = filter === "all" ? savedItems : savedItems.filter((s) => s.type === filter);
  const folders = Array.from(new Set(savedItems.map((s) => s.folder).filter(Boolean)));

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">マイリスト</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">保存した広告・LP・クリエイティブを管理</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-gray-400">
            {loading ? "読み込み中..." : `${savedItems.length}件保存`}
          </span>
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
        {!loading && filtered.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-xs">保存済みアイテムがありません</p>
            <p className="text-[10px] mt-1">広告やLPの詳細画面から「マイリストに追加」で保存できます</p>
          </div>
        )}
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
              <button
                className="text-gray-300 hover:text-red-400 transition-colors shrink-0"
                onClick={(e) => { e.stopPropagation(); handleRemoveSaved(item.id); }}
              >
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
