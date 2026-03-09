# Agent C: 指示書

## あなたの役割
バックエンド・スコアリングエンジニア。
ヒット判定ロジックの精度向上・ランキングAPIの検証と修正を担当する。

## ★ 現在の方針 (Round 2) ★
**PLANNER2_API_VERIFICATION_R2.md + C_R2_*.md を参照して作業すること。**
Round 2 タスク (C-R2-1〜5) を優先。N+1解消→ページング→Phase 2 API。

---

## タスク一覧

### 済
- ~~C1: メディアURL補完~~
- ~~C2: ヒット判定精度向上~~
- ~~C3: 分析APIパイプライン~~
- ~~C4: APIレスポンス統合~~
- ~~C5: トレンド分析 & ジャンル比較API~~
- ~~C6: データ精度向上 & LP検証API~~
- ~~C7: サムネイルURL修正~~
- ~~C8: ヒットパターンAPI~~
- ~~C9: realtime_crawl_api~~

### 未着手（Planner 2 がAPI検証後に必要分のみ実行）
- C10: production_api（export, search, dashboard-summary磨き込み）
- C11: advanced_analytics_api
- C12: notification_api
- C13: search_and_filter（autocomplete, saved searches）
- C14: ai_analysis_api
- C15: aws_lambda_sqs
- C16: report_generation
- C17: precision_api（hit/non-hit filtering accuracy）
- C18: pro_ranking_api
- C19: scenario_api
- C20: advanced_filter_api
- C21: reports_and_alerts_api
- C22: benchmark_and_comparison_api
- C23: user_preferences_api
- C24: similarity_and_recommendation_api
- C25: webhook_and_integration_api

### 継続改善タスク（C担当・追加）
`CONTINUOUS_IMPROVEMENT_BACKLOG.md` のうち、C担当分を優先実行する。

- C26: CI-013 ランキングAPIのN+1検出と解消（P0）
- C27: CI-014 重い一覧APIにページング上限を設定（P0）
- C28: CI-008 hit score再計算時の前回比較差分を保存（P0）
- C29: CI-036 SQL計測ログを追加しslow queryを抽出（P0）
- C30: CI-052 APIタイムアウト・リトライ方針を明文化（P0）
- C31: CI-003 APIエラーレスポンス仕様の統一（P1）
- C32: CI-015 頻出GETレスポンスの短期キャッシュ導入（P1）
- C33: CI-032 API契約テストを追加（P1）
- C34: CI-040 検索APIに入力バリデーション統一（P1）
- C35: CI-044 `/rankings` のレスポンスサイズ削減（P1）
- C36: CI-056 バックエンド例外分類を統一（P1）
- C37: CI-060 APIバージョン差分の互換性チェック自動化（P2）

着手順（推奨）:
1. C26
2. C27
3. C29
4. C30
5. C28

### 継続改善タスク（C担当・第3弾）
`CONTINUOUS_IMPROVEMENT_BACKLOG.md` の Batch 3 から C 担当分を追加。

- C70: CI-062 外部依存API呼び出しに回路遮断設定を導入（P0）
- C71: CI-078 構造化リクエストログのサンプリング方針導入（P0）
- C72: CI-066 OpenAPI仕様の自動生成と差分検知を導入（P1）
- C73: CI-070 分析系クエリの負荷分離方針を導入（P1）
- C74: CI-082 キャッシュキーのバージョニング規約を導入（P1）
- C75: CI-086 DBクエリタイムアウトガードをAPI層へ導入（P1）
- C76: CI-074 ランキング計算パラメータの検証枠組みを整備（P2）
- C77: CI-090 API廃止ポリシー（deprecation）を運用化（P2）

着手順（推奨）:
1. C70
2. C71
3. C72
4. C75
5. C74

### 継続改善タスク（C担当・第4弾）
CONTINUOUS_IMPROVEMENT_BACKLOG.md の Batch 4 から C 担当分を追加。

- C80: CI-092 APIごとのSLO定義と違反検知を導入（P0）
- C81: CI-108 API保護のレート制御ポリシーを統一（P0）
- C82: CI-096 エンドポイント別の入力スキーマ厳格化（P1）
- C83: CI-100 高負荷APIのフェイルソフト応答を整備（P1）
- C84: CI-112 内部API呼び出しのトレースID連携を統一（P1）
- C85: CI-116 エラーコード辞書と運用対応表を整備（P1）
- C86: CI-104 ランキング重み変更のA/B検証基盤を整備（P2）
- C87: CI-120 API互換性ガイドラインのレビュープロセス整備（P2）

着手順（推奨）:
1. C80
2. C81
3. C82
4. C84
5. C83
### 継続改善タスク（C担当・第5弾）
CONTINUOUS_IMPROVEMENT_BACKLOG.md の Batch 5 から C 担当分を追加。

- C90: CI-123 抽出結果の妥当性スコアリングを導入（P0）
- C91: CI-125 日次Top30のヒット判定品質チェックを追加（P1）

着手順（推奨）:
1. C90
2. C91

### 継続改善タスク（C担当・第6弾）
CONTINUOUS_IMPROVEMENT_BACKLOG.md の Batch 6 から C 担当分を追加。

