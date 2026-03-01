"use client";

import React, { useState, useEffect, useCallback } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";

interface Report {
  id: string | number;
  type: string;
  format: string;
  status: string;
  created_at?: string;
  download_url?: string;
  file_size?: number;
}

interface ReportGeneratorProps {
  genre?: string;
  onViewReport?: (report: Report) => void;
}

const reportTypes = [
  { value: "full_analysis", label: "総合分析レポート", description: "全ジャンル・全広告の分析" },
  { value: "genre_report", label: "ジャンルレポート", description: "指定ジャンルの詳細分析" },
  { value: "competitor_report", label: "競合レポート", description: "競合分析・マーケットシェア" },
  { value: "creative_report", label: "クリエイティブレポート", description: "勝ちパターン・トレンド分析" },
];

export default function ReportGenerator({ genre, onViewReport }: ReportGeneratorProps) {
  const [reportType, setReportType] = useState("full_analysis");
  const [format, setFormat] = useState<"json" | "html">("html");
  const [selectedGenre, setSelectedGenre] = useState(genre || "all");
  const [advertiser, setAdvertiser] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [generating, setGenerating] = useState(false);
  const [reports, setReports] = useState<Report[]>([]);
  const [reportsLoading, setReportsLoading] = useState(true);

  const loadReports = useCallback(async () => {
    setReportsLoading(true);
    try {
      const res = await fetchApi<{ items?: Report[]; reports?: Report[] }>("/rankings/reports").catch(() => null);
      if (res) {
        const items = res.items || res.reports || (Array.isArray(res) ? res : []);
        setReports(Array.isArray(items) ? items : []);
      }
    } finally {
      setReportsLoading(false);
    }
  }, []);

  useEffect(() => { loadReports(); }, [loadReports]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const body: Record<string, string | undefined> = {
        type: reportType,
        format,
        genre: selectedGenre !== "all" ? selectedGenre : undefined,
        advertiser: advertiser.trim() || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      };
      await fetchApi("/rankings/reports/generate", { method: "POST", body });
      toast.success("レポート生成を開始しました");
      loadReports();
    } catch {
      toast.error("レポート生成に失敗しました");
    } finally {
      setGenerating(false);
    }
  };

  const [deletingReportId, setDeletingReportId] = useState<string | number | null>(null);

  const handleDelete = async (id: string | number) => {
    if (deletingReportId !== null) return;
    setDeletingReportId(id);
    try {
      await fetchApi(`/rankings/reports/${id}`, { method: "DELETE" });
      toast.success("レポートを削除しました");
      setReports((prev) => prev.filter((r) => r.id !== id));
    } catch {
      toast.error("削除に失敗しました");
    } finally {
      setDeletingReportId(null);
    }
  };

  const typeLabel = (type: string) => reportTypes.find((t) => t.value === type)?.label || type;

  const statusBadge = (status: string) => {
    switch (status) {
      case "completed": return <span className="text-[8px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 font-medium">完了</span>;
      case "generating": return <span className="text-[8px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-medium">生成中</span>;
      case "failed": return <span className="text-[8px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-medium">失敗</span>;
      default: return <span className="text-[8px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">{status}</span>;
    }
  };

  return (
    <div className="space-y-4">
      {/* Generator card */}
      <div className="card px-4 py-4 space-y-4">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
          <h3 className="text-[13px] font-bold text-gray-900">レポート生成</h3>
        </div>

        {/* Report type selection */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {reportTypes.map((t) => (
            <button
              key={t.value}
              onClick={() => setReportType(t.value)}
              className={`px-3 py-2 rounded-lg border text-left transition-all ${
                reportType === t.value
                  ? "border-[#4A7DFF] bg-blue-50 ring-1 ring-[#4A7DFF]"
                  : "border-gray-200 hover:border-gray-300"
              }`}
            >
              <p className="text-[10px] font-medium text-gray-900">{t.label}</p>
              <p className="text-[8px] text-gray-400 mt-0.5">{t.description}</p>
            </button>
          ))}
        </div>

        {/* Filters row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <div>
            <label className="text-[9px] text-gray-400 block mb-0.5">ジャンル</label>
            <select value={selectedGenre} onChange={(e) => setSelectedGenre(e.target.value)} className="select-filter text-[10px] h-7 w-full">
              {genreOptions.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-[9px] text-gray-400 block mb-0.5">広告主</label>
            <input
              type="text"
              placeholder="広告主名"
              value={advertiser}
              onChange={(e) => setAdvertiser(e.target.value)}
              className="w-full h-7 px-2 rounded-lg border border-gray-200 text-[10px] text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]"
            />
          </div>
          <div>
            <label className="text-[9px] text-gray-400 block mb-0.5">期間</label>
            <div className="flex items-center gap-1">
              <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="flex-1 h-7 px-1.5 rounded-lg border border-gray-200 text-[9px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]" />
              <span className="text-[9px] text-gray-400">〜</span>
              <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="flex-1 h-7 px-1.5 rounded-lg border border-gray-200 text-[9px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF]" />
            </div>
          </div>
          <div>
            <label className="text-[9px] text-gray-400 block mb-0.5">フォーマット</label>
            <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5 h-7">
              {(["html", "json"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFormat(f)}
                  className={`flex-1 h-full rounded text-[9px] transition-colors ${
                    format === f ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"
                  }`}
                >
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        <button
          onClick={handleGenerate}
          disabled={generating}
          className="btn-primary text-[11px] h-8 px-5 flex items-center gap-1.5"
        >
          {generating ? (
            <>
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
              生成中...
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m3.75 9v6m3-3H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
              レポートを生成
            </>
          )}
        </button>
      </div>

      {/* Report history */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
          <h4 className="text-[12px] font-bold text-gray-900">レポート履歴</h4>
          {reports.length > 0 && <span className="text-[9px] text-gray-400">{reports.length}件</span>}
        </div>

        {reportsLoading ? (
          <div className="p-4 space-y-2 animate-pulse">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="h-3 bg-gray-200 rounded w-32" />
                <div className="h-3 bg-gray-100 rounded w-16" />
                <div className="h-3 bg-gray-100 rounded w-20" />
              </div>
            ))}
          </div>
        ) : reports.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-[11px] text-gray-400">レポートがありません</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-50">
            {reports.map((r) => (
              <div key={r.id} className="px-4 py-2.5 flex items-center gap-3 hover:bg-gray-50/50 transition-colors">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] font-medium text-gray-900">{typeLabel(r.type)}</span>
                    {statusBadge(r.status)}
                    <span className="text-[8px] px-1 py-0.5 rounded bg-gray-100 text-gray-500">{r.format.toUpperCase()}</span>
                  </div>
                  {r.created_at && (
                    <p className="text-[9px] text-gray-400 mt-0.5">
                      {new Date(r.created_at).toLocaleString("ja-JP", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                      {r.file_size != null && <span className="ml-2">{(r.file_size / 1024).toFixed(0)}KB</span>}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  {r.status === "completed" && (
                    <>
                      <button
                        className="text-[10px] px-2 py-1 rounded bg-[#4A7DFF] text-white hover:bg-[#3a6ae8] transition-colors"
                        onClick={() => onViewReport?.(r)}
                      >
                        表示
                      </button>
                      <button
                        className="text-[10px] px-2 py-1 rounded bg-emerald-50 text-emerald-600 hover:bg-emerald-100 transition-colors"
                        onClick={() => {
                          const url = r.download_url || `/api/v1/rankings/reports/${r.id}/download`;
                          window.open(url, "_blank", "noopener,noreferrer");
                        }}
                      >
                        DL
                      </button>
                    </>
                  )}
                  <button
                    className="text-gray-400 hover:text-red-500 transition-colors p-0.5"
                    onClick={() => handleDelete(r.id)}
                    title="削除"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
