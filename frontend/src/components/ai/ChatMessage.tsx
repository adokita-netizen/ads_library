"use client";

import { useState, useCallback } from "react";

/* ─── Types ─── */

interface AdItem {
  ad_id: number;
  product_name: string;
  hit_score: number;
  advertiser_name?: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  ads?: AdItem[];
}

interface ChatMessageProps {
  message: Message;
  onAdSelect?: (adId: number) => void;
}

/* ─── Helpers ─── */

function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-600";
  if (score >= 40) return "text-amber-500";
  return "text-red-500";
}

function scoreBg(score: number): string {
  if (score >= 70) return "bg-emerald-50";
  if (score >= 40) return "bg-amber-50";
  return "bg-red-50";
}

/* ─── Code Block ─── */

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [code]);

  return (
    <div className="my-2 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between bg-gray-700 px-3 py-1">
        <span className="text-[10px] text-gray-400 uppercase">{language || "code"}</span>
        <button
          onClick={handleCopy}
          className="text-[10px] text-gray-400 hover:text-white transition-colors"
        >
          {copied ? "コピー済み" : "コピー"}
        </button>
      </div>
      <pre className="bg-gray-800 text-gray-100 text-[12px] p-3 overflow-x-auto">
        <code>{code}</code>
      </pre>
    </div>
  );
}

/* ─── Content Renderer ─── */

function renderContent(content: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    // Text before the code block
    if (match.index > lastIndex) {
      const textBefore = content.slice(lastIndex, match.index);
      parts.push(...renderParagraphs(textBefore, parts.length));
    }
    // The code block
    parts.push(
      <CodeBlock key={`code-${parts.length}`} language={match[1]} code={match[2].trim()} />
    );
    lastIndex = match.index + match[0].length;
  }

  // Remaining text after last code block
  if (lastIndex < content.length) {
    parts.push(...renderParagraphs(content.slice(lastIndex), parts.length));
  }

  return parts;
}

function renderParagraphs(text: string, keyOffset: number): React.ReactNode[] {
  return text
    .split("\n\n")
    .filter((p) => p.trim())
    .map((paragraph, i) => {
      // Handle single newlines within a paragraph as line breaks
      const lines = paragraph.split("\n");
      return (
        <p key={`p-${keyOffset}-${i}`} className="text-[13px] leading-relaxed mb-1.5 last:mb-0">
          {lines.map((line, j) => (
            <span key={j}>
              {j > 0 && <br />}
              {line}
            </span>
          ))}
        </p>
      );
    });
}

/* ─── Ad Mini-Card ─── */

function AdMiniCard({
  ad,
  onSelect,
}: {
  ad: AdItem;
  onSelect?: (adId: number) => void;
}) {
  return (
    <button
      onClick={() => onSelect?.(ad.ad_id)}
      className="flex items-center gap-2 w-full text-left bg-white border border-gray-200 rounded-lg px-3 py-2 hover:border-[#4A7DFF] hover:shadow-sm transition-all group"
    >
      <div className="flex-1 min-w-0">
        <p className="text-[12px] font-medium text-gray-900 truncate group-hover:text-[#4A7DFF]">
          {ad.product_name}
        </p>
        {ad.advertiser_name && (
          <p className="text-[11px] text-gray-500 truncate">{ad.advertiser_name}</p>
        )}
      </div>
      <div className={`flex-shrink-0 px-2 py-0.5 rounded-full text-[11px] font-semibold ${scoreBg(ad.hit_score)} ${scoreColor(ad.hit_score)}`}>
        {ad.hit_score}
      </div>
    </button>
  );
}

/* ─── Main Component ─── */

export default function ChatMessage({ message, onAdSelect }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`max-w-[80%] ${isUser ? "order-1" : "order-1"}`}>
        {/* AI avatar */}
        {!isUser && (
          <div className="flex items-center gap-2 mb-1">
            <div className="w-6 h-6 rounded-full bg-[#4A7DFF] flex items-center justify-center flex-shrink-0">
              <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
              </svg>
            </div>
            <span className="text-[11px] text-gray-500 font-medium">AI アドバイザー</span>
          </div>
        )}

        {/* Message bubble */}
        <div
          className={`px-4 py-2.5 ${
            isUser
              ? "bg-[#4A7DFF] text-white rounded-2xl rounded-br-sm"
              : "bg-gray-100 text-gray-900 rounded-2xl rounded-bl-sm"
          }`}
        >
          {isUser ? (
            <p className="text-[13px] leading-relaxed">{message.content}</p>
          ) : (
            renderContent(message.content)
          )}
        </div>

        {/* Ad cards */}
        {!isUser && message.ads && message.ads.length > 0 && (
          <div className="mt-2 space-y-1.5">
            {message.ads.map((ad) => (
              <AdMiniCard key={ad.ad_id} ad={ad} onSelect={onAdSelect} />
            ))}
          </div>
        )}

        {/* Timestamp */}
        <p
          className={`text-[9px] text-gray-400 mt-1 ${
            isUser ? "text-right" : "text-left"
          }`}
        >
          {message.timestamp}
        </p>
      </div>
    </div>
  );
}
