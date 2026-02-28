"use client";

import React, { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface LPDetail {
  ad_id: number;
  product_name?: string;
  lp_score?: number;
  alignment_score?: number;
  screenshot_url?: string;
  elements?: Record<string, boolean>;
  destination_url?: string;
}

interface LPComparisonProps {
  adIds: number[];
}

const elementLabels: Record<string, string> = {
  form: "フォーム", cta: "CTA", testimonials: "口コミ", video: "動画",
  price: "価格表示", countdown: "カウントダウン", faq: "FAQ",
  guarantee: "保証", comparison: "比較表", steps: "ステップ説明",
  hero_image: "ヒーロー画像", social_proof: "社会的証明",
};

export default function LPComparison({ adIds }: LPComparisonProps) {
  const [details, setDetails] = useState<LPDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);

  useEffect(() => {
    if (adIds.length < 2) {
      setDetails([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all(
      adIds.slice(0, 3).map((id) =>
        fetchApi<LPDetail>(`/rankings/lp-analysis/${id}`)
          .then((res) => ({ ...res, ad_id: id }))
          .catch(() => ({ ad_id: id } as LPDetail))
      )
    )
      .then(setDetails)
      .finally(() => setLoading(false));
  }, [adIds]);

  if (loading) {
    return (
      <div className="card px-4 py-4 animate-pulse space-y-3">
        <div className="h-4 bg-gray-200 rounded w-28" />
        <div className="flex gap-3">
          {[1, 2].map((i) => (
            <div key={i} className="flex-1">
              <div className="aspect-[3/4] bg-gray-100 rounded mb-2" />
              <div className="h-3 bg-gray-200 rounded w-20" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (details.length < 2) {
    return (
      <div className="card px-4 py-8 text-center">
        <p className="text-[11px] text-gray-400">2件以上の広告を選択してLP比較を表示</p>
      </div>
    );
  }

  // Collect all element keys
  const allElements = new Set<string>();
  details.forEach((d) => {
    if (d.elements) Object.keys(d.elements).forEach((k) => allElements.add(k));
  });
  const elementKeys = Array.from(allElements).sort();

  const getScoreColor = (score: number | undefined) => {
    if (score == null) return "#94a3b8";
    if (score >= 80) return "#22c55e";
    if (score >= 50) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
        </svg>
        <h4 className="text-[12px] font-bold text-gray-900">LP比較</h4>
      </div>

      {/* Screenshots side by side */}
      <div className={`grid gap-3 ${details.length === 2 ? "grid-cols-2" : "grid-cols-3"}`}>
        {details.map((d) => {
          const screenshotSrc = d.screenshot_url || (d.ad_id ? `/api/v1/media/lp-screenshot/${d.ad_id}` : "");
          return (
            <div key={d.ad_id} className="space-y-2">
              <p className="text-[10px] font-medium text-gray-700 truncate">{d.product_name || `広告 #${d.ad_id}`}</p>
              <div
                className="relative aspect-[3/4] bg-gray-100 rounded-lg overflow-hidden cursor-pointer group"
                onClick={() => screenshotSrc && setLightboxUrl(screenshotSrc)}
              >
                {screenshotSrc && (
                  <img
                    src={screenshotSrc}
                    alt=""
                    className="w-full h-full object-cover object-top group-hover:opacity-90 transition-opacity"
                    loading="lazy"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                )}
                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/20">
                  <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607zM10.5 7.5v6m3-3h-6" />
                  </svg>
                </div>
              </div>
              {/* Scores */}
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1">
                  <span className="text-[9px] text-gray-400">LP</span>
                  <span className="text-[11px] font-bold" style={{ color: getScoreColor(d.lp_score) }}>
                    {d.lp_score ?? "-"}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[9px] text-gray-400">整合性</span>
                  <span className="text-[11px] font-bold" style={{ color: getScoreColor(d.alignment_score) }}>
                    {d.alignment_score ?? "-"}%
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Element checklist comparison */}
      {elementKeys.length > 0 && (
        <div className="card px-4 py-3">
          <h5 className="text-[10px] font-bold text-gray-900 mb-2">LP要素比較</h5>
          <table className="w-full">
            <thead>
              <tr>
                <th className="text-[9px] text-gray-400 text-left pb-1 w-24">要素</th>
                {details.map((d) => (
                  <th key={d.ad_id} className="text-[9px] text-gray-400 text-center pb-1">
                    {d.product_name ? d.product_name.slice(0, 6) : `#${d.ad_id}`}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {elementKeys.map((key) => (
                <tr key={key} className="border-t border-gray-50">
                  <td className="text-[9px] text-gray-600 py-1">{elementLabels[key] || key}</td>
                  {details.map((d) => {
                    const has = d.elements?.[key];
                    return (
                      <td key={d.ad_id} className="text-center py-1">
                        {has ? (
                          <span className="text-emerald-500 text-[11px]">✓</span>
                        ) : (
                          <span className="text-gray-300 text-[11px]">-</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Lightbox */}
      {lightboxUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setLightboxUrl(null)}
        >
          <div className="relative max-w-3xl max-h-[90vh] overflow-auto rounded-lg">
            <img src={lightboxUrl} alt="" className="w-full" />
            <button
              className="absolute top-2 right-2 w-8 h-8 rounded-full bg-white/90 flex items-center justify-center text-gray-600 hover:bg-white transition-colors"
              onClick={() => setLightboxUrl(null)}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
