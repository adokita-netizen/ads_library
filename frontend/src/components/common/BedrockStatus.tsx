"use client";

import React from "react";

export type ProvenanceKind = "ai" | "rule" | "manual";
export type PriorityKind = "high" | "medium" | "low";
export type ConfidenceBand = "high" | "medium" | "low";

export interface BedrockStatusInfo {
  aiProduct: string;
  provenance: ProvenanceKind;
  priority: PriorityKind;
  priorityScore: number;
  reviewRequired: boolean;
  reviewReason?: string;
  confidence: number;
  confidenceBand: ConfidenceBand;
  matchedTerms: string[];
}

const asText = (value: unknown) => String(value || "").trim();

const asNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const asBoolean = (value: unknown): boolean => {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return ["true", "1", "yes"].includes(value.trim().toLowerCase());
  return false;
};

const asList = (value: unknown): string[] =>
  Array.isArray(value) ? value.map((item) => String(item || "").trim()).filter(Boolean) : [];

function getMeta(source: Record<string, unknown> | null | undefined) {
  return ((source?.ad_metadata as Record<string, unknown> | undefined) || (source?.metadata as Record<string, unknown> | undefined) || {}) as Record<string, unknown>;
}

function deriveProvenance(sourceRaw: string, confidence: number, matchedTerms: string[]): ProvenanceKind {
  const raw = sourceRaw.toLowerCase();
  if (raw.includes("manual")) return "manual";
  if (raw.includes("rule") || raw.includes("heuristic")) return "rule";
  if (raw.includes("bedrock") || raw.includes("ai") || raw.includes("comprehend")) return "ai";
  if (confidence > 0 || matchedTerms.length > 0) return "ai";
  return "rule";
}

function derivePriority(explicit: string, score: number): PriorityKind {
  const raw = explicit.toLowerCase();
  if (raw === "high" || raw === "medium" || raw === "low") return raw;
  if (score >= 80) return "high";
  if (score >= 50) return "medium";
  return "low";
}

function deriveConfidenceBand(confidence: number): ConfidenceBand {
  if (confidence >= 0.8) return "high";
  if (confidence >= 0.6) return "medium";
  return "low";
}

export function deriveBedrockStatus(source: Record<string, unknown> | null | undefined): BedrockStatusInfo {
  const meta = getMeta(source);
  const aiProduct = asText(
    source?.topic_label ??
    source?.ai_product ??
    source?.product_label ??
    meta.topic_label ??
    meta.ai_product ??
    meta.product_label,
  );
  const confidence = asNumber(
    source?.topic_confidence ??
    source?.classification_confidence ??
    source?.confidence ??
    meta.topic_confidence ??
    meta.classification_confidence ??
    meta.confidence,
  ) ?? 0;
  const matchedTerms = asList(source?.matched_terms ?? source?.topic_terms ?? meta.matched_terms ?? meta.topic_terms);
  const sourceRaw = asText(
    source?.topic_provenance ??
    source?.classification_provenance ??
    source?.topic_source ??
    source?.classification_source ??
    meta.topic_provenance ??
    meta.classification_provenance ??
    meta.topic_source ??
    meta.classification_source ??
    meta.language_source,
  );
  const priorityScore = asNumber(
    source?.priority_score ??
    source?.actual_metrics_priority_score ??
    meta.priority_score ??
    meta.actual_metrics_priority_score,
  ) ?? 0;
  const explicitPriority = asText(
    source?.priority ??
    source?.priority_level ??
    source?.actual_metrics_priority ??
    meta.priority ??
    meta.priority_level ??
    meta.actual_metrics_priority,
  );
  const reviewRequired = asBoolean(
    source?.review_required ??
    source?.needs_topic_review ??
    meta.review_required ??
    meta.needs_topic_review,
  );
  const explicitReviewReason = asText(source?.review_reason ?? meta.review_reason);
  const reviewReason =
    explicitReviewReason ||
    (reviewRequired && confidence < 0.6 ? "low_confidence" : "") ||
    (reviewRequired && matchedTerms.length === 0 ? "evidence_missing" : "") ||
    undefined;

  return {
    aiProduct,
    provenance: deriveProvenance(sourceRaw, confidence, matchedTerms),
    priority: derivePriority(explicitPriority, priorityScore),
    priorityScore,
    reviewRequired,
    reviewReason,
    confidence,
    confidenceBand: deriveConfidenceBand(confidence),
    matchedTerms,
  };
}

function provenanceTone(provenance: ProvenanceKind): string {
  if (provenance === "manual") return "bg-rose-100 text-rose-700 border-rose-200";
  if (provenance === "rule") return "bg-slate-100 text-slate-700 border-slate-200";
  return "bg-indigo-100 text-indigo-700 border-indigo-200";
}

function priorityTone(priority: PriorityKind): string {
  if (priority === "high") return "bg-amber-100 text-amber-700 border-amber-200";
  if (priority === "medium") return "bg-sky-100 text-sky-700 border-sky-200";
  return "bg-gray-100 text-gray-600 border-gray-200";
}

function confidenceTone(band: ConfidenceBand): string {
  if (band === "high") return "bg-emerald-100 text-emerald-700 border-emerald-200";
  if (band === "medium") return "bg-amber-100 text-amber-700 border-amber-200";
  return "bg-rose-100 text-rose-700 border-rose-200";
}

export function ProvenanceBadge({ provenance }: { provenance: ProvenanceKind }) {
  const label = provenance === "manual" ? "手動" : provenance === "rule" ? "ルール" : "AI";
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${provenanceTone(provenance)}`}>{label}</span>;
}

export function PriorityBadge({ priority }: { priority: PriorityKind }) {
  const label = priority === "high" ? "高優先" : priority === "medium" ? "中優先" : "低優先";
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${priorityTone(priority)}`}>{label}</span>;
}

export function ConfidenceBandBadge({ band }: { band: ConfidenceBand }) {
  const label = band === "high" ? "高信頼" : band === "medium" ? "中信頼" : "低信頼";
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${confidenceTone(band)}`}>{label}</span>;
}

export function ReviewRequiredBadge({ required }: { required: boolean }) {
  return required ? (
    <span className="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-medium text-rose-700">要確認</span>
  ) : (
    <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">確認済み</span>
  );
}
