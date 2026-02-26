"use client";

import { useState, useEffect } from "react";
import { metaMarketingApi } from "@/lib/api";

const OBJECTIVES = [
  { value: "OUTCOME_TRAFFIC", label: "トラフィック" },
  { value: "OUTCOME_ENGAGEMENT", label: "エンゲージメント" },
  { value: "OUTCOME_LEADS", label: "リード" },
  { value: "OUTCOME_SALES", label: "売上" },
  { value: "OUTCOME_APP_PROMOTION", label: "アプリ宣伝" },
  { value: "OUTCOME_AWARENESS", label: "認知度" },
];

interface Props {
  accountId: string;
  onClose: () => void;
  onCreated: () => void;
}

export default function CreateCampaignModal({ accountId, onClose, onCreated }: Props) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const [name, setName] = useState("");
  const [objective, setObjective] = useState("OUTCOME_TRAFFIC");
  const [budgetType, setBudgetType] = useState<"daily" | "lifetime">("daily");
  const [budget, setBudget] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("キャンペーン名を入力してください");
      return;
    }
    if (name.trim().length > 400) {
      setError("キャンペーン名は400文字以内で入力してください");
      return;
    }
    if (budget) {
      const budgetNum = parseFloat(budget);
      if (isNaN(budgetNum) || budgetNum <= 0) {
        setError("予算は正の数値を入力してください");
        return;
      }
      if (budgetNum < 100) {
        setError("予算は最低100円以上で設定してください");
        return;
      }
    }

    setCreating(true);
    setError("");

    try {
      const budgetCents = budget ? Math.round(parseFloat(budget) * 100) : undefined;
      await metaMarketingApi.createCampaign({
        account_id: accountId,
        name: name.trim(),
        objective,
        ...(budgetType === "daily" && budgetCents ? { daily_budget: budgetCents } : {}),
        ...(budgetType === "lifetime" && budgetCents ? { lifetime_budget: budgetCents } : {}),
      });
      onCreated();
      onClose();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || "作成に失敗しました";
      setError(detail);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-campaign-title"
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
        <h3 id="create-campaign-title" className="text-[15px] font-bold text-gray-900 mb-4">キャンペーンを作成</h3>
        <p className="text-[11px] text-gray-400 mb-4">キャンペーンはPAUSED状態で作成されます</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="campaign-name" className="block text-[12px] font-medium text-gray-700 mb-1">キャンペーン名</label>
            <input
              id="campaign-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="キャンペーン名を入力"
              maxLength={400}
              aria-required="true"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
          </div>

          <div>
            <label htmlFor="campaign-objective" className="block text-[12px] font-medium text-gray-700 mb-1">目的</label>
            <select
              id="campaign-objective"
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[13px]"
            >
              {OBJECTIVES.map((obj) => (
                <option key={obj.value} value={obj.value}>{obj.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[12px] font-medium text-gray-700 mb-1">予算タイプ</label>
            <div className="flex gap-3">
              <label className="flex items-center gap-1.5 text-[12px]">
                <input
                  type="radio"
                  checked={budgetType === "daily"}
                  onChange={() => setBudgetType("daily")}
                  className="text-blue-500"
                />
                日予算
              </label>
              <label className="flex items-center gap-1.5 text-[12px]">
                <input
                  type="radio"
                  checked={budgetType === "lifetime"}
                  onChange={() => setBudgetType("lifetime")}
                  className="text-blue-500"
                />
                通算予算
              </label>
            </div>
          </div>

          <div>
            <label htmlFor="campaign-budget" className="block text-[12px] font-medium text-gray-700 mb-1">
              予算 (円)
            </label>
            <input
              id="campaign-budget"
              type="number"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="1000"
              min="100"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-[13px]"
            />
          </div>

          {error && (
            <p className="text-[12px] text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary text-[12px] px-4 py-2">
              キャンセル
            </button>
            <button type="submit" disabled={creating} className="btn-primary text-[12px] px-4 py-2 disabled:opacity-50">
              {creating ? "作成中..." : "作成（PAUSED）"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
