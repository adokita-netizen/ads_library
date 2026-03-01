"use client";

import { useState, useEffect, useCallback, useRef } from "react";

interface FeatureTooltipProps {
  featureId: string;
  message: string;
  children: React.ReactNode;
}

const STORAGE_PREFIX = "vaap_tooltip_";
const AUTO_HIDE_MS = 5000;

export default function FeatureTooltip({
  featureId,
  message,
  children,
}: FeatureTooltipProps) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const storageKey = `${STORAGE_PREFIX}${featureId}`;

  const dismiss = useCallback(() => {
    setVisible(false);
    try {
      localStorage.setItem(storageKey, "true");
    } catch {
      // ignore
    }
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, [storageKey]);

  useEffect(() => {
    try {
      const seen = localStorage.getItem(storageKey);
      if (seen !== "true") {
        setVisible(true);
        timerRef.current = setTimeout(() => {
          dismiss();
        }, AUTO_HIDE_MS);
      }
    } catch {
      // localStorage unavailable
    }

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [storageKey, dismiss]);

  return (
    <div className="relative inline-block">
      {children}

      {visible && (
        <div
          className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 z-50 cursor-pointer"
          onClick={dismiss}
        >
          <div className="relative bg-blue-50 border border-blue-100 rounded-lg px-3 py-2 shadow-sm whitespace-nowrap">
            <span className="text-[11px] text-blue-700 leading-tight">
              {message}
            </span>
            {/* Arrow pointing down */}
            <div className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[6px] border-t-blue-50" />
          </div>
        </div>
      )}
    </div>
  );
}
