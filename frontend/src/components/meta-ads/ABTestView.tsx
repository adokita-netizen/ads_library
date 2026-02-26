"use client";

import { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import type { ABTestExperiment } from "@/types";
import { metaMarketingApi } from "@/lib/api";
import ConfirmModal from "@/components/common/ConfirmModal";
import ABTestResultsPanel from "./ABTestResultsPanel";

interface Props {
  accountId: string;
}

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-600",
  running: "bg-green-50 text-green-700",
  completed: "bg-blue-50 text-blue-700",
  archived: "bg-gray-100 text-gray-500",
};

export default function ABTestView({ accountId }: Props) {
  const [experiments, setExperiments] = useState<ABTestExperiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  // Create form state
  const [newName, setNewName] = useState("");
  const [newHypothesis, setNewHypothesis] = useState("");
  const [newMetric, setNewMetric] = useState("ctr");
  const [creating, setCreating] = useState(false);

  const loadExperiments = useCallback(async () => {
    try {
      const res = await metaMarketingApi.listExperiments({ account_id: accountId });
      setExperiments(res.data?.experiments || []);
    } catch {
      setExperiments([]);
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    loadExperiments();
  }, [loadExperiments]);

  const [createError, setCreateError] = useState("");

  const handleCreate = async () => {
    if (!newName.trim()) {
      setCreateError("テスト名を入力してください");
      return;
    }
    if (newName.trim().length > 200) {
      setCreateError("テスト名は200文字以内で入力してください");
      return;
    }
    if (newHypothesis.length > 1000) {
      setCreateError("仮説は1000文字以内で入力してください");
      return;
    }
    setCreateError("");
    setCreating(true);
    try {
      await metaMarketingApi.createExperiment({
        account_id: accountId,
        name: newName.trim(),
        hypothesis: newHypothesis.trim() || undefined,
        primary_metric: newMetric,
        variants: [
          { name: "Control", description: "既存のクリエイティブ" },
          { name: "Variant A", description: "テストバリアント" },
        ],
      });
      setShowCreate(false);
      setNewName("");
      setNewHypothesis("");
      await loadExperiments();
      toast.success("実験を作成しました");
    } catch (err) {
      console.error("Failed to create experiment:", err);
      toast.error("実験の作成に失敗しました");
    } finally {
      setCreating(false);
    }
  };

  const [completeTarget, setCompleteTarget] = useState<number | null>(null);

  const handleComplete = async (experimentId: number) => {
    setCompleteTarget(null);
    try {
      await metaMarketingApi.completeExperiment(experimentId);
      await loadExperiments();
      toast.success("実験を完了しました");
    } catch (err) {
      console.error("Failed to complete experiment:", err);
      toast.error("実験の完了に失敗しました");
    }
  };

  if (loading) {
    return <div className="text-center py-8 text-[12px] text-gray-400">読み込み中...</div>;
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-[13px] font-bold text-gray-800">A/Bテスト ({experiments.length})</h3>
        <button onClick={() => setShowCreate(!showCreate)} className="btn-primary text-[11px] px-3 py-1">
          新規テスト
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="card p-4 space-y-3">
          <div>
            <label htmlFor="ab-test-name" className="sr-only">テスト名</label>
            <input
              id="ab-test-name"
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="テスト名"
              maxLength={200}
              aria-required="true"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[12px]"
            />
          </div>
          <div>
            <label htmlFor="ab-test-hypothesis" className="sr-only">仮説</label>
            <textarea
              id="ab-test-hypothesis"
              value={newHypothesis}
              onChange={(e) => setNewHypothesis(e.target.value)}
              placeholder="仮説（例：動画冒頭に質問形式を使うとCTRが向上する）"
              maxLength={1000}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[12px] h-16 resize-none"
            />
          </div>
          <div className="flex items-center gap-3">
            <label htmlFor="ab-test-metric" className="text-[11px] text-gray-600">主要指標:</label>
            <select
              id="ab-test-metric"
              value={newMetric}
              onChange={(e) => setNewMetric(e.target.value)}
              className="border border-gray-200 rounded-lg px-2 py-1 text-[12px]"
            >
              <option value="ctr">CTR</option>
              <option value="cvr">CVR</option>
              <option value="cpa">CPA</option>
            </select>
          </div>
          {createError && (
            <p className="text-[11px] text-red-600 bg-red-50 rounded-lg px-3 py-1.5">{createError}</p>
          )}
          <div className="flex gap-2">
            <button onClick={handleCreate} disabled={creating || !newName.trim()} className="btn-primary text-[11px] px-3 py-1 disabled:opacity-50">
              {creating ? "作成中..." : "作成"}
            </button>
            <button onClick={() => setShowCreate(false)} className="btn-secondary text-[11px] px-3 py-1">
              キャンセル
            </button>
          </div>
        </div>
      )}

      {/* Experiment list */}
      {experiments.length === 0 ? (
        <div className="text-center py-12 text-[13px] text-gray-400">
          A/Bテストがありません。「新規テスト」から作成してください。
        </div>
      ) : (
        <div className="space-y-3">
          {experiments.map((exp) => (
            <div key={exp.id} className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <h4 className="text-[13px] font-medium text-gray-800">{exp.name}</h4>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded ${STATUS_COLORS[exp.status] || "bg-gray-100"}`}>
                    {exp.status}
                  </span>
                </div>
                <div className="flex gap-2">
                  {exp.status === "running" && (
                    <button
                      onClick={() => setCompleteTarget(exp.id)}
                      className="text-[11px] text-blue-500 hover:underline"
                    >
                      完了判定
                    </button>
                  )}
                </div>
              </div>

              {exp.hypothesis && (
                <p className="text-[11px] text-gray-500 mb-2">仮説: {exp.hypothesis}</p>
              )}

              {/* Variants */}
              {exp.variants && exp.variants.length > 0 && (
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {exp.variants.map((v) => (
                    <div
                      key={v.id}
                      className={`rounded-lg p-2 border ${v.is_winner ? "border-green-300 bg-green-50" : "border-gray-100"}`}
                    >
                      <div className="flex items-center gap-1 mb-1">
                        <span className="text-[11px] font-medium text-gray-700">{v.name}</span>
                        {v.is_winner && (
                          <span className="text-[9px] bg-green-500 text-white px-1 py-0.5 rounded">勝者</span>
                        )}
                        <span className="text-[9px] text-gray-400">({v.variant_type})</span>
                      </div>
                      <div className="grid grid-cols-3 gap-1 text-center">
                        <div>
                          <p className="text-[9px] text-gray-500">IMP</p>
                          <p className="text-[11px] font-medium">{(v.impressions || 0).toLocaleString()}</p>
                        </div>
                        <div>
                          <p className="text-[9px] text-gray-500">CTR</p>
                          <p className="text-[11px] font-medium">{(v.ctr || 0).toFixed(2)}%</p>
                        </div>
                        <div>
                          <p className="text-[9px] text-gray-500">消化額</p>
                          <p className="text-[11px] font-medium">¥{Math.round(v.spend || 0).toLocaleString()}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Detailed results panel */}
              {(exp.status === "running" || exp.status === "completed") && exp.variants.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-100">
                  <ABTestResultsPanel experiment={exp} onMetricsUpdated={loadExperiments} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {completeTarget !== null && (
        <ConfirmModal
          title="実験の完了"
          message="この実験を完了してもよろしいですか？統計的有意性を判定し、勝者を決定します。"
          confirmLabel="完了する"
          variant="info"
          onConfirm={() => handleComplete(completeTarget)}
          onCancel={() => setCompleteTarget(null)}
        />
      )}
    </div>
  );
}
