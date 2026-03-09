# A54: Platform Expansion Query Strategy

## Objective
媒体ごとの在庫特性に合わせた補助クエリを生成し、回復時の探索幅を拡張する。

## Scope
- helper: `_build_platform_expansion_queries`
- `learned + platform_expansion + static` の優先マージを適用

## Acceptance Criteria
- recovery attemptに `query_source` が記録される
- platform_expansion クエリが fallback 候補に含まれる

## Status
Completed (2026-03-03)
