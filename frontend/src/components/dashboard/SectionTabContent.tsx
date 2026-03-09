"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import ErrorBoundary from "@/components/common/ErrorBoundary";

// Loading placeholder for lazy-loaded tab content
const TabLoader = () => (
  <div className="flex items-center justify-center py-16">
    <div className="flex items-center gap-2">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
      <span className="text-[11px] text-gray-400">読み込み中...</span>
    </div>
  </div>
);

// Lazy-load all tab components — only loaded when the user clicks that tab
const TrendCharts = dynamic(() => import("./TrendCharts"), { ssr: false, loading: TabLoader });
const MarketOverview = dynamic(() => import("./MarketOverview"), { ssr: false, loading: TabLoader });
const AdvertiserLeaderboard = dynamic(() => import("./AdvertiserLeaderboard"), { ssr: false, loading: TabLoader });
const WinningFormulas = dynamic(() => import("./WinningFormulas"), { ssr: false, loading: TabLoader });
const AdComparisonView = dynamic(() => import("./AdComparisonView"), { ssr: false, loading: TabLoader });
const CollectionsView = dynamic(() => import("./CollectionsView"), { ssr: false, loading: TabLoader });
const CreativePlanner = dynamic(() => import("./CreativePlanner"), { ssr: false, loading: TabLoader });
const Recommendations = dynamic(() => import("./Recommendations"), { ssr: false, loading: TabLoader });
const ScenarioBuilder = dynamic(() => import("./ScenarioBuilder"), { ssr: false, loading: TabLoader });
const SavedScenarios = dynamic(() => import("./SavedScenarios"), { ssr: false, loading: TabLoader });
const SuccessFailureAnalysis = dynamic(() => import("./SuccessFailureAnalysis"), { ssr: false, loading: TabLoader });
const ElementAnalysis = dynamic(() => import("./ElementAnalysis"), { ssr: false, loading: TabLoader });
const LPAnalysisPanel = dynamic(() => import("./LPAnalysisPanel"), { ssr: false, loading: TabLoader });
const FunnelView = dynamic(() => import("./FunnelView"), { ssr: false, loading: TabLoader });
const LPComparison = dynamic(() => import("./LPComparison"), { ssr: false, loading: TabLoader });
const CompetitorDashboard = dynamic(() => import("./CompetitorDashboard"), { ssr: false, loading: TabLoader });
const CompetitorProfile = dynamic(() => import("./CompetitorProfile"), { ssr: false, loading: TabLoader });
const MarketGaps = dynamic(() => import("./MarketGaps"), { ssr: false, loading: TabLoader });
const ReportGenerator = dynamic(() => import("./ReportGenerator"), { ssr: false, loading: TabLoader });
const ReportsView = dynamic(() => import("./ReportsView"), { ssr: false, loading: TabLoader });
const ReportViewer = dynamic(() => import("./ReportViewer"), { ssr: false, loading: TabLoader });
const AdComparisonTool = dynamic(() => import("./AdComparisonTool"), { ssr: false, loading: TabLoader });
const AdvertiserProfile = dynamic(() => import("./AdvertiserProfile"), { ssr: false, loading: TabLoader });
const CalendarView = dynamic(() => import("./CalendarView"), { ssr: false, loading: TabLoader });
const AdTimeline = dynamic(() => import("./AdTimeline"), { ssr: false, loading: TabLoader });
const TeamActivity = dynamic(() => import("./TeamActivity"), { ssr: false, loading: TabLoader });
const CreativeBriefGenerator = dynamic(() => import("./CreativeBriefGenerator"), { ssr: false, loading: TabLoader });
const TemplateLibrary = dynamic(() => import("./TemplateLibrary"), { ssr: false, loading: TabLoader });
const CopyVariations = dynamic(() => import("./CopyVariations"), { ssr: false, loading: TabLoader });
const AnalyticsDashboard = dynamic(() => import("./AnalyticsDashboard"), { ssr: false, loading: TabLoader });
const GenreDistributionChart = dynamic(() => import("./GenreDistributionChart"), { ssr: false, loading: TabLoader });
const GenreComparisonView = dynamic(() => import("./GenreComparisonView"), { ssr: false, loading: TabLoader });
const GenreTrendChart = dynamic(() => import("./GenreTrendChart"), { ssr: false, loading: TabLoader });

type MainTab = "overview" | "trends" | "market" | "advertisers" | "formulas" | "compare" | "collections" | "ai" | "scenario" | "deep-analysis" | "lp" | "competitors" | "reports" | "calendar" | "team" | "brief" | "analytics" | "genre";

/** Minimal ad record type for SectionTabContent props */
interface AdRecord {
  ad_id: number;
  product_name?: string;
  advertiser_name?: string;
  genre?: string;
  hit_score?: number;
}

interface SectionTabContentProps<T extends AdRecord = AdRecord> {
  sectionTab: MainTab;
  setSectionTab: (tab: MainTab) => void;
  selectedGenre: string;
  setSelectedGenre: (genre: string) => void;
  selectedIds: number[];
  hitAds: T[];
  filteredAds: T[];
  onAdSelect: (adId: number) => void;
  onDetailAd: (ad: T) => void;
  period?: string;
}

