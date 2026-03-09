# A105: Live Ad Ingestion Freshness Audit

## 優先度: 🅰️ A（クリティカル）

## 目的
- 実広告が毎日増え続ける状態を維持するため、流入量・鮮度・重複率を監査する

## 対象ファイル
- `backend/app/tasks/metrics_tasks.py`
- `backend/app/services/data_quality_report.py`
- `backend/scripts/check_ad_survival.py`

## 実装タスク
1. `daily_new_ads`, `daily_unique_ads`, `duplicate_rate`, `stale_ad_rate` を日次KPI化
2. `platform / keyword / advertiser` 単位で流入量の偏りを監査
3. `7日以内に新規広告が入っていないキーワード` を検出する
4. planner/ops が参照できる `live_ingestion_audit` JSON を出す

## 完了条件
- [x] 日次で「新しい広告が入ってきているか」を可視化できる
- [x] 流入停止や偏りを自動検知できる
- [x] D/C の改善効果を定量比較できる
