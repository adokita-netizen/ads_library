# A107: Japanese Inventory Audit & Exclusion Policy

## 優先度
- `P0`

## 目的
- 日本語広告だけを分析対象にするための監査と除外ポリシーを固める

## 対象
- `backend/app/services/data_quality_report.py`
- `backend/app/tasks/metrics_tasks.py`
- `backend/scripts/data_quality_snapshot.py`
- `backend/scripts/daily_execution_report.py`
- `backend/tests/`

## 実装タスク
1. `jp / non-jp / unknown` 件数を日次で集計する
2. `jp_char_ratio`, `language_source`, `exclude_from_analysis`, `exclude_reason` の coverage を出す
3. Bedrock 判定と rule-based 判定の不一致サンプルを監査する
4. 除外基準を定義する
5. `manual_review_queue` を出して D に渡す

## 完了条件
- [ ] 日本語広告比率が毎日見える
- [ ] 除外/隔離の基準が文書化される
- [ ] Bedrock 判定の精度確認が回る
