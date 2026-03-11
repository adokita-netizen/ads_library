"use client";

import { useState, useEffect, useRef, useCallback, type ReactNode } from "react";
import dynamic from "next/dynamic";
import Sidebar from "@/components/common/Sidebar";
import NotificationCenter from "@/components/common/NotificationCenter";
import ThemeToggle from "@/components/common/ThemeToggle";
import ProRankingView from "@/components/dashboard/ProRankingView";
import ProductDetailModal from "@/components/analysis/ProductDetailModal";
import OnboardingWizard from "@/components/common/OnboardingWizard";
import SetupProgress from "@/components/common/SetupProgress";
import KeyboardShortcuts from "@/components/common/KeyboardShortcuts";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import { commitUrlSearchParams, URL_STATE_CHANGE_EVENT, useUrlParam } from "@/lib/useUrlParam";
import { prefetchApi } from "@/lib/prefetch";
import {
  SCREEN_LOAD_METRICS_STORAGE_KEY,
  formatScreenLoadMs,
  getSlowestScreen,
  recordScreenLoadMetric,
  type ScreenLoadMetricsMap,
} from "@/lib/screenLoadMetrics";

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
const BrandDetailView = dynamic(() => import("@/components/dashboard/BrandDetailView"), { ssr: false, loading: ViewLoader });
const AppealMapView = dynamic(() => import("@/components/dashboard/AppealMapView"), { ssr: false, loading: ViewLoader });
const CreativeFamilyView = dynamic(() => import("@/components/dashboard/CreativeFamilyView"), { ssr: false, loading: ViewLoader });
const AngleFactDashboard = dynamic(() => import("@/components/dashboard/AngleFactDashboard"), { ssr: false, loading: ViewLoader });
const NotificationListView = dynamic(() => import("@/components/dashboard/NotificationListView"), { ssr: false, loading: ViewLoader });
const HeatmapView = dynamic(() => import("@/components/dashboard/HeatmapView"), { ssr: false, loading: ViewLoader });
const LPDetailView = dynamic(() => import("@/components/lps/LPDetailView"), { ssr: false, loading: ViewLoader });

type ViewType = "pro-database" | "search" | "trend" | "analysis" | "heatmap" | "lp-analysis" | "ai-expert" | "creative" | "competitive" | "hit-ads" | "meta-ads" | "team" | "campaign" | "mylist" | "scenario" | "reports" | "alerts" | "collections" | "settings" | "compare" | "advertiser-profile" | "calendar" | "creative-brief" | "media-management" | "admin" | "ai-chat" | "notifications" | "brand-detail" | "appeal-map" | "creative-families" | "angle-dashboard" | "lp-detail";

const VIEW_LABELS: Record<ViewType, string> = {
  "pro-database": "広告DB",
  "search": "検索",
  "trend": "トレンド",
  "analysis": "分析",
  "heatmap": "ヒートマップ",
  "lp-analysis": "LP分析",
  "ai-expert": "AIエキスパート",
  "creative": "クリエイティブ",
  "competitive": "競合分析",
  "hit-ads": "ヒット広告",
  "meta-ads": "Meta広告",
  "team": "チーム",
  "campaign": "キャンペーン",
  "mylist": "マイリスト",
  "scenario": "シナリオ",
  "reports": "レポート",
  "alerts": "アラート",
  "collections": "コレクション",
  "settings": "設定",
  "compare": "比較",
  "advertiser-profile": "広告主",
  "calendar": "カレンダー",
  "creative-brief": "ブリーフ",
  "media-management": "メディア管理",
  "admin": "管理",
  "ai-chat": "AIチャット",
  "notifications": "通知",
  "brand-detail": "ブランド詳細",
  "appeal-map": "訴求マップ",
  "creative-families": "クリエイティブ系統",
  "angle-dashboard": "訴求分析",
  "lp-detail": "LP詳細",
};

