# A55: Learning Dictionary Prune Ops

## Objective
学習辞書の肥大化・劣化を防ぐため、弱い古いエントリを定期的に削除する。

## Scope
- helper: `_prune_platform_query_learnings`, `_count_learning_entries`
- 実行スクリプト: `scripts/prune_platform_query_learnings.py`
- quick-crawl回復前に prune を適用

## Acceptance Criteria
- prune前後件数と removed/kept が取得できる
- 回復ループで辞書品質を維持できる

## Status
Completed (2026-03-03)
