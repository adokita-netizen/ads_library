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

type ViewType = "search" | "trend" | "analysis" | "lp-analysis" | "ai-expert" | "creative" | "competitive" | "team" | "mylist" | "store";

/** Connectivity banner — auto-hides after successful check */
function ConnectivityBanner() {
  const [status, setStatus] = useState<"checking" | "ok" | "error">("checking");
  const [detail, setDetail] = useState("");

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch("/api/health");
        const data = await res.json();
        if (data.backend === "ok") {
          setStatus("ok");
        } else {
          setStatus("error");
          setDetail(`Backend: ${data.backend_error || "unreachable"}`);
        }
      } catch (err) {
        setStatus("error");
        setDetail(`Next.js API: ${String(err)}`);
      }
    };
    checkHealth();
  }, []);

  if (status === "ok") return null;
  if (status === "checking") {
    return (
      <div className="bg-blue-50 border-b border-blue-200 px-4 py-1.5 text-xs text-blue-700">
        API接続を確認中...
      </div>
    );
  }
  return (
    <div className="bg-red-50 border-b border-red-200 px-4 py-1.5 text-xs text-red-700">
      API接続エラー: {detail}
      <button
        className="ml-2 underline"
        onClick={() => window.location.reload()}
      >
        再読み込み
      </button>
    </div>
  );
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
