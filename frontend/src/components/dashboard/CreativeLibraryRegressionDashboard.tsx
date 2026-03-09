"use client";

import { useEffect, useMemo, useState } from "react";
import { dataQualityApi } from "@/lib/api";
import type {
  CreativeLibraryAudit,
  CreativeLibraryAuditAd,
  CreativeLibraryAuditResponse,
  CreativeLibraryAuditRow,
  CreativeLibraryDailyChange,
} from "@/types";

function rateLabel(value: number | undefined) {
  const normalized = typeof value === "number" && Number.isFinite(value) ? value : 0;
  return `${Math.round(normalized * 100)}%`;
}

function toneClass(value: number | undefined) {
  const normalized = typeof value === "number" && Number.isFinite(value) ? value : 0;
  if (normalized >= 0.85) return "text-emerald-700 bg-emerald-50";
  if (normalized >= 0.6) return "text-amber-700 bg-amber-50";
  return "text-rose-700 bg-rose-50";
}

function severityClass(row: CreativeLibraryAuditRow) {
  const totalIssues = (row.missing_media_count || 0) + (row.download_unavailable_count || 0) + (row.lp_unresolved_count || 0);
  if (totalIssues >= 5) return "bg-rose-50 border-rose-200";
  if (totalIssues >= 2) return "bg-amber-50 border-amber-200";
  return "bg-emerald-50 border-emerald-200";
}

function issueSummary(row: CreativeLibraryAuditRow) {
  return [
    row.missing_media_count ? `素材欠損 ${row.missing_media_count}` : null,
    row.download_unavailable_count ? `DL不可 ${row.download_unavailable_count}` : null,
    row.lp_unresolved_count ? `LP未解決 ${row.lp_unresolved_count}` : null,
  ].filter(Boolean) as string[];
}

function changeBadge(item: CreativeLibraryDailyChange, fallback: "rose" | "emerald") {
  const isRecovery = item.direction === "recovered" || item.direction === "improved" || fallback === "emerald";
  return isRecovery ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700";
}

function PriorityReasons({ ad }: { ad: CreativeLibraryAuditAd }) {
  const reasons = ad.failure_reason_codes || [];
  const chips = reasons.length > 0
    ? reasons
    : [
        ad.needs_cr_recovery ? "missing_creative" : null,
        ad.needs_download_recovery ? "not_downloadable" : null,
        ad.needs_lp_resolution ? "lp_unresolved" : null,
      ].filter(Boolean) as string[];
  if (chips.length === 0) return <span className="text-[10px] text-gray-400">問題なし</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {chips.slice(0, 3).map((reason) => (
        <span key={reason} className="rounded bg-gray-100 px-2 py-0.5 text-[10px] text-gray-600">
          {reason}
        </span>
      ))}
    </div>
  );
}

