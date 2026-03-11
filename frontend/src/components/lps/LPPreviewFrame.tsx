"use client";

import { useState } from "react";

interface LPPreviewFrameProps {
  mirrorUrl: string;
  fidelityScore?: number;
  fidelityLevel?: string;
  originalDomain?: string;
  capturedAt?: string;
}

type DeviceMode = "desktop" | "tablet" | "mobile";

const DEVICE_WIDTHS: Record<DeviceMode, number> = {
  desktop: 1280,
  tablet: 768,
  mobile: 375,
};

const DEVICE_LABELS: Record<DeviceMode, string> = {
  desktop: "デスクトップ",
  tablet: "タブレット",
  mobile: "モバイル",
};

function getFidelityColor(score: number): string {
  if (score >= 0.7) return "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300";
  if (score >= 0.3) return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300";
  return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
}

export default function LPPreviewFrame({
  mirrorUrl,
  fidelityScore,
  fidelityLevel,
  originalDomain,
  capturedAt,
}: LPPreviewFrameProps) {
  const [device, setDevice] = useState<DeviceMode>("desktop");
  const [loading, setLoading] = useState(true);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-2.5 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shrink-0">
        {/* Device toggle */}
        <div className="flex items-center gap-1 rounded-lg border border-gray-200 dark:border-gray-700 p-0.5">
          {(Object.keys(DEVICE_WIDTHS) as DeviceMode[]).map((d) => (
            <button
              key={d}
              onClick={() => setDevice(d)}
              className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors ${
                device === d
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              {DEVICE_LABELS[d]} ({DEVICE_WIDTHS[d]}px)
            </button>
          ))}
        </div>

        {/* Fidelity badge */}
        {fidelityScore !== undefined && (
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${getFidelityColor(fidelityScore)}`}>
            忠実度: {(fidelityScore * 100).toFixed(0)}%
            {fidelityLevel && ` (${fidelityLevel})`}
          </span>
        )}

        {/* Domain & date info */}
        <div className="ml-auto flex items-center gap-3 text-[11px] text-gray-400 dark:text-gray-500">
          {originalDomain && (
            <span className="flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
              </svg>
              {originalDomain}
            </span>
          )}
          {capturedAt && (
            <span className="flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {new Date(capturedAt).toLocaleDateString("ja-JP")}
            </span>
          )}
        </div>
      </div>

      {/* Iframe container */}
      <div className="flex-1 overflow-auto bg-gray-100 dark:bg-gray-800 flex justify-center p-4">
        <div
          className="relative bg-white dark:bg-gray-950 shadow-lg rounded-lg overflow-hidden transition-all duration-300"
          style={{ width: `${DEVICE_WIDTHS[device]}px`, maxWidth: "100%", height: "100%" }}
        >
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white dark:bg-gray-950 z-10">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
                <p className="text-[12px] text-gray-400 dark:text-gray-500">プレビューを読み込み中...</p>
              </div>
            </div>
          )}
          <iframe
            src={mirrorUrl}
            className="w-full h-full border-0"
            sandbox="allow-same-origin"
            referrerPolicy="no-referrer"
            title="LPプレビュー"
            onLoad={() => setLoading(false)}
          />
        </div>
      </div>
    </div>
  );
}
