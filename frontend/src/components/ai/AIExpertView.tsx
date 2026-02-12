"use client";

import { useState, useEffect } from "react";
import { rankingsApi, notificationsApi } from "@/lib/api";

type AITab = "search" | "notifications" | "insights";

// Mock search results
const mockSearchResults = [
  { type: "ad", id: 1, title: "【医師監修】話題の美容セラムが初回980円", matchField: "title", platform: "YouTube", advertiser: "ビューティーラボ" },
  { type: "transcript", id: 2, title: "ダイエットサプリX 15秒動画", matchedText: "...たった2週間で実感できる効果を...", matchField: "transcript", platform: "TikTok", advertiser: "ヘルスケアジャパン" },
  { type: "text_detection", id: 3, title: "育毛トニックPRO 30秒", matchedText: "満足度98%", matchField: "video_text", platform: "YouTube", advertiser: "ヘアケアプロ" },
  { type: "landing_page", id: 4, title: "アイクリームモイスト LP", matchField: "lp_content", platform: "-", advertiser: "コスメティックス" },
];

const mockInsights = [
  { genre: "美容・コスメ", summary: "権威性訴求（医師監修）が増加傾向。初回割引の平均は78%OFF。", confidence: 92 },
  { genre: "健康食品", summary: "UGC風動画が急増。15秒ショート形式がCTR平均1.5倍。", confidence: 88 },
  { genre: "ヘアケア", summary: "悩み解決型フックが主流。返金保証の訴求が30%増加。", confidence: 85 },
];

const searchTypeLabels: Record<string, string> = {
  ad: "広告",
  transcript: "音声テキスト",
  text_detection: "動画テキスト",
  landing_page: "LP",
};

const searchTypeColors: Record<string, string> = {
  ad: "bg-blue-100 text-blue-700",
  transcript: "bg-purple-100 text-purple-700",
  text_detection: "bg-emerald-100 text-emerald-700",
  landing_page: "bg-amber-100 text-amber-700",
};

