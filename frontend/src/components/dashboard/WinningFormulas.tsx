"use client";

import React, { useState, useEffect, useMemo } from "react";
import { fetchApi } from "@/lib/api";

interface FormulaItem {
  hook_type?: string;
  cta_type?: string;
  offer_type?: string;
  emotion?: string;
  hit_rate: number;
  count: number;
  example_ads?: Array<{
    ad_id: number;
    product_name?: string;
    title?: string;
    hit_score?: number;
  }>;
}

interface WinningFormulasProps {
  genre?: string;
  onAdSelect?: (adId: number) => void;
}

const hookLabels: Record<string, string> = {
  question: "質問型",
  pain_point: "悩み訴求",
  benefit: "ベネフィット",
  curiosity: "好奇心",
  social_proof: "社会的証明",
  urgency: "緊急性",
  storytelling: "ストーリー",
  number: "数字訴求",
  comparison: "比較",
  authority: "権威性",
};

const ctaLabels: Record<string, string> = {
  learn_more: "詳しく見る",
  sign_up: "登録する",
  buy_now: "今すぐ購入",
  free_trial: "無料お試し",
  download: "ダウンロード",
  apply: "申し込む",
  contact: "問い合わせ",
  line_add: "LINE登録",
  compare: "比較する",
};

const offerLabels: Record<string, string> = {
  free_trial: "無料お試し",
  discount: "割引",
  limited_time: "期間限定",
  bonus: "特典付き",
  money_back: "返金保証",
  free_shipping: "送料無料",
  bundle: "セット割",
  first_time: "初回限定",
  consultation: "無料相談",
};

const emotionLabels: Record<string, string> = {
  fear: "不安",
  hope: "希望",
  anger: "怒り",
  joy: "喜び",
  surprise: "驚き",
  trust: "信頼",
  desire: "欲望",
  relief: "安心",
  curiosity: "好奇心",
};

const badgeColors = {
  hook: "bg-blue-100 text-blue-700",
  cta: "bg-emerald-100 text-emerald-700",
  offer: "bg-amber-100 text-amber-700",
  emotion: "bg-purple-100 text-purple-700",
};

const medalColors = ["#FFD700", "#C0C0C0", "#CD7F32"];

