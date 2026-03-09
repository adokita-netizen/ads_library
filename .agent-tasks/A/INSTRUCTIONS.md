# Agent A: 指示書

## あなたの役割
バックエンド・データ基盤エンジニア。
広告データの収集・補完・品質向上を担当する。

## ★ 現在の方針 (Round 2) ★
**PLANNER1_DATA_FOUNDATION_R2.md + A_R2_*.md を参照して作業すること。**
Round 2 タスク (A-R2-1〜6) を優先。既存 A8-A32 は Round 2 完了後。

---

## タスク一覧

### 済
- ~~A1: サムネイル品質修復~~
- ~~A2: リアルメトリクス収集パイプライン~~
- ~~A3: データ品質パイプライン~~
- ~~A4: データ鮮度管理 & エクスポート~~
- ~~A5: データ補完とLP検証~~
- ~~A6: クリエイティブ構造解析~~
- ~~A7: new_data_analysis~~

### 未着手（Planner 1 が優先度順に実行）
- A8: production_data_quality（NULL scores修正、creative analysis補完）
- A9: advertiser_analysis
- A10: trend_detection
- A11: nlp_copy_analysis
- A12: hit_predictor
- A13: lp_scoring
- A14: competitive_intelligence
- A15: precision_boost
- A16: fine_genre_classification
- A17: metrics_delta_tracking（再生増加数計算）
- A18: ad_scenario_generator
- A19: full_data_pipeline（全58件に全分析スクリプト実行）
- A20: ab_testing_framework
- A21: data_enrichment_v2
- A22: hit_prediction_ml
- A23: duplicate_detection
- A24: text_analytics

### 継続改善タスク（A担当・追加）
`CONTINUOUS_IMPROVEMENT_BACKLOG.md` のうち、A担当分を優先実行する。

- A25: CI-001 DB接続失敗時の指数バックオフ再試行を統一（P0）
- A26: CI-002 主要バッチの冪等性チェックを追加（P0）
- A27: CI-007 `ad_metadata` スキーマバリデーションを導入（P0）
- A28: CI-025 本番向け設定の秘密情報チェックをCIに追加（P0）
- A29: CI-026 CORS/許可オリジンの環境別制御を明確化（P0）
- A30: CI-030 backend最重要テストを `smoke` として固定（P0）
- A31: CI-016 DBインデックス見直し（検索・並び替え列）（P1）
- A32: CI-034 ローカル開発セットアップを10分以内に短縮（P1）

着手順（推奨）:
1. A25
2. A27
3. A30
4. A28
5. A26

### 継続改善タスク（A担当・第3弾）
`CONTINUOUS_IMPROVEMENT_BACKLOG.md` の Batch 3 から A 担当分を追加。

- A60: CI-061 メトリクス収集ジョブに再入防止ロックを追加（P0）
- A61: CI-077 トランザクションタイムアウトの標準値統一（P0）
- A62: CI-065 データ保持ポリシーとアーカイブ手順を整備（P1）
- A63: CI-069 `ad` と `ad_metrics` の整合性日次チェック追加（P1）
- A64: CI-081 マイグレーション前提チェックCLIを追加（P1）
- A65: CI-085 エクスポート処理のPIIマスキング強化（P1）
- A66: CI-073 主要指標の異常検知ルールを追加（P2）
- A67: CI-089 障害対応Runbookの分岐図を整備（P2）

着手順（推奨）:
1. A60
2. A61
3. A63
4. A64
5. A65

### 継続改善タスク（A担当・第4弾）
CONTINUOUS_IMPROVEMENT_BACKLOG.md の Batch 4 から A 担当分を追加。

- A80: CI-091 重要更新処理に排他制御キーを統一導入（P0）
- A81: CI-107 DB接続プール枯渇の早期警告を追加（P0）
- A82: CI-095 バッチ実行履歴の標準メタデータ保存（P1）
- A83: CI-099 データ補完ジョブの優先度キュー化（P1）
- A84: CI-111 主要テーブルの論理削除/復元手順を明確化（P1）
- A85: CI-115 データ品質レポートのSlack通知整備（P1）
- A86: CI-103 データ移行手順のチェックリストを自動生成（P2）
- A87: CI-119 運用手順の定期棚卸しを自動タスク化（P2）

着手順（推奨）:
1. A80
2. A81
3. A82
4. A83
5. A85
### 継続改善タスク（A担当・第5弾）
CONTINUOUS_IMPROVEMENT_BACKLOG.md の Batch 5 から A 担当分を追加。

- A90: CI-124 日次ジョブでTop30件を必ず収集する監査を追加（P0）
- A91: CI-127 日次実行レポートに「取得30件/キー抽出/ヒット判定」を統合表示（P1）

着手順（推奨）:
1. A90
2. A91

### 継続改善タスク（A担当・第6弾）
CONTINUOUS_IMPROVEMENT_BACKLOG.md の Batch 6 から A 担当分を追加。

