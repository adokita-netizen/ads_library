"use client";

import { useState, useEffect } from "react";
import { adsApi, predictionsApi, lpAnalysisApi } from "@/lib/api";

interface ProductDetailModalProps {
  adId: number;
  onClose: () => void;
}

interface ProductData {
  id: number;
  managementId: string;
  productName: string;
  advertiserName: string;
  genre: string;
  totalSpend: number;
  totalPlays: number;
  publishedDate: string;
  duration: number;
  platforms: string[];
  destinationType: string;
  destination: string;
}

interface AnalysisData {
  ctr_prediction?: number;
  cvr_prediction?: number;
  winning_probability?: number;
  fatigue_score?: number;
  estimated_remaining_days?: number;
  hook_types?: string[];
  structure_type?: string;
  transcription?: string;
  scenes?: Array<Record<string, unknown>>;
}

interface LPAnalysisData {
  id: number;
  url: string;
  domain: string;
  title: string;
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
}

const platformLabels: Record<string, string> = {
  youtube: "YT", shorts: "S", tiktok: "TT", meta: "Meta", facebook: "FB",
  instagram: "IG", line: "L", yahoo: "Y!", x: "X", x_twitter: "X",
  pinterest: "Pin", smartnews: "SN", google_ads: "G", gunosy: "Gn",
};

const platformColors: Record<string, string> = {
  youtube: "platform-youtube", tiktok: "platform-tiktok",
  meta: "platform-meta", facebook: "platform-facebook", instagram: "platform-instagram",
  line: "platform-line", yahoo: "platform-yahoo", x: "platform-x", x_twitter: "platform-x",
  pinterest: "bg-red-600", smartnews: "bg-sky-600", google_ads: "bg-blue-500", gunosy: "bg-orange-500",
};

function formatYen(n: number): string {
  if (n >= 100000000) return "¥" + (n / 100000000).toFixed(1) + "億";
  if (n >= 10000) return "¥" + (n / 10000).toFixed(0) + "万";
  return "¥" + n.toLocaleString();
}

function formatNumber(n: number): string {
  if (n >= 100000000) return (n / 100000000).toFixed(1) + "億";
  if (n >= 10000) return (n / 10000).toFixed(0) + "万";
  return n.toLocaleString();
}

type TabType = "overview" | "creatives" | "competitors" | "analysis" | "lp-analysis";

