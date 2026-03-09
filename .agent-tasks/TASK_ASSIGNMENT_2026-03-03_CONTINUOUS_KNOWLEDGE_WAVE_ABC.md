# Task Assignment (2026-03-03) — Continuous Knowledge Wave (A/B/C)

## ゴール
- クロールを `定期 + 手動` の二系統で回す
- 取得データからナレッジを継続蓄積する
- 辞書をAI提案で自動拡張し、レビューして運用に反映する

## 追加配分
- A43: `A43_continuous_crawl_knowledge_pipeline.md`
- B49: `B49_knowledge_feedback_ui_and_dictionary_review.md`
- C45: `C45_ai_dictionary_expansion_and_online_learning_api.md`

## 実行順
1. C45: API契約（提案/レビュー/再構築）を先に固定
2. A43: 定期+手動クロールとナレッジ蓄積を実装
3. B49: UIで運用ループを回せるようにする

## DoD
- [ ] 定期/手動クロール両方で学習ループが起動する
- [ ] AI辞書提案がレビュー経由で反映される
- [ ] 判定根拠とHIT寄与が画面で追える
- [ ] 回帰テストで一連フローが担保される

