"use client";

import React, { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { platformLabels, platformColors } from "@/lib/constants";

interface SimilarAd {
  ad_id: number;
  similarity?: number;
  product_name?: string;
  title?: string;
  advertiser_name?: string;
  platform?: string;
  hit_score?: number;
  hit_level?: string;
  thumbnail?: string;
  image_url?: string;
  creative_type?: string;
  days_running?: number;
  is_still_running?: boolean;
}

interface SimilarAdsPanelProps {
  adId: number;
  onAdSelect?: (adId: number) => void;
}

export default function SimilarAdsPanel({ adId, onAdSelect }: SimilarAdsPanelProps) {
  const [similar, setSimilar] = useState<SimilarAd[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(false);
      try {
        const res = await fetchApi<{ items?: SimilarAd[]; ads?: SimilarAd[]; similar_ads?: SimilarAd[] }>(
          `/rankings/similar/${adId}`
        );
        const items = res?.items || res?.ads || res?.similar_ads || (Array.isArray(res) ? res : []);
        setSimilar(Array.isArray(items) ? items : []);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    };
    if (adId) load();
  }, [adId]);

  if (loading) {
    return (
      <div className="mt-4 pt-3 border-t border-gray-100">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-3.5 bg-gray-200 rounded w-24 animate-pulse" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-lg border border-gray-100 p-2 animate-pulse">
              <div className="aspect-video bg-gray-100 rounded mb-2" />
              <div className="h-3 bg-gray-200 rounded w-20 mb-1" />
              <div className="h-2.5 bg-gray-100 rounded w-14" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error || similar.length === 0) {
    return null; // Silently hide if no similar ads
  }

  return (
    <div className="mt-4 pt-3 border-t border-gray-100">
      <div className="flex items-center gap-2 mb-3">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
        </svg>
        <h4 className="text-[12px] font-bold text-gray-900">類似広告</h4>
        <span className="text-[10px] text-gray-400">{similar.length}件の類似広告</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {similar.slice(0, 8).map((ad) => {
          const thumbSrc = ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || ad.image_url || "");
          const similarity = ad.similarity != null ? (ad.similarity <= 1 ? Math.round(ad.similarity * 100) : Math.round(ad.similarity)) : null;

          return (
            <div
              key={ad.ad_id}
              className="rounded-lg border border-gray-100 overflow-hidden cursor-pointer hover:shadow-md hover:border-[#4A7DFF]/30 transition-all group"
              onClick={() => onAdSelect?.(ad.ad_id)}
            >
              {/* Thumbnail */}
              <div className="relative aspect-video bg-gray-100">
                {thumbSrc ? (
                  <img
                    src={thumbSrc}
                    alt=""
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    loading="lazy"
                    onError={(e) => {
                      const el = e.target as HTMLImageElement;
                      if (ad.thumbnail && el.src !== ad.thumbnail) el.src = ad.thumbnail;
                      else if (ad.image_url && el.src !== ad.image_url) el.src = ad.image_url;
                      else el.style.display = "none";
                    }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <svg className="w-6 h-6 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                )}
                {/* Similarity badge */}
                {similarity != null && (
                  <span className="absolute top-1 right-1 text-[8px] px-1.5 py-0.5 rounded bg-black/60 text-white font-medium">
                    {similarity}%類似
                  </span>
                )}
                {/* HIT badge */}
                {ad.hit_level === "mega_hit" && (
                  <span className="absolute top-1 left-1 text-[7px] px-1 py-0.5 rounded bg-red-500 text-white font-bold">大HIT</span>
                )}
                {ad.hit_level === "hit" && (
                  <span className="absolute top-1 left-1 text-[7px] px-1 py-0.5 rounded bg-orange-500 text-white font-bold">HIT</span>
                )}
                {/* Running indicator */}
                {ad.is_still_running && (
                  <span className="absolute bottom-1 right-1 w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-white" />
                )}
              </div>

              {/* Info */}
              <div className="px-2 py-1.5">
                <p className="text-[10px] font-medium text-gray-900 truncate" title={ad.product_name || ad.title}>
                  {ad.product_name || ad.title || `Ad #${ad.ad_id}`}
                </p>
                <div className="flex items-center gap-1 mt-0.5">
                  {ad.platform && (
                    <span className={`platform-icon ${platformColors[ad.platform] || "bg-gray-400"} text-[7px]`}>
                      {platformLabels[ad.platform] || ad.platform}
                    </span>
                  )}
                  <span className="text-[10px] font-semibold text-[#4A7DFF] ml-auto">{ad.hit_score || 0}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
