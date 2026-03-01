"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

const STORAGE_KEY = "vaap_setup_complete";

interface SetupStep {
  label: string;
  done: boolean;
}

interface RankingsResponse {
  items: unknown[];
  total: number;
}

export default function SetupProgress() {
  const [steps, setSteps] = useState<SetupStep[]>([
    { label: "アカウント作成", done: true },
    { label: "初回データ取得", done: false },
    { label: "50件以上の広告", done: false },
    { label: "ランキング計算", done: false },
  ]);
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

    const updated: SetupStep[] = [
      { label: "アカウント作成", done: true },
      { label: "初回データ取得", done: false },
      { label: "50件以上の広告", done: false },
      { label: "ランキング計算", done: false },
    ];

    // Step 2: check if any data exists
    try {
      const rankings = await fetchApi<RankingsResponse>(
        "/rankings/products",
        { params: { page_size: "1" } },
      );
      if (rankings && rankings.items && rankings.items.length > 0) {
        updated[1].done = true;
      }
      // Step 3: check total >= 50
      if (rankings && typeof rankings.total === "number" && rankings.total >= 50) {
        updated[2].done = true;
      }
    } catch {
      // API unreachable or no data — leave as false
    }

    // Step 4: check dashboard-summary
    try {
      const summary = await fetchApi<Record<string, unknown>>(
        "/rankings/dashboard-summary",
      );
      if (summary && typeof summary === "object") {
        updated[3].done = true;
      }
    } catch {
      // leave as false
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
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-semibold text-gray-700">
            セットアップ進捗
          </span>
          <span className="text-[11px] font-medium text-[#4A7DFF]">
            {percentage}%
          </span>
        </div>

        {/* Progress bar */}
        <div className="h-1.5 bg-gray-100 rounded-full mb-3 overflow-hidden">
          <div
            className="h-full bg-[#4A7DFF] rounded-full transition-all duration-500"
            style={{ width: `${percentage}%` }}
          />
        </div>

        {/* Checklist */}
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
      </div>
    </div>
  );
}
