"use client";

import { useState, useEffect, useCallback } from "react";
import { setDemoMode } from "@/lib/demoData";

const STORAGE_KEY = "vaap_onboarding_completed";

interface WelcomeModalProps {
  onStartCrawl: () => void;
  onDemoMode: () => void;
}

interface StepDef {
  label: string;
  icon: React.ReactNode;
}

const STEPS: StepDef[] = [
  {
    label: "広告を収集",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
      </svg>
    ),
  },
  {
    label: "AIが自動分析",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
      </svg>
    ),
  },
  {
    label: "勝ちクリエイティブを発見",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 007.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M18.75 4.236c.982.143 1.954.317 2.916.52A6.003 6.003 0 0016.27 9.728M18.75 4.236V4.5c0 2.108-.966 3.99-2.48 5.228m0 0a6.003 6.003 0 01-5.54 0" />
      </svg>
    ),
  },
];

export default function WelcomeModal({ onStartCrawl, onDemoMode }: WelcomeModalProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      const completed = localStorage.getItem(STORAGE_KEY);
      if (completed === null) {
        setVisible(true);
      }
    } catch {
      // localStorage unavailable
    }
  }, []);

  const handleClose = useCallback(() => {
    try {
      localStorage.setItem(STORAGE_KEY, "true");
    } catch {
      // ignore
    }
    setVisible(false);
  }, []);

  const handleStartCrawl = useCallback(() => {
    handleClose();
    onStartCrawl();
  }, [handleClose, onStartCrawl]);

  const handleDemoMode = useCallback(() => {
    setDemoMode(true);
    handleClose();
    onDemoMode();
  }, [handleClose, onDemoMode]);

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={handleClose} />

      {/* Card */}
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header gradient bar */}
        <div className="h-1 bg-gradient-to-r from-[#4A7DFF] to-[#7B9FFF]" />

        <div className="p-6">
          {/* Title */}
          <h2 className="text-[16px] font-bold text-gray-900 mb-1">
            VaaPへようこそ
          </h2>
          <p className="text-[12px] text-gray-500 mb-6">
            3ステップで競合広告の分析を始めましょう
          </p>

          {/* 3-step visual */}
          <div className="flex items-start justify-between mb-8">
            {STEPS.map((step, idx) => (
              <div key={step.label} className="flex flex-col items-center flex-1">
                <div className="flex items-center w-full">
                  {/* Step circle */}
                  <div className="mx-auto flex flex-col items-center">
                    <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center text-[#4A7DFF] mb-2">
                      {step.icon}
                    </div>
                    <span className="text-[11px] font-medium text-gray-700 text-center leading-tight">
                      {step.label}
                    </span>
                  </div>
                </div>
                {/* Arrow between steps */}
                {idx < STEPS.length - 1 && (
                  <div className="hidden" />
                )}
              </div>
            ))}
          </div>

          {/* Connector arrows (positioned between step circles) */}
          <div className="flex items-center justify-center -mt-[72px] mb-8 pointer-events-none">
            <div className="flex items-center w-full max-w-[320px] justify-between px-8">
              <div className="flex-1" />
              <svg className="w-5 h-5 text-gray-300 flex-shrink-0 -mt-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
              <div className="flex-1" />
              <svg className="w-5 h-5 text-gray-300 flex-shrink-0 -mt-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
              <div className="flex-1" />
            </div>
          </div>

          {/* Buttons */}
          <div className="flex flex-col gap-3">
            <button
              onClick={handleStartCrawl}
              className="w-full px-5 py-2.5 text-[13px] font-medium bg-[#4A7DFF] text-white rounded-lg hover:bg-[#3a6ae6] transition-colors"
            >
              まず広告を収集する
            </button>
            <button
              onClick={handleDemoMode}
              className="w-full px-5 py-2.5 text-[13px] font-medium border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              デモデータで試す
            </button>
          </div>

          {/* Close link */}
          <div className="mt-4 text-center">
            <button
              onClick={handleClose}
              className="text-[11px] text-gray-400 hover:text-gray-600 transition-colors"
            >
              閉じる
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
