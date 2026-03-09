# A51: Platform Recovery Feedback Loop

## Objective
低成果媒体を優先して再試行する回復ループを導入し、取りこぼしを減らす。

## Scope
- ベース取得件数を媒体別に計測
- 0件/低件数媒体を優先して fallback query を再実行
- 回復attemptごとに媒体別件数を記録

## Acceptance Criteria
- recovery payloadに `base_platform_counts` が含まれる
- attempt詳細に `platform_counts` が含まれる

## Status
Completed (2026-03-03)
