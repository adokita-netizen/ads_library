"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

interface KeyDefinition {
  key_name: string;
  label: string;
  placeholder: string;
}

interface PlatformDefinition {
  platform: string;
  label: string;
  keys: KeyDefinition[];
  docs_url: string;
  setup_guide: string;
  cost_info: string;
  difficulty: "easy" | "medium" | "hard";
  fallback_note: string;
}

interface KeyStatus {
  platform: string;
  key_name: string;
  is_set: boolean;
  masked_value: string | null;
  updated_at: string | null;
}

// Fallback platform definitions — always show key input sections even when backend is unreachable
const FALLBACK_PLATFORMS: PlatformDefinition[] = [
  {
    platform: "youtube", label: "YouTube",
    keys: [{ key_name: "api_key", label: "YouTube Data API Key", placeholder: "AIzaSy..." }],
    docs_url: "https://console.cloud.google.com/apis/credentials",
    setup_guide: "Google Cloud Console → APIとサービス → 認証情報 → APIキーを作成 → YouTube Data API v3を有効化",
    cost_info: "無料（APIキー不要でも動作。Ads Transparency Centerは公開データ）",
    difficulty: "easy",
    fallback_note: "APIキーなしでもGoogle Ads Transparency Centerから自動取得します",
  },
  {
    platform: "meta", label: "Meta (Facebook / Instagram)",
    keys: [{ key_name: "access_token", label: "Meta Graph API アクセストークン", placeholder: "EAAGm0PX..." }],
    docs_url: "https://developers.facebook.com/tools/explorer/",
    setup_guide: "1. developers.facebook.com でアカウント作成（無料）\n2. 「マイアプリ」→ 新規アプリ作成（種類:ビジネス）\n3. Graph APIエクスプローラーを開く\n4. 右上の「トークンを取得」→ ユーザーアクセストークン\n5. ads_read権限を追加して「Generate Access Token」\n※ トークンは約1時間で期限切れ。長期トークン（60日）は「アクセストークンデバッガー」で延長可能",
    cost_info: "無料（Meta Ad Library APIは誰でも利用可能。開発者アカウント登録のみ必要）",
    difficulty: "medium",
    fallback_note: "APIキーなしでもFacebook Ad Library公開ページからスクレイピングで取得を試みます",
  },
  {
    platform: "tiktok", label: "TikTok",
    keys: [{ key_name: "access_token", label: "TikTok Marketing API トークン", placeholder: "" }],
    docs_url: "https://business-api.tiktok.com/portal/docs",
    setup_guide: "1. business-api.tiktok.com でビジネスアカウント作成\n2. Marketing API → アプリ作成\n3. 審査申請（承認まで数日〜数週間）\n4. 承認後、アクセストークンを発行",
    cost_info: "無料（ただしビジネスアカウント審査が必要、承認まで時間がかかる場合あり）",
    difficulty: "hard",
    fallback_note: "APIキーなしでもTikTok Ad Library公開ページからスクレイピングで取得を試みます",
  },
  {
    platform: "x_twitter", label: "X (Twitter)",
    keys: [{ key_name: "bearer_token", label: "Bearer Token", placeholder: "AAAAAAAAAA..." }],
    docs_url: "https://developer.x.com/en/portal/dashboard",
    setup_guide: "1. developer.x.com で開発者アカウント申請\n2. Free/Basic/Proプランを選択\n3. Projects & Apps → App作成\n4. Keys and Tokens → Bearer Token生成",
    cost_info: "Freeプラン: 月100ポスト読取のみ。Basic: $100/月。Pro: $5,000/月。広告透明性APIのアクセスにはBasic以上が必要な場合あり",
    difficulty: "hard",
    fallback_note: "APIキーなしでもX Ads Transparency公開ページからスクレイピングで取得を試みます",
  },
  {
    platform: "line", label: "LINE",
    keys: [{ key_name: "access_token", label: "LINE Ads API アクセストークン", placeholder: "" }],
    docs_url: "https://developers.line.biz/",
    setup_guide: "LINE Ads Platform APIはパートナー企業向けです。LINE広告のアカウントをお持ちの場合、担当者にAPI利用を相談してください",
    cost_info: "パートナー契約が必要（一般公開APIではありません）",
    difficulty: "hard",
    fallback_note: "APIキーなしでもLINE広告公開ページからスクレイピングで取得を試みます",
  },
  {
    platform: "yahoo", label: "Yahoo!広告",
    keys: [
      { key_name: "api_key", label: "Yahoo! Ads API アプリケーションID", placeholder: "" },
      { key_name: "api_secret", label: "Yahoo! Ads API シークレット", placeholder: "" },
    ],
    docs_url: "https://ads-developers.yahoo.co.jp/",
    setup_guide: "1. Yahoo!デベロッパーネットワークでアプリ登録\n2. Yahoo!広告アカウントとの連携が必要\n※ 自社のYahoo!広告アカウントのデータのみ取得可能",
    cost_info: "無料（ただし自社Yahoo!広告アカウント必須。他社の広告データは取得不可）",
    difficulty: "hard",
    fallback_note: "APIキーなしでもYahoo!広告透明性センターから公開データの取得を試みます",
  },
  {
    platform: "pinterest", label: "Pinterest",
    keys: [{ key_name: "access_token", label: "Pinterest API アクセストークン", placeholder: "pina_..." }],
    docs_url: "https://developers.pinterest.com/",
    setup_guide: "1. developers.pinterest.com でビジネスアカウント作成（無料）\n2. アプリ作成 → OAuth認証\n3. アクセストークン取得",
    cost_info: "無料（ビジネスアカウント登録が必要）",
    difficulty: "medium",
    fallback_note: "APIキーなしでもPinterest広告透明性ページからスクレイピングで取得を試みます",
  },
  {
    platform: "smartnews", label: "SmartNews",
    keys: [{ key_name: "api_key", label: "SmartNews Ads API キー", placeholder: "" }],
    docs_url: "https://developers.smartnews.com/",
    setup_guide: "SmartNews Ads APIはパートナー企業向けです。SmartNews広告出稿中の場合、担当者にAPI利用を相談してください",
    cost_info: "パートナー契約が必要（一般公開APIではありません）",
    difficulty: "hard",
    fallback_note: "APIキーなしでもSmartNewsフィードから広告コンテンツの検出を試みます",
  },
  {
    platform: "google_ads", label: "Google Ads",
    keys: [
      { key_name: "developer_token", label: "開発者トークン", placeholder: "" },
      { key_name: "client_id", label: "OAuth Client ID", placeholder: "xxx.apps.googleusercontent.com" },
      { key_name: "client_secret", label: "OAuth Client Secret", placeholder: "" },
      { key_name: "refresh_token", label: "OAuth Refresh Token", placeholder: "1//0..." },
    ],
    docs_url: "https://developers.google.com/google-ads/api/docs/get-started/introduction",
    setup_guide: "1. Google Ads管理アカウントを作成\n2. API Center → 開発者トークン申請（審査あり）\n3. Google Cloud Console → OAuth 2.0クライアント作成\n4. OAuthフローでRefresh Token取得\n※ 開発者トークンの審査は数日〜数週間",
    cost_info: "無料（ただし管理アカウント・開発者トークン審査が必要。自社アカウントのデータのみ）",
    difficulty: "hard",
    fallback_note: "APIキーなしでもGoogle Ads Transparency Centerから公開データの取得を試みます",
  },
  {
    platform: "gunosy", label: "Gunosy",
    keys: [{ key_name: "api_key", label: "Gunosy Ads API キー", placeholder: "" }],
    docs_url: "https://gunosy.co.jp/ad/",
    setup_guide: "Gunosy Ads APIはパートナー企業向けです。Gunosy広告出稿中の場合、担当者にAPI利用を相談してください",
    cost_info: "パートナー契約が必要（一般公開APIではありません）",
    difficulty: "hard",
    fallback_note: "APIキーなしでもGunosyフィードから広告コンテンツの検出を試みます",
  },
  {
    platform: "openai", label: "OpenAI (AI分析用)",
    keys: [{ key_name: "api_key", label: "OpenAI API Key", placeholder: "sk-..." }],
    docs_url: "https://platform.openai.com/api-keys",
    setup_guide: "1. platform.openai.com でアカウント作成\n2. API Keys → Create new secret key\n3. 支払い方法を登録（従量課金）",
    cost_info: "従量課金（GPT-4o: 約$2.5/100万入力トークン。月$5〜20程度の利用が目安）",
    difficulty: "easy",
    fallback_note: "AI分析機能（スクリプト生成、コピー分析等）に必要。未設定の場合、AI分析機能は利用不可",
  },
  {
    platform: "anthropic", label: "Anthropic (AI分析用)",
    keys: [{ key_name: "api_key", label: "Anthropic API Key", placeholder: "sk-ant-..." }],
    docs_url: "https://console.anthropic.com/settings/keys",
    setup_guide: "1. console.anthropic.com でアカウント作成\n2. API Keys → Create Key\n3. 支払い方法を登録（従量課金）",
    cost_info: "従量課金（Claude Sonnet: 約$3/100万入力トークン。OpenAIの代替として利用可能）",
    difficulty: "easy",
    fallback_note: "OpenAIの代替として利用可能。両方未設定の場合、AI分析機能は利用不可",
  },
];

