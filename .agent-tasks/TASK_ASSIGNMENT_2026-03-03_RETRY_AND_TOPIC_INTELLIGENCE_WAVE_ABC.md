# Task Assignment (2026-03-03) - Retry and Topic Intelligence Wave

## ゴール
クロール後に「低品質素材が再抽出される」「広告文/CRからトピック分類が強化される」「定期運用で知識辞書が拡張される」状態まで持っていく。

## 配分
- A48: `A48_copy_creative_topic_knowledge_expansion.md`
- C50: `C50_media_retry_dispatch_and_topic_api.md`
- B54: `B54_readable_ui_and_retry_operation_flow.md`

## 実行順
1. C50: 再抽出ディスパッチAPIとトピック判定API契約を確定
2. A48: 広告文/CR/OCRのキーワード辞書拡張と分類精度改善
3. B54: UI簡素化 + フィルタ導線 + 再抽出運用導線の統合

## DoD
- [ ] 低品質素材 `needs_media_retry=true` がバッチで再抽出される
- [ ] GLP-1 / AGA を含む複数ジャンルが広告文/CRから自動判定される
- [ ] UIでジャンル別フィルタと再抽出状態が追える
- [ ] API/E2E/ブラウザ実機テストの再発防止が整っている
