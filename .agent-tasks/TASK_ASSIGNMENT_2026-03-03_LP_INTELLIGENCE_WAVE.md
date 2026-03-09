# Task Assignment (2026-03-03) — LP Intelligence Wave

対象: `INC-2026-03-03-CREATIVE-FETCH`
目的: 遷移先LPの取得率・再現性・解析可能性を引き上げる。

## Agent D (Media/Crawling) — 取得基盤
1. D-LP-0303-1: LP取得パイプライン強化
- タイムアウト/リダイレクト/403/JSレンダリングの失敗理由をコード化
- `lp_fetch_status`, `lp_fetch_reason`, `lp_fetched_at` を保存

2. D-LP-0303-2: ブラウザ取得フォールバック
- HTTP取得失敗時のみPlaywrightで再取得
- 最終到達URLとHTTPステータス履歴を証跡保存

3. D-LP-0303-3: LPスナップショット標準化
- full-page screenshot + HTML snapshot を `ad_id` 単位で保存

## Agent A (Data Foundation) — データ品質
1. A-LP-0303-1: LPメタデータ正規化
- `final_url`, `domain`, `path`, `lang`, `title`, `h1_count` 等の抽出と標準化

2. A-LP-0303-2: LP品質ゲート
- 空HTML/極小本文/リダイレクトループを検知し `lp_quality_issue` へ記録

## Agent C (API) — 可視化API
1. C-LP-0303-1: LP取得状態API拡張
- 返却項目: `lp_fetch_status`, `lp_fetch_reason`, `final_url`, `lp_fetched_at`

2. C-LP-0303-2: LP未取得再処理API
- `lp_fetch_status=failed` の再取得対象一覧と再実行エンドポイント

## Agent B (Frontend) — UI/運用
1. B-LP-0303-1: 広告詳細にLP状態表示
- 取得状態、失敗理由、最終URL、取得日時を表示

2. B-LP-0303-2: LP失敗フィルタ追加
- 一覧に「LP未取得」「LP失敗理由」フィルタを追加

## DoD (2026-03-03 EOD)
- LP取得成功率: 80%以上
- LP失敗は理由コード付きで100%可視化
- failed LP をUIから抽出し再処理可能
- ad_id単位で screenshot/html 証跡が参照可能
