"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { fetchApi } from "@/lib/api";

/* ─── Types ─── */

type KPIKey =
  | "total_ads"
  | "active_ads"
  | "avg_score"
  | "hit_rate"
  | "new_7d"
  | "top_genre"
  | "avg_days"
  | "total_spend";

interface KPIDefinition {
  key: KPIKey;
  label: string;
  subtitle: string;
  color: string;
  bg: string;
  icon: React.ReactNode;
  format: (v: string | number) => string;
}

interface KPIResponse {
  total_ads: number;
  active_ads: number;
  avg_score: number;
  hit_rate: number;
  new_7d: number;
  top_genre: string;
  avg_days: number;
  total_spend: number;
}

/* ─── Constants ─── */

const STORAGE_KEY = "vaap_kpi_config";

const DEFAULT_KEYS: KPIKey[] = [
  "total_ads",
  "active_ads",
  "avg_score",
  "hit_rate",
  "new_7d",
  "total_spend",
];

const MOCK_DATA: KPIResponse = {
  total_ads: 12847,
  active_ads: 8934,
  avg_score: 54.2,
  hit_rate: 11.9,
  new_7d: 342,
  top_genre: "美容・健康",
  avg_days: 28.5,
  total_spend: 2340000000,
};

/* ─── Helpers ─── */

function formatNum(n: string | number): string {
  const v = typeof n === "string" ? parseFloat(n) : n;
  if (isNaN(v)) return String(n);
  if (v >= 100000000) return (v / 100000000).toFixed(1) + "億";
  if (v >= 10000) return (v / 10000).toFixed(0) + "万";
  return v.toLocaleString();
}

function formatYenShort(n: string | number): string {
  const v = typeof n === "string" ? parseFloat(n) : n;
  if (isNaN(v)) return String(n);
  if (v >= 100000000) return "¥" + (v / 100000000).toFixed(1) + "億";
  if (v >= 10000) return "¥" + (v / 10000).toFixed(0) + "万";
  return "¥" + v.toLocaleString();
}

function formatPct(n: string | number): string {
  const v = typeof n === "string" ? parseFloat(n) : n;
  if (isNaN(v)) return String(n);
  return v.toFixed(1) + "%";
}

function formatDec(n: string | number): string {
  const v = typeof n === "string" ? parseFloat(n) : n;
  if (isNaN(v)) return String(n);
  return v.toFixed(1);
}

function formatDays(n: string | number): string {
  const v = typeof n === "string" ? parseFloat(n) : n;
  if (isNaN(v)) return String(n);
  return v.toFixed(1) + "日";
}

function loadConfig(): KPIKey[] {
  if (typeof window === "undefined") return DEFAULT_KEYS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_KEYS;
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return DEFAULT_KEYS;
    const valid = (parsed as string[]).filter((k): k is KPIKey =>
      ALL_KPI_KEYS.includes(k as KPIKey),
    );
    if (valid.length < 4 || valid.length > 8) return DEFAULT_KEYS;
    return valid;
  } catch {
    return DEFAULT_KEYS;
  }
}

function persistConfig(keys: KPIKey[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(keys));
}

/* ─── Icons (inline SVG) ─── */

function IconGrid() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
    </svg>
  );
}

function IconBolt() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
    </svg>
  );
}

function IconStar() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
    </svg>
  );
}

function IconFire() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.362 5.214A8.252 8.252 0 0112 21 8.25 8.25 0 016.038 7.048 8.287 8.287 0 009 9.6a8.983 8.983 0 013.361-6.867 8.21 8.21 0 003 2.48z" />
    </svg>
  );
}

function IconTrendUp() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
    </svg>
  );
}

function IconTag() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 6h.008v.008H6V6z" />
    </svg>
  );
}

function IconCalendar() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
    </svg>
  );
}

function IconCurrency() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

/* ─── KPI definitions ─── */

const ALL_KPI_DEFS: KPIDefinition[] = [
  {
    key: "total_ads",
    label: "総広告数",
    subtitle: "登録済み広告",
    color: "text-[#4A7DFF]",
    bg: "bg-blue-50",
    icon: <IconGrid />,
    format: formatNum,
  },
  {
    key: "active_ads",
    label: "アクティブ広告",
    subtitle: "配信中の広告",
    color: "text-violet-600",
    bg: "bg-violet-50",
    icon: <IconBolt />,
    format: formatNum,
  },
  {
    key: "avg_score",
    label: "平均スコア",
    subtitle: "全広告の平均",
    color: "text-amber-500",
    bg: "bg-amber-50",
    icon: <IconStar />,
    format: formatDec,
  },
  {
    key: "hit_rate",
    label: "ヒット率",
    subtitle: "ヒット広告の割合",
    color: "text-orange-500",
    bg: "bg-orange-50",
    icon: <IconFire />,
    format: formatPct,
  },
  {
    key: "new_7d",
    label: "新着7日",
    subtitle: "直近1週間の追加",
    color: "text-emerald-600",
    bg: "bg-emerald-50",
    icon: <IconTrendUp />,
    format: (v) => `+${formatNum(v)}`,
  },
  {
    key: "top_genre",
    label: "トップジャンル",
    subtitle: "最も多いジャンル",
    color: "text-pink-500",
    bg: "bg-pink-50",
    icon: <IconTag />,
    format: (v) => String(v),
  },
  {
    key: "avg_days",
    label: "平均配信日数",
    subtitle: "広告の平均掲載期間",
    color: "text-sky-600",
    bg: "bg-sky-50",
    icon: <IconCalendar />,
    format: formatDays,
  },
  {
    key: "total_spend",
    label: "推定消化額",
    subtitle: "推定の総消化金額",
    color: "text-teal-600",
    bg: "bg-teal-50",
    icon: <IconCurrency />,
    format: formatYenShort,
  },
];

