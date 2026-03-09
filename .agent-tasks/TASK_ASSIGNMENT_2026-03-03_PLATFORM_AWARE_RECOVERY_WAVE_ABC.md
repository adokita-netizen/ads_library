# Task Assignment: 2026-03-03 Platform-Aware Recovery Wave (ABC)

## Goal
quick-crawlの低件数回復を媒体別最適化し、運用UIで要注意媒体を即認識できる状態にする。

## A (Data)
- `A51_platform_recovery_feedback.md` [Completed]

## B (Frontend)
- `B57_crawl_diagnostics_focus_platform.md` [Completed]

## C (Backend/API)
- `C53_platform_aware_recovery_strategy.md` [Completed]

## Verification
- `python -m pytest backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q`
- `npx tsc --noEmit`
- `npx playwright test e2e/crawl-search.spec.ts`
