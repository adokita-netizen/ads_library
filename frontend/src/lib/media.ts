"use client";

import { fetchApi } from "@/lib/api";

export interface MediaStatus {
  viewable?: boolean;
  downloadable?: boolean;
  has_lp?: boolean;
  primary_type?: string;
  missing_reasons?: string[];
}

const mediaReasonAliases: Record<string, string> = {
  missing_media: "missing_creative",
  missing_lp: "lp_missing",
};

interface BulkDownloadResponse {
  download_url: string;
  file_count: number;
  total_size_bytes: number;
  zip_filename: string;
  skipped_ids?: number[];
  skipped_reason_code?: string | null;
}

const failureMessages: Record<string, string> = {
  no_cached_media: "保存済み素材がありません",
  zip_creation_failed: "ZIPの生成に失敗しました",
  invalid_ad_ids: "ダウンロード対象が不正です",
  download_file_missing: "ダウンロードファイルが見つかりません",
  missing_creative: "素材が不足しています",
  lp_missing: "LPが取得できていません",
  missing_media: "素材が不足しています",
  missing_lp: "LPが取得できていません",
  lp_unresolved: "LPの解決先が未確定です",
  stale_creative: "素材の取得状態が古くなっています",
  download_unavailable: "ダウンロード可能な素材がありません",
  snapshot_only: "スナップショットのみ確認できます",
  dead: "LPが無効です",
  unresolved: "解決先を判定できていません",
  unreachable: "LPへ到達できません",
  domain_mismatch: "遷移先ドメインが一致しません",
};

export function getDownloadFailureMessage(error: unknown): string {
  const detail = (error as { data?: { detail?: { failure_reason_code?: string; message?: string } } })?.data?.detail;
  const code = detail?.failure_reason_code;
  if (code && failureMessages[code]) {
    return failureMessages[code];
  }
  return detail?.message || "ダウンロードに失敗しました";
}

export function getMediaReasonMessage(reason: string): string {
  return failureMessages[normalizeMediaReason(reason)] || "不明";
}

export function normalizeMediaReason(reason: string): string {
  return mediaReasonAliases[reason] || reason;
}

export function normalizeMediaReasons(reasons: string[] | undefined): string[] {
  if (!reasons?.length) {
    return [];
  }
  return Array.from(new Set(reasons.map((reason) => normalizeMediaReason(reason))));
}

export function openCreativeDownload(adId: number) {
  window.open(`/api/v1/media/download/${adId}`, "_blank", "noopener,noreferrer");
}

export async function bulkDownloadCreatives(adIds: number[]) {
  const uniqueAdIds = Array.from(new Set(adIds)).filter((id) => Number.isFinite(id));
  if (uniqueAdIds.length === 0) {
    throw new Error("No ads selected");
  }

  const result = await fetchApi<BulkDownloadResponse>("/media/bulk-download", {
    method: "POST",
    body: { ad_ids: uniqueAdIds },
  });

  window.open(result.download_url, "_blank", "noopener,noreferrer");
  return result;
}
