# B48: Topic Evidence UI + Mismatch Review

## 目的
「なぜこの広告がそのカテゴリ判定/HIT判定になったか」をUIで見える化し、全カテゴリで乖離レビューを可能にする。

## タスク
1. 判定根拠UIを追加（全カテゴリ）
- 広告詳細で `topic_tags`, `confidence`, `evidence_terms` を表示
- `hit_drivers`（訴求軸・オファー・CTA・クリエイティブ要素）を表示

2. 乖離レビュービュー（全カテゴリ）
- 「Meta上で多いのに未分類」候補を一覧化
- `未分類だがカテゴリ語を含む` フィルタを追加

3. クリックで再分類依頼
- 1件単位で再解析APIを叩ける導線
- 結果更新を即時反映

4. E2E回帰
- 根拠表示・フィルタ・再分類導線を検証

## 完了条件
- [ ] 各広告にカテゴリ判定/HIT寄与根拠が表示される
- [ ] 未分類候補をUIからレビューできる
- [ ] 再分類の結果が即時反映される

## 対象
- `frontend/src/components/analysis/ProductDetailModal.tsx`
- `frontend/src/components/dashboard/AdLibraryTable.tsx`
- `frontend/e2e/state-sync.spec.ts`
