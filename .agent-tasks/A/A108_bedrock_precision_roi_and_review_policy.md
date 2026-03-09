# A108: Bedrock Precision, ROI, and Review Policy

## 優先度
- `P0`

## 目的
- Bedrock を使うべき対象と使わなくてよい対象を監査し、精度とコストの両方を最適化する

## 対象
- `backend/app/services/data_quality_report.py`
- `backend/app/tasks/metrics_tasks.py`
- `backend/scripts/data_quality_snapshot.py`
- `backend/scripts/mlops_monitoring_snapshot.py`
- `backend/tests/`

## 実装タスク
1. `rule_only / bedrock_used / manual_review` の件数と比率を日次で出す
2. `language / product_category / topic_label / priority_score` の正解率監査を作る
3. 商材別に `high_confidence false positive / false negative` を棚卸しする
4. `review_required` に送る条件を定義する
5. `Bedrock を呼ぶ価値がある広告` の基準を文書化する
6. `actual metrics 取得成果` と `priority_score` の相関をレポートに出す

## 完了条件
- [ ] Bedrock 利用の精度と ROI が見える
- [ ] manual review 対象の絞り込み基準がある
- [ ] 商材別の誤判定傾向が D/C に返せる
