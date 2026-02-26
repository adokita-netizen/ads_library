"use client";

import type { OptimizationRecommendation } from "@/types";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-50 text-red-700 border-red-200",
  high: "bg-amber-50 text-amber-700 border-amber-200",
  medium: "bg-blue-50 text-blue-700 border-blue-200",
  low: "bg-gray-50 text-gray-600 border-gray-200",
};

const TYPE_LABELS: Record<string, string> = {
  budget_increase: "予算増額",
  budget_decrease: "予算削減",
  pause_ad: "広告停止",
  scale_ad: "スケール",
  creative_refresh: "クリエイティブ更新",
  bid_adjust: "入札調整",
};

interface Props {
  recommendation: OptimizationRecommendation;
  onAccept?: (id: number) => void;
  onReject?: (id: number) => void;
  onApply?: (id: number) => void;
}

export default function RecommendationCard({ recommendation: rec, onAccept, onReject, onApply }: Props) {
  return (
    <div className={`border rounded-lg p-4 ${SEVERITY_COLORS[rec.severity] || SEVERITY_COLORS.low}`}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/60">
              {TYPE_LABELS[rec.recommendation_type] || rec.recommendation_type}
            </span>
            <span className="text-[10px] uppercase font-medium">{rec.severity}</span>
          </div>
          <h4 className="text-[13px] font-medium">{rec.title}</h4>
          {rec.description && <p className="text-[11px] mt-1 opacity-80">{rec.description}</p>}
          {rec.rationale && <p className="text-[10px] mt-1 opacity-60">{rec.rationale}</p>}

          {rec.predicted_impact && (
            <div className="flex gap-3 mt-2 text-[10px]">
              <span>現在: {rec.predicted_impact.current}</span>
              <span>予測: {rec.predicted_impact.predicted}</span>
              <span className={rec.predicted_impact.change_percent > 0 ? "text-green-600" : "text-red-600"}>
                {rec.predicted_impact.change_percent > 0 ? "+" : ""}{rec.predicted_impact.change_percent}%
              </span>
            </div>
          )}
        </div>

        {/* Actions */}
        {rec.status === "pending" && (
          <div className="flex gap-1 ml-3 shrink-0">
            {onAccept && (
              <button
                onClick={() => onAccept(rec.id)}
                className="text-[10px] bg-green-500 text-white px-2 py-1 rounded hover:bg-green-600"
              >
                承認
              </button>
            )}
            {onReject && (
              <button
                onClick={() => onReject(rec.id)}
                className="text-[10px] bg-gray-300 text-gray-700 px-2 py-1 rounded hover:bg-gray-400"
              >
                却下
              </button>
            )}
          </div>
        )}
        {rec.status === "accepted" && onApply && (
          <button
            onClick={() => onApply(rec.id)}
            className="text-[10px] bg-blue-500 text-white px-2 py-1 rounded hover:bg-blue-600 ml-3"
          >
            適用
          </button>
        )}
        {rec.status === "applied" && (
          <span className="text-[10px] text-green-600 ml-3">適用済み</span>
        )}
      </div>
    </div>
  );
}
