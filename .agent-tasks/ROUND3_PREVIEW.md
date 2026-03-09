# Round 3 Preview — Phase 2 完成 + Phase 3 準備
# ★ Round 2 完了後に着手 ★

## Round 3 の目標
1. Phase 2 の全タスクを完了（アラート、AIチャット、オンボーディング等）
2. Phase 3 の設計開始（ML/AI本格導入、マルチテナント、有料化準備）
3. 200件→1000件へのデータスケール

---

## Agent A: Round 3 タスク

### A-R3-1: Data Quality Dashboard API (新規)
**概要**: データ品質の時系列推移を API で提供
- 日次の NULL率、充填率、鮮度スコアをテーブルに保存
- `GET /api/v1/data-quality/history` で時系列取得
- ファイル: `backend/scripts/data_quality_snapshot.py`, `backend/app/models/data_quality.py`

### A-R3-2: Automated Data Pipeline Orchestrator (新規)
**概要**: classify → fix_titles → collect_dates → check_survival → validate を一括自動実行
- Celery Beat / cron で日次実行
- 実行結果をSlack通知 (C-R2-3 の integrations API 利用)
- ファイル: `backend/app/tasks/data_pipeline_tasks.py`

### A-R3-3: ML Feature Store (Phase 3 準備)
**概要**: 機械学習向けの特徴量テーブルを設計
- ad_features テーブル: 広告ID → 特徴量ベクトル
- テキスト特徴: TF-IDF, キーワード出現, 文字数
- メディア特徴: 動画長, 解像度, シーン数, 顔有無
- メトリクス特徴: スコア推移, デルタ推移, 配信日数
- ファイル: `backend/app/models/ad_features.py`, `backend/scripts/compute_features.py`

### A-R3-4: Backup & Recovery Automation
**概要**: 日次バックアップ + 復元テスト自動化
- RDS スナップショット + S3 バックアップ
- 月次復元訓練スクリプト
- ファイル: `backend/scripts/backup_restore.py`

---

## Agent B: Round 3 タスク

### B-R3-1: AI Chat Interface (B43)
**概要**: C-R2-1 の AI Chat API と連携するチャットUI
- チャットパネル（右サイドパネル or フルスクリーン）
- メッセージ入力 + AI応答表示
- インテント別のリッチ表示（テーブル、チャート、広告カード）
- クイックアクション提案ボタン
- 会話履歴の保存/読込
- ファイル: `frontend/src/components/common/AIChatPanel.tsx`

### B-R3-2: Dashboard Customization (B44)
**概要**: ユーザーがダッシュボードのレイアウトをカスタマイズ
- ドラッグ&ドロップでウィジェット配置
- ウィジェット種類: KPIカード, テーブル, チャート, ヒートマップ
- レイアウトの保存/読込 (localStorage + API)
- プリセットレイアウト: 「アナリスト」「クリエイター」「マネージャー」
- ファイル: `frontend/src/components/dashboard/CustomDashboard.tsx`

### B-R3-3: Advanced Data Visualization
**概要**: Recharts/D3.js を使った高度なチャート
- 散布図: スコア vs 配信日数 (バブルサイズ=消化額)
- サンキーダイアグラム: ジャンル → フックタイプ → HIT/非HIT
- レーダーチャート: 広告の5シグナル比較
- 時系列: 週次トレンドの折れ線グラフ（ズーム対応）
- ファイル: `frontend/src/components/charts/`

### B-R3-4: PWA & Offline Support
**概要**: Progressive Web App 対応
- Service Worker でオフラインキャッシュ
- プッシュ通知 (Web Push API)
- ホーム画面追加
- ファイル: `frontend/public/sw.js`, `frontend/src/app/manifest.json`

---

## Agent C: Round 3 タスク

