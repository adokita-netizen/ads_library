# B63: Runner Policy Regression Tests

## Objective
runner失敗ポリシー変更の回帰をテストで固定する。

## Scope
- `backend/tests/test_scheduled_crawl_runner.py` 追加
- lenient soft-fail / main fail hard-error のケースを検証

## Acceptance Criteria
- policyテストがCIで再現可能に通る

## Status
Completed (2026-03-03)
