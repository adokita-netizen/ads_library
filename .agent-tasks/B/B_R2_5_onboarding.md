# B-R2-5: Onboarding & Empty States (B41 Phase 2)
# 優先度: P2 | 前提: B-R2-1〜4 完了 | ブロック: なし

## 目的
初回ユーザーがVAAPを理解し、すぐに使い始められるようにする。

## 対象ファイル
- 新規: `frontend/src/components/common/OnboardingWizard.tsx`
- 新規: `frontend/src/components/common/EmptyState.tsx`
- 新規: `frontend/src/components/common/SetupProgress.tsx`
- 修正: `frontend/src/app/page.tsx`

## 実装

### OnboardingWizard — 3ステップウィザード
```
Step 1: ようこそ VAAP へ
  - プラットフォームの概要説明
  - 主要機能のアイコン付き紹介（3つ）
    - 競合広告の収集・分析
    - HIT広告の自動検出
    - クリエイティブ提案

Step 2: データ接続
  - Meta API トークンの設定案内
  - 「後で設定する」ボタン
  - デモモードの説明

Step 3: はじめましょう
  - PRO DATABASE の簡単な使い方
  - ショートカットキー紹介 (B27 で実装済み)
  - 「ツアーを開始」/ 「スキップ」ボタン
```

### EmptyState — 統一的な空データ表示
```tsx
interface EmptyStateProps {
  icon: 'search' | 'chart' | 'image' | 'video' | 'alert' | 'collection';
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  showDemo?: boolean;  // デモデータ表示ボタン
}

// 使用例:
<EmptyState
  icon="chart"
  title="No ads data yet"
  description="Start by crawling ads from Meta Ad Library"
  actionLabel="Start Crawling"
  onAction={() => switchView('hit-ads')}
/>
```

### SetupProgress — セットアップ進捗バー
```
[■■■□□] 3/5 steps completed

✓ Platform connected
✓ First crawl completed
✓ Rankings calculated
□ Meta API token configured
□ Scheduled crawl enabled
```

### デモモード
```tsx
// localStorage に vaap-demo-mode を保存
// デモモード時は API が 404/空を返しても サンプルデータを表示
const DEMO_ADS = [
  { id: 1, title: 'Demo Ad 1', hit_score: 85, ... },
  { id: 2, title: 'Demo Ad 2', hit_score: 72, ... },
  // ... 10件のサンプル
];
```

## トリガー条件
```tsx
// page.tsx
useEffect(() => {
  const onboarded = localStorage.getItem('vaap-onboarded');
  if (!onboarded) {
    setShowOnboarding(true);
  }
}, []);
```

## 完了条件
- [ ] 初回アクセスでウィザードが表示される
- [ ] 3ステップが正しくナビゲートできる
- [ ] 「スキップ」で二度と表示されない
- [ ] EmptyState コンポーネントが全ビューで統一的に使える
- [ ] デモモードでサンプルデータが表示される
- [ ] SetupProgress がヘッダー or サイドバーに表示される
- [ ] ビルド成功
- [ ] status.md に記録
