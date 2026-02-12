"use client";

import { useState } from "react";
import Sidebar from "@/components/common/Sidebar";
import DashboardView from "@/components/dashboard/DashboardView";
import AdLibrary from "@/components/dashboard/AdLibrary";
import AnalysisView from "@/components/analysis/AnalysisView";
import CreativeStudio from "@/components/creative/CreativeStudio";
import CompetitorView from "@/components/dashboard/CompetitorView";

type ViewType = "dashboard" | "library" | "analysis" | "creative" | "competitor";

export default function Home() {
  const [currentView, setCurrentView] = useState<ViewType>("dashboard");
  const [selectedAdId, setSelectedAdId] = useState<number | null>(null);

  const handleAdSelect = (adId: number) => {
    setSelectedAdId(adId);
    setCurrentView("analysis");
  };

  const renderView = () => {
    switch (currentView) {
      case "dashboard":
        return <DashboardView />;
      case "library":
        return <AdLibrary onAdSelect={handleAdSelect} />;
      case "analysis":
        return <AnalysisView adId={selectedAdId} />;
      case "creative":
        return <CreativeStudio />;
      case "competitor":
        return <CompetitorView />;
      default:
        return <DashboardView />;
    }
  };

  return (
    <div className="flex h-screen">
      <Sidebar currentView={currentView} onViewChange={setCurrentView} />
      <main className="flex-1 overflow-auto bg-gray-50 p-6">
        {renderView()}
      </main>
    </div>
  );
}
