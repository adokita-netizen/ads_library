# Incident Runbook

最終更新: 2026-03-01

## 目的
本番障害発生時の初動対応手順を標準化する。

---

## 1. API が 500 を返す

### 症状
- フロントエンドで「エラーが発生しました」表示
- curl で 500 Internal Server Error

### 初動
```bash
# 1. ECS タスクログを確認
aws logs tail /ecs/vaap-backend --since 10m --format short

# 2. RDS 接続確認
psql -h vaap-production-db.xxx.rds.amazonaws.com -U vaap_user -d vaap -c "SELECT 1;"

# 3. Lambda ログ確認（SQS トリガー経由のエラー）
aws logs tail /aws/lambda/vaap-dispatcher --since 10m
```

### 原因切り分け

| 原因 | 兆候 | 対応 |
|------|------|------|
| DB 接続プール枯渇 | "QueuePool limit reached" | ECS タスク再起動 |
| DB スロークエリ | "timeout" in query | `pg_stat_activity` で確認、kill |
| メモリ不足 | OOMKilled in ECS | タスク定義のメモリ増量 |
| 依存サービス障害 | 外部 API timeout | CircuitBreaker 確認 |
| コードバグ | Traceback in logs | ログからスタックトレース特定 |

### DB 接続プール枯渇時
```bash
# アクティブ接続数を確認
psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# アイドル接続を kill
psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND query_start < NOW() - INTERVAL '5 minutes';"

# ECS タスク再起動
aws ecs update-service --cluster vaap --service vaap-backend --force-new-deployment
```

---

## 2. フロントエンドが白画面

### 症状
- ページが真っ白
- ブラウザコンソールに JS エラー

### 初動
```bash
# 1. ビルド確認
cd frontend && npx next build --no-lint

# 2. CloudFront キャッシュ無効化
aws cloudfront create-invalidation --distribution-id ERPIU1B8ZZ5ZA --paths "/*"

# 3. S3 デプロイ確認
aws s3 ls s3://vaap-frontend-bucket/ --recursive | tail -20
```

### 原因切り分け

| 原因 | 兆候 | 対応 |
|------|------|------|
| ビルドエラー | next build 失敗 | TS エラー修正 |
| CDN キャッシュ | 古いバンドル配信 | CloudFront 無効化 |
| API 障害 | Network タブで 500 | バックエンド調査 |
| JS ランタイムエラー | コンソールエラー | Error Boundary ログ確認 |

---

## 3. クロールが失敗する

### 症状
- クロール実行後に0件取得
- SQS DLQ にメッセージ滞留

### 初動
```bash
# 1. SQS DLQ メッセージ数確認
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-northeast-1.amazonaws.com/xxx/vaap-dlq \
  --attribute-names ApproximateNumberOfMessages

# 2. Meta API トークン有効性確認
curl -s "https://graph.facebook.com/v19.0/me?access_token=TOKEN" | python -m json.tool

# 3. Playwright 動作確認
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); b.close(); print('OK')"
```

### 原因切り分け

| 原因 | 兆候 | 対応 |
|------|------|------|
| Meta API トークン期限切れ | 401 Unauthorized | トークン再発行 |
| 429 レートリミット | "Rate limit exceeded" | 待機後リトライ |
| Playwright ブラウザ起動失敗 | "browser closed" | Docker イメージ再ビルド |
| ネットワーク障害 | connect timeout | NAT Instance 確認 |
| SQS 処理失敗 | DLQ に大量メッセージ | メッセージ内容確認、再送 |

### Meta API トークン更新手順
```
1. https://developers.facebook.com/ にログイン
2. Ad Library API のアクセストークンを取得
3. DB の api_keys テーブルを更新:
   UPDATE api_keys SET value = 'NEW_TOKEN', updated_at = NOW() WHERE key = 'meta_access_token';
4. ECS タスクを再起動（キャッシュクリア）
```

---

## 4. ヒットスコアが全て 0 / NULL

### 症状
- ProRankingTable で全広告のスコアが 0
- `hit_score` カラムが NULL