- A92: CI-129 バッチジョブ実行の排他ロックをRedis分散ロックに統一（P0）
- A93: CI-133 データ品質ダッシュボードのAPI化（P1）
- A94: CI-137 DB接続の read replica 分離導入（P1）
- A95: CI-141 データリネージ（系譜）の追跡基盤構築（P2）

着手順（推奨）:
1. A92
2. A93
3. A94

### 🅰️ ABC優先度タスク（2026-03-05 追加）

**Priority A（クリティカル）:**
- A96: Lambda sourceIpエラー修正（API Gateway経由のsourceIp KeyError修正）

**Priority B（重要）:**
- A97: CI/CDパイプライン完全自動化（GitHub Actions→ビルド→デプロイ一気通貫）
- A98: 本番監視ダッシュボード構築（CloudWatch/Prometheusの可視化）
- A99: DBバックアップ自動化（RDSスナップショットスケジュール）

**Priority C（将来拡張）:**
- A100: MLOpsパイプライン（モデルバージョン管理・再学習・品質ゲート）
- A101: Creative Library の欠損率監査と復旧KPI整備
- A102: Creative / Download / LP の欠損監査と復旧優先順位キュー整備
- A103: Creative Library の日次運用レポートと改善効果差分の可視化
- A104: Creative Library の SLO 監視と運用アラート基準整備
- A105: 実広告流入の鮮度/重複率/停止キーワード監査

着手順（推奨）:
1. **A96**（ブロッカー：APIが動かない可能性）
2. A97
3. A99
4. A98
5. A101
6. A102
7. A100

### Phase 2（プロダクト強化）
- A37: smart_alert_engine（アラートルール定義 + 評価エンジン + 通知生成）
- A38: data_freshness_automation（鮮度スコアリング + 日次品質レポート + 自動再クロール）

### コード品質改修（既存コードの修正）[ALL COMPLETED]
以下は新機能ではなく、既存コードのバグ修正・改善:
- ~~database.py: Lambda pool_size=1に縮小、pool_recycle=300s、connect_timeout追加~~ ✅ A33
- ~~config.py: 本番デフォルトsecret_key排除、DB secret失敗時エラー化~~ ✅ A34
- ~~lambda_handler.py: エラーレスポンスマスク、cleanup トランザクション分離、init条件付き実行~~ ✅ A35
- ~~sqs_ecs_trigger.py: batchItemFailures対応（SQSリトライ誘発）~~ ✅ A36
- ~~lambda.tf: FunctionResponseTypes設定追加~~ ✅ A36

---

## 作業開始前に必ず読むファイル
```
backend/app/models/ad.py                        ← Adモデル定義
backend/app/models/ad_metrics.py                ← AdDailyMetrics定義
backend/app/core/database.py                    ← SyncSessionLocal
backend/app/api/endpoints/settings.py           ← load_api_keys_from_db
backend/app/services/crawling/meta_crawler.py   ← _estimate_ad_metrics関数
backend/app/tasks/metrics_tasks.py              ← メトリクス収集タスク
backend/app/services/media_extraction.py        ← MediaExtractor
```

---

## ★★★ コンフリクト防止ルール ★★★

### 触っていいファイル（Agent A の専有領域）
```
backend/scripts/collect_real_metrics.py
backend/scripts/check_ad_survival.py
backend/scripts/classify_ads.py
backend/scripts/fix_destination_urls.py
backend/scripts/fix_titles.py
backend/scripts/collect_delivery_dates.py
backend/app/tasks/metrics_tasks.py
backend/app/core/database.py              ← エンジン設定修正OK
backend/app/core/config.py                ← バリデータ追加OK
backend/lambda_handler.py                 ← エラーハンドリング修正OK
backend/sqs_ecs_trigger.py                ← 失敗処理修正OK
backend/app/models/ad.py                  ← フィールド追加OK（既存削除NG）
backend/app/models/ad_metrics.py          ← フィールド追加OK（既存削除NG）
```

### 絶対に触ってはいけないファイル
```
# Agent D の領域（メディア・クローリング）
backend/scripts/extract_missing_videos.py
backend/scripts/backfill_media_urls.py
backend/scripts/fix_bad_thumbnails.py
backend/app/services/media_extraction.py
backend/app/services/thumbnail_fetcher.py
backend/app/services/crawling/
backend/app/tasks/crawl_tasks.py
backend/app/tasks/media_tasks.py

# Agent C の領域（スコアリング）
backend/app/services/ranking/
backend/app/api/endpoints/rankings.py
backend/app/services/competitive/
backend/app/services/prediction/
backend/scripts/check_lp_health.py
backend/scripts/recompute_hit_scores.py

# Agent B の領域（フロントエンド）
frontend/
```

### ad_metadata を更新する場合の注意
```python
meta = dict(ad.ad_metadata or {})
meta["your_key"] = "your_value"
ad.ad_metadata = meta
flag_modified(ad, "ad_metadata")
session.commit()
```

## 作業ディレクトリ
必ず `cd C:/Users/ishit/ads_library/backend` から実行すること。

## 完了報告
作業が終わったら `A/status.md` にステータスを記録すること。
