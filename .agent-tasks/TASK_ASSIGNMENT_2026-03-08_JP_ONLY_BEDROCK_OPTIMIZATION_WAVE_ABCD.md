# TASK ASSIGNMENT: 2026-03-08 JP-Only + Bedrock Optimization Wave (ABCD)

## 目的
- 日本語広告だけを主分析対象に固定し、非日本語広告の混入でランキングや分析精度が落ちる状態を止める
- Bedrock を使って商材分類・言語判定・トピック補正・ノイズ除去を強化する
- `JP only` の品質ゲートを ingestion / API / UI / audit の全レイヤで揃える

## 現状認識
- `backend/vaap_local.db` の `ads` は 1,482 件
- `metadata.language` は実質未設定
- title + description の日本語率 10% 未満の広告が 656 件あり、スペイン語・ポルトガル語などが混在

## 最終ゴール
- 主分析対象の広告は日本語広告に限定される
- 非日本語広告は `exclude_from_analysis` または別キューへ隔離される
- Bedrock による `language / product_category / topic_label / exclude_reason` が安定供給される
- frontend では `JP / non-JP / 未判定` が可視化され、必要なら `JP only` で固定できる

## Agent A
- `A107_japanese_inventory_audit_and_exclusion_policy.md`
- 役割:
  - 日本語広告比率の監査
  - 除外基準の定義
  - Bedrock 判定の精度レビュー

## Agent B
- `B99_japanese_only_filter_and_language_badges_ui.md`
- 役割:
  - `JP only` UI
  - 言語バッジ
  - 非日本語/未判定時の warning と empty state

## Agent C
- `C113_language_and_product_taxonomy_contract.md`
- `C114_bedrock_classification_gateway_contract.md`
- 役割:
  - language / taxonomy / exclusion 契約の固定
  - Bedrock 呼び出し結果の response shape 標準化

## Agent D
- `D102_japanese_gate_ingestion_and_quarantine.md`
- `D103_bedrock_language_product_classifier_pipeline.md`
- 役割:
  - ingestion 時の JP gate
  - quarantine 運用
  - Bedrock による商材分類 / 言語判定 / topic 補正

## 実行順
1. C113
2. C114
3. D102
4. D103
5. A107
6. B99

## 受け渡しルール
- D → C/A:
  - Bedrock 入出力例
  - language 判定根拠
  - quarantine reason
- C → B:
  - `language_status`, `language_source`, `product_category`, `exclude_from_analysis`, `exclude_reason`
- A → D/B:
  - 閾値調整が必要な誤判定サンプル
  - UI で強調すべき warning 条件
