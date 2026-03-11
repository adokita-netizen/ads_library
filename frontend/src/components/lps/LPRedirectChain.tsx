"use client";

import { useState } from "react";

interface LPRedirectStep {
  url: string;
  status_code?: number;
}

interface LPRedirectChainProps {
  chain: LPRedirectStep[];
}

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function getStatusColor(code?: number): string {
  if (!code) return "bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300";
  if (code >= 200 && code < 300) return "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300";
  if (code >= 300 && code < 400) return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300";
  return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
}

export default function LPRedirectChain({ chain }: LPRedirectChainProps) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);

  const handleCopyUrl = async (url: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = url;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 1500);
  };

  if (chain.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-[12px] text-gray-400 dark:text-gray-500">
        リダイレクトチェーンデータなし
      </div>
    );
  }

  return (
    <div className="px-4 py-4">
      <div className="flex flex-col gap-0">
        {chain.map((step, i) => {
          const isLast = i === chain.length - 1;
          const domain = extractDomain(step.url);

          return (
            <div key={i} className="flex flex-col">
              {/* Step node */}
              <div className="flex items-start gap-3 group">
                {/* Step indicator */}
                <div className="flex flex-col items-center shrink-0">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 ${
                      isLast
                        ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 ring-2 ring-green-300 dark:ring-green-700"
                        : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                    }`}
                  >
                    {i + 1}
                  </div>
                  {!isLast && (
                    <div className="w-0.5 h-8 bg-gray-200 dark:bg-gray-700" />
                  )}
                </div>

                {/* Step content */}
                <div className="flex-1 min-w-0 pb-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    {/* Status badge */}
                    {step.status_code && (
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold ${getStatusColor(step.status_code)}`}>
                        {step.status_code}
                      </span>
                    )}
                    {/* Domain */}
                    <span className="text-[11px] font-medium text-gray-700 dark:text-gray-200">{domain}</span>
                    {isLast && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300">
                        最終URL
                      </span>
                    )}
                  </div>
                  {/* Full URL */}
                  <div className="flex items-center gap-1.5 mt-1">
                    <p className="text-[11px] text-gray-400 dark:text-gray-500 truncate flex-1" title={step.url}>
                      {step.url}
                    </p>
                    <button
                      onClick={() => handleCopyUrl(step.url, i)}
                      className="shrink-0 p-1 rounded text-gray-300 dark:text-gray-600 hover:text-gray-500 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors opacity-0 group-hover:opacity-100"
                      title="URLをコピー"
                    >
                      {copiedIdx === i ? (
                        <svg className="w-3.5 h-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* Arrow between steps */}
              {!isLast && (
                <div className="flex items-center gap-3 -mt-1 mb-0">
                  <div className="w-8 flex justify-center shrink-0">
                    <svg className="w-3.5 h-3.5 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
                    </svg>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
