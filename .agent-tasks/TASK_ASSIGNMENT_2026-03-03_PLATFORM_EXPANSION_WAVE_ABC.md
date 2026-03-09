# Task Assignment: 2026-03-03 Platform Expansion Wave (ABC)

## Goal
媒体特性に応じた補助クエリ拡張を回復ロジックへ組み込み、query source別に成果を追跡する。

## A
- `A54_platform_expansion_query_strategy.md` [Completed]

## B
- `B60_platform_expansion_metrics_ui.md` [Completed]

## C
- `C56_query_source_diagnostics_api.md` [Completed]

## Verification
- `python -m pytest backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q` (20 passed)
- `npx tsc --noEmit`
- `CI=1 npx playwright test e2e/crawl-search.spec.ts` (5 passed)
