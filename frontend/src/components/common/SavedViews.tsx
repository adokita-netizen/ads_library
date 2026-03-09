"use client";

interface SavedViewItem {
  id: number;
  name: string;
}

interface SavedViewsProps {
  views: SavedViewItem[];
  activeViewId?: number | null;
  onSelect: (id: number) => void;
  onCreate: () => void;
}

export default function SavedViews({
  views,
  activeViewId,
  onSelect,
  onCreate,
}: SavedViewsProps) {
  return (
    <div className="mb-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2">
      <div className="flex items-center gap-2 overflow-x-auto">
        <span className="text-[11px] text-gray-500 dark:text-gray-400 shrink-0">マイビュー:</span>
        {views.slice(0, 8).map((v) => (
          <button
            key={v.id}
            onClick={() => onSelect(v.id)}
            className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] border transition-colors ${
              activeViewId === v.id
                ? "bg-[#EEF2FF] text-[#4A7DFF] border-[#cdd9ff]"
                : "bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700"
            }`}
          >
            {v.name}
          </button>
        ))}
        <button
          onClick={onCreate}
          className="shrink-0 rounded-full px-2.5 py-1 text-[11px] border border-dashed border-[#4A7DFF] text-[#4A7DFF] hover:bg-[#EEF2FF] transition-colors"
        >
          + 新規
        </button>
      </div>
    </div>
  );
}
