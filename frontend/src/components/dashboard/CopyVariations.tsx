"use client";

import React, { useState } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";

// ─── Types ───

interface Variation {
  text: string;
  effectiveness: number;
  hook_type?: string;
}

interface CopyVariationsProps {
  initialText?: string;
}

// ─── Options ───

const hookTypeOptions = [
  { value: "question", label: "質問" },
  { value: "number", label: "数字" },
  { value: "problem", label: "問題提起" },
  { value: "shock", label: "衝撃" },
  { value: "empathy", label: "共感" },
];

const toneOptions = [
  { value: "casual", label: "カジュアル" },
  { value: "professional", label: "専門的" },
  { value: "urgent", label: "緊急" },
];

const lengthOptions = [
  { value: "short", label: "短い" },
  { value: "standard", label: "標準" },
  { value: "long", label: "長い" },
];

// ─── Mock generator ───

function generateMockVariations(original: string): Variation[] {
  const hooks: { prefix: string; type: string; score: number }[] = [
    { prefix: "まだ知らないの？", type: "question", score: 82 },
    { prefix: "【驚愕】たった3日で変わった…", type: "shock", score: 76 },
    { prefix: "97%が効果を実感。", type: "number", score: 88 },
    { prefix: "その悩み、放置すると危険です。", type: "problem", score: 71 },
    { prefix: "「私も同じでした」", type: "empathy", score: 65 },
  ];
  const base = original.length > 60 ? original.slice(0, 60) + "..." : original;
  return hooks.map((h) => ({
    text: `${h.prefix} ${base}`,
    effectiveness: h.score,
    hook_type: h.type,
  }));
}

const hookLabel: Record<string, string> = {
  question: "質問",
  number: "数字",
  problem: "問題提起",
  shock: "衝撃",
  empathy: "共感",
};

export default function CopyVariations({ initialText }: CopyVariationsProps) {
  const [original, setOriginal] = useState(initialText || "");
  const [hookType, setHookType] = useState("question");
  const [tone, setTone] = useState("casual");
  const [length, setLength] = useState("standard");
  const [loading, setLoading] = useState(false);
  const [variations, setVariations] = useState<Variation[]>([]);

  const handleGenerate = async () => {
    if (!original.trim()) {
      toast.error("広告テキストを入力してください");
      return;
    }
    setLoading(true);
    try {
      const res = await fetchApi<{ variations?: Variation[]; items?: Variation[] }>("/rankings/copy-variations", {
        method: "POST",
        body: {
          text: original,
          hook_type: hookType,
          tone,
          length,
        },
      });
      const items = res?.variations || res?.items || (Array.isArray(res) ? res : []);
      setVariations(Array.isArray(items) ? items : []);
      toast.success("バリエーションを生成しました");
    } catch {
      setVariations(generateMockVariations(original));
      toast("サンプルデータを表示しています", { icon: "ℹ️" });
    } finally {
      setLoading(false);
    }
  };

  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("コピーしました");
  };

  return (
    <div className="card px-4 py-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">コピーバリエーション生成</h3>
        <span className="text-[9px] text-gray-400">広告文を複数パターンに展開</span>
      </div>

      {/* Original text input */}
      <div>
        <label className="text-[9px] text-gray-400 block mb-1">元の広告テキスト</label>
        <textarea
          value={original}
          onChange={(e) => setOriginal(e.target.value)}
          rows={3}
          placeholder="バリエーションを生成したい広告テキストを入力してください..."
          className="w-full px-3 py-2 text-[11px] border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]/40 bg-white resize-none leading-relaxed"
        />
      </div>

      {/* Config selectors */}
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-[9px] text-gray-400 block mb-1">フックタイプ</label>
          <div className="flex flex-wrap gap-1">
            {hookTypeOptions.map((o) => (
              <button
                key={o.value}
                onClick={() => setHookType(o.value)}
                className={`px-2 py-0.5 rounded-full text-[9px] border transition-colors ${
                  hookType === o.value
                    ? "bg-[#4A7DFF] text-white border-[#4A7DFF]"
                    : "bg-white text-gray-500 border-gray-200 hover:border-[#4A7DFF]/40"
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="text-[9px] text-gray-400 block mb-1">トーン</label>
          <div className="flex flex-wrap gap-1">
            {toneOptions.map((o) => (
              <button
                key={o.value}
                onClick={() => setTone(o.value)}
                className={`px-2 py-0.5 rounded-full text-[9px] border transition-colors ${
                  tone === o.value
                    ? "bg-[#4A7DFF] text-white border-[#4A7DFF]"
                    : "bg-white text-gray-500 border-gray-200 hover:border-[#4A7DFF]/40"
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="text-[9px] text-gray-400 block mb-1">長さ</label>
          <div className="flex flex-wrap gap-1">
            {lengthOptions.map((o) => (
              <button
                key={o.value}
                onClick={() => setLength(o.value)}
                className={`px-2 py-0.5 rounded-full text-[9px] border transition-colors ${
                  length === o.value
                    ? "bg-[#4A7DFF] text-white border-[#4A7DFF]"
                    : "bg-white text-gray-500 border-gray-200 hover:border-[#4A7DFF]/40"
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Generate button */}
      <button onClick={handleGenerate} disabled={loading} className="btn-primary text-[11px] h-8 px-5 w-full flex items-center justify-center gap-1.5">
        {loading ? (
          <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
        ) : (
          <>
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
            </svg>
            バリエーション生成
          </>
        )}
      </button>

      {/* Variations display */}
      {variations.length > 0 && (
        <div className="border-t border-gray-100 pt-4 space-y-2.5">
          <p className="text-[9px] text-gray-400 font-medium">生成結果 ({variations.length}件)</p>
          {variations.map((v, i) => {
            const barColor = v.effectiveness >= 80 ? "#22c55e" : v.effectiveness >= 60 ? "#f59e0b" : "#ef4444";
            return (
              <div key={i} className="border border-gray-100 rounded-lg p-3 hover:shadow-sm transition-all">
                {/* Score bar + hook label */}
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex items-center gap-1.5 flex-1 min-w-0">
                    <span className="text-[11px] font-bold shrink-0" style={{ color: barColor }}>
                      {v.effectiveness}
                    </span>
                    <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${v.effectiveness}%`, backgroundColor: barColor }}
                      />
                    </div>
                  </div>
                  {v.hook_type && (
                    <span className="text-[8px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 shrink-0">
                      {hookLabel[v.hook_type] || v.hook_type}
                    </span>
                  )}
                </div>

                {/* Variation text */}
                <p className="text-[10px] text-gray-700 leading-relaxed mb-2">{v.text}</p>

                {/* Copy button */}
                <button
                  onClick={() => handleCopyText(v.text)}
                  className="text-[9px] text-gray-400 hover:text-[#4A7DFF] transition-colors flex items-center gap-1"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                  </svg>
                  コピー
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
