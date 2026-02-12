"use client";

import { useState } from "react";

type LPTab = "list" | "competitor" | "usp-flow" | "own-lp";

// ===== Mock Data =====

interface MockLP {
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

const mockLPs: MockLP[] = [
  {
    id: 1, url: "https://lp.example.com/serum-v3", domain: "lp.example.com",
    title: "【医師監修】話題の美容セラムが初回980円", lpType: "記事LP", genre: "美容・コスメ",
    advertiser: "ビューティーラボ", product: "スキンケアセラムV3",
    qualityScore: 88, conversionScore: 85, trustScore: 90, primaryAppeal: "authority", secondaryAppeal: "social_proof",
    ctaCount: 6, testimonialCount: 8, wordCount: 12000, hasPricing: true, priceText: "初回980円",
    heroHeadline: "たった14日で実感。医師監修の最先端美容セラム", status: "completed", analyzedAt: "2025-12-20",
  },
  {
    id: 2, url: "https://lp.example.com/diet-x", domain: "lp.example.com",
    title: "1ヶ月で-5kg!?話題のダイエットサプリ", lpType: "記事LP", genre: "健康食品",
    advertiser: "ヘルスケアジャパン", product: "ダイエットサプリメントX",
    qualityScore: 75, conversionScore: 78, trustScore: 65, primaryAppeal: "benefit", secondaryAppeal: "urgency",
    ctaCount: 4, testimonialCount: 5, wordCount: 8500, hasPricing: true, priceText: "初回500円",
    heroHeadline: "食事制限なし！飲むだけカンタンダイエット", status: "completed", analyzedAt: "2025-12-21",
  },
  {
    id: 3, url: "https://lp.example.com/tonic-pro", domain: "lp.example.com",
    title: "薄毛の悩みに。特許成分配合の育毛トニック", lpType: "記事LP", genre: "ヘアケア",
    advertiser: "ヘアケアプロ", product: "育毛トニックPRO",
    qualityScore: 82, conversionScore: 80, trustScore: 85, primaryAppeal: "problem_solution", secondaryAppeal: "authority",
    ctaCount: 5, testimonialCount: 6, wordCount: 15000, hasPricing: true, priceText: "定期3,980円",
    heroHeadline: "まだ間に合う。特許成分が毛根に届く", status: "completed", analyzedAt: "2025-12-19",
  },
  {
    id: 4, url: "https://lp.example.com/eyecream", domain: "lp.example.com",
    title: "目元-10歳。口コミで話題のアイクリーム", lpType: "記事LP", genre: "美容・コスメ",
    advertiser: "コスメティックス", product: "アイクリームモイスト",
    qualityScore: 79, conversionScore: 76, trustScore: 72, primaryAppeal: "social_proof", secondaryAppeal: "emotional",
    ctaCount: 5, testimonialCount: 12, wordCount: 10000, hasPricing: true, priceText: "初回1,980円",
    heroHeadline: "30代からの目元ケア。92%が実感した潤い", status: "completed", analyzedAt: "2025-12-22",
  },
  {
    id: 5, url: "https://shop.example.com/fit-bar", domain: "shop.example.com",
    title: "プロテインバーFIT - 公式サイト", lpType: "EC直接", genre: "健康食品",
    advertiser: "フィットネスフーズ", product: "プロテインバーFIT",
    qualityScore: 70, conversionScore: 72, trustScore: 68, primaryAppeal: "benefit", secondaryAppeal: "price",
    ctaCount: 3, testimonialCount: 3, wordCount: 4500, hasPricing: true, priceText: "1本280円",
    heroHeadline: "おいしく、強く。タンパク質20g配合", status: "completed", analyzedAt: "2025-12-23",
  },
];

// Mock competitor appeal distribution
const mockAppealDistribution = [
  { axis: "benefit", avgStrength: 82, count: 15, samples: ["効果を実感した方92%", "たった14日で変化を実感"] },
  { axis: "social_proof", avgStrength: 75, count: 13, samples: ["累計100万個突破", "口コミ評価4.8"] },
  { axis: "authority", avgStrength: 71, count: 11, samples: ["医師監修", "特許取得成分配合"] },
  { axis: "urgency", avgStrength: 65, count: 10, samples: ["今だけ初回980円", "先着500名限定"] },
  { axis: "price", avgStrength: 60, count: 9, samples: ["初回80%OFF", "送料無料"] },
  { axis: "problem_solution", avgStrength: 58, count: 8, samples: ["こんなお悩みありませんか？", "なぜ解決できないのか"] },
  { axis: "emotional", avgStrength: 45, count: 6, samples: ["自信を取り戻す", "笑顔の毎日へ"] },
  { axis: "fear", avgStrength: 38, count: 4, samples: ["放置すると悪化", "このまま何もしないと"] },
  { axis: "comparison", avgStrength: 35, count: 3, samples: ["他社製品との違い", "従来品の3倍の浸透力"] },
  { axis: "novelty", avgStrength: 30, count: 2, samples: ["日本初の特許技術", "業界初の配合"] },
];

// Mock USP flow recommendation
const mockUSPFlow = {
  primaryUSP: "独自の浸透技術による即効性",
  appealAxis: "authority",
  structure: [
    { section: "フック（問題提起）", purpose: "読者の注意を引き悩みに共感", guide: "30-40代女性の肌悩みを具体的に描写", technique: "問題共感型フック" },
    { section: "原因の深掘り", purpose: "なぜ既存の方法では解決できないか", guide: "従来のスキンケアの限界を指摘", technique: "教育・啓蒙" },
    { section: "解決策（USP提示）", purpose: "商品を解決策として自然に紹介", guide: "独自浸透技術のメカニズム解説", technique: "権威性×ベネフィット" },
    { section: "エビデンス", purpose: "信頼性を数値で裏付け", guide: "臨床試験結果、医師コメント、特許情報", technique: "権威性訴求" },
    { section: "体験談", purpose: "同じ悩みの人の成功体験", guide: "年代別・悩み別の体験談4-6件", technique: "社会的証明" },
    { section: "比較優位性", purpose: "競合との差別化を可視化", guide: "成分量・浸透力・コスパの比較表", technique: "比較訴求" },
    { section: "オファー/CTA", purpose: "購入の最終後押し", guide: "初回特別価格+返金保証+期間限定特典", technique: "緊急性+価格訴求" },
  ],
  headlines: [
    "【皮膚科医が注目】40代の肌悩みに終止符を打つ、浸透力3倍の美容セラム",
    "「もう何を使っても無駄…」そんなあなたに。医師監修の最先端美容セラムの秘密",
    "92%が14日で実感。特許浸透技術が叶える、本気のエイジングケア",
  ],
  gaps: [
    "長期使用の効果推移データを示すLPが少ない",
    "成分の科学的根拠を詳しく説明するLPがほぼない",
    "動画体験談を活用しているLPが少ない",
    "返金保証の具体的条件を明示するLPが少ない",
  ],
  differentiation: [
    "臨床試験データの詳細開示",
    "動画で使用感を伝える新しいLP形式",
    "成分の浸透メカニズムを図解で分かりやすく解説",
  ],
};

// Common USP categories
const mockCommonUSPs = [
  { category: "efficacy", count: 14, prominence: 85, keywords: ["実感", "効果", "変化", "改善"] },
  { category: "authority", count: 11, prominence: 78, keywords: ["医師監修", "特許", "臨床試験", "研究"] },
  { category: "price", count: 10, prominence: 72, keywords: ["初回", "特別価格", "送料無料", "返金保証"] },
  { category: "ingredient", count: 8, prominence: 68, keywords: ["独自成分", "天然由来", "配合", "濃度"] },
  { category: "uniqueness", count: 5, prominence: 60, keywords: ["日本初", "独自技術", "特許", "業界初"] },
];

// Mock own LPs
interface MockOwnLP {
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

const mockOwnLPs: MockOwnLP[] = [
  {
    id: 101, label: "セラムV3_記事LP_A案", version: 3, genre: "美容・コスメ", product: "スキンケアセラムV3",
    qualityScore: 82, conversionScore: 78, trustScore: 85, competitorCount: 12, avgCompetitorQuality: 76,
    status: "completed", createdAt: "2025-12-15",
  },
  {
    id: 102, label: "セラムV3_記事LP_B案", version: 1, genre: "美容・コスメ", product: "スキンケアセラムV3",
    qualityScore: 75, conversionScore: 80, trustScore: 72, competitorCount: 12, avgCompetitorQuality: 76,
    status: "completed", createdAt: "2025-12-18",
  },
  {
    id: 103, label: "ダイエットX_LP_v2", version: 2, genre: "健康食品", product: "ダイエットサプリメントX",
    qualityScore: 70, conversionScore: 68, trustScore: 65, competitorCount: 8, avgCompetitorQuality: 72,
    status: "completed", createdAt: "2025-12-20",
  },
];

// Mock comparison result
const mockCompareResult = {
  competitorCount: 12,
  scores: [
    { label: "品質スコア", own: 82, comp: 76, color: "#4A7DFF" },
    { label: "CV力", own: 78, comp: 74, color: "#10b981" },
    { label: "信頼性", own: 85, comp: 71, color: "#f59e0b" },
  ],
  appealComparison: [
    { axis: "authority", own: 85, comp: 71, gap: 14 },
    { axis: "social_proof", own: 72, comp: 75, gap: -3 },
    { axis: "benefit", own: 68, comp: 82, gap: -14 },
    { axis: "urgency", own: 55, comp: 65, gap: -10 },
    { axis: "price", own: 60, comp: 58, gap: 2 },
    { axis: "emotional", own: 45, comp: 40, gap: 5 },
  ],
  missingUSPs: ["速度・即効性", "利便性"],
  strengths: [
    "権威性（医師監修）の訴求が競合平均を大きく上回る",
    "信頼性スコアがジャンル内トップクラス",
    "価格訴求のバランスが良い",
  ],
  improvements: [
    "ベネフィット訴求を強化する余地がある（競合平均-14pt）",
    "緊急性の演出が競合より弱い",
    "社会的証明（口コミ・実績数）をもっと前面に出す",
  ],
  quickWins: [
    "競合が使用している「即効性」のUSPを追加",
    "口コミ件数を具体的な数字で表示（例: 12,345件の口コミ）",
    "期間限定オファーのカウントダウンを追加",
  ],
};

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
  const [selectedGenre, setSelectedGenre] = useState("美容・コスメ");
  const [crawlUrl, setCrawlUrl] = useState("");
  const [selectedLP, setSelectedLP] = useState<MockLP | null>(null);

