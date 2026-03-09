# C52: Crawl Status Diagnostics API

## Objective
`quick-crawl` の失敗・保存0件の偏りを API で可視化し、運用上の原因特定を高速化する。

## Scope
- `GET /rankings/crawl-status/diagnostics`
- 出力: summary, zero_save_causes, platform breakdown
- helper: `zero-save cause` 分類ロジック

## Acceptance Criteria
- `hours/limit` 指定で集計可能
- platformごとの `zero_save_rate` / `failure_rate` が返る
- 保存済みケースは `saved` と分類される

## Status
Completed (2026-03-03)
