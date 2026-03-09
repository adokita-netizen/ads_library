"use client";

import { useEffect, useMemo, useState } from "react";
import { isDemoMode, setDemoMode } from "@/lib/demoData";

interface OnboardingWizardProps {
  open: boolean;
  onComplete: () => void;
}

type Step = {
  title: string;
  description: string;
  bullets: string[];
};

const SESSION_DISMISS_KEY = "vaap-onboarding-dismissed-session";

const STEPS: Step[] = [
  {
    title: "ようこそ VAAP へ",
    description: "競合広告データを一箇所で収集・分析して、次の打ち手を早く決めるためのワークスペースです。",
    bullets: [
      "競合広告の収集・分析",
      "HIT広告の自動検出",
      "クリエイティブ提案",
    ],
  },
  {
    title: "データ接続",
    description: "Meta APIトークンを設定すると、最新の広告データで分析できます。後から設定でも開始できます。",
    bullets: [
      "設定画面から Meta API トークンを登録",
      "未設定でもデモモードで画面を確認可能",
      "データ不足時はサンプル表示で操作を学習",
    ],
  },
  {
    title: "はじめましょう",
    description: "まずは PRO DATABASE を開き、検索・フィルタ・詳細表示の流れを試してください。",
    bullets: [
      "PRO DATABASE: 一覧と絞り込み",
      "ショートカット: Shift + ?",
      "通知ベルから新着とアラートを確認",
    ],
  },
];

function persistOnboarded() {
  localStorage.setItem("vaap-onboarded", "true");
  localStorage.setItem("vaap_onboarding_completed", "true");
  localStorage.setItem("onboarding_completed", "true");
  sessionStorage.removeItem(SESSION_DISMISS_KEY);
}

export default function OnboardingWizard({ open, onComplete }: OnboardingWizardProps) {
  const [step, setStep] = useState(0);
  const [demoMode, setDemoModeEnabled] = useState(() => isDemoMode());

  const current = useMemo(() => STEPS[step], [step]);
  const isLast = step === STEPS.length - 1;

  const finish = () => {
    persistOnboarded();
    onComplete();
  };

  const dismissForSession = () => {
    sessionStorage.setItem(SESSION_DISMISS_KEY, "true");
    onComplete();
  };

  const toggleDemo = () => {
    const next = !demoMode;
    setDemoModeEnabled(next);
    setDemoMode(next);
  };

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        finish();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[70] w-[min(420px,calc(100vw-2rem))]">
      <div className="relative rounded-2xl border border-gray-200 bg-white/95 shadow-2xl ring-1 ring-black/5 backdrop-blur">
        <div className="h-1 rounded-t-2xl bg-gray-100">
          <div className="h-full rounded-t-2xl bg-[#4A7DFF] transition-all" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
        </div>

        <div className="px-5 py-4 sm:px-6 sm:py-5">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-[11px] font-semibold text-gray-400">{step + 1}/{STEPS.length}</p>
            <div className="flex items-center gap-2">
              <button type="button" onClick={dismissForSession} className="text-[11px] text-gray-400 hover:text-gray-600">
                後で見る
              </button>
              <button type="button" onClick={finish} className="text-[11px] text-gray-500 hover:text-gray-700">
                スキップ
              </button>
            </div>
          </div>

          <h3 className="text-[16px] font-bold text-gray-900 sm:text-[18px]">{current.title}</h3>
          <p className="mt-1 text-[12px] leading-6 text-gray-600 sm:text-[13px]">{current.description}</p>

          <ul className="mt-4 space-y-2">
            {current.bullets.map((line) => (
              <li key={line} className="flex items-start gap-2 text-[11px] text-gray-700 sm:text-[12px]">
                <span className="mt-1 h-1.5 w-1.5 rounded-full bg-[#4A7DFF]" />
                <span>{line}</span>
              </li>
            ))}
          </ul>

          {step === 1 && (
            <button
              type="button"
              onClick={toggleDemo}
              className={`mt-4 rounded-lg border px-3 py-2 text-[11px] font-medium transition-colors sm:text-[12px] ${
                demoMode ? "border-blue-200 bg-blue-50 text-blue-700" : "border-gray-200 text-gray-700 hover:bg-gray-50"
              }`}
            >
              {demoMode ? "デモモード: ON" : "デモモード: OFF"}
            </button>
          )}

          <div className="mt-5 flex items-center justify-between">
            <button
              type="button"
              disabled={step === 0}
              onClick={() => setStep((prev) => Math.max(0, prev - 1))}
              className="rounded-lg border border-gray-200 px-3 py-2 text-[11px] font-medium text-gray-600 disabled:cursor-not-allowed disabled:opacity-40 sm:text-[12px]"
            >
              戻る
            </button>
            <button
              type="button"
              onClick={() => (isLast ? finish() : setStep((prev) => prev + 1))}
              className="rounded-lg bg-[#4A7DFF] px-4 py-2 text-[11px] font-semibold text-white hover:bg-[#3A6AEE] sm:text-[12px]"
            >
              {isLast ? "ツアーを開始" : "次へ"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
