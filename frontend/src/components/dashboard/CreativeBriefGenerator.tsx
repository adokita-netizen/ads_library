"use client";

import React, { useState } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";
import { copyToClipboard } from "@/lib/format";

// ─── Types ───

interface BriefResult {
  recommended_hooks?: string[];
  recommended_ctas?: string[];
  power_words?: string[];
  structure?: { step: string; label: string; description: string }[];
  predicted_performance?: number;
  summary?: string;
}

interface CreativeBriefGeneratorProps {
  genre?: string;
}

// ─── Mock Data ───

const MOCK_BRIEF: BriefResult = {
  recommended_hooks: ["「まだ○○で悩んでいませんか？」", "「たった3日で実感」", "「知らないと損する○○の真実」"],
  recommended_ctas: ["今すぐ無料で試す", "限定50名様", "30日間全額返金保証"],
  power_words: ["驚異の", "たった○日で", "プロが認めた", "今だけ", "業界初", "満足度98%"],
  structure: [
    { step: "hook", label: "フック", description: "視聴者の注意を3秒以内に掴む質問・衝撃的事実" },
    { step: "problem", label: "問題提起", description: "ターゲットが共感する具体的な悩み・課題を提示" },
    { step: "solution", label: "解決策", description: "商品・サービスがどう解決するか明確に提示" },
    { step: "proof", label: "証拠", description: "実績データ・口コミ・権威性で信頼を獲得" },
    { step: "cta", label: "CTA", description: "限定性・緊急性を添えて行動を促す" },
  ],
  predicted_performance: 74,
  summary: "質問型フックと限定CTAの組み合わせは、美容系ジャンルで高いCVRを記録しています。",
};

const purposeOptions = [
  { value: "awareness", label: "認知拡大" },
  { value: "conversion", label: "CV獲得" },
  { value: "branding", label: "ブランディング" },
  { value: "remarketing", label: "リマーケティング" },
];

const budgetOptions = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" },
];

const structureColors: Record<string, string> = {
  hook: "#4A7DFF",
  problem: "#ef4444",
  solution: "#22c55e",
  proof: "#f59e0b",
  cta: "#8b5cf6",
};

