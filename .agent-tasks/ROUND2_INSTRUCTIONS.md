# Round 2 指示書 — 2026-03-01
# 方針: Phase 1 残タスクを高速消化 + Phase 2 着手開始

---

## 全体方針

### 現状
- コード: 80%+ → 約95%完成（コード品質改修も全Agent完了）
- データ: 176件（目標200+には未達）
- API: C1-C37 完了、105+エンドポイント実装済み
- UI: B1-B40 完了、22ビュー実装済み
- メディア: D1-D32 完了、パイプライン動作確認済み

### Round 2 の目標
1. **Agent A**: 未着手の Phase 1 データ品質タスクを高速消化 → Phase 2 着手
2. **Agent B**: B29-B32 消化 → Phase 2 (B41-B44) 着手
3. **Agent C**: Phase 2 (C38-C40) 着手 — AI/通知/外部連携
4. **Agent D**: Phase 1 残タスク(D7-D25)から高優先度を選択消化 → Phase 2 着手

---

## Agent A: 次の指示 (Planner 1)

### 即座にやること (優先度順)

#### A-R2-1: A8 Production Data Quality (P0)
**目的**: 176件のNULLスコア・欠損creative analysis を修正
**ファイル**: 専有領域内のスクリプト群
**手順**:
1. DBに接続して現状のNULL率を調査:
   ```sql
   SELECT
     COUNT(*) as total,
     COUNT(CASE WHEN ad_metadata->>'latest_hit_score' IS NULL THEN 1 END) as no_score,
     COUNT(CASE WHEN ad_metadata->>'creative_quality' IS NULL THEN 1 END) as no_quality,
     COUNT(CASE WHEN category IS NULL THEN 1 END) as no_category,
     COUNT(CASE WHEN title IS NULL OR title = '' THEN 1 END) as no_title
   FROM ads;
   ```
2. NULL率が高いフィールドから順に修正スクリプトを実行
3. 結果をstatus.mdに記録

#### A-R2-2: A17 Metrics Delta Tracking (P0)
**目的**: 再生増加数・消化額増加の日次デルタ計算を実装
**ファイル**: `backend/app/tasks/metrics_tasks.py`
**やること**:
- `AdDailyMetrics` に前日比の増分計算ロジックを追加
- `view_count_increase` = 当日 - 前日の累計再生数
- `spend_increase` = 当日 - 前日の累計消化額
- ProRankingTable が `view_increase`, `spend_increase` を期待している

#### A-R2-3: A19 Full Data Pipeline (P1)
**目的**: 全176件に対して全分析スクリプトを一括実行
**手順**:
```bash
cd C:/Users/ishit/ads_library/backend
python -m scripts.classify_ads
python -m scripts.fix_titles
python -m scripts.fix_destination_urls
python -m scripts.collect_delivery_dates
python -m scripts.check_ad_survival
```
- 各スクリプトの成功/失敗件数を記録
- 失敗した広告のIDとエラー原因をstatus.mdに記載

#### A-R2-4: CI-001 DB接続リトライ統一 (P0)
**目的**: API/Worker/Lambdaで指数バックオフリトライを統一
**ファイル**: `backend/app/core/database.py`
**やること**:
- 接続失敗時に最大3回リトライ（1s → 2s → 4s）
- 3回失敗で構造化ログ出力
- Lambda/ECS/APIで同一ポリシー適用

#### A-R2-5: CI-007 ad_metadata スキーマバリデーション (P0)
**目的**: 必須キー欠落を検知・警告
**ファイル**: 新規 `backend/scripts/validate_metadata.py`
**やること**:
- 必須キーリスト定義: latest_hit_score, creative_quality, is_still_running, days_running
- 各広告をチェックし、欠落キーを警告ログ出力
- デイリーレポートとして出力（件数+欠落キー別のカウント）

### Phase 2 着手

#### A-R2-6: A37 Smart Alert Engine (P2)
**目的**: アラートルール定義 + 評価エンジン
**ファイル**:
- `backend/app/models/alert_rule.py` (新規)
- `backend/app/models/alert_history.py` (新規)
- `backend/app/services/alert_engine.py` (新規)
**やること**:
- AlertRule モデル: condition_type, threshold, target_field, notification_channel
- AlertHistory モデル: rule_id, triggered_at, ad_id, old_value, new_value
- 評価エンジン: 各ルールをDBの広告データと照合し、条件合致時に AlertHistory に記録

