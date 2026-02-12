"use client";

import { useState } from "react";

const mockMembers = [
  { id: 1, name: "田中 太郎", role: "管理者", email: "tanaka@example.com", lastActive: "2025-12-23" },
  { id: 2, name: "佐藤 花子", role: "分析者", email: "sato@example.com", lastActive: "2025-12-22" },
  { id: 3, name: "鈴木 一郎", role: "クリエイター", email: "suzuki@example.com", lastActive: "2025-12-21" },
];

const mockSharedItems = [
  { id: 1, type: "分析レポート", title: "美容ジャンル 12月競合分析", author: "田中 太郎", createdAt: "2025-12-20", views: 12 },
  { id: 2, type: "クリエイティブ", title: "セラムV3 動画台本案", author: "鈴木 一郎", createdAt: "2025-12-19", views: 8 },
  { id: 3, type: "LP設計", title: "ダイエットX USP→LP導線", author: "佐藤 花子", createdAt: "2025-12-18", views: 5 },
];

export default function TeamSpaceView() {
  const [activeSection, setActiveSection] = useState<"members" | "shared">("shared");

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
        {activeSection === "shared" && (
          <div className="space-y-3">
            {mockSharedItems.map((item) => (
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
            ))}
          </div>
        )}

        {activeSection === "members" && (
          <div className="space-y-3">
            {mockMembers.map((m) => (
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
            ))}
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
