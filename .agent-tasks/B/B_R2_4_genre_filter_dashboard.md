# B-R2-4: Genre Filter Dashboard Enhancement (B32)
# 優先度: P1 | 前提: なし | ブロック: なし

## 目的
ジャンルサイドバーの操作性を改善し、ジャンルベースの探索体験を向上させる。

## 対象ファイル
- `frontend/src/components/dashboard/ProRankingView.tsx` (修正)

## 実装タスク

### Task 1: ジャンルツリー検索
```tsx
// ジャンルサイドバー上部に検索フィールド追加
const [genreSearch, setGenreSearch] = useState('');

const filteredGenres = useMemo(() => {
  if (!genreSearch) return genres;
  const q = genreSearch.toLowerCase();
  return genres.filter(g =>
    g.name.toLowerCase().includes(q) ||
    g.parent?.toLowerCase().includes(q)
  );
}, [genres, genreSearch]);

// UI
<input
  type="text"
  value={genreSearch}
  onChange={e => setGenreSearch(e.target.value)}
  placeholder="Search genres..."
  className="w-full px-3 py-1.5 text-[12px] border border-gray-200 dark:border-gray-600 rounded-md
             bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
/>
```

### Task 2: 折りたたみ/展開の改善
```tsx
// 親カテゴリごとにグルーピング + アコーディオン
const [expandedParents, setExpandedParents] = useState<Set<string>>(new Set());

const toggleParent = (parent: string) => {
  setExpandedParents(prev => {
    const next = new Set(prev);
    next.has(parent) ? next.delete(parent) : next.add(parent);
    return next;
  });
};

// 全展開/全折りたたみボタン
<div className="flex gap-2 mb-2">
  <button onClick={() => setExpandedParents(new Set(allParents))} className="text-[11px] text-blue-500">
    Expand all
  </button>
  <button onClick={() => setExpandedParents(new Set())} className="text-[11px] text-blue-500">
    Collapse all
  </button>
</div>
```

### Task 3: ジャンル件数のリアルタイム更新
```tsx
// genre-master API レスポンスの ad_count をバッジで表示
// フィルター適用後の件数も動的に更新

<div className="flex items-center justify-between">
  <span className="text-[12px]">{genre.name}</span>
  <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded-full text-gray-500">
    {genre.ad_count}
  </span>
</div>
```

### Task 4: 選択中ジャンルのパンくず表示
```tsx
// テーブル上部にパンくず表示
{selectedGenre && selectedGenre !== 'all' && (
  <div className="flex items-center gap-1 text-[12px] text-gray-500 mb-2">
    <button onClick={() => setSelectedGenre('all')} className="hover:text-blue-500">
      All
    </button>
    <span>/</span>
    {parentGenre && (
      <>
        <button onClick={() => setSelectedGenre(parentGenre)} className="hover:text-blue-500">
          {parentGenre}
        </button>
        <span>/</span>
      </>
    )}
    <span className="text-gray-900 dark:text-gray-100 font-medium">{selectedGenre}</span>
    <button
      onClick={() => setSelectedGenre('all')}
      className="ml-1 text-gray-400 hover:text-red-500"
    >
      x
    </button>
  </div>
)}
```

### Task 5: ジャンルサイドバーの折りたたみ (モバイル対応)
```tsx
// モバイルではジャンルサイドバーを非表示にし、ドロワーで開く
const [showGenreSidebar, setShowGenreSidebar] = useState(true);

// lg以上: 常時表示, lg未満: ボタンクリックで表示
<div className={`${showGenreSidebar ? 'block' : 'hidden'} lg:block w-full lg:w-56 shrink-0`}>
  {/* ジャンルサイドバー */}
</div>
```

## 完了条件
- [ ] ジャンル検索フィールドが動作する
- [ ] 親カテゴリのアコーディオン展開/折りたたみが動作する
- [ ] 全展開/全折りたたみボタンが動作する
- [ ] ジャンル件数バッジが表示される
- [ ] パンくずナビゲーションが表示される
- [ ] モバイルでサイドバーが適切にトグルされる
- [ ] ビルド成功
- [ ] status.md に記録
