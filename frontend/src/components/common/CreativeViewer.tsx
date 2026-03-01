"use client";

import { useState, useMemo, useCallback, useEffect } from "react";

interface CreativeViewerProps {
  imageUrl?: string | null;
  videoUrl?: string | null;
  snapshotUrl?: string | null;
  thumbnailUrl?: string | null;
  creativeType?: string | null;
  // B36: S3 key support
  imageS3Key?: string | null;
  carouselUrls?: string[] | null;
  extractionStatus?: string | null;
  adId?: number | null;
}

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  completed: { label: "抽出完了", color: "bg-green-500" },
  enriched: { label: "強化済", color: "bg-green-500" },
  pending: { label: "待機中", color: "bg-yellow-500" },
  pending_heavy: { label: "待機中", color: "bg-yellow-500" },
  dispatched: { label: "実行中", color: "bg-blue-500" },
  failed: { label: "失敗", color: "bg-red-500" },
};

export function CreativeViewer({
  imageUrl,
  videoUrl,
  snapshotUrl,
  thumbnailUrl,
  creativeType,
  imageS3Key,
  carouselUrls,
  extractionStatus,
  adId,
}: CreativeViewerProps) {
  const [expanded, setExpanded] = useState(false);
  const [carouselIndex, setCarouselIndex] = useState(0);
  const [extracting, setExtracting] = useState(false);
  const [extractedUrl, setExtractedUrl] = useState<string | null>(null);

  // B36: Build fallback chain with S3 proxy priority
  const s3ProxyUrl = useMemo(() => {
    if (imageS3Key) return `/api/v1/media/images/${encodeURIComponent(imageS3Key)}`;
    if (adId) return `/api/v1/media/thumbnail/${adId}`;
    return null;
  }, [imageS3Key, adId]);

  const fallbackSources = useMemo(
    () => [s3ProxyUrl, imageUrl, thumbnailUrl].filter((s): s is string => !!s),
    [s3ProxyUrl, imageUrl, thumbnailUrl],
  );
  const [fallbackIndex, setFallbackIndex] = useState(0);

  // Reset fallback when sources change
  useEffect(() => {
    setFallbackIndex(0);
  }, [imageUrl, thumbnailUrl, imageS3Key, adId]);

  const currentSrc = fallbackSources[fallbackIndex] || null;
  const imgFailed = fallbackIndex >= fallbackSources.length;

  const handleImageError = useCallback(() => {
    if (fallbackIndex + 1 < fallbackSources.length) {
      setFallbackIndex((prev) => prev + 1);
    } else {
      setFallbackIndex(fallbackSources.length);
    }
  }, [fallbackIndex, fallbackSources.length]);

  // B36: Carousel images
  const carousel = useMemo(() => carouselUrls?.filter(Boolean) || [], [carouselUrls]);
  const hasCarousel = carousel.length > 1;

  const badge = extractionStatus ? STATUS_BADGE[extractionStatus] : null;

  const isVideo = videoUrl || creativeType === "video";

  // 1. Video
  if (isVideo && videoUrl) {
    const videoSrc = adId ? `/api/v1/media/video/${adId}` : videoUrl;
    return (
      <div className="rounded-lg overflow-hidden bg-gray-100 relative">
        <video
          src={videoSrc}
          controls
          playsInline
          preload="metadata"
          poster={thumbnailUrl || undefined}
          crossOrigin="anonymous"
          className="w-full max-h-[400px] object-contain"
        />
        {badge && (
          <span className={`absolute top-2 right-2 px-1.5 py-0.5 rounded text-[9px] font-bold text-white ${badge.color}`}>
            {badge.label}
          </span>
        )}
      </div>
    );
  }

  // 2. Carousel
  if (hasCarousel) {
    return (
      <div className="rounded-lg overflow-hidden bg-gray-100 relative">
        <img
          src={carousel[carouselIndex]}
          alt={`Carousel ${carouselIndex + 1}/${carousel.length}`}
          className="w-full max-h-[400px] object-contain cursor-pointer"
          loading="lazy"
          onClick={() => setExpanded(true)}
          onError={() => {
            if (carouselIndex + 1 < carousel.length) setCarouselIndex(carouselIndex + 1);
          }}
        />
        {/* Carousel nav */}
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1">
          {carousel.map((_, i) => (
            <button
              key={i}
              onClick={() => setCarouselIndex(i)}
              className={`w-2 h-2 rounded-full transition-colors ${i === carouselIndex ? "bg-white" : "bg-white/50"}`}
            />
          ))}
        </div>
        {carousel.length > 1 && (
          <>
            <button
              onClick={() => setCarouselIndex((carouselIndex - 1 + carousel.length) % carousel.length)}
              className="absolute left-1 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-black/30 text-white flex items-center justify-center text-sm hover:bg-black/50"
            >
              &lt;
            </button>
            <button
              onClick={() => setCarouselIndex((carouselIndex + 1) % carousel.length)}
              className="absolute right-1 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-black/30 text-white flex items-center justify-center text-sm hover:bg-black/50"
            >
              &gt;
            </button>
          </>
        )}
        {badge && (
          <span className={`absolute top-2 right-2 px-1.5 py-0.5 rounded text-[9px] font-bold text-white ${badge.color}`}>
            {badge.label}
          </span>
        )}
        {expanded && (
          <div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4"
            onClick={() => setExpanded(false)}
          >
            <img
              src={carousel[carouselIndex]}
              alt="Expanded carousel"
              className="max-w-full max-h-full object-contain rounded-lg"
            />
          </div>
        )}
      </div>
    );
  }

  // 3. Image with fallback chain
  if (currentSrc && !imgFailed) {
    return (
      <>
        <div
          className="rounded-lg overflow-hidden bg-gray-100 cursor-pointer relative"
          onClick={() => setExpanded(true)}
        >
          <img
            src={currentSrc}
            alt={creativeType || "Ad creative"}
            className="w-full max-h-[400px] object-contain"
            loading="lazy"
            onError={handleImageError}
          />
          {badge && (
            <span className={`absolute top-2 right-2 px-1.5 py-0.5 rounded text-[9px] font-bold text-white ${badge.color}`}>
              {badge.label}
            </span>
          )}
        </div>

        {expanded && (
          <div
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4"
            onClick={() => setExpanded(false)}
          >
            <img
              src={currentSrc}
              alt={creativeType || "Ad creative"}
              className="max-w-full max-h-full object-contain rounded-lg"
            />
          </div>
        )}
      </>
    );
  }

  // 4. Snapshot (Facebook ads library link) — show preview card with extract option
  if (snapshotUrl) {
    const handleExtract = async () => {
      if (!adId || extracting) return;
      setExtracting(true);
      try {
        const res = await fetch(`/api/v1/ads/${adId}/extract-media`, { method: "POST" });
        if (res.ok) {
          const data = await res.json();
          if (data.thumbnail_url || data.image_url) {
            setExtractedUrl(data.thumbnail_url || data.image_url);
          }
        }
      } catch {
        // ignore
      } finally {
        setExtracting(false);
      }
    };

    // If extraction succeeded, show the image
    if (extractedUrl) {
      return (
        <div className="rounded-lg overflow-hidden bg-gray-100 relative">
          {badge && (
            <span className={`absolute top-2 right-2 z-10 px-1.5 py-0.5 rounded text-[9px] font-bold text-white ${badge.color}`}>
              {badge.label}
            </span>
          )}
          <img
            src={extractedUrl}
            alt="Ad creative"
            className="w-full max-h-[400px] object-contain cursor-pointer"
            onClick={() => setExpanded(true)}
          />
          <div className="flex items-center justify-end px-3 py-1.5 bg-gray-100 border-t border-gray-200">
            <a
              href={snapshotUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-blue-500 hover:text-blue-700"
            >
              広告ライブラリで確認
            </a>
          </div>
          {expanded && (
            <div
              className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4"
              onClick={() => setExpanded(false)}
            >
              <img src={extractedUrl} alt="Ad creative" className="max-w-full max-h-full object-contain rounded-lg" />
            </div>
          )}
        </div>
      );
    }

    // Default: show snapshot card with link + extract button
    return (
      <div className="rounded-lg overflow-hidden bg-gray-50 border border-gray-200 relative">
        {badge && (
          <span className={`absolute top-2 right-2 z-10 px-1.5 py-0.5 rounded text-[9px] font-bold text-white ${badge.color}`}>
            {badge.label}
          </span>
        )}
        <div className="p-6 text-center space-y-3">
          <svg
            className="w-10 h-10 mx-auto text-gray-300"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"
            />
          </svg>
          <div className="flex items-center justify-center gap-2">
            <a
              href={snapshotUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#4A7DFF] text-white text-[12px] font-medium hover:bg-[#3a6ae8] transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
              広告を確認する
            </a>
            {adId && (
              <button
                onClick={handleExtract}
                disabled={extracting}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gray-600 text-white text-[12px] font-medium hover:bg-gray-700 transition-colors disabled:opacity-50"
              >
                {extracting ? (
                  <div className="animate-spin w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full" />
                ) : (
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                )}
                画像を取得
              </button>
            )}
          </div>
          <p className="text-[10px] text-gray-400">
            クリエイティブ画像が未取得です
          </p>
        </div>
      </div>
    );
  }

  // 5. Placeholder with creative type
  return (
    <div className="rounded-lg overflow-hidden bg-gray-100 flex flex-col items-center justify-center py-10 relative">
      {badge && (
        <span className={`absolute top-2 right-2 px-1.5 py-0.5 rounded text-[9px] font-bold text-white ${badge.color}`}>
          {badge.label}
        </span>
      )}
      <svg
        className="w-12 h-12 text-gray-300 mb-2"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1}
      >
        {creativeType === "video" ? (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z"
          />
        ) : (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"
          />
        )}
      </svg>
      <p className="text-[11px] text-gray-400">
        {imgFailed ? "画像を読み込めません" : "クリエイティブなし"}
      </p>
    </div>
  );
}
