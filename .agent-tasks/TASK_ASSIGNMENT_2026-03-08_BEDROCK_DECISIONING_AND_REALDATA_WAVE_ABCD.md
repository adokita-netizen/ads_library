# TASK ASSIGNMENT: 2026-03-08 Bedrock Decisioning + Real Data Optimization Wave (ABCD)

## 目的
- Bedrock を単なる分類器ではなく、在庫整理・商材整理・実データ優先取得・レビュー削減の中核にする
- 日本語広告 only の前提を崩さず、`actual metrics` が入るべき広告を先に見つけて精度を上げる
- `rule-based -> Bedrock -> manual review` の順でコストと精度を最適化する

## 背景
- 現状は `metadata.language` が薄く、JP only も実データ流入も安定していない
- Bedrock 活用は `language / product / topic` に寄っており、運用判断まで繋がっていない
- 実データ数値は全件に同じ優先度で追うより、`商材価値 x 継続性 x 重要度 x 欠損状況` で優先付けした方が良い

## この wave で固定したいこと
- Bedrock の役割を `分類` から `意思決定補助` まで広げる
- 日本語広告の中で `どの広告から actual metrics を取りに行くか` を AI で優先付けする
- `manual review` は「曖昧・高価値・高リスク」だけに絞る
- prompt / model / confidence / fallback / cache の運用契約を C が固定する

## Bedrock 活用方針
1. `language / product_category / subcategory / topic_label / offer_type / funnel_type` を推定する
2. `actual metrics priority score` を出し、実データ取得対象の優先順位を決める
3. `review_required / review_reason / confidence_band` を出し、人手レビューを必要最小限にする
4. prompt version と model version を保存し、A が精度監査できるようにする
5. rule-based で確定できるケースは Bedrock を呼ばず、unknown / high-value / ambiguous のみ AI を使う

## Agent A
- `A108_bedrock_precision_roi_and_review_policy.md`
- 役割:
  - Bedrock 判定精度と ROI の監査
  - review 対象の絞り込み基準作成
  - 商材別の誤判定分析

## Agent B
- `B100_bedrock_provenance_review_and_priority_ui.md`
- 役割:
  - Bedrock 由来の商材・優先度・レビュー理由を UI で可視化
  - `actual metrics priority` の一覧導線
  - review queue の運用 UI

## Agent C
- `C115_bedrock_decision_contract_and_prompt_registry.md`
- `C116_bedrock_review_queue_and_priority_api.md`
- 役割:
  - Bedrock decision schema / prompt registry / confidence contract
  - review queue / priority API / provenance API の固定

## Agent D
- `D104_bedrock_triage_and_priority_scoring_pipeline.md`
- `D105_bedrock_backfill_active_learning_and_cost_control.md`
- 役割:
  - Bedrock triage pipeline
  - actual metrics priority scoring
  - backfill / cache / cooldown / active learning / cost control

## 実行順
1. C115
2. D104
3. C116
4. D105
5. A108
6. B100

## 受け渡しルール
- D -> C/A/B:
  - `decision_payload`
  - `priority_score`
  - `review_required`
  - `review_reason`
  - `prompt_version`
  - `model_name`
- C -> B:
  - UI で表示すべき enum / confidence band / provenance label
- A -> D/C:
  - 誤判定セット
  - Bedrock 利用対象に残すべきケース
  - ルールで十分なケースの削減提案

## 成功条件
- Bedrock が「分類だけ」で終わらず、実データ優先度と review 削減に効いている
- `JP only` と `actual metrics first` の両立ができる
- prompt / model / confidence / fallback が追跡可能になっている
