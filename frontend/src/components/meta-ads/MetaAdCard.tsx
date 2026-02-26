"use client";

import type { MetaAd } from "@/types";
import { metaMarketingApi } from "@/lib/api";
import StatusToggle from "./StatusToggle";

interface Props {
  ad: MetaAd;
  onRefresh?: () => void;
}

export default function MetaAdCard({ ad, onRefresh }: Props) {
  const thumbnailUrl = ad.creative_thumbnail_url || ad.creative_image_url;

  return (
    <div className="card p-3 hover:shadow-md transition-shadow">
      {/* Thumbnail */}
      <div className="aspect-video bg-gray-100 rounded-lg mb-2 overflow-hidden relative">
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={ad.name}
            className="w-full h-full object-cover"
            loading="lazy"
            onError={(e) => {
              const target = e.target as HTMLImageElement;
              target.style.display = "none";
              // Show fallback text
              const parent = target.parentElement;
              if (parent) {
                const fallback = document.createElement("div");
                fallback.className = "w-full h-full flex items-center justify-center text-gray-400 text-[11px]";
                fallback.textContent = "画像読み込み失敗";
                parent.appendChild(fallback);
              }
            }}
          />
        ) : ad.creative_video_url ? (
          <div className="w-full h-full flex items-center justify-center bg-gray-800 text-white text-[11px]">
            動画広告
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-400 text-[11px]">
            プレビューなし
          </div>
        )}
        {/* Status toggle */}
        <div className="absolute top-2 right-2">
          <StatusToggle
            currentStatus={ad.effective_status}
            entityType="ad"
            entityName={ad.name}
            onStatusChange={async (newStatus) => {
              await metaMarketingApi.updateAdStatus(ad.meta_id, { status: newStatus });
              onRefresh?.();
            }}
          />
        </div>
      </div>

      {/* Info */}
      <div className="space-y-1">
        <p className="text-[12px] font-medium text-gray-800 truncate" title={ad.name}>
          {ad.name}
        </p>

        {ad.creative_title && (
          <p className="text-[11px] text-gray-600 truncate" title={ad.creative_title}>
            {ad.creative_title}
          </p>
        )}

        {ad.creative_body && (
          <p className="text-[10px] text-gray-400 line-clamp-2">{ad.creative_body}</p>
        )}

        <div className="flex items-center gap-2 pt-1">
          {ad.creative_type && (
            <span className="text-[9px] px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">
              {ad.creative_type}
            </span>
          )}
          <span className="text-[10px] text-gray-400">{ad.meta_id}</span>
        </div>

        {ad.creative_link_url && (
          <a
            href={ad.creative_link_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-blue-500 hover:underline truncate block"
          >
            {ad.creative_link_url}
          </a>
        )}
      </div>
    </div>
  );
}