export default function CreativeBriefGenerator({ genre: initialGenre }: CreativeBriefGeneratorProps) {
  const [selectedGenre, setSelectedGenre] = useState(initialGenre || "all");
  const [target, setTarget] = useState("");
  const [purpose, setPurpose] = useState("conversion");
  const [budget, setBudget] = useState("medium");
  const [loading, setLoading] = useState(false);
  const [brief, setBrief] = useState<BriefResult | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const res = await fetchApi<BriefResult>("/rankings/generate-brief", {
        method: "POST",
        body: {
          genre: selectedGenre !== "all" ? selectedGenre : undefined,
          target_audience: target || undefined,
          purpose,
          budget,
        },
      });
      setBrief(res);
      toast.success("ブリーフを生成しました");
    } catch {
      setBrief(MOCK_BRIEF);
      toast("サンプルデータを表示しています", { icon: "ℹ️" });
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!brief) return;
    const lines: string[] = [];
    lines.push("【クリエイティブブリーフ】");
    lines.push(`ジャンル: ${genreOptions.find((g) => g.value === selectedGenre)?.label || selectedGenre}`);
    if (target) lines.push(`ターゲット: ${target}`);
    lines.push(`目的: ${purposeOptions.find((p) => p.value === purpose)?.label || purpose}`);
    lines.push("");
    if (brief.recommended_hooks?.length) lines.push(`推奨フック:\n${brief.recommended_hooks.map((h) => `  - ${h}`).join("\n")}`);
    if (brief.recommended_ctas?.length) lines.push(`推奨CTA:\n${brief.recommended_ctas.map((c) => `  - ${c}`).join("\n")}`);
    if (brief.power_words?.length) lines.push(`パワーワード: ${brief.power_words.join("、")}`);
    if (brief.structure?.length) {
      lines.push("\n構成案:");
      brief.structure.forEach((s) => lines.push(`  ${s.label}: ${s.description}`));
    }
    if (brief.predicted_performance != null) lines.push(`\n推定パフォーマンス: ${brief.predicted_performance}/100`);
    copyToClipboard(lines.join("\n")).then(() => toast.success("クリップボードにコピーしました"));
  };

  const score = brief?.predicted_performance ?? 0;
  const scoreColor = score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="card px-4 py-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">クリエイティブブリーフ生成</h3>
        <span className="text-[9px] text-gray-400">AIが最適なクリエイティブ構成を提案</span>
      </div>

      {/* Form */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-[9px] text-gray-400 block mb-0.5">ジャンル選択</label>
          <select value={selectedGenre} onChange={(e) => setSelectedGenre(e.target.value)} className="select-filter text-[10px] h-7 w-full">
            {genreOptions.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[9px] text-gray-400 block mb-0.5">ターゲット層</label>
          <input
            type="text"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            placeholder="例: 30代女性"
            className="w-full h-7 px-2 text-[10px] border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/40 bg-white"
          />
        </div>
      </div>

      {/* Purpose radio */}
      <div>
        <label className="text-[9px] text-gray-400 block mb-1">目的</label>
        <div className="flex flex-wrap gap-1.5">
          {purposeOptions.map((o) => (
            <button
              key={o.value}
              onClick={() => setPurpose(o.value)}
              className={`px-2.5 py-1 rounded-full text-[10px] border transition-colors ${
                purpose === o.value
                  ? "bg-[#4A7DFF] text-white border-[#4A7DFF]"
                  : "bg-white text-gray-600 border-gray-200 hover:border-[#4A7DFF]/40"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {/* Budget radio */}
      <div>
        <label className="text-[9px] text-gray-400 block mb-1">予算帯</label>
        <div className="flex gap-1.5">
          {budgetOptions.map((o) => (
            <button
              key={o.value}
              onClick={() => setBudget(o.value)}
              className={`px-3 py-1 rounded-full text-[10px] border transition-colors ${
                budget === o.value
                  ? "bg-[#4A7DFF] text-white border-[#4A7DFF]"
                  : "bg-white text-gray-600 border-gray-200 hover:border-[#4A7DFF]/40"
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {/* Generate button */}
      <button onClick={handleGenerate} disabled={loading} className="btn-primary text-[11px] h-8 px-5 w-full flex items-center justify-center gap-1.5">
        {loading ? (
          <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
        ) : (
          <>
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
            ブリーフ生成
          </>
        )}
      </button>

      {/* Result display */}
      {brief && (
        <div className="border-t border-gray-100 pt-4 space-y-4">
          {/* Summary */}
          {brief.summary && (
            <div className="bg-blue-50 rounded-lg px-3 py-2">
              <p className="text-[10px] text-blue-700 leading-relaxed">{brief.summary}</p>
            </div>
          )}

          {/* Recommended Hooks */}
          {brief.recommended_hooks && brief.recommended_hooks.length > 0 && (
            <div>
              <p className="text-[9px] text-gray-400 font-medium mb-1.5">推奨フック</p>
              <div className="flex flex-wrap gap-1.5">
                {brief.recommended_hooks.map((h, i) => (
                  <span key={i} className="text-[10px] px-2 py-1 rounded-full bg-blue-100 text-blue-700 font-medium">{h}</span>
                ))}
              </div>
            </div>
          )}

          {/* Recommended CTAs */}
          {brief.recommended_ctas && brief.recommended_ctas.length > 0 && (
            <div>
              <p className="text-[9px] text-gray-400 font-medium mb-1.5">推奨CTA</p>
              <div className="flex flex-wrap gap-1.5">
                {brief.recommended_ctas.map((c, i) => (
                  <span key={i} className="text-[10px] px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-medium">{c}</span>
                ))}
              </div>
            </div>
          )}

          {/* Power Words */}
          {brief.power_words && brief.power_words.length > 0 && (
            <div>
              <p className="text-[9px] text-gray-400 font-medium mb-1.5">パワーワード候補</p>
              <div className="flex flex-wrap gap-1.5">
                {brief.power_words.map((w, i) => (
                  <span key={i} className="text-[10px] px-2 py-1 rounded-full bg-amber-100 text-amber-700 font-medium">{w}</span>
                ))}
              </div>
            </div>
          )}

          {/* Structure timeline */}
          {brief.structure && brief.structure.length > 0 && (
            <div>
              <p className="text-[9px] text-gray-400 font-medium mb-2">構成案</p>
              <div className="relative pl-4">
                <div className="absolute left-[7px] top-1 bottom-1 w-0.5 bg-gray-200" />
                {brief.structure.map((s, i) => (
                  <div key={i} className="relative flex items-start gap-3 mb-3 last:mb-0">
                    <div
                      className="w-3.5 h-3.5 rounded-full shrink-0 -ml-[9px] border-2 border-white shadow-sm"
                      style={{ backgroundColor: structureColors[s.step] || "#94a3b8" }}
                    />
                    <div className="flex-1 min-w-0">
                      <span className="text-[11px] font-bold text-gray-800">{s.label}</span>
                      {i < (brief.structure?.length ?? 0) - 1 && (
                        <span className="text-[9px] text-gray-300 mx-1.5">→</span>
                      )}
                      <p className="text-[10px] text-gray-500 leading-relaxed mt-0.5">{s.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Performance gauge + copy button */}
          <div className="flex items-center gap-4 pt-2 border-t border-gray-100">
            <div className="relative shrink-0">
              <svg width="84" height="84" className="-rotate-90">
                <circle cx="42" cy="42" r={radius} fill="none" stroke="#f3f4f6" strokeWidth="7" />
                <circle
                  cx="42" cy="42" r={radius} fill="none"
                  stroke={scoreColor}
                  strokeWidth="7"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={offset}
                  className="transition-all duration-700"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-[16px] font-bold" style={{ color: scoreColor }}>{score}</span>
                <span className="text-[7px] text-gray-400 font-medium">推定スコア</span>
              </div>
            </div>
            <div className="flex-1">
              <p className="text-[10px] text-gray-500 mb-2">推定パフォーマンス</p>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${score}%`, backgroundColor: scoreColor }} />
              </div>
            </div>
            <button
              onClick={handleCopy}
              className="shrink-0 text-[10px] px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors flex items-center gap-1"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
              </svg>
              クリップボードにコピー
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
