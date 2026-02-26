"use client";

import { useState, useEffect, useCallback } from "react";
import type {
  MetaTokenStatus,
  MetaAdAccount,
  MetaAvailableAccount,
  MetaCampaign,
  MetaAdSet,
  MetaAd,
  MetaInsight,
} from "@/types";
import { metaMarketingApi } from "@/lib/api";
import MetaCampaignTable from "./MetaCampaignTable";
import MetaAdSetTable from "./MetaAdSetTable";
import MetaAdCard from "./MetaAdCard";
import MetaInsightsChart from "./MetaInsightsChart";
import CreativeAnalysisPanel from "./CreativeAnalysisPanel";
import ABTestView from "./ABTestView";
import OptimizationDashboard from "./OptimizationDashboard";
import PerformanceDashboard from "./PerformanceDashboard";
import CreativePerformanceView from "./CreativePerformanceView";
import ConfirmModal from "@/components/common/ConfirmModal";

type Tab = "accounts" | "performance" | "campaigns" | "adsets" | "ads" | "creative-perf" | "creative-analysis" | "ab-test" | "optimization";

const ACCOUNT_STATUS_MAP: Record<number, { label: string; color: string }> = {
  1: { label: "アクティブ", color: "text-green-600 bg-green-50" },
  2: { label: "無効", color: "text-red-600 bg-red-50" },
  3: { label: "未決済", color: "text-amber-600 bg-amber-50" },
  7: { label: "保留中", color: "text-gray-600 bg-gray-50" },
  9: { label: "レビュー中", color: "text-blue-600 bg-blue-50" },
  101: { label: "クローズ済み", color: "text-gray-500 bg-gray-100" },
};

