"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { fetchApi } from "@/lib/api";

interface AlertItem {
  id: number | string;
  type: string;
  message: string;
  ad_id?: number;
  created_at?: string;
  is_read?: boolean;
}

interface AlertsPanelProps {
  onAdSelect?: (adId: number) => void;
  /** When true, render as full-page panel instead of dropdown popover */
  fullPage?: boolean;
}

const typeIcons: Record<string, { icon: string; color: string; label: string }> = {
  new_hit:    { icon: "★", color: "bg-amber-50 text-amber-700",   label: "新規ヒット広告" },
  high_score: { icon: "↑", color: "bg-red-50 text-red-700",       label: "スコア変動" },
  trend_up:   { icon: "↗", color: "bg-emerald-50 text-emerald-700", label: "スコア変動" },
  mega_hit:   { icon: "◆", color: "bg-purple-50 text-purple-700", label: "大ヒット検出" },
  competitor: { icon: "⚑", color: "bg-blue-50 text-blue-700",     label: "競合アラート" },
  crawl_done: { icon: "✓", color: "bg-gray-50 text-gray-700",     label: "クロール完了" },
};

export default function AlertsPanel({ onAdSelect, fullPage }: AlertsPanelProps) {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const loadAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchApi<{ items?: AlertItem[]; alerts?: AlertItem[] }>("/rankings/alerts");
      const items = res.items || res.alerts || (Array.isArray(res) ? res : []);
      setAlerts(Array.isArray(items) ? items : []);
    } catch {
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load on first open (popover mode) or on mount (full-page mode)
  useEffect(() => {
    if (fullPage) {
      loadAlerts();
    }
  }, [fullPage, loadAlerts]);

  useEffect(() => {
    if (!open || fullPage) return;
    loadAlerts();
  }, [open, fullPage, loadAlerts]);

  // Close popover on outside click
  useEffect(() => {
    if (fullPage) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [fullPage]);

  const unreadCount = alerts.filter((a) => !a.is_read).length;

  const markRead = async (id: number | string) => {
    const alertId = Number(id);
    if (!Number.isFinite(alertId)) return;
    try {
      await fetchApi(`/rankings/alerts/${alertId}/read`, { method: "POST" });
      setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, is_read: true } : a)));
    } catch {
      // Keep current UI state when API request fails.
    }
  };

  const markAllRead = async () => {
    try {
      await fetchApi("/rankings/alerts/read-all", { method: "POST" });
      setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })));
    } catch {
      // Keep current UI state when API request fails.
    }
  };

  const formatTime = (dateStr?: string) => {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    const now = Date.now();
    const diff = now - d.getTime();
    if (diff < 1000 * 60 * 60) return `${Math.max(1, Math.floor(diff / (1000 * 60)))}分前`;
    if (diff < 1000 * 60 * 60 * 24) return `${Math.floor(diff / (1000 * 60 * 60))}時間前`;
    if (diff < 1000 * 60 * 60 * 24 * 7) return `${Math.floor(diff / (1000 * 60 * 60 * 24))}日前`;
    return d.toLocaleDateString("ja-JP", { month: "short", day: "numeric" });
  };

  /* ─── Alert Row ─── */
  const renderAlert = (alert: AlertItem) => {
    const typeInfo = typeIcons[alert.type] || { icon: "●", color: "bg-gray-50 text-gray-700", label: "通知" };
    return (
      <div
        key={alert.id}
        className={`px-4 py-2.5 border-b border-gray-50 hover:bg-gray-50 transition-colors group ${
          !alert.is_read ? "bg-blue-50/30" : ""
        }`}
      >
        <div className="flex items-start gap-2.5">
          <span className={`w-6 h-6 rounded-lg flex items-center justify-center text-[11px] font-bold shrink-0 ${typeInfo.color}`}>
            {typeInfo.icon}
          </span>
          <div
            className={`flex-1 min-w-0 ${alert.ad_id ? "cursor-pointer" : ""}`}
            onClick={() => {
              if (alert.ad_id) {
                onAdSelect?.(alert.ad_id);
                if (!fullPage) setOpen(false);
              }
            }}
          >
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="text-[8px] px-1 py-0.5 rounded bg-gray-100 text-gray-500 font-medium">{typeInfo.label}</span>
              {!alert.is_read && (
                <span className="w-1.5 h-1.5 rounded-full bg-[#4A7DFF]" />
              )}
            </div>
            <p className="text-[11px] text-gray-700 leading-relaxed">{alert.message}</p>
            <div className="flex items-center gap-2 mt-0.5">
              {alert.created_at && (
                <p className="text-[9px] text-gray-400">{formatTime(alert.created_at)}</p>
              )}
              {alert.ad_id && (
                <span className="text-[9px] text-[#4A7DFF] hover:underline">詳細を見る</span>
              )}
            </div>
          </div>
          {!alert.is_read && (
            <button
              onClick={(e) => { e.stopPropagation(); void markRead(alert.id); }}
              className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-600 transition-all p-0.5 shrink-0"
              title="既読にする"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
              </svg>
            </button>
          )}
        </div>
      </div>
    );
  };

  /* ─── Full-page mode ─── */
  if (fullPage) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
            </svg>
            <h2 className="text-[15px] font-bold text-gray-900">お知らせ</h2>
            {unreadCount > 0 && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500 text-white font-bold">{unreadCount}件未読</span>
            )}
          </div>
          {unreadCount > 0 && (
            <button
              onClick={markAllRead}
              className="text-[11px] px-3 py-1.5 rounded-lg text-[#4A7DFF] hover:bg-blue-50 transition-colors font-medium"
            >
              すべて既読にする
            </button>
          )}
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {loading ? (
            <div className="p-5 space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="animate-pulse flex gap-2">
                  <div className="w-6 h-6 rounded bg-gray-200 shrink-0" />
                  <div className="flex-1">
                    <div className="h-3 bg-gray-200 rounded w-full mb-1" />
                    <div className="h-2 bg-gray-100 rounded w-20" />
                  </div>
                </div>
              ))}
            </div>
          ) : alerts.length === 0 ? (
            <div className="py-16 text-center">
              <svg className="w-10 h-10 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
              </svg>
              <p className="text-[12px] text-gray-500">新しい通知はありません</p>
            </div>
          ) : (
            <div>
              {alerts.map(renderAlert)}
            </div>
          )}
        </div>
      </div>
    );
  }

  /* ─── Popover mode (original) ─── */
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="relative h-8 w-8 rounded-lg flex items-center justify-center text-gray-500 hover:bg-gray-100 transition-colors"
        title="通知"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-red-500 text-white text-[8px] font-bold flex items-center justify-center">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-96 bg-white rounded-xl shadow-xl border border-gray-200 z-30 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between">
            <h4 className="text-[12px] font-bold text-gray-900">通知</h4>
            <div className="flex items-center gap-2">
              {alerts.length > 0 && (
                <span className="text-[9px] text-gray-400">{alerts.length}件</span>
              )}
              {unreadCount > 0 && (
                <button
                  onClick={markAllRead}
                  className="text-[9px] text-[#4A7DFF] hover:underline font-medium"
                >
                  すべて既読
                </button>
              )}
            </div>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {loading ? (
              <div className="p-4 space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse flex gap-2">
                    <div className="w-6 h-6 rounded bg-gray-200 shrink-0" />
                    <div className="flex-1">
                      <div className="h-3 bg-gray-200 rounded w-full mb-1" />
                      <div className="h-2 bg-gray-100 rounded w-20" />
                    </div>
                  </div>
                ))}
              </div>
            ) : alerts.length === 0 ? (
              <div className="py-8 text-center">
                <svg className="w-8 h-8 text-gray-300 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
                </svg>
                <p className="text-[11px] text-gray-400">新しい通知はありません</p>
              </div>
            ) : (
              alerts.slice(0, 20).map(renderAlert)
            )}
          </div>
        </div>
      )}
    </div>
  );
}
