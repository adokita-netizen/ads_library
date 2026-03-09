"use client";

import { useState, useEffect } from "react";
import { lpAnalysisApi } from "@/lib/api";
import { useUrlParam } from "@/lib/useUrlParam";

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
const LP_TAB_IDS: LPTab[] = ["list", "competitor", "usp-flow", "own-lp"];

const GENRE_OPTIONS = [
  { value: "ec_d2c", label: "EC・D2C" },
  { value: "app", label: "アプリ" },
  { value: "finance", label: "金融" },
  { value: "education", label: "教育" },
  { value: "beauty", label: "美容・コスメ" },
  { value: "food", label: "食品" },
  { value: "gaming", label: "ゲーム" },
  { value: "health", label: "健康食品" },
  { value: "technology", label: "テクノロジー" },
  { value: "real_estate", label: "不動産" },
  { value: "travel", label: "旅行" },
  { value: "other", label: "その他" },
] as const;

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

const lpTabGuide: Array<{ id: LPTab; step: string; label: string; description: string }> = [
  { id: "list", step: "STEP 1", label: "競合LPを分析", description: "URLを入れて分析し、カードを押すと右側に詳細が出ます。" },
  { id: "own-lp", step: "STEP 2", label: "自社LPを登録", description: "URL・HTML・本文を取り込み、競合平均と比較できます。" },
  { id: "competitor", step: "STEP 3", label: "訴求傾向を見る", description: "集めたLPから、勝ち筋の訴求パターンをまとめて見ます。" },
  { id: "usp-flow", step: "STEP 4", label: "記事LP導線を作る", description: "商品情報を入れると、USPと記事LP構成案を出します。" },
];

const uspSampleInput = {
  product: "オンライン肥満外来サポート",
  genre: "health",
  target: "40代女性、自己流ダイエットで失敗経験があり、通院の手間は減らしたい人",
  description: "医師監修で食事指導とオンライン診療を組み合わせ、無理なく継続しやすいダイエット支援サービス",
};

const lpUrlSample = "https://lp.soelu.com/";

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

function isLPAnalyzed(lp: Pick<LPData, "qualityScore" | "conversionScore" | "trustScore" | "status">) {
  return lp.qualityScore > 0 || lp.conversionScore > 0 || lp.trustScore > 0 || lp.status === "analyzed";
}

