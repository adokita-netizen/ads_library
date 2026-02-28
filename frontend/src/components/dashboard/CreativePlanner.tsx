"use client";

import React, { useState } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";

interface PredictionResult {
  probability?: number;
  hit_probability?: number;
  recommendation?: string;
  example_ads?: { ad_id: number; product_name?: string; hit_score?: number; thumbnail?: string }[];
}

interface CreativePlannerProps {
  genre?: string;
  onAdSelect?: (adId: number) => void;
}

const hookOptions = [
  { value: "", label: "選択してください" },
  { value: "question", label: "質問型" },
  { value: "pain_point", label: "悩み訴求" },
  { value: "benefit", label: "ベネフィット" },
  { value: "curiosity", label: "好奇心" },
  { value: "social_proof", label: "社会的証明" },
  { value: "urgency", label: "緊急性" },
  { value: "storytelling", label: "ストーリー" },
  { value: "number", label: "数字訴求" },
];

const ctaOptions = [
  { value: "", label: "選択してください" },
  { value: "purchase", label: "購入" },
  { value: "signup", label: "会員登録" },
  { value: "download", label: "ダウンロード" },
  { value: "inquiry", label: "問い合わせ" },
  { value: "learn_more", label: "詳しく見る" },
  { value: "free_trial", label: "無料体験" },
];

const offerOptions = [
  { value: "", label: "選択してください" },
  { value: "discount", label: "割引" },
  { value: "free_trial", label: "無料体験" },
  { value: "limited_time", label: "期間限定" },
  { value: "bonus", label: "特典付き" },
  { value: "guarantee", label: "返金保証" },
  { value: "comparison", label: "比較優位" },
];

const emotionOptions = [
  { value: "", label: "選択してください" },
  { value: "excitement", label: "ワクワク" },
  { value: "fear", label: "不安・恐怖" },
  { value: "curiosity", label: "好奇心" },
  { value: "trust", label: "安心・信頼" },
  { value: "urgency", label: "焦り" },
  { value: "empathy", label: "共感" },
];

export default function CreativePlanner({ genre, onAdSelect }: CreativePlannerProps) {
  const [hookType, setHookType] = useState("");
  const [ctaType, setCtaType] = useState("");
  const [offerType, setOfferType] = useState("");
  const [emotion, setEmotion] = useState("");
  const [creativeType, setCreativeType] = useState<"video" | "image">("video");
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handlePredict = async () => {
    if (!hookType && !ctaType && !offerType && !emotion) {
      toast.error("少なくとも1つの要素を選択してください");
      return;
    }
    setLoading(true);
    try {
      const body: Record<string, string | undefined> = {
        hook_type: hookType || undefined,
        cta_type: ctaType || undefined,
        offer_type: offerType || undefined,
        emotion: emotion || undefined,
        creative_type: creativeType,
        genre: genre || undefined,
      };
      const res = await fetchApi<PredictionResult>("/rankings/predict-hit", {
        method: "POST",
        body,
      });
      setResult(res);
    } catch {
      toast.error("予測に失敗しました");
    } finally {
      setLoading(false);
    }
  };

  const probability = result?.probability ?? result?.hit_probability ?? 0;
  const level = probability >= 80 ? "high" : probability >= 50 ? "moderate" : "low";
  const levelColor = { high: "#22c55e", moderate: "#f59e0b", low: "#ef4444" }[level];

  return (
    <div className="card px-4 py-4 space-y-4">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">クリエイティブプランナー</h3>
        <span className="text-[9px] text-gray-400">要素を選んでHIT率を予測</span>
      </div>

      {/* Selectors grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        <div>
          <label className="text-[9px] text-gray-400 block mb-0.5">フックタイプ</label>
          <select value={hookType} onChange={(e) => setHookType(e.target.value)} className="select-filter text-[10px] h-7 w-full">
            {hookOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[9px] text-gray-400 block mb-0.5">CTA</label>
          <select value={ctaType} onChange={(e) => setCtaType(e.target.value)} className="select-filter text-[10px] h-7 w-full">
            {ctaOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[9px] text-gray-400 block mb-0.5">オファー</label>
          <select value={offerType} onChange={(e) => setOfferType(e.target.value)} className="select-filter text-[10px] h-7 w-full">
            {offerOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[9px] text-gray-400 block mb-0.5">感情訴求</label>
          <select value={emotion} onChange={(e) => setEmotion(e.target.value)} className="select-filter text-[10px] h-7 w-full">
            {emotionOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[9px] text-gray-400 block mb-0.5">クリエイティブ</label>
          <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5 h-7">
            {(["video", "image"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setCreativeType(t)}
                className={`flex-1 px-2 rounded text-[9px] h-full transition-colors ${
                  creativeType === t ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"
                }`}
              >
                {t === "video" ? "動画" : "静止画"}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-end">
          <button
            onClick={handlePredict}
            disabled={loading}
            className="btn-primary text-[11px] h-7 px-4 w-full flex items-center justify-center gap-1"
          >
            {loading ? (
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                </svg>
                予測する
              </>
            )}
          </button>
        </div>
      </div>

      {/* Result */}
      {result && (
        <div className="border-t border-gray-100 pt-3 space-y-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="text-[22px] font-bold" style={{ color: levelColor }}>
                {Math.round(probability)}%
              </span>
              <span className="text-[10px] text-gray-400">HIT確率</span>
            </div>
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${probability}%`, backgroundColor: levelColor }}
              />
            </div>
          </div>

          {result.recommendation && (
            <div className="bg-blue-50 rounded-lg px-3 py-2">
              <p className="text-[10px] text-blue-700 leading-relaxed">{result.recommendation}</p>
            </div>
          )}

          {/* Example hits */}
          {result.example_ads && result.example_ads.length > 0 && (
            <div>
              <p className="text-[10px] text-gray-400 mb-1.5">同パターンのHIT広告</p>
              <div className="flex gap-2 overflow-x-auto pb-1">
                {result.example_ads.slice(0, 6).map((ad) => {
                  const thumbSrc = ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || "");
                  return (
                    <div
                      key={ad.ad_id}
                      className="shrink-0 w-28 cursor-pointer rounded-lg overflow-hidden border border-gray-200 hover:shadow-md transition-all"
                      onClick={() => onAdSelect?.(ad.ad_id)}
                    >
                      <div className="relative aspect-video bg-gray-100">
                        {thumbSrc && (
                          <img
                            src={thumbSrc}
                            alt=""
                            className="w-full h-full object-cover"
                            loading="lazy"
                            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                          />
                        )}
                        {ad.hit_score != null && (
                          <span className="absolute top-0.5 right-0.5 text-[8px] px-1 py-0.5 rounded bg-black/60 text-white font-bold">
                            {ad.hit_score}
                          </span>
                        )}
                      </div>
                      <p className="text-[9px] text-gray-700 px-1.5 py-1 truncate">{ad.product_name || "不明"}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
