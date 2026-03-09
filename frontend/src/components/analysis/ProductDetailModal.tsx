"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { adsApi, predictionsApi, lpAnalysisApi, fetchApi } from "@/lib/api";
import { platformLabels, platformColors } from "@/lib/constants";
import { formatYen, formatNumber } from "@/lib/format";
import { copyToClipboard } from "@/lib/format";
import { getMediaReasonMessage, openCreativeDownload } from "@/lib/media";
import { CreativeViewer } from "../common/CreativeViewer";
import { NumericProvenanceBadge, NumericProvenanceMetricCard, type NumericProvenanceState } from "../common/NumericProvenance";
import { deriveLanguageStatus, LanguageStatusBadges, LanguageStatusWarning } from "../common/LanguageStatus";
import { deriveBedrockStatus, ProvenanceBadge, PriorityBadge, ConfidenceBandBadge, ReviewRequiredBadge } from "../common/BedrockStatus";

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
  language?: string;
  languageSource?: string;
  excludeFromAnalysis?: boolean;
  excludeReason?: string;
  jpCharRatio?: number;
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

interface Ad360Section {
  data: Record<string, unknown>;
  missing_fields: string[];
}

interface Ad360Payload {
  ad_id: number;
  sections: {
    core: Ad360Section;
    creative: Ad360Section;
    text: Ad360Section;
    analysis: Ad360Section;
    lp: Ad360Section;
    quality: Ad360Section;
  };
}

interface TopicClassifyResult {
  confidence: number;
  evidence_terms: string[];
  hit_drivers: string[];
}

interface DictionarySuggestResult {
  candidate_terms: Array<{ topic_label: string; term: string; confidence: number }>;
}

type TabType = "overview" | "copy-guide" | "lp-analysis" | "analysis";

const asText = (value: unknown, fallback = "未取得") => {
  const text = value == null ? "" : String(value).trim();
  return text || fallback;
};

const asList = (value: unknown) =>
  Array.isArray(value) ? Array.from(new Set(value.map((item) => String(item || "").trim()).filter(Boolean))) : [];

const asPercent = (value: unknown) => {
  if (typeof value !== "number" || Number.isNaN(value)) return "未取得";
  return `${Math.round((value <= 1 ? value * 100 : value))}%`;
};

const renderField = (value: string) => value.replaceAll("_", " ").replaceAll(".", " / ");

const asNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const getHostname = (value: string) => {
  if (!value) return "";
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
};

const normalizeDomain = (value: string) => value.replace(/^www\./, "").toLowerCase();

const pickDisplayGenre = (data: Record<string, unknown>) =>
  String(
    data.fine_genre ||
    data.fineGenre ||
    data.genre ||
    data.category ||
    "",
  ).trim();

const isSafeExternalLpUrl = (value?: string | null) => {
  const raw = String(value || "").trim();
  if (!raw) return false;
  try {
    const hostname = new URL(raw).hostname.replace(/^www\./, "").toLowerCase();
    return !["facebook.com", "fb.com", "instagram.com", "messenger.com", "m.me"].some(
      (domain) => hostname === domain || hostname.endsWith(`.${domain}`),
    );
  } catch {
    return false;
  }
};

function buildLpTrust(product: ProductData | null, ad360: Ad360Payload | null, lpData: LPAnalysisData | null) {
  const lpSection = ad360?.sections.lp.data || {};
  const sourceUrl = asText(lpSection.original_url, "") || product?.destination || lpData?.url || "";
  const finalUrl =
    asText(lpSection.resolved_url, "") ||
    asText(lpSection.final_url, "") ||
    lpData?.url ||
    asText(lpSection.url, "") ||
    "";
  const sourceDomain = asText(lpSection.source_domain, "") || getHostname(sourceUrl);
  const finalDomain = asText(lpSection.domain, "") || lpData?.domain || getHostname(finalUrl);
  const statusRaw = asText(lpSection.lp_status, "") || asText(lpSection.status, "") || lpData?.status || "";
  const score = asNumber(lpSection.lp_score) ?? lpData?.qualityScore ?? null;
  const mismatch = Boolean(sourceDomain && finalDomain) && normalizeDomain(sourceDomain) !== normalizeDomain(finalDomain);
  const redirected = Boolean(sourceUrl && finalUrl && sourceUrl !== finalUrl);
  const statusLower = statusRaw.toLowerCase();
  const unresolved = !finalUrl || ["unresolved", "not_fetched", "pending", "unknown"].includes(statusLower);
  const dead = ["dead", "error", "unreachable", "failed", "timeout", "404", "410", "500", "503"].includes(statusLower);

  let label = "到達確認済み";
  let tone = "emerald";
  if (dead) {
    label = "到達不可";
    tone = "rose";
  } else if (unresolved) {
    label = "未解決";
    tone = "gray";
  } else if (mismatch) {
    label = "ドメイン不一致";
    tone = "amber";
  } else if (redirected || statusLower === "redirect") {
    label = "リダイレクトあり";
    tone = "amber";
  }

  return {
    sourceUrl,
    finalUrl,
    sourceDomain,
    finalDomain,
    statusRaw: statusRaw || "unknown",
    score,
    mismatch,
    redirected,
    unresolved,
    dead,
    label,
    tone,
  };
}

