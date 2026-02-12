"use client";

import { useState, useEffect } from "react";
import { adsApi, predictionsApi } from "@/lib/api";

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

const platformLabels: Record<string, string> = {
  youtube: "YT", shorts: "S", tiktok: "TT", facebook: "FB",
  instagram: "IG", line: "L", yahoo: "Y!", x: "X",
};

const platformColors: Record<string, string> = {
  youtube: "platform-youtube", tiktok: "platform-tiktok",
  facebook: "platform-facebook", instagram: "platform-instagram",
  line: "platform-line", yahoo: "platform-yahoo", x: "platform-x",
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

  // Fetch predictions when analysis tab is activated
  useEffect(() => {
    if (activeTab !== "analysis" || !product || analysis?.ctr_prediction) return;
    const fetchPredictions = async () => {
      try {
        const response = await predictionsApi.predict({ ad_id: adId });
        if (response.data) {
          setAnalysis((prev) => ({ ...prev, ...response.data }));
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
                <div className="card bg-gradient-to-r from-purple-50 to-blue-50">
                  <div className="flex items-center gap-2 mb-2">
                    {product.destinationType && (
                      <span className="badge text-[9px] bg-purple-100 text-purple-700">{product.destinationType}</span>
                    )}
                    <span className="text-[11px] text-gray-500">遷移先LP</span>
                  </div>
                  <p className="text-[10px] text-[#4A7DFF] break-all">{product.destination}</p>
                  <p className="text-[11px] text-gray-500 mt-3">
                    LP分析はLP分析タブで確認できます。
                  </p>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-400">
                  <p className="text-xs">遷移先LPの情報がありません</p>
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
