# C49: Meta Ad-Granularity Extraction API

## 目的
Meta広告ライブラリー相当の粒度（`ad_id`）で、クリエイティブ/動画/本文をAPIで取得・検証できるようにする。

## タスク
1. 抽出詳細API
- `GET /rankings/meta-extraction/{ad_id}`
- 返却:
  - `creative_urls`（image/video）
  - `text_fields`（title/description/ocr/transcript）
  - `extract_source`
  - `quality_score`
  - `missing_fields`

2. 再抽出API
- `POST /rankings/meta-extraction/{ad_id}/retry`
- 再抽出戦略を段階実行（API→Browser→Fallback）
- 結果と失敗理由コードを返却

3. 契約テスト
- 完全取得/部分取得/失敗の3ケース
- `ad_id` 粒度で構造が不変であることを保証

## 完了条件
- [x] ad_id単位で抽出状態をAPI確認できる
- [x] 再抽出APIが実行できる
- [x] 契約テストが通る
