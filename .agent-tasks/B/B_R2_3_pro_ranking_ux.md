# B-R2-3: Pro Ranking Table UX Enhancement (B31)
# 優先度: P1 | 前提: なし | ブロック: なし

## 目的
ProRankingTable のテーブル操作UXをプロフェッショナルレベルに引き上げる。

## 対象ファイル
- `frontend/src/components/dashboard/ProRankingTable.tsx` (修正)
- `frontend/src/components/dashboard/ProRankingView.tsx` (修正)

## 実装タスク

### Task 1: 固定ヘッダー (sticky header)
```tsx
// テーブルコンテナに max-height + overflow-y-auto
// thead に sticky top-0 z-10 bg-white dark:bg-gray-900
<div className="max-h-[calc(100vh-280px)] overflow-y-auto">
  <table>
    <thead className="sticky top-0 z-10 bg-white dark:bg-gray-900 shadow-sm">
      ...
    </thead>
    <tbody>...</tbody>
  </table>
</div>
```

### Task 2: カラム表示/非表示トグル
```tsx
// カラム設定ドロップダウン
const [visibleColumns, setVisibleColumns] = useState<Set<string>>(
  new Set(['rank', 'thumbnail', 'product_name', 'genre', 'view_increase', 'total_views', 'spend_increase', 'total_spend', 'hit_score'])
);

// ツールバーに歯車アイコンのドロップダウン
// 各カラムのチェックボックス
// localStorage に永続化 (CI-057 対応)
useEffect(() => {
  const saved = localStorage.getItem('vaap-columns');
  if (saved) setVisibleColumns(new Set(JSON.parse(saved)));
}, []);

useEffect(() => {
  localStorage.setItem('vaap-columns', JSON.stringify([...visibleColumns]));
}, [visibleColumns]);
```

### Task 3: ソート状態のURL同期 (CI-045)
```tsx
import { useSearchParams } from 'next/navigation';

// URL params: ?sort=hit_score&order=desc&page=1&genre=beauty
// ブラウザの戻る/進むで状態復元
const searchParams = useSearchParams();

const sortField = searchParams.get('sort') || 'hit_score';
const sortOrder = searchParams.get('order') || 'desc';
const currentPage = parseInt(searchParams.get('page') || '1');

// ソート変更時にURL更新
const handleSort = (field: string) => {
  const params = new URLSearchParams(searchParams.toString());
  params.set('sort', field);
  params.set('order', sortField === field && sortOrder === 'desc' ? 'asc' : 'desc');
  window.history.pushState(null, '', `?${params.toString()}`);
};
```

### Task 4: 選択行ハイライト強化
```tsx
const [selectedRowId, setSelectedRowId] = useState<number | null>(null);

// 行クリック時
<tr
  onClick={() => setSelectedRowId(ad.id)}
  className={`
    cursor-pointer transition-colors
    ${selectedRowId === ad.id
      ? 'bg-blue-50 dark:bg-blue-900/30 ring-1 ring-blue-300'
      : 'hover:bg-gray-50 dark:hover:bg-gray-800'}
  `}
>
```

### Task 5: 二重送信防止 (CI-053)
```tsx
// クロール実行、エクスポート等のアクションボタンに適用
const [isSubmitting, setIsSubmitting] = useState(false);

const handleAction = async () => {
  if (isSubmitting) return;
  setIsSubmitting(true);
  try {
    await performAction();
  } finally {
    setIsSubmitting(false);
  }
};

<button disabled={isSubmitting} onClick={handleAction}>
  {isSubmitting ? 'Processing...' : 'Execute'}
</button>
```

## ビルド確認
```bash
cd C:/Users/ishit/ads_library/frontend
npx next build --no-lint
```

## 完了条件
- [ ] テーブルヘッダーがスクロール時に固定される
- [ ] カラム表示/非表示が切り替えられ、localStorage に永続化される
- [ ] ソート状態がURLに反映され、戻る/進むで復元される
- [ ] 選択行のハイライトが視覚的に明確
- [ ] アクションボタンの二重送信が防止される
- [ ] ビルド成功
- [ ] status.md に記録