function ScreenReadyProbe({
  screen,
  onReady,
  children,
}: {
  screen: ViewType;
  onReady: (screen: ViewType) => void;
  children: ReactNode;
}) {
  useEffect(() => {
    onReady(screen);
  }, [onReady, screen]);

  return <>{children}</>;
}

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
  const [evidenceMode] = useUrlParam("evidence", "");
  const lastNonSettingsViewRef = useRef<ViewType>("pro-database");
  const [urlSyncReady, setUrlSyncReady] = useState(false);
  const [selectedAdId, setSelectedAdId] = useState<number | null>(null);
  const [showProductDetail, setShowProductDetail] = useState(false);
  const [selectedAdvertiser, setSelectedAdvertiser] = useState<string>("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [screenLoadMetrics, setScreenLoadMetrics] = useState<ScreenLoadMetricsMap>({});
  const pendingScreenLoadRef = useRef<{ screen: ViewType; startedAt: number }>({
    screen: currentView,
    startedAt: typeof performance !== "undefined" ? performance.now() : Date.now(),
  });

  useEffect(() => {
    try {
      const raw = localStorage.getItem(SCREEN_LOAD_METRICS_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        setScreenLoadMetrics(parsed as ScreenLoadMetricsMap);
      }
    } catch {
      // ignore storage parse failures
    }
  }, []);

  // Prefetch critical data for the default view on mount
  useEffect(() => {
    prefetchApi("/rankings/genre-master");
    prefetchApi("/rankings/search-collections");
    prefetchApi("/rankings/pro-ranking", { page: 1, page_size: 20, period: "7d", sort_by: "cumulative_views" });

    // Register ServiceWorker only in production.
    // In local dev, SW cache can stale API/UI behavior and produce noisy console errors.
    if ("serviceWorker" in navigator) {
      if (process.env.NODE_ENV === "production") {
        navigator.serviceWorker.register("/sw.js").catch(() => {});
      } else {
        navigator.serviceWorker.getRegistrations().then((regs) => {
          regs.forEach((r) => r.unregister());
        }).catch(() => {});
      }
    }
  }, []);

  // Backward compatibility: old shared URLs may still contain ?view=store.
  useEffect(() => {
    if ((currentView as string) === "store") {
      setCurrentView("pro-database");
    }
  }, [currentView, setCurrentView]);

  useEffect(() => {
    try {
      if (evidenceMode === "results") {
        setShowOnboarding(false);
        return;
      }
      const onboardingKeys = [
        localStorage.getItem("vaap-onboarded"),
        localStorage.getItem("vaap_onboarding_completed"),
        localStorage.getItem("onboarding_completed"),
      ];
      if ((currentView as string) !== "lp-analysis" && !onboardingKeys.includes("true")) {
        setShowOnboarding(true);
      }
    } catch {
      // ignore
    }
  }, [currentView]);

  useEffect(() => {
    pendingScreenLoadRef.current = {
      screen: currentView,
      startedAt: typeof performance !== "undefined" ? performance.now() : Date.now(),
    };
  }, [currentView]);

  useEffect(() => {
    if (currentView !== "settings") {
      lastNonSettingsViewRef.current = currentView;
    }
  }, [currentView]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setUrlSyncReady(true);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !urlSyncReady) return;
    const syncCurrentViewToUrl = () => {
      const params = new URLSearchParams(window.location.search);
      const urlView = params.get("view") || "pro-database";
      if (urlView === currentView) return;
      if (currentView === "pro-database") params.delete("view");
      else params.set("view", currentView);
      commitUrlSearchParams(params, "replace");
    };

    syncCurrentViewToUrl();
    window.addEventListener("popstate", syncCurrentViewToUrl);
    window.addEventListener(URL_STATE_CHANGE_EVENT, syncCurrentViewToUrl);
    return () => {
      window.removeEventListener("popstate", syncCurrentViewToUrl);
      window.removeEventListener(URL_STATE_CHANGE_EVENT, syncCurrentViewToUrl);
    };
  }, [currentView, urlSyncReady]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (currentView !== "settings") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("view") === "settings") return;
    params.set("view", "settings");
    commitUrlSearchParams(params, "replace");
  }, [currentView, evidenceMode]);

  const handleScreenReady = useCallback((screen: ViewType) => {
    const pending = pendingScreenLoadRef.current;
    if (!pending || pending.screen !== screen) return;
    const now = typeof performance !== "undefined" ? performance.now() : Date.now();
    const elapsedMs = Math.max(1, now - pending.startedAt);
    setScreenLoadMetrics((prev) => {
      const next = recordScreenLoadMetric(prev, screen, elapsedMs);
      try {
        localStorage.setItem(SCREEN_LOAD_METRICS_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore storage quota failures
      }
      return next;
    });
  }, []);

  const handleAdSelect = (adId: number) => {
    setSelectedAdId(adId);
    setShowProductDetail(true);
  };

  const handleViewChange = useCallback((view: ViewType) => {
    setCurrentView(view);
  }, [setCurrentView]);

  const handleBackFromSettings = useCallback(() => {
    handleViewChange(lastNonSettingsViewRef.current || "pro-database");
  }, [handleViewChange]);

  const handleViewAdvertiser = (name: string) => {
    setSelectedAdvertiser(name);
    handleViewChange("advertiser-profile");
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
      case "heatmap":
        return <HeatmapView />;
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
          <div className="flex flex-wrap items-center gap-2 px-5 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
              <button
                type="button"
                onClick={handleBackFromSettings}
                className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-[11px] font-medium text-gray-600 dark:text-gray-300 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                </svg>
                {VIEW_LABELS[lastNonSettingsViewRef.current] || "広告DB"}へ戻る
              </button>
              <h2 className="text-[15px] font-bold text-gray-900 dark:text-gray-100">システム設定</h2>
              <p className="text-[11px] text-gray-400 dark:text-gray-500 md:ml-1">データベース接続とシステム全体の設定を管理します</p>
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
            <div className="flex items-center px-5 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
              <h2 className="text-[15px] font-bold text-gray-900 dark:text-gray-100">レポート</h2>
              <p className="text-[11px] text-gray-400 dark:text-gray-500 ml-3">広告パフォーマンスの分析レポートとエクスポート</p>
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
      case "brand-detail":
        return <BrandDetailView onAdSelect={handleAdSelect} onBack={() => handleViewChange("pro-database")} />;
      case "appeal-map":
        return <AppealMapView />;
      case "creative-families":
        return <CreativeFamilyView onAdSelect={handleAdSelect} />;
      case "angle-dashboard":
        return <AngleFactDashboard onAdSelect={handleAdSelect} />;
      case "lp-detail":
        return <LPDetailView onBack={() => handleViewChange("lp-analysis")} />;
      case "advertiser-profile":
        return (
            <AdvertiserProfile
            advertiserName={selectedAdvertiser || "不明"}
            onAdSelect={handleAdSelect}
            onBack={() => handleViewChange("pro-database")}
          />
        );
      default:
        return <ProRankingView onAdSelect={handleAdSelect} />;
    }
  };

  const currentScreenMetric = screenLoadMetrics[currentView];
  const slowestScreen = getSlowestScreen(screenLoadMetrics);
  const shouldShowOnboarding = showOnboarding && currentView === "pro-database";

  return (
    <div className="flex h-screen min-h-0 overflow-hidden flex-col bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <ConnectivityBanner />
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <Sidebar currentView={currentView} onViewChange={(v) => handleViewChange(v as ViewType)} mobileOpen={mobileMenuOpen} onMobileClose={() => setMobileMenuOpen(false)} />
        <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {/* Desktop header bar */}
          <div className="hidden md:flex items-center justify-between px-4 py-2.5 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-md bg-[#4A7DFF] flex items-center justify-center">
                <span className="text-white text-[10px] font-black">V</span>
              </div>
              <span className="text-[13px] font-bold text-gray-900 dark:text-gray-100">VAAP</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden lg:flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-[11px] text-slate-700 dark:border-sky-900/70 dark:bg-sky-950/40 dark:text-slate-200">
                <span className="font-semibold text-sky-700 dark:text-sky-300">画面読込</span>
                <span>{VIEW_LABELS[currentView]}</span>
                <span className="font-semibold">{formatScreenLoadMs(currentScreenMetric?.latestMs || 0)}</span>
                {currentScreenMetric && <span className="text-slate-500 dark:text-slate-400">平均 {formatScreenLoadMs(currentScreenMetric.avgMs)}</span>}
                {slowestScreen && slowestScreen[0] !== currentView && (
                  <span className="text-slate-500 dark:text-slate-400">
                    最遅 {VIEW_LABELS[slowestScreen[0] as ViewType]} {formatScreenLoadMs(slowestScreen[1].latestMs)}
                  </span>
                )}
              </div>
              <ThemeToggle />
              <NotificationCenter
                onViewAll={() => handleViewChange("notifications")}
                onAdSelect={handleAdSelect}
              />
            </div>
          </div>

          {/* Mobile header bar */}
          <div className="flex md:hidden items-center justify-between gap-2 px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shrink-0">
            <div className="flex items-center gap-2">
              <button onClick={() => setMobileMenuOpen(true)} aria-label="メニューを開く" aria-expanded={mobileMenuOpen} className="p-1.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                </svg>
              </button>
              <div className="w-6 h-6 rounded-md bg-[#4A7DFF] flex items-center justify-center">
                <span className="text-white text-[9px] font-black">V</span>
              </div>
              <span className="text-[13px] font-bold text-gray-900 dark:text-gray-100">VAAP</span>
            </div>
            <NotificationCenter
              onViewAll={() => handleViewChange("notifications")}
              onAdSelect={handleAdSelect}
            />
            <ThemeToggle compact />
          </div>
          <div className="flex-1 min-h-0 overflow-auto">
            <ErrorBoundary key={currentView} label={`画面: ${currentView}`}>
              {currentView !== "settings" && !shouldShowOnboarding && (
                <SetupProgress onNavigate={(view) => handleViewChange(view)} />
              )}
              <ScreenReadyProbe screen={currentView} onReady={handleScreenReady}>
                {renderView()}
              </ScreenReadyProbe>
            </ErrorBoundary>
          </div>
        </main>
      </div>

      {/* Product Detail Modal */}
      {showProductDetail && selectedAdId && (
        <ProductDetailModal
          adId={selectedAdId}
          onClose={() => setShowProductDetail(false)}
        />
      )}

      <OnboardingWizard open={shouldShowOnboarding} onComplete={() => setShowOnboarding(false)} />

      {/* Global Keyboard Shortcuts */}
      <KeyboardShortcuts />
    </div>
  );
}




