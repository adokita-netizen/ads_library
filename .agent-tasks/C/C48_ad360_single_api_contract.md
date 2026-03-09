# C48: Ad360 Single API Contract

## 目的
1広告に必要な情報を単一APIで返し、フロントが迷わず描画できる契約にする。

## タスク
1. Ad360 API追加
- `GET /rankings/ad360/{ad_id}`
- 返却: 基本情報 + クリエイティブ + テキスト + 分析 + LP情報 + 品質メタ

2. レスポンス契約固定
- `sections`: `core`, `creative`, `text`, `analysis`, `lp`, `quality`
- 各セクションの `missing_fields[]` を返却

3. 契約テスト
- 完全データ/欠損データ/失敗データの3ケース
- フィールド欠落時でもレスポンス構造は不変

## 完了条件
- [x] ad360 APIが利用可能
- [x] 契約テストが通る
- [x] 欠損時の構造が安定
