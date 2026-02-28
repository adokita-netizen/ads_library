"use client";

import { useState, useEffect } from "react";
import { adsApi } from "@/lib/api";
import { platformLabels, platformColors } from "@/lib/constants";
import { formatYen, formatNumber } from "@/lib/format";
import { CreativeViewer } from "../common/CreativeViewer";

interface CompareAd {
  id: number;
  title?: string;
  product_name?: string;
  advertiser_name?: string;
  platform?: string;
  genre?: string;
  image_url?: string;
  video_url?: string;
  snapshot_url?: string;
  thumbnail_url?: string;
  creative_type?: string;
  cumulative_spend?: number;
  view_count?: number;
  hit_score?: number;
  trend_score?: number;
  duration_seconds?: number;
  published_date?: string;
  destination_url?: string;
  days_running?: number;
  is_still_running?: boolean;
  estimation_method?: string;
}

interface CreativeCompareViewProps {
  adIds: number[];
  onClose: () => void;
  onAdSelect: (adId: number) => void;
}

export default function CreativeCompareView({ adIds, onClose, onAdSelect }: CreativeCompareViewProps) {
  const [ads, setAds] = useState<CompareAd[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      const results = await Promise.allSettled(
        adIds.slice(0, 3).map((id) => adsApi.get(id))
      );
      const loaded: CompareAd[] = [];
      for (const r of results) {
        if (r.status === "fulfilled" && r.value.data) {
          const d = r.value.data;
          const meta = d.ad_metadata || d.metadata || {};
          loaded.push({
            id: d.id,
            title: d.title || d.product_name,
            product_name: d.product_name || d.title,
            advertiser_name: d.advertiser_name,
            platform: d.platform,
            genre: d.category || d.genre,
            image_url: d.image_url,
            video_url: d.video_url,
            snapshot_url: d.snapshot_url,
            thumbnail_url: d.thumbnail_url,
            creative_type: d.creative_type,
            cumulative_spend: d.cumulative_spend || d.total_spend || 0,
            view_count: d.view_count || d.cumulative_views || 0,
            hit_score: d.hit_score || meta.latest_hit_score || 0,
            trend_score: d.trend_score || 0,
            duration_seconds: d.duration_seconds || d.duration || 0,
            published_date: d.published_date || d.created_at,
            destination_url: d.destination_url,
            days_running: d.days_running || meta.days_running,
            is_still_running: d.is_still_running ?? meta.is_still_running,
            estimation_method: d.estimation_method || meta.estimation_method,
          });
        }
      }
      setAds(loaded);
      setLoading(false);
    };
    fetchAll();
  }, [adIds]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-6 pb-6">
      <div className="relative w-full max-w-6xl max-h-full overflow-hidden rounded-xl bg-white shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className="text-[15px] font-bold text-gray-900">クリエイティブ比較</h2>
            <p className="text-[11px] text-gray-400">{ads.length}件の広告を並列比較</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
              <span className="ml-2 text-xs text-gray-400">読み込み中...</span>
            </div>
          ) : (
            <div className={`grid gap-4 ${ads.length === 2 ? "grid-cols-2" : "grid-cols-3"}`}>
              {ads.map((ad) => {
                const scoreColor =
                  (ad.hit_score || 0) >= 80 ? "#ef4444" : (ad.hit_score || 0) >= 50 ? "#f59e0b" : "#4A7DFF";
                return (
                  <div key={ad.id} className="border border-gray-200 rounded-lg overflow-hidden bg-white">
                    {/* Creative */}
                    <div className="max-h-[220px] overflow-hidden">
                      <CreativeViewer
                        imageUrl={ad.id ? `/api/v1/media/thumbnail/${ad.id}` : (ad.image_url || ad.thumbnail_url || null)}
                        videoUrl={ad.id ? `/api/v1/media/video/${ad.id}` : (ad.video_url || null)}
                        snapshotUrl={ad.snapshot_url || null}
                        thumbnailUrl={ad.id ? `/api/v1/media/thumbnail/${ad.id}` : (ad.thumbnail_url || null)}
                        creativeType={ad.creative_type || null}
                      />
                    </div>

                    {/* Info */}
                    <div className="p-4 space-y-3">
                      {/* Title */}
                      <div>
                        <p className="text-[13px] font-semibold text-gray-900 truncate">{ad.product_name || ad.title || "-"}</p>
                        <p className="text-[10px] text-gray-400 truncate">{ad.advertiser_name || "-"}</p>
                      </div>

                      {/* Tags */}
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {ad.platform && (
                          <span className={`platform-icon ${platformColors[ad.platform] || "bg-gray-400"} text-[8px]`}>
                            {platformLabels[ad.platform] || ad.platform}
                          </span>
                        )}
                        {ad.genre && <span className="badge-blue text-[9px]">{ad.genre}</span>}
                        {ad.estimation_method === "audience_based" && (
                          <span className="badge text-[8px] bg-green-100 text-green-700">実データ</span>
                        )}
                      </div>

                      {/* Hit score */}
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[10px] text-gray-400">ヒットスコア</span>
                          <span className="text-[12px] font-bold" style={{ color: scoreColor }}>{ad.hit_score || 0}</span>
                        </div>
                        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{ width: `${ad.hit_score || 0}%`, backgroundColor: scoreColor }}
                          />
                        </div>
                      </div>

                      {/* Metrics */}
                      <div className="space-y-1.5 text-[11px]">
                        <div className="flex justify-between">
                          <span className="text-gray-400">推定消化額</span>
                          <span className="font-semibold text-gray-900">{formatYen(ad.cumulative_spend || 0)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">推定再生数</span>
                          <span className="font-semibold text-gray-900">{formatNumber(ad.view_count || 0)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">配信日数</span>
                          <span className="text-gray-700">
                            {ad.days_running != null ? `${ad.days_running}日` : ad.published_date ? `${Math.max(1, Math.round((Date.now() - new Date(ad.published_date).getTime()) / 86400000))}日` : "-"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-400">ステータス</span>
                          {ad.is_still_running !== false ? (
                            <span className="font-semibold text-emerald-600">● 配信中</span>
                          ) : (
                            <span className="text-gray-400">○ 終了</span>
                          )}
                        </div>
                        {ad.duration_seconds != null && ad.duration_seconds > 0 && (
                          <div className="flex justify-between">
                            <span className="text-gray-400">動画尺</span>
                            <span className="text-gray-700">{ad.duration_seconds}秒</span>
                          </div>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
                        {ad.destination_url && (
                          <a
                            href={ad.destination_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] px-2 py-1 rounded bg-gray-50 text-[#4A7DFF] hover:bg-blue-50 transition-colors"
                          >
                            LP確認
                          </a>
                        )}
                        <button
                          className="text-[10px] px-2 py-1 rounded bg-gray-50 text-gray-600 hover:bg-gray-100 transition-colors ml-auto"
                          onClick={(e) => { e.stopPropagation(); onAdSelect(ad.id); }}
                        >
                          詳細を見る
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
