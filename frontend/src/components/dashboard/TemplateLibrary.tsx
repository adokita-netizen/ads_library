"use client";

import React, { useState, useEffect, useMemo } from "react";
import toast from "react-hot-toast";
import { fetchApi } from "@/lib/api";
import { genreOptions } from "@/lib/constants";

// ─── Types ───

interface TemplateSection {
  label: string;
  description?: string;
}

interface Template {
  id: string;
  name: string;
  hit_rate: number;
  genres: string[];
  sections: TemplateSection[];
  description?: string;
  created_at?: string;
}

interface TemplateLibraryProps {
  onSelectTemplate?: (templateId: string) => void;
}

// ─── Mock Data ───

const MOCK_TEMPLATES: Template[] = [
  {
    id: "tmpl_001",
    name: "美容系・質問型フック・限定CTA",
    hit_rate: 78,
    genres: ["beauty", "health"],
    sections: [
      { label: "質問フック", description: "悩みに共感する質問で開始" },
      { label: "Before/After", description: "使用前後の変化を視覚的に提示" },
      { label: "成分解説", description: "独自成分・技術の信頼性を訴求" },
      { label: "口コミ紹介", description: "実際のユーザー体験談" },
      { label: "限定CTA", description: "初回限定○○%OFF+返金保証" },
    ],
    created_at: "2026-02-15",
  },
  {
    id: "tmpl_002",
    name: "EC・数字訴求・緊急型",
    hit_rate: 72,
    genres: ["ec_d2c", "food"],
    sections: [
      { label: "数字フック", description: "「累計100万個突破」等の実績数値" },
      { label: "USP提示", description: "競合との明確な差別化ポイント" },
      { label: "社会的証明", description: "ランキング1位・メディア掲載" },
      { label: "緊急CTA", description: "残りわずか・本日限定" },
    ],
    created_at: "2026-02-10",
  },
  {
    id: "tmpl_003",
    name: "アプリ・体験型ストーリー",
    hit_rate: 65,
    genres: ["app", "gaming"],
    sections: [
      { label: "問題提起", description: "日常の不便を具体的に描写" },
      { label: "アプリ紹介", description: "UI画面のデモ・操作感の訴求" },
      { label: "利用シーン", description: "実際の使用場面を複数提示" },
      { label: "無料DL CTA", description: "今すぐ無料ダウンロード" },
    ],
    created_at: "2026-02-08",
  },
  {
    id: "tmpl_004",
    name: "金融・権威性訴求・信頼構築型",
    hit_rate: 61,
    genres: ["finance", "real_estate"],
    sections: [
      { label: "衝撃的データ", description: "知らないと損する数値の提示" },
      { label: "専門家解説", description: "FP・専門家による信頼性の補強" },
      { label: "事例紹介", description: "成功事例・シミュレーション結果" },
      { label: "無料相談CTA", description: "まずは無料シミュレーション" },
    ],
    created_at: "2026-02-05",
  },
  {
    id: "tmpl_005",
    name: "教育・共感型・変身ストーリー",
    hit_rate: 58,
    genres: ["education"],
    sections: [
      { label: "共感フック", description: "「英語が苦手だった私が…」型の導入" },
      { label: "挫折→転機", description: "失敗体験から出会いへの展開" },
      { label: "メソッド紹介", description: "独自学習法の説明" },
      { label: "成果証明", description: "TOEIC○点UP等の具体的成果" },
      { label: "無料体験CTA", description: "7日間無料体験" },
    ],
    created_at: "2026-01-28",
  },
  {
    id: "tmpl_006",
    name: "食品・シズル感・衝動型",
    hit_rate: 69,
    genres: ["food", "ec_d2c"],
    sections: [
      { label: "シズルカット", description: "食欲をそそるビジュアルで開始" },
      { label: "素材こだわり", description: "産地・製法のストーリー" },
      { label: "食レポ", description: "実食リアクション・感想" },
      { label: "お得セットCTA", description: "初回限定お試しセット" },
    ],
    created_at: "2026-01-20",
  },
];

type SortKey = "hit_rate" | "newest";

const genreLabelMap: Record<string, string> = Object.fromEntries(genreOptions.map((g) => [g.value, g.label]));