  // Own LP state
  const [selectedOwnLP, setSelectedOwnLP] = useState<MockOwnLP | null>(null);
  const [showCompare, setShowCompare] = useState(false);
  const [importMethod, setImportMethod] = useState<ImportMethod>("url");
  const [importLabel, setImportLabel] = useState("");
  const [importGenre, setImportGenre] = useState("美容・コスメ");
  const [importProduct, setImportProduct] = useState("");
  const [importContent, setImportContent] = useState("");

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
          {/* URL Input for crawling */}
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
              onClick={() => { /* Would call lpAnalysisApi.crawl */ setCrawlUrl(""); }}
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
                  <span className="text-[11px] text-gray-400">{mockLPs.length}件のLP</span>
                </div>

                {mockLPs.map((lp) => (
                  <div
                    key={lp.id}
                    onClick={() => setSelectedLP(lp)}
                    className={`card cursor-pointer transition-shadow hover:shadow-md ${
                      selectedLP?.id === lp.id ? "ring-2 ring-[#4A7DFF]" : ""
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {/* Scores */}
                      <div className="flex gap-2 shrink-0">
                        <ScoreCircle score={lp.qualityScore} label="品質" />
                        <ScoreCircle score={lp.conversionScore} label="CV力" color="#10b981" />
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`badge text-[9px] ${
                            lp.lpType === "記事LP" ? "bg-purple-100 text-purple-700" : "bg-emerald-100 text-emerald-700"
                          }`}>{lp.lpType}</span>
                          <span className="badge-blue text-[9px]">{lp.genre}</span>
                        </div>
                        <p className="text-[12px] font-medium text-gray-900 truncate">{lp.title}</p>
                        <p className="text-[10px] text-gray-400 truncate mt-0.5">{lp.domain} · {lp.advertiser}</p>

                        {/* Appeal axes */}
                        <div className="flex items-center gap-1.5 mt-2">
                          <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[lp.primaryAppeal]}`}>
                            {appealAxisLabels[lp.primaryAppeal]}
                          </span>
                          <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium text-white/90 ${appealAxisColors[lp.secondaryAppeal]}`}>
                            {appealAxisLabels[lp.secondaryAppeal]}
                          </span>
                        </div>

                        {/* Metrics row */}
                        <div className="flex items-center gap-3 mt-2 text-[10px] text-gray-500">
                          <span>CTA×{lp.ctaCount}</span>
                          <span>口コミ×{lp.testimonialCount}</span>
                          <span>{(lp.wordCount / 1000).toFixed(1)}k文字</span>
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

                {/* Hero headline */}
                <div className="card bg-gradient-to-r from-blue-50 to-purple-50">
                  <p className="text-[10px] text-gray-400 font-medium mb-1">ヒーロー見出し</p>
                  <p className="text-[14px] font-bold text-gray-900 leading-relaxed">
                    {selectedLP.heroHeadline}
                  </p>
                </div>

                {/* Score grid */}
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

                {/* Page flow */}
                <div className="card">
                  <h4 className="text-[12px] font-bold text-gray-900 mb-2">ページ構成フロー</h4>
                  <div className="flex items-center flex-wrap gap-1">
                    {["hero", "problem", "solution", "authority", "testimonial", "comparison", "pricing", "cta"].map((section, i) => (
                      <div key={section} className="flex items-center">
                        <span className="rounded bg-gray-100 px-2 py-1 text-[10px] font-medium text-gray-700">
                          {section}
                        </span>
                        {i < 7 && <span className="text-gray-300 mx-0.5">→</span>}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Appeal axes detail */}
                <div className="card">
                  <h4 className="text-[12px] font-bold text-gray-900 mb-2">訴求軸</h4>
                  <div className="space-y-2">
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[selectedLP.primaryAppeal]}`}>
                          主訴求: {appealAxisLabels[selectedLP.primaryAppeal]}
                        </span>
                        <span className="text-[10px] text-gray-500">強度 85/100</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${appealAxisColors[selectedLP.primaryAppeal]}`} style={{ width: "85%" }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[selectedLP.secondaryAppeal]}`}>
                          副訴求: {appealAxisLabels[selectedLP.secondaryAppeal]}
                        </span>
                        <span className="text-[10px] text-gray-500">強度 62/100</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${appealAxisColors[selectedLP.secondaryAppeal]}`} style={{ width: "62%" }} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* USPs */}
                <div className="card">
                  <h4 className="text-[12px] font-bold text-gray-900 mb-2">USP（独自の売り）</h4>
                  <div className="space-y-2">
                    {[
                      { category: "authority", text: "皮膚科医監修の高濃度美容セラム", prominence: 90 },
                      { category: "efficacy", text: "92%が14日で肌変化を実感", prominence: 85 },
                      { category: "ingredient", text: "特許取得の浸透技術「ナノデリバリー」", prominence: 75 },
                    ].map((usp, i) => (
                      <div key={i} className="flex items-start gap-2 p-2 bg-gray-50 rounded-lg">
                        <span className="badge text-[8px] bg-gray-200 text-gray-600 shrink-0 mt-0.5">
                          {uspCategoryLabels[usp.category] || usp.category}
                        </span>
                        <div className="flex-1">
                          <p className="text-[11px] text-gray-800">{usp.text}</p>
                          <div className="flex items-center gap-1 mt-1">
                            <div className="w-16 h-1 bg-gray-200 rounded-full overflow-hidden">
                              <div className="h-full rounded-full bg-[#4A7DFF]" style={{ width: `${usp.prominence}%` }} />
                            </div>
                            <span className="text-[9px] text-gray-400">重要度 {usp.prominence}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* LP URL */}
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
            {/* Genre selector */}
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
              <span className="text-[11px] text-gray-400">ジャンル内 {mockLPs.length} LPの分析データ</span>
            </div>

            {/* Appeal distribution */}
            <div className="card">
              <h3 className="text-[13px] font-bold text-gray-900 mb-3">訴求軸の使用状況（競合LP横断分析）</h3>
              <p className="text-[11px] text-gray-500 mb-4">
                このジャンルの競合LPがどの訴求軸をどれくらいの強度で使用しているかを可視化します。
                使用率が高い = 効果実証済みの手法。使用率が低い = 差別化の機会。
              </p>
              <div className="space-y-3">
                {mockAppealDistribution.map((item) => (
                  <div key={item.axis}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[item.axis]}`}>
                          {appealAxisLabels[item.axis]}
                        </span>
                        <span className="text-[10px] text-gray-500">{item.count}件のLPで使用</span>
                      </div>
                      <span className="text-[12px] font-semibold text-gray-700">{item.avgStrength}</span>
                    </div>
                    <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${appealAxisColors[item.axis]} transition-all`}
                        style={{ width: `${item.avgStrength}%` }}
                      />
                    </div>
                    <div className="flex gap-2 mt-1">
                      {item.samples.map((s, i) => (
                        <span key={i} className="text-[9px] text-gray-400 italic">「{s}」</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Common USPs */}
            <div className="card">
              <h3 className="text-[13px] font-bold text-gray-900 mb-3">よく使われるUSPカテゴリ</h3>
              <div className="grid grid-cols-2 gap-3">
                {mockCommonUSPs.map((usp) => (
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

            {/* Target personas */}
            <div className="card">
              <h3 className="text-[13px] font-bold text-gray-900 mb-3">ターゲットペルソナ分布</h3>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { gender: "女性", age: "30-40代", concerns: ["シミ・くすみ", "たるみ", "乾燥"], count: 8 },
                  { gender: "女性", age: "20-30代", concerns: ["毛穴", "ニキビ跡", "肌荒れ"], count: 4 },
                  { gender: "男性", age: "30-40代", concerns: ["薄毛", "頭皮ケア", "加齢臭"], count: 3 },
                ].map((p, i) => (
                  <div key={i} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-[11px] font-bold text-gray-800">{p.gender} {p.age}</span>
                      <span className="text-[9px] text-gray-400">({p.count}LP)</span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {p.concerns.map((c) => (
                        <span key={c} className="rounded bg-blue-50 px-1.5 py-0.5 text-[9px] text-blue-700">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "own-lp" && (
          <div className="flex h-full">
            {/* Left: Import + Own LP List */}
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
                      <input
                        className="input text-xs mt-1 w-full"
                        placeholder="例: セラムV3_記事LP_A案"
                        value={importLabel}
                        onChange={(e) => setImportLabel(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-gray-500 font-medium">ジャンル</label>
                      <select
                        className="select-filter w-full mt-1 text-xs"
                        value={importGenre}
                        onChange={(e) => setImportGenre(e.target.value)}
                      >
                        <option>美容・コスメ</option>
                        <option>健康食品</option>
                        <option>ヘアケア</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] text-gray-500 font-medium">商品名</label>
                      <input
                        className="input text-xs mt-1 w-full"
                        placeholder="例: スキンケアセラムV3"
                        value={importProduct}
                        onChange={(e) => setImportProduct(e.target.value)}
                      />
                    </div>
                  </div>

                  {/* Input method tabs */}
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
                          importMethod === m.id
                            ? "bg-[#4A7DFF] text-white"
                            : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                        }`}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>

