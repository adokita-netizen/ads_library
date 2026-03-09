# A109: Meta Completion Audit and Acceptance

## 優先度
- `P0`

## 目的
- Meta 取得基盤の完成度を数値で監査し、実運用に入れる受け入れラインを定義する

## 対象
- `backend/scripts/run_live_ad_ingestion_wave.py`
- `backend/scripts/run_jp_growth_pipeline.py`
- `backend/app/services/data_quality_report.py`
- `backend/scripts/data_quality_snapshot.py`
- `backend/tests/`

## 実装タスク
1. Meta 広告の `real / estimated / missing` の件数と比率を日次で出す
2. `日本語率 / new save rate / LP attach rate / creative attach rate` を Meta 限定で可視化する
3. `saved_count > 0` でも実数値未取得の広告を抽出して棚卸しする
4. `Meta 完成度スコア` を定義し、80% / 90% の判定条件を文書化する
5. `token valid だが API が失敗する` ケースと `browser fallback 依存` ケースを分けて監査する

## 完了条件
- [ ] Meta の完成度が数字で見える
- [ ] 実数値と推定値の混在状況が監査できる
- [ ] 受け入れ基準が C/D/B に渡せる
