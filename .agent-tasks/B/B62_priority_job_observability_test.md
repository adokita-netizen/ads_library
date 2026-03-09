# B62: Priority Job Observability Test

## Objective
priority crawl job の選定品質をテストで担保し、運用時の可視性を維持する。

## Scope
- `backend/tests/test_meta_instagram_boost.py` を追加
- learned success を優先する query 選定を検証

## Acceptance Criteria
- priority query selector の回帰が自動テストで検知できる

## Status
Completed (2026-03-03)
