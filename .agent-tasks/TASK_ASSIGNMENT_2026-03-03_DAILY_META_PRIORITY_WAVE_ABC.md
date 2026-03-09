# Task Assignment: 2026-03-03 Daily Meta Priority Wave (ABC)

## Goal
Meta/Instagram の高頻度領域を日次で自動投入し、取りこぼしを継続的に補完する。

## A
- `A56_daily_meta_instagram_priority_job.md` [Completed]

## B
- `B62_priority_job_observability_test.md` [Completed]

## C
- `C58_scheduled_runner_meta_boost_integration.md` [Completed]

## Verification
- `python -m pytest backend/tests/test_meta_instagram_boost.py backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q` (22 passed)
- `python -m scripts.run_daily_meta_instagram_boost --dry-run --query-limit 6`
