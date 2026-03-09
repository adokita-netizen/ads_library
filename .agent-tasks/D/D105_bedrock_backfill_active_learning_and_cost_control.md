# D105: Bedrock Backfill, Active Learning, and Cost Control

## 優先度
- `P0`

## 目的
- Bedrock 活用を継続運用できるように、backfill・active learning・コスト制御を入れる

## 対象
- `backend/app/tasks/ops_tasks.py`
- `backend/app/tasks/mlops_tasks.py`
- `backend/scripts/`
- `backend/tests/`

## 実装タスク
1. 既存広告に対する backfill 実行順を `priority_score` ベースで決める
2. 同一 advertiser / domain / product 群の cache 再利用を入れる
3. `prompt_version`, `model_name`, `decision_hash` を保存し、重複呼び出しを避ける
4. manual review 結果を再学習用フィードバックとして保存する
5. low-confidence と false-negative を優先再分類する
6. 日次で `cost / calls / cache hit / review reduction / actual metrics uplift` を集計する

## 完了条件
- [ ] Bedrock の backfill が優先度ベースで回る
- [ ] 重複推論と無駄コストが抑えられる
- [ ] manual review の結果が次回判定改善に効く