const ALL_KPI_KEYS: KPIKey[] = ALL_KPI_DEFS.map((d) => d.key);

/* ─── Skeleton Card ─── */

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 px-4 py-3 animate-pulse">
      <div className="h-3 w-16 bg-gray-200 rounded mb-2" />
      <div className="h-6 w-24 bg-gray-200 rounded mb-1" />
      <div className="h-2.5 w-20 bg-gray-100 rounded" />
    </div>
  );
}

/* ─── Main Component ─── */

export default function CustomKPICards() {
  const [data, setData] = useState<KPIResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedKeys, setSelectedKeys] = useState<KPIKey[]>(DEFAULT_KEYS);
  const [showSettings, setShowSettings] = useState(false);
  const settingsRef = useRef<HTMLDivElement>(null);

  // Load config on mount
  useEffect(() => {
    setSelectedKeys(loadConfig());
  }, []);

  // Fetch KPI data
  const fetchKPI = useCallback(async () => {
    try {
      const res = await fetchApi<KPIResponse>("/rankings/dashboard-kpi");
      setData(res);
    } catch {
      setData(MOCK_DATA);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchKPI();
    const interval = setInterval(fetchKPI, 60000);
    return () => clearInterval(interval);
  }, [fetchKPI]);

  // Close settings dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setShowSettings(false);
      }
    }
    if (showSettings) {
      document.addEventListener("mousedown", handleClick);
      return () => document.removeEventListener("mousedown", handleClick);
    }
  }, [showSettings]);

  const handleToggleKey = useCallback(
    (key: KPIKey) => {
      setSelectedKeys((prev) => {
        const isActive = prev.includes(key);
        let updated: KPIKey[];
        if (isActive) {
          if (prev.length <= 4) return prev; // Min 4
          updated = prev.filter((k) => k !== key);
        } else {
          if (prev.length >= 8) return prev; // Max 8
          updated = [...prev, key];
        }
        persistConfig(updated);
        return updated;
      });
    },
    [],
  );

  const handleResetDefaults = useCallback(() => {
    setSelectedKeys(DEFAULT_KEYS);
    persistConfig(DEFAULT_KEYS);
  }, []);

  const visibleDefs = ALL_KPI_DEFS.filter((d) => selectedKeys.includes(d.key));

  if (loading) {
    return (
      <div className="mb-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="mb-4">
      {/* Header with settings button */}
      <div className="flex items-center justify-end mb-2 relative">
        <div className="relative" ref={settingsRef}>
          <button
            onClick={() => setShowSettings((p) => !p)}
            className="flex items-center gap-1 px-2 py-1 text-[11px] text-gray-500 hover:text-[#4A7DFF] hover:bg-[#EEF2FF] rounded-md transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            カスタマイズ
          </button>

          {/* Settings dropdown */}
          {showSettings && (
            <div className="absolute right-0 top-full mt-1 z-40 bg-white border border-gray-200 rounded-xl shadow-lg py-2 px-3 w-56">
              <p className="text-[11px] text-gray-400 font-medium mb-2">
                表示するKPIを選択（4〜8個）
              </p>
              <div className="space-y-1">
                {ALL_KPI_DEFS.map((def) => {
                  const checked = selectedKeys.includes(def.key);
                  const disabled =
                    (checked && selectedKeys.length <= 4) ||
                    (!checked && selectedKeys.length >= 8);
                  return (
                    <label
                      key={def.key}
                      className={`flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-colors ${
                        disabled ? "opacity-40 cursor-not-allowed" : "hover:bg-gray-50"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={disabled}
                        onChange={() => handleToggleKey(def.key)}
                        className="w-3.5 h-3.5 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]/30"
                      />
                      <span className={`${def.bg} ${def.color} p-0.5 rounded`}>
                        {def.icon}
                      </span>
                      <span className="text-[12px] text-gray-700">{def.label}</span>
                    </label>
                  );
                })}
              </div>
              <div className="mt-2 pt-2 border-t border-gray-100">
                <button
                  onClick={handleResetDefaults}
                  className="w-full text-center text-[11px] text-gray-500 hover:text-[#4A7DFF] py-1 transition-colors"
                >
                  デフォルトに戻す
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* KPI cards grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
        {visibleDefs.map((def) => {
          const rawValue = data[def.key];
          const displayValue = def.format(rawValue);
          return (
            <div
              key={def.key}
              className="bg-white rounded-xl border border-gray-200 px-4 py-3 hover:shadow-sm transition-shadow"
            >
              <div className="flex items-center gap-1.5 mb-1">
                <span className={`${def.bg} ${def.color} p-1 rounded-md`}>
                  {def.icon}
                </span>
                <span className="text-[11px] text-gray-500 font-medium">
                  {def.label}
                </span>
              </div>
              <div className="mb-0.5">
                <span className={`text-[18px] font-bold ${def.color} leading-tight`}>
                  {displayValue}
                </span>
              </div>
              <p className="text-[11px] text-gray-400">{def.subtitle}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
