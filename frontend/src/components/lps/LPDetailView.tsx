"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import type { LPMirrorInfo, LPAssetInfo, LPRedirectStep } from "@/types";
import LPPreviewFrame from "./LPPreviewFrame";
import LPEvidencePanel from "./LPEvidencePanel";
import LPSourcePanel from "./LPSourcePanel";
import LPAssetTable from "./LPAssetTable";
import LPRedirectChain from "./LPRedirectChain";

interface LPDetailViewProps {
  onBack?: () => void;
  initialSnapshotId?: number;
}

type DetailTab = "preview" | "evidence" | "source";

const TAB_CONFIG: { id: DetailTab; label: string; icon: JSX.Element }[] = [
  {
    id: "preview",
    label: "プレビュー",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    id: "evidence",
    label: "エビデンス",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
      </svg>
    ),
  },
  {
    id: "source",
    label: "ソース",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
      </svg>
    ),
  },
];

const MIRROR_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  built: { label: "ビルド完了", color: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300" },
  building: { label: "ビルド中", color: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300" },
  pending: { label: "未ビルド", color: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400" },
  failed: { label: "ビルド失敗", color: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300" },
};

export default function LPDetailView({ onBack, initialSnapshotId }: LPDetailViewProps) {
  const [snapshotId, setSnapshotId] = useState<number>(initialSnapshotId || 0);
  const [snapshotIdInput, setSnapshotIdInput] = useState<string>(String(initialSnapshotId || ""));
  const [activeTab, setActiveTab] = useState<DetailTab>("preview");

  const [mirror, setMirror] = useState<LPMirrorInfo | null>(null);
  const [assets, setAssets] = useState<LPAssetInfo[]>([]);
  const [redirectChain, setRedirectChain] = useState<LPRedirectStep[]>([]);
  const [sourceHtml, setSourceHtml] = useState<string>("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [building, setBuilding] = useState(false);

  const loadMirrorData = useCallback(async (id: number) => {
    if (!id) return;
    setLoading(true);
    setError(null);

    try {
      const data = await fetchApi<LPMirrorInfo>(`/rankings/lp-mirror/${id}`);
      setMirror(data);

      // Load assets and redirect chain in parallel
      const [assetsData, chainData] = await Promise.allSettled([
        fetchApi<{ assets: LPAssetInfo[] }>(`/rankings/lp-mirror/${id}/assets`),
        fetchApi<{ chain: LPRedirectStep[] }>(`/rankings/lp-mirror/${id}/redirect-chain`),
      ]);

      if (assetsData.status === "fulfilled") setAssets(assetsData.value.assets || []);
      if (chainData.status === "fulfilled") setRedirectChain(chainData.value.chain || []);

      // Load source if available
      if (data.source_html) {
        setSourceHtml(data.source_html);
      } else {
        try {
          const srcData = await fetchApi<{ html: string }>(`/rankings/lp-mirror/${id}/source`);
          setSourceHtml(srcData.html || "");
        } catch {
          setSourceHtml("");
        }
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`ミラーデータの取得に失敗しました: ${message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (snapshotId > 0) {
      loadMirrorData(snapshotId);
    }
  }, [snapshotId, loadMirrorData]);

  const handleBuildMirror = async () => {
    if (!snapshotId) return;
    setBuilding(true);
    try {
      await fetchApi<{ status: string }>(`/rankings/lp-mirror/${snapshotId}/build`, { method: "POST" });
      // Reload after build trigger
      await loadMirrorData(snapshotId);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(`ミラービルドの開始に失敗しました: ${message}`);
    } finally {
      setBuilding(false);
    }
  };

  const handleLoadSnapshot = () => {
    const id = parseInt(snapshotIdInput, 10);
    if (id > 0) {
      setSnapshotId(id);
    }
  };

  const statusInfo = mirror?.mirror_status ? MIRROR_STATUS_LABELS[mirror.mirror_status] || { label: mirror.mirror_status, color: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400" } : null;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-3 px-5 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shrink-0">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-[11px] font-medium text-gray-600 dark:text-gray-300 transition-colors hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
            戻る
          </button>
        )}
        <h2 className="text-[15px] font-bold text-gray-900 dark:text-gray-100">LP詳細プレビュー</h2>

        {/* Snapshot ID input */}
        <div className="flex items-center gap-1.5 ml-auto">
          <label className="text-[11px] text-gray-500 dark:text-gray-400">スナップショットID:</label>
          <input
            type="number"
            value={snapshotIdInput}
            onChange={(e) => setSnapshotIdInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLoadSnapshot()}
            className="w-24 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-[12px] text-gray-700 dark:text-gray-200"
            placeholder="ID"
            min={1}
          />
          <button
            onClick={handleLoadSnapshot}
            className="px-3 py-1 rounded-md bg-blue-600 text-white text-[11px] font-medium hover:bg-blue-700 transition-colors"
          >
            読み込み
          </button>
        </div>
      </div>

      {/* Status bar */}
      {mirror && (
        <div className="flex flex-wrap items-center gap-3 px-5 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 shrink-0">
          {statusInfo && (
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusInfo.color}`}>
              {statusInfo.label}
            </span>
          )}
          {mirror.domain && (
            <span className="text-[11px] text-gray-500 dark:text-gray-400">
              ドメイン: <span className="font-medium text-gray-700 dark:text-gray-200">{mirror.domain}</span>
            </span>
          )}
          {mirror.asset_count > 0 && (
            <span className="text-[11px] text-gray-500 dark:text-gray-400">
              アセット: <span className="font-medium text-gray-700 dark:text-gray-200">{mirror.asset_count}</span>
            </span>
          )}
          {mirror.total_byte_size > 0 && (
            <span className="text-[11px] text-gray-500 dark:text-gray-400">
              合計サイズ: <span className="font-medium text-gray-700 dark:text-gray-200">{(mirror.total_byte_size / (1024 * 1024)).toFixed(2)} MB</span>
            </span>
          )}

          {/* Build button */}
          {(!mirror.mirror_status || mirror.mirror_status === "pending" || mirror.mirror_status === "failed") && (
            <button
              onClick={handleBuildMirror}
              disabled={building}
              className="ml-auto inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-blue-600 text-white text-[11px] font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {building ? (
                <>
                  <div className="w-3 h-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  ビルド中...
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17l-5.384 3.079A2.25 2.25 0 013 16.225V7.775a2.25 2.25 0 013.036-2.024l5.384 3.079M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  ミラーをビルド
                </>
              )}
            </button>
          )}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-blue-600 border-t-transparent animate-spin" />
            <p className="text-[12px] text-gray-400 dark:text-gray-500">データを読み込み中...</p>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="mx-5 mt-4 p-4 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800">
          <div className="flex items-start gap-2">
            <svg className="w-5 h-5 text-red-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            <div>
              <p className="text-[12px] font-medium text-red-700 dark:text-red-300">{error}</p>
              <button
                onClick={() => snapshotId > 0 && loadMirrorData(snapshotId)}
                className="mt-2 text-[11px] text-red-600 dark:text-red-400 underline hover:no-underline"
              >
                再試行
              </button>
            </div>
          </div>
        </div>
      )}

      {/* No snapshot selected */}
      {!snapshotId && !loading && !error && (
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-3 text-gray-400 dark:text-gray-500">
            <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            <p className="text-[13px] font-medium">スナップショットIDを入力してください</p>
            <p className="text-[11px]">上部のフィールドにスナップショットIDを入力して読み込みボタンを押してください</p>
          </div>
        </div>
      )}

      {/* Main content */}
      {mirror && !loading && !error && (
        <>
          {/* Tabs */}
          <div className="flex items-center gap-1 px-5 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shrink-0">
            {TAB_CONFIG.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors ${
                  activeTab === tab.id
                    ? "bg-blue-50 dark:bg-blue-950 text-blue-600 dark:text-blue-400 shadow-sm"
                    : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800"
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-auto min-h-0">
            {activeTab === "preview" && mirror.mirror_url ? (
              <div className="flex flex-col h-full">
                <div className="flex-1 min-h-[400px]">
                  <LPPreviewFrame
                    mirrorUrl={mirror.mirror_url}
                    fidelityScore={mirror.fidelity_score}
                    fidelityLevel={mirror.fidelity_level}
                    originalDomain={mirror.domain}
                    capturedAt={mirror.captured_at}
                  />
                </div>

                {/* Redirect chain */}
                {redirectChain.length > 0 && (
                  <div className="border-t border-gray-200 dark:border-gray-700">
                    <div className="px-5 py-2 bg-gray-50 dark:bg-gray-800/50">
                      <h3 className="text-[12px] font-semibold text-gray-700 dark:text-gray-200">リダイレクトチェーン ({redirectChain.length} ステップ)</h3>
                    </div>
                    <LPRedirectChain chain={redirectChain} />
                  </div>
                )}

                {/* Asset table */}
                {assets.length > 0 && (
                  <div className="border-t border-gray-200 dark:border-gray-700">
                    <div className="px-5 py-2 bg-gray-50 dark:bg-gray-800/50">
                      <h3 className="text-[12px] font-semibold text-gray-700 dark:text-gray-200">アセット一覧 ({assets.length} 件)</h3>
                    </div>
                    <LPAssetTable assets={assets} />
                  </div>
                )}
              </div>
            ) : activeTab === "preview" && !mirror.mirror_url ? (
              <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-400 dark:text-gray-500">
                <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <p className="text-[13px] font-medium">ミラーURLが利用できません</p>
                <p className="text-[11px]">ミラーをビルドしてプレビューを表示してください</p>
                <button
                  onClick={handleBuildMirror}
                  disabled={building}
                  className="mt-2 px-4 py-1.5 rounded-md bg-blue-600 text-white text-[11px] font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {building ? "ビルド中..." : "ミラーをビルド"}
                </button>
              </div>
            ) : null}

            {activeTab === "evidence" && (
              <LPEvidencePanel
                snapshotId={snapshotId}
                screenshots={mirror.screenshots || {}}
              />
            )}

            {activeTab === "source" && (
              sourceHtml ? (
                <LPSourcePanel sourceHtml={sourceHtml} />
              ) : (
                <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-400 dark:text-gray-500">
                  <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
                  </svg>
                  <p className="text-[13px] font-medium">ソースHTMLが利用できません</p>
                </div>
              )
            )}
          </div>
        </>
      )}
    </div>
  );
}
