"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchApi } from "@/lib/api";
import EmptyState from "@/components/common/EmptyState";
import { setDemoMode } from "@/lib/demoData";

type NotificationKind = "alert" | "new_ad" | "analysis_complete" | "system";

interface NotificationItem {
  id: number;
  type: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string | null;
  ad_id?: number | null;
  action_url?: string | null;
}

interface NotificationApiResponse {
  notifications?: NotificationItem[];
  unread_count?: number;
}

interface LocalToastItem {
  id?: number;
  title?: string;
  body?: string;
  description?: string;
  type?: string;
  read?: boolean;
  is_read?: boolean;
  ad_id?: number;
  created_at?: string;
}

interface NotificationCenterProps {
  onViewAll: () => void;
  onAdSelect?: (adId: number) => void;
}

const TYPE_STYLES: Record<NotificationKind, string> = {
  alert: "bg-red-100 text-red-600",
  new_ad: "bg-green-100 text-green-700",
  analysis_complete: "bg-blue-100 text-blue-700",
  system: "bg-gray-100 text-gray-600",
};

function normalizeType(value: string): NotificationKind {
  const lower = (value || "").toLowerCase();
  if (["new_ad", "new-hit", "new_hit", "hit_alert"].includes(lower)) return "new_ad";
  if (["analysis_complete", "ranking_update", "crawl_complete"].includes(lower)) return "analysis_complete";
  if (["alert", "critical", "warning", "error", "new_hit", "trend_spike"].includes(lower)) return "alert";
  return "system";
}

function timeAgo(iso?: string | null): string {
  if (!iso) return "just now";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.max(0, Math.floor(diffMs / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function normalizeLocalToNotification(row: LocalToastItem, idx: number): NotificationItem {
  const rawId = typeof row.id === "number" ? row.id : Date.now() + idx;
  return {
    id: rawId,
    type: row.type || "system",
    title: row.title || "Notification",
    body: row.body || row.description || "",
    read: Boolean(row.read ?? row.is_read),
    created_at: row.created_at || new Date().toISOString(),
    ad_id: typeof row.ad_id === "number" ? row.ad_id : null,
    action_url: null,
  };
}

function BellIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
    </svg>
  );
}

export default function NotificationCenter({ onViewAll, onAdSelect }: NotificationCenterProps) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchApi<NotificationApiResponse>("/rankings/notifications", {
        params: { page: 1, per_page: 20, unread_only: 0 },
      });
      const list = Array.isArray(data.notifications) ? data.notifications : [];
      setNotifications(list);
      setUnreadCount(typeof data.unread_count === "number" ? data.unread_count : list.filter((n) => !n.read).length);
    } catch {
      const raw = localStorage.getItem("vaap-toast-history") || "[]";
      const rows = JSON.parse(raw) as LocalToastItem[];
      const fallback = Array.isArray(rows) ? rows.slice(0, 20).map(normalizeLocalToNotification) : [];
      setNotifications(fallback);
      setUnreadCount(fallback.filter((n) => !n.read).length);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 60000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    const onDocClick = (event: MouseEvent) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const markRead = useCallback(async (id: number) => {
    try {
      await fetchApi(`/rankings/notifications/${id}/read`, { method: "PUT" });
    } catch {
      // local-only fallback update below
    }
    setNotifications((prev) => prev.map((row) => (row.id === id ? { ...row, read: true } : row)));
    setUnreadCount((prev) => Math.max(0, prev - 1));
  }, []);

  const markAllRead = useCallback(async () => {
    try {
      await fetchApi("/rankings/notifications/read-all", { method: "PUT" });
    } catch {
      // local-only fallback update below
    }
    setNotifications((prev) => prev.map((row) => ({ ...row, read: true })));
    setUnreadCount(0);
  }, []);

  const visibleItems = useMemo(() => notifications.slice(0, 20), [notifications]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-label="通知"
        className="relative w-9 h-9 rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-colors"
      >
        <div className="flex items-center justify-center">
          <BellIcon />
        </div>
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[10px] leading-4 font-semibold text-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-50 w-80 rounded-xl border border-gray-200 bg-white shadow-xl">
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100">
            <p className="text-[13px] font-semibold text-gray-900">通知</p>
            <button
              type="button"
              onClick={markAllRead}
              className="text-[11px] font-medium text-blue-600 hover:text-blue-700"
            >
              すべて既読
            </button>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {visibleItems.length === 0 ? (
              <EmptyState
                icon="alert"
                title="通知はありません"
                description="新しいアラートや更新がここに表示されます。"
                showDemo
                onDemo={() => setDemoMode(true)}
              />
            ) : (
              visibleItems.map((item) => {
                const kind = normalizeType(item.type);
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => {
                      if (!item.read) {
                        void markRead(item.id);
                      }
                      if (item.ad_id && onAdSelect) {
                        onAdSelect(item.ad_id);
                        setOpen(false);
                        return;
                      }
                      if (item.action_url) {
                        window.location.href = item.action_url;
                      }
                    }}
                    className={`w-full text-left px-3 py-2.5 border-b border-gray-100 hover:bg-gray-50 transition-colors ${item.read ? "" : "bg-blue-50/40"}`}
                  >
                    <div className="flex items-start gap-2.5">
                      <span className={`mt-0.5 inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px] ${TYPE_STYLES[kind]}`}>
                        {kind === "alert" ? "!" : kind === "new_ad" ? "+" : kind === "analysis_complete" ? "i" : "s"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          {!item.read && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />}
                          <p className="truncate text-[12px] font-medium text-gray-900">{item.title}</p>
                        </div>
                        {item.body ? <p className="mt-0.5 line-clamp-2 text-[11px] text-gray-500">{item.body}</p> : null}
                        <p className="mt-1 text-[10px] text-gray-400">{timeAgo(item.created_at)}</p>
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          <div className="px-3 py-2 border-t border-gray-100">
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onViewAll();
              }}
              className="w-full text-center text-[12px] font-medium text-blue-600 hover:text-blue-700"
            >
              Open notification center
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
