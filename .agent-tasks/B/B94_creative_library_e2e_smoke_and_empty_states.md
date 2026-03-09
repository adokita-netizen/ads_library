# B94: Creative Library E2E Smoke & Empty States

## 優先度: 🅰️ A（クリティカル）

## 目的
- 「見れる / DLできる / LPを開ける」導線が実データに近い形で壊れていないことを frontend 側で固定する

## 対象ファイル
- `frontend/src/components/dashboard/HitAdAnalysisView.tsx`
- `frontend/src/components/dashboard/CreativeGalleryView.tsx`
- `frontend/src/components/dashboard/AdDetailModal.tsx`
- `frontend/tests/`

## 実装タスク
1. 一覧から詳細を開き、`CR確認 / DL / LP遷移先` が見える smoke を追加
2. `DL不可 / LP欠損 / snapshot only` の empty state を固定
3. bulk-download 後の結果サマリ表示を E2E で検証
4. 既存 import 崩れや page 単位の表示崩れを回帰対象に含める

## 完了条件
- [ ] 主要導線の smoke が追加される
- [ ] 欠損時の UI 表示が崩れない
- [ ] Creative Library の回帰を早期検知できる