export default function LPAnalysisView() {
  const [activeTabParam, setActiveTabParam] = useUrlParam("lp_step", "list");
  const activeTab = (LP_TAB_IDS.includes(activeTabParam as LPTab) ? activeTabParam : "list") as LPTab;
  const [selectedGenre, setSelectedGenre] = useState("all");
  const [crawlUrl, setCrawlUrl] = useState("");
  const [selectedLP, setSelectedLP] = useState<LPData | null>(null);
  const [showOnlyAnalyzed, setShowOnlyAnalyzed] = useState(true);

  // Data states
  const [lps, setLPs] = useState<LPData[]>([]);
  const [lpsLoading, setLPsLoading] = useState(true);
  const [appealDistribution, setAppealDistribution] = useState<Array<{ axis: string; avgStrength: number; count: number; samples: string[] }>>([]);
  const [commonUSPs, setCommonUSPs] = useState<Array<{ category: string; count: number; prominence: number; keywords: string[] }>>([]);
  const [competitorLoading, setCompetitorLoading] = useState(false);
  const [uspFlow, setUSPFlow] = useState<Record<string, unknown> | null>(null);
  const [uspFlowLoading, setUSPFlowLoading] = useState(false);
  const [crawlLoading, setCrawlLoading] = useState(false);

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
  const [importLoading, setImportLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uspProduct, setUSPProduct] = useState("");
  const [uspGenre, setUSPGenre] = useState("other");
  const [uspTarget, setUSPTarget] = useState("");
  const [uspDescription, setUSPDescription] = useState("");
  const analyzedLPCount = lps.filter((lp) => isLPAnalyzed(lp)).length;
  const hasCompetitorSeedData = appealDistribution.length > 0 || commonUSPs.length > 0;
  const hasEnoughCompetitorData = analyzedLPCount >= 3 && hasCompetitorSeedData;
  const visibleLPs = showOnlyAnalyzed ? lps.filter((lp) => isLPAnalyzed(lp)) : lps;
  const activeTabGuideItem = lpTabGuide.find((item) => item.id === activeTab) ?? lpTabGuide[0];
  const setActiveTab = (tab: LPTab) => setActiveTabParam(tab);

  // Helper: safely parse domain from URL
  const safeDomain = (url: string | undefined): string => {
    if (!url) return "";
    try { return new URL(url).hostname; } catch { return ""; }
  };

  // Helper: map LP API items to LPData (deduplicated)
  const mapLPItems = (items: Record<string, unknown>[]): LPData[] =>
    items.map((item, idx) => ({
      id: (item.id as number) || idx + 1,
      url: (item.url as string) || "",
      domain: (item.domain as string) || safeDomain(item.url as string),
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
      analyzedAt: (item.analyzed_at as string) || (item.created_at as string) || "",
    }));

  // Helper: map OwnLP API items (deduplicated)
  const mapOwnLPItems = (items: Record<string, unknown>[]): OwnLP[] =>
    items.map((item) => ({
      id: (item.id as number) || 0,
      label: (item.own_lp_label as string) || (item.label as string) || "",
      version: (item.own_lp_version as number) || (item.version as number) || 1,
      genre: (item.genre as string) || "",
      product: (item.product_name as string) || "",
      qualityScore: (item.quality_score as number) || 0,
      conversionScore: (item.conversion_score as number) || 0,
      trustScore: (item.trust_score as number) || 0,
      competitorCount: (item.competitor_count_in_genre as number) || (item.competitor_count as number) || 0,
      avgCompetitorQuality: (item.avg_competitor_quality as number) || 0,
      status: (item.status as string) || "",
      createdAt: (item.created_at as string) || "",
    }));

  // Auto-dismiss error
  useEffect(() => {
    if (!errorMessage) return;
    const t = setTimeout(() => setErrorMessage(null), 5000);
    return () => clearTimeout(t);
  }, [errorMessage]);

  // Fetch LPs
  useEffect(() => {
    const fetchLPs = async () => {
      setLPsLoading(true);
      try {
        const params: Record<string, string> = {};
        if (selectedGenre !== "all") params.genre = selectedGenre;
        const response = await lpAnalysisApi.list(params);
        const data = response.data;
        const items = data?.landing_pages || data?.items || data?.results;
        if (Array.isArray(items)) {
          setLPs(mapLPItems(items));
        }
      } catch (error) {
        console.error("Failed to fetch LPs:", error);
        setErrorMessage("LP一覧の取得に失敗しました");
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
        const data = response.data;
        const items = data?.own_lps || data?.items || data?.results;
        if (Array.isArray(items)) {
          setOwnLPs(mapOwnLPItems(items));
        }
      } catch (error) {
        console.error("Failed to fetch own LPs:", error);
        setErrorMessage("自社LP一覧の取得に失敗しました");
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
              axis: (item.appeal_axis as string) || (item.axis as string) || "",
              avgStrength: (item.avg_strength as number) || 0,
              count: (item.usage_count as number) || (item.count as number) || 0,
              samples: (item.sample_texts as string[]) || (item.samples as string[]) || [],
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
        setErrorMessage("競合分析データの取得に失敗しました");
      } finally {
        setCompetitorLoading(false);
      }
    };
    fetchCompetitorInsight();
  }, [activeTab, selectedGenre]);

  // Handle crawl
  const handleCrawl = async () => {
    const trimmed = crawlUrl.trim();
    if (!trimmed || crawlLoading) return;
    // Basic URL validation
    try { new URL(trimmed); } catch {
      setErrorMessage("有効なURLを入力してください（例: https://example.com）");
      return;
    }
    setCrawlLoading(true);
    try {
      await lpAnalysisApi.crawl({ url: crawlUrl, auto_analyze: true });
      setCrawlUrl("");
      // Refresh LP list
      const response = await lpAnalysisApi.list();
      const data = response.data;
      const items = data?.landing_pages || data?.items || data?.results;
      if (Array.isArray(items)) {
        setLPs(mapLPItems(items));
      }
    } catch (error) {
      console.error("Failed to crawl LP:", error);
      setErrorMessage("LPのクロールに失敗しました");
    } finally {
      setCrawlLoading(false);
    }
  };

  // Handle own LP import
  const handleImport = async () => {
    if (!importLabel.trim() || importLoading) return;
    setImportLoading(true);
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
      const data = response.data;
      const items = data?.own_lps || data?.items || data?.results;
      if (Array.isArray(items)) {
        setOwnLPs(mapOwnLPItems(items));
      }
    } catch (error) {
      console.error("Failed to import own LP:", error);
      setErrorMessage("自社LPの取り込みに失敗しました");
    } finally {
      setImportLoading(false);
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
      const raw = response.data;
      // Normalize compare response to frontend-friendly structure
      const scores = [
        { label: "品質スコア", own: raw.own_quality || 0, comp: raw.competitor_avg_quality || 0, color: "#4A7DFF" },
        { label: "CV力", own: raw.own_conversion || 0, comp: raw.competitor_avg_conversion || 0, color: "#10b981" },
        { label: "信頼性", own: raw.own_trust || 0, comp: raw.competitor_avg_trust || 0, color: "#f59e0b" },
      ];
      setCompareResult({
        ...raw,
        scores,
        strengths: raw.strengths_vs_competitors || [],
        improvements: raw.improvement_opportunities || [],
      });
    } catch (error) {
      console.error("Failed to compare LP:", error);
      setErrorMessage("競合比較に失敗しました");
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
      const raw = response.data;
      // Normalize USP flow response to frontend-friendly keys
      setUSPFlow({
        ...raw,
        primaryUSP: raw.recommended_primary_usp || raw.primaryUSP || "",
        appealAxis: raw.recommended_appeal_axis || raw.appealAxis || "",
        structure: raw.article_lp_structure || raw.structure || [],
        headlines: raw.headline_suggestions || raw.headlines || [],
      });
    } catch (error) {
      console.error("Failed to generate USP flow:", error);
      setErrorMessage("USP導線設計の生成に失敗しました");
    } finally {
      setUSPFlowLoading(false);
    }
  };

  const fillUSPSample = () => {
    setUSPProduct(uspSampleInput.product);
    setUSPGenre(uspSampleInput.genre);
    setUSPTarget(uspSampleInput.target);
    setUSPDescription(uspSampleInput.description);
  };

  const fillLPSampleUrl = () => {
    setActiveTab("list");
    setCrawlUrl(lpUrlSample);
  };

  const activeTabCallout = (() => {
    if (activeTab === "list") {
      return {
        title: "いまやること: 競合LPを1本入れて分析する",
        description: "分析結果が1本でも出ると、右側詳細と後続タブの意味が分かりやすくなります。",
        actionLabel: "サンプルURLを入れる",
        onAction: fillLPSampleUrl,
        nextLabel: analyzedLPCount > 0 ? "自社LP登録へ進む" : "USP設計へ進む",
        onNext: () => setActiveTab(analyzedLPCount > 0 ? "own-lp" : "usp-flow"),
      };
    }
    if (activeTab === "own-lp") {
      return {
        title: "いまやること: 自社LPの本文かURLを登録する",
        description: "まずは比較したい自社LPを1本だけ入れれば十分です。本文だけでも使えます。",
        actionLabel: "テキスト取り込みを使う",
        onAction: () => setImportMethod("text"),
        nextLabel: "競合傾向を見る",
        onNext: () => setActiveTab("competitor"),
      };
    }
    if (activeTab === "competitor") {
      return {
        title: "いまやること: 競合LPを3件以上ためる",
        description: "このタブは単発分析ではなく、複数LPの傾向をまとめて読むための場所です。",
        actionLabel: "競合LP分析に戻る",
        onAction: () => setActiveTab("list"),
        nextLabel: "USP設計へ進む",
        onNext: () => setActiveTab("usp-flow"),
      };
    }
    return {
      title: "いまやること: サンプル入力で記事LP導線を出す",
      description: "競合データがなくても、まず叩き台を出して使い方を掴めます。",
      actionLabel: "サンプル入力を入れる",
      onAction: fillUSPSample,
      nextLabel: "競合LP分析に戻る",
      onNext: () => setActiveTab("list"),
    };
  })();

  return (
    <div className="flex flex-col h-full">
      {/* Error Toast */}
      {errorMessage && (
        <div
          role="alert"
          aria-live="assertive"
          className="fixed top-4 right-4 z-50 flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 px-4 py-2.5 rounded-lg shadow-lg text-xs animate-in fade-in"
        >
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} className="ml-2 text-red-400 hover:text-red-600">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 bg-white">
        <div>
          <h2 className="text-[15px] font-bold text-gray-900">LP分析・USP設計</h2>
          <p className="text-[11px] text-gray-400 mt-0.5">
            遷移先LPの分析 → 訴求パターン把握 → USP→記事LP導線設計
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setActiveTab("list")}
              className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] font-medium text-gray-700 transition-colors hover:bg-gray-100"
            >
              使い方を見る
            </button>
            <button
              type="button"
              onClick={fillLPSampleUrl}
              className="rounded-lg border border-[#c8d8ff] bg-[#eef4ff] px-3 py-2 text-[11px] font-medium text-[#4A7DFF] transition-colors hover:bg-[#e5eeff]"
            >
              例を入れる
            </button>
            <div className="flex items-center gap-1">
              <input
                id="lp-crawl-url"
                type="url"
                aria-label="分析するLP URL"
                placeholder="LP URLを入力して分析..."
                className="input text-xs w-64"
                value={crawlUrl}
                onChange={(e) => setCrawlUrl(e.target.value)}
              />
              <button
                type="button"
                className="btn-primary text-xs whitespace-nowrap"
                onClick={handleCrawl}
                disabled={crawlLoading}
              >
                {crawlLoading ? "分析中..." : "分析開始"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="grid gap-3 border-b border-gray-200 bg-[#f8f9fc] px-5 py-3 md:grid-cols-4">
        {lpTabGuide.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`rounded-2xl border px-4 py-3 text-left transition-all ${
              activeTab === tab.id
                ? "border-[#4A7DFF] bg-white shadow-sm"
                : "border-gray-200 bg-white/70 hover:border-[#bcd0ff] hover:bg-white"
            }`}
          >
            <p className={`text-[10px] font-semibold tracking-[0.16em] ${activeTab === tab.id ? "text-[#4A7DFF]" : "text-gray-400"}`}>
              {tab.step}
            </p>
            <p className="mt-1 text-[13px] font-semibold text-gray-900">{tab.label}</p>
            <p className="mt-1 text-[11px] leading-5 text-gray-500">{tab.description}</p>
          </button>
        ))}
      </div>

      <div className="border-b border-gray-200 bg-gradient-to-r from-[#f7f9ff] via-white to-[#f5fbff] px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#4A7DFF]">Quick Start</p>
            <h3 className="mt-1 text-[15px] font-bold text-gray-900">この画面でやることを3手に絞る</h3>
            <p className="mt-1 text-[12px] leading-5 text-gray-600">
              1. 競合LPを1本分析して材料を作る 2. 必要なら自社LPを取り込んで比較する 3. USPから記事LP導線を生成する
            </p>
          </div>
          <div className="grid min-w-[260px] grid-cols-3 gap-2">
            <div className="rounded-xl border border-[#dbe6ff] bg-white px-3 py-2 text-center">
              <p className="text-[10px] text-gray-500">競合LP</p>
              <p className="text-[18px] font-bold text-gray-900">{lps.length}</p>
            </div>
            <div className="rounded-xl border border-[#dbe6ff] bg-white px-3 py-2 text-center">
              <p className="text-[10px] text-gray-500">分析済み</p>
              <p className="text-[18px] font-bold text-[#4A7DFF]">{analyzedLPCount}</p>
            </div>
            <div className="rounded-xl border border-[#dbe6ff] bg-white px-3 py-2 text-center">
              <p className="text-[10px] text-gray-500">自社LP</p>
              <p className="text-[18px] font-bold text-emerald-600">{ownLPs.length}</p>
            </div>
          </div>
        </div>
        <div className="mt-4 rounded-2xl border border-[#dbe6ff] bg-white px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="max-w-3xl">
              <p className="text-[10px] font-semibold tracking-[0.16em] text-[#4A7DFF]">{activeTabGuideItem.step}</p>
              <p className="mt-1 text-[13px] font-semibold text-gray-900">{activeTabCallout.title}</p>
              <p className="mt-1 text-[11px] leading-5 text-gray-500">{activeTabCallout.description}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={activeTabCallout.onAction}
                className="rounded-lg border border-[#c8d8ff] bg-[#eef4ff] px-3 py-2 text-[11px] font-medium text-[#4A7DFF] transition-colors hover:bg-[#e5eeff]"
              >
                {activeTabCallout.actionLabel}
              </button>
              <button
                type="button"
                onClick={activeTabCallout.onNext}
                className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] font-medium text-gray-700 transition-colors hover:bg-gray-100"
              >
                {activeTabCallout.nextLabel}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {activeTab === "list" && (
          <div className="flex h-full">
            {/* LP List */}
            <div className={`${selectedLP ? "w-1/2 border-r border-gray-200" : "w-full"} overflow-y-auto custom-scrollbar`}>
                <div className="p-4 space-y-2">
                  {!lpsLoading && lps.length > 0 && analyzedLPCount === 0 && (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
                      <p className="text-[12px] font-semibold text-amber-900">まだ分析値が入っていません</p>
                      <p className="mt-1 text-[11px] leading-5 text-amber-800">
                        いま見えているLPは一覧登録だけで、品質/CV力がまだ算出されていない可能性があります。まず新しいLP URLで1本分析して、詳細カードの内容が出るか確認してください。
                      </p>
                    </div>
                  )}

                  {/* Genre filter */}
                  <div className="mb-3 flex flex-wrap items-center gap-2">
                    <select
                      className="select-filter text-xs"
                      value={selectedGenre}
                      onChange={(e) => setSelectedGenre(e.target.value)}
                    >
                    <option value="all">全ジャンル</option>
                    {GENRE_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
                    </select>
                    <span className="text-[11px] text-gray-400">
                      {lpsLoading ? "読み込み中..." : `${visibleLPs.length}件を表示 / 全${lps.length}件`}
                    </span>
                    <label className="ml-auto inline-flex cursor-pointer items-center gap-2 rounded-full border border-[#dbe6ff] bg-white px-3 py-1.5 text-[11px] text-gray-700">
                      <input
                        type="checkbox"
                        className="h-3.5 w-3.5 accent-[#4A7DFF]"
                        checked={showOnlyAnalyzed}
                        onChange={(e) => setShowOnlyAnalyzed(e.target.checked)}
                      />
                      分析済みのみ表示
                    </label>
                  </div>

                {lpsLoading && (
                  <div className="flex items-center justify-center py-8">
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
                    <span className="ml-2 text-xs text-gray-400">読み込み中...</span>
                  </div>
                )}

                {!lpsLoading && lps.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-gray-300 bg-white px-6 py-12 text-center text-gray-400">
                    <p className="text-sm font-semibold text-gray-800">LP分析データがまだありません</p>
                    <p className="mt-2 text-[11px] leading-5 text-gray-500">
                      まずは競合LPを1本入れて分析します。URLを入れて `分析開始` を押すと、ここにカードが追加されます。
                    </p>
                    <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                      <button
                        type="button"
                        onClick={() => setActiveTab("own-lp")}
                        className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] font-medium text-gray-700 hover:bg-gray-100"
                      >
                        自社LPを先に登録する
                      </button>
                      <button
                        type="button"
                        onClick={() => setActiveTab("usp-flow")}
                        className="rounded-lg border border-[#c8d8ff] bg-[#eef4ff] px-3 py-2 text-[11px] font-medium text-[#4A7DFF] hover:bg-[#e5eeff]"
                      >
                        USP設計だけ試す
                      </button>
                    </div>
                  </div>
                )}

                {!lpsLoading && lps.length > 0 && visibleLPs.length === 0 && (
                  <div className="rounded-2xl border border-dashed border-amber-300 bg-amber-50 px-6 py-10 text-center">
                    <p className="text-sm font-semibold text-amber-900">表示中の分析済みLPがありません</p>
                    <p className="mt-2 text-[11px] leading-5 text-amber-800">
                      現在のジャンルでは未分析LPだけが登録されています。`分析済みのみ表示` をOFFにするか、新しいURLで分析してください。
                    </p>
                  </div>
                )}

                {visibleLPs.map((lp) => (
                  <div
                    key={lp.id}
                    onClick={() => setSelectedLP(lp)}
                    className={`card cursor-pointer transition-shadow hover:shadow-md ${
                      selectedLP?.id === lp.id ? "ring-2 ring-[#4A7DFF]" : ""
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {isLPAnalyzed(lp) ? (
                        <div className="flex gap-2 shrink-0">
                          <ScoreCircle score={lp.qualityScore} label="品質" />
                          <ScoreCircle score={lp.conversionScore} label="CV力" color="#10b981" />
                        </div>
                      ) : (
                        <div className="shrink-0 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-center">
                          <p className="text-[10px] font-semibold text-amber-900">未分析</p>
                          <p className="mt-1 text-[9px] text-amber-700">URLを再分析して詳細化</p>
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`badge text-[9px] ${
                            lp.lpType === "記事LP" ? "bg-purple-100 text-purple-700" : "bg-emerald-100 text-emerald-700"
                          }`}>{lp.lpType}</span>
                          <span className="badge-blue text-[9px]">{lp.genre}</span>
                          {!isLPAnalyzed(lp) && (
                            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[9px] font-medium text-amber-800">
                              スコア未生成
                            </span>
                          )}
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
                  <div>
                    <h3 className="text-[13px] font-bold text-gray-900">{selectedLP.product || selectedLP.title || "LP詳細"}</h3>
                    <p className="mt-1 text-[10px] text-gray-400">{selectedLP.domain} {selectedLP.advertiser ? `· ${selectedLP.advertiser}` : ""}</p>
                  </div>
                  <button onClick={() => setSelectedLP(null)} className="text-gray-400 hover:text-gray-600">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                <div className="rounded-2xl border border-gray-200 bg-white p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {selectedLP.lpType && (
                      <span className={`badge text-[9px] ${
                        selectedLP.lpType === "記事LP" ? "bg-purple-100 text-purple-700" : "bg-emerald-100 text-emerald-700"
                      }`}>
                        {selectedLP.lpType}
                      </span>
                    )}
                    {selectedLP.genre && <span className="badge-blue text-[9px]">{selectedLP.genre}</span>}
                    {!isLPAnalyzed(selectedLP) && (
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[9px] font-medium text-amber-800">未分析</span>
                    )}
                  </div>
                  <p className="mt-3 text-[14px] font-bold leading-relaxed text-gray-900">
                    {selectedLP.title || selectedLP.heroHeadline || "タイトル情報はまだ取得されていません"}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-[10px] text-gray-500">
                    {selectedLP.ctaCount > 0 && <span className="rounded-full bg-gray-100 px-2 py-1">CTA {selectedLP.ctaCount}</span>}
                    {selectedLP.testimonialCount > 0 && <span className="rounded-full bg-gray-100 px-2 py-1">口コミ {selectedLP.testimonialCount}</span>}
                    {selectedLP.wordCount > 0 && <span className="rounded-full bg-gray-100 px-2 py-1">{(selectedLP.wordCount / 1000).toFixed(1)}k文字</span>}
                    {selectedLP.hasPricing && selectedLP.priceText && <span className="rounded-full bg-orange-50 px-2 py-1 text-orange-700">{selectedLP.priceText}</span>}
                  </div>
                </div>
                {selectedLP.heroHeadline && (
                  <div className="card bg-gradient-to-r from-blue-50 to-purple-50">
                    <p className="text-[10px] text-gray-400 font-medium mb-1">ヒーロー見出し</p>
                    <p className="text-[14px] font-bold text-gray-900 leading-relaxed">{selectedLP.heroHeadline}</p>
                  </div>
                )}
                {!isLPAnalyzed(selectedLP) && (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
                    <p className="text-[12px] font-semibold text-amber-900">このLPはまだ十分に分析されていません</p>
                    <p className="mt-1 text-[11px] leading-5 text-amber-800">
                      一覧には登録されていますが、品質・CV力などのスコアが未生成です。上部URL欄から再度 `分析開始` したLPを優先して使ってください。
                    </p>
                  </div>
                )}
                {isLPAnalyzed(selectedLP) && (
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
                )}
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
                {GENRE_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
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

            {!competitorLoading && !hasEnoughCompetitorData && (
              <div className="rounded-2xl border border-dashed border-amber-300 bg-amber-50 px-6 py-10 text-center">
                <p className="text-sm font-semibold text-amber-900">競合傾向を出すには分析済みLPがまだ足りません</p>
                <p className="mt-2 text-[11px] leading-5 text-amber-800">
                  先に `LP一覧・分析` で競合LPを3件以上分析してください。件数が増えると、訴求軸の偏りやUSPの共通点が意味を持ちます。
                </p>
                <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                  <button
                    type="button"
                    onClick={() => setActiveTab("list")}
                    className="rounded-lg border border-[#c8d8ff] bg-white px-3 py-2 text-[11px] font-medium text-[#4A7DFF] hover:bg-[#eef4ff]"
                  >
                    競合LPを分析する
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab("usp-flow")}
                    className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] font-medium text-gray-700 hover:bg-gray-100"
                  >
                    先にUSP設計へ進む
                  </button>
                </div>
              </div>
            )}

            {hasEnoughCompetitorData && appealDistribution.length > 0 && (
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

            {hasEnoughCompetitorData && commonUSPs.length > 0 && (
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
                      <label htmlFor="own-lp-label" className="text-[10px] text-gray-500 font-medium">管理ラベル</label>
                      <input id="own-lp-label" className="input text-xs mt-1 w-full" placeholder="例: セラムV3_記事LP_A案" value={importLabel} onChange={(e) => setImportLabel(e.target.value)} />
                    </div>
                    <div>
                      <label htmlFor="own-lp-genre" className="text-[10px] text-gray-500 font-medium">ジャンル</label>
                      <select id="own-lp-genre" className="select-filter w-full mt-1 text-xs" value={importGenre} onChange={(e) => setImportGenre(e.target.value)}>
                        {GENRE_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label htmlFor="own-lp-product" className="text-[10px] text-gray-500 font-medium">商品名</label>
                      <input id="own-lp-product" className="input text-xs mt-1 w-full" placeholder="例: スキンケアセラムV3" value={importProduct} onChange={(e) => setImportProduct(e.target.value)} />
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
                    <input id="own-lp-content-url" type="url" aria-label="自社LP URL" className="input text-xs w-full" placeholder="https://your-lp.example.com/article-lp" value={importContent} onChange={(e) => setImportContent(e.target.value)} />
                  ) : (
                    <textarea id="own-lp-content-text" aria-label={importMethod === "html" ? "自社LP HTML" : "自社LPテキスト本文"} className="input text-xs w-full h-24 resize-y" placeholder={importMethod === "html" ? "<html>...</html>" : "記事LPのテキスト本文を貼り付け..."} value={importContent} onChange={(e) => setImportContent(e.target.value)} />
                  )}
                  <button type="button" className="btn-primary text-xs mt-3" onClick={handleImport} disabled={importLoading}>
                    <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                    </svg>
                    {importLoading ? "取り込み中..." : "取り込み開始"}
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
                    <div className="rounded-2xl border border-dashed border-gray-300 bg-white px-5 py-8 text-center text-gray-400">
                      <p className="text-xs font-semibold text-gray-800">自社LPがまだ登録されていません</p>
                      <p className="mt-1 text-[10px] leading-5 text-gray-500">
                        URL、HTML、本文のどれでも登録できます。比較したいLP本文があるなら `テキスト` が最短です。
                      </p>
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
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2">
                <div>
                  <p className="text-[11px] font-semibold text-gray-900">迷ったらサンプルで試す</p>
                  <p className="text-[10px] text-gray-500">入力例を入れて、そのまま生成結果の形を確認できます。</p>
                </div>
                <button
                  type="button"
                  onClick={fillUSPSample}
                  className="rounded-lg border border-[#c8d8ff] bg-white px-3 py-2 text-[11px] font-medium text-[#4A7DFF] hover:bg-[#eef4ff]"
                >
                  サンプル入力を入れる
                </button>
              </div>
              <form onSubmit={(e) => {
                e.preventDefault();
                handleGenerateUSPFlow(
                  uspProduct,
                  uspDescription,
                  uspTarget,
                  uspGenre,
                );
              }}>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                      <label htmlFor="usp-product" className="text-[10px] text-gray-500 font-medium">商品名</label>
                      <input
                        id="usp-product"
                        name="product"
                        className="input text-xs mt-1"
                        required
                      value={uspProduct}
                      onChange={(e) => setUSPProduct(e.target.value)}
                    />
                  </div>
                  <div>
                      <label htmlFor="usp-genre" className="text-[10px] text-gray-500 font-medium">ジャンル</label>
                      <select
                        id="usp-genre"
                        name="genre"
                        className="select-filter w-full mt-1 text-xs"
                        value={uspGenre}
                      onChange={(e) => setUSPGenre(e.target.value)}
                    >
                      {GENRE_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
                    </select>
                  </div>
                  <div>
                      <label htmlFor="usp-target" className="text-[10px] text-gray-500 font-medium">ターゲット</label>
                      <input
                        id="usp-target"
                        name="target"
                        className="input text-xs mt-1"
                        required
                      value={uspTarget}
                      onChange={(e) => setUSPTarget(e.target.value)}
                    />
                  </div>
                  <div>
                      <label htmlFor="usp-description" className="text-[10px] text-gray-500 font-medium">商品説明</label>
                      <input
                        id="usp-description"
                        name="description"
                        className="input text-xs mt-1"
                        required
                      value={uspDescription}
                      onChange={(e) => setUSPDescription(e.target.value)}
                    />
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
                <p className="text-xs font-semibold text-gray-800">商品情報を入力して、先に叩き台を作れます</p>
                <p className="mt-1 text-[10px] leading-5 text-gray-500">
                  競合データがなくても生成できます。後で `LP一覧・分析` や `競合訴求パターン` の結果を見て微調整してください。
                </p>
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
                    {Boolean((uspFlow as Record<string, unknown>).appealAxis) && (
                      <p className="text-[11px] text-gray-600">
                        推奨訴求軸: <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[String((uspFlow as Record<string, unknown>).appealAxis)] || "bg-gray-500"}`}>
                          {appealAxisLabels[String((uspFlow as Record<string, unknown>).appealAxis)] || String((uspFlow as Record<string, unknown>).appealAxis)}
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
