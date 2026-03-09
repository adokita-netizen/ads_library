# B100: Bedrock Provenance, Review, and Priority UI

## 優先度
- `P0`

## 目的
- Bedrock が付けた商材分類・優先度・レビュー理由を UI で運用可能にする

## 対象
- `frontend/src/components/dashboard/ProRankingView.tsx`
- `frontend/src/components/dashboard/ProRankingTable.tsx`
- `frontend/src/components/dashboard/AnalyticsDashboard.tsx`
- `frontend/src/components/analysis/ProductDetailModal.tsx`
- `frontend/src/components/dashboard/AdDetailModal.tsx`
- `frontend/src/types/index.ts`
- `frontend/e2e/`

## 実装タスク
1. 一覧に `AI商材`, `priority`, `review_required` 列を追加する
2. `rule / AI / manual` の provenance badge を表示する
3. `actual metrics 優先取得` のソート / フィルタ導線を追加する
4. `review_reason` と `confidence_band` を詳細モーダルで見せる
5. `JP only + high priority + review_required` の運用ビューを作る
6. E2E で `high priority`, `manual review`, `AI classified`, `rule-only` を固定する

## 完了条件
- [ ] Bedrock 判定の理由と由来が UI で見える
- [ ] actual metrics を追うべき広告が UI ですぐ分かる
- [ ] review queue を UI から扱える