function buildCreativeTrust(creative: CreativeData | null, ad360: Ad360Payload | null) {
  const creativeSection = ad360?.sections.creative.data || {};
  const qualitySection = ad360?.sections.quality.data || {};
  const mediaStatusCandidate = qualitySection.media_status ?? creativeSection.media_status;
  const mediaStatus =
    typeof mediaStatusCandidate === "object" && mediaStatusCandidate !== null
      ? mediaStatusCandidate as Record<string, unknown>
      : {};
  const reasons = asList(mediaStatus.missing_reasons ?? qualitySection.missing_reasons);
  const canView =
    typeof mediaStatus.viewable === "boolean"
      ? Boolean(mediaStatus.viewable)
      : Boolean(creative?.snapshotUrl || creative?.imageUrl || creative?.videoUrl || creative?.thumbnailUrl);
  const canDownload =
    typeof mediaStatus.downloadable === "boolean"
      ? Boolean(mediaStatus.downloadable)
      : Boolean(creative?.imageUrl || creative?.videoUrl);
  const snapshotOnly = canView && !canDownload && Boolean(creative?.snapshotUrl);
  return {
    canDownload,
    snapshotOnly,
    reason: reasons[0] || "download_unavailable",
  };
}

function toneClasses(tone: string) {
  if (tone === "rose") return "bg-rose-50 text-rose-700 border-rose-200";
  if (tone === "amber") return "bg-amber-50 text-amber-700 border-amber-200";
  if (tone === "gray") return "bg-gray-100 text-gray-700 border-gray-200";
  return "bg-emerald-50 text-emerald-700 border-emerald-200";
}

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
  const [ad360, setAd360] = useState<Ad360Payload | null>(null);
  const [ad360Loading, setAd360Loading] = useState(false);
  const [ad360Error, setAd360Error] = useState<string | null>(null);
  const [classifyResult, setClassifyResult] = useState<TopicClassifyResult | null>(null);
  const [dictionaryResult, setDictionaryResult] = useState<DictionarySuggestResult | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
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
        const adResponse = await adsApi.get(adId);

        if (adResponse.data) {
          const data = adResponse.data;
          setProduct({
            id: data.id || adId,
            managementId: data.external_id || data.management_id || `AD-${adId}`,
            productName: data.product_name || data.title || "",
            advertiserName: data.advertiser_name || "",
            genre: pickDisplayGenre(data),
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
            language: data.language || (data.ad_metadata || data.metadata || {}).language || undefined,
            languageSource: data.language_source || (data.ad_metadata || data.metadata || {}).language_source || undefined,
            excludeFromAnalysis: data.exclude_from_analysis ?? (data.ad_metadata || data.metadata || {}).exclude_from_analysis ?? false,
            excludeReason: data.exclude_reason || (data.ad_metadata || data.metadata || {}).exclude_reason || undefined,
            jpCharRatio: data.jp_char_ratio ?? (data.ad_metadata || data.metadata || {}).jp_char_ratio ?? null,
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
            category: pickDisplayGenre(data),
            destination_url: data.destination_url || "",
          });
        }
      } catch (error) {
        console.error("Failed to fetch ad data:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [adId]);

  useEffect(() => {
    let cancelled = false;
    setAd360Loading(true);
    setAd360Error(null);
    fetchApi<Ad360Payload>(`/rankings/ad360/${adId}`)
      .then((data) => {
        if (!cancelled) setAd360(data);
      })
      .catch(() => {
        if (!cancelled) {
          setAd360(null);
          setAd360Error("ad360詳細の取得に失敗しました");
        }
      })
      .finally(() => {
        if (!cancelled) setAd360Loading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [adId, refreshTick]);

  useEffect(() => {
    if (analysis) return;
    if (activeTab !== "analysis" && activeTab !== "copy-guide") return;

    const fetchAnalysis = async () => {
      try {
        const res = await adsApi.getAnalysis(adId);
        const aData = res.data;
        if (!aData) return;
        setAnalysis(aData);
        setRawAd((prev) => ({
          ...prev,
          hook_type: aData.hook_types?.[0] || undefined,
          structure_type: aData.structure_type || undefined,
          full_transcript: aData.transcription || undefined,
        }));
      } catch {
        // Analysis missing (404) is expected for non-analyzed ads.
      }
    };

    fetchAnalysis();
  }, [activeTab, adId, analysis]);

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

  const ad360Summary = useMemo(() => {
    if (!ad360) return null;
    const analysisSection = ad360.sections.analysis.data;
    const lpSection = ad360.sections.lp.data;
    const qualitySection = ad360.sections.quality.data;
    const creativeSection = ad360.sections.creative.data;
    const evidenceTerms = Array.from(new Set([...asList(classifyResult?.evidence_terms), ...asList(analysisSection.evidence_terms), ...asList(analysisSection.matched_terms)]));
    const hitDrivers = Array.from(new Set([...asList(classifyResult?.hit_drivers), ...asList(analysisSection.hit_drivers)]));
    const lpSummary = asText(lpSection.structure_summary, "") || asText(lpSection.appeal_strategy_summary, "") || asText(lpSection.target_persona_summary, "") || asText(lpSection.meta_description, "");
    const badges: string[] = [];
    if (typeof qualitySection.extract_quality_score === "number" && qualitySection.extract_quality_score < 40) badges.push("低品質");
    if (qualitySection.needs_media_retry === true) badges.push("再取得推奨");
    if (creativeSection.creative_type === "video" && qualitySection.quality_flags && !(qualitySection.quality_flags as Record<string, unknown>).has_video) badges.push("動画欠損");
    return { evidenceTerms, hitDrivers, lpSummary, badges };
  }, [ad360, classifyResult]);
  const lpTrust = useMemo(() => buildLpTrust(product, ad360, lpData), [product, ad360, lpData]);
  const qualitySection = ad360?.sections.quality;
  const qualityValue = asNumber(qualitySection?.data.extract_quality_score);
  const qualityMissingFields = asList(qualitySection?.missing_fields);
  const qualityMissing = qualityMissingFields.includes("extract_quality_score");
  const qualityState: NumericProvenanceState =
    qualityMissing ? "missing" : qualitySection?.data.needs_media_retry === true ? "stale" : qualityValue != null ? "real" : "missing";
  const spendState: NumericProvenanceState =
    product?.estimationMethod === "audience_based" ? "real" : product?.totalSpend ? "estimated" : "missing";
  const impressionsState: NumericProvenanceState =
    product?.impressions ? (product?.estimationMethod === "audience_based" ? "real" : "estimated") : "missing";
  const reachState: NumericProvenanceState = product?.reach ? "estimated" : "missing";
  const lpScoreState: NumericProvenanceState =
    lpTrust.dead ? "stale" : lpTrust.unresolved ? "missing" : lpTrust.score != null ? "real" : "missing";
  const creativeTrust = useMemo(() => buildCreativeTrust(creative, ad360), [creative, ad360]);
  const languageInfo = useMemo(
    () =>
      deriveLanguageStatus({
        language: product?.language,
        language_source: product?.languageSource,
        exclude_from_analysis: product?.excludeFromAnalysis,
        exclude_reason: product?.excludeReason,
        jp_char_ratio: product?.jpCharRatio,
      }),
    [product],
  );
  const bedrockInfo = useMemo(
    () =>
      deriveBedrockStatus({
        topic_label: ad360?.sections.analysis.data.topic_label,
        topic_confidence: ad360?.sections.analysis.data.topic_confidence,
        matched_terms: ad360?.sections.analysis.data.matched_terms,
        review_required: ad360?.sections.analysis.data.review_required,
        review_reason: ad360?.sections.analysis.data.review_reason,
        needs_topic_review: ad360?.sections.analysis.data.needs_topic_review,
        topic_provenance: ad360?.sections.analysis.data.topic_provenance,
        classification_provenance: ad360?.sections.analysis.data.classification_provenance,
        topic_source: ad360?.sections.analysis.data.topic_source,
        classification_source: ad360?.sections.analysis.data.classification_source,
        priority: ad360?.sections.analysis.data.priority,
        priority_level: ad360?.sections.analysis.data.priority_level,
        priority_score: ad360?.sections.analysis.data.priority_score,
        actual_metrics_priority: ad360?.sections.analysis.data.actual_metrics_priority,
        actual_metrics_priority_score: ad360?.sections.analysis.data.actual_metrics_priority_score,
      }),
    [ad360],
  );

  const runAction = async (key: string, task: () => Promise<void>) => {
    setActionLoading(key);
    try {
      await task();
    } finally {
      setActionLoading(null);
    }
  };

  const refreshAd360 = () => setRefreshTick((value) => value + 1);

  const handleReclassify = async () => runAction("reclassify", async () => {
    const result = await fetchApi<TopicClassifyResult>("/rankings/classify-topic", { method: "POST", body: { ad_id: adId } });
    setClassifyResult(result);
    refreshAd360();
  });

  const handleDictionarySuggest = async () => runAction("dictionary", async () => {
    const topicLabel = ad360 ? asText(ad360.sections.analysis.data.topic_label, "") : "";
    const result = await fetchApi<DictionarySuggestResult>("/rankings/dictionary/suggest", {
      method: "POST",
      body: { ad_ids: [adId], topic_labels: topicLabel ? [topicLabel] : undefined, limit: 6 },
    });
    setDictionaryResult(result);
  });

  const handleKnowledgeRebuild = async () => runAction("knowledge", async () => {
    await fetchApi("/rankings/knowledge/rebuild", { method: "POST", body: { source: "manual", include_recent_days: 30, max_ads: 500 } });
  });

  const handleMediaRetry = async () => runAction("media", async () => {
    await fetchApi(`/rankings/meta-extraction/${adId}/retry`, { method: "POST" });
    refreshAd360();
  });

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
                {product ? `${product.advertiserName} · ${product.genre}` : ""}
              </p>
              <div className="mt-1.5">
                <div className="flex flex-wrap gap-1.5">
                  <LanguageStatusBadges info={languageInfo} />
                  <span className="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700">
                    AI商材 {bedrockInfo.aiProduct || "未分類"}
                  </span>
                  <ProvenanceBadge provenance={bedrockInfo.provenance} />
                  <PriorityBadge priority={bedrockInfo.priority} />
                  <ReviewRequiredBadge required={bedrockInfo.reviewRequired} />
                </div>
              </div>
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
          {!loading && <div className="mb-4"><LanguageStatusWarning info={languageInfo} /></div>}

          {!loading && !product && (
            <div className="text-center py-12 text-gray-400">
              <p className="text-xs">広告データを取得できませんでした</p>
            </div>
          )}

          {!loading && product && activeTab === "overview" && (
            <div className="space-y-5">
              {/* Creative Viewer */}
              {creative && (
                <>
                  <CreativeViewer
                    imageUrl={creative.imageUrl}
                    videoUrl={creative.videoUrl}
                    snapshotUrl={creative.snapshotUrl}
                    thumbnailUrl={creative.thumbnailUrl}
                    creativeType={creative.creativeType}
                    adId={adId}
                  />
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="rounded-lg bg-gray-900 px-3 py-2 text-[11px] font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:bg-gray-300"
                      onClick={() => {
                        if (!creativeTrust.canDownload) {
                          window.alert(getMediaReasonMessage(creativeTrust.reason));
                          return;
                        }
                        openCreativeDownload(adId);
                      }}
                      disabled={!creativeTrust.canDownload}
                    >
                      画像を取得
                    </button>
                    <button
                      className="rounded-lg bg-[#4A7DFF] px-3 py-2 text-[11px] font-medium text-white hover:bg-[#3a6ae8] disabled:cursor-not-allowed disabled:bg-blue-200"
                      onClick={() => {
                        if (!isSafeExternalLpUrl(lpTrust.finalUrl)) return;
                        window.open(lpTrust.finalUrl, "_blank", "noopener,noreferrer");
                      }}
                      disabled={!isSafeExternalLpUrl(lpTrust.finalUrl)}
                    >
                      最終LPを見る
                    </button>
                    <button
                      className="rounded-lg bg-gray-100 px-3 py-2 text-[11px] font-medium text-gray-700 hover:bg-gray-200"
                      onClick={() => copyToClipboard(lpTrust.finalUrl || product.destination || "").catch(() => undefined)}
                    >
                      URLコピー
                    </button>
                  </div>
                  {creativeTrust.snapshotOnly ? <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">snapshotのみで閲覧可です。DL可能素材は未取得です。</p> : null}
                  {!creativeTrust.snapshotOnly && !creativeTrust.canDownload ? <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-700">DL可能素材は未取得です。必要なら再取得を実行してください。</p> : null}
                </>
              )}

              <div className="card space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-[13px] font-bold text-gray-900">Ad360統合詳細</h3>
                    <p className="text-[10px] text-gray-500">概要 / クリエイティブ / テキスト / 分析 / LP / 品質</p>
                  </div>
                  <button className="rounded-lg border border-gray-200 px-3 py-1.5 text-[11px] font-medium text-gray-600 hover:bg-gray-50" onClick={refreshAd360}>
                    再読込
                  </button>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button className="rounded-lg bg-blue-50 px-3 py-1.5 text-[11px] font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-60" disabled={actionLoading === "reclassify"} onClick={() => void handleReclassify()}>
                    {actionLoading === "reclassify" ? "実行中..." : "再分類"}
                  </button>
                  <button className="rounded-lg bg-amber-50 px-3 py-1.5 text-[11px] font-medium text-amber-700 hover:bg-amber-100 disabled:opacity-60" disabled={actionLoading === "dictionary"} onClick={() => void handleDictionarySuggest()}>
                    {actionLoading === "dictionary" ? "実行中..." : "辞書提案"}
                  </button>
                  <button className="rounded-lg bg-purple-50 px-3 py-1.5 text-[11px] font-medium text-purple-700 hover:bg-purple-100 disabled:opacity-60" disabled={lpAnalyzing} onClick={() => void handleStartLPAnalysis()}>
                    {lpAnalyzing ? "解析中..." : "再クロール"}
                  </button>
                  <button className="rounded-lg bg-emerald-50 px-3 py-1.5 text-[11px] font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-60" disabled={actionLoading === "knowledge"} onClick={() => void handleKnowledgeRebuild()}>
                    {actionLoading === "knowledge" ? "実行中..." : "知識更新"}
                  </button>
                  <button className="rounded-lg bg-purple-50 px-3 py-1.5 text-[11px] font-medium text-purple-700 hover:bg-purple-100 disabled:opacity-60" disabled={actionLoading === "media"} onClick={() => void handleMediaRetry()}>
                    {actionLoading === "media" ? "実行中..." : "再取得"}
                  </button>
                </div>

                <div className="rounded-lg bg-slate-50 px-4 py-3">
                  <p className="text-[10px] font-medium text-gray-400">Bedrock分類</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-medium text-indigo-700">
                      AI商材 {bedrockInfo.aiProduct || "未分類"}
                    </span>
                    <ProvenanceBadge provenance={bedrockInfo.provenance} />
                    <PriorityBadge priority={bedrockInfo.priority} />
                    <ReviewRequiredBadge required={bedrockInfo.reviewRequired} />
                    <ConfidenceBandBadge band={bedrockInfo.confidenceBand} />
                  </div>
                  <div className="mt-2 grid gap-2 md:grid-cols-2">
                    <div className="rounded-lg bg-white px-3 py-2 text-[11px] text-gray-700">
                      <span className="text-gray-400">確認理由:</span> {bedrockInfo.reviewReason || "なし"}
                    </div>
                    <div className="rounded-lg bg-white px-3 py-2 text-[11px] text-gray-700">
                      <span className="text-gray-400">信頼帯:</span> {bedrockInfo.confidenceBand}
                    </div>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-lg bg-slate-50 px-4 py-3">
                    <p className="text-[10px] font-medium text-gray-400">HIT寄与要素</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(ad360Summary?.hitDrivers || []).length > 0 ? (ad360Summary?.hitDrivers || []).map((item: string) => <span key={item} className="rounded-full bg-white px-2 py-1 text-[10px] text-slate-700">{item}</span>) : <span className="text-[11px] text-gray-400">未取得</span>}
                    </div>
                  </div>
                  <div className="rounded-lg bg-slate-50 px-4 py-3">
                    <p className="text-[10px] font-medium text-gray-400">判定根拠語</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(ad360Summary?.evidenceTerms || []).length > 0 ? (ad360Summary?.evidenceTerms || []).map((item: string) => <span key={item} className="rounded-full bg-white px-2 py-1 text-[10px] text-slate-700">{item}</span>) : <span className="text-[11px] text-gray-400">未取得</span>}
                    </div>
                  </div>
                </div>

                <div className="rounded-lg bg-slate-50 px-4 py-3">
                  <p className="text-[10px] font-medium text-gray-400">LP要約</p>
                  <p className="mt-2 text-[12px] leading-relaxed text-gray-700">{ad360Summary?.lpSummary || "未取得"}</p>
                </div>

                <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[11px] font-semibold text-gray-900">LP信頼</p>
                    <span className={`rounded-full border px-2 py-1 text-[10px] font-medium ${toneClasses(lpTrust.tone)}`}>{lpTrust.label}</span>
                    {lpTrust.score != null ? <span className="rounded-full border border-sky-200 bg-sky-50 px-2 py-1 text-[10px] font-medium text-sky-700">信頼スコア {Math.round(lpTrust.score)}</span> : null}
                    {lpTrust.redirected ? <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-medium text-amber-700">最終遷移先を表示</span> : null}
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <div className="rounded-lg bg-slate-50 px-3 py-2">
                      <p className="text-[10px] text-gray-400">最終遷移先</p>
                      <p className="mt-1 break-words text-[11px] text-gray-800">{lpTrust.finalUrl || "LP遷移先が未解決です"}</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 px-3 py-2">
                      <p className="text-[10px] text-gray-400">元URL</p>
                      <p className="mt-1 break-words text-[11px] text-gray-800">{lpTrust.sourceUrl || "未取得"}</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 px-3 py-2">
                      <p className="text-[10px] text-gray-400">ドメイン</p>
                      <p className="mt-1 break-words text-[11px] text-gray-800">{lpTrust.finalDomain || "未取得"}{lpTrust.mismatch && lpTrust.sourceDomain ? ` / 元: ${lpTrust.sourceDomain}` : ""}</p>
                    </div>
                    <div className="rounded-lg bg-slate-50 px-3 py-2">
                      <p className="text-[10px] text-gray-400">判定</p>
                      <p className="mt-1 break-words text-[11px] text-gray-800">{lpTrust.statusRaw}</p>
                    </div>
                  </div>
                  {!lpTrust.finalUrl ? <p className="mt-3 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] text-gray-600">LP遷移先が未解決です。短縮URLや中継URLの場合は再クロール後に最終ドメインを確認してください。</p> : null}
                </div>

                {dictionaryResult?.candidate_terms?.length ? (
                  <div className="rounded-lg bg-amber-50 px-4 py-3">
                    <p className="text-[10px] font-medium text-amber-700">辞書提案候補</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {dictionaryResult.candidate_terms.map((item) => (
                        <span key={`${item.topic_label}-${item.term}`} className="rounded-full bg-white px-2 py-1 text-[10px] text-amber-700">
                          {item.term} ({item.topic_label}, {Math.round(item.confidence * 100)}%)
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}

                {ad360Loading ? (
                  <div className="flex items-center justify-center py-6">
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
                  </div>
                ) : ad360Error ? (
                  <div className="rounded-lg bg-red-50 px-4 py-3 text-[12px] text-red-700">{ad360Error}</div>
                ) : ad360 ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    {Object.entries(ad360.sections).map(([sectionKey, section]) => (
                      <div key={sectionKey} className="rounded-lg border border-gray-200 px-4 py-3">
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <p className="text-[12px] font-semibold text-gray-900">{sectionKey}</p>
                          <button
                            className="rounded bg-gray-100 px-2 py-1 text-[10px] font-medium text-gray-700 hover:bg-gray-200"
                            onClick={() => {
                              if (sectionKey === "analysis") void handleReclassify();
                              else if (sectionKey === "lp") void handleStartLPAnalysis();
                              else void handleMediaRetry();
                            }}
                          >
                            再取得
                          </button>
                        </div>
                        <div className="space-y-2">
                          {Object.entries(section.data).slice(0, 6).map(([key, value]) => (
                            <div key={key} className="rounded bg-gray-50 px-3 py-2">
                              <p className="text-[10px] text-gray-400">{key}</p>
                              <p className="mt-0.5 break-words text-[11px] text-gray-800">
                                {Array.isArray(value) ? (value.length > 0 ? value.join(", ") : "未取得") : typeof value === "object" && value !== null ? JSON.stringify(value) : asText(value)}
                              </p>
                            </div>
                          ))}
                          <div>
                            <p className="text-[10px] font-medium text-gray-400">欠損項目</p>
                            <div className="mt-1 flex flex-wrap gap-1.5">
                              {section.missing_fields.length > 0 ? section.missing_fields.map((field) => (
                                <span key={field} className="rounded-full bg-rose-50 px-2 py-1 text-[10px] text-rose-700">{renderField(field)}</span>
                              )) : <span className="text-[11px] text-emerald-600">欠損なし</span>}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>

              {/* Delivery Metrics */}
              <div className="grid grid-cols-3 gap-3">
                <NumericProvenanceMetricCard
                  label="推定消化額"
                  value={formatYen(product.totalSpend)}
                  state={spendState}
                  note={spendState === "real" ? "実績集計" : spendState === "estimated" ? "CPMまたは audience 推定" : "未取得"}
                  warning={spendState === "estimated" ? "estimated_only / 実データ未取得" : undefined}
                />
                <NumericProvenanceMetricCard
                  label="推定表示回数"
                  value={product.impressions ? formatNumber(product.impressions) : "-"}
                  state={impressionsState}
                  note={product.cpm != null && product.cpm > 0 ? `CPM ${formatYen(product.cpm)}` : impressionsState === "missing" ? "backfill待ち" : "推定表示回数"}
                />
                <NumericProvenanceMetricCard
                  label="推定再生回数"
                  value={formatNumber(product.totalPlays)}
                  state={product.totalPlays > 0 ? "real" : "missing"}
                  note={product.reach != null && product.reach > 0 ? `リーチ ${formatNumber(product.reach)}` : "観測再生数"}
                  warning={reachState === "missing" ? "missing_numeric_count > 0 / reach未取得" : undefined}
                />
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
              {isSafeExternalLpUrl(product.destination) && (
                <div className="card">
                  <div className="mb-2 flex items-center gap-2">
                    <h3 className="text-[13px] font-bold text-gray-900">遷移先</h3>
                    <NumericProvenanceBadge state={lpScoreState} />
                    <NumericProvenanceBadge state={qualityState} />
                  </div>
                  <div className="flex items-center gap-2">
                    {product.destinationType && (
                      <span className="badge text-[9px] bg-purple-100 text-purple-700">{product.destinationType}</span>
                    )}
                    <a href={product.destination} target="_blank" rel="noopener noreferrer" className="text-[11px] text-[#4A7DFF] hover:underline break-all">
                      {product.destination}
                    </a>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <NumericProvenanceMetricCard
                      label="LP score"
                      value={lpTrust.score != null ? Math.round(lpTrust.score) : "-"}
                      state={lpScoreState}
                      note={lpScoreState === "real" ? "LP解析済み" : lpScoreState === "stale" ? "LP状態が古い可能性" : "LP解析待ち"}
                    />
                    <NumericProvenanceMetricCard
                      label="quality score"
                      value={qualityValue != null ? Math.round(qualityValue) : "-"}
                      state={qualityState}
                      note={qualityState === "real" ? "抽出品質スコア" : qualityState === "stale" ? "再取得推奨" : "抽出待ち"}
                      warning={qualityMissing ? "missing_numeric_count > 0 / backfill待ち" : undefined}
                    />
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
              {isSafeExternalLpUrl(product.destination) ? (
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
                  <p className="text-xs">有効なLP遷移先が未解決です</p>
                  <p className="text-[10px] mt-1">Meta内部URLや未解決URLは表示対象から除外しています</p>
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
