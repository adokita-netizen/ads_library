"use client";

import { platformLabels } from "@/lib/constants";

interface FilterState {
  scoreMin: number;
  scoreMax: number;
  daysMin: number;
  daysMax: number;
  runningStatus: "all" | "running" | "stopped";
  sortBy: "score" | "days" | "spend" | "recent";
  searchText: string;
  creativeType: "all" | "video" | "image";
  hookType: string;
  emotion: string;
  platform: string;
  dateFrom: string;
  dateTo: string;
  japaneseOnly: boolean;
  hideDuplicates: boolean;
}

const DEFAULT_FILTERS: FilterState = {
  scoreMin: 0,
  scoreMax: 100,
  daysMin: 0,
  daysMax: 9999,
  runningStatus: "all",
  sortBy: "score",
  searchText: "",
  creativeType: "all",
  hookType: "all",
  emotion: "all",
  platform: "all",
  dateFrom: "",
  dateTo: "",
  japaneseOnly: true,
  hideDuplicates: true,
};

interface HitAdFilterControlsProps {
  filters: FilterState;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  showFilters: boolean;
  setShowFilters: (show: boolean) => void;
  activeFilterCount: number;
  filteredCount: number;
  totalCount: number;
}

export type { FilterState };
export { DEFAULT_FILTERS };