export default function APIKeysSettings() {
  const [platforms, setPlatforms] = useState<PlatformDefinition[]>(FALLBACK_PLATFORMS);
  const [keyStatuses, setKeyStatuses] = useState<KeyStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingKey, setEditingKey] = useState<{ platform: string; key_name: string } | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [expandedPlatform, setExpandedPlatform] = useState<string | null>(null);
  const [backendAvailable, setBackendAvailable] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [platformsData, keysData] = await Promise.all([
        fetchApi<{ platforms: PlatformDefinition[] }>("/settings/api-keys/platforms").catch(() => null),
        fetchApi<{ keys: KeyStatus[] }>("/settings/api-keys").catch(() => null),
      ]);
      if (platformsData?.platforms && platformsData.platforms.length > 0) {
        setPlatforms(platformsData.platforms);
        setBackendAvailable(true);
      } else {
        setPlatforms(FALLBACK_PLATFORMS);
        setBackendAvailable(false);
      }
      setKeyStatuses(keysData?.keys || []);
    } catch (err) {
      console.error("Failed to load settings:", err);
      setPlatforms(FALLBACK_PLATFORMS);
      setBackendAvailable(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const getKeyStatus = (platform: string, keyName: string): KeyStatus | undefined => {
    return keyStatuses.find((k) => k.platform === platform && k.key_name === keyName);
  };

  const isPlatformConfigured = (platform: string): boolean => {
    return keyStatuses.some((k) => k.platform === platform && k.is_set);
  };

  const handleSave = async (platform: string, keyName: string) => {
    if (!editValue.trim()) return;
    setSaving(true);
    setMessage(null);
    try {
      await fetchApi("/settings/api-keys", {
        method: "POST",
        body: { platform, key_name: keyName, key_value: editValue.trim() },
      });
      setMessage({ type: "success", text: "保存しました" });
      setEditingKey(null);
      setEditValue("");
      await loadData();
    } catch (err) {
      setMessage({ type: "error", text: "保存に失敗しました" });
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (platform: string, keyName: string) => {
    if (!confirm("このAPIキーを削除しますか?")) return;
    try {
      await fetchApi("/settings/api-keys", {
        method: "DELETE",
        body: { platform, key_name: keyName },
      });
      setMessage({ type: "success", text: "削除しました" });
      await loadData();
    } catch (err) {
      setMessage({ type: "error", text: "削除に失敗しました" });
      console.error(err);
    }
  };

  // Count configured platforms
  const configuredCount = platforms.filter((p) => isPlatformConfigured(p.platform)).length;

  // Split into ad platforms and AI platforms
  const adPlatforms = platforms.filter((p) => !["openai", "anthropic"].includes(p.platform));
  const aiPlatforms = platforms.filter((p) => ["openai", "anthropic"].includes(p.platform));

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">API キー設定</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">
            各広告媒体のAPIキーを設定すると、リアルデータの取得が可能になります
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">
            {configuredCount}/{platforms.length} 媒体設定済み
          </span>
          <div className="w-24 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-[#4A7DFF] rounded-full transition-all"
              style={{ width: `${platforms.length > 0 ? (configuredCount / platforms.length) * 100 : 0}%` }}
            />
          </div>
        </div>
      </div>

      {/* Message */}
      {message && (
        <div
          className={`mx-5 mt-3 px-3 py-2 rounded text-xs ${
            message.type === "success"
              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
              : "bg-red-50 text-red-700 border border-red-200"
          }`}
        >
          {message.text}
          <button className="ml-2 underline" onClick={() => setMessage(null)}>
            閉じる
          </button>
        </div>
      )}

      {/* Backend unavailable warning */}
      {!loading && !backendAvailable && (
        <div className="mx-5 mt-3 px-3 py-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
          バックエンドサーバーに接続できません。APIキーの保存はサーバー起動後に行えます。
          <button className="ml-2 underline font-medium" onClick={() => { setLoading(true); loadData(); }}>
            再接続
          </button>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto custom-scrollbar px-5 py-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
            <span className="ml-2 text-xs text-gray-400">読み込み中...</span>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Setup Guide Box */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 className="text-[13px] font-bold text-blue-900 mb-2">セットアップ手順</h3>
              <ol className="text-[12px] text-blue-800 space-y-1.5 list-decimal ml-4">
                <li>下記の各媒体セクションを展開し、APIキーを入力してください</li>
                <li>キーは保存ボタンを押した時点で即座にデータベースに保存されます</li>
                <li>保存後、「検索」画面からクロールを実行すると、リアルデータが取得されます</li>
                <li><strong>APIキー未設定でもクロール可能</strong> — 各媒体の公開ページからスクレイピングで取得を試みます</li>
              </ol>
              <p className="text-[11px] text-blue-600 mt-2">
                ※ 各媒体のAPIキー取得方法・費用・難易度は、各セクション内をご確認ください
              </p>
            </div>

            {/* Quick Start Recommendation */}
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
              <h3 className="text-[13px] font-bold text-emerald-900 mb-2">おすすめの始め方</h3>
              <div className="text-[12px] text-emerald-800 space-y-1.5">
                <p>1. まずは<strong>APIキーなし</strong>でクロールを試してください（スクレイピングで動作します）</p>
                <p>2. より多くのデータが必要なら <strong>Meta (無料)</strong> のAPIキーを設定</p>
                <p>3. AI分析を使うなら <strong>OpenAI</strong> または <strong>Anthropic</strong> のキーを設定</p>
                <p>4. YouTube はAPIキー不要で公開データから自動取得します</p>
              </div>
            </div>

            {/* Ad Platforms */}
            <div>
              <h3 className="text-[13px] font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 7.5l16.5-4.125M12 6.75c-2.708 0-5.363.224-7.948.655C2.999 7.58 2.25 8.507 2.25 9.574v9.176A2.25 2.25 0 004.5 21h15a2.25 2.25 0 002.25-2.25V9.574c0-1.067-.75-1.994-1.802-2.169A48.329 48.329 0 0012 6.75z" />
                </svg>
                広告媒体 API キー
              </h3>
              <div className="space-y-2">
                {adPlatforms.map((platform) => (
                  <PlatformCard
                    key={platform.platform}
                    platform={platform}
                    isConfigured={isPlatformConfigured(platform.platform)}
                    isExpanded={expandedPlatform === platform.platform}
                    onToggle={() =>
                      setExpandedPlatform(
                        expandedPlatform === platform.platform ? null : platform.platform
                      )
                    }
                    getKeyStatus={getKeyStatus}
                    editingKey={editingKey}
                    editValue={editValue}
                    saving={saving}
                    onEdit={(keyName) => {
                      setEditingKey({ platform: platform.platform, key_name: keyName });
                      setEditValue("");
                    }}
                    onCancel={() => {
                      setEditingKey(null);
                      setEditValue("");
                    }}
                    onEditValueChange={setEditValue}
                    onSave={handleSave}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            </div>

            {/* AI Platforms */}
            <div>
              <h3 className="text-[13px] font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
                AI サービス API キー
              </h3>
              <div className="space-y-2">
                {aiPlatforms.map((platform) => (
                  <PlatformCard
                    key={platform.platform}
                    platform={platform}
                    isConfigured={isPlatformConfigured(platform.platform)}
                    isExpanded={expandedPlatform === platform.platform}
                    onToggle={() =>
                      setExpandedPlatform(
                        expandedPlatform === platform.platform ? null : platform.platform
                      )
                    }
                    getKeyStatus={getKeyStatus}
                    editingKey={editingKey}
                    editValue={editValue}
                    saving={saving}
                    onEdit={(keyName) => {
                      setEditingKey({ platform: platform.platform, key_name: keyName });
                      setEditValue("");
                    }}
                    onCancel={() => {
                      setEditingKey(null);
                      setEditValue("");
                    }}
                    onEditValueChange={setEditValue}
                    onSave={handleSave}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            </div>

            {/* Environment Variables Note */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <h3 className="text-[12px] font-bold text-gray-600 mb-1">環境変数について</h3>
              <p className="text-[11px] text-gray-500">
                UIで設定したAPIキーは環境変数(.env)よりも優先されます。
                環境変数での設定も引き続きサポートされています。UIで設定した場合、環境変数は上書きされません
                (UIキーが優先して使用されます)。
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Platform Card Component ───────────────────────────────── */

interface PlatformCardProps {
  platform: PlatformDefinition;
  isConfigured: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  getKeyStatus: (platform: string, keyName: string) => KeyStatus | undefined;
  editingKey: { platform: string; key_name: string } | null;
  editValue: string;
  saving: boolean;
  onEdit: (keyName: string) => void;
  onCancel: () => void;
  onEditValueChange: (value: string) => void;
  onSave: (platform: string, keyName: string) => void;
  onDelete: (platform: string, keyName: string) => void;
}

function PlatformCard({
  platform,
  isConfigured,
  isExpanded,
  onToggle,
  getKeyStatus,
  editingKey,
  editValue,
  saving,
  onEdit,
  onCancel,
  onEditValueChange,
  onSave,
  onDelete,
}: PlatformCardProps) {
  const allKeysConfigured = platform.keys.every(
    (k) => getKeyStatus(platform.platform, k.key_name)?.is_set
  );

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <span
            className={`w-2 h-2 rounded-full ${
              allKeysConfigured ? "bg-emerald-500" : isConfigured ? "bg-amber-400" : "bg-gray-300"
            }`}
          />
          <span className="text-[13px] font-medium text-gray-900">{platform.label}</span>
          {allKeysConfigured ? (
            <span className="text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded font-medium">
              設定済み
            </span>
          ) : isConfigured ? (
            <span className="text-[10px] bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded font-medium">
              一部設定済み
            </span>
          ) : (
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
              platform.difficulty === "easy" ? "bg-emerald-50 text-emerald-600" :
              platform.difficulty === "medium" ? "bg-amber-50 text-amber-600" :
              "bg-gray-100 text-gray-500"
            }`}>
              {platform.difficulty === "easy" ? "簡単・無料" : platform.difficulty === "medium" ? "無料" : "要契約"}
            </span>
          )}
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-gray-100 px-4 py-3">
          {/* Cost & Difficulty Info */}
          <div className="flex items-center gap-3 mb-3">
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
              platform.difficulty === "easy" ? "bg-emerald-100 text-emerald-700" :
              platform.difficulty === "medium" ? "bg-amber-100 text-amber-700" :
              "bg-red-100 text-red-700"
            }`}>
              {platform.difficulty === "easy" ? "簡単" : platform.difficulty === "medium" ? "普通" : "難しい"}
            </span>
            <span className="text-[11px] text-gray-600">{platform.cost_info}</span>
          </div>

          {/* Fallback Note */}
          <div className="bg-amber-50 border border-amber-200 rounded p-2.5 mb-3">
            <p className="text-[11px] text-amber-700">
              <span className="font-semibold">APIキーなしの場合:</span> {platform.fallback_note}
            </p>
          </div>

          {/* Setup Guide */}
          <div className="bg-gray-50 rounded p-3 mb-3">
            <p className="text-[11px] font-semibold text-gray-600 mb-1">取得手順:</p>
            <p className="text-[11px] text-gray-500 whitespace-pre-line">{platform.setup_guide}</p>
            <a
              href={platform.docs_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] text-[#4A7DFF] hover:underline mt-1"
            >
              公式ドキュメント
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
            </a>
          </div>

          {/* Key Fields */}
          <div className="space-y-3">
            {platform.keys.map((keyDef) => {
              const status = getKeyStatus(platform.platform, keyDef.key_name);
              const isEditing =
                editingKey?.platform === platform.platform &&
                editingKey?.key_name === keyDef.key_name;

              return (
                <div key={keyDef.key_name} className="flex flex-col gap-1.5">
                  <label className="text-[11px] font-medium text-gray-600">{keyDef.label}</label>

                  {isEditing ? (
                    <div className="flex gap-2">
                      <input
                        type="password"
                        value={editValue}
                        onChange={(e) => onEditValueChange(e.target.value)}
                        placeholder={keyDef.placeholder || "APIキーを入力..."}
                        className="flex-1 px-3 py-1.5 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-[#4A7DFF] focus:border-[#4A7DFF] font-mono"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === "Enter") onSave(platform.platform, keyDef.key_name);
                          if (e.key === "Escape") onCancel();
                        }}
                      />
                      <button
                        onClick={() => onSave(platform.platform, keyDef.key_name)}
                        disabled={saving || !editValue.trim()}
                        className="px-3 py-1.5 text-[11px] font-medium bg-[#4A7DFF] text-white rounded hover:bg-[#3a6ae6] disabled:opacity-50 transition-colors"
                      >
                        {saving ? "保存中..." : "保存"}
                      </button>
                      <button
                        onClick={onCancel}
                        className="px-3 py-1.5 text-[11px] font-medium bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors"
                      >
                        キャンセル
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      {status?.is_set ? (
                        <>
                          <div className="flex-1 px-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded font-mono text-gray-500">
                            {status.masked_value}
                          </div>
                          <button
                            onClick={() => onEdit(keyDef.key_name)}
                            className="px-3 py-1.5 text-[11px] font-medium bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors"
                          >
                            変更
                          </button>
                          <button
                            onClick={() => onDelete(platform.platform, keyDef.key_name)}
                            className="px-3 py-1.5 text-[11px] font-medium bg-red-50 text-red-600 rounded hover:bg-red-100 transition-colors"
                          >
                            削除
                          </button>
                        </>
                      ) : (
                        <>
                          <div className="flex-1 px-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded text-gray-400 italic">
                            未設定
                          </div>
                          <button
                            onClick={() => onEdit(keyDef.key_name)}
                            className="px-3 py-1.5 text-[11px] font-medium bg-[#4A7DFF] text-white rounded hover:bg-[#3a6ae6] transition-colors"
                          >
                            設定
                          </button>
                        </>
                      )}
                    </div>
                  )}

                  {status?.updated_at && (
                    <p className="text-[10px] text-gray-400">
                      最終更新: {new Date(status.updated_at).toLocaleString("ja-JP")}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