export default function SectionTabContent<T extends AdRecord>({
  sectionTab,
  setSectionTab,
  selectedGenre,
  setSelectedGenre,
  selectedIds,
  hitAds,
  filteredAds,
  onAdSelect,
  onDetailAd,
  period,
}: SectionTabContentProps<T>) {
  const [profileAdvertiser, setProfileAdvertiser] = useState<string | null>(null);
  const [competitorName, setCompetitorName] = useState<string | null>(null);
  const [viewingReport, setViewingReport] = useState<{ id: string | number; format: string } | null>(null);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);

  const genre = selectedGenre !== "all" ? selectedGenre : undefined;

  const handleAdSelect = (adId: number) => {
    const ad = hitAds.find((a) => a.ad_id === adId);
    if (ad) onDetailAd(ad);
    else onAdSelect(adId);
  };

  if (sectionTab === "overview") return null;

  const renderContent = () => {
    switch (sectionTab) {
      case "trends":
        return (
          <div className="space-y-4">
            <MarketOverview genre={genre} />
            <TrendCharts genre={genre} />
          </div>
        );

      case "advertisers":
        return profileAdvertiser ? (
          <AdvertiserProfile
            advertiserName={profileAdvertiser}
            onAdSelect={handleAdSelect}
            onBack={() => setProfileAdvertiser(null)}
          />
        ) : (
          <AdvertiserLeaderboard
            genre={genre}
            onAdSelect={onAdSelect}
            onAdvertiserProfile={setProfileAdvertiser}
          />
        );

      case "formulas":
        return <WinningFormulas genre={genre} onAdSelect={onAdSelect} />;

      case "market":
        return <MarketOverview genre={genre} />;

      case "compare":
        return (
          <div className="space-y-4">
            {selectedIds.length < 2 ? (
              <div className="card px-4 py-10 text-center">
                <svg className="w-12 h-12 text-gray-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                </svg>
                <p className="text-[13px] font-medium text-gray-600 mb-1">比較する広告を選択してください</p>
                <p className="text-[11px] text-gray-400 mb-3">概要タブのテーブルまたはカードビューで2-4件の広告にチェックを入れてください</p>
                <button onClick={() => setSectionTab("overview")} className="btn-primary text-[12px] px-4 py-2">
                  概要タブに戻る
                </button>
              </div>
            ) : (
              <AdComparisonView
                adIds={selectedIds.slice(0, 4)}
                onClose={() => setSectionTab("overview")}
                onAdSelect={handleAdSelect}
                inline
              />
            )}
            <AdComparisonTool onAdSelect={handleAdSelect} />
          </div>
        );

      case "collections":
        return <CollectionsView onAdSelect={handleAdSelect} />;

      case "ai":
        return (
          <div className="space-y-4">
            <CreativePlanner genre={genre} onAdSelect={handleAdSelect} />
            <Recommendations genre={genre} onAdSelect={handleAdSelect} />
          </div>
        );

      case "scenario":
        return (
          <div className="space-y-4">
            <ScenarioBuilder
              loadScenarioId={selectedScenarioId}
              onScenarioLoaded={() => setSelectedScenarioId(null)}
            />
            <SavedScenarios onLoad={setSelectedScenarioId} />
          </div>
        );

      case "deep-analysis":
        return (
          <div className="space-y-4">
            <SuccessFailureAnalysis genre={genre} onAdSelect={handleAdSelect} />
            <ElementAnalysis genre={genre} onElementFilter={() => {}} />
          </div>
        );

      case "lp":
        return (
          <div className="space-y-4">
            <LPAnalysisPanel genre={genre} />
            <FunnelView
              adIds={selectedIds.length > 0 ? selectedIds : filteredAds.slice(0, 6).map((a) => a.ad_id)}
              onAdSelect={handleAdSelect}
            />
            {selectedIds.length >= 2 && <LPComparison adIds={selectedIds.slice(0, 3)} />}
          </div>
        );

      case "competitors":
        return competitorName ? (
          <CompetitorProfile
            name={competitorName}
            onBack={() => setCompetitorName(null)}
            onAdSelect={handleAdSelect}
          />
        ) : (
          <div className="space-y-4">
            <CompetitorDashboard
              genre={genre}
              onAdSelect={handleAdSelect}
              onCompetitorSelect={(name) => setCompetitorName(name)}
            />
            <MarketGaps genre={genre} />
          </div>
        );

      case "reports":
        return viewingReport ? (
          <ReportViewer
            reportId={viewingReport.id}
            format={viewingReport.format}
            onBack={() => setViewingReport(null)}
          />
        ) : (
          <div className="space-y-4">
            <ReportsView genre={genre} onAdSelect={handleAdSelect} />
            <ReportGenerator
              genre={genre}
              onViewReport={(report: { id: string | number; format: string }) => setViewingReport({ id: report.id, format: report.format })}
            />
          </div>
        );

      case "calendar":
        return (
          <div className="space-y-4">
            <CalendarView />
            <AdTimeline />
          </div>
        );

      case "team":
        return <TeamActivity />;

      case "brief":
        return (
          <div className="space-y-4">
            <CreativeBriefGenerator genre={genre} />
            <TemplateLibrary />
            <CopyVariations />
          </div>
        );

      case "analytics":
        return <AnalyticsDashboard genre={genre} onAdSelect={handleAdSelect} />;

      case "genre":
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <GenreDistributionChart period={period || "7d"} onGenreClick={(g) => setSelectedGenre(g)} />
              <GenreComparisonView period={period || "7d"} />
            </div>
            <GenreTrendChart period={period || "30d"} onGenreClick={(g) => setSelectedGenre(g)} />
          </div>
        );

      default:
        return null;
    }
  };

  const content = renderContent();
  return content ? (
    <ErrorBoundary key={sectionTab} label={`タブ: ${sectionTab}`}>
      {content}
    </ErrorBoundary>
  ) : null;
}
