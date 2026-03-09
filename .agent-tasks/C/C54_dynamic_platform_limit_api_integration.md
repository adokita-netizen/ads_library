# C54: Dynamic Platform Limit API Integration

## Objective
quick-crawl の初回/回復実行に媒体別limitを適用し、収集効率を最適化する。

## Scope
- helper追加: `_compute_platform_limit_map`
- `_crawl_platforms_no_expand` に `per_platform_limits` を追加
- recovery実行でも同limit mapを活用

## Acceptance Criteria
- quick-crawl response に `platform_limits` が返る
- 既存 contract を破壊しない（回帰テスト通過）

## Status
Completed (2026-03-03)
