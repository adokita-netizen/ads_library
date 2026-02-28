# Agent B: バグ修正・改善タスク

## 概要
フロントエンドの既知バグ・品質問題を修正する。
コンフリクト防止ルールは `INSTRUCTIONS.md` を厳守すること。

---

## 修正項目（優先度順）

### BUG-1: AdLibrary.tsx - 画像エラーハンドラの非安全なDOM操作 [CRITICAL]
**ファイル:** `frontend/src/components/dashboard/AdLibrary.tsx` (行 181-190)
**問題:** `parentElement!` で非nullアサーションを使用しており、parentがnullの場合クラッシュする
**修正方法:** Reactの状態管理でフォールバック表示を制御する。または最低限 `parentElement` のnullチェックを追加する。

```tsx
// 現在（危険）
(e.target as HTMLImageElement).parentElement!.classList.add(...)
(e.target as HTMLImageElement).parentElement!.appendChild(svg);

// 修正案: nullチェックを追加
onError={(e) => {
  const img = e.target as HTMLImageElement;
  img.style.display = "none";
  const parent = img.parentElement;
  if (!parent) return;
  parent.classList.add("flex", "items-center", "justify-center");
  // ... svg作成処理
  parent.appendChild(svg);
}}
```

### BUG-2: HitAdAnalysisView.tsx - ジャンル変更時にselectedIdsがクリアされない [HIGH]
**ファイル:** `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
**問題:** `selectedGenre` を変更しても `selectedIds` がリセットされず、存在しないIDが残る
**修正方法:** `selectedGenre` 変更時に `setSelectedIds([])` を実行する

```tsx
// useEffectで対応するか、onChange内で対応
useEffect(() => {
  setSelectedIds([]);
}, [selectedGenre]);
```

### BUG-3: HitAdAnalysisView.tsx - 分布計算がuseMemo化されていない [MEDIUM]
**ファイル:** `frontend/src/components/dashboard/HitAdAnalysisView.tsx` (行 122-137)
**問題:** `genreDistribution`, `platformDistribution`, `sortedGenres`, `sortedPlatforms`, `avgSpendIncrease`, `avgViewIncrease` がレンダーごとに再計算される
**修正方法:** `useMemo` でラップする

```tsx
const { genreDistribution, platformDistribution, sortedGenres, sortedPlatforms, avgSpendIncrease, avgViewIncrease } = useMemo(() => {
  const hitOnly = hitAds.filter((a) => a.is_hit);
  // ... 現在の計算ロジック
  return { genreDistribution, platformDistribution, sortedGenres, sortedPlatforms, avgSpendIncrease, avgViewIncrease };
}, [hitAds]);
```

### BUG-4: HitAdAnalysisView.tsx - サマリーカードの配信統計表示改善 [MEDIUM]
**ファイル:** `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
**問題:** `hit_level` が `mega_hit` の広告が新しく74件あるが、サマリーカードでは `is_hit` のみカウントしている。大ヒットと通常ヒットを分けて表示すべき。
**修正方法:** サマリーカード部分で mega_hit / hit を分けてカウント・表示する。

```tsx
// 現在
const totalHits = hitAds.filter((a) => a.is_hit).length;

// 改善
const megaHitCount = hitAds.filter((a) => a.hit_level === "mega_hit").length;
const hitCount = hitAds.filter((a) => a.hit_level === "hit").length;
const totalHits = megaHitCount + hitCount;
```

サマリーカードに「大ヒット: XX件 / ヒット: XX件」と表示する。

### BUG-5: HitAdAnalysisView.tsx - テーブルのHITバッジ改善 [MEDIUM]
**ファイル:** `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
**問題:** 現在のHITバッジは `days_running` ベースだが、バックエンドが `hit_level` を返すようになったので、APIの `hit_level` を使うべき。
**修正方法:** テーブル内のバッジ表示を `hit_level` フィールドに基づいて変更する。

```tsx
// ad.hit_level に基づく表示
{ad.hit_level === "mega_hit" && (
  <span className="... bg-red-100 text-red-700 ...">大HIT</span>
)}
{ad.hit_level === "hit" && (
  <span className="... bg-orange-100 text-orange-700 ...">HIT</span>
)}
```

### BUG-6: AdLibrary.tsx - 検索クエリがuseEffect依存配列に含まれていない [LOW]
**ファイル:** `frontend/src/components/dashboard/AdLibrary.tsx` (行 34-36)
**問題:** `useEffect` の依存配列に `searchQuery` が含まれていない。フォーム送信で `loadAds()` は呼ばれるのでクリティカルではないが、`setPage(1)` 後の再読み込みが依存配列経由で行われるため問題ない。
**対応:** 現状維持で問題なし（フォーム送信で正常に動作している）。ただしエンターキーでの送信もフォームsubmitで処理されているか確認。

---

## 注意事項
- `import { useMemo } from "react"` を追加すること（BUG-3対応時）
- 修正後に `cd frontend && npx next build --no-lint` でビルド確認すること
- バックエンドファイルは一切触らないこと
- 既存の型定義（HitAd interface）には `hit_level?: string` が既にある（行41）
