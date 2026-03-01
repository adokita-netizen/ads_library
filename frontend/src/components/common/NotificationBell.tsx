"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { fetchApi } from "@/lib/api";

/* ─── Types ─── */

type NotificationType = "hit_alert" | "crawl_complete" | "ranking_update" | "system";

interface Notification {
  id: number;
  type: NotificationType;
  title: string;
  description: string;
  ad_id?: number | null;
  is_read: boolean;
  created_at: string;
}

interface NotificationBellProps {
  onViewAll: () => void;
  onAdSelect?: (adId: number) => void;
}

/* ─── Mock data ─── */

const MOCK_NOTIFICATIONS: Notification[] = [
  { id: 1, type: "hit_alert", title: "新しいヒット広告を検出", description: "「美容液A」がヒットラインを超えました", ad_id: 101, is_read: false, created_at: new Date(Date.now() - 5 * 60_000).toISOString() },
  { id: 2, type: "crawl_complete", title: "クロール完了", description: "Meta広告ライブラリの巡回が完了しました（32件取得）", ad_id: null, is_read: false, created_at: new Date(Date.now() - 30 * 60_000).toISOString() },
  { id: 3, type: "ranking_update", title: "ランキング更新", description: "「健康食品」ジャンルのランキングが更新されました", ad_id: null, is_read: true, created_at: new Date(Date.now() - 2 * 3600_000).toISOString() },
  { id: 4, type: "system", title: "システムメンテナンス", description: "明日02:00-04:00にメンテナンスを実施します", ad_id: null, is_read: true, created_at: new Date(Date.now() - 24 * 3600_000).toISOString() },
];

/* ─── Helpers ─── */

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "たった今";
  if (mins < 60) return `${mins}分前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}時間前`;
  const days = Math.floor(hours / 24);
  return `${days}日前`;
}

function TypeIcon({ type }: { type: NotificationType }) {
  switch (type) {
    case "hit_alert":
      return (
        <div className="w-7 h-7 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
          <svg className="w-3.5 h-3.5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
          </svg>
        </div>
      );
    case "crawl_complete":
      return (
        <div className="w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
          <svg className="w-3.5 h-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
      );
    case "ranking_update":
      return (
        <div className="w-7 h-7 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
          <svg className="w-3.5 h-3.5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
        </div>
      );
    case "system":
      return (
        <div className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center shrink-0">
          <svg className="w-3.5 h-3.5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </div>
      );
  }
}

/* ─── Component ─── */

export default function NotificationBell({ onViewAll, onAdSelect }: NotificationBellProps) {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  /* Fetch recent notifications */
  const fetchRecent = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchApi<{ items?: Notification[]; notifications?: Notification[] }>(
        "/notifications/recent",
        { params: { limit: 10 } },
      );
      const items = res.items || res.notifications || (Array.isArray(res) ? (res as Notification[]) : []);
      setNotifications(items);
      setUnreadCount(items.filter((n) => !n.is_read).length);
    } catch {
      // API not available -- use mock data
      setNotifications(MOCK_NOTIFICATIONS);
      setUnreadCount(MOCK_NOTIFICATIONS.filter((n) => !n.is_read).length);
    } finally {
      setLoading(false);
    }
  }, []);

  /* Fetch unread count (lightweight polling) */
  const fetchUnreadCount = useCallback(async () => {
    try {
      const res = await fetchApi<{ count?: number; unread_count?: number }>("/notifications/unread-count");
      const count = res.count ?? res.unread_count ?? 0;
      setUnreadCount(count);
    } catch {
      // Silently ignore -- keep current count
    }
  }, []);

  /* Load on first open */
  useEffect(() => {
    if (open) fetchRecent();
  }, [open, fetchRecent]);

  /* 30-second polling for unread count */
  useEffect(() => {
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 30_000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  /* Click outside to close */
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  /* Mark all as read */
  const markAllRead = async () => {
    try {
      await fetchApi("/notifications/mark-all-read", { method: "POST" });
    } catch {
      // Optimistic UI update even if API fails
    }
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
  };

  /* Handle notification click */
  const handleClick = (n: Notification) => {
    if (n.ad_id && onAdSelect) {
      onAdSelect(n.ad_id);
      setOpen(false);
    }
  };

  return (
    <div ref={ref} className="relative">
      {/* Bell button */}
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="relative p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        aria-label="通知"
      >
        <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 flex items-center justify-center rounded-full bg-red-500 text-white text-[9px] font-bold px-1 leading-none">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-[360px] bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-700">
            <h3 className="text-[13px] font-semibold text-gray-900 dark:text-gray-100">通知</h3>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="text-[11px] text-[#4A7DFF] hover:text-[#3A6AEE] font-medium transition-colors"
              >
                すべて既読
              </button>
            )}
          </div>

          {/* Notification list */}
          <div className="max-h-[400px] overflow-y-auto">
            {loading ? (
              <div className="p-6 text-center">
                <div className="inline-block w-5 h-5 border-2 border-gray-200 border-t-[#4A7DFF] rounded-full animate-spin" />
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-10 text-center">
                <svg className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
                </svg>
                <p className="text-[12px] text-gray-400 dark:text-gray-500">通知はありません</p>
              </div>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleClick(n)}
                  className={`w-full text-left flex items-start gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors ${
                    !n.is_read ? "bg-blue-50/40 dark:bg-blue-900/10" : ""
                  } ${n.ad_id ? "cursor-pointer" : "cursor-default"}`}
                >
                  <TypeIcon type={n.type} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {!n.is_read && (
                        <span className="w-1.5 h-1.5 rounded-full bg-[#4A7DFF] shrink-0" />
                      )}
                      <p className="text-[12px] font-medium text-gray-900 dark:text-gray-100 truncate">
                        {n.title}
                      </p>
                    </div>
                    <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                      {n.description}
                    </p>
                    <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-1">
                      {timeAgo(n.created_at)}
                    </p>
                  </div>
                </button>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-gray-100 dark:border-gray-700 px-4 py-2.5">
            <button
              onClick={() => {
                setOpen(false);
                onViewAll();
              }}
              className="w-full text-center text-[12px] text-[#4A7DFF] hover:text-[#3A6AEE] font-medium transition-colors"
            >
              すべての通知を見る &rarr;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
