# B96: Recovery Queue & Manual Retry UI

## 優先度: 🅱️ B（重要）

## 目的
- DL不可や LP未解決の広告を、利用者が UI 上で把握し、再取得アクションに繋げられるようにする

## 対象ファイル
- `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
- `frontend/src/components/dashboard/CreativeGalleryView.tsx`
- `frontend/src/components/dashboard/AdDetailModal.tsx`
- `frontend/src/types/index.ts`

## 実装タスク
1. `missing_reasons / lp_status` を使って復旧待ち広告を一覧フィルタできるようにする
2. `snapshot only / download unavailable / lp unresolved` を UI 上で区別する
3. 再取得系 API がある前提で `再取得` 導線を置けるレイアウトにする
4. 復旧済み広告が一覧に戻った時の状態同期を崩さない

## 完了条件
- [ ] 復旧待ち広告を UI から絞り込める
- [ ] 手動再試行の導線を後付けしやすい
