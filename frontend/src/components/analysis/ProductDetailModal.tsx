"use client";

import { useState, useEffect, useRef } from "react";
import { adsApi, predictionsApi, lpAnalysisApi } from "@/lib/api";
import { platformLabels, platformColors } from "@/lib/constants";
import { formatYen, formatNumber } from "@/lib/format";
import { copyToClipboard } from "@/lib/format";
import { CreativeViewer } from "../common/CreativeViewer";

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
  estimationMethod?: string;
  daysRunning?: number;
  isStillRunning?: boolean;
  deliveryStartTime?: string;
  impressions?: number;
  reach?: number;
  cpm?: number;
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
  improvement_suggestions?: Array<{
    category: string;
    suggestion: string;
    priority: string;
    expected_ctr_lift?: string;
    expected_cvr_lift?: string;
  }>;
  feature_importance?: Array<{
    feature: string;
    importance: number;
    value: string;
  }>;
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

interface CreativeData {
  imageUrl?: string | null;
  videoUrl?: string | null;
  snapshotUrl?: string | null;
  thumbnailUrl?: string | null;
  creativeType?: string | null;
}

interface RawAdData {
  title?: string;
  description?: string;
  platform?: string;
  category?: string;
  destination_url?: string;
  hook_type?: string;
  hook_text?: string;
  cta_text?: string;
  structure_type?: string;
  overall_sentiment?: string;
  is_ugc_style?: boolean;
  has_narration?: boolean;
  has_subtitles?: boolean;
  keywords?: Array<{ keyword: string; score: number; category: string }>;
  full_transcript?: string;
}

type TabType = "overview" | "copy-guide" | "lp-analysis" | "analysis";

