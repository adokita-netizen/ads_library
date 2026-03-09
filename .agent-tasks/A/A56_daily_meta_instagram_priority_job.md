# A56: Daily Meta/Instagram Priority Job

## Objective
Meta/Instagramで取りこぼしやすいテーマを日次で優先クロールする。

## Scope
- `scripts/run_daily_meta_instagram_boost.py` を追加
- 学習辞書 + static query から優先クエリを選定
- dry-run/実行レポートを `exports/` に出力

## Acceptance Criteria
- 日次ジョブで priority query が自動選定される
- dry-run で安全に検証可能

## Status
Completed (2026-03-03)
