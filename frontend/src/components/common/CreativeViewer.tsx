"use client";

import { useState, useMemo, useCallback } from "react";

interface CreativeViewerProps {
  imageUrl?: string | null;
  videoUrl?: string | null;
  snapshotUrl?: string | null;
  thumbnailUrl?: string | null;
  creativeType?: string | null;
}

export function CreativeViewer({
  imageUrl,
  videoUrl,
  snapshotUrl,
  thumbnailUrl,
  creativeType,
}: CreativeViewerProps) {
  const [expanded, setExpanded] = useState(false);

  // B7: Fallback chain for image sources
  const fallbackSources = useMemo(
    () => [imageUrl, thumbnailUrl].filter((s): s is string => !!s),
    [imageUrl, thumbnailUrl],
  );
  const [fallbackIndex, setFallbackIndex] = useState(0);
  const currentSrc = fallbackSources[fallbackIndex] || null;
  const imgFailed = fallbackIndex >= fallbackSources.length;

  const handleImageError = useCallback(() => {
    if (fallbackIndex + 1 < fallbackSources.length) {
      setFallbackIndex((prev) => prev + 1);
    } else {
      setFallbackIndex(fallbackSources.length); // mark all failed
    }
  }, [fallbackIndex, fallbackSources.length]);

  const isVideo = videoUrl || creativeType === "video";

  // 1. Video
  if (isVideo && videoUrl) {
    return (
      <div className="rounded-lg overflow-hidden bg-gray-100">
        <video
          src={videoUrl}
          controls
          playsInline
          preload="metadata"
          poster={thumbnailUrl || undefined}
          crossOrigin="anonymous"
          className="w-full max-h-[400px] object-contain"
        />
      </div>
    );
  }

  // 2. Image with fallback chain
  if (currentSrc && !imgFailed) {
    return (
      <>
        <div
          className="rounded-lg overflow-hidden bg-gray-100 cursor-pointer"
          onClick={() => setExpanded(true)}
        >
          <img
            src={currentSrc}
            alt={creativeType || "Ad creative"}
            className="w-full max-h-[400px] object-contain"
            loading="lazy"
            onError={handleImageError}
          />
        </div>

        {/* Expanded overlay */}
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

  // 3. Snapshot (Facebook ads library link)
  if (snapshotUrl) {
    return (
      <div className="rounded-lg overflow-hidden bg-gray-50 border border-gray-200 p-6 text-center">
        <svg
          className="w-10 h-10 mx-auto text-gray-300 mb-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
          />
        </svg>
        <a
          href={snapshotUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#4A7DFF] text-white text-[12px] font-medium hover:bg-[#3a6ae8] transition-colors"
        >
          <svg
            className="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
            />
          </svg>
          広告を確認する
        </a>
        <p className="text-[10px] text-gray-400 mt-2">外部サイトで広告を表示します</p>
      </div>
    );
  }

  // 4. Placeholder with creative type
  return (
    <div className="rounded-lg overflow-hidden bg-gray-100 flex flex-col items-center justify-center py-10">
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