---

## Agent B: 次の指示 (Planner 3)

### 即座にやること (優先度順)

#### B-R2-1: B29 Dark Mode & Responsive (P1)
**ファイル**: `frontend/src/` 内の既存コンポーネント
**やること**:
- Tailwind `dark:` クラスを主要コンポーネントに追加
- ThemeToggle コンポーネントをヘッダーに追加
- `localStorage` でテーマ永続化
- 主要5画面（PRO DATABASE, ヒット広告分析, 検索, トレンド, 設定）のダークモード対応
- 対象コンポーネント: page.tsx, Sidebar.tsx, ProRankingView.tsx, HitAdAnalysisView.tsx, AdDetailModal.tsx

#### B-R2-2: B30 Heatmap & Analytics Visualization (P1)
**ファイル**: 新規 `frontend/src/components/dashboard/HeatmapView.tsx`
**やること**:
- 曜日×時間帯のヒートマップ（広告配信密度）
- SVGベースの描画（外部ライブラリ不要）
- カラースケール: 低=青, 中=黄, 高=赤
- ジャンルフィルター対応
- page.tsx に統合（analytics-dashboard ビュー内）

#### B-R2-3: B31 Pro Ranking Table UX (P1)
**ファイル**: `frontend/src/components/dashboard/ProRankingTable.tsx`
**やること**:
- カラムリサイズ（ドラッグでカラム幅変更）
- カラム表示/非表示トグル
- ソート状態のURL同期（戻る/進む対応）
- 固定ヘッダー（スクロール時にヘッダー固定）
- 選択行のハイライト強化

#### B-R2-4: B32 Genre Filter Dashboard (P1)
**ファイル**: `frontend/src/components/dashboard/ProRankingView.tsx`
**やること**:
- ジャンルサイドバーの折りたたみ/展開の改善
- ジャンル件数のリアルタイム更新
- ジャンルツリーの検索機能
- 選択中ジャンルのパンくず表示

### Phase 2 着手

#### B-R2-5: B41 Onboarding & Empty States (P2)
**ファイル**: 新規 `frontend/src/components/common/OnboardingWizard.tsx`
**やること**:
- 初回アクセス時のウェルカムモーダル（3ステップウィザード）
- 各画面の空データ状態（EmptyState）の統一デザイン
- デモモード: ダミーデータで全機能をプレビュー
- セットアップ進捗インジケータ（API接続/データ取得/分析完了）

#### B-R2-6: B42 Notification Center (P2)
**ファイル**: 新規 `frontend/src/components/common/NotificationCenter.tsx`
**やること**:
- ヘッダーに通知ベルアイコン + 未読バッジ
- クリックでドロップダウン通知一覧
- 通知種別: アラート/新着広告/分析完了/システム
- API: `GET /api/v1/rankings/notifications` (C39で実装予定)
- フォールバック: APIが無い場合はローカルストレージのトースト履歴を表示

---

## Agent C: 次の指示 (Planner 2)

### Phase 2 全力着手

#### C-R2-1: C38 AI Chat API (P0)
**ファイル**:
- `backend/app/api/endpoints/ai_chat.py` (新規)
- `backend/app/services/ai/chat_service.py` (新規)
- `backend/app/models/conversation.py` (新規)
**やること**:
1. **会話モデル**: Conversation(id, user_id, title, created_at, messages[])
2. **チャットエンドポイント**:
   - `POST /api/v1/ai-chat/message` — メッセージ送信、AI応答を返す
   - `GET /api/v1/ai-chat/conversations` — 会話履歴一覧
   - `GET /api/v1/ai-chat/conversations/{id}` — 特定会話の全メッセージ
   - `DELETE /api/v1/ai-chat/conversations/{id}` — 会話削除
3. **インテント分類**: メッセージからインテントを判定
   - `analyze_ad` → 特定広告の分析結果を返す
   - `compare_ads` → 複数広告の比較
   - `find_trends` → トレンド情報
   - `suggest_creative` → クリエイティブ提案
   - `general` → 汎用質問
4. **構造化レスポンス**: テキスト + 推奨アクション + 関連広告ID
5. **注意**: Claude API統合はユーザーがAPIキーを設定した場合のみ。未設定時はルールベースの応答

