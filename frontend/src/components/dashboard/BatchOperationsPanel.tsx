"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface OperationHistory {
  name: string;
  timestamp: string;
  result: string;
}

const OPERATIONS = [
  {
    id: "batch-extract",
    name: "メディア一括抽出",
    description: "pending広告のメディアをPlaywrightで一括抽出",
    api: "/rankings/batch-extract-media",
    method: "POST",
    paramLabel: "件数上限",
    paramKey: "limit",
    paramDefault: 50,
    color: "bg-blue-500",
  },
  {
    id: "retry-failed",
    name: "失敗を再試行",
    description: "失敗した抽出をリセットして再実行",
    api: "/rankings/retry-failed-media",
    method: "POST",
    paramLabel: "件数上限",
    paramKey: "limit",
    paramDefault: 20,
    color: "bg-red-500",
  },
  {
    id: "compute-rankings",
    name: "スコア再計算",
    description: "全広告のヒットスコアを再計算",
    api: "/rankings/compute",
    method: "POST",
    paramLabel: "",
    paramKey: "",
    paramDefault: 0,
    color: "bg-purple-500",
  },
  {
    id: "data-health",
    name: "データヘルスチェック",
    description: "DB品質サマリーを取得",
    api: "/rankings/data-health",
    method: "GET",
    paramLabel: "",
    paramKey: "",
    paramDefault: 0,
    color: "bg-green-500",
  },
] as const;

export default function BatchOperationsPanel() {
  const [loadingOp, setLoadingOp] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, string>>({});
  const [params, setParams] = useState<Record<string, number>>({
    "batch-extract": 50,
    "retry-failed": 20,
  });
  const [history, setHistory] = useState<OperationHistory[]>([]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("vaap-batch-history");
      if (saved) setHistory(JSON.parse(saved));
    } catch {
      /* ignore */
    }
  }, []);

  const addHistory = (name: string, result: string) => {
    const entry: OperationHistory = {
      name,
      timestamp: new Date().toLocaleString("ja-JP"),
      result,
    };
    const updated = [entry, ...history].slice(0, 20);
    setHistory(updated);
    try {
      localStorage.setItem("vaap-batch-history", JSON.stringify(updated));
    } catch {
      /* ignore */
    }
  };

  const handleExecute = async (op: typeof OPERATIONS[number]) => {
    if (!confirm(`「${op.name}」を実行しますか？`)) return;
    setLoadingOp(op.id);
    setResults((prev) => ({ ...prev, [op.id]: "" }));
    try {
      const fetchOptions: { method?: string; params?: Record<string, string> } = {};
      if (op.method !== "GET") fetchOptions.method = op.method;
      if (op.paramKey && params[op.id]) {
        fetchOptions.params = { [op.paramKey]: String(params[op.id]) };
      }
      const result = await fetchApi<Record<string, unknown>>(op.api, fetchOptions);
      const summary = JSON.stringify(result, null, 0).slice(0, 200);
      setResults((prev) => ({ ...prev, [op.id]: summary }));
      addHistory(op.name, summary);
    } catch (e) {
      const errMsg = `Error: ${String(e)}`;
      setResults((prev) => ({ ...prev, [op.id]: errMsg }));
      addHistory(op.name, errMsg);
    } finally {
      setLoadingOp(null);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center px-5 py-3 border-b border-gray-200 bg-white">
        <h2 className="text-[15px] font-bold text-gray-900">管理ツール</h2>
        <p className="text-[11px] text-gray-400 ml-3">バッチ操作と管理機能</p>
      </div>

      <div className="flex-1 overflow-auto custom-scrollbar p-5 space-y-6">
        {/* Operation Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {OPERATIONS.map((op) => (
            <div key={op.id} className="bg-white rounded-lg shadow-sm border border-gray-100 p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="text-[13px] font-bold text-gray-900">{op.name}</h3>
                  <p className="text-[11px] text-gray-400 mt-0.5">{op.description}</p>
                </div>
                <div className={`w-2 h-2 rounded-full ${op.color}`} />
              </div>

              {op.paramLabel && (
                <div className="mb-3">
                  <label className="text-[11px] text-gray-500 block mb-1">{op.paramLabel}</label>
                  <input
                    type="number"
                    value={params[op.id] || op.paramDefault}
                    onChange={(e) => setParams((prev) => ({ ...prev, [op.id]: Number(e.target.value) }))}
                    className="w-24 px-2 py-1 border border-gray-200 rounded text-[12px] text-gray-700"
                    min={1}
                    max={200}
                  />
                </div>
              )}

              <button
                onClick={() => handleExecute(op)}
                disabled={!!loadingOp}
                className={`w-full px-3 py-1.5 text-white text-[12px] font-medium rounded-lg disabled:opacity-50 transition-colors ${op.color} hover:opacity-90`}
              >
                {loadingOp === op.id ? "実行中..." : "実行"}
              </button>

              {results[op.id] && (
                <div className="mt-2 px-2 py-1.5 bg-gray-50 rounded text-[10px] text-gray-600 break-all max-h-20 overflow-auto">
                  {results[op.id]}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Execution History */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-100 p-4">
          <h3 className="text-[13px] font-bold text-gray-900 mb-3">実行履歴</h3>
          {history.length === 0 ? (
            <p className="text-[11px] text-gray-400">実行履歴はありません</p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-auto">
              {history.map((h, i) => (
                <div key={i} className="flex items-start gap-3 text-[11px] border-b border-gray-50 pb-2">
                  <span className="text-gray-400 shrink-0 w-32">{h.timestamp}</span>
                  <span className="font-medium text-gray-700 shrink-0 w-28">{h.name}</span>
                  <span className="text-gray-500 truncate">{h.result}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
