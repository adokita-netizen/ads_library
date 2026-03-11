"use client";

import { useState } from "react";

interface LPEvidencePanelProps {
  snapshotId: number;
  screenshots: {
    mobile?: string;
    desktop?: string;
    fullpage?: string;
  };
}

type ScreenshotTab = "mobile" | "desktop" | "fullpage";

const TAB_LABELS: Record<ScreenshotTab, string> = {
  mobile: "モバイル",
  desktop: "デスクトップ",
  fullpage: "フルページ",
};

export default function LPEvidencePanel({ snapshotId, screenshots }: LPEvidencePanelProps) {
  const availableTabs = (Object.keys(TAB_LABELS) as ScreenshotTab[]).filter(
    (t) => screenshots[t]
  );
  const [activeTab, setActiveTab] = useState<ScreenshotTab>(availableTabs[0] || "desktop");
  const [zoomedImage, setZoomedImage] = useState<string | null>(null);
  const [compareMode, setCompareMode] = useState(false);

  if (availableTabs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-gray-400 dark:text-gray-500">
        <svg className="w-12 h-12 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
        </svg>
        <p className="text-[13px] font-medium">スクリーンショットなし</p>
        <p className="text-[11px] mt-1">スナップショット #{snapshotId} にはスクリーンショットが含まれていません</p>
      </div>
    );
  }

  const currentImage = screenshots[activeTab];

  return (
    <div className="flex flex-col h-full">
      {/* Tabs & controls */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shrink-0">
        <div className="flex items-center gap-1 rounded-lg border border-gray-200 dark:border-gray-700 p-0.5">
          {availableTabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors ${
                activeTab === tab
                  ? "bg-blue-600 text-white shadow-sm"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>

        {/* Compare mode toggle - show only if both mobile and desktop exist */}
        {screenshots.mobile && screenshots.desktop && (
          <button
            onClick={() => setCompareMode(!compareMode)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors border ${
              compareMode
                ? "border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400"
                : "border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800"
            }`}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
            </svg>
            比較モード
          </button>
        )}
      </div>

      {/* Screenshot display */}
      <div className="flex-1 overflow-auto bg-gray-100 dark:bg-gray-800 p-4">
        {compareMode && screenshots.mobile && screenshots.desktop ? (
          <div className="flex gap-4 justify-center">
            <div className="flex flex-col items-center gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">モバイル</span>
              <img
                src={screenshots.mobile}
                alt="モバイル スクリーンショット"
                className="max-w-[375px] rounded-lg shadow-md border border-gray-200 dark:border-gray-700 cursor-pointer hover:opacity-90 transition-opacity"
                onClick={() => setZoomedImage(screenshots.mobile!)}
              />
            </div>
            <div className="flex flex-col items-center gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">デスクトップ</span>
              <img
                src={screenshots.desktop}
                alt="デスクトップ スクリーンショット"
                className="max-w-[640px] rounded-lg shadow-md border border-gray-200 dark:border-gray-700 cursor-pointer hover:opacity-90 transition-opacity"
                onClick={() => setZoomedImage(screenshots.desktop!)}
              />
            </div>
          </div>
        ) : (
          currentImage && (
            <div className="flex justify-center">
              <img
                src={currentImage}
                alt={`${TAB_LABELS[activeTab]} スクリーンショット`}
                className="max-w-full rounded-lg shadow-md border border-gray-200 dark:border-gray-700 cursor-pointer hover:opacity-90 transition-opacity"
                onClick={() => setZoomedImage(currentImage)}
              />
            </div>
          )
        )}
      </div>

      {/* Zoom modal */}
      {zoomedImage && (
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 p-8"
          onClick={() => setZoomedImage(null)}
        >
          <button
            className="absolute top-4 right-4 p-2 rounded-full bg-white/10 text-white hover:bg-white/20 transition-colors"
            onClick={() => setZoomedImage(null)}
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <img
            src={zoomedImage}
            alt="拡大表示"
            className="max-w-full max-h-full object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}