export default function AIExpertView() {
  const [activeTab, setActiveTab] = useState<AITab>("search");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchScope, setSearchScope] = useState("all");

  // Search state
  const [searchResults, setSearchResults] = useState(mockSearchResults);
  const [searchLoading, setSearchLoading] = useState(false);

  // Notification config state
  const [notifChannel, setNotifChannel] = useState("slack");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [notifyHitAds, setNotifyHitAds] = useState(true);
  const [notifyCompetitor, setNotifyCompetitor] = useState(true);
  const [notifyRanking, setNotifyRanking] = useState(false);
  const [watchedGenres, setWatchedGenres] = useState<string[]>(["美容・コスメ"]);
  const [notifConfigs, setNotifConfigs] = useState<Array<Record<string, unknown>>>([]);
  const [savingNotif, setSavingNotif] = useState(false);

  // Load existing notification configs on mount
  useEffect(() => {
    const loadConfigs = async () => {
      try {
        const response = await notificationsApi.listConfigs();
        const configs = response.data?.items || response.data?.results || response.data;
        if (Array.isArray(configs)) {
          setNotifConfigs(configs);
        }
      } catch (error) {
        console.warn("Failed to load notification configs:", error);
      }
    };
    loadConfigs();
  }, []);

  // Search handler
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    try {
      const response = await rankingsApi.proSearch({
        q: searchQuery,
        search_scope: searchScope !== "all" ? searchScope : undefined,
      });
      const items = response.data?.items || response.data?.results || response.data;
      if (Array.isArray(items) && items.length > 0) {
        const mapped = items.map((item: Record<string, unknown>) => ({
          type: (item.type as string) || "ad",
          id: (item.id as number) || 0,
          title: (item.title as string) || "",
          matchedText: (item.matched_text as string) || undefined,
          matchField: (item.match_field as string) || "",
          platform: (item.platform as string) || "",
          advertiser: (item.advertiser_name as string) || "",
        }));
        setSearchResults(mapped);
      } else {
        setSearchResults([]);
      }
    } catch (error) {
      console.warn("Search API unavailable, using mock data:", error);
      setSearchResults(mockSearchResults);
    } finally {
      setSearchLoading(false);
    }
  };

  // Save notification config handler
  const handleSaveNotifConfig = async () => {
    setSavingNotif(true);
    try {
      await notificationsApi.createConfig({
        channel_type: notifChannel,
        webhook_url: notifChannel === "slack" ? webhookUrl : undefined,
        api_token: notifChannel === "chatwork" ? webhookUrl : undefined,
        notify_new_hit_ads: notifyHitAds,
        notify_competitor_activity: notifyCompetitor,
        watched_genres: watchedGenres,
      });
      // Reload configs after save
      const response = await notificationsApi.listConfigs();
      const configs = response.data?.items || response.data?.results || response.data;
      if (Array.isArray(configs)) {
        setNotifConfigs(configs);
      }
    } catch (error) {
      console.warn("Failed to save notification config:", error);
    } finally {
      setSavingNotif(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">AI専門家</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">Pro-Search・AIインサイト・通知設定</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 px-5 border-b border-gray-200 bg-[#f8f9fc]">
        {([
          { id: "search" as AITab, label: "Pro-Search" },
          { id: "insights" as AITab, label: "AIインサイト" },
          { id: "notifications" as AITab, label: "通知設定" },
        ]).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-[12px] font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-[#4A7DFF] text-[#4A7DFF] bg-white"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {/* Pro-Search */}
        {activeTab === "search" && (
          <div className="p-5 space-y-4">
            <div className="card">
              <h3 className="text-[13px] font-bold text-gray-900 mb-2">Pro-Search</h3>
              <p className="text-[11px] text-gray-500 mb-3">
                広告タイトル・動画内テキスト(OCR)・音声テキスト(文字起こし)・LP本文を横断検索
              </p>
              <div className="flex items-center gap-2 mb-2">
                <input
                  type="text"
                  placeholder="キーワードを入力..."
                  className="input text-xs flex-1"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <select
                  className="select-filter text-xs"
                  value={searchScope}
                  onChange={(e) => setSearchScope(e.target.value)}
                >
                  <option value="all">全て</option>
                  <option value="ads">広告のみ</option>
                  <option value="transcript">音声テキスト</option>
                  <option value="text">動画テキスト</option>
                  <option value="lp">LP</option>
                </select>
                <button className="btn-primary text-xs whitespace-nowrap" onClick={handleSearch} disabled={searchLoading}>
                  {searchLoading ? (
                    <div className="h-3.5 w-3.5 mr-1 inline-block animate-spin rounded-full border-2 border-white border-t-transparent" />
                  ) : (
                    <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                    </svg>
                  )}
                  検索
                </button>
              </div>
            </div>

            {/* Results */}
            <div className="space-y-2">
              <p className="text-[11px] text-gray-400">{searchResults.length}件の結果</p>
              {searchResults.map((r) => (
                <div key={`${r.type}-${r.id}`} className="card hover:shadow-md transition-shadow cursor-pointer">
                  <div className="flex items-start gap-3">
                    <span className={`badge text-[9px] shrink-0 mt-0.5 ${searchTypeColors[r.type]}`}>
                      {searchTypeLabels[r.type]}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-[12px] font-medium text-gray-900">{r.title}</p>
                      {r.matchedText && (
                        <p className="text-[11px] text-gray-500 mt-0.5">
                          ...{r.matchedText}...
                        </p>
                      )}
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-gray-400">
                        <span>{r.platform}</span>
                        <span>·</span>
                        <span>{r.advertiser}</span>
                        <span>·</span>
                        <span className="text-[#4A7DFF]">マッチ: {r.matchField}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* AI Insights */}
        {activeTab === "insights" && (
          <div className="p-5 space-y-4">
            <div className="card bg-gradient-to-r from-blue-50 to-indigo-50">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
                <h3 className="text-[13px] font-bold text-gray-900">AI市場インサイト</h3>
              </div>
              <p className="text-[11px] text-gray-600">
                収集した広告データとLP分析結果から、AIが自動的にジャンル別のトレンドと戦略的インサイトを生成します。
              </p>
            </div>

            {mockInsights.map((insight, i) => (
              <div key={i} className="card">
                <div className="flex items-center justify-between mb-2">
                  <span className="badge-blue text-[10px] font-bold">{insight.genre}</span>
                  <span className="text-[9px] text-gray-400">信頼度 {insight.confidence}%</span>
                </div>
                <p className="text-[12px] text-gray-800 leading-relaxed">{insight.summary}</p>
                <div className="h-1 bg-gray-100 rounded-full mt-2 overflow-hidden">
                  <div className="h-full rounded-full bg-[#4A7DFF]" style={{ width: `${insight.confidence}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Notification Settings */}
        {activeTab === "notifications" && (
          <div className="p-5 space-y-4">
            <div className="card">
              <h3 className="text-[13px] font-bold text-gray-900 mb-3">通知チャンネル設定</h3>
              <p className="text-[11px] text-gray-500 mb-3">
                ヒット広告の検出や競合の動きをSlack/Chatworkに自動通知します。
              </p>

              <div className="space-y-3">
                <div>
                  <label className="text-[10px] text-gray-500 font-medium">チャンネルタイプ</label>
                  <div className="flex gap-2 mt-1">
                    {["slack", "chatwork"].map((ch) => (
                      <button
                        key={ch}
                        onClick={() => setNotifChannel(ch)}
                        className={`px-3 py-1.5 rounded text-[11px] font-medium transition-colors ${
                          notifChannel === ch
                            ? "bg-[#4A7DFF] text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                        }`}
                      >
                        {ch === "slack" ? "Slack" : "Chatwork"}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-[10px] text-gray-500 font-medium">
                    {notifChannel === "slack" ? "Webhook URL" : "APIトークン"}
                  </label>
                  <input
                    type="text"
                    className="input text-xs mt-1 w-full"
                    placeholder={notifChannel === "slack" ? "https://hooks.slack.com/services/..." : "APIトークンを入力"}
                    value={webhookUrl}
                    onChange={(e) => setWebhookUrl(e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div className="card">
              <h3 className="text-[13px] font-bold text-gray-900 mb-3">通知条件</h3>
              <div className="space-y-2">
                {[
                  { label: "ヒット広告を検出", desc: "急上昇中の広告を検出した時に通知", checked: notifyHitAds, onChange: setNotifyHitAds },
                  { label: "競合アクティビティ", desc: "監視中の競合が新しい広告を出稿した時に通知", checked: notifyCompetitor, onChange: setNotifyCompetitor },
                  { label: "ランキング変動", desc: "監視中のジャンルでランキングが大きく変動した時に通知", checked: notifyRanking, onChange: setNotifyRanking },
                ].map((item) => (
                  <label key={item.label} className="flex items-start gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={item.checked}
                      onChange={(e) => item.onChange(e.target.checked)}
                      className="mt-0.5 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]"
                    />
                    <div>
                      <p className="text-[12px] font-medium text-gray-900">{item.label}</p>
                      <p className="text-[10px] text-gray-400">{item.desc}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="card">
              <h3 className="text-[13px] font-bold text-gray-900 mb-3">監視ジャンル</h3>
              <div className="flex flex-wrap gap-2">
                {["美容・コスメ", "健康食品", "ヘアケア", "ダイエット", "スキンケア", "サプリ"].map((g) => (
                  <button
                    key={g}
                    onClick={() => setWatchedGenres((prev) =>
                      prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]
                    )}
                    className={`px-3 py-1 rounded-full text-[10px] font-medium transition-colors ${
                      watchedGenres.includes(g)
                        ? "bg-[#4A7DFF] text-white"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {g}
                  </button>
                ))}
              </div>
            </div>

            {/* Existing configs */}
            {notifConfigs.length > 0 && (
              <div className="card">
                <h3 className="text-[13px] font-bold text-gray-900 mb-3">登録済み設定</h3>
                <div className="space-y-1">
                  {notifConfigs.map((cfg, i) => (
                    <div key={(cfg.id as number) || i} className="flex items-center gap-3 text-[11px] text-gray-600 p-2 bg-gray-50 rounded">
                      <span className="badge text-[9px] bg-blue-100 text-blue-700">{(cfg.channel_type as string) || "slack"}</span>
                      <span>{(cfg.is_active as boolean) ? "有効" : "無効"}</span>
                      <span className="text-gray-400 ml-auto">{(cfg.created_at as string) || ""}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <button className="btn-primary text-xs" onClick={handleSaveNotifConfig} disabled={savingNotif}>
                {savingNotif ? "保存中..." : "設定を保存"}
              </button>
              <button
                className="px-3 py-1.5 rounded bg-gray-100 text-gray-600 text-xs font-medium hover:bg-gray-200 transition-colors"
                onClick={async () => {
                  if (notifConfigs.length > 0 && notifConfigs[0].id) {
                    try {
                      await notificationsApi.testNotification(notifConfigs[0].id as number);
                    } catch (error) {
                      console.warn("Test notification failed:", error);
                    }
                  }
                }}
              >
                テスト通知を送信
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
