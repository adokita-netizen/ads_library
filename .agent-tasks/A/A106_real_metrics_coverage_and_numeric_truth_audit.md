# A106: Real Metrics Coverage & Numeric Truth Audit

## 優先度
- `P0`

## 目的
- 実データ数値が本当に入っている項目と、推定・欠損の項目を分離して監査する

## 対象
- `backend/app/services/data_quality_report.py`
- `backend/app/tasks/metrics_tasks.py`
- `backend/scripts/data_quality_snapshot.py`
- `backend/scripts/daily_execution_report.py`
- `backend/tests/`

## 実装タスク
1. `spend / impressions / reach / view_count / lp_score / extract_quality_score` について `real / estimated / missing` を集計する
2. 媒体別・ジャンル別・直近7日/30日別の coverage を出す
3. `stale_real_metrics_count`, `estimated_only_count`, `missing_numeric_count` を日次 report に追加する
4. `priority_backfill_targets` を出し、D が backfill しやすい JSON にする
5. 前日差分で悪化した数値品質を report / alert 候補に出す

## 完了条件
- [ ] 実数値カバレッジが日次 JSON で見える
- [ ] 推定値依存の高い媒体 / ジャンルが特定できる
- [ ] D の backfill 優先順位に直接渡せる

## ハンドオフ
- to C:
  - 監査で必要な provenance field 一覧
- to B:
  - UI で warning すべき `stale / estimated_only / missing`
- to D:
  - backfill 優先 ad / platform / keyword の queue 候補
