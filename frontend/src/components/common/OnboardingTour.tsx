"use client";

import { useState, useEffect } from "react";

const STORAGE_KEY = "onboarding_completed";

interface TourStep {
  title: string;
  description: string;
}

const STEPS: TourStep[] = [
  {
    title: "PRO DATABASE",
    description: "ここで全広告を一覧できます",
  },
  {
    title: "検索",
    description: "キーワード、ジャンル、広告主で絞り込み",
  },
  {
    title: "シナリオ作成",
    description: "ヒットパターンから広告シナリオを自動生成",
  },
  {
    title: "レポート",
    description: "パフォーマンスレポートとエクスポート",
  },
  {
    title: "お知らせ",
    description: "新着ヒット広告やスコア変動をリアルタイム通知",
  },
];

export default function OnboardingTour() {
  const [visible, setVisible] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    try {
      const completed = localStorage.getItem(STORAGE_KEY);
      if (completed !== "true") {
        setVisible(true);
      }
    } catch {
      // localStorage unavailable
    }
  }, []);

  if (!visible) return null;

  const step = STEPS[currentStep];
  const totalSteps = STEPS.length;
  const isLast = currentStep === totalSteps - 1;

  const handleNext = () => {
    if (isLast) {
      handleComplete();
    } else {
      setCurrentStep((s) => s + 1);
    }
  };

  const handleSkip = () => {
    handleComplete();
  };

  const handleComplete = () => {
    try {
      localStorage.setItem(STORAGE_KEY, "true");
    } catch {
      // ignore
    }
    setVisible(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Dark backdrop */}
      <div className="absolute inset-0 bg-black/60" />

      {/* Card */}
      <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        {/* Progress bar */}
        <div className="h-1 bg-gray-100">
          <div
            className="h-full bg-[#4A7DFF] transition-all duration-300"
            style={{ width: `${((currentStep + 1) / totalSteps) * 100}%` }}
          />
        </div>

        <div className="p-6">
          {/* Step counter */}
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-medium text-gray-400">
              {currentStep + 1}/{totalSteps}
            </span>
            <button
              onClick={handleSkip}
              className="text-[10px] text-gray-400 hover:text-gray-600 transition-colors"
            >
              スキップ
            </button>
          </div>

          {/* Step icon */}
          <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center mb-4">
            <svg className="w-6 h-6 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              {currentStep === 0 && (
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
              )}
              {currentStep === 1 && (
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              )}
              {currentStep === 2 && (
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
              )}
              {currentStep === 3 && (
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
              )}
              {currentStep === 4 && (
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
              )}
            </svg>
          </div>

          {/* Content */}
          <h3 className="text-[14px] font-bold text-gray-900 mb-1">{step.title}</h3>
          <p className="text-[11px] text-gray-500 leading-relaxed mb-6">{step.description}</p>

          {/* Step dots */}
          <div className="flex items-center justify-center gap-1.5 mb-5">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`w-1.5 h-1.5 rounded-full transition-colors ${
                  i === currentStep ? "bg-[#4A7DFF]" : i < currentStep ? "bg-[#4A7DFF]/40" : "bg-gray-200"
                }`}
              />
            ))}
          </div>

          {/* Buttons */}
          <div className="flex items-center justify-between">
            <button
              onClick={handleSkip}
              className="text-[11px] text-gray-400 hover:text-gray-600 transition-colors px-3 py-2"
            >
              スキップ
            </button>
            <button
              onClick={handleNext}
              className="px-5 py-2 text-[11px] font-medium bg-[#4A7DFF] text-white rounded-lg hover:bg-[#3a6ae6] transition-colors"
            >
              {isLast ? "完了" : "次へ"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
