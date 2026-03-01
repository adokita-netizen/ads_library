"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import Sidebar from "@/components/common/Sidebar";
import ProRankingView from "@/components/dashboard/ProRankingView";
import ProductDetailModal from "@/components/analysis/ProductDetailModal";
import OnboardingTour from "@/components/common/OnboardingTour";
import KeyboardShortcuts from "@/components/common/KeyboardShortcuts";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import { useUrlParam } from "@/lib/useUrlParam";
import { prefetchApi } from "@/lib/prefetch";

// Loading placeholder for lazy-loaded views
const ViewLoader = () => (
  <div className="flex-1 flex items-center justify-center">
    <div className="animate-pulse flex flex-col items-center gap-3">
      <div className="w-8 h-8 rounded-lg bg-gray-200" />
      <div className="h-2 w-24 rounded bg-gray-200" />
    </div>
  </div>
);

// Lazy-load non-default views to reduce initial bundle size
const AdLibraryTable = dynamic(() => import("@/components/dashboard/AdLibraryTable"), { ssr: false, loading: ViewLoader });
const TrendView = dynamic(() => import("@/components/dashboard/TrendView"), { ssr: false, loading: ViewLoader });
const CreativeStudio = dynamic(() => import("@/components/creative/CreativeStudio"), { ssr: false, loading: ViewLoader });
const LPAnalysisView = dynamic(() => import("@/components/lp/LPAnalysisView"), { ssr: false, loading: ViewLoader });
const AIExpertView = dynamic(() => import("@/components/ai/AIExpertView"), { ssr: false, loading: ViewLoader });
const TeamSpaceView = dynamic(() => import("@/components/workspace/TeamSpaceView"), { ssr: false, loading: ViewLoader });
const MyListView = dynamic(() => import("@/components/workspace/MyListView"), { ssr: false, loading: ViewLoader });
const StoreView = dynamic(() => import("@/components/workspace/StoreView"), { ssr: false, loading: ViewLoader });
const CompetitiveIntelView = dynamic(() => import("@/components/competitive/CompetitiveIntelView"), { ssr: false, loading: ViewLoader });
const CampaignGalleryView = dynamic(() => import("@/components/workspace/CampaignGalleryView"), { ssr: false, loading: ViewLoader });
const MetaAdsView = dynamic(() => import("@/components/meta-ads/MetaAdsView"), { ssr: false, loading: ViewLoader });
const HitAdAnalysisView = dynamic(() => import("@/components/dashboard/HitAdAnalysisView"), { ssr: false, loading: ViewLoader });
const ReportsView = dynamic(() => import("@/components/dashboard/ReportsView"), { ssr: false, loading: ViewLoader });
const AlertsPanel = dynamic(() => import("@/components/dashboard/AlertsPanel"), { ssr: false, loading: ViewLoader });
const CollectionsView = dynamic(() => import("@/components/dashboard/CollectionsView"), { ssr: false, loading: ViewLoader });
const ScenarioBuilder = dynamic(() => import("@/components/dashboard/ScenarioBuilder"), { ssr: false, loading: ViewLoader });
const AdComparisonTool = dynamic(() => import("@/components/dashboard/AdComparisonTool"), { ssr: false, loading: ViewLoader });
const AdvertiserProfile = dynamic(() => import("@/components/dashboard/AdvertiserProfile"), { ssr: false, loading: ViewLoader });
const APIKeysSettings = dynamic(() => import("@/components/settings/APIKeysSettings"), { ssr: false, loading: ViewLoader });
const DatabaseSettings = dynamic(() => import("@/components/settings/DatabaseSettings"), { ssr: false, loading: ViewLoader });
const UserPreferences = dynamic(() => import("@/components/settings/UserPreferences"), { ssr: false, loading: ViewLoader });
const CalendarView = dynamic(() => import("@/components/dashboard/CalendarView"), { ssr: false, loading: ViewLoader });
const CreativeBriefGenerator = dynamic(() => import("@/components/dashboard/CreativeBriefGenerator"), { ssr: false, loading: ViewLoader });
const AnalyticsDashboard = dynamic(() => import("@/components/dashboard/AnalyticsDashboard"), { ssr: false, loading: ViewLoader });
const MediaExtractionDashboard = dynamic(() => import("@/components/dashboard/MediaExtractionDashboard"), { ssr: false, loading: ViewLoader });
const BatchOperationsPanel = dynamic(() => import("@/components/dashboard/BatchOperationsPanel"), { ssr: false, loading: ViewLoader });
const AIChatView = dynamic(() => import("@/components/ai/AIChatView"), { ssr: false, loading: ViewLoader });
const NotificationListView = dynamic(() => import("@/components/dashboard/NotificationListView"), { ssr: false, loading: ViewLoader });

