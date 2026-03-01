"use client";

interface QuickActionsProps {
  onSelect: (prompt: string) => void;
}

const actions = [
  { label: "ヒット分析", prompt: "現在のヒット広告の傾向を分析して、共通する成功要因を教えてください。" },
  { label: "勝ちパターン", prompt: "直近30日間で高スコアを記録した広告の勝ちパターンをまとめてください。" },
  { label: "競合比較", prompt: "主要な競合他社の広告戦略を比較分析してください。" },
  { label: "ブリーフ生成", prompt: "ヒット広告のデータを基に、新しいクリエイティブブリーフを生成してください。" },
  { label: "トレンド予測", prompt: "現在のデータから今後のクリエイティブトレンドを予測してください。" },
  { label: "コピー改善", prompt: "既存の広告コピーの改善点を分析し、より効果的な代替案を提案してください。" },
];

export default function QuickActions({ onSelect }: QuickActionsProps) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
      {actions.map((action) => (
        <button
          key={action.label}
          onClick={() => onSelect(action.prompt)}
          className="flex-shrink-0 rounded-full bg-gray-100 hover:bg-[#EEF2FF] text-[11px] text-gray-700 px-3 py-1.5 transition-colors whitespace-nowrap"
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}