#### C-R2-2: C39 Alert Notification API (P0)
**ファイル**:
- `backend/app/api/endpoints/notifications.py` (新規 or rankings.py に追加)
- `backend/app/services/notification_service.py` (新規)
**やること**:
1. **通知CRUD**:
   - `GET /api/v1/rankings/notifications` — 通知一覧（ページング、未読/既読フィルタ）
   - `PUT /api/v1/rankings/notifications/{id}/read` — 既読マーク
   - `PUT /api/v1/rankings/notifications/read-all` — 全既読
   - `DELETE /api/v1/rankings/notifications/{id}` — 削除
2. **アラートルール管理**:
   - `POST /api/v1/rankings/alert-rules` — ルール作成
   - `GET /api/v1/rankings/alert-rules` — ルール一覧
   - `PUT /api/v1/rankings/alert-rules/{id}` — ルール更新
   - `DELETE /api/v1/rankings/alert-rules/{id}` — ルール削除
3. **システム通知生成**:
   - クロール完了時
   - 新しいHIT広告検出時
   - スコア急変時（score_delta > 20）
   - データ品質アラート

#### C-R2-3: C40 External Integration API (P1)
**ファイル**:
- `backend/app/api/endpoints/integrations.py` (新規)
- `backend/app/services/integrations/slack_notifier.py` (新規)
- `backend/app/services/integrations/webhook_sender.py` (新規)
**やること**:
1. **Slack通知**:
   - `POST /api/v1/integrations/slack/configure` — Webhook URL設定
   - `POST /api/v1/integrations/slack/test` — テスト送信
   - 通知テンプレート: HIT広告発見, 日次サマリー, アラート
2. **Webhook配信**:
   - `POST /api/v1/integrations/webhooks` — Webhook登録
   - `GET /api/v1/integrations/webhooks` — 一覧
   - `DELETE /api/v1/integrations/webhooks/{id}` — 削除
   - イベント: new_hit_ad, score_change, crawl_complete, alert_triggered
3. **CSV定期配信**:
   - `POST /api/v1/integrations/scheduled-export` — 定期エクスポート設定
   - 日次/週次でCSVを生成し、指定先に配信

### CI改善タスク (並行実行)

#### C-R2-4: CI-013 N+1クエリ解消 (P0)
**ファイル**: `backend/app/api/endpoints/rankings.py`
**やること**:
- 代表的なランキングAPIクエリのSQL発行回数を計測
- joinedload / selectinload で N+1 を解消
- 目標: SQL回数30%以上削減

#### C-R2-5: CI-014 ページング上限設定 (P0)
**ファイル**: `backend/app/api/endpoints/rankings.py`
**やること**:
- limit パラメータに上限を設定（max=100）
- 超過時は 400 Bad Request を返却
- 全一覧APIに統一適用

---

## Agent D: 次の指示 (Planner 1)

### Phase 1 残タスク (高優先度)

#### D-R2-1: D7 Scheduled Crawl Setup (P0)
**ファイル**:
- `terraform/eventbridge.tf` (既存)
- `backend/app/services/crawling/`
**やること**:
1. EventBridge の cron スケジュール確認・調整
2. ジャンル別ローテーションクロールの実装:
   - 月曜: 美容/コスメ
   - 火曜: 健康食品/サプリ
   - 水曜: ダイエット/フィットネス
   - 木曜: 育毛/スキンケア
   - 金曜: 全ジャンル（差分チェック）
3. クロール結果の件数ログ出力

#### D-R2-2: D8 Video Processing Pipeline (P0)
**ファイル**: `backend/app/tasks/media_tasks.py`
**やること**:
1. 動画ダウンロード → S3 アップロードのパイプライン確認
2. duration_seconds 自動取得（ffprobe or Playwright）
3. resolution_width/height 自動取得
4. file_size_bytes 記録
5. 動画フォーマット変換（必要なら MP4 に統一）

#### D-R2-3: D14 Media Precision — Aggressive Recovery (P1)
**ファイル**: `backend/scripts/extract_missing_videos.py`
**やること**:
1. video_url=NULL の広告を再スキャン
2. Playwright での抽出失敗時に代替手法:
   - Meta API からの直接URL取得
   - Facebook render_ad ページからの抽出
   - OG:video メタタグからの抽出