export default function ProductDetailModal({ adId, onClose }: ProductDetailModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [product, setProduct] = useState<ProductData | null>(null);
  const [creative, setCreative] = useState<CreativeData | null>(null);
  const [rawAd, setRawAd] = useState<RawAdData | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lpData, setLpData] = useState<LPAnalysisData | null>(null);
  const [lpAnalyzing, setLpAnalyzing] = useState(false);
  const [lpSearched, setLpSearched] = useState(false);
  const [briefCopied, setBriefCopied] = useState(false);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const briefTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
      if (briefTimeoutRef.current) clearTimeout(briefTimeoutRef.current);
    };
  }, []);

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
            estimationMethod: data.estimation_method || data.estimationMethod || (data.ad_metadata || data.metadata || {}).estimation_method || undefined,
            daysRunning: data.days_running || data.daysRunning || (data.ad_metadata || data.metadata || {}).days_running || undefined,
            isStillRunning: data.is_still_running ?? data.isStillRunning ?? (data.ad_metadata || data.metadata || {}).is_still_running ?? undefined,
            deliveryStartTime: data.delivery_start_time || data.deliveryStartTime || (data.ad_metadata || data.metadata || {}).delivery_start_time || undefined,
            impressions: data.impressions || (data.ad_metadata || data.metadata || {}).impressions_from_audience || 0,
            reach: data.reach || (data.ad_metadata || data.metadata || {}).estimated_audience_max || 0,
            cpm: data.cpm || 0,
          });
          setCreative({
            imageUrl: data.image_url || data.imageUrl || null,
            videoUrl: data.video_url || data.videoUrl || null,
            snapshotUrl: data.snapshot_url || data.snapshotUrl || null,
            thumbnailUrl: data.thumbnail_url || data.thumbnailUrl || null,
            creativeType: data.creative_type || data.creativeType || null,
          });
          setRawAd({
            title: data.title || data.product_name || "",
            description: data.description || "",
            platform: data.platform || "",
            category: data.category || data.genre || "",
            destination_url: data.destination_url || "",
          });
        }

        if (analysisResponse.status === "fulfilled" && analysisResponse.value.data) {
          const aData = analysisResponse.value.data;
          setAnalysis(aData);
          setRawAd((prev) => ({
            ...prev,
            hook_type: aData.hook_types?.[0] || undefined,
            structure_type: aData.structure_type || undefined,
            full_transcript: aData.transcription || undefined,
          }));
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
          pollTimeoutRef.current = setTimeout(poll, 3000);
        } else {
          setLpAnalyzing(false);
        }
      };
      pollTimeoutRef.current = setTimeout(poll, 2000);
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
            { id: "copy-guide", label: "パクりガイド" },
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
              {/* Creative Viewer */}
              {creative && (
                <CreativeViewer
                  imageUrl={creative.imageUrl}
                  videoUrl={creative.videoUrl}
                  snapshotUrl={creative.snapshotUrl}
                  thumbnailUrl={creative.thumbnailUrl}
                  creativeType={creative.creativeType}
                  adId={adId}
                />
              )}

              {/* Delivery Metrics */}
              <div className="grid grid-cols-3 gap-3">
                <div className="card py-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <p className="text-[10px] text-gray-400 font-medium">推定消化額</p>
                    {product.estimationMethod === "audience_based" ? (
                      <span className="badge text-[8px] bg-green-100 text-green-700">実データ</span>
                    ) : product.estimationMethod === "cpm_based" ? (
                      <span className="badge text-[8px] bg-yellow-100 text-yellow-700">CPM推定</span>
                    ) : null}
                  </div>
                  <p className="text-lg font-bold text-gray-900">{formatYen(product.totalSpend)}</p>
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium mb-1">推定表示回数</p>
                  <p className="text-lg font-bold text-gray-900">
                    {product.impressions ? formatNumber(product.impressions) : "-"}
                  </p>
                  {product.cpm != null && product.cpm > 0 && (
                    <p className="text-[9px] text-gray-400 mt-0.5">CPM {formatYen(product.cpm)}</p>
                  )}
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium mb-1">推定再生回数</p>
                  <p className="text-lg font-bold text-gray-900">{formatNumber(product.totalPlays)}</p>
                  {product.reach != null && product.reach > 0 && (
                    <p className="text-[9px] text-gray-400 mt-0.5">リーチ {formatNumber(product.reach)}</p>
                  )}
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium mb-1">配信日数</p>
                  <p className="text-lg font-bold text-gray-900">
                    {product.daysRunning != null
                      ? <>{product.daysRunning}<span className="text-[13px] text-gray-400 ml-0.5">日</span></>
                      : product.publishedDate
                        ? <>{Math.max(1, Math.round((Date.now() - new Date(product.publishedDate).getTime()) / 86400000))}<span className="text-[13px] text-gray-400 ml-0.5">日</span></>
                        : "-"}
                  </p>
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium mb-1">ステータス</p>
                  {product.isStillRunning === true ? (
                    <p className="text-lg font-bold text-emerald-600">● 配信中</p>
                  ) : product.isStillRunning === false ? (
                    <p className="text-lg font-bold text-gray-400">○ 終了</p>
                  ) : (
                    <p className="text-lg font-bold text-gray-300">不明</p>
                  )}
                  <p className="text-[9px] text-gray-400 mt-0.5">
                    {product.deliveryStartTime
                      ? `開始: ${new Date(product.deliveryStartTime).toLocaleDateString("ja-JP")}`
                      : product.publishedDate
                        ? `開始: ${new Date(product.publishedDate).toLocaleDateString("ja-JP")}`
                        : ""}
                  </p>
                </div>
                <div className="card py-3">
                  <p className="text-[10px] text-gray-400 font-medium mb-1">出稿媒体</p>
                  <p className="text-lg font-bold text-gray-900">{product.platforms.length}<span className="text-[13px] text-gray-400 ml-0.5">媒体</span></p>
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

          {!loading && product && activeTab === "copy-guide" && (
            <div className="space-y-5">
              {/* Copy Guide Header */}
              <div className="card bg-gradient-to-r from-blue-50 to-indigo-50 px-5 py-4">
                <div className="flex items-center gap-2 mb-2">
                  <svg className="w-5 h-5 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                  </svg>
                  <h3 className="text-[14px] font-bold text-gray-900">この広告の勝ちフォーミュラ</h3>
                </div>
                <p className="text-[11px] text-gray-500">この広告の構成要素を分解しました。下のブリーフをコピーしてクリエイティブ生成に活用できます。</p>
              </div>

              {/* Formula Breakdown */}
              <div className="grid grid-cols-2 gap-3">
                {/* Basic Info */}
                <div className="card px-4 py-3">
                  <p className="text-[10px] text-gray-400 font-medium mb-2">基本情報</p>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-gray-500">商材</span>
                      <span className="text-[11px] font-medium text-gray-900">{product.productName || "-"}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-gray-500">ジャンル</span>
                      <span className="badge-blue text-[9px]">{product.genre || "-"}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-gray-500">媒体</span>
                      <span className="text-[11px] text-gray-700">{product.platforms.join(", ") || "-"}</span>
                    </div>
                    {product.duration > 0 && (
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-gray-500">尺</span>
                        <span className="text-[11px] text-gray-700">{product.duration}秒</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Performance */}
                <div className="card px-4 py-3">
                  <p className="text-[10px] text-gray-400 font-medium mb-2">実績</p>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-gray-500">累計消化額</span>
                      <span className="text-[11px] font-bold text-gray-900">{formatYen(product.totalSpend)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-gray-500">累計再生数</span>
                      <span className="text-[11px] font-bold text-gray-900">{formatNumber(product.totalPlays)}</span>
                    </div>
                    {analysis?.winning_probability != null && (
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-gray-500">勝ちスコア</span>
                        <span className="text-[11px] font-bold text-[#4A7DFF]">{Math.round(analysis.winning_probability)}/100</span>
                      </div>
                    )}
                    {analysis?.ctr_prediction != null && (
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-gray-500">推定CTR</span>
                        <span className="text-[11px] font-bold text-emerald-600">{(analysis.ctr_prediction * 100).toFixed(1)}%</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Creative Structure */}
              <div className="card px-4 py-3">
                <p className="text-[10px] text-gray-400 font-medium mb-3">クリエイティブ構成</p>
                <div className="flex items-stretch gap-2">
                  {/* Hook */}
                  <div className="flex-1 rounded-lg bg-red-50 border border-red-100 px-3 py-2.5 text-center">
                    <p className="text-[9px] text-red-400 font-medium mb-1">HOOK（冒頭）</p>
                    <p className="text-[11px] font-semibold text-red-700">
                      {rawAd?.hook_type || analysis?.hook_types?.[0] || "不明"}
                    </p>
                  </div>
                  <div className="flex items-center text-gray-300">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </div>
                  {/* Body */}
                  <div className="flex-1 rounded-lg bg-blue-50 border border-blue-100 px-3 py-2.5 text-center">
                    <p className="text-[9px] text-blue-400 font-medium mb-1">BODY（本編）</p>
                    <p className="text-[11px] font-semibold text-blue-700">
                      {rawAd?.structure_type || analysis?.structure_type || "不明"}
                    </p>
                  </div>
                  <div className="flex items-center text-gray-300">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </div>
                  {/* CTA */}
                  <div className="flex-1 rounded-lg bg-emerald-50 border border-emerald-100 px-3 py-2.5 text-center">
                    <p className="text-[9px] text-emerald-400 font-medium mb-1">CTA（行動喚起）</p>
                    <p className="text-[11px] font-semibold text-emerald-700">
                      {analysis?.improvement_suggestions?.find((s) => s.category === "cta")?.suggestion?.slice(0, 20) || "詳細はAI分析タブ"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Feature highlights from analysis */}
              {analysis?.feature_importance && analysis.feature_importance.length > 0 && (
                <div className="card px-4 py-3">
                  <p className="text-[10px] text-gray-400 font-medium mb-2">この広告の強み（上位要因）</p>
                  <div className="flex flex-wrap gap-1.5">
                    {analysis.feature_importance
                      .sort((a, b) => b.importance - a.importance)
                      .slice(0, 5)
                      .map((f, i) => {
                        const featureMap: Record<string, string> = {
                          hook_quality: "フック品質", cta_strength: "CTA強度", visual_appeal: "ビジュアル",
                          copy_effectiveness: "コピー効果", audio_quality: "音声", pacing: "テンポ",
                          duration: "動画長", text_overlay: "テキスト", face_presence: "顔あり",
                          product_display: "商品表示", ugc_style: "UGC", subtitles: "字幕",
                        };
                        return (
                          <span key={i} className="inline-flex items-center gap-1 badge text-[10px] bg-blue-50 text-blue-700">
                            {featureMap[f.feature] || f.feature}: {f.value}
                          </span>
                        );
                      })}
                  </div>
                </div>
              )}

              {/* Transcript snippet */}
              {analysis?.transcription && (
                <div className="card px-4 py-3">
                  <p className="text-[10px] text-gray-400 font-medium mb-2">トークスクリプト（参考）</p>
                  <p className="text-[11px] text-gray-600 leading-relaxed whitespace-pre-wrap line-clamp-6">
                    {analysis.transcription}
                  </p>
                </div>
              )}

              {/* Copy Brief Button */}
              <div className="card px-4 py-4 bg-gray-50">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[12px] font-semibold text-gray-900">クリエイティブブリーフ</p>
                    <p className="text-[10px] text-gray-400 mt-0.5">この広告の情報をコピーして、クリエイティブ生成ツールで活用</p>
                  </div>
                  <button
                    className={`px-4 py-2 rounded-lg text-[12px] font-medium transition-all ${
                      briefCopied
                        ? "bg-emerald-500 text-white"
                        : "bg-[#4A7DFF] text-white hover:bg-[#3a6ae8]"
                    }`}
                    onClick={() => {
                      const brief = [
                        `【パクりブリーフ】`,
                        `商材名: ${product.productName}`,
                        `広告主: ${product.advertiserName}`,
                        `ジャンル: ${product.genre}`,
                        `媒体: ${product.platforms.join(", ")}`,
                        product.duration > 0 ? `動画尺: ${product.duration}秒` : null,
                        `累計消化額: ${formatYen(product.totalSpend)}`,
                        `累計再生数: ${formatNumber(product.totalPlays)}`,
                        analysis?.winning_probability ? `勝ちスコア: ${Math.round(analysis.winning_probability)}/100` : null,
                        ``,
                        `--- 構成 ---`,
                        `フック: ${rawAd?.hook_type || analysis?.hook_types?.[0] || "不明"}`,
                        `構成タイプ: ${rawAd?.structure_type || analysis?.structure_type || "不明"}`,
                        analysis?.feature_importance
                          ? `強み: ${analysis.feature_importance.sort((a, b) => b.importance - a.importance).slice(0, 3).map((f) => f.feature).join(", ")}`
                          : null,
                        ``,
                        analysis?.transcription ? `--- トークスクリプト ---\n${analysis.transcription.slice(0, 500)}` : null,
                        ``,
                        product.destination ? `遷移先LP: ${product.destination}` : null,
                      ].filter(Boolean).join("\n");

                      copyToClipboard(brief).then(() => {
                        setBriefCopied(true);
                        briefTimeoutRef.current = setTimeout(() => setBriefCopied(false), 2000);
                      }).catch(() => {
                        // Clipboard API may fail due to permissions or non-secure context
                      });
                    }}
                  >
                    {briefCopied ? (
                      <>
                        <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                        コピー済み
                      </>
                    ) : (
                      <>
                        <svg className="w-3.5 h-3.5 mr-1 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                        </svg>
                        ブリーフをコピー
                      </>
                    )}
                  </button>
                </div>
              </div>
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

                  {/* Improvement Suggestions */}
                  {analysis.improvement_suggestions && analysis.improvement_suggestions.length > 0 && (
                    <div className="card">
                      <h3 className="text-[13px] font-bold text-gray-900 mb-3">改善ポイント</h3>
                      <div className="space-y-2">
                        {(analysis.improvement_suggestions ?? []).map((item, idx) => {
                          const priorityStyle = item.priority === "high"
                            ? "bg-red-100 text-red-700"
                            : item.priority === "medium"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-gray-100 text-gray-600";
                          const priorityLabel = item.priority === "high" ? "高" : item.priority === "medium" ? "中" : "低";
                          const categoryMap: Record<string, string> = {
                            hook: "フック", cta: "CTA", visual: "ビジュアル", copy: "コピー",
                            targeting: "ターゲティング", structure: "構成", audio: "音声", pacing: "テンポ",
                          };
                          return (
                            <div key={idx} className="flex items-start gap-2 p-2.5 rounded-lg bg-gray-50">
                              <span className={`badge text-[9px] shrink-0 mt-0.5 ${priorityStyle}`}>{priorityLabel}</span>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5 mb-0.5">
                                  <span className="badge text-[9px] bg-blue-50 text-blue-600">
                                    {categoryMap[item.category] || item.category}
                                  </span>
                                </div>
                                <p className="text-[11px] text-gray-700 leading-relaxed">{item.suggestion}</p>
                                {(item.expected_ctr_lift || item.expected_cvr_lift) && (
                                  <div className="flex items-center gap-2 mt-1">
                                    {item.expected_ctr_lift && (
                                      <span className="text-[10px] text-emerald-600">CTR {item.expected_ctr_lift}</span>
                                    )}
                                    {item.expected_cvr_lift && (
                                      <span className="text-[10px] text-emerald-600">CVR {item.expected_cvr_lift}</span>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Feature Importance */}
                  {analysis.feature_importance && analysis.feature_importance.length > 0 && (
                    <div className="card">
                      <h3 className="text-[13px] font-bold text-gray-900 mb-3">パフォーマンス要因</h3>
                      <div className="space-y-2">
                        {(analysis.feature_importance ?? []).map((item, idx) => {
                          const featureMap: Record<string, string> = {
                            hook_quality: "フック品質", cta_strength: "CTA強度", visual_appeal: "ビジュアル訴求",
                            copy_effectiveness: "コピー効果", audio_quality: "音声品質", pacing: "テンポ",
                            brand_recognition: "ブランド認知", targeting_precision: "ターゲティング精度",
                            duration: "動画長", text_overlay: "テキストオーバーレイ",
                            face_presence: "顔の有無", product_display: "商品表示",
                            ugc_style: "UGCスタイル", subtitles: "字幕",
                          };
                          const barWidth = Math.max(Math.min(item.importance * 100, 100), 5);
                          return (
                            <div key={idx} className="flex items-center gap-3">
                              <span className="text-[11px] text-gray-600 w-28 shrink-0 truncate">
                                {featureMap[item.feature] || item.feature}
                              </span>
                              <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-[#4A7DFF] rounded-full transition-all"
                                  style={{ width: `${barWidth}%` }}
                                />
                              </div>
                              <span className="text-[10px] text-gray-500 w-16 shrink-0 text-right">{item.value}</span>
                            </div>
                          );
                        })}
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
