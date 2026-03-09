# C101: Recovery Trigger API & Operation Contract

## 優先度: 🅰️ A（クリティカル）

## 目的
- D の回収処理を手動運用に閉じず、UI や運用ツールから安全に起動できる API 契約を整える

## 対象ファイル
- `backend/app/api/endpoints/ads.py`
- `backend/app/api/endpoints/media.py`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. `再取得` 用 API の入力/出力契約を定義する
2. `accepted / queued / skipped / reason_code` を標準レスポンスにする
3. 同一広告への連打や重複キュー投入を避ける契約を決める
4. API 契約書に UI 用レスポンス例を追加する

## 完了条件
- [ ] 復旧起動 API を frontend/ops から安全に呼べる
- [ ] 手動再試行の契約が固定される
