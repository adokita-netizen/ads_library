"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import EmptyState from "@/components/common/EmptyState";

/* ─── Types ─── */

type NotificationType = "alert" | "new_ad" | "analysis_complete" | "system";
type FilterTab = "all" | "unread" | "alert" | "system";

interface Notification {
  id: number;
  type: NotificationType;
  title: string;
  body: string;
  ad_id?: number | null;
  read: boolean;
  created_at: string | null;
  action_url?: string | null;
}

interface PaginatedResponse {
  notifications?: Notification[];
  unread_count?: number;
}

interface NotificationListViewProps {
  onAdSelect?: (adId: number) => void;
}

/* ─── Helpers ─── */

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "たった今";
  if (mins < 60) return `${mins}分前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}時間前`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}日前`;
  return new Date(ts).toLocaleDateString("ja-JP", { month: "short", day: "numeric" });
}

function formatFullDate(ts: string): string {
  return new Date(ts).toLocaleString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/* ─── Type Icon ─── */

function TypeIcon({ type, size = "md" }: { type: NotificationType; size?: "sm" | "md" }) {
  const s = size === "sm" ? "w-7 h-7" : "w-9 h-9";
  const iconS = size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4";

  switch (type) {
    case "alert":
      return (
        <div className={`${s} rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center shrink-0`}>
          <svg className={`${iconS} text-amber-600 dark:text-amber-400`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
          </svg>
        </div>
      );
    case "new_ad":
      return (
        <div className={`${s} rounded-full bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center shrink-0`}>
          <svg className={`${iconS} text-emerald-600 dark:text-emerald-400`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
      );
    case "analysis_complete":
      return (
        <div className={`${s} rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0`}>
          <svg className={`${iconS} text-blue-600 dark:text-blue-400`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
        </div>
      );
    case "system":
      return (
        <div className={`${s} rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center shrink-0`}>
          <svg className={`${iconS} text-gray-600 dark:text-gray-400`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </div>
      );
  }
}

/* ─── Filter tabs config ─── */

const FILTER_TABS: { key: FilterTab; label: string }[] = [
  { key: "all", label: "すべて" },
  { key: "unread", label: "未読" },
  { key: "alert", label: "アラート" },
  { key: "system", label: "システム" },
];

/* ─── Skeleton ─── */

function SkeletonCard() {
  return (
    <div className="flex items-start gap-3 px-5 py-4 animate-pulse">
      <div className="w-9 h-9 rounded-full bg-gray-200 dark:bg-gray-700 shrink-0" />
      <div className="flex-1 space-y-2">
        <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-2/3" />
        <div className="h-2.5 bg-gray-200 dark:bg-gray-700 rounded w-full" />
        <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded w-1/4" />
      </div>
    </div>
  );
}

/* ─── Component ─── */

const PER_PAGE = 20;

export default function NotificationListView({ onAdSelect }: NotificationListViewProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<FilterTab>("all");
  const [loading, setLoading] = useState(true);

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  /* Build API filter params */
  const buildParams = useCallback(
    (p: number): Record<string, string | number> => {
      const params: Record<string, string | number> = {
        page: p,
        per_page: PER_PAGE,
        unread_only: 0,
      };
      if (filter === "unread") params.unread_only = 1;
      if (filter === "alert") params.type = "alert";
      if (filter === "system") params.type = "system";
      return params;
    },
    [filter],
  );

  /* Fetch notifications */
  const fetchNotifications = useCallback(
    async (p: number) => {
      setLoading(true);
      try {
        const res = await fetchApi<PaginatedResponse>("/rankings/notifications", {
          params: buildParams(p),
        });
        const items = res.notifications || [];
        setNotifications(items);
        setUnreadCount(res.unread_count ?? items.filter((item) => !item.read).length);
        setTotal(items.length < PER_PAGE && p === 1 ? items.length : Math.max(items.length, p * PER_PAGE));
      } catch {
        const raw = localStorage.getItem("vaap-toast-history") || "[]";
        const rows = JSON.parse(raw) as Array<{
          id?: number;
          title?: string;
          body?: string;
          description?: string;
          type?: string;
          read?: boolean;
          is_read?: boolean;
          ad_id?: number;
          created_at?: string;
        }>;
        const mapped = Array.isArray(rows)
          ? rows.map((row, index) => ({
              id: typeof row.id === "number" ? row.id : Date.now() + index,
              type: (row.type === "hit_alert"
                ? "alert"
                : row.type === "crawl_complete" || row.type === "ranking_update"
                ? "analysis_complete"
                : row.type === "new_ad"
                ? "new_ad"
                : "system") as NotificationType,
              title: row.title || "Notification",
              body: row.body || row.description || "",
              ad_id: typeof row.ad_id === "number" ? row.ad_id : null,
              read: Boolean(row.read ?? row.is_read),
              created_at: row.created_at || new Date().toISOString(),
              action_url: null,
            }))
          : [];
        const filtered = mapped.filter((item) => {
          if (filter === "unread") return !item.read;
          if (filter === "alert") return item.type === "alert";
          if (filter === "system") return item.type === "system";
          return true;
        });
        const pageItems = filtered.slice((p - 1) * PER_PAGE, p * PER_PAGE);
        setNotifications(pageItems);
        setUnreadCount(mapped.filter((item) => !item.read).length);
        setTotal(filtered.length);
      } finally {
        setLoading(false);
      }
    },
    [buildParams, filter],
  );

  useEffect(() => {
    setPage(1);
  }, [filter]);

  useEffect(() => {
    fetchNotifications(page);
  }, [page, fetchNotifications]);

  /* Bulk mark read */
  const markAllRead = async () => {
    try {
      await fetchApi("/rankings/notifications/read-all", { method: "PUT" });
    } catch {
      // Optimistic update
    }
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    setUnreadCount(0);
  };

  /* Handle notification click */
  const handleClick = (n: Notification) => {
    if (!n.read) {
      setNotifications((prev) =>
        prev.map((item) => (item.id === n.id ? { ...item, read: true } : item)),
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
      try {
        fetchApi(`/rankings/notifications/${n.id}/read`, { method: "PUT" }).catch(() => {});
      } catch {
        // ignore
      }
    }
    if (n.ad_id && onAdSelect) {
      onAdSelect(n.ad_id);
      return;
    }
    if (n.action_url) {
      window.location.href = n.action_url;
    }
  };

  const unreadInView = notifications.filter((n) => !n.read).length;

  return (
    <div className="h-full flex flex-col bg-white dark:bg-gray-900">
      {/* Header */}
      <div className="px-5 pt-5 pb-3 border-b border-gray-100 dark:border-gray-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-[16px] font-bold text-gray-900 dark:text-gray-100">
              通知センター
            </h2>
            <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
              {total}件の通知 / 未読 {unreadCount}件
            </p>
          </div>
          {unreadInView > 0 && (
            <button
              onClick={markAllRead}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium text-[#4A7DFF] hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              一括既読
            </button>
          )}
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1">
          {FILTER_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={`px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors ${
                filter === tab.key
                  ? "bg-[#4A7DFF] text-white"
                  : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Notification list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div>
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : notifications.length === 0 ? (
          <EmptyState
            icon="alert"
            title="通知はまだありません"
            description="新しい通知が届くとここに表示されます。"
          />
        ) : (
          notifications.map((n) => (
            <div
              key={n.id}
              onClick={() => handleClick(n)}
              className={`flex items-start gap-3 px-5 py-4 border-b border-gray-50 dark:border-gray-800 transition-colors ${
                !n.read ? "bg-blue-50/30 dark:bg-blue-900/10" : ""
              } ${(n.ad_id || n.action_url) ? "cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/60" : ""}`}
            >
              <TypeIcon type={n.type} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  {!n.read && (
                    <span className="w-2 h-2 rounded-full bg-[#4A7DFF] shrink-0" />
                  )}
                  <p className="text-[13px] font-medium text-gray-900 dark:text-gray-100 truncate">
                    {n.title}
                  </p>
                </div>
                <p className="text-[12px] text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                  {n.body}
                </p>
                <div className="flex items-center gap-2 mt-1.5">
                  <p className="text-[11px] text-gray-400 dark:text-gray-500">
                    {timeAgo(n.created_at || new Date().toISOString())}
                  </p>
                  <span className="text-gray-300 dark:text-gray-600 text-[11px]">|</span>
                  <p className="text-[11px] text-gray-300 dark:text-gray-600">
                    {formatFullDate(n.created_at || new Date().toISOString())}
                  </p>
                </div>
              </div>
              {(n.ad_id || n.action_url) && (
                <div className="shrink-0 mt-1">
                  <svg className="w-4 h-4 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 dark:border-gray-800">
          <p className="text-[11px] text-gray-400 dark:text-gray-500">
            {(page - 1) * PER_PAGE + 1}-{Math.min(page * PER_PAGE, total)} / {total}件
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-2.5 py-1 rounded-md text-[11px] font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              前へ
            </button>
            {Array.from({ length: totalPages }).map((_, i) => {
              const p = i + 1;
              // Show at most 5 page buttons around current page
              if (totalPages > 5 && Math.abs(p - page) > 2 && p !== 1 && p !== totalPages) {
                if (p === page - 3 || p === page + 3) {
                  return (
                    <span key={p} className="text-[11px] text-gray-400 px-1">
                      ...
                    </span>
                  );
                }
                return null;
              }
              return (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-7 h-7 rounded-md text-[11px] font-medium transition-colors ${
                    p === page
                      ? "bg-[#4A7DFF] text-white"
                      : "text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                  }`}
                >
                  {p}
                </button>
              );
            })}
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-2.5 py-1 rounded-md text-[11px] font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              次へ
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
