"use client";

import { useState, useEffect, useRef, useCallback, KeyboardEvent } from "react";
import { fetchApi } from "@/lib/api";
import ChatMessage from "./ChatMessage";
import ChatHistory from "./ChatHistory";
import QuickActions from "./QuickActions";

/* ─── Types ─── */

interface AdItem {
  ad_id: number;
  product_name: string;
  hit_score: number;
  advertiser_name?: string;
}

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  ads?: AdItem[];
}

interface ConversationMeta {
  id: string;
  title: string;
  date: string;
  messageCount: number;
}

interface StoredConversation {
  id: string;
  title: string;
  date: string;
  messages: ChatMsg[];
  backendConversationId?: number;
}

interface AIChatViewProps {
  onAdSelect?: (adId: number) => void;
}

/* ─── Constants ─── */

const STORAGE_KEY = "vaap_chat_history";
const MAX_CONVERSATIONS = 20;

const SUGGESTED_QUESTIONS = [
  { title: "ヒット広告の共通点は？", prompt: "最近のヒット広告に共通する要素を分析してください。" },
  { title: "美容ジャンルのトレンドは？", prompt: "美容・コスメジャンルの最新広告トレンドを教えてください。" },
  { title: "競合A社の戦略分析", prompt: "主要な競合他社の広告出稿傾向と戦略を分析してください。" },
  { title: "効果的なコピーの書き方", prompt: "高いCTRを記録している広告コピーの特徴と書き方のコツを教えてください。" },
  { title: "LP改善のヒント", prompt: "ランディングページの改善ポイントをデータに基づいて提案してください。" },
  { title: "来月のクリエイティブ戦略", prompt: "来月に向けたクリエイティブ戦略を、現在のトレンドデータに基づいて提案してください。" },
];

/* ─── Storage Helpers ─── */

function loadConversations(): StoredConversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveConversations(conversations: StoredConversation[]): void {
  if (typeof window === "undefined") return;
  // Keep only the latest MAX_CONVERSATIONS
  const trimmed = conversations.slice(0, MAX_CONVERSATIONS);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
}

function generateId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function formatDate(date: Date): string {
  const m = (date.getMonth() + 1).toString().padStart(2, "0");
  const d = date.getDate().toString().padStart(2, "0");
  return `${m}/${d}`;
}

function formatTimestamp(date: Date): string {
  return `${date.getHours().toString().padStart(2, "0")}:${date.getMinutes().toString().padStart(2, "0")}`;
}

/* ─── Typing Indicator ─── */

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-4">
      <div className="flex items-center gap-2">
        <div className="w-6 h-6 rounded-full bg-[#4A7DFF] flex items-center justify-center flex-shrink-0">
          <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
          </svg>
        </div>
        <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "0ms" }} />
          <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "150ms" }} />
          <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "300ms" }} />
        </div>
      </div>
    </div>
  );
}

/* ─── Main Component ─── */