export default function TemplateLibrary({ onSelectTemplate }: TemplateLibraryProps) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterGenre, setFilterGenre] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("hit_rate");

  useEffect(() => {
    setLoading(true);
    fetchApi<{ templates?: Template[]; items?: Template[] }>("/rankings/scenario-templates")
      .then((res) => {
        const items = res?.templates || res?.items || (Array.isArray(res) ? res : []);
        setTemplates(Array.isArray(items) ? items : []);
      })
      .catch(() => {
        setTemplates(MOCK_TEMPLATES);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let items = [...templates];
    if (filterGenre !== "all") {
      items = items.filter((t) => t.genres.includes(filterGenre));
    }
    if (sortKey === "hit_rate") {
      items.sort((a, b) => b.hit_rate - a.hit_rate);
    } else {
      items.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    }
    return items;
  }, [templates, filterGenre, sortKey]);

  const handleSelect = (id: string) => {
    onSelectTemplate?.(id);
    toast.success("テンプレートを選択しました");
  };

  return (
    <div className="card px-4 py-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <svg className="w-4 h-4 text-[#4A7DFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
        </svg>
        <h3 className="text-[13px] font-bold text-gray-900">テンプレートライブラリ</h3>
        <span className="text-[9px] text-gray-400">実績ベースの構成テンプレート</span>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        <select value={filterGenre} onChange={(e) => setFilterGenre(e.target.value)} className="select-filter text-[10px] h-7">
          {genreOptions.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
        </select>
        <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-0.5 h-7 ml-auto">
          {([["hit_rate", "HIT率順"], ["newest", "新着順"]] as [SortKey, string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setSortKey(key)}
              className={`px-2.5 rounded text-[9px] h-full transition-colors ${
                sortKey === key ? "bg-white shadow-sm text-gray-900 font-medium" : "text-gray-500"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="border border-gray-100 rounded-lg p-3 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
              <div className="h-3 bg-gray-100 rounded w-1/2 mb-3" />
              <div className="space-y-1.5">
                <div className="h-2.5 bg-gray-100 rounded w-full" />
                <div className="h-2.5 bg-gray-100 rounded w-5/6" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Template grid */}
      {!loading && filtered.length === 0 && (
        <div className="text-center py-8">
          <p className="text-[11px] text-gray-500">該当するテンプレートがありません</p>
          <p className="text-[10px] text-gray-400 mt-1">フィルターを変更してお試しください</p>
        </div>
      )}

      {!loading && filtered.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filtered.map((tmpl) => {
            const rateColor = tmpl.hit_rate >= 70 ? "#22c55e" : tmpl.hit_rate >= 50 ? "#f59e0b" : "#94a3b8";
            return (
              <div key={tmpl.id} className="border border-gray-100 rounded-lg p-3 hover:shadow-md hover:border-[#4A7DFF]/20 transition-all group">
                {/* Name + hit rate badge */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h4 className="text-[11px] font-bold text-gray-800 leading-tight flex-1">{tmpl.name}</h4>
                  <span
                    className="shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded"
                    style={{ backgroundColor: `${rateColor}18`, color: rateColor }}
                  >
                    {tmpl.hit_rate}%
                  </span>
                </div>

                {/* Genre tags */}
                <div className="flex flex-wrap gap-1 mb-2.5">
                  {tmpl.genres.map((g) => (
                    <span key={g} className="text-[8px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                      {genreLabelMap[g] || g}
                    </span>
                  ))}
                </div>

                {/* Structure preview */}
                <div className="space-y-1 mb-3">
                  {tmpl.sections.map((s, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <span className="w-4 h-4 rounded bg-[#4A7DFF]/10 text-[#4A7DFF] text-[8px] font-bold flex items-center justify-center shrink-0">
                        {i + 1}
                      </span>
                      <span className="text-[10px] text-gray-600 truncate">{s.label}</span>
                    </div>
                  ))}
                </div>

                {/* Select button */}
                <button
                  onClick={() => handleSelect(tmpl.id)}
                  className="w-full text-[10px] py-1.5 rounded-lg border border-[#4A7DFF]/20 text-[#4A7DFF] font-medium hover:bg-[#4A7DFF] hover:text-white transition-colors"
                >
                  このテンプレートを使う
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