export default function ProductDetailModal({ adId, onClose }: ProductDetailModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [product, setProduct] = useState<ProductData | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lpData, setLpData] = useState<LPAnalysisData | null>(null);
  const [lpAnalyzing, setLpAnalyzing] = useState(false);
  const [lpSearched, setLpSearched] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [adResponse, analysisResponse] = await Promise.allSettled([
          adsApi.get(adId),
          adsApi.getAnalysis(adId),
        ]);

        if (adResponse.status === "fulfilled" && adResponse.value.data) {
          const data = adResponse.value.data;
          setProduct({
            id: data.id || adId,
            managementId: data.external_id || data.management_id || `AD-${adId}`,
            productName: data.product_name || data.title || "",
            advertiserName: data.advertiser_name || "",
            genre: data.category || data.genre || "",
            totalSpend: data.cumulative_spend || data.total_spend || 0,
            totalPlays: data.view_count || data.cumulative_views || 0,
            publishedDate: data.published_date || data.created_at || "",
            duration: data.duration_seconds || data.duration || 0,
            platforms: data.platforms || [data.platform].filter(Boolean),
            destinationType: data.destination_type || "",
            destination: data.destination_url || data.destination || "",
          });
        }

        if (analysisResponse.status === "fulfilled" && analysisResponse.value.data) {
          setAnalysis(analysisResponse.value.data);
        }
      } catch (error) {
        console.error("Failed to fetch ad data:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [adId]);

  // Fetch existing LP analysis when LP tab is activated
  useEffect(() => {
    if (activeTab !== "lp-analysis" || !product?.destination || lpSearched) return;
    const fetchLPData = async () => {
      try {
        const response = await lpAnalysisApi.list({ url: product.destination });
        const data = response.data;
        const items = data?.landing_pages || data?.items || data?.results;
        if (Array.isArray(items) && items.length > 0) {
          const lp = items[0] as Record<string, unknown>;
          setLpData({
            id: (lp.id as number) || 0,
            url: (lp.url as string) || product.destination,
            domain: (lp.domain as string) || "",
            title: (lp.title as string) || "",
            qualityScore: (lp.quality_score as number) || 0,
            conversionScore: (lp.conversion_score as number) || 0,
            trustScore: (lp.trust_score as number) || 0,
            primaryAppeal: (lp.primary_appeal as string) || "",
            secondaryAppeal: (lp.secondary_appeal as string) || "",
            ctaCount: (lp.cta_count as number) || 0,
            testimonialCount: (lp.testimonial_count as number) || 0,
            wordCount: (lp.word_count as number) || 0,
            hasPricing: (lp.has_pricing as boolean) || false,
            priceText: (lp.price_text as string) || "",
            heroHeadline: (lp.hero_headline as string) || "",
            status: (lp.status as string) || "",
          });
        }
      } catch {
        // No existing analysis found - that's ok
      } finally {
        setLpSearched(true);
      }
    };
    fetchLPData();
  }, [activeTab, product?.destination, lpSearched]);

  const handleStartLPAnalysis = async () => {
    if (!product?.destination) return;
    setLpAnalyzing(true);
    try {
      await lpAnalysisApi.crawl({
        url: product.destination,
        ad_id: product.id,
        genre: product.genre || undefined,
        product_name: product.productName || undefined,
        advertiser_name: product.advertiserName || undefined,
        auto_analyze: true,
      });
      // After triggering, poll for results
      let attempts = 0;
      const poll = async () => {
        attempts++;
        try {
          const response = await lpAnalysisApi.list({ url: product.destination });
          const pollData = response.data;
          const items = pollData?.landing_pages || pollData?.items || pollData?.results;
          if (Array.isArray(items) && items.length > 0) {
            const lp = items[0] as Record<string, unknown>;
            const status = (lp.status as string) || "";
            if (status === "analyzed" || status === "completed" || (lp.quality_score as number) > 0) {
              setLpData({
                id: (lp.id as number) || 0,
                url: (lp.url as string) || product.destination,
                domain: (lp.domain as string) || "",
                title: (lp.title as string) || "",
                qualityScore: (lp.quality_score as number) || 0,
                conversionScore: (lp.conversion_score as number) || 0,
                trustScore: (lp.trust_score as number) || 0,
                primaryAppeal: (lp.primary_appeal as string) || "",
                secondaryAppeal: (lp.secondary_appeal as string) || "",
                ctaCount: (lp.cta_count as number) || 0,
                testimonialCount: (lp.testimonial_count as number) || 0,
                wordCount: (lp.word_count as number) || 0,
                hasPricing: (lp.has_pricing as boolean) || false,
                priceText: (lp.price_text as string) || "",
                heroHeadline: (lp.hero_headline as string) || "",
                status,
              });
              setLpAnalyzing(false);
              return;
            }
          }
        } catch {
          // Still processing
        }
        if (attempts < 15) {
          setTimeout(poll, 3000);
        } else {
          setLpAnalyzing(false);
        }
      };
      setTimeout(poll, 2000);
    } catch (error) {
      console.error("Failed to start LP analysis:", error);
      setLpAnalyzing(false);
    }
  };

  // Fetch predictions when analysis tab is activated
  useEffect(() => {
    if (activeTab !== "analysis" || !product || analysis?.ctr_prediction) return;
    const fetchPredictions = async () => {
      try {
        const response = await predictionsApi.predict({ ad_id: adId });
        if (response.data) {
          setAnalysis((prev) => prev ? { ...prev, ...response.data } : response.data);
        }
      } catch (error) {
        console.error("Failed to fetch predictions:", error);
      }
    };
    fetchPredictions();
  }, [activeTab, adId, product, analysis?.ctr_prediction]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-8 pb-8">
      <div className="relative w-full max-w-5xl max-h-full overflow-hidden rounded-xl bg-white shadow-2xl flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="w-16 h-10 rounded bg-gray-200 flex items-center justify-center">
              <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
              </svg>
            </div>
            <div>
              <h2 className="text-[15px] font-bold text-gray-900">
                {product?.productName || "読み込み中..."}
              </h2>
              <p className="text-[11px] text-gray-400">
                {product ? `${product.advertiserName} · ${product.managementId} · ${product.genre}` : ""}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button className="btn-secondary text-xs">
              <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
              </svg>
              マイリストに追加
            </button>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 px-6 border-b border-gray-200 bg-[#f8f9fc]">
          {([
            { id: "overview", label: "概要" },
            { id: "lp-analysis", label: "遷移先LP分析" },
            { id: "analysis", label: "AI分析" },
          ] as { id: TabType; label: string }[]).map((tab) => (
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

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
              <span className="ml-2 text-xs text-gray-400">読み込み中...</span>
            </div>
          )}

          {!loading && !product && (
            <div className="text-center py-12 text-gray-400">
              <p className="text-xs">広告データを取得できませんでした</p>
            </div>
          )}

          {!loading && product && activeTab === "overview" && (
            <div className="space-y-5">
              {/* Top Stats */}
              <div className="grid grid-cols-4 gap-3">
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium">累計予想消化額</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">{formatYen(product.totalSpend)}</p>
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium">累計再生回数</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">{formatNumber(product.totalPlays)}</p>
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium">出稿媒体数</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">{product.platforms.length}媒体</p>
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium">公開日</p>
                  <p className="text-lg font-bold text-gray-900 mt-1">{product.publishedDate}</p>
                </div>
              </div>

              {/* Platform breakdown */}
              <div className="card">
                <h3 className="text-[13px] font-bold text-gray-900 mb-3">出稿媒体</h3>
                <div className="flex items-center gap-2 flex-wrap">
                  {product.platforms.map((p) => (
                    <span key={p} className={`platform-icon ${platformColors[p] || "bg-gray-200"}`}>
                      {platformLabels[p] || p}
                    </span>
                  ))}
                </div>
              </div>

              {/* Destination */}
              {product.destination && (
                <div className="card">
                  <h3 className="text-[13px] font-bold text-gray-900 mb-2">遷移先</h3>
                  <div className="flex items-center gap-2">
                    {product.destinationType && (
                      <span className="badge text-[9px] bg-purple-100 text-purple-700">{product.destinationType}</span>
                    )}
                    <a href={product.destination} target="_blank" rel="noopener noreferrer" className="text-[11px] text-[#4A7DFF] hover:underline break-all">
                      {product.destination}
                    </a>
                  </div>
                </div>
              )}
            </div>
          )}

          {!loading && product && activeTab === "lp-analysis" && (
            <div className="space-y-4">
              {product.destination ? (
                <>
                  {/* Destination URL info */}
                  <div className="card bg-gradient-to-r from-purple-50 to-blue-50">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          {product.destinationType && (
                            <span className="badge text-[9px] bg-purple-100 text-purple-700">{product.destinationType}</span>
                          )}
                          <span className="text-[11px] text-gray-500">遷移先LP</span>
                        </div>
                        <a href={product.destination} target="_blank" rel="noopener noreferrer" className="text-[11px] text-[#4A7DFF] hover:underline break-all">
                          {product.destination}
                        </a>
                      </div>
                      {!lpData && !lpAnalyzing && (
                        <button
                          className="btn-primary text-xs whitespace-nowrap ml-4"
                          onClick={handleStartLPAnalysis}
                        >
                          <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                          </svg>
                          LP分析を実行
                        </button>
                      )}
                      {lpAnalyzing && (
                        <div className="flex items-center gap-2 ml-4">
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
                          <span className="text-[11px] text-gray-500">分析中...</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* LP Analysis Results */}
                  {lpData && (
                    <>
                      {/* Title & Domain */}
                      {lpData.title && (
                        <div className="card">
                          <h3 className="text-[13px] font-bold text-gray-900">{lpData.title}</h3>
                          <p className="text-[10px] text-gray-400 mt-0.5">{lpData.domain}</p>
                          {lpData.heroHeadline && (
                            <p className="text-[11px] text-gray-600 mt-2 italic">&ldquo;{lpData.heroHeadline}&rdquo;</p>
                          )}
                        </div>
                      )}

                      {/* Scores */}
                      <div className="grid grid-cols-3 gap-3">
                        <div className="card text-center py-4">
                          <p className="text-[10px] text-gray-400 font-medium">品質スコア</p>
                          <p className={`text-2xl font-bold mt-1 ${lpData.qualityScore >= 70 ? "text-emerald-600" : lpData.qualityScore >= 40 ? "text-amber-600" : "text-red-500"}`}>
                            {lpData.qualityScore || "-"}
                          </p>
                        </div>
                        <div className="card text-center py-4">
                          <p className="text-[10px] text-gray-400 font-medium">CV可能性</p>
                          <p className={`text-2xl font-bold mt-1 ${lpData.conversionScore >= 70 ? "text-emerald-600" : lpData.conversionScore >= 40 ? "text-amber-600" : "text-red-500"}`}>
                            {lpData.conversionScore || "-"}
                          </p>
                        </div>
                        <div className="card text-center py-4">
                          <p className="text-[10px] text-gray-400 font-medium">信頼性スコア</p>
                          <p className={`text-2xl font-bold mt-1 ${lpData.trustScore >= 70 ? "text-emerald-600" : lpData.trustScore >= 40 ? "text-amber-600" : "text-red-500"}`}>
                            {lpData.trustScore || "-"}
                          </p>
                        </div>
                      </div>

                      {/* Appeal axes */}
                      {(lpData.primaryAppeal || lpData.secondaryAppeal) && (
                        <div className="card">
                          <h3 className="text-[13px] font-bold text-gray-900 mb-2">訴求軸</h3>
                          <div className="flex items-center gap-2">
                            {lpData.primaryAppeal && (
                              <span className="badge text-[10px] bg-blue-100 text-blue-700">{lpData.primaryAppeal}</span>
                            )}
                            {lpData.secondaryAppeal && (
                              <span className="badge text-[10px] bg-gray-100 text-gray-600">{lpData.secondaryAppeal}</span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* LP Structure details */}
                      <div className="card">
                        <h3 className="text-[13px] font-bold text-gray-900 mb-3">LP構成情報</h3>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="flex items-center justify-between py-1.5 border-b border-gray-100">
                            <span className="text-[11px] text-gray-500">CTA数</span>
                            <span className="text-[12px] font-medium text-gray-900">{lpData.ctaCount}</span>
                          </div>
                          <div className="flex items-center justify-between py-1.5 border-b border-gray-100">
                            <span className="text-[11px] text-gray-500">お客様の声</span>
                            <span className="text-[12px] font-medium text-gray-900">{lpData.testimonialCount}件</span>
                          </div>
                          <div className="flex items-center justify-between py-1.5 border-b border-gray-100">
                            <span className="text-[11px] text-gray-500">文字数</span>
                            <span className="text-[12px] font-medium text-gray-900">{lpData.wordCount ? lpData.wordCount.toLocaleString() : "-"}文字</span>
                          </div>
                          <div className="flex items-center justify-between py-1.5 border-b border-gray-100">
                            <span className="text-[11px] text-gray-500">価格表示</span>
                            <span className="text-[12px] font-medium text-gray-900">{lpData.hasPricing ? lpData.priceText || "あり" : "なし"}</span>
                          </div>
                        </div>
                      </div>

                      {/* Re-analyze button */}
                      <div className="flex justify-center">
                        <button
                          className="btn-secondary text-xs"
                          onClick={handleStartLPAnalysis}
                          disabled={lpAnalyzing}
                        >
                          {lpAnalyzing ? "分析中..." : "再分析"}
                        </button>
                      </div>
                    </>
                  )}

                  {/* No analysis yet but searched */}
                  {!lpData && !lpAnalyzing && lpSearched && (
                    <div className="text-center py-8 text-gray-400">
                      <svg className="w-8 h-8 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9zm3.75 11.625a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
                      </svg>
                      <p className="text-xs">この遷移先LPはまだ分析されていません</p>
                      <p className="text-[10px] mt-1">上の「LP分析を実行」ボタンから分析を開始できます</p>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-12 text-gray-400">
                  <p className="text-xs">遷移先LPの情報がありません</p>
                  <p className="text-[10px] mt-1">この広告にはLP遷移先URLが設定されていません</p>
                </div>
              )}
            </div>
          )}

          {!loading && product && activeTab === "analysis" && (
            <div className="space-y-4">
              {analysis ? (
                <>
                  {/* Prediction scores */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="card text-center py-4">
                      <p className="text-[10px] text-gray-400 font-medium">推定CTR</p>
                      <p className="text-2xl font-bold text-[#4A7DFF] mt-1">
                        {analysis.ctr_prediction ? `${(analysis.ctr_prediction * 100).toFixed(1)}%` : "-"}
                      </p>
                    </div>
                    <div className="card text-center py-4">
                      <p className="text-[10px] text-gray-400 font-medium">推定CVR</p>
                      <p className="text-2xl font-bold text-[#4A7DFF] mt-1">
                        {analysis.cvr_prediction ? `${(analysis.cvr_prediction * 100).toFixed(1)}%` : "-"}
                      </p>
                    </div>
                    <div className="card text-center py-4">
                      <p className="text-[10px] text-gray-400 font-medium">勝ちスコア</p>
                      <p className="text-2xl font-bold text-[#4A7DFF] mt-1">
                        {analysis.winning_probability ? Math.round(analysis.winning_probability) : "-"}
                      </p>
                    </div>
                  </div>

                  {/* Fatigue */}
                  {analysis.fatigue_score !== undefined && (
                    <div className="card">
                      <h3 className="text-[13px] font-bold text-gray-900 mb-3">広告疲労度</h3>
                      <div className="flex items-center gap-4">
                        <div className="relative w-20 h-20">
                          <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
                            <circle cx="18" cy="18" r="14" fill="none" stroke="#f3f4f6" strokeWidth="3" />
                            <circle
                              cx="18" cy="18" r="14" fill="none" stroke="#4A7DFF" strokeWidth="3"
                              strokeDasharray={`${2 * Math.PI * 14}`}
                              strokeDashoffset={`${2 * Math.PI * 14 * (1 - analysis.fatigue_score / 100)}`}
                              strokeLinecap="round"
                            />
                          </svg>
                          <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-gray-900">
                            {Math.round(analysis.fatigue_score)}%
                          </span>
                        </div>
                        <div className="flex-1">
                          <p className="text-[12px] text-gray-600">
                            現在の疲労度は
                            <span className={`font-semibold ${analysis.fatigue_score > 60 ? "text-red-600" : analysis.fatigue_score > 30 ? "text-amber-600" : "text-emerald-600"}`}>
                              {analysis.fatigue_score > 60 ? "高め" : analysis.fatigue_score > 30 ? "やや上昇傾向" : "低め"}
                            </span>
                            です。
                            {analysis.estimated_remaining_days && (
                              <>推定残存有効期間は<span className="font-semibold text-gray-900">約{analysis.estimated_remaining_days}日</span>です。</>
                            )}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Transcription */}
                  {analysis.transcription && (
                    <div className="card">
                      <h3 className="text-[13px] font-bold text-gray-900 mb-2">音声テキスト（文字起こし）</h3>
                      <p className="text-[11px] text-gray-600 leading-relaxed whitespace-pre-wrap">{analysis.transcription}</p>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-12 text-gray-400">
                  <p className="text-xs">AI分析データがありません</p>
                  <p className="text-[10px] mt-1">この広告を分析するには、広告ライブラリから分析を実行してください</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