export default function HitAdFilterControls({
  filters,
  setFilters,
  showFilters,
  setShowFilters,
  activeFilterCount,
  filteredCount,
  totalCount,
}: HitAdFilterControlsProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="text-[11px] px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors flex items-center gap-1"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z" />
          </svg>
          フィルター {showFilters ? "▲" : "▼"}
        </button>
        {activeFilterCount > 0 && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#4A7DFF] text-white font-medium">{activeFilterCount}</span>
        )}
        <span className="text-[10px] text-gray-400 ml-auto">{filteredCount}件表示 / 全{totalCount}件</span>
      </div>
      {showFilters && (
        <div className="card px-4 py-3 space-y-3">
          {/* Search input */}
          <div className="relative">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <input
              type="text"
              placeholder="商材名、広告主、個別ワードで検索... 例: GLP-1 / ピラティス / 24時間ジム"
              value={filters.searchText}
              onChange={(e) => setFilters((f) => ({ ...f, searchText: e.target.value }))}
              className="w-full h-8 pl-8 pr-3 rounded-lg border border-gray-200 text-[11px] text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF] focus:border-[#4A7DFF]"
            />
            {filters.searchText && (
              <button
                onClick={() => setFilters((f) => ({ ...f, searchText: "" }))}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {/* Score range presets + slider */}
            <div>
              <p className="text-[10px] text-gray-400 font-medium mb-1.5">
                スコア範囲
                {(filters.scoreMin > 0 || filters.scoreMax < 100) && (
                  <span className="ml-1 text-[#4A7DFF] font-bold">{filters.scoreMin}-{filters.scoreMax}</span>
                )}
              </p>
              <div className="flex flex-wrap gap-1 mb-1.5">
                {([
                  { label: "全て", min: 0, max: 100 },
                  { label: "大HIT (70+)", min: 70, max: 100 },
                  { label: "HIT (45+)", min: 45, max: 100 },
                  { label: "低スコア", min: 0, max: 44 },
                ] as const).map((p) => (
                  <button
                    key={p.label}
                    onClick={() => setFilters((f) => ({ ...f, scoreMin: p.min, scoreMax: p.max }))}
                    className={`text-[9px] px-2 py-1 rounded transition-colors ${filters.scoreMin === p.min && filters.scoreMax === p.max ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-1.5">
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={filters.scoreMin}
                  onChange={(e) => setFilters((f) => ({ ...f, scoreMin: Math.min(Number(e.target.value), f.scoreMax) }))}
                  className="flex-1 h-1 accent-[#4A7DFF]"
                />
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={filters.scoreMax}
                  onChange={(e) => setFilters((f) => ({ ...f, scoreMax: Math.max(Number(e.target.value), f.scoreMin) }))}
                  className="flex-1 h-1 accent-[#4A7DFF]"
                />
              </div>
            </div>
            {/* Days range presets */}
            <div>
              <p className="text-[10px] text-gray-400 font-medium mb-1.5">配信日数</p>
              <div className="flex flex-wrap gap-1">
                {([
                  { label: "全期間", min: 0, max: 9999 },
                  { label: "30日+", min: 30, max: 9999 },
                  { label: "60日+", min: 60, max: 9999 },
                  { label: "90日+", min: 90, max: 9999 },
                ] as const).map((p) => (
                  <button
                    key={p.label}
                    onClick={() => setFilters((f) => ({ ...f, daysMin: p.min, daysMax: p.max }))}
                    className={`text-[9px] px-2 py-1 rounded transition-colors ${filters.daysMin === p.min && filters.daysMax === p.max ? "bg-[#4A7DFF] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            {/* Running status */}
            <div>
              <p className="text-[10px] text-gray-400 font-medium mb-1.5">配信状態</p>
              <select
                value={filters.runningStatus}
                onChange={(e) => setFilters((f) => ({ ...f, runningStatus: e.target.value as "all" | "running" | "stopped" }))}
                className="select-filter text-[11px] h-7 w-full"
              >
                <option value="all">全て</option>
                <option value="running">配信中</option>
                <option value="stopped">停止済み</option>
              </select>
            </div>
            {/* Sort */}
            <div>
              <p className="text-[10px] text-gray-400 font-medium mb-1.5">ソート順</p>
              <select
                value={filters.sortBy}
                onChange={(e) => setFilters((f) => ({ ...f, sortBy: e.target.value as "score" | "days" | "spend" | "recent" }))}
                className="select-filter text-[11px] h-7 w-full"
              >
                <option value="score">スコア順</option>
                <option value="days">配信日数順</option>
                <option value="spend">消化額順</option>
                <option value="recent">最新順</option>
              </select>
            </div>
            {/* Creative type filter */}
            <div>
              <p className="text-[10px] text-gray-400 font-medium mb-1.5">クリエイティブ</p>
              <select
                value={filters.creativeType}
                onChange={(e) => setFilters((f) => ({ ...f, creativeType: e.target.value as "all" | "video" | "image" }))}
                className="select-filter text-[11px] h-7 w-full"
              >
                <option value="all">全て</option>
                <option value="video">動画</option>
                <option value="image">静止画</option>
              </select>
            </div>
            {/* Platform filter */}
            <div>
              <p className="text-[10px] text-gray-400 font-medium mb-1.5">媒体</p>
              <select
                value={filters.platform}
                onChange={(e) => setFilters((f) => ({ ...f, platform: e.target.value }))}
                className="select-filter text-[11px] h-7 w-full"
              >
                <option value="all">全媒体</option>
                {Object.entries(platformLabels).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
          </div>
          {/* Additional filters row */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 pt-2 border-t border-gray-100">
            {/* Hook type filter */}
            <div>
              <p className="text-[10px] text-gray-400 font-medium mb-1.5">フックタイプ</p>
              <select
                value={filters.hookType}
                onChange={(e) => setFilters((f) => ({ ...f, hookType: e.target.value }))}
                className="select-filter text-[11px] h-7 w-full"
              >
                <option value="all">全フック</option>
                <option value="question">質問型</option>
                <option value="pain_point">悩み訴求</option>
                <option value="benefit">ベネフィット</option>
                <option value="curiosity">好奇心</option>
                <option value="social_proof">社会的証明</option>
                <option value="urgency">緊急性</option>
                <option value="storytelling">ストーリー</option>
                <option value="number">数字訴求</option>
                <option value="comparison">比較</option>
                <option value="authority">権威性</option>
              </select>
            </div>
            {/* Emotion filter */}
            <div>
              <p className="text-[10px] text-gray-400 font-medium mb-1.5">感情訴求</p>
              <select
                value={filters.emotion}
                onChange={(e) => setFilters((f) => ({ ...f, emotion: e.target.value }))}
                className="select-filter text-[11px] h-7 w-full"
              >
                <option value="all">全て</option>
                <option value="fear">不安</option>
                <option value="hope">希望</option>
                <option value="anger">怒り</option>
                <option value="joy">喜び</option>
                <option value="surprise">驚き</option>
                <option value="trust">信頼</option>
                <option value="desire">欲望</option>
                <option value="relief">安心</option>
                <option value="curiosity">好奇心</option>
              </select>
            </div>
            {/* Date range: from */}
            <div>
              <p className="text-[10px] text-gray-400 font-medium mb-1.5">掲載開始日（から）</p>
              <input
                type="date"
                value={filters.dateFrom}
                onChange={(e) => setFilters((f) => ({ ...f, dateFrom: e.target.value }))}
                className="w-full h-7 px-2 rounded-lg border border-gray-200 text-[11px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF] focus:border-[#4A7DFF]"
              />
            </div>
            {/* Date range: to */}
            <div>
              <p className="text-[10px] text-gray-400 font-medium mb-1.5">掲載開始日（まで）</p>
              <input
                type="date"
                value={filters.dateTo}
                onChange={(e) => setFilters((f) => ({ ...f, dateTo: e.target.value }))}
                className="w-full h-7 px-2 rounded-lg border border-gray-200 text-[11px] text-gray-700 focus:outline-none focus:ring-1 focus:ring-[#4A7DFF] focus:border-[#4A7DFF]"
              />
            </div>
            {/* Language & duplicate toggles */}
            <div>
              <label className="flex items-center gap-1.5 cursor-pointer mt-1">
                <input
                  type="checkbox"
                  checked={filters.japaneseOnly}
                  onChange={(e) => setFilters((f) => ({ ...f, japaneseOnly: e.target.checked }))}
                  className="w-3 h-3 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]"
                />
                <span className="text-[10px] text-gray-600">日本語のみ</span>
              </label>
              <label className="flex items-center gap-1.5 cursor-pointer mt-1">
                <input
                  type="checkbox"
                  checked={filters.hideDuplicates}
                  onChange={(e) => setFilters((f) => ({ ...f, hideDuplicates: e.target.checked }))}
                  className="w-3 h-3 rounded border-gray-300 text-[#4A7DFF] focus:ring-[#4A7DFF]"
                />
                <span className="text-[10px] text-gray-600">重複を非表示</span>
              </label>
            </div>
            {/* Reset all filters */}
            <div className="flex items-end">
              <button
                onClick={() => setFilters(DEFAULT_FILTERS)}
                className="h-7 px-3 rounded-lg text-[10px] font-medium text-gray-500 bg-gray-100 hover:bg-gray-200 transition-colors w-full"
              >
                リセット
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
