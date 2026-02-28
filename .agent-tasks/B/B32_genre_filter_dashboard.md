# B32: ジャンルフィルタ & ダッシュボード

## 目的
ジャンル別の分析ダッシュボードUIを構築。15ジャンルの視覚的な分析ツール。

## タスク

### 1. GenreDistributionChart コンポーネント
- `frontend/src/components/dashboard/GenreDistributionChart.tsx` を作成
- 円グラフまたはツリーマップでジャンル分布を表示
- クリックでそのジャンルにフィルタ

### 2. GenreComparisonView コンポーネント
- `frontend/src/components/dashboard/GenreComparisonView.tsx` を作成
- 2-3ジャンルを選択して横断比較
- バーチャート: 広告数、平均スコア、平均再生数
- テーブル: 各ジャンルのトップ5広告

### 3. GenreTrendChart コンポーネント
- `frontend/src/components/dashboard/GenreTrendChart.tsx` を作成
- 折れ線グラフでジャンル別トレンド推移
- 週次/月次切替

## 制約
- `frontend/src/components/dashboard/` にのみファイル作成
- Tailwind CSSのみ、SVG or Canvas でチャート描画
- fetchApiを使用
