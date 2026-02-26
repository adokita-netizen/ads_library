"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/common/Sidebar";
import AdLibraryTable from "@/components/dashboard/AdLibraryTable";
import TrendView from "@/components/dashboard/TrendView";
import ProductDetailModal from "@/components/analysis/ProductDetailModal";
import CreativeStudio from "@/components/creative/CreativeStudio";
import LPAnalysisView from "@/components/lp/LPAnalysisView";
import AIExpertView from "@/components/ai/AIExpertView";
import TeamSpaceView from "@/components/workspace/TeamSpaceView";
import MyListView from "@/components/workspace/MyListView";
import StoreView from "@/components/workspace/StoreView";
import CompetitiveIntelView from "@/components/competitive/CompetitiveIntelView";
import APIKeysSettings from "@/components/settings/APIKeysSettings";
import DatabaseSettings from "@/components/settings/DatabaseSettings";

type ViewType = "search" | "trend" | "analysis" | "lp-analysis" | "ai-expert" | "creative" | "competitive" | "team" | "mylist" | "store" | "settings";

/** Connectivity banner — wakes up Render backend, auto-hides on success */
function ConnectivityBanner() {
  const [status, setStatus] = useState<"waking" | "ok" | "error">("waking");
  const [detail, setDetail] = useState("");
  const [dataTest, setDataTest] = useState<"pending" | "ok" | "error">("pending");
  const [dataDetail, setDataDetail] = useState("");
  const [dismissed, setDismissed] = useState(false);
  const [dots, setDots] = useState("");

  // Animated dots for waking state
  useEffect(() => {
    if (status !== "waking") return;
    const interval = setInterval(() => setDots((d) => (d.length >= 3 ? "" : d + ".")), 500);
    return () => clearInterval(interval);
  }, [status]);

  const runCheck = async () => {
    setStatus("waking");
    setDataTest("pending");
    setDismissed(false);

    // Step 1: Health check (handles Render cold start retry server-side)
    try {
      const res = await fetch("/api/health");
      const data = await res.json();
      if (data.backend === "ok") {
        setStatus("ok");
      } else {
        setStatus("error");
        setDetail(data.backend_error || "バックエンドに接続できません");
        return;
      }
    } catch (err) {
      setStatus("error");
      setDetail(`API接続エラー: ${String(err)}`);
      return;
    }

    // Step 2: Data connectivity check (backend is now warm)
    try {
      const res = await fetch("/api/v1/rankings/products?period=weekly&page_size=1");
      if (!res.ok) {
        setDataTest("error");
        setDataDetail(`HTTP ${res.status}`);
        return;
      }
      // No data is OK — just means DB is empty, not an error
      setDataTest("ok");
    } catch (err) {
      setDataTest("error");
      setDataDetail(`データ取得: ${String(err)}`);
    }
  };

  useEffect(() => {
    runCheck();
  }, []);

  if (dismissed) return null;
  if (status === "ok" && dataTest === "ok") return null;

  if (status === "waking") {
    return (
      <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 text-xs text-blue-700 flex items-center gap-2">
        <div className="h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        <span>バックエンドサーバーを起動中です{dots}（無料プランのため初回アクセス時に30-60秒かかります）</span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-xs text-amber-700 flex items-center justify-between">
        <span>
          バックエンドサーバーに接続できません: {detail}
        </span>
        <span className="flex items-center gap-2 ml-3 shrink-0">
          <button className="underline font-medium" onClick={runCheck}>
            再接続
          </button>
          <button className="underline" onClick={() => setDismissed(true)}>
            閉じる
          </button>
        </span>
      </div>
    );
  }

  if (dataTest === "error") {
    return (
      <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 text-xs text-amber-700 flex items-center justify-between">
        <span>API接続OK / データ取得エラー: {dataDetail}</span>
        <span className="flex items-center gap-2 ml-3 shrink-0">
          <button className="underline font-medium" onClick={runCheck}>再接続</button>
          <button className="underline" onClick={() => setDismissed(true)}>閉じる</button>
        </span>
      </div>
    );
  }

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
  const [currentView, setCurrentView] = useState<ViewType>("search");
  const [selectedAdId, setSelectedAdId] = useState<number | null>(null);
  const [showProductDetail, setShowProductDetail] = useState(false);

  const handleAdSelect = (adId: number) => {
    setSelectedAdId(adId);
    setShowProductDetail(true);
  };

  const renderView = () => {
    switch (currentView) {
      case "search":
        return <AdLibraryTable onAdSelect={handleAdSelect} />;
      case "trend":
        return <TrendView />;
      case "analysis":
        return <AdLibraryTable onAdSelect={handleAdSelect} />;
      case "lp-analysis":
        return <LPAnalysisView />;
      case "ai-expert":
        return <AIExpertView />;
      case "creative":
        return <CreativeStudio />;
      case "competitive":
        return <CompetitiveIntelView />;
      case "team":
        return <TeamSpaceView />;
      case "mylist":
        return <MyListView />;
      case "store":
        return <StoreView />;
      case "settings":
        return (
          <div className="flex flex-col h-full">
            <div className="flex items-center px-5 py-3 border-b border-gray-200 bg-white">
              <h2 className="text-[15px] font-bold text-gray-900">システム設定</h2>
              <p className="text-[11px] text-gray-400 ml-3">データベース接続とシステム全体の設定を管理します</p>
            </div>
            <div className="flex-1 overflow-auto custom-scrollbar px-5 py-4 space-y-6">
              <DatabaseSettings />
              <APIKeysSettings />
            </div>
          </div>
        );
      default:
        return <AdLibraryTable onAdSelect={handleAdSelect} />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden flex-col">
      <ConnectivityBanner />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar currentView={currentView} onViewChange={(v) => setCurrentView(v as ViewType)} />
        <main className="flex-1 overflow-hidden flex flex-col">
          {renderView()}
        </main>
      </div>

      {/* Product Detail Modal */}
      {showProductDetail && selectedAdId && (
        <ProductDetailModal
          adId={selectedAdId}
          onClose={() => setShowProductDetail(false)}
        />
      )}
    </div>
  );
}
