"use client";

import { useState } from "react";
import Sidebar from "@/components/common/Sidebar";
import AdLibraryTable from "@/components/dashboard/AdLibraryTable";
import TrendView from "@/components/dashboard/TrendView";
import ProductDetailModal from "@/components/analysis/ProductDetailModal";
import CreativeStudio from "@/components/creative/CreativeStudio";
import LPAnalysisView from "@/components/lp/LPAnalysisView";

type ViewType = "search" | "trend" | "analysis" | "lp-analysis" | "ai-expert" | "creative" | "team" | "mylist" | "store";

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
      case "creative":
        return <CreativeStudio />;
      default:
        return <AdLibraryTable onAdSelect={handleAdSelect} />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar currentView={currentView} onViewChange={(v) => setCurrentView(v as ViewType)} />
      <main className="flex-1 overflow-hidden flex flex-col">
        {renderView()}
      </main>

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
