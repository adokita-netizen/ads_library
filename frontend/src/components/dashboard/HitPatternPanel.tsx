"use client";

import React, { useState, useEffect, useMemo } from "react";
import { fetchApi } from "@/lib/api";

// ─── Types ───

interface FactorItem {
  name: string;
  label?: string;
  hit_rate: number;
  count: number;
  total?: number;
}

interface WinningPattern {
  rank?: number;
  hook_type?: string;
  cta_type?: string;
  offer_type?: string;
  emotion?: string;
  hit_rate: number;
  count: number;
  sample_ad_ids?: number[];
}

interface HitFactorsData {
  hook_types?: FactorItem[];
  cta_types?: FactorItem[];
  offer_types?: FactorItem[];
  emotion_types?: FactorItem[];
  winning_patterns?: WinningPattern[];
}

// ─── Label maps ───

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
  shock: "衝撃・驚き",
  empathy: "共感型",
  unknown: "不明",
};

const ctaLabels: Record<string, string> = {
  purchase: "購入",
  consultation: "無料相談",
  free_trial: "無料お試し",
  line_add: "LINE追加",
  download: "ダウンロード",
  register: "会員登録",
  inquiry: "問い合わせ",
  reserve: "予約",
  learn_more: "詳しく見る",
  unknown: "不明",
};

const offerLabels: Record<string, string> = {
  discount: "割引",
  free: "無料",
  limited_time: "期間限定",
  bonus: "特典付き",
  guarantee: "返金保証",
  comparison: "比較",
  trial: "お試し",
  bundle: "セット",
  exclusive: "限定",
  unknown: "不明",
};

const emotionLabels: Record<string, string> = {
  fear: "不安・恐怖",
  hope: "希望",
  anger: "怒り",
  joy: "喜び",
  surprise: "驚き",
  trust: "信頼",
  desire: "欲望",
  relief: "安心",
  curiosity: "好奇心",
  unknown: "不明",
};

function getLabel(key: string, item: FactorItem, labels: Record<string, string>): string {
  return item.label || labels[key] || labels[item.name] || item.name;
}

// ─── Bar color by hit rate ───

function barColor(hitRate: number): string {
  if (hitRate >= 70) return "#22c55e";
  if (hitRate >= 45) return "#f59e0b";
  return "#94a3b8";
}

// ─── Sub-components ───

