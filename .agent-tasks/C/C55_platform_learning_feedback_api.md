# C55: Platform Learning Feedback API

## Objective
回復処理の学習ループをAPIロジックに接続し、自己改善型のfallback選定を実現する。

## Scope
- helper追加:
  - `_load_platform_query_learnings`
  - `_save_platform_query_learnings`
  - `_record_platform_query_learning`
  - `_get_learned_recovery_queries`
- quick-crawl recoveryで学習クエリ優先 + 学習結果の記録
- diagnostics summaryへ learned_attempts / learned_success_rate 追加

## Acceptance Criteria
- 回復attemptに `learned_query` フラグが記録される
- diagnostics APIで学習指標が返る

## Status
Completed (2026-03-03)