export default function AIChatView({ onAdSelect }: AIChatViewProps) {
  const [conversations, setConversations] = useState<StoredConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const getBackendConversationId = useCallback(
    (convId: string | null): number | undefined => {
      if (!convId) return undefined;
      return conversations.find((c) => c.id === convId)?.backendConversationId;
    },
    [conversations],
  );

  // Load conversations from localStorage on mount
  useEffect(() => {
    const stored = loadConversations();
    setConversations(stored);
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      const maxHeight = 4 * 24; // ~4 lines
      textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
    }
  }, [inputValue]);

  // Build conversation meta list
  const conversationMetas: ConversationMeta[] = conversations.map((c) => ({
    id: c.id,
    title: c.title,
    date: c.date,
    messageCount: c.messages.length,
  }));

  // Persist current conversation to storage
  const persistConversation = useCallback(
    (
      convId: string,
      msgs: ChatMsg[],
      allConversations: StoredConversation[],
      backendConversationId?: number,
    ) => {
      const idx = allConversations.findIndex((c) => c.id === convId);
      const title =
        msgs.length > 0
          ? msgs[0].content.slice(0, 30) + (msgs[0].content.length > 30 ? "..." : "")
          : "新しい会話";
      const updated: StoredConversation = {
        id: convId,
        title,
        date: formatDate(new Date()),
        messages: msgs,
        backendConversationId,
      };

      let newConversations: StoredConversation[];
      if (idx >= 0) {
        newConversations = [...allConversations];
        newConversations[idx] = updated;
      } else {
        newConversations = [updated, ...allConversations];
      }

      setConversations(newConversations);
      saveConversations(newConversations);
      return newConversations;
    },
    [],
  );

  // Send message handler
  const handleSend = useCallback(async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || isLoading) return;

    const now = new Date();
    const userMsg: ChatMsg = {
      role: "user",
      content: trimmed,
      timestamp: formatTimestamp(now),
    };

    // Create a new conversation if none active
    let convId = activeConversationId;
    if (!convId) {
      convId = generateId();
      setActiveConversationId(convId);
    }

    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInputValue("");
    setIsLoading(true);

    // Persist with user message
    const existingBackendConversationId = getBackendConversationId(convId);
    const latestConversations = persistConversation(
      convId,
      updatedMessages,
      conversations,
      existingBackendConversationId,
    );

    try {
      // Try real API first
      const response = await fetchApi<{
        conversation_id: number;
        response: {
          message: string;
          data?: {
            top_ads?: Array<{
              ad_id: number;
              title?: string;
              hit_score?: number;
              advertiser_name?: string;
            }>;
          };
        };
      }>("/ai-chat/message", {
        method: "POST",
        body: {
          message: trimmed,
          conversation_id: existingBackendConversationId ?? null,
        },
      });

      const ads: AdItem[] = (response?.response?.data?.top_ads || []).map((ad) => ({
        ad_id: ad.ad_id,
        product_name: ad.title || `広告 #${ad.ad_id}`,
        hit_score: Math.round(Number(ad.hit_score || 0)),
        advertiser_name: ad.advertiser_name,
      }));

      const assistantMsg: ChatMsg = {
        role: "assistant",
        content: response.response?.message || "応答が空でした。",
        timestamp: formatTimestamp(new Date()),
        ads,
      };

      const withResponse = [...updatedMessages, assistantMsg];
      setMessages(withResponse);
      persistConversation(convId, withResponse, latestConversations, response.conversation_id);
    } catch {
      const errorMsg: ChatMsg = {
        role: "assistant",
        content: "AI応答の取得に失敗しました。しばらく経ってから再試行してください。",
        timestamp: formatTimestamp(new Date()),
      };
      const withError = [...updatedMessages, errorMsg];
      setMessages(withError);
      persistConversation(convId, withError, latestConversations, existingBackendConversationId);
    } finally {
      setIsLoading(false);
    }
  }, [inputValue, isLoading, messages, activeConversationId, conversations, persistConversation, getBackendConversationId]);

  // Keyboard handler
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // Quick action handler
  const handleQuickAction = useCallback((prompt: string) => {
    setInputValue(prompt);
    // Focus the textarea after setting value
    setTimeout(() => textareaRef.current?.focus(), 0);
  }, []);

  // Select conversation
  const handleSelectConversation = useCallback(
    (id: string) => {
      const conv = conversations.find((c) => c.id === id);
      if (conv) {
        setActiveConversationId(id);
        setMessages(conv.messages);
      }
    },
    [conversations],
  );

  // New conversation
  const handleNewConversation = useCallback(() => {
    setActiveConversationId(null);
    setMessages([]);
    setInputValue("");
  }, []);

  // Delete conversation
  const handleDeleteConversation = useCallback(
    (id: string) => {
      const updated = conversations.filter((c) => c.id !== id);
      setConversations(updated);
      saveConversations(updated);

      if (activeConversationId === id) {
        setActiveConversationId(null);
        setMessages([]);
      }
    },
    [conversations, activeConversationId],
  );

  // Suggested question click
  const handleSuggestedQuestion = useCallback(
    (prompt: string) => {
      setInputValue(prompt);
      setTimeout(() => {
        textareaRef.current?.focus();
      }, 0);
    },
    [],
  );

  const hasMessages = messages.length > 0;

  return (
    <div className="flex h-full bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Chat History Sidebar */}
      {showHistory && (
        <ChatHistory
          conversations={conversationMetas}
          activeId={activeConversationId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          onDelete={handleDeleteConversation}
        />
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowHistory((p) => !p)}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500 transition-colors"
              title={showHistory ? "履歴を隠す" : "履歴を表示"}
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                {showHistory ? (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M18.75 19.5l-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                )}
              </svg>
            </button>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[#4A7DFF] flex items-center justify-center">
                <svg className="w-4.5 h-4.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                </svg>
              </div>
              <div>
                <h2 className="text-[13px] font-semibold text-gray-900">AI広告アドバイザー</h2>
                <p className="text-[10px] text-gray-400">広告分析・戦略提案・クリエイティブ支援</p>
              </div>
            </div>
          </div>

          <button
            className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 transition-colors"
            title="設定"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {!hasMessages ? (
            /* Welcome state */
            <div className="flex flex-col items-center justify-center h-full">
              <div className="w-16 h-16 rounded-2xl bg-[#EEF2FF] flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                </svg>
              </div>
              <h3 className="text-[13px] font-semibold text-gray-900 mb-1">
                AI広告アドバイザーへようこそ
              </h3>
              <p className="text-[12px] text-gray-500 mb-6 text-center max-w-md">
                広告データの分析、勝ちパターンの発見、クリエイティブ戦略の提案など、
                広告運用に関するあらゆる質問にお答えします。
              </p>

              {/* Suggested questions grid */}
              <div className="grid grid-cols-2 gap-2 w-full max-w-lg">
                {SUGGESTED_QUESTIONS.map((q) => (
                  <button
                    key={q.title}
                    onClick={() => handleSuggestedQuestion(q.prompt)}
                    className="text-left px-3 py-2.5 rounded-lg border border-gray-200 hover:border-[#4A7DFF] hover:bg-[#EEF2FF] transition-all group"
                  >
                    <p className="text-[12px] font-medium text-gray-700 group-hover:text-[#4A7DFF]">
                      {q.title}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Message list */
            <>
              {messages.map((msg, idx) => (
                <ChatMessage
                  key={`${activeConversationId}-${idx}`}
                  message={msg}
                  onAdSelect={onAdSelect}
                />
              ))}
              {isLoading && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-200 px-4 py-3">
          {/* Quick Actions */}
          <div className="mb-2">
            <QuickActions onSelect={handleQuickAction} />
          </div>

          {/* Input Row */}
          <div className="flex items-end gap-2">
            <div className="flex-1 relative">
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="広告について質問してください..."
                rows={1}
                className="w-full resize-none rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5 text-[13px] text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-[#4A7DFF] focus:ring-1 focus:ring-[#4A7DFF] focus:bg-white transition-all"
                style={{ maxHeight: `${4 * 24}px` }}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || isLoading}
              className="flex-shrink-0 w-10 h-10 rounded-xl bg-[#4A7DFF] text-white flex items-center justify-center hover:bg-[#3A6DEF] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
            </button>
          </div>

          <p className="text-[10px] text-gray-400 mt-1.5 text-center">
            Enter で送信 / Shift+Enter で改行
          </p>
        </div>
      </div>
    </div>
  );
}