function HorizontalBarSection({
  title,
  items,
  labels,
}: {
  title: string;
  items: FactorItem[];
  labels: Record<string, string>;
}) {
  if (!items || items.length === 0) return null;
  const sorted = [...items].sort((a, b) => b.hit_rate - a.hit_rate);
  const maxRate = Math.max(1, ...sorted.map((i) => i.hit_rate));

  return (
    <div>
      <p className="text-[11px] text-gray-500 font-medium mb-2">{title}</p>
      <div className="space-y-1.5">
        {sorted.map((item) => {
          const pct = maxRate > 0 ? (item.hit_rate / maxRate) * 100 : 0;
          const displayRate = typeof item.hit_rate === "number" && item.hit_rate <= 1
            ? Math.round(item.hit_rate * 100)
            : Math.round(item.hit_rate);
          return (
            <div key={item.name} className="flex items-center gap-2">
              <span className="text-[10px] text-gray-600 w-20 truncate shrink-0" title={getLabel(item.name, item, labels)}>
                {getLabel(item.name, item, labels)}
              </span>
              <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden relative">
                <div
                  className="h-full rounded transition-all"
                  style={{ width: `${pct}%`, backgroundColor: barColor(displayRate) }}
                />
                <span className="absolute inset-y-0 right-1.5 flex items-center text-[9px] font-medium text-gray-700">
                  {displayRate}%
                  <span className="ml-1 text-[8px] text-gray-400">({item.count}件)</span>
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WinningPatternCard({ pattern, rank }: { pattern: WinningPattern; rank: number }) {
  const displayRate = typeof pattern.hit_rate === "number" && pattern.hit_rate <= 1
    ? Math.round(pattern.hit_rate * 100)
    : Math.round(pattern.hit_rate);

  const parts: string[] = [];
  if (pattern.hook_type) parts.push(hookLabels[pattern.hook_type] || pattern.hook_type);
  if (pattern.cta_type) parts.push(ctaLabels[pattern.cta_type] || pattern.cta_type);
  if (pattern.offer_type) parts.push(offerLabels[pattern.offer_type] || pattern.offer_type);
  if (pattern.emotion) parts.push(emotionLabels[pattern.emotion] || pattern.emotion);

  const medalColors = ["bg-yellow-100 text-yellow-800 border-yellow-300", "bg-gray-100 text-gray-600 border-gray-300", "bg-orange-100 text-orange-700 border-orange-300"];
  const medalBg = rank <= 3 ? medalColors[rank - 1] || "" : "bg-gray-50 text-gray-500 border-gray-200";

  return (
    <div className={`flex items-start gap-3 rounded-lg border px-3 py-2.5 ${medalBg}`}>
      <span className="shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full text-[11px] font-bold bg-white/70 border border-current">
        {rank}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1 flex-wrap mb-1">
          {parts.map((p, i) => (
            <React.Fragment key={i}>
              {i > 0 && <span className="text-[9px] text-gray-400 mx-0.5">x</span>}
              <span className="text-[10px] font-medium">{p}</span>
            </React.Fragment>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-bold" style={{ color: barColor(displayRate) }}>
            {displayRate}%
          </span>
          <span className="text-[9px] text-gray-400">{pattern.count}件</span>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ───

interface HitPatternPanelProps {
  genre?: string;
}

export default function HitPatternPanel({ genre }: HitPatternPanelProps) {
  const [data, setData] = useState<HitFactorsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);

    const params: Record<string, string | number | undefined> = {};
    if (genre && genre !== "all") params.genre = genre;

    fetchApi<HitFactorsData>("/rankings/hit-factors", { params })
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [genre]);

  // Check if data is empty (API returned but no useful content)
  const isEmpty = useMemo(() => {
    if (!data) return true;
    const hasHooks = (data.hook_types?.length ?? 0) > 0;
    const hasCtas = (data.cta_types?.length ?? 0) > 0;
    const hasOffers = (data.offer_types?.length ?? 0) > 0;
    const hasPatterns = (data.winning_patterns?.length ?? 0) > 0;
    return !hasHooks && !hasCtas && !hasOffers && !hasPatterns;
  }, [data]);

  if (loading) {
    return (
      <div className="card px-4 py-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
          <span className="text-[11px] text-gray-400">ヒットパターンを分析中...</span>
        </div>
        <div className="space-y-3 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-4 bg-gray-100 rounded w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (error || isEmpty || !data) {
    return (
      <div className="card px-4 py-4">
        <div className="flex items-center gap-2 mb-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
          </svg>
          <h3 className="text-[13px] font-bold text-gray-900">ヒットパターン分析</h3>
        </div>
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <svg className="w-10 h-10 text-gray-200 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
          <p className="text-[12px] text-gray-500 mb-1">データ準備中</p>
          <p className="text-[10px] text-gray-400">広告データが蓄積されると、ヒットパターンが自動分析されます</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card px-4 py-4">
      <div className="flex items-center gap-2 mb-4">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">ヒットパターン分析</h3>
        <span className="text-[10px] text-gray-400">要素別ヒット率</span>
      </div>

      {/* Hit rate charts by category */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        <HorizontalBarSection
          title="フック別ヒット率"
          items={data.hook_types || []}
          labels={hookLabels}
        />
        <HorizontalBarSection
          title="CTA別ヒット率"
          items={data.cta_types || []}
          labels={ctaLabels}
        />
        <HorizontalBarSection
          title="オファー別ヒット率"
          items={data.offer_types || []}
          labels={offerLabels}
        />
        {(data.emotion_types?.length ?? 0) > 0 && (
          <HorizontalBarSection
            title="感情別ヒット率"
            items={data.emotion_types || []}
            labels={emotionLabels}
          />
        )}
      </div>

      {/* Winning Patterns TOP 5 */}
      {data.winning_patterns && data.winning_patterns.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <svg className="w-4 h-4 text-yellow-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 007.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M7.73 9.728a6.726 6.726 0 002.748 1.35m8.272-6.842V4.5c0 2.108-.966 3.99-2.48 5.228m2.48-5.492a46.32 46.32 0 012.916.52 6.003 6.003 0 01-5.395 4.972m0 0a6.726 6.726 0 01-2.749 1.35m0 0a6.772 6.772 0 01-3.044 0" />
            </svg>
            <p className="text-[11px] font-bold text-gray-900">勝ちパターン TOP{Math.min(5, data.winning_patterns.length)}</p>
          </div>
          <div className="space-y-2">
            {data.winning_patterns.slice(0, 5).map((pat, i) => (
              <WinningPatternCard key={i} pattern={pat} rank={pat.rank || i + 1} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
