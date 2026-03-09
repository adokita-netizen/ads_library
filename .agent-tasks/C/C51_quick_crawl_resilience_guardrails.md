# C51: Quick-Crawl Resilience Guardrails

## Objective
クロール結果フォーマット異常や媒体単位の戻り値不整合で `quick-crawl` 全体が 500 になる事象を防ぐ。

## Scope
- `CrawlerManager.search_all_platforms` の result 型ガード（None/non-list）
- `_save_crawled_ads` の防御（non-dict/non-list/invalid ad object skip）
- `quick-crawl` レスポンスに `skipped_invalid_count` を露出

## Acceptance Criteria
- 1媒体が `None` を返しても quick-crawl は completed で返る
- 保存処理で invalid item が混ざっても全体エラーにしない
- 異常件数がレスポンスで追跡できる

## Status
Completed (2026-03-03)
