"use client";

import { useState, useEffect } from "react";
import { lpAnalysisApi } from "@/lib/api";

type LPTab = "list" | "competitor" | "usp-flow" | "own-lp";

interface LPData {
  id: number;
  url: string;
  domain: string;
  title: string;
  lpType: string;
  genre: string;
  advertiser: string;
  product: string;
  qualityScore: number;
  conversionScore: number;
  trustScore: number;
  primaryAppeal: string;
  secondaryAppeal: string;
  ctaCount: number;
  testimonialCount: number;
  wordCount: number;
  hasPricing: boolean;
  priceText: string;
  heroHeadline: string;
  status: string;
  analyzedAt: string;
}

const appealAxisLabels: Record<string, string> = {
  benefit: "ベネフィット訴求",
  problem_solution: "悩み解決型",
  authority: "権威性",
  social_proof: "社会的証明",
  urgency: "緊急性",
  price: "価格訴求",
  comparison: "比較優位性",
  emotional: "感情訴求",
  fear: "恐怖訴求",
  novelty: "新規性・話題性",
};

const appealAxisColors: Record<string, string> = {
  benefit: "bg-blue-500",
  problem_solution: "bg-purple-500",
  authority: "bg-amber-500",
  social_proof: "bg-emerald-500",
  urgency: "bg-red-500",
  price: "bg-orange-500",
  comparison: "bg-cyan-500",
  emotional: "bg-pink-500",
  fear: "bg-gray-600",
  novelty: "bg-indigo-500",
};

interface OwnLP {
  id: number;
  label: string;
  version: number;
  genre: string;
  product: string;
  qualityScore: number;
  conversionScore: number;
  trustScore: number;
  competitorCount: number;
  avgCompetitorQuality: number;
  status: string;
  createdAt: string;
}

type ImportMethod = "url" | "html" | "text";

const uspCategoryLabels: Record<string, string> = {
  efficacy: "効果・実感",
  authority: "権威性",
  price: "価格・保証",
  ingredient: "成分・原料",
  uniqueness: "独自性",
  guarantee: "保証・安心",
  convenience: "利便性",
  speed: "即効性",
  safety: "安全性",
  experience: "体験・口コミ",
};

function ScoreCircle({ score, label, color = "#4A7DFF" }: { score: number; label: string; color?: string }) {
  const circumference = 2 * Math.PI * 14;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-14 h-14">
        <svg className="w-14 h-14 -rotate-90" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="14" fill="none" stroke="#f3f4f6" strokeWidth="3" />
          <circle
            cx="18" cy="18" r="14" fill="none" stroke={color} strokeWidth="3"
            strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-[12px] font-bold text-gray-900">
          {score}
        </span>
      </div>
      <span className="text-[9px] text-gray-400 mt-1">{label}</span>
    </div>
  );
}