type ViewType = "pro-database" | "search" | "trend" | "analysis" | "lp-analysis" | "ai-expert" | "creative" | "competitive" | "hit-ads" | "meta-ads" | "team" | "campaign" | "mylist" | "store" | "scenario" | "reports" | "alerts" | "collections" | "settings" | "compare" | "advertiser-profile" | "calendar" | "creative-brief" | "media-management" | "admin" | "ai-chat" | "notifications";

/** Connectivity banner — auto-hides after successful check, dismissible on error */
function ConnectivityBanner() {
  const [status, setStatus] = useState<"checking" | "ok" | "error">("checking");
  const [detail, setDetail] = useState("");
  const [dataTest, setDataTest] = useState<"pending" | "ok" | "error">("pending");
  const [dataDetail, setDataDetail] = useState("");
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      // Step 1: Check health endpoint
      try {
        const res = await fetch("/api/health");
        const data = await res.json();
        if (data.status === "healthy" || data.database === "ok") {
          setStatus("ok");
        } else if (data.in_memory_mode) {
          // Backend is running but in memory mode — still usable
          setStatus("ok");
        } else if (data.backend === "ok") {
          setStatus("ok");
        } else {
          setStatus("error");
          setDetail(`バックエンド: ${data.backend_error || data.database_error || "未接続"}`);
          return;
        }
      } catch (err) {
        setStatus("error");
        setDetail(`Next.js API: ${String(err)}`);
        return;
      }

      // Step 2: Check data endpoint (this is what the table actually uses)
      try {
        const res = await fetch("/api/v1/rankings/products?period=weekly&page_size=1");
        const text = await res.text();
        if (!res.ok) {
          setDataTest("error");
          setDataDetail(`HTTP ${res.status}: ${text.substring(0, 200)}`);
          return;
        }
        const data = JSON.parse(text);
        const count = data?.items?.length ?? data?.total ?? 0;
        if (count > 0) {
          setDataTest("ok");
        } else {
          setDataTest("error");
          setDataDetail("API応答はOKですが、データが0件です");
        }
      } catch (err) {
        setDataTest("error");
        setDataDetail(`データ取得: ${String(err)}`);
      }
    };
    checkHealth();
  }, []);

  // Dismissed by user or everything works — hide banner
  if (dismissed) return null;
  if (status === "ok" && dataTest === "ok") return null;

  if (status === "checking") {
    return (
      <div className="bg-blue-50 border-b border-blue-200 px-4 py-1.5 text-xs text-blue-700">
        API接続を確認中...
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-xs text-amber-700 flex items-center justify-between">
        <span>
          バックエンドサーバーに接続できません。オフラインモードで動作中です（APIキーはローカルに保存されます）。
        </span>
        <span className="flex items-center gap-2 ml-3 shrink-0">
          <button className="underline font-medium" onClick={() => { setStatus("checking"); setDismissed(false); window.location.reload(); }}>
            再接続
          </button>
          <button className="underline" onClick={() => setDismissed(true)}>
            閉じる
          </button>
        </span>
      </div>
    );
  }

  // Health OK but data failed
  if (dataTest === "error") {
    return (
      <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-xs text-amber-700 flex items-center justify-between">
        <span>API接続OK / データ取得エラー: {dataDetail}</span>
        <span className="flex items-center gap-2 ml-3 shrink-0">
          <button className="underline font-medium" onClick={() => window.location.reload()}>再読み込み</button>
          <button className="underline" onClick={() => setDismissed(true)}>閉じる</button>
        </span>
      </div>
    );
  }

  // Data test still pending
  if (dataTest === "pending") {
    return (
      <div className="bg-blue-50 border-b border-blue-200 px-4 py-1.5 text-xs text-blue-700">
        データ接続を確認中...
      </div>
    );
  }

  return null;
}

