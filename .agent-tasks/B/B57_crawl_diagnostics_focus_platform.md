# B57: Crawl Diagnostics Focus Platform

## Objective
診断カードで「要注意媒体」を即時判定し、運用判断を短縮する。

## Scope
- CrawlPanel 健全性カードに high-risk platform を表示
- `platforms[].zero_save_rate` を利用して最大値媒体を出す

## Acceptance Criteria
- 24h診断で要注意媒体が表示される
- 診断取得失敗時もUI崩れなし

## Status
Completed (2026-03-03)
