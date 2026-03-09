# C58: Scheduled Runner Meta Boost Integration

## Objective
日次ランナーで Meta/Instagram priority crawl を自動実行する。

## Scope
- `scripts/scheduled_crawl_runner.py` の crawl phase に
  - `scheduled_crawl.py`
  - `run_daily_meta_instagram_boost.py`
  を連結

## Acceptance Criteria
- scheduled runner 実行時に priority boost ジョブが走る
- 既存フェーズ構造を壊さない

## Status
Completed (2026-03-03)
