"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { fetchApi } from "@/lib/api";
import toast from "react-hot-toast";

// ─── Types ───

interface ActivityItem {
  id: string;
  user: string;
  userInitial: string;
  action: string;
  target: string;
  timestamp: string;
}

interface TeamMember {
  id: number;
  name: string;
  initial: string;
  isOnline: boolean;
}

interface WeeklySummary {
  activeMembers: number;
  notes: number;
  collections: number;
}

// ─── Mock Data ───

const MOCK_ACTIVITIES: ActivityItem[] = [
  { id: "a1", user: "田中 太郎", userInitial: "田", action: "コレクションに追加", target: "美容系ヒット集", timestamp: new Date(Date.now() - 15 * 60000).toISOString() },
  { id: "a2", user: "佐藤 花子", userInitial: "佐", action: "メモを追加", target: "スキンケア広告X", timestamp: new Date(Date.now() - 45 * 60000).toISOString() },
  { id: "a3", user: "鈴木 一郎", userInitial: "鈴", action: "新規コレクション作成", target: "ダイエット系Q1", timestamp: new Date(Date.now() - 3 * 3600000).toISOString() },
  { id: "a4", user: "田中 太郎", userInitial: "田", action: "エクスポート", target: "月次レポート2月", timestamp: new Date(Date.now() - 5 * 3600000).toISOString() },
  { id: "a5", user: "佐藤 花子", userInitial: "佐", action: "競合分析を実施", target: "サプリメントA", timestamp: new Date(Date.now() - 8 * 3600000).toISOString() },
  { id: "a6", user: "山田 二郎", userInitial: "山", action: "コレクションに追加", target: "金融系参考", timestamp: new Date(Date.now() - 24 * 3600000).toISOString() },
];

const MOCK_MEMBERS: TeamMember[] = [
  { id: 1, name: "田中 太郎", initial: "田", isOnline: true },
  { id: 2, name: "佐藤 花子", initial: "佐", isOnline: true },
  { id: 3, name: "鈴木 一郎", initial: "鈴", isOnline: false },
  { id: 4, name: "山田 二郎", initial: "山", isOnline: false },
];

const MOCK_SUMMARY: WeeklySummary = { activeMembers: 3, notes: 12, collections: 4 };

// ─── Helpers ───

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "たった今";
  if (mins < 60) return `${mins}分前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}時間前`;
  return `${Math.floor(hours / 24)}日前`;
}

// ─── Component ───

export default function TeamActivity() {
  const [activities, setActivities] = useState<ActivityItem[]>(MOCK_ACTIVITIES);
  const [members, setMembers] = useState<TeamMember[]>(MOCK_MEMBERS);
  const [summary, setSummary] = useState<WeeklySummary>(MOCK_SUMMARY);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const data = await fetchApi<{
        activities?: ActivityItem[];
        members?: TeamMember[];
        summary?: WeeklySummary;
      }>("/rankings/team-activity").catch(() => null);

      if (data) {
        if (data.activities) setActivities(data.activities);
        if (data.members) setMembers(data.members);
        if (data.summary) setSummary(data.summary);
      }
    } catch {
      toast.error("チーム情報の取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const onlineCount = useMemo(() => members.filter((m) => m.isOnline).length, [members]);

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-gray-100 bg-[#f8f9fc] flex items-center justify-between">
        <div>
          <h4 className="text-[12px] font-bold text-gray-900">チームアクティビティ</h4>
          <p className="text-[10px] text-gray-400">チームの最新動向</p>
        </div>
        {loading && (
          <div className="w-3.5 h-3.5 border-2 border-[#4A7DFF] border-t-transparent rounded-full animate-spin" />
        )}
      </div>

      {/* Team member avatars */}
      <div className="px-4 py-2.5 border-b border-gray-100 flex items-center gap-2">
        <div className="flex -space-x-2">
          {members.map((m) => (
            <div key={m.id} className="relative" title={m.name}>
              <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center text-[10px] font-bold text-gray-500 border-2 border-white">
                {m.initial}
              </div>
              <span
                className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-[1.5px] border-white ${
                  m.isOnline ? "bg-green-400" : "bg-gray-300"
                }`}
              />
            </div>
          ))}
        </div>
        <span className="text-[10px] text-gray-500 ml-1">
          {onlineCount}人オンライン
        </span>
      </div>

      {/* Activity feed */}
      <div className="max-h-[220px] overflow-y-auto divide-y divide-gray-100">
        {activities.map((a) => (
          <div key={a.id} className="px-4 py-2.5 hover:bg-gray-50">
            <div className="flex items-start gap-2">
              <div className="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center text-[9px] font-bold text-gray-500 shrink-0 mt-0.5">
                {a.userInitial}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] text-gray-700 leading-relaxed">
                  <span className="font-medium">{a.user}</span>
                  {" が "}
                  <span className="text-[#4A7DFF]">{a.action}</span>
                  {a.target && (
                    <>
                      {": "}
                      <span className="font-medium">{a.target}</span>
                    </>
                  )}
                </p>
                <p className="text-[9px] text-gray-400 mt-0.5">{timeAgo(a.timestamp)}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Weekly summary */}
      <div className="px-4 py-3 border-t border-gray-100 bg-[#f8f9fc]">
        <p className="text-[10px] font-bold text-gray-600 mb-2">今週のサマリー</p>
        <div className="grid grid-cols-3 gap-2">
          <div className="text-center">
            <p className="text-[14px] font-black text-[#4A7DFF]">{summary.activeMembers}</p>
            <p className="text-[9px] text-gray-500">アクティブ</p>
          </div>
          <div className="text-center">
            <p className="text-[14px] font-black text-purple-600">{summary.notes}</p>
            <p className="text-[9px] text-gray-500">メモ</p>
          </div>
          <div className="text-center">
            <p className="text-[14px] font-black text-green-600">{summary.collections}</p>
            <p className="text-[9px] text-gray-500">コレクション</p>
          </div>
        </div>
      </div>
    </div>
  );
}
