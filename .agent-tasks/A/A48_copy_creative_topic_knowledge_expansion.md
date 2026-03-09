# A48: Copy/Creative Topic Knowledge Expansion (DataOps)

## 目的
広告文・OCR・クリエイティブ属性を使って、GLP-1/AGAを含むジャンル推定の取りこぼしを減らす。

## タスク
1. トピック辞書の自動拡張
- 入力: `title`, `description`, OCRテキスト, LPキーワード
- 出力: `topic_candidates`, `topic_confidence`, `matched_terms`
- 日次で新規語彙を `ad_metadata.topic_dictionary_suggestions` に蓄積

2. 多ソース分類スコア
- 広告文/画像/OCR/LPの各ソースに重みを持たせる
- 最終ラベルを `ad_metadata.topic_label` に保存
- 低信頼は `needs_topic_review=true` を付与

3. ギャップ監査
- 主要カテゴリ(医療ダイエット/AGA/美容/金融/教育 ほか)の件数推移
- 「クロール件数 > 分類件数」の乖離を日次アラート化

## 完了条件
- [x] 広告文+OCR+LPの統合分類が保存される
- [x] 辞書提案が継続的に蓄積される
- [x] 乖離レポートで欠落カテゴリを追える
