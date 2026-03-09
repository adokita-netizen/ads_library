# B47: Creative Clarity + Refresh Validation

## 目的
「不鮮明クリエイティブ」と「クロール後に新情報が見えない」体験を解消する。

## タスク
1. 一覧サムネイルの取得優先順を再点検し、低解像度URLを回避
2. クロール成功後の反映導線を可視化（更新時刻・追加件数）
3. GLP-1等キーワードで反映有無をブラウザ実機で検証
4. 回帰E2Eを追加（成功/失敗/タイムアウト/低解像度）

## 完了条件
- [ ] 主要導線でぼやけ画像の再現率が大幅に低下
- [ ] クロール後の反映遅延がUIで判別可能
- [ ] E2Eで再発防止

## 対象
- `frontend/src/components/dashboard/AdLibraryTable.tsx`
- `frontend/e2e/crawl-search.spec.ts`
- `frontend/e2e/state-sync.spec.ts`

