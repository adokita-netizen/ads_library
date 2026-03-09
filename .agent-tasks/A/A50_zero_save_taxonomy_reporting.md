# A50: Zero-Save Taxonomy Reporting

## Objective
`saved_ads_count=0` を定量化し、原因分類を継続監視可能にする。

## Scope
- `quick_crawl_daily_report.py` に zero-save 原因分類を追加
- 媒体別 `zero_save_rate` / `failure_rate` をJSONに出力

## Acceptance Criteria
- レポートに `zero_save_completed`, `zero_save_causes`, `platforms[]` が含まれる
- 既存 success/failure 集計との互換性を維持

## Status
Completed (2026-03-03)
