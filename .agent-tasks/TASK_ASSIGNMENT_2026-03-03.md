# Task Assignment (2026-03-03) — Creative Fetch Incident Response

対象: `INC-2026-03-03-CREATIVE-FETCH`
参照: `IMPLEMENTATION_PLAN_2026-03-03_CREATIVE_LIBRARY.md`

## 優先順位
1. P0: 取得失敗の理由可視化と ad_id 照合担保
2. P0: API失敗時フォールバック実装
3. P0: UIで「ライブラリとして使える」状態を成立
4. P0: 横向き動画の監査可能化

## Agent A (Planner 1 / Data Foundation)
1. A-0303-1: `ad_metadata` 保存ルール統一
- 追加キー: `creative_fetch_status`, `creative_fetch_reason`, `creative_fetch_source`, `creative_fetched_at`, `orientation`, `aspect_ratio`
- 保存時の必須/任意ルールを定義し、NULL許容方針を明文化

2. A-0303-2: データ品質ゲート追加
- `source` 未設定保存を禁止
- `ad_id` 不一致素材を保存拒否（監査ログへ）

## Agent C (Planner 2 / API)
1. C-0303-1: 取得状態API拡張
- 広告詳細APIに `creative_type`, `creative_fetch_source`, `creative_fetched_at`, `creative_fetch_reason` を返却
- 未取得時レスポンス整形を統一

2. C-0303-2: 失敗理由コード標準化
- `not_found_in_api`, `media_url_missing`, `download_failed`, `format_mismatch`, `blocked_or_expired`, `unknown_schema`
- ad_id単位で構造化ログ出力

3. C-0303-3: 再取得対象抽出API
- 「未取得広告一覧」API（理由コード付き）を追加

## Agent D (Planner 1 / Media/Crawling)
1. D-0303-1: API失敗時ブラウザフォールバック
- API失敗時のみ実行
- `ad_id` 一致チェック必須
- `creative_fetch_source=meta_browser_fallback` で保存

2. D-0303-2: 横向き動画監査
- width/height 収集、`aspect_ratio` 算出、`orientation` 保存
- `horizontal` 判定は監査ログ出力 + 日次サンプルレポート

3. D-0303-3: 取得証跡の永続化
- run_id/request_id/task_id を素材保存ログに紐付け

## Agent B (Planner 3 / Frontend)
1. B-0303-1: 広告詳細の取得状態表示
- 表示項目: 種別(image/video), 取得元(api/fallback), 取得日時, 失敗理由

2. B-0303-2: ライブラリ一覧フィルタ
- 「クリエイティブ有無」フィルタ追加
- 「未取得のみ」表示を追加（再取得対象可視化）

3. B-0303-3: 横向き動画注意表示
- orientation=horizontal の明示表示

## ハンドオフ順
1. D → A/C: フォールバック保存項目仕様を共有
2. A → C: 保存ルール確定後、API返却項目を固定
3. C → B: レスポンス契約確定後、UI反映

## DoD (2026-03-03 EOD)
- 取得不能広告が理由コード付きで一覧化される
- API失敗時のフォールバック回収が ad_id 一致で記録される
- UIで取得状態と未取得フィルタが利用可能
- horizontal動画が件数・原因付きで監査可能
