"use client";

import { useEffect, useRef, useCallback } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";

/* ─── Types ─── */

interface UnreadCountResponse {
  count?: number;
  unread_count?: number;
  latest?: LatestNotification | null;
}

interface LatestNotification {
  id: number;
  type: string;
  title: string;
  description?: string;
}

/* ─── Icon for toast ─── */

function toastIcon(type: string): string {
  switch (type) {
    case "hit_alert":
      return "\uD83D\uDD25"; // fire
    case "crawl_complete":
      return "\u2705"; // check
    case "ranking_update":
      return "\uD83D\uDCC8"; // chart
    case "system":
      return "\u2699\uFE0F"; // gear
    default:
      return "\uD83D\uDD14"; // bell
  }
}

/* ─── Constants ─── */

const POLL_INTERVAL_MS = 30_000;
const TOAST_DURATION_MS = 5_000;
const MAX_TOASTS = 3;

/* ─── Component ─── */

export function ToastNotificationPoller() {
  const lastCountRef = useRef<number | null>(null);
  const activeToastsRef = useRef(0);
  const mountedRef = useRef(true);

  const pollUnreadCount = useCallback(async () => {
    if (!mountedRef.current) return;

    try {
      const res = await fetchApi<UnreadCountResponse>("/notifications/unread-count");
      const currentCount = res.count ?? res.unread_count ?? 0;

      // On first poll, just record the baseline
      if (lastCountRef.current === null) {
        lastCountRef.current = currentCount;
        return;
      }

      // New notifications detected
      if (currentCount > lastCountRef.current && activeToastsRef.current < MAX_TOASTS) {
        const notification = res.latest;
        const title = notification?.title ?? "新しい通知があります";
        const type = notification?.type ?? "system";

        activeToastsRef.current += 1;

        toast(
          (t) => (
            <div className="flex items-center gap-2.5 min-w-[200px]">
              <span className="text-[16px] shrink-0" role="img" aria-label={type}>
                {toastIcon(type)}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-medium text-gray-900 dark:text-gray-100 truncate">
                  {title}
                </p>
              </div>
              <button
                onClick={() => {
                  toast.dismiss(t.id);
                }}
                className="shrink-0 px-2 py-0.5 rounded text-[11px] font-medium text-[#4A7DFF] hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
              >
                見る
              </button>
            </div>
          ),
          {
            duration: TOAST_DURATION_MS,
            position: "bottom-right",
            style: {
              padding: "10px 14px",
              borderRadius: "10px",
              boxShadow: "0 4px 20px rgba(0,0,0,0.12)",
              border: "1px solid rgba(0,0,0,0.06)",
            },
            ariaProps: {
              role: "status",
              "aria-live": "polite",
            },
          },
        );

        // Decrement active toast count after auto-dismiss
        setTimeout(() => {
          if (mountedRef.current) {
            activeToastsRef.current = Math.max(0, activeToastsRef.current - 1);
          }
        }, TOAST_DURATION_MS + 500);
      }

      lastCountRef.current = currentCount;
    } catch {
      // Silently ignore -- API not available
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    // Initial poll
    pollUnreadCount();

    // Set up interval
    const intervalId = setInterval(pollUnreadCount, POLL_INTERVAL_MS);

    return () => {
      mountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [pollUnreadCount]);

  // This component renders nothing -- it only manages polling + toasts
  return null;
}

export default ToastNotificationPoller;
