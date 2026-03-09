# B39: フロントエンドパフォーマンス最適化

## 問題
- 大量データ（500件+）表示時にレンダリングが重い → 仮想スクロール未導入
- `useMemo` / `useCallback` の適用不足 → 不要な再レンダリング
- フィルタリング・ソートのたびに全件再計算

## 対象ファイル
- `frontend/src/components/HitAdAnalysisView.tsx`
- `frontend/src/components/AdLibrary.tsx`
- `frontend/src/components/ProductDetailModal.tsx`

## 修正

### 1. フィルタ・ソート結果の useMemo 化
```tsx
// Before
const filtered = ads.filter(ad => matchesFilter(ad, filter));
const sorted = filtered.sort((a, b) => sortFn(a, b));

// After
const filtered = useMemo(
  () => ads.filter(ad => matchesFilter(ad, filter)),
  [ads, filter]
);
const sorted = useMemo(
  () => [...filtered].sort((a, b) => sortFn(a, b)),
  [filtered, sortKey, sortOrder]
);
```

### 2. コールバック関数の useCallback 化
```tsx
// イベントハンドラを useCallback でラップ
const handleFilterChange = useCallback((newFilter: FilterType) => {
  setFilter(newFilter);
}, []);

const handleSort = useCallback((key: string) => {
  setSortKey(key);
  setSortOrder(prev => prev === "asc" ? "desc" : "asc");
}, []);
```

### 3. 大量リスト表示の最適化
- 表示件数のページネーション or "もっと読み込む" パターン導入
- 初期表示は50件、スクロール末端で追加読み込み

```tsx
const [displayCount, setDisplayCount] = useState(50);
const displayedAds = sorted.slice(0, displayCount);

const loadMore = useCallback(() => {
  setDisplayCount(prev => Math.min(prev + 50, sorted.length));
}, [sorted.length]);
```

## 制約
- 外部ライブラリの追加は不要（React標準フックのみ使用）
- 既存のUI表示・動作は変更しない
