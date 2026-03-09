# C56: Query Source Diagnostics API

## Objective
回復クエリのソース別成果（learned/platform_expansion/static）を追跡可能にする。

## Scope
- recovery attemptに `query_source` を記録
- diagnostics summaryへ `platform_expansion_attempts/success_rate` を追加

## Acceptance Criteria
- APIから query source 別の主要KPIが取得できる
- 後続UIで可視化できる形で返る

## Status
Completed (2026-03-03)