export default function LPAnalysisView() {
  const [activeTab, setActiveTab] = useState<LPTab>("list");
  const [selectedGenre, setSelectedGenre] = useState("all");
  const [crawlUrl, setCrawlUrl] = useState("");
  const [selectedLP, setSelectedLP] = useState<LPData | null>(null);

  // Data states
  const [lps, setLPs] = useState<LPData[]>([]);
  const [lpsLoading, setLPsLoading] = useState(true);
  const [appealDistribution, setAppealDistribution] = useState<Array<{ axis: string; avgStrength: number; count: number; samples: string[] }>>([]);
  const [commonUSPs, setCommonUSPs] = useState<Array<{ category: string; count: number; prominence: number; keywords: string[] }>>([]);
  const [competitorLoading, setCompetitorLoading] = useState(false);
  const [uspFlow, setUSPFlow] = useState<Record<string, unknown> | null>(null);
  const [uspFlowLoading, setUSPFlowLoading] = useState(false);

  // Own LP state
  const [ownLPs, setOwnLPs] = useState<OwnLP[]>([]);
  const [ownLPsLoading, setOwnLPsLoading] = useState(true);
  const [selectedOwnLP, setSelectedOwnLP] = useState<OwnLP | null>(null);
  const [showCompare, setShowCompare] = useState(false);
  const [compareResult, setCompareResult] = useState<Record<string, unknown> | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [importMethod, setImportMethod] = useState<ImportMethod>("url");
  const [importLabel, setImportLabel] = useState("");
  const [importGenre, setImportGenre] = useState("美容・コスメ");
  const [importProduct, setImportProduct] = useState("");
  const [importContent, setImportContent] = useState("");

  // Fetch LPs
  useEffect(() => {
    const fetchLPs = async () => {
      setLPsLoading(true);
      try {
        const params: Record<string, string> = {};
        if (selectedGenre !== "all") params.genre = selectedGenre;
        const response = await lpAnalysisApi.list(params);
        const items = response.data?.items || response.data?.results || response.data;
        if (Array.isArray(items)) {
          const mapped: LPData[] = items.map((item: Record<string, unknown>, idx: number) => ({
            id: (item.id as number) || idx + 1,
            url: (item.url as string) || "",
            domain: (item.domain as string) || new URL((item.url as string) || "https://example.com").hostname,
            title: (item.title as string) || "",
            lpType: (item.lp_type as string) || (item.destination_type as string) || "",
            genre: (item.genre as string) || "",
            advertiser: (item.advertiser_name as string) || (item.advertiser as string) || "",
            product: (item.product_name as string) || (item.product as string) || "",
            qualityScore: (item.quality_score as number) || 0,
            conversionScore: (item.conversion_score as number) || 0,
            trustScore: (item.trust_score as number) || 0,
            primaryAppeal: (item.primary_appeal as string) || "",
            secondaryAppeal: (item.secondary_appeal as string) || "",
            ctaCount: (item.cta_count as number) || 0,
            testimonialCount: (item.testimonial_count as number) || 0,
            wordCount: (item.word_count as number) || 0,
            hasPricing: (item.has_pricing as boolean) || false,
            priceText: (item.price_text as string) || "",
            heroHeadline: (item.hero_headline as string) || "",
            status: (item.status as string) || "",
            analyzedAt: (item.analyzed_at as string) || (item.created_at as string) || "",
          }));
          setLPs(mapped);
        }
      } catch (error) {
        console.error("Failed to fetch LPs:", error);
      } finally {
        setLPsLoading(false);
      }
    };
    fetchLPs();
  }, [selectedGenre]);

  // Fetch own LPs
  useEffect(() => {
    const fetchOwnLPs = async () => {
      setOwnLPsLoading(true);
      try {
        const response = await lpAnalysisApi.listOwn();
        const items = response.data?.items || response.data?.results || response.data;
        if (Array.isArray(items)) {
          const mapped: OwnLP[] = items.map((item: Record<string, unknown>) => ({
            id: (item.id as number) || 0,
            label: (item.label as string) || "",
            version: (item.version as number) || 1,
            genre: (item.genre as string) || "",
            product: (item.product_name as string) || "",
            qualityScore: (item.quality_score as number) || 0,
            conversionScore: (item.conversion_score as number) || 0,
            trustScore: (item.trust_score as number) || 0,
            competitorCount: (item.competitor_count as number) || 0,
            avgCompetitorQuality: (item.avg_competitor_quality as number) || 0,
            status: (item.status as string) || "",
            createdAt: (item.created_at as string) || "",
          }));
          setOwnLPs(mapped);
        }
      } catch (error) {
        console.error("Failed to fetch own LPs:", error);
      } finally {
        setOwnLPsLoading(false);
      }
    };
    fetchOwnLPs();
  }, []);

  // Fetch competitor insight when switching to competitor tab
  useEffect(() => {
    if (activeTab !== "competitor") return;
    const fetchCompetitorInsight = async () => {
      setCompetitorLoading(true);
      try {
        const response = await lpAnalysisApi.competitorInsight({
          genre: selectedGenre !== "all" ? selectedGenre : "美容・コスメ",
        });
        const data = response.data;
        if (data) {
          if (Array.isArray(data.appeal_distribution)) {
            setAppealDistribution(data.appeal_distribution.map((item: Record<string, unknown>) => ({
              axis: (item.axis as string) || "",
              avgStrength: (item.avg_strength as number) || 0,
              count: (item.count as number) || 0,
              samples: (item.samples as string[]) || [],
            })));
          }
          if (Array.isArray(data.common_usps)) {
            setCommonUSPs(data.common_usps.map((item: Record<string, unknown>) => ({
              category: (item.category as string) || "",
              count: (item.count as number) || 0,
              prominence: (item.prominence as number) || 0,
              keywords: (item.keywords as string[]) || [],
            })));
          }
        }
      } catch (error) {
        console.error("Failed to fetch competitor insight:", error);
      } finally {
        setCompetitorLoading(false);
      }
    };
    fetchCompetitorInsight();
  }, [activeTab, selectedGenre]);

  // Handle crawl
  const handleCrawl = async () => {
    if (!crawlUrl.trim()) return;
    try {
      await lpAnalysisApi.crawl({ url: crawlUrl, auto_analyze: true });
      setCrawlUrl("");
      // Refresh LP list
      const response = await lpAnalysisApi.list();
      const items = response.data?.items || response.data?.results || response.data;
      if (Array.isArray(items)) {
        setLPs(items.map((item: Record<string, unknown>, idx: number) => ({
          id: (item.id as number) || idx + 1,
          url: (item.url as string) || "",
          domain: (item.domain as string) || "",
          title: (item.title as string) || "",
          lpType: (item.lp_type as string) || "",
          genre: (item.genre as string) || "",
          advertiser: (item.advertiser_name as string) || "",
          product: (item.product_name as string) || "",
          qualityScore: (item.quality_score as number) || 0,
          conversionScore: (item.conversion_score as number) || 0,
          trustScore: (item.trust_score as number) || 0,
          primaryAppeal: (item.primary_appeal as string) || "",
          secondaryAppeal: (item.secondary_appeal as string) || "",
          ctaCount: (item.cta_count as number) || 0,
          testimonialCount: (item.testimonial_count as number) || 0,
          wordCount: (item.word_count as number) || 0,
          hasPricing: (item.has_pricing as boolean) || false,
          priceText: (item.price_text as string) || "",
          heroHeadline: (item.hero_headline as string) || "",
          status: (item.status as string) || "",
          analyzedAt: (item.analyzed_at as string) || "",
        })));
      }
    } catch (error) {
      console.error("Failed to crawl LP:", error);
    }
  };

  // Handle own LP import
  const handleImport = async () => {
    if (!importLabel.trim()) return;
    try {
      await lpAnalysisApi.importOwn({
        label: importLabel,
        genre: importGenre,
        product_name: importProduct,
        url: importMethod === "url" ? importContent : undefined,
        html_content: importMethod === "html" ? importContent : undefined,
        text_content: importMethod === "text" ? importContent : undefined,
        auto_analyze: true,
      });
      setImportLabel("");
      setImportProduct("");
      setImportContent("");
      // Refresh own LPs
      const response = await lpAnalysisApi.listOwn();
      const items = response.data?.items || response.data?.results || response.data;
      if (Array.isArray(items)) {
        setOwnLPs(items.map((item: Record<string, unknown>) => ({
          id: (item.id as number) || 0,
          label: (item.label as string) || "",
          version: (item.version as number) || 1,
          genre: (item.genre as string) || "",
          product: (item.product_name as string) || "",
          qualityScore: (item.quality_score as number) || 0,
          conversionScore: (item.conversion_score as number) || 0,
          trustScore: (item.trust_score as number) || 0,
          competitorCount: (item.competitor_count as number) || 0,
          avgCompetitorQuality: (item.avg_competitor_quality as number) || 0,
          status: (item.status as string) || "",
          createdAt: (item.created_at as string) || "",
        })));
      }
    } catch (error) {
      console.error("Failed to import own LP:", error);
    }
  };

  // Handle compare
  const handleCompare = async (lp: OwnLP) => {
    setSelectedOwnLP(lp);
    setShowCompare(true);
    setCompareLoading(true);
    try {
      const response = await lpAnalysisApi.compareOwn({
        own_lp_id: lp.id,
        genre: lp.genre,
      });
      setCompareResult(response.data);
    } catch (error) {
      console.error("Failed to compare LP:", error);
    } finally {
      setCompareLoading(false);
    }
  };

  // Handle USP flow generation
  const handleGenerateUSPFlow = async (productName: string, productDesc: string, target: string, genre: string) => {
    setUSPFlowLoading(true);
    try {
      const response = await lpAnalysisApi.uspFlow({
        product_name: productName,
        product_description: productDesc,
        target_audience: target,
        genre: genre,
      });
      setUSPFlow(response.data);
    } catch (error) {
      console.error("Failed to generate USP flow:", error);
    } finally {
      setUSPFlowLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">LP分析・USP設計</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">
            遷移先LPの分析 → 訴求パターン把握 → USP→記事LP導線設計
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            <input
              type="text"
              placeholder="LP URLを入力して分析..."
              className="input text-xs w-64"
              value={crawlUrl}
              onChange={(e) => setCrawlUrl(e.target.value)}
            />
            <button
              className="btn-primary text-xs whitespace-nowrap"
              onClick={handleCrawl}
            >
              分析開始
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 px-5 border-b border-gray-200 bg-[#f8f9fc]">
        {([
          { id: "list" as LPTab, label: "LP一覧・分析" },
          { id: "own-lp" as LPTab, label: "自社LP管理" },
          { id: "competitor" as LPTab, label: "競合訴求パターン" },
          { id: "usp-flow" as LPTab, label: "USP→記事LP設計" },
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

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {activeTab === "list" && (
          <div className="flex h-full">
            {/* LP List */}
            <div className={`${selectedLP ? "w-1/2 border-r border-gray-200" : "w-full"} overflow-y-auto custom-scrollbar`}>
              <div className="p-4 space-y-2">
                {/* Genre filter */}
                <div className="flex items-center gap-2 mb-3">
                  <select
                    className="select-filter text-xs"
                    value={selectedGenre}
                    onChange={(e) => setSelectedGenre(e.target.value)}
                  >
                    <option value="all">全ジャンル</option>
                    <option value="美容・コスメ">美容・コスメ</option>
                    <option value="健康食品">健康食品</option>
                    <option value="ヘアケア">ヘアケア</option>
                  </select>
                  <span className="text-[11px] text-gray-400">
                    {lpsLoading ? "読み込み中..." : `${lps.length}件のLP`}
                  </span>
                </div>

                {lpsLoading && (
                  <div className="flex items-center justify-center py-8">
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
                    <span className="ml-2 text-xs text-gray-400">読み込み中...</span>
                  </div>
                )}

                {!lpsLoading && lps.length === 0 && (
                  <div className="text-center py-12 text-gray-400">
                    <p className="text-xs">LP分析データがありません</p>
                    <p className="text-[10px] mt-1">上部のURL入力フィールドからLPを分析してください</p>
                  </div>
                )}

                {lps.map((lp) => (
                  <div
                    key={lp.id}
                    onClick={() => setSelectedLP(lp)}
                    className={`card cursor-pointer transition-shadow hover:shadow-md ${
                      selectedLP?.id === lp.id ? "ring-2 ring-[#4A7DFF]" : ""
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex gap-2 shrink-0">
                        <ScoreCircle score={lp.qualityScore} label="品質" />
                        <ScoreCircle score={lp.conversionScore} label="CV力" color="#10b981" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`badge text-[9px] ${
                            lp.lpType === "記事LP" ? "bg-purple-100 text-purple-700" : "bg-emerald-100 text-emerald-700"
                          }`}>{lp.lpType}</span>
                          <span className="badge-blue text-[9px]">{lp.genre}</span>
                        </div>
                        <p className="text-[12px] font-medium text-gray-900 truncate">{lp.title}</p>
                        <p className="text-[10px] text-gray-400 truncate mt-0.5">{lp.domain} · {lp.advertiser}</p>
                        {(lp.primaryAppeal || lp.secondaryAppeal) && (
                          <div className="flex items-center gap-1.5 mt-2">
                            {lp.primaryAppeal && (
                              <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[lp.primaryAppeal] || "bg-gray-500"}`}>
                                {appealAxisLabels[lp.primaryAppeal] || lp.primaryAppeal}
                              </span>
                            )}
                            {lp.secondaryAppeal && (
                              <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium text-white/90 ${appealAxisColors[lp.secondaryAppeal] || "bg-gray-500"}`}>
                                {appealAxisLabels[lp.secondaryAppeal] || lp.secondaryAppeal}
                              </span>
                            )}
                          </div>
                        )}
                        <div className="flex items-center gap-3 mt-2 text-[10px] text-gray-500">
                          {lp.ctaCount > 0 && <span>CTA×{lp.ctaCount}</span>}
                          {lp.testimonialCount > 0 && <span>口コミ×{lp.testimonialCount}</span>}
                          {lp.wordCount > 0 && <span>{(lp.wordCount / 1000).toFixed(1)}k文字</span>}
                          {lp.hasPricing && <span className="text-orange-600 font-medium">{lp.priceText}</span>}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* LP Detail Panel */}
            {selectedLP && (
              <div className="w-1/2 overflow-y-auto custom-scrollbar p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-[13px] font-bold text-gray-900">{selectedLP.product}</h3>
                  <button onClick={() => setSelectedLP(null)} className="text-gray-400 hover:text-gray-600">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                {selectedLP.heroHeadline && (
                  <div className="card bg-gradient-to-r from-blue-50 to-purple-50">
                    <p className="text-[10px] text-gray-400 font-medium mb-1">ヒーロー見出し</p>
                    <p className="text-[14px] font-bold text-gray-900 leading-relaxed">{selectedLP.heroHeadline}</p>
                  </div>
                )}
                <div className="grid grid-cols-4 gap-2">
                  <div className="card py-2 text-center">
                    <p className="text-[9px] text-gray-400">品質</p>
                    <p className="text-lg font-bold text-[#4A7DFF]">{selectedLP.qualityScore}</p>
                  </div>
                  <div className="card py-2 text-center">
                    <p className="text-[9px] text-gray-400">CV力</p>
                    <p className="text-lg font-bold text-emerald-600">{selectedLP.conversionScore}</p>
                  </div>
                  <div className="card py-2 text-center">
                    <p className="text-[9px] text-gray-400">信頼性</p>
                    <p className="text-lg font-bold text-amber-600">{selectedLP.trustScore}</p>
                  </div>
                  <div className="card py-2 text-center">
                    <p className="text-[9px] text-gray-400">CTAx</p>
                    <p className="text-lg font-bold text-gray-900">{selectedLP.ctaCount}</p>
                  </div>
                </div>
                {(selectedLP.primaryAppeal || selectedLP.secondaryAppeal) && (
                  <div className="card">
                    <h4 className="text-[12px] font-bold text-gray-900 mb-2">訴求軸</h4>
                    <div className="space-y-2">
                      {selectedLP.primaryAppeal && (
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[selectedLP.primaryAppeal] || "bg-gray-500"}`}>
                              主訴求: {appealAxisLabels[selectedLP.primaryAppeal] || selectedLP.primaryAppeal}
                            </span>
                          </div>
                        </div>
                      )}
                      {selectedLP.secondaryAppeal && (
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[selectedLP.secondaryAppeal] || "bg-gray-500"}`}>
                              副訴求: {appealAxisLabels[selectedLP.secondaryAppeal] || selectedLP.secondaryAppeal}
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                <div className="card">
                  <h4 className="text-[12px] font-bold text-gray-900 mb-1">LP URL</h4>
                  <a href={selectedLP.url} target="_blank" rel="noopener noreferrer" className="text-[11px] text-[#4A7DFF] hover:underline break-all">
                    {selectedLP.url}
                  </a>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "competitor" && (
          <div className="p-5 space-y-5">
            <div className="flex items-center gap-3">
              <select
                className="select-filter"
                value={selectedGenre}
                onChange={(e) => setSelectedGenre(e.target.value)}
              >
                <option value="美容・コスメ">美容・コスメ</option>
                <option value="健康食品">健康食品</option>
                <option value="ヘアケア">ヘアケア</option>
              </select>
              <span className="text-[11px] text-gray-400">
                {competitorLoading ? "読み込み中..." : `ジャンル内の分析データ`}
              </span>
            </div>

            {competitorLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
                <span className="ml-2 text-xs text-gray-400">分析中...</span>
              </div>
            )}

            {!competitorLoading && appealDistribution.length === 0 && (
              <div className="card text-center py-8 text-gray-400">
                <p className="text-xs">競合分析データがありません</p>
                <p className="text-[10px] mt-1">先にLPをクロール・分析してください</p>
              </div>
            )}

            {appealDistribution.length > 0 && (
              <div className="card">
                <h3 className="text-[13px] font-bold text-gray-900 mb-3">訴求軸の使用状況（競合LP横断分析）</h3>
                <div className="space-y-3">
                  {appealDistribution.map((item) => (
                    <div key={item.axis}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[item.axis] || "bg-gray-500"}`}>
                            {appealAxisLabels[item.axis] || item.axis}
                          </span>
                          <span className="text-[10px] text-gray-500">{item.count}件のLPで使用</span>
                        </div>
                        <span className="text-[12px] font-semibold text-gray-700">{item.avgStrength}</span>
                      </div>
                      <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${appealAxisColors[item.axis] || "bg-gray-400"} transition-all`}
                          style={{ width: `${item.avgStrength}%` }}
                        />
                      </div>
                      {item.samples.length > 0 && (
                        <div className="flex gap-2 mt-1">
                          {item.samples.map((s, i) => (
                            <span key={i} className="text-[9px] text-gray-400 italic">{s}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {commonUSPs.length > 0 && (
              <div className="card">
                <h3 className="text-[13px] font-bold text-gray-900 mb-3">よく使われるUSPカテゴリ</h3>
                <div className="grid grid-cols-2 gap-3">
                  {commonUSPs.map((usp) => (
                    <div key={usp.category} className="p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[11px] font-bold text-gray-800">
                          {uspCategoryLabels[usp.category] || usp.category}
                        </span>
                        <span className="text-[10px] text-gray-500">{usp.count}件</span>
                      </div>
                      <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden mb-2">
                        <div className="h-full rounded-full bg-[#4A7DFF]" style={{ width: `${usp.prominence}%` }} />
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {usp.keywords.map((kw) => (
                          <span key={kw} className="rounded bg-white px-1.5 py-0.5 text-[9px] text-gray-600 border border-gray-200">
                            {kw}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "own-lp" && (
          <div className="flex h-full">
            <div className={`${showCompare ? "w-1/2 border-r border-gray-200" : "w-full"} overflow-y-auto custom-scrollbar`}>
              <div className="p-4 space-y-4">
                {/* Import Form */}
                <div className="card">
                  <h3 className="text-[13px] font-bold text-gray-900 mb-3">自社LP取り込み</h3>
                  <p className="text-[11px] text-gray-500 mb-3">
                    自社の記事LPをURL、HTML、またはテキストで取り込み、競合LPと比較分析できます。
                  </p>
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div>
                      <label className="text-[10px] text-gray-500 font-medium">管理ラベル</label>
                      <input className="input text-xs mt-1 w-full" placeholder="例: セラムV3_記事LP_A案" value={importLabel} onChange={(e) => setImportLabel(e.target.value)} />
                    </div>
                    <div>
                      <label className="text-[10px] text-gray-500 font-medium">ジャンル</label>
                      <select className="select-filter w-full mt-1 text-xs" value={importGenre} onChange={(e) => setImportGenre(e.target.value)}>
                        <option>美容・コスメ</option>
                        <option>健康食品</option>
                        <option>ヘアケア</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] text-gray-500 font-medium">商品名</label>
                      <input className="input text-xs mt-1 w-full" placeholder="例: スキンケアセラムV3" value={importProduct} onChange={(e) => setImportProduct(e.target.value)} />
                    </div>
                  </div>
                  <div className="flex gap-1 mb-2">
                    {([
                      { id: "url" as ImportMethod, label: "URL" },
                      { id: "html" as ImportMethod, label: "HTML" },
                      { id: "text" as ImportMethod, label: "テキスト" },
                    ]).map((m) => (
                      <button
                        key={m.id}
                        onClick={() => { setImportMethod(m.id); setImportContent(""); }}
                        className={`px-3 py-1 rounded text-[11px] font-medium transition-colors ${
                          importMethod === m.id ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                        }`}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                  {importMethod === "url" ? (
                    <input className="input text-xs w-full" placeholder="https://your-lp.example.com/article-lp" value={importContent} onChange={(e) => setImportContent(e.target.value)} />
                  ) : (
                    <textarea className="input text-xs w-full h-24 resize-y" placeholder={importMethod === "html" ? "<html>...</html>" : "記事LPのテキスト本文を貼り付け..."} value={importContent} onChange={(e) => setImportContent(e.target.value)} />
                  )}
                  <button className="btn-primary text-xs mt-3" onClick={handleImport}>
                    <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                    </svg>
                    取り込み開始
                  </button>
                </div>

                {/* Own LP List */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-[13px] font-bold text-gray-900">自社LP一覧</h3>
                    <span className="text-[11px] text-gray-400">
                      {ownLPsLoading ? "読み込み中..." : `${ownLPs.length}件`}
                    </span>
                  </div>

                  {!ownLPsLoading && ownLPs.length === 0 && (
                    <div className="text-center py-8 text-gray-400">
                      <p className="text-xs">自社LPがまだ登録されていません</p>
                      <p className="text-[10px] mt-1">上のフォームからLPを取り込んでください</p>
                    </div>
                  )}

                  <div className="space-y-2">
                    {ownLPs.map((lp) => {
                      const qualityDiff = lp.qualityScore - lp.avgCompetitorQuality;
                      return (
                        <div
                          key={lp.id}
                          onClick={() => handleCompare(lp)}
                          className={`card cursor-pointer transition-shadow hover:shadow-md ${
                            selectedOwnLP?.id === lp.id ? "ring-2 ring-[#4A7DFF]" : ""
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <div className="flex gap-2 shrink-0">
                              <ScoreCircle score={lp.qualityScore} label="品質" />
                              <ScoreCircle score={lp.conversionScore} label="CV力" color="#10b981" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="badge text-[9px] bg-indigo-100 text-indigo-700">自社LP</span>
                                <span className="badge-blue text-[9px]">{lp.genre}</span>
                                <span className="text-[9px] text-gray-400">v{lp.version}</span>
                              </div>
                              <p className="text-[12px] font-medium text-gray-900 truncate">{lp.label}</p>
                              <p className="text-[10px] text-gray-400 mt-0.5">{lp.product}</p>
                              {lp.competitorCount > 0 && (
                                <div className="flex items-center gap-3 mt-2">
                                  <span className="text-[10px] text-gray-500">競合 {lp.competitorCount}件</span>
                                  <span className={`text-[10px] font-medium ${qualityDiff >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                                    {qualityDiff >= 0 ? "▲" : "▼"} 競合平均比 {qualityDiff >= 0 ? "+" : ""}{qualityDiff}pt
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Comparison Panel */}
            {showCompare && selectedOwnLP && (
              <div className="w-1/2 overflow-y-auto custom-scrollbar p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-[13px] font-bold text-gray-900">
                    競合比較: {selectedOwnLP.label}
                  </h3>
                  <button onClick={() => setShowCompare(false)} className="text-gray-400 hover:text-gray-600">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {compareLoading && (
                  <div className="flex items-center justify-center py-8">
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
                    <span className="ml-2 text-xs text-gray-400">比較分析中...</span>
                  </div>
                )}

                {!compareLoading && !compareResult && (
                  <div className="text-center py-8 text-gray-400">
                    <p className="text-xs">比較データを取得できませんでした</p>
                  </div>
                )}

                {!compareLoading && compareResult && (
                  <>
                    {/* Score Comparison Bars */}
                    {Array.isArray((compareResult as Record<string, unknown>).scores) && (
                      <div className="card">
                        <h4 className="text-[12px] font-bold text-gray-900 mb-3">スコア比較（自社 vs 競合平均）</h4>
                        <div className="space-y-3">
                          {((compareResult as Record<string, unknown>).scores as Array<{ label: string; own: number; comp: number; color: string }>).map((s) => (
                            <div key={s.label}>
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-[11px] text-gray-700 font-medium">{s.label}</span>
                                <div className="flex items-center gap-2 text-[10px]">
                                  <span className="font-bold" style={{ color: s.color }}>自社 {s.own}</span>
                                  <span className="text-gray-400">vs</span>
                                  <span className="text-gray-600">競合平均 {s.comp}</span>
                                </div>
                              </div>
                              <div className="flex gap-1 h-3">
                                <div className="rounded-l-full h-full transition-all" style={{ width: `${s.own}%`, backgroundColor: s.color }} />
                                <div className="rounded-r-full h-full bg-gray-300 transition-all" style={{ width: `${s.comp}%` }} />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Strengths & Improvements */}
                    {Array.isArray((compareResult as Record<string, unknown>).strengths) && (
                      <div className="card">
                        <h4 className="text-[12px] font-bold text-gray-900 mb-3">AI改善提案</h4>
                        <div className="mb-3">
                          <span className="text-[11px] font-bold text-emerald-700">競合に対する強み</span>
                          <div className="space-y-1 mt-1">
                            {((compareResult as Record<string, unknown>).strengths as string[]).map((s, i) => (
                              <div key={i} className="flex items-start gap-1.5">
                                <span className="shrink-0 mt-1 w-1.5 h-1.5 rounded-full bg-emerald-400" />
                                <span className="text-[11px] text-gray-700">{s}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                        {Array.isArray((compareResult as Record<string, unknown>).improvements) && (
                          <div>
                            <span className="text-[11px] font-bold text-blue-700">改善機会</span>
                            <div className="space-y-1 mt-1">
                              {((compareResult as Record<string, unknown>).improvements as string[]).map((s, i) => (
                                <div key={i} className="flex items-start gap-1.5">
                                  <span className="shrink-0 mt-1 w-1.5 h-1.5 rounded-full bg-blue-400" />
                                  <span className="text-[11px] text-gray-700">{s}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === "usp-flow" && (
          <div className="p-5 space-y-5">
            {/* Input form */}
            <div className="card">
              <h3 className="text-[13px] font-bold text-gray-900 mb-3">USP→記事LP 導線設計エンジン</h3>
              <p className="text-[11px] text-gray-500 mb-3">
                商品情報と競合分析データを基に、最適なUSP設計から記事LP構成までの導線を自動提案します。
              </p>
              <form onSubmit={(e) => {
                e.preventDefault();
                const fd = new FormData(e.currentTarget);
                handleGenerateUSPFlow(
                  fd.get("product") as string,
                  fd.get("description") as string,
                  fd.get("target") as string,
                  fd.get("genre") as string,
                );
              }}>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] text-gray-500 font-medium">商品名</label>
                    <input name="product" className="input text-xs mt-1" required />
                  </div>
                  <div>
                    <label className="text-[10px] text-gray-500 font-medium">ジャンル</label>
                    <select name="genre" className="select-filter w-full mt-1 text-xs">
                      <option>美容・コスメ</option>
                      <option>健康食品</option>
                      <option>ヘアケア</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-[10px] text-gray-500 font-medium">ターゲット</label>
                    <input name="target" className="input text-xs mt-1" required />
                  </div>
                  <div>
                    <label className="text-[10px] text-gray-500 font-medium">商品説明</label>
                    <input name="description" className="input text-xs mt-1" required />
                  </div>
                </div>
                <button type="submit" className="btn-primary text-xs mt-3" disabled={uspFlowLoading}>
                  {uspFlowLoading ? (
                    <div className="h-3.5 w-3.5 mr-1 inline-block animate-spin rounded-full border-2 border-white border-t-transparent" />
                  ) : (
                    <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                    </svg>
                  )}
                  AIで導線設計を生成
                </button>
              </form>
            </div>

            {!uspFlow && !uspFlowLoading && (
              <div className="card text-center py-12 text-gray-400">
                <p className="text-xs">商品情報を入力し「AIで導線設計を生成」をクリックしてください</p>
              </div>
            )}

            {uspFlow && (
              <>
                {/* USP Recommendation */}
                {(uspFlow as Record<string, unknown>).primaryUSP && (
                  <div className="card bg-gradient-to-r from-blue-50 to-indigo-50">
                    <div className="flex items-center gap-2 mb-2">
                      <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                      </svg>
                      <h3 className="text-[13px] font-bold text-gray-900">推奨USP</h3>
                    </div>
                    <p className="text-[14px] font-bold text-[#4A7DFF] mb-1">{(uspFlow as Record<string, unknown>).primaryUSP as string}</p>
                    {(uspFlow as Record<string, unknown>).appealAxis && (
                      <p className="text-[11px] text-gray-600">
                        推奨訴求軸: <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[(uspFlow as Record<string, unknown>).appealAxis as string] || "bg-gray-500"}`}>
                          {appealAxisLabels[(uspFlow as Record<string, unknown>).appealAxis as string] || (uspFlow as Record<string, unknown>).appealAxis as string}
                        </span>
                      </p>
                    )}
                  </div>
                )}

                {/* Structure */}
                {Array.isArray((uspFlow as Record<string, unknown>).structure) && (
                  <div className="card">
                    <h3 className="text-[13px] font-bold text-gray-900 mb-4">推奨 記事LP構成</h3>
                    <div className="relative">
                      <div className="absolute left-4 top-3 bottom-3 w-0.5 bg-gradient-to-b from-[#4A7DFF] to-purple-400" />
                      <div className="space-y-4">
                        {((uspFlow as Record<string, unknown>).structure as Array<{ section: string; purpose: string; guide: string; technique: string }>).map((section, i, arr) => (
                          <div key={i} className="relative flex items-start gap-4 pl-10">
                            <div className={`absolute left-2 top-1 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white ${
                              i === 0 ? "bg-[#4A7DFF]" : i === arr.length - 1 ? "bg-purple-500" : "bg-gray-400"
                            }`}>
                              {i + 1}
                            </div>
                            <div className="flex-1 p-3 bg-gray-50 rounded-lg">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-[12px] font-bold text-gray-900">{section.section}</span>
                                <span className="badge text-[8px] bg-blue-100 text-blue-700">{section.technique}</span>
                              </div>
                              <p className="text-[10px] text-gray-500 mb-0.5">{section.purpose}</p>
                              <p className="text-[11px] text-gray-700">{section.guide}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Headlines */}
                {Array.isArray((uspFlow as Record<string, unknown>).headlines) && (
                  <div className="card">
                    <h3 className="text-[13px] font-bold text-gray-900 mb-3">見出し案</h3>
                    <div className="space-y-2">
                      {((uspFlow as Record<string, unknown>).headlines as string[]).map((hl, i) => (
                        <div key={i} className="flex items-start gap-2 p-2 bg-gray-50 rounded-lg">
                          <span className="shrink-0 w-5 h-5 rounded bg-[#4A7DFF] text-white text-[10px] font-bold flex items-center justify-center">{i + 1}</span>
                          <p className="text-[12px] text-gray-800 font-medium leading-relaxed">{hl}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
