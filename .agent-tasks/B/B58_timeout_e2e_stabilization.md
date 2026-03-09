# B58: Timeout E2E Stabilization

## Objective
quick-crawl timeout系のE2Eを文言揺れに耐える形で安定化する。

## Scope
- `crawl-search.spec.ts` の timeout assertion を overlay text の正規表現判定に変更

## Acceptance Criteria
- CI環境差でも timeout ケースがフレークしない

## Status
Completed (2026-03-03)