### 初動
```bash
# 1. NULL スコア件数確認
psql -c "SELECT count(*) FROM ad WHERE hit_score IS NULL OR hit_score = 0;"

# 2. 最終スコア計算日時確認
psql -c "SELECT MAX(updated_at) FROM product_ranking;"

# 3. 再計算実行
cd backend && python scripts/recompute_hit_scores.py
```

### 原因切り分け

| 原因 | 兆候 | 対応 |
|------|------|------|
| 再計算未実行 | product_ranking が空 | recompute_hit_scores.py 実行 |
| メトリクスデータ不足 | ad_daily_metrics が空 | A: collect_real_metrics.py 実行 |
| スコア計算バグ | 全て同じスコア | ranking_service.py のロジック確認 |
| DB マイグレーション漏れ | カラム不存在 | alembic upgrade head |

---

## 5. メディアファイルが表示されない

### 症状
- サムネイルがプレースホルダー表示
- 動画が再生されない

### 初動
```bash
# 1. S3 バケット確認
aws s3 ls s3://vaap-media-bucket/ --summarize | tail -5

# 2. プロキシ API 確認
curl -I http://localhost:8000/api/v1/media/thumbnail/AD_ID

# 3. 直接 URL 確認
psql -c "SELECT image_url, thumbnail_url, image_s3_key FROM ad WHERE id = AD_ID;"
```

### 原因切り分け

| 原因 | 兆候 | 対応 |
|------|------|------|
| S3 アクセス権限 | 403 Forbidden | IAM ポリシー確認 |
| S3 キー未設定 | image_s3_key = NULL | メディア抽出ジョブ再実行 |
| 外部 URL 期限切れ | 403/404 on fbcdn URL | re-crawl + re-extract |
| プロキシ API エラー | 500 on /media/ | エンドポイントのログ確認 |
| CORS エラー | ブラウザコンソールに CORS | S3 CORS 設定確認 |

---

## 6. Lambda/SQS 処理が滞留

### 症状
- SQS キューにメッセージが溜まる
- Lambda のインフレイトが上昇

### 初動
```bash
# 1. SQS メッセージ数
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-northeast-1.amazonaws.com/xxx/vaap-crawl-queue \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible

# 2. Lambda エラー率
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=vaap-dispatcher \
  --start-time $(date -u -d '-1 hour' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum

# 3. Lambda 同時実行数
aws lambda get-function-concurrency --function-name vaap-dispatcher
```

### 対応
```bash
# DLQ メッセージを確認してから再送
aws sqs receive-message --queue-url DLQ_URL --max-number-of-messages 5

# Lambda の同時実行数を調整
aws lambda put-function-concurrency --function-name vaap-dispatcher --reserved-concurrent-executions 10
```

---

## 7. NAT Instance 障害

### 症状
- ECS タスクから外部 API にアクセスできない
- Lambda から外部サイトに接続できない

### 初動
```bash
# 1. NAT Instance 状態確認
aws ec2 describe-instances --instance-ids i-02e8893b4193a114e \
  --query "Reservations[].Instances[].State.Name"

# 2. ルートテーブル確認
aws ec2 describe-route-tables --filters Name=association.subnet-id,Values=PRIVATE_SUBNET_ID

# 3. NAT Instance 再起動
aws ec2 reboot-instances --instance-ids i-02e8893b4193a114e
```

---

## エスカレーション基準

| レベル | 基準 | 対応時間 |
|--------|------|---------|
| P0 (Critical) | 全機能停止、データ損失リスク | 即時 |
| P1 (High) | 主要機能停止（クロール不能、スコア計算不能） | 1時間以内 |
| P2 (Medium) | 一部機能低下（画像表示不可、エクスポート失敗） | 4時間以内 |
| P3 (Low) | UIバグ、パフォーマンス劣化 | 次スプリント |

---

## 連絡先

| 担当 | エージェント | 専門領域 |
|------|------------|---------|
| データ基盤 | Agent A | DB, バッチ, メトリクス |
| フロントエンド | Agent B | UI, UX, Next.js |
| API/スコア | Agent C | API, ランキング, 検索 |
| メディア/クロール | Agent D | Playwright, S3, メディア |