### C-R3-1: Claude API Integration (AI Chat 本格化)
**概要**: C-R2-1 のルールベース応答を Claude API で強化
- システムプロンプト: VAAPの広告データをコンテキストに含める
- RAG: 質問に関連する広告データをDBから取得し、プロンプトに注入
- ストリーミング応答 (SSE)
- 使用量制限: トークン数/日、リクエスト数/時間
- ファイル: `backend/app/services/ai/claude_client.py`

### C-R3-2: GraphQL API (オプション)
**概要**: REST に加えて GraphQL エンドポイントを提供
- Strawberry or Graphene で実装
- フロントエンドが必要なフィールドだけ取得 → レスポンスサイズ削減
- ファイル: `backend/app/api/graphql/`

### C-R3-3: API Versioning
**概要**: v2 API の設計
- /api/v2/ プレフィックス
- Breaking changes を v2 で導入、v1 は非推奨化
- OpenAPI spec の自動生成
- ファイル: `backend/app/api/v2/`

### C-R3-4: Advanced Scoring Model
**概要**: ML ベースのヒットスコアモデル
- 現在のルールベーススコアを教師データとして XGBoost で学習
- 特徴量: A-R3-3 の Feature Store から取得
- モデルのバージョン管理 + A/Bテスト
- ファイル: `backend/app/services/prediction/ml_scorer.py`

---

## Agent D: Round 3 タスク

### D-R3-1: Multi-Platform Crawl Expansion (D35)
**概要**: YouTube/TikTok/X のクローラーを本番品質に
- YouTube: Data API v3 + Playwright フォールバック
- TikTok: 広告ライブラリAPI + Playwright
- X (Twitter): 広告透明性センター
- 各プラットフォームの正規化 (共通スキーマ)
- ファイル: `backend/app/services/crawling/youtube_crawler.py`, `tiktok_crawler.py`, `x_crawler.py`

### D-R3-2: AWS Rekognition Integration (D11)
**概要**: 画像/動画の自動分析
- ラベル検出: 商品、人物、テキスト
- 顔分析: 表情、年齢推定
- テキスト検出: 画像内のテキスト抽出
- コンテンツモデレーション
- ファイル: `backend/app/services/cv/rekognition_service.py`

### D-R3-3: AWS Transcribe + Comprehend (D13)
**概要**: 動画の音声分析
- Transcribe: 自動文字起こし
- Comprehend: 感情分析、キーワード抽出、言語検出
- 結果を ad_metadata に保存
- ファイル: `backend/app/services/audio/transcribe_service.py`

### D-R3-4: CDN & Media Optimization
**概要**: メディアファイルの配信最適化
- CloudFront でメディアを配信
- 画像のリサイズ/WebP変換
- 動画のトランスコーディング (HLS)
- ファイル: `terraform/cloudfront_media.tf`

---

## Phase 3 アーキテクチャ変更

### マルチテナント準備
```
現在: シングルテナント（1社向け）
Phase 3: マルチテナント（SaaS化）

変更点:
- 全テーブルに tenant_id カラム追加
- 認証: JWT + テナント識別
- 課金: Stripe 統合
- データ分離: RLS (Row Level Security)
```

### ML パイプライン
```
Feature Store (A-R3-3)
  → ML Training (C-R3-4)
    → Model Registry (S3)
      → Inference API (C-R3-4)
        → Scoring (既存フローに統合)
```

### スケーリング
```
現在: 176件の広告
Phase 3: 10,000+ 件

変更点:
- PostgreSQL → Aurora (自動スケーリング)
- Redis クラスター
- ECS Auto Scaling
- API レスポンスキャッシュ (CloudFront or Redis)
```

---

## Timeline (目安)

```
Round 2 (現在): Day 1-5
  → Phase 1 残消化 + Phase 2 着手

Round 3: Day 6-15
  → Phase 2 完了 + Phase 3 設計

Round 4: Day 16-30
  → Phase 3 実装開始 (ML, マルチテナント, クローラー拡張)

Round 5: Day 31-60
  → Phase 3 完了 + 本番リリース準備
```
