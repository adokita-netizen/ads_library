# A103: Creative Library Daily Ops & Effect Report

## 優先度: 🅰️ A（クリティカル）

## 目的
- CR/DL/LP 改善が継続運用で崩れないよう、日次オペレーションと改善効果レポートを固定する

## 対象ファイル
- `backend/app/tasks/metrics_tasks.py`
- `backend/app/services/data_quality_report.py`
- `backend/scripts/check_ad_survival.py`

## 実装タスク
1. `creative_library_daily_report` を追加し、前日比の `viewable/downloadable/lp_present/lp_resolved` 差分を出す
2. `platform / advertiser / genre` 単位の悪化検知を入れる
3. `Top regressions` と `Top recoveries` を日次で出す
4. planner がそのまま参照できる JSON 出力を固定する

## 完了条件
- [x] 改善率と悪化広告を前日比で追える
- [x] 復旧の優先順位だけでなく効果も確認できる

## 制約
- 監査とレポートに寄せ、メディア抽出ロジックは変更しない
