"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";

// ─── Types ───

interface SavedScenario {
  id: number;
  name: string;
  genre: string;
  archetype: string;
  predicted_score: number;
  created_at: string;
  platform: string;
  product_name: string;
}

// ─── Mock Data (TODO: Replace with API calls when endpoints are ready) ───

const MOCK_SAVED_SCENARIOS: SavedScenario[] = [
  { id: 1, name: "美容液LP向け 感情訴求型", genre: "beauty", archetype: "Before/After変身型", predicted_score: 82, created_at: "2026-02-25T10:30:00Z", platform: "instagram", product_name: "○○美容液" },
  { id: 2, name: "ダイエットサプリ 問題解決型", genre: "health", archetype: "問題解決型", predicted_score: 75, created_at: "2026-02-24T14:00:00Z", platform: "facebook", product_name: "△△サプリ" },
  { id: 3, name: "英会話アプリ ストーリー型", genre: "education", archetype: "ストーリーテリング型", predicted_score: 68, created_at: "2026-02-23T09:15:00Z", platform: "tiktok", product_name: "□□英会話" },
  { id: 4, name: "EC限定セール 緊急性型", genre: "ec_d2c", archetype: "緊急性・限定型", predicted_score: 71, created_at: "2026-02-22T16:45:00Z", platform: "facebook", product_name: "EC商品" },
  { id: 5, name: "金融サービス 権威型", genre: "finance", archetype: "権威・専門家型", predicted_score: 60, created_at: "2026-02-21T11:20:00Z", platform: "instagram", product_name: "投資サービス" },
];

// ─── Helpers ───

const genreLabel = (value: string) => genreOptions.find((g) => g.value === value)?.label || value;

const formatDate = (dateStr: string) => {
  const d = new Date(dateStr);
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}`;
};

// ─── Main Component ───

interface SavedScenariosProps {
  onLoad?: (scenarioId: number) => void;
}

export default function SavedScenarios({ onLoad }: SavedScenariosProps) {
  const [scenarios, setScenarios] = useState<SavedScenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState("");
  const [filterGenre, setFilterGenre] = useState("all");
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const fetchScenarios = useCallback(async () => {
    setLoading(true);
    try {
      // TODO: Replace with actual API call when endpoint is ready
      // const data = await fetchApi<{ items: SavedScenario[] }>("/rankings/saved-scenarios");
      // setScenarios(data.items || []);
      await new Promise((r) => setTimeout(r, 500));
      setScenarios(MOCK_SAVED_SCENARIOS);
    } catch (err) {
      console.error("保存済みシナリオの取得に失敗しました", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScenarios();
  }, [fetchScenarios]);

  const handleDelete = async (id: number) => {
    try {
      // TODO: Replace with actual API call when endpoint is ready
      // await fetchApi(`/rankings/saved-scenarios/${id}`, { method: "DELETE" });
      setScenarios((prev) => prev.filter((s) => s.id !== id));
      setDeleteConfirm(null);
    } catch (err) {
      console.error("削除に失敗しました", err);
    }
  };

  const filtered = scenarios.filter((s) => {
    if (filterGenre !== "all" && s.genre !== filterGenre) return false;
    if (searchText && !s.name.toLowerCase().includes(searchText.toLowerCase()) && !s.product_name.toLowerCase().includes(searchText.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-100">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[14px] font-bold text-gray-900">保存済みシナリオ</h3>
          <span className="text-[11px] text-gray-400">{scenarios.length}件</span>
        </div>
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="シナリオ名で検索..."
              className="w-full pl-8 pr-3 py-1.5 text-[12px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30"
            />
          </div>
          <select
            value={filterGenre}
            onChange={(e) => setFilterGenre(e.target.value)}
            className="px-3 py-1.5 text-[12px] border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/30"
          >
            {genreOptions.map((g) => (
              <option key={g.value} value={g.value}>{g.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* List */}
      <div className="divide-y divide-gray-50 max-h-[400px] overflow-auto custom-scrollbar">
        {loading ? (
          <div className="p-8 text-center">
            <div className="w-6 h-6 border-2 border-[#4A7DFF] border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-[12px] text-gray-400">読み込み中...</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center">
            <p className="text-[12px] text-gray-400">保存済みシナリオがありません</p>
          </div>
        ) : (
          filtered.map((scenario) => (
            <div key={scenario.id} className="px-4 py-3 hover:bg-gray-50 transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[13px] font-medium text-gray-900 truncate">{scenario.name}</span>
                    <span className={`shrink-0 px-1.5 py-0.5 rounded text-[9px] font-bold ${
                      scenario.predicted_score >= 80 ? "bg-green-100 text-green-700" :
                      scenario.predicted_score >= 60 ? "bg-yellow-100 text-yellow-700" :
                      "bg-gray-100 text-gray-600"
                    }`}>
                      {scenario.predicted_score}点
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-gray-400">
                    <span className="px-1.5 py-0.5 bg-gray-100 rounded">{genreLabel(scenario.genre)}</span>
                    <span className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">{scenario.archetype}</span>
                    <span className="uppercase">{scenario.platform}</span>
                    <span>{formatDate(scenario.created_at)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0 ml-3">
                  {onLoad && (
                    <button
                      onClick={() => onLoad(scenario.id)}
                      className="p-1.5 text-gray-400 hover:text-[#4A7DFF] transition-colors"
                      title="読み込む"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                      </svg>
                    </button>
                  )}
                  {deleteConfirm === scenario.id ? (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handleDelete(scenario.id)}
                        className="px-2 py-1 text-[10px] font-medium text-white bg-red-500 rounded hover:bg-red-600"
                      >
                        削除
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(null)}
                        className="px-2 py-1 text-[10px] font-medium text-gray-600 bg-gray-100 rounded"
                      >
                        取消
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setDeleteConfirm(scenario.id)}
                      className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                      title="削除"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