export default function MetaAdsView() {
  const [activeTab, setActiveTab] = useState<Tab>("accounts");
  const [tokenStatus, setTokenStatus] = useState<MetaTokenStatus | null>(null);
  const [accounts, setAccounts] = useState<MetaAdAccount[]>([]);
  const [availableAccounts, setAvailableAccounts] = useState<MetaAvailableAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);

  // Data states (Phase 2+)
  const [campaigns, setCampaigns] = useState<MetaCampaign[]>([]);
  const [adSets, setAdSets] = useState<MetaAdSet[]>([]);
  const [ads, setAds] = useState<MetaAd[]>([]);
  const [insights, setInsights] = useState<MetaInsight[]>([]);

  const [loading, setLoading] = useState(true);
  const [loadingAccounts, setLoadingAccounts] = useState(false);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [refreshingCampaigns, setRefreshingCampaigns] = useState(false);
  const [refreshingAdSets, setRefreshingAdSets] = useState(false);
  const [disconnectTarget, setDisconnectTarget] = useState<string | null>(null);
  const [campaignPage, setCampaignPage] = useState(1);
  const [campaignTotal, setCampaignTotal] = useState(0);
  const [adSetPage, setAdSetPage] = useState(1);
  const [adSetTotal, setAdSetTotal] = useState(0);
  const PAGE_SIZE = 20;

  // Load token status and connected accounts
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [tokenRes, accountsRes] = await Promise.all([
        metaMarketingApi.tokenStatus().catch(() => null),
        metaMarketingApi.listAccounts().catch(() => null),
      ]);
      if (tokenRes?.data) setTokenStatus(tokenRes.data);
      if (accountsRes?.data) {
        const accts = accountsRes.data.accounts || [];
        setAccounts(accts);
        setSelectedAccountId((prev) => prev || (accts.length > 0 ? accts[0].account_id : null));
      }
    } catch (err) {
      console.error("Failed to load meta marketing data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Load available accounts from Meta API
  const loadAvailableAccounts = async () => {
    setLoadingAccounts(true);
    try {
      const res = await metaMarketingApi.availableAccounts();
      setAvailableAccounts(res.data?.accounts || []);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || "取得に失敗しました";
      setMessage({ type: "error", text: `アカウント一覧の取得に失敗: ${detail}` });
    } finally {
      setLoadingAccounts(false);
    }
  };

  // Connect an account
  const connectAccount = async (acct: MetaAvailableAccount) => {
    setConnecting(acct.account_id);
    try {
      await metaMarketingApi.connectAccount({
        account_id: acct.account_id,
        account_name: acct.name,
        business_name: acct.business_name,
        currency: acct.currency || "JPY",
        timezone_name: acct.timezone_name || "Asia/Tokyo",
      });
      setMessage({ type: "success", text: `アカウント ${acct.name || acct.account_id} を接続しました` });
      await loadData();
      // Refresh available accounts to update is_connected
      await loadAvailableAccounts();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || "接続に失敗しました";
      setMessage({ type: "error", text: detail });
    } finally {
      setConnecting(null);
    }
  };

  // Disconnect an account
  const requestDisconnect = (accountId: string) => {
    setDisconnectTarget(accountId);
  };

  const confirmDisconnect = async () => {
    if (!disconnectTarget) return;
    const accountId = disconnectTarget;
    setDisconnectTarget(null);
    try {
      await metaMarketingApi.disconnectAccount(accountId);
      setMessage({ type: "success", text: "アカウントを切断しました" });
      await loadData();
    } catch (err: any) {
      setMessage({ type: "error", text: "切断に失敗しました" });
    }
  };

  // Load campaign data (Phase 2)
  const loadCampaigns = useCallback(async () => {
    if (!selectedAccountId) return;
    setRefreshingCampaigns(true);
    try {
      const res = await metaMarketingApi.listCampaigns({
        account_id: selectedAccountId,
        page: campaignPage,
        page_size: PAGE_SIZE,
      });
      setCampaigns(res.data?.campaigns || []);
      setCampaignTotal(res.data?.total || 0);
    } catch {
      setCampaigns([]);
    } finally {
      setRefreshingCampaigns(false);
    }
  }, [selectedAccountId, campaignPage]);

  const loadAdSets = useCallback(async () => {
    if (!selectedAccountId) return;
    setRefreshingAdSets(true);
    try {
      const res = await metaMarketingApi.listAdSets({
        account_id: selectedAccountId,
        page: adSetPage,
        page_size: PAGE_SIZE,
      });
      setAdSets(res.data?.ad_sets || []);
      setAdSetTotal(res.data?.total || 0);
    } catch {
      setAdSets([]);
    } finally {
      setRefreshingAdSets(false);
    }
  }, [selectedAccountId, adSetPage]);

  const loadAds = useCallback(async () => {
    if (!selectedAccountId) return;
    try {
      const res = await metaMarketingApi.listAds({ account_id: selectedAccountId });
      setAds(res.data?.ads || []);
    } catch {
      setAds([]);
    }
  }, [selectedAccountId]);

  const loadInsights = useCallback(async () => {
    if (!selectedAccountId) return;
    try {
      const res = await metaMarketingApi.getInsights({ account_id: selectedAccountId, entity_type: "campaign" });
      setInsights(res.data?.insights || []);
    } catch {
      setInsights([]);
    }
  }, [selectedAccountId]);

  // Load tab data when switching tabs
  useEffect(() => {
    if (activeTab === "campaigns") {
      loadCampaigns();
      loadInsights();
    }
    if (activeTab === "adsets") loadAdSets();
    if (activeTab === "ads") loadAds();
  }, [activeTab, loadCampaigns, loadAdSets, loadAds, loadInsights]);

  const tabs: { id: Tab; label: string }[] = [
    { id: "accounts", label: "アカウント" },
    { id: "performance", label: "パフォーマンス" },
    { id: "campaigns", label: "キャンペーン" },
    { id: "adsets", label: "広告セット" },
    { id: "ads", label: "広告" },
    { id: "creative-perf", label: "クリエイティブ×数値" },
    { id: "creative-analysis", label: "クリエイティブ分析" },
    { id: "ab-test", label: "A/Bテスト" },
    { id: "optimization", label: "最適化" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <h2 className="text-[15px] font-bold text-gray-900">自社広告管理</h2>
          <span className="text-[11px] text-gray-400">Meta Marketing API連携</span>
        </div>
        {selectedAccountId && accounts.length > 1 && (
          <select
            value={selectedAccountId}
            onChange={(e) => setSelectedAccountId(e.target.value)}
            className="text-[12px] border border-gray-200 rounded-lg px-2 py-1"
            aria-label="広告アカウント選択"
          >
            {accounts.map((a) => (
              <option key={a.account_id} value={a.account_id}>
                {a.account_name || a.account_id} ({a.account_id})
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Tabs */}
      <div
        className="flex border-b border-gray-200 bg-white px-5"
        role="tablist"
        aria-label="Meta広告管理タブ"
        onKeyDown={(e) => {
          const idx = tabs.findIndex((t) => t.id === activeTab);
          if (e.key === "ArrowRight") {
            e.preventDefault();
            const next = tabs[(idx + 1) % tabs.length];
            setActiveTab(next.id);
            (e.currentTarget.children[(idx + 1) % tabs.length] as HTMLElement)?.focus();
          } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            const prev = tabs[(idx - 1 + tabs.length) % tabs.length];
            setActiveTab(prev.id);
            (e.currentTarget.children[(idx - 1 + tabs.length) % tabs.length] as HTMLElement)?.focus();
          }
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`tabpanel-${tab.id}`}
            tabIndex={activeTab === tab.id ? 0 : -1}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-2 text-[12px] font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-[#4A7DFF] text-[#4A7DFF]"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Message */}
      {message && (
        <div
          className={`mx-5 mt-3 px-3 py-2 rounded-lg text-[12px] ${
            message.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
          }`}
        >
          {message.text}
          <button className="ml-2 underline text-[11px]" onClick={() => setMessage(null)}>
            閉じる
          </button>
        </div>
      )}

      {/* Content */}
      <div
        className="flex-1 overflow-auto custom-scrollbar px-5 py-4"
        role="tabpanel"
        id={`tabpanel-${activeTab}`}
        aria-labelledby={`tab-${activeTab}`}
      >
        {loading ? (
          <div className="flex items-center justify-center h-40 text-[13px] text-gray-400">
            読み込み中...
          </div>
        ) : activeTab === "accounts" ? (
          <AccountsTab
            tokenStatus={tokenStatus}
            accounts={accounts}
            availableAccounts={availableAccounts}
            loadingAccounts={loadingAccounts}
            connecting={connecting}
            onLoadAvailable={loadAvailableAccounts}
            onConnect={connectAccount}
            onDisconnect={requestDisconnect}
          />
        ) : activeTab === "performance" ? (
          selectedAccountId ? (
            <PerformanceDashboard accountId={selectedAccountId} />
          ) : (
            <div className="text-center py-12 text-[13px] text-gray-400">
              アカウントを接続してください。
            </div>
          )
        ) : activeTab === "campaigns" ? (
          <div className="space-y-4">
            {insights.length > 0 && <MetaInsightsChart insights={insights} />}
            <MetaCampaignTable
              campaigns={campaigns}
              onRefresh={loadCampaigns}
              accountId={selectedAccountId || undefined}
              refreshing={refreshingCampaigns}
              page={campaignPage}
              total={campaignTotal}
              pageSize={PAGE_SIZE}
              onPageChange={setCampaignPage}
            />
          </div>
        ) : activeTab === "adsets" ? (
          <MetaAdSetTable
            adSets={adSets}
            onRefresh={loadAdSets}
            refreshing={refreshingAdSets}
            page={adSetPage}
            total={adSetTotal}
            pageSize={PAGE_SIZE}
            onPageChange={setAdSetPage}
          />
        ) : activeTab === "ads" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {ads.length === 0 ? (
              <div className="col-span-full text-center py-12 text-[13px] text-gray-400">
                広告データがありません。キャンペーンデータを同期してください。
              </div>
            ) : (
              ads.map((ad) => <MetaAdCard key={ad.id} ad={ad} onRefresh={loadAds} />)
            )}
          </div>
        ) : activeTab === "creative-perf" ? (
          selectedAccountId ? (
            <CreativePerformanceView accountId={selectedAccountId} />
          ) : (
            <div className="text-center py-12 text-[13px] text-gray-400">
              アカウントを接続してください。
            </div>
          )
        ) : activeTab === "creative-analysis" ? (
          selectedAccountId ? (
            <CreativeAnalysisPanel accountId={selectedAccountId} />
          ) : (
            <div className="text-center py-12 text-[13px] text-gray-400">
              アカウントを接続してください。
            </div>
          )
        ) : activeTab === "ab-test" ? (
          selectedAccountId ? (
            <ABTestView accountId={selectedAccountId} />
          ) : (
            <div className="text-center py-12 text-[13px] text-gray-400">
              アカウントを接続してください。
            </div>
          )
        ) : activeTab === "optimization" ? (
          selectedAccountId ? (
            <OptimizationDashboard accountId={selectedAccountId} />
          ) : (
            <div className="text-center py-12 text-[13px] text-gray-400">
              アカウントを接続してください。
            </div>
          )
        ) : null}
      </div>

      {disconnectTarget && (
        <ConfirmModal
          title="アカウントの切断"
          message="このアカウントを切断してもよろしいですか？同期データは保持されます。"
          confirmLabel="切断する"
          variant="danger"
          onConfirm={confirmDisconnect}
          onCancel={() => setDisconnectTarget(null)}
        />
      )}
    </div>
  );
}

// ── Accounts Tab ────────────────────────────────────────────────

interface AccountsTabProps {
  tokenStatus: MetaTokenStatus | null;
  accounts: MetaAdAccount[];
  availableAccounts: MetaAvailableAccount[];
  loadingAccounts: boolean;
  connecting: string | null;
  onLoadAvailable: () => void;
  onConnect: (acct: MetaAvailableAccount) => void;
  onDisconnect: (accountId: string) => void;
}

function AccountsTab({
  tokenStatus,
  accounts,
  availableAccounts,
  loadingAccounts,
  connecting,
  onLoadAvailable,
  onConnect,
  onDisconnect,
}: AccountsTabProps) {
  return (
    <div className="space-y-6">
      {/* Token Status */}
      <div className="card p-4">
        <h3 className="text-[13px] font-bold text-gray-800 mb-3">トークン状態</h3>
        {!tokenStatus ? (
          <p className="text-[12px] text-gray-500">トークン情報を取得中...</p>
        ) : !tokenStatus.has_token ? (
          <div className="bg-amber-50 rounded-lg p-3">
            <p className="text-[12px] text-amber-700">
              Metaアクセストークンが設定されていません。設定画面からトークンを登録してください。
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span
                className={`inline-block w-2 h-2 rounded-full ${
                  tokenStatus.is_valid ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span className="text-[12px] text-gray-700">
                {tokenStatus.is_valid ? "有効" : "無効"}
              </span>
              {tokenStatus.days_remaining !== undefined && tokenStatus.days_remaining !== null && (
                <span
                  className={`text-[11px] px-1.5 py-0.5 rounded ${
                    tokenStatus.is_expiring
                      ? "bg-amber-100 text-amber-700"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  残り{tokenStatus.days_remaining}日
                </span>
              )}
            </div>

            {tokenStatus.scopes.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {tokenStatus.scopes.map((scope) => (
                  <span
                    key={scope}
                    className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded"
                  >
                    {scope}
                  </span>
                ))}
              </div>
            )}

            {tokenStatus.missing_scopes.length > 0 && (
              <div className="bg-amber-50 rounded-lg p-2 mt-2">
                <p className="text-[11px] text-amber-700">
                  不足スコープ: {tokenStatus.missing_scopes.join(", ")}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Connected Accounts */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[13px] font-bold text-gray-800">接続済みアカウント</h3>
          <button
            onClick={onLoadAvailable}
            disabled={loadingAccounts || !tokenStatus?.is_valid}
            className="btn-primary text-[11px] px-3 py-1 disabled:opacity-50"
          >
            {loadingAccounts ? "取得中..." : "アカウントを追加"}
          </button>
        </div>

        {accounts.length === 0 ? (
          <p className="text-[12px] text-gray-400 py-4 text-center">
            接続されたアカウントはありません。上のボタンからMeta広告アカウントを接続してください。
          </p>
        ) : (
          <div className="space-y-2">
            {accounts.map((acct) => {
              const statusInfo = ACCOUNT_STATUS_MAP[acct.account_status || 0] || {
                label: `ステータス: ${acct.account_status}`,
                color: "text-gray-600 bg-gray-50",
              };
              return (
                <div
                  key={acct.account_id}
                  className="flex items-center justify-between p-3 border border-gray-100 rounded-lg hover:bg-gray-50"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-[13px] font-medium text-gray-800 truncate">
                        {acct.account_name || acct.account_id}
                      </p>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${statusInfo.color}`}>
                        {statusInfo.label}
                      </span>
                    </div>
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      ID: {acct.account_id}
                      {acct.business_name && ` / ${acct.business_name}`}
                      {" / "}
                      {acct.currency} / {acct.timezone_name}
                    </p>
                    {acct.last_synced_at && (
                      <p className="text-[10px] text-gray-400 mt-0.5">
                        最終同期: {new Date(acct.last_synced_at).toLocaleString("ja-JP")}
                        {acct.sync_status !== "completed" && (
                          <span className="ml-1 text-amber-500">({acct.sync_status})</span>
                        )}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => onDisconnect(acct.account_id)}
                    className="text-[11px] text-red-500 hover:text-red-700 px-2 py-1 shrink-0"
                  >
                    切断
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Available Accounts (from Meta API) */}
      {availableAccounts.length > 0 && (
        <div className="card p-4">
          <h3 className="text-[13px] font-bold text-gray-800 mb-3">
            利用可能なアカウント ({availableAccounts.length})
          </h3>
          <div className="space-y-2">
            {availableAccounts.map((acct) => (
              <div
                key={acct.account_id}
                className="flex items-center justify-between p-3 border border-gray-100 rounded-lg"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] font-medium text-gray-700 truncate">
                    {acct.name || acct.account_id}
                  </p>
                  <p className="text-[11px] text-gray-400">
                    ID: {acct.account_id}
                    {acct.business_name && ` / ${acct.business_name}`}
                    {acct.currency && ` / ${acct.currency}`}
                  </p>
                </div>
                {acct.is_connected ? (
                  <span className="text-[11px] text-green-600 px-2 py-1">接続済み</span>
                ) : (
                  <button
                    onClick={() => onConnect(acct)}
                    disabled={connecting === acct.account_id}
                    className="btn-primary text-[11px] px-3 py-1 disabled:opacity-50"
                  >
                    {connecting === acct.account_id ? "接続中..." : "接続"}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
