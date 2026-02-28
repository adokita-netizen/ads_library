"use client";

import React, { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface VisualLabel {
  name: string;
  confidence: number;
}

interface TextDetection {
  text: string;
  confidence: number;
}

interface FaceAnalysis {
  emotion: string;
  confidence: number;
  age_range?: { low: number; high: number };
  gender?: string;
}

interface CreativeIntelligenceData {
  labels?: VisualLabel[];
  text_detections?: TextDetection[];
  faces?: FaceAnalysis[];
  sentiment?: string;
  key_phrases?: string[];
  moderation_labels?: { name: string; confidence: number }[];
}

interface CreativeIntelligenceProps {
  adId: number;
}

const sentimentColors: Record<string, { bg: string; text: string; label: string }> = {
  positive: { bg: "bg-emerald-100", text: "text-emerald-700", label: "ポジティブ" },
  negative: { bg: "bg-red-100", text: "text-red-700", label: "ネガティブ" },
  neutral: { bg: "bg-gray-100", text: "text-gray-600", label: "ニュートラル" },
  mixed: { bg: "bg-amber-100", text: "text-amber-700", label: "ミックス" },
};

const emotionLabels: Record<string, string> = {
  happy: "喜び",
  sad: "悲しみ",
  angry: "怒り",
  confused: "困惑",
  disgusted: "嫌悪",
  surprised: "驚き",
  calm: "落ち着き",
  fear: "恐怖",
};

export default function CreativeIntelligence({ adId }: CreativeIntelligenceProps) {
  const [data, setData] = useState<CreativeIntelligenceData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchApi<CreativeIntelligenceData>(`/rankings/creative-intelligence/${adId}`)
      .then((res) => setData(res))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [adId]);

  if (loading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-32" />
        <div className="h-20 bg-gray-100 rounded" />
        <div className="h-16 bg-gray-100 rounded" />
      </div>
    );
  }

  if (!data) return null;

  const labels = data.labels || [];
  const texts = data.text_detections || [];
  const faces = data.faces || [];
  const phrases = data.key_phrases || [];
  const sentiment = data.sentiment ? sentimentColors[data.sentiment] || sentimentColors.neutral : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
        <h4 className="text-[12px] font-bold text-gray-900">クリエイティブ分析（AI）</h4>
        {sentiment && (
          <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${sentiment.bg} ${sentiment.text}`}>
            {sentiment.label}
          </span>
        )}
      </div>

      {/* Visual Labels */}
      {labels.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-400 mb-1.5">検出された視覚要素</p>
          <div className="space-y-1">
            {labels.slice(0, 8).map((label, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-[10px] text-gray-700 w-20 truncate shrink-0">{label.name}</span>
                <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[#4A7DFF] transition-all"
                    style={{ width: `${label.confidence}%` }}
                  />
                </div>
                <span className="text-[9px] text-gray-400 w-8 text-right shrink-0">{Math.round(label.confidence)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Text Detections (OCR) */}
      {texts.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-400 mb-1.5">検出テキスト（OCR）</p>
          <div className="flex flex-wrap gap-1">
            {texts.slice(0, 10).map((t, i) => (
              <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-100">
                {t.text}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Face/Emotion Analysis */}
      {faces.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-400 mb-1.5">顔・表情分析</p>
          <div className="flex flex-wrap gap-1.5">
            {faces.map((face, i) => (
              <div key={i} className="flex items-center gap-1 px-2 py-1 rounded-lg bg-purple-50 border border-purple-100">
                <span className="text-[10px] font-medium text-purple-700">
                  {emotionLabels[face.emotion] || face.emotion}
                </span>
                <span className="text-[9px] text-purple-400">{Math.round(face.confidence)}%</span>
                {face.age_range && (
                  <span className="text-[8px] text-purple-400">({face.age_range.low}-{face.age_range.high}歳)</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Key Phrases */}
      {phrases.length > 0 && (
        <div>
          <p className="text-[10px] text-gray-400 mb-1.5">キーフレーズ</p>
          <div className="flex flex-wrap gap-1">
            {phrases.map((phrase, i) => (
              <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-100">
                {phrase}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
