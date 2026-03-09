# Task Assignment (2026-03-03) — Topic Gap Wave (A/B/C)

## 目的
- 広告文/CR画像/OCR/LP証拠で分類する
- 医療限定ではなく全カテゴリの見逃しを減らす
- 「Meta上の実感」と「本システムの表示」の乖離を縮小する

## 追加配分
- A42: `A42_adcopy_taxonomy_and_medical_signal_dictionary.md`
- B48: `B48_topic_evidence_ui_and_mismatch_review.md`
- C44: `C44_topic_classification_api_and_gap_metrics.md`

## 実行順
1. A42: 辞書・分類ロジック・バックフィル
2. C44: 分類API/乖離監査API/契約テスト
3. B48: 根拠表示UI・乖離レビューUI・E2E

## DoD
- [ ] 主要カテゴリ全体で見逃し率が改善
- [ ] 判定根拠とHIT寄与がUIで見える
- [ ] topic gapがAPIで観測できる
- [ ] 契約テスト + E2Eで回帰防止