                  {importMethod === "url" ? (
                    <input
                      className="input text-xs w-full"
                      placeholder="https://your-lp.example.com/article-lp"
                      value={importContent}
                      onChange={(e) => setImportContent(e.target.value)}
                    />
                  ) : (
                    <textarea
                      className="input text-xs w-full h-24 resize-y"
                      placeholder={importMethod === "html" ? "<html>...</html>" : "記事LPのテキスト本文を貼り付け..."}
                      value={importContent}
                      onChange={(e) => setImportContent(e.target.value)}
                    />
                  )}

                  <button
                    className="btn-primary text-xs mt-3"
                    onClick={() => { setImportLabel(""); setImportProduct(""); setImportContent(""); }}
                  >
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
                    <span className="text-[11px] text-gray-400">{mockOwnLPs.length}件</span>
                  </div>

                  <div className="space-y-2">
                    {mockOwnLPs.map((lp) => {
                      const qualityDiff = lp.qualityScore - lp.avgCompetitorQuality;
                      return (
                        <div
                          key={lp.id}
                          onClick={() => { setSelectedOwnLP(lp); setShowCompare(true); }}
                          className={`card cursor-pointer transition-shadow hover:shadow-md ${
                            selectedOwnLP?.id === lp.id ? "ring-2 ring-[#4A7DFF]" : ""
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            {/* Score */}
                            <div className="flex gap-2 shrink-0">
                              <ScoreCircle score={lp.qualityScore} label="品質" />
                              <ScoreCircle score={lp.conversionScore} label="CV力" color="#10b981" />
                            </div>

                            {/* Info */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="badge text-[9px] bg-indigo-100 text-indigo-700">自社LP</span>
                                <span className="badge-blue text-[9px]">{lp.genre}</span>
                                <span className="text-[9px] text-gray-400">v{lp.version}</span>
                              </div>
                              <p className="text-[12px] font-medium text-gray-900 truncate">{lp.label}</p>
                              <p className="text-[10px] text-gray-400 mt-0.5">{lp.product}</p>

                              {/* Competitor comparison hint */}
                              <div className="flex items-center gap-3 mt-2">
                                <span className="text-[10px] text-gray-500">
                                  競合 {lp.competitorCount}件
                                </span>
                                <span className={`text-[10px] font-medium ${qualityDiff >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                                  {qualityDiff >= 0 ? "▲" : "▼"} 競合平均比 {qualityDiff >= 0 ? "+" : ""}{qualityDiff}pt
                                </span>
                              </div>
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

                {/* Score Comparison Bars */}
                <div className="card">
                  <h4 className="text-[12px] font-bold text-gray-900 mb-3">スコア比較（自社 vs 競合平均）</h4>
                  <div className="space-y-3">
                    {mockCompareResult.scores.map((s) => (
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
                          <div
                            className="rounded-l-full h-full transition-all"
                            style={{ width: `${s.own}%`, backgroundColor: s.color }}
                          />
                          <div
                            className="rounded-r-full h-full bg-gray-300 transition-all"
                            style={{ width: `${s.comp}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-4 mt-3 text-[9px] text-gray-400">
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-[#4A7DFF]" /> 自社</span>
                    <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-gray-300" /> 競合平均</span>
                  </div>
                </div>

                {/* Appeal Axis Gap Chart */}
                <div className="card">
                  <h4 className="text-[12px] font-bold text-gray-900 mb-3">訴求軸ギャップ分析</h4>
                  <p className="text-[10px] text-gray-500 mb-3">
                    プラス = 競合より強い、マイナス = 競合より弱い（改善機会）
                  </p>
                  <div className="space-y-2">
                    {mockCompareResult.appealComparison.map((item) => {
                      const maxGap = 20;
                      const barWidth = Math.min(Math.abs(item.gap) / maxGap * 50, 50);
                      return (
                        <div key={item.axis} className="flex items-center gap-2">
                          <span className={`w-24 text-right text-[10px] font-medium ${appealAxisColors[item.axis] ? "text-gray-700" : "text-gray-500"}`}>
                            {appealAxisLabels[item.axis] || item.axis}
                          </span>
                          <div className="flex-1 flex items-center h-5">
                            {/* Center axis */}
                            <div className="w-1/2 flex justify-end">
                              {item.gap < 0 && (
                                <div
                                  className="h-4 rounded-l bg-red-400 transition-all"
                                  style={{ width: `${barWidth}%` }}
                                />
                              )}
                            </div>
                            <div className="w-px h-5 bg-gray-300 shrink-0" />
                            <div className="w-1/2">
                              {item.gap > 0 && (
                                <div
                                  className="h-4 rounded-r bg-emerald-400 transition-all"
                                  style={{ width: `${barWidth}%` }}
                                />
                              )}
                            </div>
                          </div>
                          <span className={`w-10 text-[10px] font-bold ${
                            item.gap > 0 ? "text-emerald-600" : item.gap < 0 ? "text-red-500" : "text-gray-400"
                          }`}>
                            {item.gap > 0 ? "+" : ""}{item.gap}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Missing USP Categories */}
                {mockCompareResult.missingUSPs.length > 0 && (
                  <div className="card bg-amber-50 border-amber-200">
                    <h4 className="text-[12px] font-bold text-amber-800 mb-2">不足しているUSPカテゴリ</h4>
                    <p className="text-[10px] text-amber-700 mb-2">競合が使用しているが自社LPに含まれていないUSP</p>
                    <div className="flex flex-wrap gap-1.5">
                      {mockCompareResult.missingUSPs.map((usp) => (
                        <span key={usp} className="rounded-full bg-amber-200 px-2.5 py-1 text-[10px] font-medium text-amber-800">
                          {usp}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* AI Recommendations */}
                <div className="card">
                  <h4 className="text-[12px] font-bold text-gray-900 mb-3">AI改善提案</h4>

                  {/* Strengths */}
                  <div className="mb-3">
                    <div className="flex items-center gap-1.5 mb-2">
                      <span className="w-4 h-4 rounded bg-emerald-100 flex items-center justify-center">
                        <svg className="w-3 h-3 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                      </span>
                      <span className="text-[11px] font-bold text-emerald-700">競合に対する強み</span>
                    </div>
                    <div className="space-y-1">
                      {mockCompareResult.strengths.map((s, i) => (
                        <div key={i} className="flex items-start gap-1.5 pl-5">
                          <span className="shrink-0 mt-1 w-1.5 h-1.5 rounded-full bg-emerald-400" />
                          <span className="text-[11px] text-gray-700">{s}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Improvement Opportunities */}
                  <div className="mb-3">
                    <div className="flex items-center gap-1.5 mb-2">
                      <span className="w-4 h-4 rounded bg-blue-100 flex items-center justify-center">
                        <svg className="w-3 h-3 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22" />
                        </svg>
                      </span>
                      <span className="text-[11px] font-bold text-blue-700">改善機会</span>
                    </div>
                    <div className="space-y-1">
                      {mockCompareResult.improvements.map((s, i) => (
                        <div key={i} className="flex items-start gap-1.5 pl-5">
                          <span className="shrink-0 mt-1 w-1.5 h-1.5 rounded-full bg-blue-400" />
                          <span className="text-[11px] text-gray-700">{s}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Quick Wins */}
                  <div>
                    <div className="flex items-center gap-1.5 mb-2">
                      <span className="w-4 h-4 rounded bg-amber-100 flex items-center justify-center">
                        <svg className="w-3 h-3 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                        </svg>
                      </span>
                      <span className="text-[11px] font-bold text-amber-700">すぐに実施できる改善</span>
                    </div>
                    <div className="space-y-1">
                      {mockCompareResult.quickWins.map((s, i) => (
                        <div key={i} className="flex items-start gap-1.5 pl-5">
                          <span className="shrink-0 mt-1 w-1.5 h-1.5 rounded-full bg-amber-400" />
                          <span className="text-[11px] text-gray-700">{s}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
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
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-gray-500 font-medium">商品名</label>
                  <input className="input text-xs mt-1" defaultValue="スキンケアセラムV3" />
                </div>
                <div>
                  <label className="text-[10px] text-gray-500 font-medium">ジャンル</label>
                  <select className="select-filter w-full mt-1 text-xs">
                    <option>美容・コスメ</option>
                    <option>健康食品</option>
                    <option>ヘアケア</option>
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-gray-500 font-medium">ターゲット</label>
                  <input className="input text-xs mt-1" defaultValue="30-40代女性、肌のエイジングケアに悩む" />
                </div>
                <div>
                  <label className="text-[10px] text-gray-500 font-medium">商品説明</label>
                  <input className="input text-xs mt-1" defaultValue="皮膚科医監修の高濃度ビタミンC美容液" />
                </div>
              </div>
              <button className="btn-primary text-xs mt-3">
                <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
                AIで導線設計を生成
              </button>
            </div>

            {/* USP Recommendation */}
            <div className="card bg-gradient-to-r from-blue-50 to-indigo-50">
              <div className="flex items-center gap-2 mb-2">
                <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
                <h3 className="text-[13px] font-bold text-gray-900">推奨USP</h3>
              </div>
              <p className="text-[14px] font-bold text-[#4A7DFF] mb-1">{mockUSPFlow.primaryUSP}</p>
              <p className="text-[11px] text-gray-600">
                推奨訴求軸: <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-medium text-white ${appealAxisColors[mockUSPFlow.appealAxis]}`}>
                  {appealAxisLabels[mockUSPFlow.appealAxis]}
                </span>
              </p>
            </div>

            {/* Article LP Structure - Flow visualization */}
            <div className="card">
              <h3 className="text-[13px] font-bold text-gray-900 mb-4">推奨 記事LP構成</h3>
              <div className="relative">
                {/* Vertical line */}
                <div className="absolute left-4 top-3 bottom-3 w-0.5 bg-gradient-to-b from-[#4A7DFF] to-purple-400" />

                <div className="space-y-4">
                  {mockUSPFlow.structure.map((section, i) => (
                    <div key={i} className="relative flex items-start gap-4 pl-10">
                      {/* Node */}
                      <div className={`absolute left-2 top-1 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white ${
                        i === 0 ? "bg-[#4A7DFF]" : i === mockUSPFlow.structure.length - 1 ? "bg-purple-500" : "bg-gray-400"
                      }`}>
                        {i + 1}
                      </div>

                      <div className="flex-1 p-3 bg-gray-50 rounded-lg hover:bg-blue-50/50 transition-colors">
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

            {/* Headline suggestions */}
            <div className="card">
              <h3 className="text-[13px] font-bold text-gray-900 mb-3">見出し案</h3>
              <div className="space-y-2">
                {mockUSPFlow.headlines.map((hl, i) => (
                  <div key={i} className="flex items-start gap-2 p-2 bg-gray-50 rounded-lg">
                    <span className="shrink-0 w-5 h-5 rounded bg-[#4A7DFF] text-white text-[10px] font-bold flex items-center justify-center">
                      {i + 1}
                    </span>
                    <p className="text-[12px] text-gray-800 font-medium leading-relaxed">{hl}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Competitor gaps & differentiation */}
            <div className="grid grid-cols-2 gap-3">
              <div className="card">
                <h3 className="text-[13px] font-bold text-gray-900 mb-2">競合の弱点・ギャップ</h3>
                <div className="space-y-1.5">
                  {mockUSPFlow.gaps.map((gap, i) => (
                    <div key={i} className="flex items-start gap-1.5">
                      <span className="shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full bg-red-400" />
                      <span className="text-[11px] text-gray-700">{gap}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="card">
                <h3 className="text-[13px] font-bold text-gray-900 mb-2">差別化ポイント</h3>
                <div className="space-y-1.5">
                  {mockUSPFlow.differentiation.map((diff, i) => (
                    <div key={i} className="flex items-start gap-1.5">
                      <span className="shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      <span className="text-[11px] text-gray-700">{diff}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