- C92: CI-128 APIレスポンスの snake_case/camelCase 二重出力を標準化（P0）
- C93: CI-132 APIレスポンス圧縮(gzip/brotli)を標準化（P1）
- C94: CI-136 GraphQL ゲートウェイの導入検討・PoC（P1）
- C95: CI-140 APIゲートウェイでのリクエスト認証基盤導入（P2）

着手順（推奨）:
1. C92
2. C93
3. C94

### 🅰️🅱️🅲 ABC優先度タスク（2026-03-05 追加）

**Priority A（クリティカル）:**
- C60: ads.py/media.pyの空エラーハンドラ修正（pass→適切なエラー処理）

**Priority B（重要）:**
- C61: バックエンドテストカバレッジ向上（主要APIの契約テスト拡充）
- C62: API仕様書(OpenAPI/Swagger)整備（レスポンスモデル定義・ドキュメント強化）

**Priority C（将来拡張）:**
- C63: 負荷テスト・パフォーマンス検証（10,000件データ対応）
- C96: Creative Library の media_status 契約固定とDL失敗理由コード標準化
- C97: Bulk download 結果契約と LP info 契約整列
- C98: CR / DL / LP 契約を frontend 利用前提で完成
- C99: LP 解決情報契約と reason code registry を固定
- C100: Creative Library API 契約テストとレスポンス例を整備
- C101: Recovery Trigger API と operation contract を整備
- C102: Creative Library 用 smoke fixture pack を整備
- C103: live ingest の品質ゲートと dedup 契約を固定

着手順（推奨）:
1. **C60**（ブロッカー：エラーが黙殺される）
2. **C96**（Bの素材状態表示とDL失敗表示の前提）
3. C97
4. C98
5. C62（API仕様→B64のフロント連携に必要）

### Phase 2（プロダクト強化）
- C38: ai_chat_api（Claude API統合 + インテント分類 + 会話履歴 + 構造化レスポンス）
- C39: alert_notification_api（通知CRUD + アラートルール管理 + システム通知生成）
- C40: external_integration_api（Slack通知 + Webhook配信 + CSV定期配信）

### コード品質改修（既存コードの修正）
以下は新機能ではなく、既存コードのバグ修正・改善:
- rankings.py: レスポンスフィールド選択返却、ページネーション、N+1クエリ解消
- ads.py: 動画アップロードバリデーション、escape_like強化、fetch_all_thumbnails非同期化
- media.py: ファイルハンドルclose漏れ、ZIP一時ファイルcleanup、パストラバーサル防御

### ★ 依存関係
Agent A の「リアルメトリクス収集」が先に完了していると、
スコア計算の入力データの品質が上がる。A未完了でも実行可能だが、A完了後に再実行推奨。

---

## 作業開始前に必ず読むファイル
```
backend/app/services/ranking/ranking_service.py
backend/app/services/competitive/trend_predictor.py
backend/app/services/competitive/spend_estimator.py
backend/app/services/prediction/performance_predictor.py
backend/app/services/prediction/fatigue_detector.py
backend/app/services/prediction/feature_engineering.py
backend/app/models/ad_metrics.py
backend/app/models/ad.py
backend/app/models/analysis.py
backend/app/api/endpoints/rankings.py
```

---

## ★★★ コンフリクト防止ルール ★★★

### 触っていいファイル（Agent C の専有領域）
```
backend/app/services/ranking/ranking_service.py
backend/app/services/ranking/__init__.py
backend/app/api/endpoints/rankings.py
backend/app/api/endpoints/ads.py              ← バリデーション修正OK
backend/app/api/endpoints/media.py            ← リソースリーク修正OK
backend/app/services/competitive/spend_estimator.py
backend/app/services/competitive/trend_predictor.py
backend/app/services/prediction/
backend/app/models/ad_metrics.py              ← フィールド追加OK（既存削除NG）
backend/app/models/analysis.py                ← フィールド追加OK（既存削除NG）
backend/scripts/recompute_hit_scores.py
backend/scripts/check_lp_health.py            ← 新規作成OK
backend/app/schemas/                          ← レスポンススキーマ修正OK
```

### 絶対に触ってはいけないファイル
```
# Agent A の領域
backend/scripts/collect_real_metrics.py
backend/scripts/extract_missing_videos.py
backend/scripts/check_ad_survival.py
backend/scripts/fix_bad_thumbnails.py
backend/scripts/backfill_media_urls.py
backend/app/tasks/
backend/app/services/crawling/
backend/app/services/media_extraction.py
backend/app/services/thumbnail_fetcher.py

# Agent B の領域
frontend/
```

### ad_metadata を更新する場合の注意
```python
meta = dict(ad.ad_metadata or {})
meta["latest_hit_score"] = hit_score
meta["latest_score_breakdown"] = signals
ad.ad_metadata = meta
flag_modified(ad, "ad_metadata")
session.commit()

# ★ Agent Aが書き込んだキーを削除・上書きしない
```

### ProductRanking テーブルへの書き込み
```python
# Agent C のみが ProductRanking に書き込む
# hit_score, trend_score, is_hit, rank の更新は Agent C の責任
```

## 作業ディレクトリ
必ず `cd C:/Users/ishit/ads_library/backend` から実行すること。

## 完了報告
作業が終わったら `C/status.md` を作成してステータスを記録すること。
