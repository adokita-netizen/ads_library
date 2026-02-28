"use client";

import React, { useState, useEffect } from "react";
import toast from "react-hot-toast";

interface Preferences {
  notifications: { newHit: boolean; scoreChange: boolean; competitor: boolean; crawlComplete: boolean };
  display: { itemsPerPage: number; defaultSort: string; defaultPeriod: string };
  autoRefresh: { enabled: boolean; interval: number };
  theme: "light" | "dark";
}

const defaultPrefs: Preferences = {
  notifications: { newHit: true, scoreChange: true, competitor: false, crawlComplete: true },
  display: { itemsPerPage: 20, defaultSort: "score", defaultPeriod: "weekly" },
  autoRefresh: { enabled: true, interval: 60 },
  theme: "light",
};

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center justify-between py-1.5 cursor-pointer group">
      <span className="text-[11px] text-gray-700 group-hover:text-gray-900 transition-colors">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-8 h-4.5 rounded-full transition-colors ${checked ? "bg-[#4A7DFF]" : "bg-gray-300"}`}
        style={{ width: 32, height: 18 }}
      >
        <span
          className="absolute top-0.5 left-0.5 w-3.5 h-3.5 rounded-full bg-white shadow transition-transform"
          style={{ width: 14, height: 14, transform: checked ? "translateX(14px)" : "translateX(0)" }}
        />
      </button>
    </label>
  );
}

export default function UserPreferences() {
  const [prefs, setPrefs] = useState<Preferences>(defaultPrefs);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("user_preferences");
      if (saved) setPrefs({ ...defaultPrefs, ...JSON.parse(saved) });
    } catch {}
  }, []);

  const update = (fn: (p: Preferences) => Preferences) => setPrefs((p) => fn(p));

  const handleSave = () => {
    try {
      localStorage.setItem("user_preferences", JSON.stringify(prefs));
      toast.success("設定を保存しました");
    } catch {
      toast.error("設定の保存に失敗しました");
    }
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center justify-between">
        <h2 className="text-[14px] font-bold text-gray-900">ユーザー設定</h2>
        <button onClick={handleSave} className="btn-primary text-[11px] px-4 py-1.5">保存</button>
      </div>

      {/* Notification settings */}
      <div className="card px-4 py-3 space-y-1">
        <h3 className="text-[12px] font-bold text-gray-900 mb-2">通知設定</h3>
        <Toggle label="新規ヒット広告" checked={prefs.notifications.newHit} onChange={(v) => update((p) => ({ ...p, notifications: { ...p.notifications, newHit: v } }))} />
        <Toggle label="スコア変動" checked={prefs.notifications.scoreChange} onChange={(v) => update((p) => ({ ...p, notifications: { ...p.notifications, scoreChange: v } }))} />
        <Toggle label="競合アラート" checked={prefs.notifications.competitor} onChange={(v) => update((p) => ({ ...p, notifications: { ...p.notifications, competitor: v } }))} />
        <Toggle label="クロール完了" checked={prefs.notifications.crawlComplete} onChange={(v) => update((p) => ({ ...p, notifications: { ...p.notifications, crawlComplete: v } }))} />
      </div>

      {/* Display settings */}
      <div className="card px-4 py-3 space-y-3">
        <h3 className="text-[12px] font-bold text-gray-900">表示設定</h3>
        <div>
          <p className="text-[10px] text-gray-400 mb-1.5">表示件数</p>
          <div className="flex items-center gap-1">
            {[10, 20, 50].map((n) => (
              <button key={n} onClick={() => update((p) => ({ ...p, display: { ...p.display, itemsPerPage: n } }))}
                className={`px-3 py-1 rounded text-[10px] transition-colors ${prefs.display.itemsPerPage === n ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600"}`}
              >{n}件</button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-[10px] text-gray-400 mb-1.5">デフォルトソート</p>
          <select value={prefs.display.defaultSort} onChange={(e) => update((p) => ({ ...p, display: { ...p.display, defaultSort: e.target.value } }))} className="select-filter text-[10px] h-7">
            <option value="score">スコア順</option>
            <option value="views">再生数順</option>
            <option value="spend">消化額順</option>
            <option value="recent">最新順</option>
          </select>
        </div>
        <div>
          <p className="text-[10px] text-gray-400 mb-1.5">デフォルト期間</p>
          <select value={prefs.display.defaultPeriod} onChange={(e) => update((p) => ({ ...p, display: { ...p.display, defaultPeriod: e.target.value } }))} className="select-filter text-[10px] h-7">
            <option value="daily">日次</option>
            <option value="weekly">週次</option>
            <option value="monthly">月次</option>
            <option value="all">全期間</option>
          </select>
        </div>
      </div>

      {/* Auto refresh */}
      <div className="card px-4 py-3 space-y-2">
        <h3 className="text-[12px] font-bold text-gray-900">自動更新</h3>
        <Toggle label="自動更新を有効にする" checked={prefs.autoRefresh.enabled} onChange={(v) => update((p) => ({ ...p, autoRefresh: { ...p.autoRefresh, enabled: v } }))} />
        {prefs.autoRefresh.enabled && (
          <div>
            <p className="text-[10px] text-gray-400 mb-1.5">更新間隔</p>
            <div className="flex items-center gap-1">
              {[{ v: 30, l: "30秒" }, { v: 60, l: "1分" }, { v: 300, l: "5分" }].map(({ v, l }) => (
                <button key={v} onClick={() => update((p) => ({ ...p, autoRefresh: { ...p.autoRefresh, interval: v } }))}
                  className={`px-3 py-1 rounded text-[10px] transition-colors ${prefs.autoRefresh.interval === v ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600"}`}
                >{l}</button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Theme */}
      <div className="card px-4 py-3">
        <h3 className="text-[12px] font-bold text-gray-900 mb-2">テーマ</h3>
        <div className="flex items-center gap-1">
          {(["light", "dark"] as const).map((t) => (
            <button key={t} onClick={() => update((p) => ({ ...p, theme: t }))}
              className={`px-4 py-1.5 rounded text-[10px] transition-colors ${prefs.theme === t ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600"}`}
            >{t === "light" ? "ライト" : "ダーク"}</button>
          ))}
        </div>
      </div>
    </div>
  );
}