export default function CreativeLibraryRegressionDashboard({ onAdSelect }: { onAdSelect: (adId: number) => void }) {
  const [audit, setAudit] = useState<CreativeLibraryAudit | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await dataQualityApi.getCreativeLibraryAudit({ top_n: 5 }) as CreativeLibraryAuditResponse;
        if (!cancelled) {
          setAudit(data.creative_library_audit);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Creative Library 監査の取得に失敗しました");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const worstPlatforms = useMemo(
    () => (audit?.platform_breakdown || []).slice().sort((a, b) => ((b.missing_media_count || 0) + (b.download_unavailable_count || 0) + (b.lp_unresolved_count || 0)) - ((a.missing_media_count || 0) + (a.download_unavailable_count || 0) + (a.lp_unresolved_count || 0))).slice(0, 3),
    [audit],
  );
  const worstGenres = useMemo(
    () => (audit?.genre_breakdown || []).slice().sort((a, b) => ((b.missing_media_count || 0) + (b.download_unavailable_count || 0) + (b.lp_unresolved_count || 0)) - ((a.missing_media_count || 0) + (a.download_unavailable_count || 0) + (a.lp_unresolved_count || 0))).slice(0, 3),
    [audit],
  );

  return (
    <div className="card px-4 py-4 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-[13px] font-bold text-gray-900">クリエイティブライブラリ回帰監視</h3>
          <p className="text-[10px] text-gray-400">CR / DL / LP の改善状況と悪化傾向を日次監査から可視化</p>
        </div>
      </div>

      {loading && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="rounded-lg bg-gray-50 px-3 py-3 animate-pulse">
              <div className="h-3 w-20 rounded bg-gray-200" />
              <div className="mt-2 h-6 w-16 rounded bg-gray-200" />
            </div>
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-[11px] text-rose-700">
          {error}
        </div>
      )}

      {!loading && !error && audit && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              { label: "閲覧可", value: audit.summary.creative_viewable_rate },
              { label: "DL可", value: audit.summary.creative_downloadable_rate },
              { label: "LPあり", value: audit.summary.lp_present_rate },
              { label: "LP解決済み", value: audit.summary.lp_resolved_rate },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border border-gray-200 bg-white px-3 py-3">
                <p className="text-[10px] text-gray-400">{item.label}</p>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`rounded px-2 py-0.5 text-[12px] font-semibold ${toneClass(item.value)}`}>{rateLabel(item.value)}</span>
                  <div className="h-1.5 flex-1 rounded-full bg-gray-100">
                    <div className={`h-full rounded-full ${item.value && item.value >= 0.85 ? "bg-emerald-500" : item.value && item.value >= 0.6 ? "bg-amber-500" : "bg-rose-500"}`} style={{ width: `${Math.max(4, Math.round((item.value || 0) * 100))}%` }} />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
              <div className="flex items-center justify-between">
                <h4 className="text-[12px] font-semibold text-gray-900">悪化上位</h4>
                <span className="text-[10px] text-gray-400">悪化広告</span>
              </div>
              <div className="mt-3 space-y-2">
                {(audit.creative_library_daily_report?.top_regressions || []).length === 0 ? (
                  <p className="text-[11px] text-gray-400">悪化広告はありません</p>
                ) : (
                  (audit.creative_library_daily_report?.top_regressions || []).slice(0, 5).map((item) => (
                    <button key={`reg-${item.ad_id}`} onClick={() => onAdSelect(item.ad_id)} className="flex w-full items-center justify-between rounded-lg bg-rose-50 px-3 py-2 text-left hover:bg-rose-100">
                      <div>
                        <p className="text-[11px] font-medium text-gray-900">{item.title}</p>
                        <p className="text-[10px] text-gray-500">{item.platform || "-"} / {item.genre || "-"}</p>
                      </div>
                      <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${changeBadge(item, "rose")}`}>{item.delta_score != null ? `${item.delta_score}` : "悪化"}</span>
                    </button>
                  ))
                )}
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
              <div className="flex items-center justify-between">
                <h4 className="text-[12px] font-semibold text-gray-900">改善上位</h4>
                <span className="text-[10px] text-gray-400">改善広告</span>
              </div>
              <div className="mt-3 space-y-2">
                {(audit.creative_library_daily_report?.top_recoveries || []).length === 0 ? (
                  <p className="text-[11px] text-gray-400">改善広告はありません</p>
                ) : (
                  (audit.creative_library_daily_report?.top_recoveries || []).slice(0, 5).map((item) => (
                    <button key={`rec-${item.ad_id}`} onClick={() => onAdSelect(item.ad_id)} className="flex w-full items-center justify-between rounded-lg bg-emerald-50 px-3 py-2 text-left hover:bg-emerald-100">
                      <div>
                        <p className="text-[11px] font-medium text-gray-900">{item.title}</p>
                        <p className="text-[10px] text-gray-500">{item.platform || "-"} / {item.genre || "-"}</p>
                      </div>
                      <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${changeBadge(item, "emerald")}`}>{item.delta_score != null ? `+${item.delta_score}` : "改善"}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-lg border border-gray-200 bg-white px-4 py-3 lg:col-span-1">
              <h4 className="text-[12px] font-semibold text-gray-900">優先復旧広告</h4>
              <div className="mt-3 space-y-2">
                {(audit.priority_recovery_ads || []).slice(0, 5).map((ad) => (
                  <button key={ad.ad_id} onClick={() => onAdSelect(ad.ad_id)} className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-left hover:bg-gray-100">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] font-medium text-gray-900">{ad.title}</p>
                      <span className="rounded bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">{Math.round(ad.priority_score || 0)}</span>
                    </div>
                    <p className="mt-0.5 text-[10px] text-gray-500">{ad.platform || "-"} / {ad.genre || "-"}</p>
                    <div className="mt-2">
                      <PriorityReasons ad={ad} />
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
              <h4 className="text-[12px] font-semibold text-gray-900">媒体別の悪化</h4>
              <div className="mt-3 space-y-2">
                {worstPlatforms.map((row) => (
                  <div key={row.label} className={`rounded-lg border px-3 py-2 ${severityClass(row)}`}>
                    <div className="flex items-center justify-between">
                      <p className="text-[11px] font-medium text-gray-900">{row.label}</p>
                      <span className="text-[10px] text-gray-500">{row.total_ads || 0}件</span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {issueSummary(row).map((item) => (
                        <span key={item} className="rounded bg-white px-2 py-0.5 text-[10px] text-gray-700">{item}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white px-4 py-3">
              <h4 className="text-[12px] font-semibold text-gray-900">ジャンル別の悪化</h4>
              <div className="mt-3 space-y-2">
                {worstGenres.map((row) => (
                  <div key={row.label} className={`rounded-lg border px-3 py-2 ${severityClass(row)}`}>
                    <div className="flex items-center justify-between">
                      <p className="text-[11px] font-medium text-gray-900">{row.label}</p>
                      <span className="text-[10px] text-gray-500">{row.total_ads || 0}件</span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {issueSummary(row).map((item) => (
                        <span key={item} className="rounded bg-white px-2 py-0.5 text-[10px] text-gray-700">{item}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
