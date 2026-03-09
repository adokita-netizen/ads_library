"use client";

export type QuickFilterKey =
  | "hit_only"
  | "video_only"
  | "active_only"
  | "new_week"
  | "score_70_plus";

interface QuickFilterBarProps {
  active: QuickFilterKey[];
  onToggle: (key: QuickFilterKey) => void;
}

const FILTERS: Array<{ key: QuickFilterKey; label: string }> = [
  { key: "hit_only", label: "HIT広告のみ" },
  { key: "video_only", label: "動画のみ" },
  { key: "active_only", label: "配信中" },
  { key: "new_week", label: "今週の新着" },
  { key: "score_70_plus", label: "スコア70+" },
];

export default function QuickFilterBar({ active, onToggle }: QuickFilterBarProps) {
  return (
    <div className="mb-3 flex items-center gap-2 overflow-x-auto">
      {FILTERS.map((f) => {
        const isActive = active.includes(f.key);
        return (
          <button
            key={f.key}
            onClick={() => onToggle(f.key)}
            className={`shrink-0 rounded-full px-3 py-1.5 text-[11px] border transition-colors ${
              isActive
                ? "bg-[#4A7DFF] text-white border-[#4A7DFF]"
                : "bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
            }`}
          >
            {f.label}
          </button>
        );
      })}
    </div>
  );
}
