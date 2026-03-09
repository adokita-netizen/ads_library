# B46: Frontend Error Crush + Stable Refresh

## 概要
ブラウザ上での頻発エラーを潰し、クロール後の最新反映を安定化する。
「表示は完了だがデータは古い」「検索窓が効かない」を再発させない。

## 目的
- コンソールエラー/Unhandled例外を主要導線でゼロ化
- クロール後の一覧反映をユーザー操作なしで成立
- エラー時のUI崩壊を防ぎ、復旧導線を用意

## タスク

### Task 1: 主要導線のエラー境界強化
- AdLibrary / CrawlModal / ProductDetail の Error Boundary導入
- fetch失敗時に画面クラッシュせず再試行ボタンを表示
- `500/timeout/network` をユーザー向け文言へ正規化

### Task 2: 反映遅延の視覚化
- クロール完了後に
  - `再取得中` 表示
  - `最終更新時刻` 表示
  - `追加件数` 表示
- 反映確認前に「完了」だけ表示しない

### Task 3: 検索窓・フィルタ導線の回帰防止
- Enter送信/全角スペース/空入力バリデーションを固定
- ジャンルフィルタ併用時もクロール語同期が崩れないことを保証

### Task 4: ブラウザE2E拡張
- `crawl-search.spec.ts` に以下を追加
  - 500応答時の表示検証
  - timeout時の表示検証
  - 成功後即時反映検証
- `state-sync.spec.ts` で検索語・URL同期崩れを検証

## 完了条件
- [ ] 主要導線でコンソールエラー/クラッシュが出ない
- [ ] クロール完了後に最新反映が目視/自動テストで確認できる
- [ ] 検索窓とジャンルフィルタの併用で不整合が出ない
- [ ] 新規E2EケースがCIで通る

## 触っていいファイル
- `frontend/src/components/dashboard/AdLibraryTable.tsx`
- `frontend/src/components/analysis/ProductDetailModal.tsx`
- `frontend/src/lib/api.ts`
- `frontend/e2e/crawl-search.spec.ts`
- `frontend/e2e/state-sync.spec.ts`

## 連携
- C42で返す `error_code` をUI文言マップに必ず反映する

