# B56: Crawl Health Diagnostics Panel

## Objective
クロール画面から即座に「成功率/保存0件率/主因」を見れるようにする。

## Scope
- `CrawlPanel` で `/rankings/crawl-status/diagnostics` を取得
- 24h健全性カード（success/zero-save/top cause）を表示

## Acceptance Criteria
- 最新24hの健全性値が表示される
- 診断APIが落ちても既存クロールUIは継続動作する

## Status
Completed (2026-03-03)
