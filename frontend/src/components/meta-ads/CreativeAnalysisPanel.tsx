"use client";

import { useState, useCallback } from "react";
import toast from "react-hot-toast";
import { metaMarketingApi } from "@/lib/api";
import type { CreativeInsightsSummary, CompetitorComparison } from "@/types";

interface Props {
  accountId: string;
}

export default function CreativeAnalysisPanel({ accountId }: Props) {
  const [insights, setInsights] = useState<CreativeInsightsSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [adIdInput, setAdIdInput] = useState("");
  const [comparison, setComparison] = useState<CompetitorComparison | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const loadInsights = useCallback(async () => {
    setLoading(true);
    try {
      const res = await metaMarketingApi.getCreativeInsights(accountId);
      setInsights(res.data);
      toast.success("インサイトを読み込みました");
    } catch (err) {
      console.error("Failed to load creative insights:", err);
      toast.error("インサイトの読み込みに失敗しました");
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  const analyzeAd = async () => {
    if (!adIdInput.trim()) return;
    setAnalyzing(true);
    try {
      await metaMarketingApi.analyzeAd(adIdInput.trim());
      const compRes = await metaMarketingApi.getCompetitorComparison(adIdInput.trim());
      setComparison(compRes.data);
      toast.success("分析が完了しました");
    } catch (err) {
      console.error("Analysis failed:", err);
      toast.error("分析に失敗しました");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Account Insights */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[13px] font-bold text-gray-800">クリエイティブパフォーマンス概要</h3>
          <button onClick={loadInsights} className="btn-secondary text-[11px] px-3 py-1">
            {loading ? "読み込み中..." : "分析を実行"}
          </button>
        </div>

        {insights ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-[10px] text-gray-500">総広告数</p>
                <p className="text-[18px] font-bold text-gray-800">{insights.total_ads}</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-[10px] text-gray-500">クリエイティブタイプ</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {Object.entries(insights.creative_type_distribution || {}).map(([type, count]) => (
                    <span key={type} className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">
                      {type}: {count}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {insights.top_performers?.length > 0 && (
              <div>
                <p className="text-[11px] font-medium text-gray-700 mb-2">Top パフォーマー</p>
                <div className="space-y-1">
                  {insights.top_performers.slice(0, 5).map((p, i) => (
                    <div key={i} className="flex items-center justify-between text-[11px] py-1 border-b border-gray-50">
                      <span className="text-gray-600">{p.entity_id}</span>
                      <div className="flex gap-3">
                        <span className="text-gray-500">CTR: {p.ctr}%</span>
                        <span className="text-gray-500">&yen;{p.total_spend.toLocaleString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-[12px] text-gray-400 py-4 text-center">
            「分析を実行」をクリックしてクリエイティブインサイトを表示
          </p>
        )}
      </div>

      {/* Individual Ad Analysis */}
      <div className="card p-4">
        <h3 className="text-[13px] font-bold text-gray-800 mb-3">広告の競合比較分析</h3>
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            value={adIdInput}
            onChange={(e) => setAdIdInput(e.target.value)}
            placeholder="Meta Ad ID を入力"
            className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-[12px]"
          />
          <button
            onClick={analyzeAd}
            disabled={analyzing || !adIdInput.trim()}
            className="btn-primary text-[11px] px-3 py-1.5 disabled:opacity-50"
          >
            {analyzing ? "分析中..." : "分析"}
          </button>
        </div>

        {comparison && (
          <div className="space-y-3">
            <p className="text-[12px] font-medium text-gray-700">{comparison.own_ad_name}</p>

            {comparison.own_scores && Object.keys(comparison.own_scores).length > 0 && (
              <div className="grid grid-cols-3 gap-2">
                {Object.entries(comparison.own_scores).map(([key, value]) => (
                  <div key={key} className="bg-blue-50 rounded-lg p-2 text-center">
                    <p className="text-[10px] text-blue-500">{key.replace("_", " ")}</p>
                    <p className="text-[14px] font-bold text-blue-700">{value || "-"}</p>
                  </div>
                ))}
              </div>
            )}

            {comparison.advantages?.length > 0 && (
              <div className="bg-green-50 rounded-lg p-2">
                <p className="text-[10px] font-medium text-green-700 mb-1">優位点</p>
                {comparison.advantages.map((a, i) => (
                  <p key={i} className="text-[11px] text-green-600">+ {a}</p>
                ))}
              </div>
            )}

            {comparison.disadvantages?.length > 0 && (
              <div className="bg-amber-50 rounded-lg p-2">
                <p className="text-[10px] font-medium text-amber-700 mb-1">改善点</p>
                {comparison.disadvantages.map((d, i) => (
                  <p key={i} className="text-[11px] text-amber-600">- {d}</p>
                ))}
              </div>
            )}

            {comparison.suggestions?.length > 0 && (
              <div className="bg-blue-50 rounded-lg p-2">
                <p className="text-[10px] font-medium text-blue-700 mb-1">改善提案</p>
                {comparison.suggestions.map((s, i) => (
                  <p key={i} className="text-[11px] text-blue-600">{s}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
