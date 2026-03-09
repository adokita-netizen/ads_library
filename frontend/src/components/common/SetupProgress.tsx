"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

const STORAGE_KEY = "vaap_setup_complete";
const API_KEYS_STORAGE_KEY = "vaap_api_keys_local";

interface SetupStep {
  label: string;
  done: boolean;
}

interface RankingsResponse {
  items: unknown[];
  total: number;
}

interface SetupProgressProps {
  onNavigate?: (view: "settings" | "pro-database") => void;
}

const DEFAULT_STEPS: SetupStep[] = [
  { label: "プラットフォーム接続済み", done: true },
  { label: "初回クロール完了", done: false },
  { label: "ランキング計算完了", done: false },
  { label: "Meta APIトークン設定済み", done: false },
  { label: "定期クロール有効化", done: false },
];

export default function SetupProgress({ onNavigate }: SetupProgressProps) {
  const [steps, setSteps] = useState<SetupStep[]>(DEFAULT_STEPS);
  const [hidden, setHidden] = useState(true);
  const [loading, setLoading] = useState(true);

  const checkSetup = useCallback(async () => {
    // If already fully complete, stay hidden
    try {
      if (localStorage.getItem(STORAGE_KEY) === "true") {
        setHidden(true);
        setLoading(false);
        return;
      }
    } catch {
      // ignore
    }

    const updated: SetupStep[] = DEFAULT_STEPS.map((step) => ({ ...step }));

    // Step 2: check if any crawl data exists
    try {
      const rankings = await fetchApi<RankingsResponse>(
        "/rankings/products",
        { params: { page_size: "1" } },
      );
      if (rankings && rankings.items && rankings.items.length > 0) {
        updated[1].done = true;
      }
    } catch {
      // API unreachable or no data — leave as false
    }

    // Step 3: check rankings summary
    try {
      const summary = await fetchApi<Record<string, unknown>>(
        "/rankings/dashboard-summary",
      );
      if (summary && typeof summary === "object") {
        updated[2].done = true;
      }
    } catch {
      // leave as false
    }

    // Step 4: check locally configured Meta token
    try {
      const raw = localStorage.getItem(API_KEYS_STORAGE_KEY);
      const rows = raw ? JSON.parse(raw) : [];
      if (Array.isArray(rows) && rows.some((row) => row?.platform === "meta" && row?.key_name === "access_token" && row?.key_value)) {
        updated[3].done = true;
      }
    } catch {
      // ignore storage parse failures
    }

    setSteps(updated);

    // If all done, mark as complete so we never show again
    const allDone = updated.every((s) => s.done);
    if (allDone) {
      try {
        localStorage.setItem(STORAGE_KEY, "true");
      } catch {
        // ignore
      }
      setHidden(true);
    } else {
      setHidden(false);
    }

    setLoading(false);
  }, []);

  useEffect(() => {
    checkSetup();
  }, [checkSetup]);

  if (hidden || loading) return null;

  const doneCount = steps.filter((s) => s.done).length;
  const percentage = Math.round((doneCount / steps.length) * 100);

  return (
    <div className="w-full px-3 py-2">
      <div className="bg-white rounded-lg border border-gray-100 p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-semibold text-gray-700">
            セットアップ進捗
          </span>
          <span className="text-[11px] font-medium text-[#4A7DFF]">
            {doneCount}/{steps.length}
          </span>
        </div>

        <div className="h-1.5 bg-gray-100 rounded-full mb-3 overflow-hidden">
          <div
            className="h-full bg-[#4A7DFF] rounded-full transition-all duration-500"
            style={{ width: `${percentage}%` }}
          />
        </div>

        <ul className="space-y-1.5">
          {steps.map((step) => (
            <li key={step.label} className="flex items-center gap-2">
              {step.done ? (
                <svg
                  className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M4.5 12.75l6 6 9-13.5"
                  />
                </svg>
              ) : (
                <div className="w-3.5 h-3.5 rounded-full border-[1.5px] border-gray-300 flex-shrink-0" />
              )}
              <span
                className={`text-[11px] ${
                  step.done ? "text-gray-400 line-through" : "text-gray-600"
                }`}
              >
                {step.label}
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onNavigate?.("settings")}
            className="inline-flex items-center gap-1.5 rounded-md border border-[#4A7DFF]/20 bg-[#EEF2FF] px-2.5 py-1.5 text-[11px] font-medium text-[#4A7DFF] transition-colors hover:bg-[#E3EAFF]"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 6h9m-9 6h9m-9 6h9M4.5 6h.008v.008H4.5V6zm0 6h.008v.008H4.5V12zm0 6h.008v.008H4.5V18z" />
            </svg>
            設定を開く
          </button>
          <button
            type="button"
            onClick={() => onNavigate?.("pro-database")}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-[11px] font-medium text-gray-600 transition-colors hover:bg-gray-50"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
            広告DBへ
          </button>
        </div>
      </div>
    </div>
  );
}
