# C50: Media Retry Dispatch and Topic API

## 目的
低品質素材の再抽出をAPI運用に組み込み、トピック分類結果をAPIから安定取得できるようにする。

## タスク
1. 再抽出バッチAPI拡張
- `POST /rankings/batch-extract-media` で `needs_media_retry=true` を対象化
- レスポンスに `retry_candidates_dispatched` を追加
- 失敗時は `last_media_retry_error` を保存

2. トピック情報API
- `GET /rankings/{ad_id}` 系レスポンスへ
  - `topic_label`
  - `topic_confidence`
  - `matched_terms`
  - `needs_topic_review`
  を追加
- 一覧APIに `topic` フィルタを追加

3. 契約/回帰テスト
- `needs_media_retry` 対象がディスパッチされるケース
- 通常 pending と retry 対象が混在するケース
- topicフィルタで期待集合が返るケース

## 完了条件
- [x] 再抽出対象がAPI経由で確実に回る
- [x] トピック情報を一覧/詳細APIで取得できる
- [x] 契約テストで回帰を防止できる

