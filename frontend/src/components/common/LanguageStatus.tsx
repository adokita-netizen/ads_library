"use client";

import React from "react";

export type LanguageStatusKind = "jp" | "non-jp" | "unknown";

export interface LanguageStatusInfo {
  kind: LanguageStatusKind;
  label: string;
  sourceLabel?: string;
  sourceRaw?: string;
  isAi: boolean;
  excluded: boolean;
  excludeReason?: string;
  ratio?: number | null;
}

function normalizeLanguage(value: unknown): string {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "";
  if (["ja", "jp", "ja-jp", "japanese"].includes(raw)) return "ja";
  if (["non-ja", "non-jp", "non_jp", "en", "english"].includes(raw)) return "non-ja";
  return raw;
}

function asBoolean(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return value.toLowerCase() === "true";
  return false;
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function getSourceLabel(sourceRaw: string): string | undefined {
  if (!sourceRaw) return undefined;
  if (sourceRaw.includes("bedrock")) return "AI判定";
  if (sourceRaw.includes("comprehend")) return "AI判定";
  if (sourceRaw.includes("ai")) return "AI判定";
  if (sourceRaw.includes("rule")) return "ルール判定";
  if (sourceRaw.includes("heuristic")) return "ルール判定";
  return undefined;
}

export function deriveLanguageStatus(source: Record<string, unknown> | null | undefined): LanguageStatusInfo {
  const meta = ((source?.ad_metadata as Record<string, unknown> | undefined) || (source?.metadata as Record<string, unknown> | undefined) || {}) as Record<string, unknown>;
  const language = normalizeLanguage(source?.language ?? meta.language);
  const sourceRaw = String(source?.language_source ?? meta.language_source ?? "").trim().toLowerCase();
  const excluded = asBoolean(source?.exclude_from_analysis ?? meta.exclude_from_analysis);
  const excludeReason = String(source?.exclude_reason ?? meta.exclude_reason ?? "").trim() || undefined;
  const ratio = asNumber(source?.jp_char_ratio ?? meta.jp_char_ratio ?? source?.japanese_ratio ?? meta.japanese_ratio);

  let kind: LanguageStatusKind = "unknown";
  if (language === "ja") kind = "jp";
  else if (language && language !== "unknown") kind = "non-jp";

  if (kind === "unknown" && ratio != null) {
    if (ratio >= 0.4) kind = "jp";
    else if (ratio < 0.1) kind = "non-jp";
  }

  return {
    kind,
    label: kind === "jp" ? "JP" : kind === "non-jp" ? "non-JP" : "未判定",
    sourceLabel: getSourceLabel(sourceRaw),
    sourceRaw: sourceRaw || undefined,
    isAi: sourceRaw.includes("bedrock") || sourceRaw.includes("ai") || sourceRaw.includes("comprehend"),
    excluded,
    excludeReason,
    ratio,
  };
}

function badgeTone(kind: LanguageStatusKind): string {
  if (kind === "jp") return "bg-emerald-100 text-emerald-700 border-emerald-200";
  if (kind === "non-jp") return "bg-slate-100 text-slate-700 border-slate-200";
  return "bg-amber-100 text-amber-700 border-amber-200";
}

export function LanguageStatusBadges({ info }: { info: LanguageStatusInfo }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${badgeTone(info.kind)}`}>
        {info.label}
      </span>
      {info.sourceLabel ? (
        <span className="inline-flex items-center rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700">
          {info.sourceLabel}
        </span>
      ) : null}
      {info.excluded ? (
        <span className="inline-flex items-center rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[10px] font-medium text-rose-700">
          除外
        </span>
      ) : null}
    </div>
  );
}

export function LanguageStatusWarning({ info }: { info: LanguageStatusInfo }) {
  if (!info.excluded) return null;
  return (
    <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[11px] text-rose-700">
      exclude_from_analysis=true
      {info.excludeReason ? ` / ${info.excludeReason}` : ""}
    </p>
  );
}