3. 回収率を記録（目標: video広告の90%以上でURL取得）

#### D-R2-4: D12 LP Crawler (P1)
**ファイル**: `backend/app/services/crawling/lp_crawler.py` (既存 or 新規)
**やること**:
1. destination_url に対して Playwright でスクリーンショット取得
2. LP のタイトル・メタディスクリプション・OG画像を抽出
3. 結果を ad_metadata に保存:
   - `lp_title`, `lp_description`, `lp_og_image`, `lp_screenshot_s3_key`
4. LP到達不能（404/timeout）の場合はステータスを記録

### Phase 2 着手

#### D-R2-5: D33 Intelligent Crawl Orchestration (P2)
**ファイル**:
- `backend/app/services/crawling/crawl_orchestrator.py` (新規)
- `backend/app/services/crawling/rate_limiter.py` (新規)
**やること**:
1. **優先度キュー**: HIT候補広告の再クロールを優先
2. **アダプティブレート制限**: 429レスポンス率に応じて自動減速
3. **サーキットブレーカー**: 連続失敗で一時停止、exponential backoff で再開
4. **プラットフォームヘルスチェック**: 各プラットフォームの到達性を定期チェック

#### D-R2-6: D34 Video Intelligence Pipeline (P2)
**ファイル**:
- `backend/app/services/video_pipeline.py` (新規)
- `backend/app/services/thumbnail_selector.py` (新規)
**やること**:
1. **キーフレーム抽出**: 動画から代表フレームを5枚抽出
2. **シーン検出**: PySceneDetect でシーン境界を特定
3. **自動サムネイル選択**: 最も視覚的に魅力的なフレームを自動選択
4. 結果を ad_metadata に保存: frame_count, scene_count, best_thumbnail_frame

---

## クロスプランナー連携ポイント (Round 2)

### C38 (AI Chat) → B43 (AI Chat UI)
- C が API を作成 → B が UI を作成
- レスポンス形式: `{ message: string, intent: string, actions: [], related_ad_ids: [] }`

### C39 (Notifications) → B42 (Notification Center)
- C が通知API を作成 → B が通知ベルUIを作成
- レスポンス形式: `{ notifications: [{ id, type, title, body, read, created_at }], unread_count }`

### A37 (Alert Engine) → C39 (Notification API)
- A がアラート評価エンジン → C がAPI化 → B がUI表示
- AlertRule/AlertHistory モデルは Agent A が作成、C がAPI経由で読み書き

### D7 (Scheduled Crawl) → A (Data Pipeline)
- D がクロール → A がクロール後の分析パイプライン実行

---

## 実行順序 (推奨)

```
並行実行可能:
  Agent A: A-R2-1 → A-R2-2 → A-R2-3 → A-R2-4 → A-R2-5
  Agent B: B-R2-1 → B-R2-2 → B-R2-3 → B-R2-4
  Agent C: C-R2-1 → C-R2-2 → C-R2-3 (+ C-R2-4, C-R2-5 並行)
  Agent D: D-R2-1 → D-R2-2 → D-R2-3 → D-R2-4

Phase 2 は Phase 1 残が片付いてから:
  Agent A: A-R2-6
  Agent B: B-R2-5 → B-R2-6
  Agent D: D-R2-5 → D-R2-6
```

---

## CI改善タスク消化 (Round 2 で消化すべき P0)

| ID | 担当 | タスク | ステータス |
|----|------|--------|-----------|
| CI-001 | A | DB接続リトライ統一 | → A-R2-4 |
| CI-007 | A | metadataバリデーション | → A-R2-5 |
| CI-013 | C | N+1解消 | → C-R2-4 |
| CI-014 | C | ページング上限 | → C-R2-5 |
| CI-019 | B | 状態UI統一 | B5で大部分完了、B-R2-1で残り |
| CI-025 | A | 秘密情報CIチェック | 次ラウンドに延期可 |
| CI-038 | D | クロール重複ガード | → D-R2-1 に含める |
| CI-052 | C | APIタイムアウト方針 | → C-R2-5 に含める |
| CI-053 | B | 二重送信防止 | → B-R2-3 に含める |
| CI-054 | D | 429アダプティブ抑制 | → D-R2-5 |
