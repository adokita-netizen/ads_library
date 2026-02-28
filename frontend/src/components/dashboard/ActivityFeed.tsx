"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

/* ─── Types ─── */

interface ActivityItem {
  id: number;
  type: "new_ad" | "score_change" | "hit_line";
  title: string;
  description: string;
  ad_id?: number;
  timestamp: string;
}

/* ─── Icon by type ─── */

function ActivityIcon({ type }: { type: ActivityItem["type"] }) {
  switch (type) {
    case "new_ad":
      return (
        <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center shrink-0">
          <svg className="w-3 h-3 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
        </div>
      );
    case "score_change":
      return (
        <div className="w-6 h-6 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
          <svg className="w-3 h-3 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22" />
          </svg>
        </div>
      );
    case "hit_line":
      return (
        <div className="w-6 h-6 rounded-full bg-red-100 flex items-center justify-center shrink-0">
          <svg className="w-3 h-3 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
          </svg>
        </div>
      );
  }
}

/* ─── Time format ─── */

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "たった今";
  if (mins < 60) return `${mins}分前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}時間前`;
  const days = Math.floor(hours / 24);
  return `${days}日前`;
}

/* ─── Main Component ─── */

interface ActivityFeedProps {
  onAdSelect?: (adId: number) => void;
}

export default function ActivityFeed({ onAdSelect }: ActivityFeedProps) {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetchApi<{ items?: ActivityItem[]; alerts?: ActivityItem[] }>(
        "/rankings/alerts",
        { params: { limit: 10 } }
      );
      setItems(res.items || res.alerts || []);
    } catch {
      // TODO: API未実装時はモックデータを使用
      const now = new Date();
      setItems([
        {
          id: 1,
          type: "new_ad",
          title: "新規広告検出",
          description: "新規広告検出: 美容液プレミアムケア",
          ad_id: 101,
          timestamp: new Date(now.getTime() - 5 * 60000).toISOString(),
        },
        {
          id: 2,
          type: "score_change",
          title: "スコア変動",
          description: "スコア変動: HealthCorp +15pt",
          ad_id: 202,
          timestamp: new Date(now.getTime() - 23 * 60000).toISOString(),
        },
        {
          id: 3,
          type: "hit_line",
          title: "ヒットライン突破",
          description: "ヒットライン突破: ダイエットサプリX",
          ad_id: 303,
          timestamp: new Date(now.getTime() - 45 * 60000).toISOString(),
        },
        {
          id: 4,
          type: "new_ad",
          title: "新規広告検出",
          description: "新規広告検出: 脱毛サロンLP",
          ad_id: 404,
          timestamp: new Date(now.getTime() - 2 * 3600000).toISOString(),
        },
        {
          id: 5,
          type: "score_change",
          title: "スコア変動",
          description: "スコア変動: BeautyLab -8pt",
          ad_id: 505,
          timestamp: new Date(now.getTime() - 4 * 3600000).toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 30000); // 30秒ごとに自動更新
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      {/* Header - clickable to toggle collapse */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 border-b border-gray-200 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
          </svg>
          <span className="text-[12px] font-semibold text-gray-700">
            アクティビティフィード
          </span>
          {items.length > 0 && (
            <span className="px-1.5 py-0.5 text-[9px] font-bold bg-[#4A7DFF] text-white rounded-full leading-none">
              {items.length}
            </span>
          )}
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${collapsed ? "" : "rotate-180"}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {/* Content */}
      {!collapsed && (
        <div className="max-h-[300px] overflow-y-auto custom-scrollbar">
          {loading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-start gap-3 animate-pulse">
                  <div className="w-6 h-6 bg-gray-200 rounded-full shrink-0" />
                  <div className="flex-1 space-y-1">
                    <div className="h-3 w-3/4 bg-gray-200 rounded" />
                    <div className="h-2.5 w-1/3 bg-gray-100 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="p-6 text-center">
              <p className="text-[11px] text-gray-400">
                最近のアクティビティはありません
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => item.ad_id && onAdSelect?.(item.ad_id)}
                  className="w-full flex items-start gap-3 px-4 py-2.5 hover:bg-gray-50 transition-colors text-left"
                >
                  <ActivityIcon type={item.type} />
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] text-gray-700 truncate">
                      {item.description}
                    </p>
                    <p className="text-[10px] text-gray-400 mt-0.5">
                      {timeAgo(item.timestamp)}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
