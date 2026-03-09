# C47: Full-Cycle API Taskpack (Implement + Test + Fix)

## スコープ
API側で「実装→契約テスト→不具合修正」を1タスクで完了させる。

## 実装
1. トピック分類API/辞書レビューAPI
2. quality gate API
3. crawl-search consistency API

## テスト
1. pytest: 契約テスト（成功/失敗/境界）
2. pytest: error_code整合テスト
3. 負荷: 低件数/高件数の応答確認

## 修正
1. 500/timeoutの分類と再試行改善
2. 契約不一致の修正
3. 乖離閾値のチューニング

## 完了条件
- [x] 実装が利用可能
- [x] 契約テストが通る
- [x] API不具合が修正される
