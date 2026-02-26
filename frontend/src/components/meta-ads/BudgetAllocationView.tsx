"use client";

import { useState, useCallback } from "react";
import toast from "react-hot-toast";
import { metaMarketingApi } from "@/lib/api";

interface AllocationItem {
  ad_set_id: string;
  ad_set_name?: string;
  spend: number;
  budget: number;
  conversions: number;
  cpa: number;
  utilization: number;
}

interface BudgetAllocationData {
  campaign_id: string;
  total_budget: number;
  total_spend: number;
  allocations: AllocationItem[];
}

interface Props {
  campaignId: string;
}

export default function BudgetAllocationView({ campaignId }: Props) {
  const [data, setData] = useState<BudgetAllocationData | null>(null);
  const [loading, setLoading] = useState(false);

  const loadAllocation = useCallback(async () => {
    setLoading(true);
    try {
      const res = await metaMarketingApi.getBudgetAllocation(campaignId);
      setData(res.data);
    } catch {
      toast.error("予算配分データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  if (!data && !loading) {
    return (
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[13px] font-bold text-gray-800">予算配分</h3>
          <button onClick={loadAllocation} className="btn-secondary text-[11px] px-3 py-1">
            データを読み込む
          </button>
        </div>
        <p className="text-[12px] text-gray-400 py-4 text-center">
          「データを読み込む」をクリックして予算配分を表示
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="card p-4 text-center py-8 text-[12px] text-gray-400">
        読み込み中...
      </div>
    );
  }

  if (!data || !data.allocations?.length) {
    return (
      <div className="card p-4 text-center py-8 text-[12px] text-gray-400">
        予算配分データがありません
      </div>
    );
  }

  const maxSpend = Math.max(...data.allocations.map((a) => a.spend), 1);
  const medianCpa = (() => {
    const cpas = data.allocations.filter((a) => a.cpa > 0 && a.cpa < Infinity).map((a) => a.cpa).sort((a, b) => a - b);
    return cpas.length > 0 ? cpas[Math.floor(cpas.length / 2)] : 0;
  })();

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[13px] font-bold text-gray-800">予算配分</h3>
        <button onClick={loadAllocation} className="btn-secondary text-[11px] px-3 py-1">
          更新
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-gray-50 rounded-lg p-2 text-center">
          <p className="text-[10px] text-gray-500">総予算</p>
          <p className="text-[14px] font-bold text-gray-800">&yen;{Math.round(data.total_budget).toLocaleString()}</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-2 text-center">
          <p className="text-[10px] text-gray-500">総消化額</p>
          <p className="text-[14px] font-bold text-gray-800">&yen;{Math.round(data.total_spend).toLocaleString()}</p>
        </div>
        <div className="bg-gray-50 rounded-lg p-2 text-center">
          <p className="text-[10px] text-gray-500">消化率</p>
          <p className="text-[14px] font-bold text-gray-800">
            {data.total_budget > 0 ? ((data.total_spend / data.total_budget) * 100).toFixed(1) : 0}%
          </p>
        </div>
      </div>

      {/* Horizontal bar chart */}
      <div className="space-y-2">
        {data.allocations.map((alloc) => {
          const spendWidth = maxSpend > 0 ? (alloc.spend / maxSpend) * 100 : 0;
          const isInefficient = medianCpa > 0 && alloc.cpa > medianCpa * 2;
          return (
            <div key={alloc.ad_set_id} className="space-y-0.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] font-medium text-gray-700 truncate max-w-[200px]">
                    {alloc.ad_set_name || alloc.ad_set_id}
                  </span>
                  {isInefficient && (
                    <span className="text-[9px] px-1 py-0.5 bg-red-50 text-red-600 rounded" title="CPAが中央値の2倍以上">
                      非効率
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-[10px] text-gray-500">
                  <span>CPA: {alloc.cpa > 0 && alloc.cpa < Infinity ? `¥${Math.round(alloc.cpa).toLocaleString()}` : "-"}</span>
                  <span>CV: {alloc.conversions}</span>
                </div>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-3">
                <div
                  className={`h-3 rounded-full transition-all ${isInefficient ? "bg-red-400" : "bg-[#4A7DFF]"}`}
                  style={{ width: `${Math.max(spendWidth, 2)}%` }}
                  title={`¥${Math.round(alloc.spend).toLocaleString()}`}
                />
              </div>
              <div className="flex justify-between text-[9px] text-gray-400">
                <span>&yen;{Math.round(alloc.spend).toLocaleString()}</span>
                <span>予算: &yen;{Math.round(alloc.budget).toLocaleString()}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