export default function Home() {
  const [currentView, setCurrentView] = useUrlParam("view", "pro-database") as [ViewType, (v: string) => void];
  const [selectedAdId, setSelectedAdId] = useState<number | null>(null);
  const [showProductDetail, setShowProductDetail] = useState(false);
  const [selectedAdvertiser, setSelectedAdvertiser] = useState<string>("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Prefetch critical data for the default view on mount
  useEffect(() => {
    prefetchApi("/rankings/genre-master");
    prefetchApi("/rankings/search-collections");
    prefetchApi("/rankings/pro-ranking", { page: 1, page_size: 50, period: "7d", sort_by: "cumulative_views" });

    // Register ServiceWorker for offline caching
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  const handleAdSelect = (adId: number) => {
    setSelectedAdId(adId);
    setShowProductDetail(true);
  };

  const handleViewAdvertiser = (name: string) => {
    setSelectedAdvertiser(name);
    setCurrentView("advertiser-profile");
  };

  const renderView = () => {
    switch (currentView) {
      case "pro-database":
        return <ProRankingView onAdSelect={handleAdSelect} />;
      case "search":
        return <AdLibraryTable onAdSelect={handleAdSelect} />;
      case "trend":
        return <TrendView />;
      case "analysis":
        return <AnalyticsDashboard />;
      case "lp-analysis":
        return <LPAnalysisView />;
      case "ai-expert":
        return <AIExpertView />;
      case "creative":
        return <CreativeStudio />;
      case "competitive":
        return <CompetitiveIntelView />;
      case "hit-ads":
        return <HitAdAnalysisView onAdSelect={handleAdSelect} />;
      case "meta-ads":
        return <MetaAdsView />;
      case "team":
        return <TeamSpaceView />;
      case "campaign":
        return <CampaignGalleryView onAdSelect={handleAdSelect} />;
      case "mylist":
        return <MyListView />;
      case "store":
        return <StoreView />;
      case "calendar":
        return <CalendarView />;
      case "creative-brief":
        return <CreativeBriefGenerator />;
      case "media-management":
        return <MediaExtractionDashboard />;
      case "admin":
        return <BatchOperationsPanel />;
      case "ai-chat":
        return <AIChatView onAdSelect={handleAdSelect} />;
      case "notifications":
        return <NotificationListView onAdSelect={handleAdSelect} />;
      case "settings":
        return (
          <div className="flex flex-col h-full">
            <div className="flex items-center px-5 py-3 border-b border-gray-200 bg-white">
              <h2 className="text-[15px] font-bold text-gray-900">システム設定</h2>
              <p className="text-[11px] text-gray-400 ml-3">データベース接続とシステム全体の設定を管理します</p>
            </div>
            <div className="flex-1 overflow-auto custom-scrollbar px-5 py-4 space-y-6">
              <UserPreferences />
              <DatabaseSettings />
              <APIKeysSettings />
            </div>
          </div>
        );
      case "scenario":
        return <ScenarioBuilder />;
      case "reports":
        return (
          <div className="flex flex-col h-full">
            <div className="flex items-center px-5 py-3 border-b border-gray-200 bg-white">
              <h2 className="text-[15px] font-bold text-gray-900">レポート</h2>
              <p className="text-[11px] text-gray-400 ml-3">広告パフォーマンスの分析レポートとエクスポート</p>
            </div>
            <div className="flex-1 overflow-auto custom-scrollbar px-5 py-4">
              <ReportsView onAdSelect={handleAdSelect} />
            </div>
          </div>
        );
      case "alerts":
        return <AlertsPanel fullPage onAdSelect={handleAdSelect} />;
      case "collections":
        return <CollectionsView fullPage onAdSelect={handleAdSelect} />;
      case "compare":
        return <AdComparisonTool onAdSelect={handleAdSelect} />;
      case "advertiser-profile":
        return (
            <AdvertiserProfile
            advertiserName={selectedAdvertiser || "不明"}
            onAdSelect={handleAdSelect}
            onBack={() => setCurrentView("pro-database")}
          />
        );
      default:
        return <ProRankingView onAdSelect={handleAdSelect} />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden flex-col">
      <ConnectivityBanner />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar currentView={currentView} onViewChange={(v) => setCurrentView(v as ViewType)} mobileOpen={mobileMenuOpen} onMobileClose={() => setMobileMenuOpen(false)} />
        <main className="flex-1 overflow-hidden flex flex-col">
          {/* Mobile header bar */}
          <div className="flex md:hidden items-center gap-2 px-3 py-2 border-b border-gray-200 bg-white shrink-0">
            <button onClick={() => setMobileMenuOpen(true)} aria-label="メニューを開く" aria-expanded={mobileMenuOpen} className="p-1.5 text-gray-600 hover:text-gray-900">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              </svg>
            </button>
            <div className="w-6 h-6 rounded-md bg-[#4A7DFF] flex items-center justify-center">
              <span className="text-white text-[9px] font-black">V</span>
            </div>
            <span className="text-[13px] font-bold text-gray-900">VAAP</span>
          </div>
          <ErrorBoundary key={currentView} label={`画面: ${currentView}`}>
            {renderView()}
          </ErrorBoundary>
        </main>
      </div>

      {/* Product Detail Modal */}
      {showProductDetail && selectedAdId && (
        <ProductDetailModal
          adId={selectedAdId}
          onClose={() => setShowProductDetail(false)}
        />
      )}

      {/* Onboarding Tour - shows on first visit */}
      <OnboardingTour />

      {/* Global Keyboard Shortcuts */}
      <KeyboardShortcuts />
    </div>
  );
}
