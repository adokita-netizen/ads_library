# A53: Learned Fallback Query Dictionary

## Objective
媒体別で回復に効いたクエリを蓄積し、次回の低件数回復で優先利用する。

## Scope
- `data/platform_query_learnings.json` を読込/保存
- `base_query x platform` ごとに `recovery_query` の attempts/success を記録
- 次回回復時に成功実績クエリを先頭利用

## Acceptance Criteria
- 学習後、`_get_learned_recovery_queries` が成功クエリを返す
- quick-crawl 回復attemptに `learned_query` フラグが残る

## Status
Completed (2026-03-03)
