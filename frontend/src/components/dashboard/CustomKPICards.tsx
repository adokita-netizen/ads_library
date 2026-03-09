"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchApi } from "@/lib/api";
import { formatNumber, formatYen } from "@/lib/format";

type KpiKey =
  | "total_ads"
  | "active_ads"
  | "avg_score"
  | "hit_rate"
  | "new_7d"
  | "total_spend";

interface KPIData {
  total_ads: number;
  new_7d: number;
  hit_ads: number;
  hit_percentage: number;
  active_ads: number;
  avg_score: number;
  total_spend: number;
}

const STORAGE_KEY = "vaap_custom_kpis";
const DEFAULT_KEYS: KpiKey[] = ["total_ads", "active_ads", "avg_score", "hit_rate"];

export default function CustomKPICards() {
  const [data, setData] = useState<KPIData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<KpiKey[]>(DEFAULT_KEYS);
  const [showConfig, setShowConfig] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length >= 4 && parsed.length <= 8) {
          setSelected(parsed.filter((x): x is KpiKey => typeof x === "string"));
        }
      }
    } catch {
      // ignore malformed storage
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(selected));
    } catch {
      // ignore
    }
  }, [selected]);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await fetchApi<KPIData>("/rankings/dashboard-kpi");
        setData(res);
      } catch {
        setData({
          total_ads: 0,
          new_7d: 0,
          hit_ads: 0,
          hit_percentage: 0,
          active_ads: 0,
          avg_score: 0,
          total_spend: 0,
        });
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

  const allItems = useMemo(() => {
    const d = data || {
      total_ads: 0,
      new_7d: 0,
      hit_ads: 0,
      hit_percentage: 0,
      active_ads: 0,
      avg_score: 0,
      total_spend: 0,
    };
    return [
      { key: "total_ads" as KpiKey, label: "総広告数", value: `${formatNumber(d.total_ads)}件` },
      { key: "active_ads" as KpiKey, label: "アクティブ広告", value: `${formatNumber(d.active_ads)}件` },
      { key: "avg_score" as KpiKey, label: "平均スコア", value: `${d.avg_score.toFixed(1)}pt` },
      { key: "hit_rate" as KpiKey, label: "HIT率", value: `${d.hit_percentage.toFixed(1)}%` },
      { key: "new_7d" as KpiKey, label: "新着(7日)", value: `+${formatNumber(d.new_7d)}` },
      { key: "total_spend" as KpiKey, label: "推定総消化額", value: formatYen(d.total_spend) },
    ];
  }, [data]);

  const shown = allItems.filter((i) => selected.includes(i.key));

  const toggle = (k: KpiKey) => {
    setSelected((prev) => {
      if (prev.includes(k)) {
        if (prev.length <= 4) return prev;
        return prev.filter((x) => x !== k);
      }
      if (prev.length >= 8) return prev;
      return [...prev, k];
    });
  };

  return (
    <div className="mb-3">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-[12px] font-semibold text-gray-700 dark:text-gray-300">KPIカード</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSelected(DEFAULT_KEYS)}
            className="text-[10px] text-gray-500 dark:text-gray-400 hover:text-[#4A7DFF]"
          >
            デフォルト
          </button>
          <button
            onClick={() => setShowConfig((v) => !v)}
            className="text-[10px] text-gray-500 dark:text-gray-400 hover:text-[#4A7DFF]"
          >
            カスタム
          </button>
        </div>
      </div>
      {showConfig && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {allItems.map((item) => {
            const active = selected.includes(item.key);
            return (
              <button
                key={item.key}
                onClick={() => toggle(item.key)}
                className={`rounded-full px-2.5 py-1 text-[10px] border ${
                  active
                    ? "bg-[#EEF2FF] text-[#4A7DFF] border-[#cdd9ff]"
                    : "bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-700"
                }`}
              >
                {active ? "✓ " : ""}{item.label}
              </button>
            );
          })}
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        {loading && Array.from({ length: 4 }).map((_, idx) => (
          <div key={`s-${idx}`} className="h-[62px] rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 animate-pulse" />
        ))}
        {!loading && shown.map((item) => (
          <div key={item.key} className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2">
            <p className="text-[10px] text-gray-500 dark:text-gray-400">{item.label}</p>
            <p className="text-[14px] font-bold text-gray-900 dark:text-gray-100 mt-0.5">{item.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
