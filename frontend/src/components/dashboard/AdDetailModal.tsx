"use client";

import React, { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { getMediaReasonMessage, openCreativeDownload } from "@/lib/media";
import { platformBadgeColors, platformLabels, genreOptions } from "@/lib/constants";
import { copyToClipboard, formatNumber, formatYen } from "@/lib/format";
import type { AdMediaInfo, MetaTokenInfo } from "@/types";
import { CreativeViewer } from "../common/CreativeViewer";
import { NumericProvenanceBadge, NumericProvenanceMetricCard, type NumericProvenanceState } from "../common/NumericProvenance";
import { deriveLanguageStatus, LanguageStatusBadges, LanguageStatusWarning } from "../common/LanguageStatus";
import { deriveBedrockStatus, ProvenanceBadge, PriorityBadge, ConfidenceBandBadge, ReviewRequiredBadge } from "../common/BedrockStatus";
import SimilarAdsPanel from "./SimilarAdsPanel";
import CreativeIntelligence from "./CreativeIntelligence";
import HitPrediction from "./HitPrediction";
import AdAnnotations from "./AdAnnotations";

interface HitAd {
  rank: number;
  ad_id: number;
  product_name: string;
  advertiser_name: string;
  genre: string;
  platform: string;
  view_increase: number;
  spend_increase: number;
  cumulative_views: number;
  cumulative_spend: number;
  hit_score: number;
  trend_score: number;
  thumbnail: string;
  duration_seconds: number;
  image_url: string;
  snapshot_url: string;
  destination_url: string;
  destination_type: string;
  like_count: number;
  published_date: string;
  management_id: string;
  ad_url: string;
  description: string;
  title: string;
  video_url?: string;
  creative_type?: string;
  estimation_method?: string;
  hit_level?: string;
  resolved_url?: string;
  final_url?: string;
  domain?: string;
  lp_status?: string;
  lp_score?: number;
  language?: string;
  language_source?: string;
  exclude_from_analysis?: boolean;
  exclude_reason?: string;
  jp_char_ratio?: number;
  metric_source?: string;
  creative_source?: string;
  lp_source?: string;
  metric_status?: NumericProvenanceState;
  creative_status?: NumericProvenanceState;
  freshness_status?: "fresh" | "missing" | "stale" | string;
  last_meta_success_at?: string;
  meta_quality_state?: NumericProvenanceState;
  meta_recovery_reason?: string;
}

interface AdDetailModalProps {
  ad: HitAd;
  onClose: () => void;
  onAdSelect: (adId: number) => void;
  onRecoveryQueued?: () => void;
}

interface ScoreBreakdownData {
  signals?: Record<string, { score: number; max: number; detail?: string }>;
}

interface TopicClassifyResult {
  confidence: number;
  evidence_terms: string[];
  hit_drivers: string[];
}

interface DictionarySuggestResult {
  candidate_terms: Array<{ topic_label: string; term: string; confidence: number }>;
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

const signalLabels: Record<string, string> = {
  longevity: "配信継続力",
  spend: "消化額",
  active_bonus: "配信中ボーナス",
  creative: "クリエイティブ",
  trend: "トレンド",
};

const signalColors: Record<string, string> = {
  longevity: "#3b82f6",
  spend: "#22c55e",
  active_bonus: "#f97316",
  creative: "#a855f7",
  trend: "#ec4899",
};

const genreLabel = (value: string | null | undefined) => {
  if (!value || value === "未分類") return "未分類";
  return genreOptions.find((g) => g.value === value)?.label || value;
};

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

function buildLpTrust(lpData: Record<string, unknown> | null, ad: HitAd, mediaInfo: AdMediaInfo | null) {
  const data = lpData || {};
  const lpInfo = mediaInfo?.lp_info || {};
  const sourceUrl = asText(lpInfo.destination_url, "") || asText(data.original_url, "") || ad.destination_url || "";
  const finalUrl =
    asText(lpInfo.resolved_url, "") ||
    asText(data.resolved_url, "") ||
    asText(data.final_url, "") ||
    ad.resolved_url ||
    ad.final_url ||
    asText(data.url, "") ||
    "";
  const sourceDomain = asText(lpInfo.domain, "") || asText(data.source_domain, "") || getHostname(sourceUrl);
  const finalDomain =
    asText(lpInfo.final_domain, "") ||
    asText(data.domain, "") ||
    asText(data.final_domain, "") ||
    ad.domain ||
    getHostname(finalUrl);
  const statusRaw =
    asText(lpInfo.lp_status, "") ||
    asText(data.lp_status, "") ||
    asText(data.status, "") ||
    asText(data.fetch_status, "") ||
    ad.lp_status ||
    "";
  const lpScore = asNumber(lpInfo.lp_score) ?? asNumber(data.lp_score) ?? ad.lp_score ?? null;
  const mismatch =
    Boolean(sourceDomain && finalDomain) &&
    normalizeDomain(sourceDomain) !== normalizeDomain(finalDomain);
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
    lpScore,
    mismatch,
    redirected,
    unresolved,
    dead,
    label,
    tone,
  };
}

function buildMediaTrust(ad360: Ad360Payload | null, ad: HitAd, mediaInfo: AdMediaInfo | null) {
  const creative = ad360?.sections.creative.data || {};
  const quality = ad360?.sections.quality.data || {};
  const mediaStatusCandidate = mediaInfo?.media_status ?? quality.media_status ?? creative.media_status;
  const mediaStatus =
    typeof mediaStatusCandidate === "object" && mediaStatusCandidate !== null
      ? mediaStatusCandidate as Record<string, unknown>
      : {};
  const reasons = asList(mediaStatus.missing_reasons ?? quality.missing_reasons);
  const canView =
    typeof mediaStatus.viewable === "boolean"
      ? Boolean(mediaStatus.viewable)
      : Boolean(mediaInfo?.snapshot_url || mediaInfo?.image_url || mediaInfo?.video_url || ad.snapshot_url || ad.image_url || ad.video_url || creative.thumbnail_url);
  const canDownload =
    typeof mediaStatus.downloadable === "boolean"
      ? Boolean(mediaStatus.downloadable)
      : Boolean(mediaInfo?.image_url || mediaInfo?.video_url || ad.image_url || ad.video_url);
  const snapshotOnly =
    reasons.includes("snapshot_only") ||
    (canView && !canDownload && Boolean(mediaInfo?.snapshot_url || ad.snapshot_url));
  return {
    canView,
    canDownload,
    snapshotOnly,
    reasons,
    primaryReason: reasons[0] || "download_unavailable",
  };
}

function toneClasses(tone: string) {
  if (tone === "rose") return "bg-rose-50 text-rose-700 border-rose-200";
  if (tone === "amber") return "bg-amber-50 text-amber-700 border-amber-200";
  if (tone === "gray") return "bg-gray-100 text-gray-700 border-gray-200";
  return "bg-emerald-50 text-emerald-700 border-emerald-200";
}

function isMetaPlatform(platform: string | undefined): boolean {
  return platform === "facebook" || platform === "instagram" || platform === "meta";
}

function formatMetaSource(value: string | undefined): string {
  const normalized = (value || "missing").replaceAll("_", " ");
  if (normalized === "api") return "API";
  if (normalized === "db") return "DB";
  return normalized;
}

function formatMetaTimestamp(value?: string) {
  if (!value) return "未取得";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleString("ja-JP");
}

function isNewMetaAd(lastMetaSuccessAt?: string): boolean {
  if (!lastMetaSuccessAt) return false;
  const parsed = Date.parse(lastMetaSuccessAt);
  if (Number.isNaN(parsed)) return false;
  return Date.now() - parsed <= 1000 * 60 * 60 * 48;
}

export default function AdDetailModal({ ad, onClose, onAdSelect, onRecoveryQueued }: AdDetailModalProps) {
  const [scoreBreakdown, setScoreBreakdown] = useState<ScoreBreakdownData | null>(null);
  const [scoreLoading, setScoreLoading] = useState(false);
  const [mediaInfo, setMediaInfo] = useState<AdMediaInfo | null>(null);
  const [ad360, setAd360] = useState<Ad360Payload | null>(null);
  const [ad360Loading, setAd360Loading] = useState(false);
  const [ad360Error, setAd360Error] = useState<string | null>(null);
  const [classifyResult, setClassifyResult] = useState<TopicClassifyResult | null>(null);
  const [dictionaryResult, setDictionaryResult] = useState<DictionarySuggestResult | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [metaTokenInfo, setMetaTokenInfo] = useState<MetaTokenInfo | null>(null);

  useEffect(() => {
    let cancelled = false;
    setScoreLoading(true);
    fetchApi<ScoreBreakdownData>(`/rankings/score-breakdown/${ad.ad_id}`)
      .then((data) => !cancelled && setScoreBreakdown(data))
      .catch(() => !cancelled && setScoreBreakdown(null))
      .finally(() => !cancelled && setScoreLoading(false));

    fetchApi<AdMediaInfo>(`/ads/${ad.ad_id}/media`)
      .then((data) => !cancelled && setMediaInfo(data))
      .catch(() => !cancelled && setMediaInfo(null));

    if (isMetaPlatform(ad.platform)) {
      fetchApi<MetaTokenInfo>("/settings/meta/token-info")
        .then((data) => !cancelled && setMetaTokenInfo(data))
        .catch(() => !cancelled && setMetaTokenInfo(null));
    } else {
      setMetaTokenInfo(null);
    }

    setAd360Loading(true);
    setAd360Error(null);
    fetchApi<Ad360Payload>(`/rankings/ad360/${ad.ad_id}`)
      .then((data) => !cancelled && setAd360(data))
      .catch(() => {
        if (!cancelled) {
          setAd360(null);
          setAd360Error("ad360詳細の取得に失敗しました");
        }
      })
      .finally(() => !cancelled && setAd360Loading(false));

    return () => {
      cancelled = true;
    };
  }, [ad.ad_id, refreshTick]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const summary = useMemo(() => {
    if (!ad360) return null;
    const analysis = ad360.sections.analysis.data;
    const lp = ad360.sections.lp.data;
    const quality = ad360.sections.quality.data;
    const creative = ad360.sections.creative.data;
    const evidenceTerms = Array.from(new Set([...asList(classifyResult?.evidence_terms), ...asList(analysis.evidence_terms), ...asList(analysis.matched_terms)]));
    const hitDrivers = Array.from(new Set([...asList(classifyResult?.hit_drivers), ...asList(analysis.hit_drivers)]));
    const lpSummary = asText(lp.structure_summary, "") || asText(lp.appeal_strategy_summary, "") || asText(lp.target_persona_summary, "") || asText(lp.meta_description, "");
    const badges = [];
    if (typeof quality.extract_quality_score === "number" && quality.extract_quality_score < 40) badges.push("低品質");
    if (quality.needs_media_retry === true) badges.push("再取得推奨");
    if (creative.creative_type === "video" && quality.quality_flags && !(quality.quality_flags as Record<string, unknown>).has_video) badges.push("動画欠損");
    return { evidenceTerms, hitDrivers, lpSummary, badges };
  }, [ad360, classifyResult]);
  const lpTrust = useMemo(() => buildLpTrust(ad360?.sections.lp.data || null, ad, mediaInfo), [ad360, ad, mediaInfo]);
  const mediaTrust = useMemo(() => buildMediaTrust(ad360, ad, mediaInfo), [ad360, ad, mediaInfo]);
  const qualitySection = ad360?.sections.quality;
  const qualityValue = asNumber(qualitySection?.data.extract_quality_score);
  const qualityMissing = qualitySection?.missing_fields.includes("extract_quality_score") ?? false;
  const qualityState: NumericProvenanceState =
    qualityMissing ? "missing" : qualitySection?.data.needs_media_retry === true ? "stale" : qualityValue != null ? "real" : "missing";
  const lpScoreState: NumericProvenanceState =
    lpTrust.dead ? "stale" : lpTrust.unresolved ? "missing" : lpTrust.lpScore != null ? "real" : "missing";
  const spendState: NumericProvenanceState =
    ad.estimation_method === "audience_based" ? "real" : ad.cumulative_spend > 0 || ad.spend_increase > 0 ? "estimated" : "missing";
  const viewState: NumericProvenanceState = ad.cumulative_views > 0 || ad.view_increase > 0 ? "real" : "missing";
  const trendState: NumericProvenanceState = ad.trend_score > 0 ? "estimated" : "missing";
  const languageInfo = useMemo(() => deriveLanguageStatus(ad as unknown as Record<string, unknown>), [ad]);
  const showMeta = isMetaPlatform(ad.platform);
  const metaState = (ad.meta_quality_state || "missing") as NumericProvenanceState;
  const creativeState = (ad.creative_status || (mediaTrust.snapshotOnly ? "estimated" : mediaTrust.canDownload ? "real" : "missing")) as NumericProvenanceState;
  const metricState = (ad.metric_status || spendState) as NumericProvenanceState;
  const freshnessState = ad.freshness_status === "stale" ? "stale" : ad.last_meta_success_at ? "real" : "missing";
  const metaEmptyStates = useMemo(() => {
    const states: string[] = [];
    if (mediaTrust.snapshotOnly) states.push("snapshot only");
    if (!mediaTrust.snapshotOnly && !mediaTrust.canDownload) states.push("creative pending");
    if (!ad.destination_url || lpTrust.unresolved) states.push("lp missing");
    if (ad.meta_recovery_reason === "detail_enrich_failed") states.push("detail enrich failed");
    return states;
  }, [ad.destination_url, ad.meta_recovery_reason, lpTrust.unresolved, mediaTrust.canDownload, mediaTrust.snapshotOnly]);
  const bedrockInfo = useMemo(
    () =>
      deriveBedrockStatus({
        ...ad,
        ...(ad360?.sections.analysis.data || {}),
      } as Record<string, unknown>),
    [ad, ad360],
  );

  const scoreColor = ad.hit_score >= 80 ? "#ef4444" : ad.hit_score >= 50 ? "#f59e0b" : "#4A7DFF";
  const pLabel = platformLabels[ad.platform] || ad.platform;
  const pBadge = platformBadgeColors[ad.platform] || "bg-gray-100 text-gray-800";

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
    const result = await fetchApi<TopicClassifyResult>("/rankings/classify-topic", { method: "POST", body: { ad_id: ad.ad_id } });
    setClassifyResult(result);
    refreshAd360();
    toast.success("再分類を実行しました");
  });

  const handleDictionarySuggest = async () => runAction("dictionary", async () => {
    const topicLabel = ad360 ? asText(ad360.sections.analysis.data.topic_label, "") : "";
    const result = await fetchApi<DictionarySuggestResult>("/rankings/dictionary/suggest", {
      method: "POST",
      body: { ad_ids: [ad.ad_id], topic_labels: topicLabel ? [topicLabel] : undefined, limit: 6 },
    });
    setDictionaryResult(result);
    toast.success(`辞書候補を ${result.candidate_terms.length} 件取得しました`);
  });

  const handleKnowledgeRebuild = async () => runAction("knowledge", async () => {
    await fetchApi("/rankings/knowledge/rebuild", { method: "POST", body: { source: "manual", include_recent_days: 30, max_ads: 500 } });
    toast.success("知識スナップショットを再構築しました");
  });

  const handleMediaRetry = async () => runAction("media", async () => {
    await fetchApi(`/rankings/meta-extraction/${ad.ad_id}/retry`, { method: "POST" });
    refreshAd360();
    onRecoveryQueued?.();
    toast.success("再取得を投入しました");
  });

  const handleLPCrawl = async () => runAction("lp", async () => {
    const lpUrl = ad360 ? asText(ad360.sections.lp.data.final_url, "") || asText(ad360.sections.lp.data.url, "") : "";
    const url = lpUrl || ad.destination_url;
    if (!url) throw new Error("missing lp url");
    await fetchApi("/lp-analysis/crawl", { method: "POST", body: { url, ad_id: ad.ad_id, auto_analyze: true } });
    onRecoveryQueued?.();
    toast.success("LP再クロールを開始しました");
  }).catch(() => toast.error("LP URL がありません"));

  const retrySection = async (sectionKey: keyof Ad360Payload["sections"]) => {
    if (sectionKey === "analysis") return handleReclassify();
    if (sectionKey === "lp") return handleLPCrawl();
    return handleMediaRetry();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl dark:bg-gray-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3 dark:border-gray-700">
          <div className="min-w-0">
            <h2 className="truncate text-[15px] font-bold text-gray-900 dark:text-gray-100">{ad.product_name || ad.title || "不明"}</h2>
            <p className="truncate text-[11px] text-gray-400 dark:text-gray-500">{ad.advertiser_name || "-"}</p>
          </div>
          <button onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-200">×</button>
        </div>

        <div className="custom-scrollbar flex-1 overflow-y-auto p-5">
          <div className="grid gap-5 xl:grid-cols-[1.02fr_0.98fr]">
            <div className="space-y-4">
              <CreativeViewer
                imageUrl={ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (mediaInfo?.image_url || ad.image_url || ad.thumbnail || null)}
                videoUrl={ad.ad_id ? `/api/v1/media/video/${ad.ad_id}` : (mediaInfo?.video_url || ad.video_url || null)}
                snapshotUrl={mediaInfo?.snapshot_url || ad.snapshot_url || null}
                thumbnailUrl={ad.ad_id ? `/api/v1/media/thumbnail/${ad.ad_id}` : (ad.thumbnail || mediaInfo?.image_url || null)}
                creativeType={ad.creative_type || null}
              />
              <div className="grid grid-cols-2 gap-2">
                <button
                  className="min-h-10 rounded-lg bg-gray-900 text-[12px] font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:bg-gray-300"
                  onClick={() => {
                    if (!mediaTrust.canDownload) {
                      toast.error(getMediaReasonMessage(mediaTrust.primaryReason));
                      return;
                    }
                    openCreativeDownload(ad.ad_id);
                  }}
                  disabled={!mediaTrust.canDownload}
                >
                  クリエイティブDL
                </button>
                <button
                  className="min-h-10 rounded-lg bg-gray-100 text-[12px] font-medium text-gray-700 hover:bg-gray-200 disabled:cursor-not-allowed disabled:opacity-40"
                  disabled={!mediaTrust.canView}
                  onClick={() => window.open(ad.ad_url || mediaInfo?.snapshot_url || ad.snapshot_url || `/api/v1/media/creative/${ad.ad_id}`, "_blank", "noopener,noreferrer")}
                >
                  {mediaTrust.snapshotOnly ? "スナップショット確認" : "別タブで確認"}
                </button>
              </div>
              {mediaTrust.snapshotOnly ? <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">snapshotのみで閲覧可です。DL可能素材は未取得です。</p> : null}
              {!mediaTrust.snapshotOnly && !mediaTrust.canDownload ? <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-700">DL可能素材は未取得です。必要なら再取得を実行してください。</p> : null}

              <Panel title="要点">
                <div className="flex flex-wrap gap-1.5">
                  <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${pBadge}`}>{pLabel}</span>
                  <span className="rounded bg-sky-50 px-2 py-0.5 text-[10px] text-sky-700">{genreLabel(ad.genre)}</span>
                  {showMeta ? <NumericProvenanceBadge state={metaState} /> : null}
                  {showMeta && isNewMetaAd(ad.last_meta_success_at) ? <span className="rounded bg-sky-100 px-2 py-0.5 text-[10px] font-medium text-sky-700">NEW</span> : null}
                  <LanguageStatusBadges info={languageInfo} />
                  <span className="rounded bg-indigo-50 px-2 py-0.5 text-[10px] text-indigo-700 border border-indigo-200">AI商材 {bedrockInfo.aiProduct || "未分類"}</span>
                  <ProvenanceBadge provenance={bedrockInfo.provenance} />
                  <PriorityBadge priority={bedrockInfo.priority} />
                  <ReviewRequiredBadge required={bedrockInfo.reviewRequired} />
                  <ConfidenceBandBadge band={bedrockInfo.confidenceBand} />
                  {(summary?.badges || []).map((badge) => <span key={badge} className="rounded bg-rose-50 px-2 py-0.5 text-[10px] text-rose-700">{badge}</span>)}
                </div>
                <LanguageStatusWarning info={languageInfo} />
                <SummaryText label="review_reason" value={bedrockInfo.reviewReason || "なし"} />
                <SummaryRow label="confidence_band" values={[bedrockInfo.confidenceBand]} />
                {showMeta ? (
                  <>
                    <SummaryRow label="Meta provenance" values={[
                      `metrics: ${formatMetaSource(ad.metric_source)}`,
                      `creative: ${formatMetaSource(ad.creative_source)}`,
                      `lp: ${formatMetaSource(ad.lp_source)}`,
                      ...(metaTokenInfo ? [`token: ${formatMetaSource(metaTokenInfo.runtime_source || metaTokenInfo.token_source)}`] : []),
                    ]} />
                    <SummaryRow label="Meta states" values={metaEmptyStates.length > 0 ? metaEmptyStates : ["healthy"]} />
                    <SummaryText label="last_meta_success_at" value={formatMetaTimestamp(ad.last_meta_success_at)} />
                  </>
                ) : null}
                <MetricBar score={ad.hit_score} scoreColor={scoreColor} />
                <SummaryRow label="HIT寄与要素" values={summary?.hitDrivers || []} />
                <SummaryRow label="判定根拠語" values={summary?.evidenceTerms || []} />
                <SummaryText label="LP要約" value={summary?.lpSummary || ""} />
                <div className="flex flex-wrap gap-2">
                  <ActionButton label="再分類" busy={actionLoading === "reclassify"} onClick={handleReclassify} tone="blue" />
                  <ActionButton label="辞書提案" busy={actionLoading === "dictionary"} onClick={handleDictionarySuggest} tone="amber" />
                  <ActionButton label="知識更新" busy={actionLoading === "knowledge"} onClick={handleKnowledgeRebuild} tone="emerald" />
                </div>
              </Panel>

              <Panel title="LP信頼">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full border px-2.5 py-1 text-[10px] font-medium ${toneClasses(lpTrust.tone)}`}>{lpTrust.label}</span>
                  {lpTrust.lpScore != null ? <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[10px] font-medium text-sky-700">信頼スコア {Math.round(lpTrust.lpScore)}</span> : null}
                  <NumericProvenanceBadge state={lpScoreState} />
                  <NumericProvenanceBadge state={qualityState} />
                  {lpTrust.redirected ? <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[10px] font-medium text-amber-700">最終遷移先を表示</span> : null}
                </div>
                <SummaryText label="最終遷移先" value={lpTrust.finalUrl || "LP遷移先が未解決です"} />
                <SummaryText label="元URL" value={lpTrust.sourceUrl || "未取得"} />
                <SummaryRow label="ドメイン" values={[lpTrust.finalDomain || "未取得", ...(lpTrust.mismatch && lpTrust.sourceDomain ? [`元: ${lpTrust.sourceDomain}`] : [])]} />
                <SummaryRow label="判定" values={[lpTrust.statusRaw || "unknown", ...(lpTrust.dead ? ["到達不可"] : []), ...(lpTrust.unresolved ? ["未解決"] : []), ...(lpTrust.mismatch ? ["domain mismatch"] : [])]} />
                <div className="grid grid-cols-2 gap-3">
                  <NumericProvenanceMetricCard
                    label="LP score"
                    value={lpTrust.lpScore != null ? Math.round(lpTrust.lpScore) : "-"}
                    state={lpScoreState}
                    note={lpScoreState === "real" ? "LP解析結果" : lpScoreState === "stale" ? "到達状態が古い可能性" : "LP解析待ち"}
                  />
                  <NumericProvenanceMetricCard
                    label="quality score"
                    value={qualityValue != null ? Math.round(qualityValue) : "-"}
                    state={qualityState}
                    note={qualityState === "real" ? "最新抽出結果" : qualityState === "stale" ? "再取得推奨" : "抽出待ち"}
                    warning={qualitySection?.missing_fields.length ? "missing_numeric_count > 0 / backfill待ち" : undefined}
                  />
                </div>
                {!lpTrust.finalUrl ? <p className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-[11px] text-gray-600">LP遷移先が未解決です。短縮URLや中継URLの場合は再クロール後に最終ドメインを確認してください。</p> : null}
              </Panel>

              {showMeta ? (
                <Panel title="Meta品質 / Provenance">
                  <div className="flex flex-wrap items-center gap-2">
                    <NumericProvenanceBadge state={metaState} />
                    <NumericProvenanceBadge state={metricState} />
                    <NumericProvenanceBadge state={creativeState} />
                    <NumericProvenanceBadge state={freshnessState} />
                    {metaTokenInfo ? <span className={`rounded-full border px-2.5 py-1 text-[10px] font-medium ${metaTokenInfo.is_valid ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-rose-200 bg-rose-50 text-rose-700"}`}>token {metaTokenInfo.runtime_source}</span> : null}
                  </div>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <NumericProvenanceMetricCard label="metrics" value={formatMetaSource(ad.metric_source)} state={metricState} note={metricState === "real" ? "Meta API由来" : metricState === "estimated" ? "fallback / 推定" : "未取得"} />
                    <NumericProvenanceMetricCard label="creative" value={formatMetaSource(ad.creative_source)} state={creativeState} note={creativeState === "real" ? "DL可能素材あり" : creativeState === "estimated" ? "snapshot / fallback" : "素材未取得"} />
                    <NumericProvenanceMetricCard label="LP" value={formatMetaSource(ad.lp_source)} state={lpScoreState} note={lpTrust.finalUrl ? "LP解決済み" : "LP未解決"} />
                    <NumericProvenanceMetricCard label="token" value={metaTokenInfo ? formatMetaSource(metaTokenInfo.runtime_source || metaTokenInfo.token_source) : "-"} state={metaTokenInfo?.is_valid ? "real" : metaTokenInfo ? "stale" : "missing"} note={metaTokenInfo?.fallback_reason || metaTokenInfo?.message || "token情報未取得"} warning={metaTokenInfo?.last_validation_error || undefined} />
                  </div>
                  {metaEmptyStates.length > 0 ? (
                    <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-700">
                      状態: {metaEmptyStates.join(" / ")}
                    </p>
                  ) : null}
                  {ad.meta_recovery_reason ? (
                    <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-700">
                      recovery reason: {ad.meta_recovery_reason.replaceAll("_", " ")}
                    </p>
                  ) : null}
                </Panel>
              ) : null}

              <Panel title="スコア内訳">
                {scoreLoading ? <Loader /> : scoreBreakdown?.signals ? (
                  <div className="space-y-2">
                    {Object.entries(scoreBreakdown.signals).map(([key, sig]) => (
                      <div key={key}>
                        <div className="flex items-center gap-2">
                          <span className="w-20 shrink-0 text-[10px] text-gray-500 dark:text-gray-400">{signalLabels[key] || key}</span>
                          <div className="h-2 flex-1 rounded-full bg-gray-200 dark:bg-gray-700">
                            <div className="h-full rounded-full" style={{ width: `${sig.max > 0 ? (sig.score / sig.max) * 100 : 0}%`, backgroundColor: signalColors[key] || "#6b7280" }} />
                          </div>
                          <span className="w-10 shrink-0 text-right text-[10px] text-gray-600 dark:text-gray-300">{sig.score}/{sig.max}</span>
                        </div>
                        {sig.detail ? <p className="ml-[88px] mt-0.5 text-[9px] text-gray-400 dark:text-gray-500">{sig.detail}</p> : null}
                      </div>
                    ))}
                  </div>
                ) : <p className="text-[10px] text-gray-400 dark:text-gray-500">内訳データなし</p>}
              </Panel>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <NumericProvenanceMetricCard label="消化額増加 (週)" value={formatYen(ad.spend_increase || 0)} state={spendState} note={spendState === "real" ? "媒体観測値" : spendState === "estimated" ? "CPMモデルによる推定値" : "未取得"} />
                <NumericProvenanceMetricCard label="累計推定消化額" value={formatYen(ad.cumulative_spend || 0)} state={spendState} note={spendState === "real" ? "実績集計" : spendState === "estimated" ? "実データ未取得時は推定" : "未取得"} warning={spendState === "estimated" ? "estimated_only / 実データ未取得" : undefined} />
                <NumericProvenanceMetricCard label="再生数増加 (週)" value={formatNumber(ad.view_increase || 0)} state={viewState} note={viewState === "real" ? "観測値ベース" : "観測値なし"} />
                <NumericProvenanceMetricCard label="累計再生数" value={formatNumber(ad.cumulative_views || 0)} state={viewState} note={viewState === "real" ? "観測値ベース" : "観測値なし"} />
                <NumericProvenanceMetricCard label="いいね数" value={formatNumber(ad.like_count || 0)} state={ad.like_count > 0 ? "real" : "missing"} note={ad.like_count > 0 ? "媒体観測値" : "未取得"} />
                <NumericProvenanceMetricCard label="トレンドスコア" value={String(ad.trend_score || 0)} state={trendState} note={trendState === "estimated" ? "内部計算値" : "算出前"} />
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-[14px] font-bold text-gray-900 dark:text-gray-100">Ad360統合詳細</h3>
                  <p className="text-[11px] text-gray-500 dark:text-gray-400">概要 / クリエイティブ / テキスト / 分析 / LP / 品質</p>
                </div>
                <button className="rounded-lg border border-gray-200 px-3 py-1.5 text-[11px] font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800" onClick={refreshAd360}>再読込</button>
              </div>

              {ad360Loading ? <Panel title="ad360"><Loader /></Panel> : null}
              {ad360Error ? <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-[12px] text-red-700">{ad360Error}</div> : null}
              {ad360 ? (
                <>
                  <SectionPanel title="概要" section={ad360.sections.core} busy={actionLoading === "media"} onRetry={() => retrySection("core")} />
                  <SectionPanel title="クリエイティブ" section={ad360.sections.creative} busy={actionLoading === "media"} onRetry={() => retrySection("creative")} />
                  <SectionPanel title="テキスト" section={ad360.sections.text} busy={actionLoading === "media"} onRetry={() => retrySection("text")} />
                  <SectionPanel title="分析" section={ad360.sections.analysis} busy={actionLoading === "reclassify"} onRetry={() => retrySection("analysis")} extra={dictionaryResult ? <TagList label="辞書候補" items={dictionaryResult.candidate_terms.map((item) => `${item.term} (${item.topic_label}, ${Math.round(item.confidence * 100)}%)`)} /> : null} />
                  <SectionPanel title="LP" section={ad360.sections.lp} busy={actionLoading === "lp"} onRetry={() => retrySection("lp")} />
                  <SectionPanel title="品質" section={ad360.sections.quality} busy={actionLoading === "media"} onRetry={() => retrySection("quality")} />
                </>
              ) : null}
            </div>
          </div>
        </div>

        <div className="px-5 pb-2"><CreativeIntelligence adId={ad.ad_id} /></div>
        <div className="px-5 pb-2"><HitPrediction adId={ad.ad_id} /></div>
        <div className="px-5 pb-2"><SimilarAdsPanel adId={ad.ad_id} onAdSelect={onAdSelect} /></div>
        <div className="px-5 pb-2"><AdAnnotations adId={ad.ad_id} /></div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 bg-gray-50 px-5 py-3 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex flex-wrap gap-2">
            <button
              className="rounded-lg bg-[#4A7DFF] px-3 py-1.5 text-[12px] font-medium text-white hover:bg-[#3a6ae8] disabled:cursor-not-allowed disabled:bg-blue-200"
              onClick={() => {
                if (!lpTrust.finalUrl) {
                  toast.error("LP遷移先が未解決です");
                  return;
                }
                window.open(lpTrust.finalUrl, "_blank", "noopener,noreferrer");
              }}
              disabled={!lpTrust.finalUrl}
            >
              最終LPを見る
            </button>
            {ad.ad_url ? <button className="rounded-lg bg-gray-100 px-3 py-1.5 text-[12px] font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300" onClick={() => window.open(ad.ad_url, "_blank", "noopener,noreferrer")}>広告を確認</button> : null}
            <button className="rounded-lg bg-purple-50 px-3 py-1.5 text-[12px] font-medium text-purple-600 hover:bg-purple-100" onClick={() => void handleLPCrawl()}>再クロール</button>
            <button className="rounded-lg bg-gray-100 px-3 py-1.5 text-[12px] font-medium text-gray-700 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300" onClick={() => copyToClipboard(lpTrust.finalUrl || ad.destination_url || ad.ad_url || "").then(() => toast.success("URLをコピーしました"))}>URLコピー</button>
          </div>
          <button onClick={onClose} className="rounded-lg px-4 py-1.5 text-[12px] font-medium text-gray-600 hover:bg-gray-200 dark:text-gray-300">閉じる</button>
        </div>
      </div>
    </div>
  );
}

function Loader() {
  return (
    <div className="flex items-center justify-center py-3">
      <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#4A7DFF] border-t-transparent" />
      <span className="ml-2 text-[10px] text-gray-400 dark:text-gray-500">読み込み中...</span>
    </div>
  );
}

function ActionButton({ label, busy, onClick, tone }: { label: string; busy?: boolean; onClick: () => void; tone: "blue" | "amber" | "emerald" }) {
  const styles = {
    blue: "bg-blue-50 text-blue-700 hover:bg-blue-100",
    amber: "bg-amber-50 text-amber-700 hover:bg-amber-100",
    emerald: "bg-emerald-50 text-emerald-700 hover:bg-emerald-100",
  }[tone];
  return <button className={`rounded-lg px-3 py-1.5 text-[11px] font-medium disabled:opacity-60 ${styles}`} onClick={onClick} disabled={busy}>{busy ? "実行中..." : label}</button>;
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800/60">
      <h3 className="mb-3 text-[13px] font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function MetricBar({ score, scoreColor }: { score: number; scoreColor: string }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[11px] text-gray-500 dark:text-gray-400">ヒットスコア</span>
        <span className="text-[18px] font-bold" style={{ color: scoreColor }}>{score}<span className="ml-1 text-[11px] text-gray-400 dark:text-gray-500">/ 100</span></span>
      </div>
      <div className="h-2 rounded-full bg-gray-200 dark:bg-gray-700">
        <div className="h-full rounded-full" style={{ width: `${score}%`, backgroundColor: scoreColor }} />
      </div>
    </div>
  );
}

function SummaryRow({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="grid gap-2 md:grid-cols-[88px_1fr]">
      <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-gray-400 dark:text-gray-500">{label}</p>
      {values.length > 0 ? <div className="flex flex-wrap gap-1.5">{values.map((item) => <span key={`${label}-${item}`} className="rounded-full bg-gray-100 px-2 py-1 text-[10px] text-gray-700 dark:bg-gray-700 dark:text-gray-100">{item}</span>)}</div> : <p className="text-[11px] text-gray-400 dark:text-gray-500">未取得</p>}
    </div>
  );
}

function SummaryText({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-2 md:grid-cols-[88px_1fr]">
      <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-gray-400 dark:text-gray-500">{label}</p>
      <p className="text-[12px] leading-relaxed text-gray-700 dark:text-gray-200">{value || "未取得"}</p>
    </div>
  );
}

function TagList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="space-y-2">
      <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-gray-400 dark:text-gray-500">{label}</p>
      {items.length > 0 ? <div className="flex flex-wrap gap-1.5">{items.map((item) => <span key={`${label}-${item}`} className="rounded-full bg-gray-100 px-2 py-1 text-[10px] text-gray-700 dark:bg-gray-700 dark:text-gray-100">{item}</span>)}</div> : <p className="text-[11px] text-gray-400 dark:text-gray-500">未取得</p>}
    </div>
  );
}

function SectionPanel({ title, section, busy, onRetry, extra }: { title: string; section: Ad360Section; busy?: boolean; onRetry: () => void; extra?: React.ReactNode }) {
  const rows = Object.entries(section.data).slice(0, 8).map(([key, value]) => {
    if (Array.isArray(value)) return [key, value.length > 0 ? value.join(", ") : "未取得"] as const;
    if (typeof value === "object" && value !== null) return [key, JSON.stringify(value)] as const;
    return [key, asText(value)] as const;
  });
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800/60">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-[13px] font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
        <ActionButton label="再取得" busy={busy} onClick={onRetry} tone="blue" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        {rows.map(([label, value]) => (
          <div key={label} className="rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-900/40">
            <p className="text-[10px] text-gray-400 dark:text-gray-500">{label}</p>
            <p className="mt-0.5 break-words text-[12px] font-medium text-gray-800 dark:text-gray-100">{value}</p>
          </div>
        ))}
      </div>
      {extra}
      <TagList label="欠損項目" items={section.missing_fields.map((item) => renderField(item))} />
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-gray-50 px-3 py-2.5 dark:bg-gray-800">
      <p className="text-[10px] font-medium text-gray-400 dark:text-gray-500">{label}</p>
      <p className="mt-0.5 text-[15px] font-bold text-gray-900 dark:text-gray-100">{value}</p>
    </div>
  );
}

function MetaItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="px-3 py-2">
      <p className="mb-0.5 text-[10px] text-gray-400 dark:text-gray-500">{label}</p>
      {children}
    </div>
  );
}
