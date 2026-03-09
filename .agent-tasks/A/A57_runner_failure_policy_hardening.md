# A57: Runner Failure Policy Hardening

## Objective
日次ランナーの失敗時挙動を明確化し、運用時の停止条件を制御可能にする。

## Scope
- `CRAWL_RUNNER_STRICT` による strict/lenient モード追加
- crawl phase の soft-fail (boost失敗許容) を実装

## Acceptance Criteria
- lenient時: main crawl成功なら boost失敗でも継続
- strict時: phase失敗を即時エラー化

## Status
Completed (2026-03-03)
