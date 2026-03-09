# Task Assignment: 2026-03-03 Learning Prune Wave (ABC)

## Goal
学習辞書の品質を維持するため、prune運用と可視化を追加して回復精度を持続させる。

## A
- `A55_learning_dictionary_prune_ops.md` [Completed]

## B
- `B61_learning_dictionary_size_visibility.md` [Completed]

## C
- `C57_learning_dictionary_prune_api_and_metrics.md` [Completed]

## Verification
- `python -m pytest backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q` (21 passed)
- `python -m scripts.prune_platform_query_learnings --min-attempts 3 --min-success-rate 0.15 --stale-days 14`
- `npx tsc --noEmit`
- `CI=1 npx playwright test e2e/crawl-search.spec.ts` (5 passed)
