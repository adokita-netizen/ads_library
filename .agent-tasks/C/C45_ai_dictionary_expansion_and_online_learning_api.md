# C45: AI Dictionary Expansion + Online Learning API

## 目的
AIによる辞書生成・拡張をAPI化し、定期/手動クロール後に継続学習ループを回す。

## タスク
1. 辞書提案API
- `POST /rankings/dictionary/suggest`
- 入力: 期間/カテゴリ/広告集合
- 出力: `candidate_terms[]`, `reason`, `confidence`

2. 辞書レビューAPI
- `POST /rankings/dictionary/review`
- `adopt/hold/reject` を保存
- 採用時は分類器へ反映

3. 継続学習API
- `POST /rankings/knowledge/rebuild`
- 手動クロール完了時と定期ジョブで呼び出し
- ナレッジスナップショットをバージョン管理

4. 契約テスト
- 提案→レビュー→再分類の一連APIを固定テスト

## 完了条件
- [x] AI辞書提案がAPIで生成できる
- [x] レビュー結果が永続化される
- [x] 定期/手動クロール後に知識再構築が走る
