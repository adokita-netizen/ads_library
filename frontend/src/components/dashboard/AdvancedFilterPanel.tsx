"use client";

import React, { useState, useEffect } from "react";

// ─── Types ───

export interface AdvancedFilters {
  videoFormat: "all" | "video" | "image" | "carousel";
  excludedAdvertisers: string[];
  excludedDomains: string[];
  platform: "all" | "facebook" | "instagram" | "tiktok";
  dateRange: { from: string | null; to: string | null };
  viewCountMin: number | null;
  viewCountMax: number | null;
  likeCountMin: number | null;
  likeCountMax: number | null;
  destinationType: string | null;
  destinationDomain: string | null;
  spendMin: number | null;
  spendMax: number | null;
}

export const defaultFilters: AdvancedFilters = {
  videoFormat: "all",
  excludedAdvertisers: [],
  excludedDomains: [],
  platform: "all",
  dateRange: { from: null, to: null },
  viewCountMin: null,
  viewCountMax: null,
  likeCountMin: null,
  likeCountMax: null,
  destinationType: null,
  destinationDomain: null,
  spendMin: null,
  spendMax: null,
};

export function getActiveFilterCount(filters: AdvancedFilters): number {
  let count = 0;
  if (filters.videoFormat !== "all") count++;
  if (filters.excludedAdvertisers.length > 0) count++;
  if (filters.excludedDomains.length > 0) count++;
  if (filters.platform !== "all") count++;
  if (filters.dateRange.from || filters.dateRange.to) count++;
  if (filters.viewCountMin !== null || filters.viewCountMax !== null) count++;
  if (filters.likeCountMin !== null || filters.likeCountMax !== null) count++;
  if (filters.destinationType) count++;
  if (filters.destinationDomain) count++;
  if (filters.spendMin !== null || filters.spendMax !== null) count++;
  return count;
}

// ─── Props ───

interface AdvancedFilterPanelProps {
  isOpen: boolean;
  onClose: () => void;
  filters: AdvancedFilters;
  onApply: (filters: AdvancedFilters) => void;
}

// ─── Accordion Section ───

