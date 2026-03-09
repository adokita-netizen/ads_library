# デプロイ・インフラ視点 — 本番環境を動かすためのチェックリスト

## 本番構成

```
[ユーザー]
    ↓ HTTPS
[CloudFront] ERPIU1B8ZZ5ZA
    ├── /          → S3 (Next.js静的エクスポート)
    └── /api/      → API Gateway → Lambda (vaap-production-api)
                                      ↓
                                  [RDS PostgreSQL]
                                  vaap-production-db.cxwsa6mgcgg6.ap-northeast-1.rds.amazonaws.com
                                      ↓
                    [SQS heavy]  →  Lambda trigger  →  ECS Fargate (vaap-production-worker)
                    [SQS light]  →  Lambda (light-tasks)
```

---

## チェックリスト

### 1. フロントエンドデプロイ

- [ ] `cd frontend && NEXT_OUTPUT=export npx next build`
- [ ] `out/` ディレクトリが生成される
- [ ] S3バケットに `aws s3 sync out/ s3://BUCKET_NAME --delete`
- [ ] CloudFront invalidation: `aws cloudfront create-invalidation --distribution-id ERPIU1B8ZZ5ZA --paths "/*"`
- [ ] `https://d3qlbagx7gq5sp.cloudfront.net` でページが表示される
- [ ] API接続バナーが「接続OK」になる

### 2. バックエンドデプロイ (Lambda)

- [ ] `cd backend && zip -r lambda.zip . -x "*.pyc" "__pycache__/*" ".git/*"`
- [ ] Lambda関数 `vaap-production-api` を更新
- [ ] `/api/health` が200を返す
- [ ] `/api/v1/rankings/products` がデータを返す
- [ ] 環境変数確認:
  - `DATABASE_URL` → RDS接続文字列
  - `AWS_REGION` → ap-northeast-1
  - `SQS_HEAVY_QUEUE_URL` → vaap-production-heavy-tasks
  - `SQS_LIGHT_QUEUE_URL` → vaap-production-light-tasks
  - `S3_BUCKET` → メディア保存用
  - `PLAYWRIGHT_BROWSERS_PATH` → (Lambda不要、Worker用)

### 3. ワーカーデプロイ (ECS Fargate)

- [ ] `docker/Dockerfile.worker` をビルド
- [ ] ECRにプッシュ: `271669411511.dkr.ecr.ap-northeast-1.amazonaws.com/vaap-production-worker`
- [ ] ECSタスク定義を更新
- [ ] **Playwright動作確認**: ECSタスクを手動実行して media extraction が成功するか
- [ ] 環境変数確認:
  - `DATABASE_URL` → RDS接続文字列
  - `PLAYWRIGHT_BROWSERS_PATH` → /opt/playwright-browsers
  - `S3_BUCKET` → メディア保存用

### 4. データベース

- [ ] RDS PostgreSQL が起動中
- [ ] `vaap-production-db.cxwsa6mgcgg6.ap-northeast-1.rds.amazonaws.com` に接続可能
- [ ] マイグレーション: `alembic upgrade head`
- [ ] 58件の広告が存在: `SELECT COUNT(*) FROM ads;`
- [ ] ProductRanking テーブルにデータがある

### 5. SQSキュー

- [ ] `vaap-production-heavy-tasks` キューが存在
- [ ] `vaap-production-light-tasks` キューが存在
- [ ] DLQ（デッドレターキュー）が設定済み
- [ ] Lambda トリガーが設定済み（SQS → ECS trigger Lambda）

### 6. NAT Instance

- [ ] `i-02e8893b4193a114e` (t4g.nano) が起動中
- [ ] iptables手動設定が有効
- [ ] ECS Fargate タスクが外部インターネットにアクセス可能

### 7. APIキー・トークン

- [ ] **Meta API Token**: ❌ 無効 → ユーザーが Meta Business から再取得必要
- [ ] **OpenAI API Key**: 設定の `/settings` で確認
- [ ] **Anthropic API Key**: 設定の `/settings` で確認
- [ ] DB内の `api_keys` テーブルに保存されているか確認

### 8. GitHub Actions (CI/CD)

- [ ] `.github/workflows/deploy.yml` が最新
- [ ] ECR push が成功する
- [ ] Lambda デプロイが成功する
- [ ] S3 sync が成功する

---

## 本番障害時のデバッグ手順

### フロントが表示されない
1. CloudFront → S3 の接続確認
2. S3バケットの `index.html` が存在するか
3. CloudFront の OAI/OAC 設定

### APIが500を返す
1. Lambda ログ: CloudWatch `/aws/lambda/vaap-production-api`
2. RDS接続: セキュリティグループの確認
3. Lambda メモリ/タイムアウト設定

### メディア抽出が動かない
1. SQSキューにメッセージが入っているか
2. ECS trigger Lambda のログ
3. ECS Fargate タスクのログ: CloudWatch `/ecs/vaap-production-worker`
4. NAT Instance が起動しているか

### データが更新されない
1. Meta API Token の有効性
2. クローラーのエラーログ
3. SQS DLQ にメッセージが溜まっていないか

---

## Round 2 追加チェック項目

### 新テーブル（マイグレーション必須）
- [ ] `conversations` テーブル (C-R2-1: AI Chat)
- [ ] `alert_rules` テーブル (A-R2-6 / C-R2-2)
- [ ] `alert_history` テーブル (A-R2-6 / C-R2-2)
- [ ] `alembic upgrade head` で3テーブル追加

### 新APIルーター登録
- [ ] `main.py` に `/api/v1/ai-chat` ルーター追加
- [ ] `main.py` に `/api/v1/integrations` ルーター追加

### 新環境変数
- [ ] `SLACK_WEBHOOK_URL` — Slack通知用（オプション）

### Dockerfile.worker 追加パッケージ
- [ ] `ffprobe` / `ffmpeg` インストール（動画メタデータ抽出用）

### フロントエンド追加確認
- [ ] ダークモード: `darkMode: 'class'` が tailwind.config.js に存在
- [ ] 通知センター: NotificationCenter コンポーネントがヘッダーに配置
- [ ] オンボーディング: localStorage `vaap-onboarded` フラグ
- [ ] First Load JS: 160kB 以下

### Round 2 API動作確認
```bash
# AI Chat
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/ai-chat/conversations"

# Notifications
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/rankings/notifications"

# Alert Rules
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/rankings/alert-rules"

# Integrations
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/integrations/webhooks"
```

---

## コスト注意

| リソース | 月額目安 | 注意 |
|----------|----------|------|
| RDS (db.t3.micro) | ~$15 | 停止忘れ注意 |
| NAT Instance (t4g.nano) | ~$4 | 常時起動 |
| Lambda | ~$1-5 | リクエスト数依存 |
| ECS Fargate | ~$0-20 | タスク実行時のみ |
| S3 + CloudFront | ~$1-3 | 静的ファイル |
| **合計** | **~$20-45/月** | |
