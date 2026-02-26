"use client";

import { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import type { OptimizationRecommendation } from "@/types";
import { metaMarketingApi } from "@/lib/api";
import ConfirmModal from "@/components/common/ConfirmModal";
import RecommendationCard from "./RecommendationCard";

interface Props {
  accountId: string;
}

export default function OptimizationDashboard({ accountId }: Props) {
  const [recommendations, setRecommendations] = useState<OptimizationRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("pending");

  const loadRecommendations = useCallback(async () => {
    setLoading(true);
    try {
      const res = await metaMarketingApi.listRecommendations({
        account_id: accountId,
        status: filter || undefined,
      });
      setRecommendations(res.data?.recommendations || []);
    } catch {
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  }, [accountId, filter]);

  useEffect(() => {
    loadRecommendations();
  }, [loadRecommendations]);

  const handleAccept = async (id: number) => {
    try {
      await metaMarketingApi.acceptRecommendation(id);
      await loadRecommendations();
      toast.success("レコメンドを承認しました");
    } catch (err) {
      console.error("Failed to accept:", err);
      toast.error("承認に失敗しました");
    }
  };

  const handleReject = async (id: number) => {
    try {
      await metaMarketingApi.rejectRecommendation(id);
      await loadRecommendations();
      toast.success("レコメンドを却下しました");
    } catch (err) {
      console.error("Failed to reject:", err);
      toast.error("却下に失敗しました");
    }
  };

  const [applyTarget, setApplyTarget] = useState<number | null>(null);

  const handleApply = async (id: number) => {
    setApplyTarget(null);
    try {
      await metaMarketingApi.applyRecommendation(id);
      await loadRecommendations();
      toast.success("レコメンドを適用しました");
    } catch (err) {
      console.error("Failed to apply:", err);
      toast.error("適用に失敗しました");
    }
  };

  return (
    <div className="space-y-4">
      {/* Header & Filter */}
      <div className="flex items-center justify-between">
        <h3 className="text-[13px] font-bold text-gray-800">最適化レコメンド ({recommendations.length})</h3>
        <div className="flex gap-1">
          {["pending", "accepted", "applied", "rejected", ""].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-[10px] px-2 py-1 rounded ${
                filter === f ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-500"
              }`}
            >
              {f === "" ? "全て" : f === "pending" ? "保留中" : f === "accepted" ? "承認済" : f === "applied" ? "適用済" : "却下"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="text-center py-8 text-[12px] text-gray-400">読み込み中...</div>
      ) : recommendations.length === 0 ? (
        <div className="text-center py-12 text-[13px] text-gray-400">
          レコメンドがありません。データ同期後に自動生成されます。
        </div>
      ) : (
        <div className="space-y-3">
          {recommendations.map((rec) => (
            <RecommendationCard
              key={rec.id}
              recommendation={rec}
              onAccept={handleAccept}
              onReject={handleReject}
              onApply={(id) => setApplyTarget(id)}
            />
          ))}
        </div>
      )}

      {applyTarget !== null && (
        <ConfirmModal
          title="レコメンドの適用"
          message="このレコメンドをMeta APIに適用しますか？実際の広告設定が変更されます。"
          confirmLabel="適用する"
          variant="warning"
          onConfirm={() => handleApply(applyTarget)}
          onCancel={() => setApplyTarget(null)}
        />
      )}
    </div>
  );
}
