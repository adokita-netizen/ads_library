# B99: Japanese-Only Filter & Language Badges UI

## 優先度
- `P0`

## 目的
- 日本語広告だけを見る運用を UI で強制しやすくする

## 対象
- `frontend/src/components/dashboard/ProRankingView.tsx`
- `frontend/src/components/dashboard/ProRankingTable.tsx`
- `frontend/src/components/analysis/ProductDetailModal.tsx`
- `frontend/src/components/dashboard/AdDetailModal.tsx`
- `frontend/src/types/index.ts`
- `frontend/e2e/`

## 実装タスク
1. `JP only` トグルを追加する
2. 各広告に `JP / non-JP / 未判定` バッジを出す
3. `exclude_from_analysis=true` の広告は warning 表示にする
4. Bedrock 判定由来なら `AI判定` を表示する
5. E2E で `JP`, `non-JP`, `unknown`, `excluded` を固定する

## 完了条件
- [ ] 日本語広告だけに絞る導線がある
- [ ] 非日本語広告を誤って主分析に使いにくい
- [ ] language 状態が一覧と詳細で分かる
