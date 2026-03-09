# C53: Platform-Aware Recovery Strategy

## Objective
quick-crawl回復処理を媒体特性に合わせて最適化し、低件数時の回復率を上げる。

## Scope
- helper追加:
  - `_platform_fetch_counts`
  - `_build_recovery_platform_batches`
- recoveryで 0件/低件数媒体を先行再試行
- attempt上限を設けて過剰リトライを防止

## Acceptance Criteria
- 回復attemptが媒体バッチ単位で実行される
- 回復結果に媒体別内訳が残る
- 既存quick-crawl契約を破壊しない

## Status
Completed (2026-03-03)
