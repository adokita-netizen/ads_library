"use client";

import React, { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface PredictionData {
  probability?: number;
  hit_probability?: number;
  positive_factors?: string[];
  negative_factors?: string[];
  recommendation?: string;
  improvements?: string[];
  confidence?: number;
}

interface HitPredictionProps {
  adId: number;
}

export default function HitPrediction({ adId }: HitPredictionProps) {
  const [data, setData] = useState<PredictionData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchApi<PredictionData>(`/rankings/predict-hit/${adId}`)
      .then((res) => setData(res))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [adId]);

  if (loading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-28" />
        <div className="h-24 bg-gray-100 rounded" />
      </div>
    );
  }

  if (!data) return null;

  const probability = data.probability ?? data.hit_probability ?? 0;
  const level = probability >= 80 ? "high" : probability >= 50 ? "moderate" : "low";
  const levelConfig = {
    high: { color: "#22c55e", bg: "bg-emerald-50", text: "text-emerald-700", label: "HIGH HIT POTENTIAL", ring: "ring-emerald-200" },
    moderate: { color: "#f59e0b", bg: "bg-amber-50", text: "text-amber-700", label: "MODERATE", ring: "ring-amber-200" },
    low: { color: "#ef4444", bg: "bg-red-50", text: "text-red-700", label: "LOW", ring: "ring-red-200" },
  }[level];

  const positives = data.positive_factors || [];
  const negatives = data.negative_factors || [];
  const improvements = data.improvements || [];

  // SVG gauge
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (probability / 100) * circumference;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
        </svg>
        <h4 className="text-[12px] font-bold text-gray-900">ヒット予測</h4>
      </div>

      <div className="flex items-center gap-4">
        {/* Probability gauge */}
        <div className="relative shrink-0">
          <svg width="96" height="96" className="-rotate-90">
            <circle cx="48" cy="48" r={radius} fill="none" stroke="#f3f4f6" strokeWidth="8" />
            <circle
              cx="48" cy="48" r={radius} fill="none"
              stroke={levelConfig.color}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              className="transition-all duration-700"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[18px] font-bold" style={{ color: levelConfig.color }}>
              {Math.round(probability)}%
            </span>
            <span className="text-[7px] font-bold text-gray-400">HIT確率</span>
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <span className={`inline-block text-[10px] font-bold px-2 py-0.5 rounded ${levelConfig.bg} ${levelConfig.text} mb-2`}>
            {levelConfig.label}
          </span>
          {data.recommendation && (
            <p className="text-[10px] text-gray-600 leading-relaxed">{data.recommendation}</p>
          )}
          {data.confidence != null && (
            <p className="text-[9px] text-gray-400 mt-1">信頼度: {Math.round(data.confidence)}%</p>
          )}
        </div>
      </div>

      {/* Positive / Negative factors */}
      {(positives.length > 0 || negatives.length > 0) && (
        <div className="grid grid-cols-2 gap-2">
          {positives.length > 0 && (
            <div>
              <p className="text-[9px] text-gray-400 mb-1">強み</p>
              <div className="flex flex-wrap gap-1">
                {positives.map((f, i) => (
                  <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-100">
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}
          {negatives.length > 0 && (
            <div>
              <p className="text-[9px] text-gray-400 mb-1">弱み</p>
              <div className="flex flex-wrap gap-1">
                {negatives.map((f, i) => (
                  <span key={i} className="text-[9px] px-1.5 py-0.5 rounded bg-red-50 text-red-600 border border-red-100">
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Improvement suggestions */}
      {improvements.length > 0 && (
        <div>
          <p className="text-[9px] text-gray-400 mb-1">改善提案</p>
          <ul className="space-y-1">
            {improvements.map((tip, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="text-[9px] text-[#4A7DFF] mt-0.5 shrink-0">●</span>
                <span className="text-[10px] text-gray-600 leading-relaxed">{tip}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
