"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

interface TeamMember {
  id: number;
  name: string;
  role: string;
  email: string;
  lastActive: string;
}

interface SharedItem {
  id: number;
  type: string;
  title: string;
  author: string;
  createdAt: string;
  views: number;
}

export default function TeamSpaceView() {
  const [activeSection, setActiveSection] = useState<"members" | "shared">("shared");
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [sharedItems, setSharedItems] = useState<SharedItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchApi<{
        members?: TeamMember[];
        shared_items?: SharedItem[];
      }>("/rankings/team-activity");
      if (data.members) setMembers(data.members);
      if (data.shared_items) setSharedItems(data.shared_items);
    } catch {
      // API unavailable - show empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">チームスペース</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">チームメンバーとの共同作業・共有スペース</p>
        </div>
      </div>

      <div className="flex gap-0 px-5 border-b border-gray-200 bg-[#f8f9fc]">
        {([
          { id: "shared" as const, label: "共有アイテム" },
          { id: "members" as const, label: "メンバー管理" },
        ]).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveSection(tab.id)}
            className={`px-4 py-2.5 text-[12px] font-medium border-b-2 transition-colors ${
              activeSection === tab.id
                ? "border-[#4A7DFF] text-[#4A7DFF] bg-white"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar p-5">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-6 h-6 border-2 border-[#4A7DFF] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : activeSection === "shared" ? (
          <div className="space-y-3">
            {sharedItems.length === 0 ? (
              <p className="text-[12px] text-gray-400 text-center py-8">共有アイテムはありません</p>
            ) : (
              sharedItems.map((item) => (
                <div key={item.id} className="card hover:shadow-md transition-shadow cursor-pointer">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="badge text-[9px] bg-blue-100 text-blue-700">{item.type}</span>
                      <div>
                        <p className="text-[12px] font-medium text-gray-900">{item.title}</p>
                        <p className="text-[10px] text-gray-400">{item.author} · {item.createdAt}</p>
                      </div>
                    </div>
                    <span className="text-[10px] text-gray-400">{item.views}回閲覧</span>
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {members.length === 0 ? (
              <p className="text-[12px] text-gray-400 text-center py-8">メンバーはまだいません</p>
            ) : (
              members.map((m) => (
                <div key={m.id} className="card">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-full bg-[#4A7DFF] flex items-center justify-center text-white text-[12px] font-bold">
                      {m.name[0]}
                    </div>
                    <div className="flex-1">
                      <p className="text-[12px] font-medium text-gray-900">{m.name}</p>
                      <p className="text-[10px] text-gray-400">{m.email}</p>
                    </div>
                    <span className="badge text-[9px] bg-gray-100 text-gray-600">{m.role}</span>
                    <span className="text-[10px] text-gray-400">最終: {m.lastActive}</span>
                  </div>
                </div>
              ))
            )}
            <button className="btn-primary text-xs mt-2">
              <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              メンバーを招待
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
