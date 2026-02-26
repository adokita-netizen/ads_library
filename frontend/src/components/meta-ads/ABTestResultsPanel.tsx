"use client";

import { useState } from "react";
import toast from "react-hot-toast";
import type { ABTestExperiment } from "@/types";
import { metaMarketingApi } from "@/lib/api";

interface Props {
  experiment: ABTestExperiment;
  onMetricsUpdated?: () => void;
}

export default function ABTestResultsPanel({ experiment, onMetricsUpdated }: Props) {
  const [updatingMetrics, setUpdatingMetrics] = useState(false);

  const variants = experiment.variants || [];
  if (variants.length === 0) {
    return (
      <div className="text-center py-4 text-[12px] text-gray-400">
        バリアントが設定されていません
      </div>
    );
  }

  const maxImpressions = Math.max(...variants.map((v) => v.impressions || 0), 1);
  const maxCtr = Math.max(...variants.map((v) => v.ctr || 0), 0.01);
  const maxSpend = Math.max(...variants.map((v) => v.spend || 0), 1);

  const control = variants.find((v) => v.variant_type === "control");
  const sampleProgress = experiment.min_sample_size > 0
    ? Math.min(
        (variants.reduce((sum, v) => sum + (v.impressions || 0), 0) / experiment.min_sample_size) * 100,
        100
      )
    : 0;

  const handleUpdateMetrics = async () => {
    setUpdatingMetrics(true);
    try {
      await metaMarketingApi.updateExperimentMetrics(experiment.id);
      toast.success("指標を更新しました");
      onMetricsUpdated?.();
    } catch {
      toast.error("指標の更新に失敗しました");
    } finally {
      setUpdatingMetrics(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header with update button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h4 className="text-[12px] font-bold text-gray-800">テスト結果</h4>
          {experiment.statistical_significance !== null && experiment.statistical_significance !== undefined && (
            <span className="text-[10px] px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded">
              p={experiment.statistical_significance.toFixed(4)}
            </span>
          )}
        </div>
        <button
          onClick={handleUpdateMetrics}
          disabled={updatingMetrics}
          className="btn-secondary text-[10px] px-2 py-1 disabled:opacity-50"
        >
          {updatingMetrics ? "更新中..." : "指標更新"}
        </button>
      </div>

      {/* Sample size progress */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] text-gray-500">サンプルサイズ進捗</span>
          <span className="text-[10px] text-gray-500">
            {variants.reduce((sum, v) => sum + (v.impressions || 0), 0).toLocaleString()} / {experiment.min_sample_size.toLocaleString()}
          </span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full transition-all ${sampleProgress >= 100 ? "bg-green-500" : "bg-blue-500"}`}
            style={{ width: `${sampleProgress}%` }}
          />
        </div>
        <div className="flex items-center justify-between mt-0.5">
          <span className="text-[9px] text-gray-400">信頼水準: {(experiment.confidence_level * 100).toFixed(0)}%</span>
          <span className="text-[9px] text-gray-400">{sampleProgress.toFixed(0)}%</span>
        </div>
      </div>

      {/* Variant comparison bars */}
      <div className="space-y-3">
        {/* Impressions comparison */}
        <div>
          <p className="text-[10px] font-medium text-gray-600 mb-1.5">インプレッション</p>
          {variants.map((v) => {
            const width = maxImpressions > 0 ? ((v.impressions || 0) / maxImpressions) * 100 : 0;
            return (
              <div key={v.id} className="flex items-center gap-2 mb-1">
                <div className="w-20 flex items-center gap-1 shrink-0">
                  <span className="text-[10px] text-gray-700 truncate">{v.name}</span>
                  {v.is_winner && (
                    <span className="text-[8px] bg-green-500 text-white px-1 rounded">勝</span>
                  )}
                </div>
                <div className="flex-1 bg-gray-100 rounded-full h-4 relative">
                  <div
                    className={`h-4 rounded-full ${v.variant_type === "control" ? "bg-gray-400" : "bg-[#4A7DFF]"}`}
                    style={{ width: `${Math.max(width, 2)}%` }}
                  />
                  <span className="absolute right-2 top-0 h-4 flex items-center text-[9px] text-gray-600 font-medium">
                    {(v.impressions || 0).toLocaleString()}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* CTR comparison */}
        <div>
          <p className="text-[10px] font-medium text-gray-600 mb-1.5">CTR (%)</p>
          {variants.map((v) => {
            const width = maxCtr > 0 ? ((v.ctr || 0) / maxCtr) * 100 : 0;
            const liftVsControl = control && control.ctr > 0 && v.id !== control.id
              ? ((v.ctr - control.ctr) / control.ctr * 100)
              : null;
            return (
              <div key={v.id} className="flex items-center gap-2 mb-1">
                <div className="w-20 shrink-0">
                  <span className="text-[10px] text-gray-700 truncate">{v.name}</span>
                </div>
                <div className="flex-1 bg-gray-100 rounded-full h-4 relative">
                  <div
                    className={`h-4 rounded-full ${v.variant_type === "control" ? "bg-gray-400" : "bg-emerald-500"}`}
                    style={{ width: `${Math.max(width, 2)}%` }}
                  />
                  <span className="absolute right-2 top-0 h-4 flex items-center text-[9px] text-gray-600 font-medium">
                    {(v.ctr || 0).toFixed(2)}%
                    {liftVsControl !== null && (
                      <span className={`ml-1 ${liftVsControl >= 0 ? "text-green-600" : "text-red-500"}`}>
                        ({liftVsControl >= 0 ? "+" : ""}{liftVsControl.toFixed(1)}%)
                      </span>
                    )}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Spend comparison */}
        <div>
          <p className="text-[10px] font-medium text-gray-600 mb-1.5">消化額 (&yen;)</p>
          {variants.map((v) => {
            const width = maxSpend > 0 ? ((v.spend || 0) / maxSpend) * 100 : 0;
            return (
              <div key={v.id} className="flex items-center gap-2 mb-1">
                <div className="w-20 shrink-0">
                  <span className="text-[10px] text-gray-700 truncate">{v.name}</span>
                </div>
                <div className="flex-1 bg-gray-100 rounded-full h-4 relative">
                  <div
                    className={`h-4 rounded-full ${v.variant_type === "control" ? "bg-gray-400" : "bg-amber-500"}`}
                    style={{ width: `${Math.max(width, 2)}%` }}
                  />
                  <span className="absolute right-2 top-0 h-4 flex items-center text-[9px] text-gray-600 font-medium">
                    &yen;{Math.round(v.spend || 0).toLocaleString()}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