function FilterSection({ title, badge, children, defaultOpen = false }: {
  title: string;
  badge?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-gray-700/50">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-medium text-gray-200">{title}</span>
          {badge && (
            <span className="px-1.5 py-0.5 text-[9px] font-bold bg-[#4A7DFF] text-white rounded-full leading-none">{badge}</span>
          )}
        </div>
        <svg className={`w-4 h-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3">
          {children}
        </div>
      )}
    </div>
  );
}

// ─── Destination type options ───
const destinationTypeOptions = [
  { value: "", label: "すべて" },
  { value: "official_site", label: "公式サイト" },
  { value: "article_lp", label: "記事LP" },
  { value: "ec_site", label: "ECサイト" },
  { value: "line_add", label: "LINE追加" },
  { value: "app_dl", label: "アプリDL" },
  { value: "sns", label: "SNS" },
];

// ─── Main Component ───

export default function AdvancedFilterPanel({ isOpen, onClose, filters, onApply }: AdvancedFilterPanelProps) {
  const [localFilters, setLocalFilters] = useState<AdvancedFilters>(filters);
  const [excludeInput, setExcludeInput] = useState("");
  const [excludeDomainInput, setExcludeDomainInput] = useState("");

  useEffect(() => {
    setLocalFilters(filters);
  }, [filters]);

  const handleClear = () => {
    setLocalFilters(defaultFilters);
  };

  const handleApply = () => {
    onApply(localFilters);
    onClose();
  };

  const addExcludedAdvertiser = () => {
    if (excludeInput.trim() && !localFilters.excludedAdvertisers.includes(excludeInput.trim())) {
      setLocalFilters({
        ...localFilters,
        excludedAdvertisers: [...localFilters.excludedAdvertisers, excludeInput.trim()],
      });
      setExcludeInput("");
    }
  };

  const removeExcludedAdvertiser = (name: string) => {
    setLocalFilters({
      ...localFilters,
      excludedAdvertisers: localFilters.excludedAdvertisers.filter((a) => a !== name),
    });
  };

  const addExcludedDomain = () => {
    if (excludeDomainInput.trim() && !localFilters.excludedDomains.includes(excludeDomainInput.trim())) {
      setLocalFilters({
        ...localFilters,
        excludedDomains: [...localFilters.excludedDomains, excludeDomainInput.trim()],
      });
      setExcludeDomainInput("");
    }
  };

  const removeExcludedDomain = (domain: string) => {
    setLocalFilters({
      ...localFilters,
      excludedDomains: localFilters.excludedDomains.filter((d) => d !== domain),
    });
  };

  const setDatePreset = (preset: string) => {
    const now = new Date();
    let from: string | null = null;
    if (preset === "7d") {
      from = new Date(now.getTime() - 7 * 86400000).toISOString().slice(0, 10);
    } else if (preset === "30d") {
      from = new Date(now.getTime() - 30 * 86400000).toISOString().slice(0, 10);
    } else if (preset === "90d") {
      from = new Date(now.getTime() - 90 * 86400000).toISOString().slice(0, 10);
    }
    setLocalFilters({
      ...localFilters,
      dateRange: { from, to: preset === "all" ? null : now.toISOString().slice(0, 10) },
    });
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/50" onClick={onClose} />

      {/* Panel */}
      <div className="fixed top-0 right-0 z-50 h-full w-[360px] bg-gray-900 text-white shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700/50">
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <span className="text-[13px] font-bold text-white">詳細な設定</span>
          </div>
          <button
            onClick={handleClear}
            className="text-[11px] text-[#4A7DFF] hover:text-blue-300 font-medium transition-colors"
          >
            クリア
          </button>
        </div>

        {/* Filter Sections */}
        <div className="flex-1 overflow-auto custom-scrollbar">
          {/* 1. 動画フォーマットの設定 */}
          <FilterSection title="動画フォーマットの設定" defaultOpen>
            <div>
              <label className="block text-[11px] text-gray-400 mb-1.5">動画形式</label>
              <select
                value={localFilters.videoFormat}
                onChange={(e) => setLocalFilters({ ...localFilters, videoFormat: e.target.value as AdvancedFilters["videoFormat"] })}
                className="w-full px-3 py-2 text-[12px] bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50 focus:border-[#4A7DFF]"
              >
                <option value="all">すべて</option>
                <option value="video">動画</option>
                <option value="image">静止画</option>
                <option value="carousel">カルーセル</option>
              </select>
            </div>
          </FilterSection>

          {/* 2. 除外設定 */}
          <FilterSection
            title="除外設定"
            badge={`${localFilters.excludedAdvertisers.length + localFilters.excludedDomains.length}件`}
          >
            <div>
              <label className="block text-[11px] text-gray-400 mb-1.5">広告主を除外</label>
              <div className="flex gap-1.5">
                <input
                  type="text"
                  value={excludeInput}
                  onChange={(e) => setExcludeInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") addExcludedAdvertiser(); }}
                  placeholder="広告主名..."
                  className="flex-1 px-3 py-1.5 text-[12px] bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
                />
                <button onClick={addExcludedAdvertiser} className="px-3 py-1.5 text-[11px] font-medium bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600">追加</button>
              </div>
              {localFilters.excludedAdvertisers.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {localFilters.excludedAdvertisers.map((name) => (
                    <span key={name} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-800 border border-gray-700 rounded text-[10px] text-gray-300">
                      {name}
                      <button onClick={() => removeExcludedAdvertiser(name)} className="text-gray-500 hover:text-red-400">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div>
              <label className="block text-[11px] text-gray-400 mb-1.5">ドメインを除外</label>
              <div className="flex gap-1.5">
                <input
                  type="text"
                  value={excludeDomainInput}
                  onChange={(e) => setExcludeDomainInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") addExcludedDomain(); }}
                  placeholder="example.com"
                  className="flex-1 px-3 py-1.5 text-[12px] bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
                />
                <button onClick={addExcludedDomain} className="px-3 py-1.5 text-[11px] font-medium bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600">追加</button>
              </div>
              {localFilters.excludedDomains.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {localFilters.excludedDomains.map((domain) => (
                    <span key={domain} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-800 border border-gray-700 rounded text-[10px] text-gray-300">
                      {domain}
                      <button onClick={() => removeExcludedDomain(domain)} className="text-gray-500 hover:text-red-400">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </FilterSection>

          {/* 3. メイン設定 */}
          <FilterSection title="メイン設定" defaultOpen>
            <div>
              <label className="block text-[11px] text-gray-400 mb-1.5">プラットフォーム</label>
              <select
                value={localFilters.platform}
                onChange={(e) => setLocalFilters({ ...localFilters, platform: e.target.value as AdvancedFilters["platform"] })}
                className="w-full px-3 py-2 text-[12px] bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
              >
                <option value="all">すべての広告</option>
                <option value="facebook">Facebook</option>
                <option value="instagram">Instagram</option>
                <option value="tiktok">TikTok</option>
              </select>
            </div>
          </FilterSection>

          {/* 4. 公開日設定 */}
          <FilterSection title="公開日設定">
            <div className="flex gap-2 mb-2">
              {[
                { label: "過去7日", value: "7d" },
                { label: "過去30日", value: "30d" },
                { label: "過去90日", value: "90d" },
                { label: "全期間", value: "all" },
              ].map((preset) => (
                <button
                  key={preset.value}
                  onClick={() => setDatePreset(preset.value)}
                  className="flex-1 px-2 py-1.5 text-[10px] font-medium bg-gray-800 border border-gray-700 rounded-lg text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] text-gray-500 mb-1">開始日</label>
                <input
                  type="date"
                  value={localFilters.dateRange.from || ""}
                  onChange={(e) => setLocalFilters({ ...localFilters, dateRange: { ...localFilters.dateRange, from: e.target.value || null } })}
                  className="w-full px-2 py-1.5 text-[11px] bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
                />
              </div>
              <div>
                <label className="block text-[10px] text-gray-500 mb-1">終了日</label>
                <input
                  type="date"
                  value={localFilters.dateRange.to || ""}
                  onChange={(e) => setLocalFilters({ ...localFilters, dateRange: { ...localFilters.dateRange, to: e.target.value || null } })}
                  className="w-full px-2 py-1.5 text-[11px] bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
                />
              </div>
            </div>
          </FilterSection>

          {/* 5. 再生回数を設定 */}
          <FilterSection title="再生回数を設定">
            <div className="flex gap-2 mb-2">
              {[
                { label: "1,000+", value: 1000 },
                { label: "10,000+", value: 10000 },
                { label: "100,000+", value: 100000 },
                { label: "1,000,000+", value: 1000000 },
              ].map((preset) => (
                <button
                  key={preset.value}
                  onClick={() => setLocalFilters({ ...localFilters, viewCountMin: preset.value, viewCountMax: null })}
                  className={`flex-1 px-1 py-1.5 text-[9px] font-medium border rounded-lg transition-colors ${
                    localFilters.viewCountMin === preset.value
                      ? "bg-[#4A7DFF] border-[#4A7DFF] text-white"
                      : "bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700"
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] text-gray-500 mb-1">最小</label>
                <input
                  type="number"
                  value={localFilters.viewCountMin ?? ""}
                  onChange={(e) => setLocalFilters({ ...localFilters, viewCountMin: e.target.value ? Number(e.target.value) : null })}
                  placeholder="0"
                  className="w-full px-2 py-1.5 text-[11px] bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
                />
              </div>
              <div>
                <label className="block text-[10px] text-gray-500 mb-1">最大</label>
                <input
                  type="number"
                  value={localFilters.viewCountMax ?? ""}
                  onChange={(e) => setLocalFilters({ ...localFilters, viewCountMax: e.target.value ? Number(e.target.value) : null })}
                  placeholder="制限なし"
                  className="w-full px-2 py-1.5 text-[11px] bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
                />
              </div>
            </div>
          </FilterSection>

          {/* 6. いいね数を設定 */}
          <FilterSection title="いいね数を設定">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] text-gray-500 mb-1">最小</label>
                <input
                  type="number"
                  value={localFilters.likeCountMin ?? ""}
                  onChange={(e) => setLocalFilters({ ...localFilters, likeCountMin: e.target.value ? Number(e.target.value) : null })}
                  placeholder="0"
                  className="w-full px-2 py-1.5 text-[11px] bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
                />
              </div>
              <div>
                <label className="block text-[10px] text-gray-500 mb-1">最大</label>
                <input
                  type="number"
                  value={localFilters.likeCountMax ?? ""}
                  onChange={(e) => setLocalFilters({ ...localFilters, likeCountMax: e.target.value ? Number(e.target.value) : null })}
                  placeholder="制限なし"
                  className="w-full px-2 py-1.5 text-[11px] bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
                />
              </div>
            </div>
          </FilterSection>

          {/* 7. 遷移先サイトの設定 */}
          <FilterSection title="遷移先サイトの設定">
            <div>
              <label className="block text-[11px] text-gray-400 mb-1.5">遷移先タイプ</label>
              <select
                value={localFilters.destinationType || ""}
                onChange={(e) => setLocalFilters({ ...localFilters, destinationType: e.target.value || null })}
                className="w-full px-3 py-2 text-[12px] bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
              >
                {destinationTypeOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] text-gray-400 mb-1.5">ドメイン検索</label>
              <input
                type="text"
                value={localFilters.destinationDomain || ""}
                onChange={(e) => setLocalFilters({ ...localFilters, destinationDomain: e.target.value || null })}
                placeholder="example.com"
                className="w-full px-3 py-1.5 text-[12px] bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-[#4A7DFF]/50"
              />
            </div>
          </FilterSection>
        </div>

        {/* Footer */}
        <div className="shrink-0 px-4 py-3 border-t border-gray-700/50 bg-gray-900">
          <button
            onClick={handleApply}
            className="w-full py-2.5 bg-[#4A7DFF] text-white rounded-lg text-[13px] font-bold hover:bg-[#3b6de6] transition-colors"
          >
            フィルターを適用
          </button>
        </div>
      </div>
    </>
  );
}