export default function WinningFormulas({ genre, onAdSelect }: WinningFormulasProps) {
  const [formulas, setFormulas] = useState<FormulaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, string | number | undefined> = {};
        if (genre && genre !== "all") params.genre = genre;
        // Try the hit-factors endpoint which includes winning patterns
        const res = await fetchApi<{
          winning_patterns?: FormulaItem[];
          formulas?: FormulaItem[];
          items?: FormulaItem[];
        }>("/rankings/hit-factors", { params });
        const items = res?.winning_patterns || res?.formulas || res?.items || (Array.isArray(res) ? res : []);
        setFormulas(Array.isArray(items) ? items : []);
      } catch {
        setError("勝ちフォーミュラの取得に失敗しました");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [genre]);

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card px-4 py-4 animate-pulse">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-6 h-6 rounded-full bg-gray-200" />
              <div className="h-3.5 bg-gray-200 rounded w-48" />
            </div>
            <div className="flex gap-2">
              <div className="h-5 bg-gray-100 rounded w-16" />
              <div className="h-5 bg-gray-100 rounded w-20" />
              <div className="h-5 bg-gray-100 rounded w-14" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="card px-4 py-6 text-center">
        <p className="text-[12px] text-red-500 mb-2">{error}</p>
        <p className="text-[10px] text-gray-400">データが準備中の可能性があります</p>
      </div>
    );
  }

  if (formulas.length === 0) {
    return (
      <div className="card px-4 py-8 text-center">
        <svg className="w-10 h-10 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
        </svg>
        <p className="text-[12px] text-gray-500 mb-1">勝ちフォーミュラのデータがありません</p>
        <p className="text-[10px] text-gray-400">十分なヒット広告が蓄積されると自動生成されます</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-1">
        <svg className="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">勝ちフォーミュラ</h3>
        <span className="text-[10px] text-gray-400">ヒット広告の勝ち組み合わせTOP{Math.min(formulas.length, 10)}</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {formulas.slice(0, 10).map((formula, i) => {
          const hitRate = typeof formula.hit_rate === "number" ? (formula.hit_rate <= 1 ? formula.hit_rate * 100 : formula.hit_rate) : 0;
          const isExpanded = expandedIdx === i;
          return (
            <div
              key={i}
              className={`card px-4 py-3 cursor-pointer transition-all hover:shadow-md ${isExpanded ? "ring-1 ring-[#4A7DFF]/30" : ""}`}
              onClick={() => setExpandedIdx(isExpanded ? null : i)}
            >
              {/* Header with rank */}
              <div className="flex items-center gap-2 mb-2">
                {i < 3 ? (
                  <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0" style={{ backgroundColor: `${medalColors[i]}20` }}>
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill={medalColors[i]}>
                      <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
                    </svg>
                  </div>
                ) : (
                  <span className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center text-[10px] font-bold text-gray-500 shrink-0">
                    {i + 1}
                  </span>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1">
                    <span className="text-[14px] font-bold" style={{
                      color: hitRate >= 30 ? "#22c55e" : hitRate >= 15 ? "#f59e0b" : "#6b7280",
                    }}>
                      {hitRate.toFixed(1)}%
                    </span>
                    <span className="text-[9px] text-gray-400">HIT率</span>
                    <span className="text-[9px] text-gray-400 ml-auto">{formula.count}件</span>
                  </div>
                </div>
              </div>

              {/* Badges */}
              <div className="flex flex-wrap gap-1.5">
                {formula.hook_type && (
                  <span className={`text-[9px] px-2 py-0.5 rounded-full font-medium ${badgeColors.hook}`}>
                    {hookLabels[formula.hook_type] || formula.hook_type}
                  </span>
                )}
                {formula.cta_type && (
                  <span className={`text-[9px] px-2 py-0.5 rounded-full font-medium ${badgeColors.cta}`}>
                    {ctaLabels[formula.cta_type] || formula.cta_type}
                  </span>
                )}
                {formula.offer_type && (
                  <span className={`text-[9px] px-2 py-0.5 rounded-full font-medium ${badgeColors.offer}`}>
                    {offerLabels[formula.offer_type] || formula.offer_type}
                  </span>
                )}
                {formula.emotion && (
                  <span className={`text-[9px] px-2 py-0.5 rounded-full font-medium ${badgeColors.emotion}`}>
                    {emotionLabels[formula.emotion] || formula.emotion}
                  </span>
                )}
              </div>

              {/* Hit rate bar */}
              <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(hitRate, 100)}%`,
                    backgroundColor: hitRate >= 30 ? "#22c55e" : hitRate >= 15 ? "#f59e0b" : "#94a3b8",
                  }}
                />
              </div>

              {/* Expanded: example ads */}
              {isExpanded && formula.example_ads && formula.example_ads.length > 0 && (
                <div className="mt-3 pt-2 border-t border-gray-100">
                  <p className="text-[10px] text-gray-400 font-medium mb-1.5">このパターンの広告例</p>
                  <div className="space-y-1">
                    {formula.example_ads.slice(0, 5).map((ad) => (
                      <button
                        key={ad.ad_id}
                        className="w-full text-left flex items-center gap-2 py-1 px-2 rounded hover:bg-gray-50 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          onAdSelect?.(ad.ad_id);
                        }}
                      >
                        <span className="text-[10px] text-gray-700 truncate flex-1">
                          {ad.product_name || ad.title || `Ad #${ad.ad_id}`}
                        </span>
                        <span className="text-[10px] font-semibold text-[#4A7DFF] shrink-0">{ad.hit_score || 0}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
