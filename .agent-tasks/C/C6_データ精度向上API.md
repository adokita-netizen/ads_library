# Agent C タスク: データ精度向上 & LP検証API

## 方向性
広告データの「精度」を上げる。destination_url（LP遷移先）が本当に生きているか検証し、
広告の品質スコアをより正確にするためのAPIを追加する。

## やってほしいこと

### 1. LP到達性検証エンドポイント
`GET /rankings/lp-health`
- 全広告のdestination_urlに対してHTTPステータスを確認するバッチ処理はスクリプト側でやるが、
  結果を返すAPIを作る
- ad_metadataに `lp_status` (200/301/404/timeout等) と `lp_checked_at` を記録する
  **スクリプト** `backend/scripts/check_lp_health.py` を新規作成して実行
- APIはad_metadataからlp_statusを読んで集計を返す:
  - total_checked, status_200, status_redirect, status_error, unchecked
  - 問題のあるLP一覧（404やtimeout）

### 2. 広告品質サマリーAPI
`GET /rankings/quality-summary`
- 各広告の「データ完成度」をスコア化して返す
- 完成度の基準:
  - title あり (+10), description あり (+10)
  - destination_url あり (+10), LP到達可能 (+10)
  - thumbnail_url あり (+10), image_url あり (+10)
  - video_url あり (+10, 動画広告の場合)
  - category あり (+10)
  - score_breakdown あり (+10)
  - days_running > 0 (+10)
- 全体の平均完成度、低品質広告リスト（完成度60%以下）を返す

### 3. hit-ads レスポンスに destination_url を確実に含める
現在の `/rankings/hit-ads` レスポンスに `destination_url` が含まれているか確認。
含まれていなければ追加する。フロントエンドがLPリンクを表示するために必要。
同様に `description`（広告本文）も確実に含める。

## check_lp_health.py について
- `backend/scripts/check_lp_health.py` を新規作成
- 全広告のdestination_urlにHEADリクエスト（タイムアウト10秒）
- レスポンスステータスをad_metadataの `lp_status` に記録
- `lp_checked_at` にISO8601タイムスタンプ記録
- flag_modified パターン必須
- print文は英語のみ
- リクエスト間隔0.5秒（レート制限）

## 制約
- INSTRUCTIONS.md のコンフリクト防止ルール厳守
- API: `backend/app/api/endpoints/rankings.py` に追加
- スクリプト: `backend/scripts/check_lp_health.py` 新規作成OK
  （Agent Cの ad_metadata キー: lp_status, lp_checked_at, data_completeness）
- 既存エンドポイントを壊さない
