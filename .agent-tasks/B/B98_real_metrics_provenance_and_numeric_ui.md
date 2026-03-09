# B98: Real Metrics Provenance & Numeric UI

## 優先度
- `P0`

## 目的
- 数値が「入っている」だけでなく、実測なのか推定なのか欠損なのかを UI で分かるようにする

## 対象
- `frontend/src/components/analysis/ProductDetailModal.tsx`
- `frontend/src/components/dashboard/AdDetailModal.tsx`
- `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
- `frontend/src/components/dashboard/AnalyticsDashboard.tsx`
- `frontend/src/types/index.ts`
- `frontend/e2e/`

## 実装タスク
1. 数値カードに `実測 / 推定 / 欠損 / stale` バッジを付ける
2. `spend / impressions / reach / LP score / quality score` の provenance を tooltip か補助文で表示する
3. `estimated_only` 時は「実データ未取得」の warning を追加する
4. `missing_numeric_count > 0` のとき、画面内で再取得または backfill 待ちの状態を出す
5. E2E で `real`, `estimated`, `missing`, `stale` の4状態を固定する

## 完了条件
- [ ] 実測値と推定値を利用者が誤認しない
- [ ] stale / missing の時に画面が壊れず導線がある
- [ ] Ad360 / 詳細 / 一覧の主要導線で回帰テストがある

## ハンドオフ
- to C:
  - UI が必要とする最終 field 名
- from A:
  - warning 表示すべき状態定義
