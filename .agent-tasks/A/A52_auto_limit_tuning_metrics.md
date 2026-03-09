# A52: Auto Limit Tuning Metrics

## Objective
媒体別の直近成果に応じて crawl limit を自動調整し、低成果媒体の探索量を増やす。

## Scope
- 直近24hの completed job から platform別成功率/zero-save率を算出
- quick-crawl 初回実行に `platform_limits` を適用

## Acceptance Criteria
- response/progress_detail に `platform_limits` が含まれる
- 低成果媒体のlimitが増加し、高成果媒体は抑制される

## Status
Completed (2026-03-03)
