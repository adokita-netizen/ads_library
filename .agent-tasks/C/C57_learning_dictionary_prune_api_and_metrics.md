# C57: Learning Dictionary Prune API and Metrics

## Objective
学習辞書の保守をAPI/運用スクリプト双方で実行可能にし、診断へ反映する。

## Scope
- `POST /rankings/learning/prune` 追加
- diagnostics summary に `learning_entries` 追加
- recoveryでの自動prune適用

## Acceptance Criteria
- APIで prune 結果（before/after/removed/kept）が取得できる
- UI側で学習辞書サイズが確認できる

## Status
Completed (2026-03-03)
