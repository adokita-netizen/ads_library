# 運用監視視点 — 何を見れば壊れたことが分かるか

## 監視ダッシュボード構成

### Layer 1: ユーザー体験 (最も重要)

| 監視項目 | 確認方法 | アラート条件 |
|---------|---------|-------------|
| サイトが表示されるか | CloudFront + S3 | 5xx が 1% 超 |
| APIが応答するか | `/api/health` | 3回連続失敗 |
| データが表示されるか | `/api/v1/rankings/pro-ranking` | 空レスポンス |
| 画像が表示されるか | `/api/v1/media/thumbnail/*` | 403/404 が 50% 超 |

### Layer 2: バックエンド

| 監視項目 | CloudWatch メトリクス | アラート条件 |
|---------|---------------------|-------------|
| Lambda エラー率 | Lambda Errors | > 5% |
| Lambda 実行時間 | Lambda Duration | p99 > 10s |
| Lambda スロットリング | Lambda Throttles | > 0 |
| API Gateway 5xx | ApiGateway 5XXError | > 1% |
| API Gateway レイテンシ | ApiGateway Latency | p99 > 5s |

### Layer 3: データベース

| 監視項目 | CloudWatch メトリクス | アラート条件 |
|---------|---------------------|-------------|
| RDS CPU | CPUUtilization | > 80% |
| RDS 接続数 | DatabaseConnections | > 80% of max |
| RDS 空きストレージ | FreeStorageSpace | < 1GB |
| RDS レイテンシ | ReadLatency / WriteLatency | > 20ms |

### Layer 4: ワーカー

| 監視項目 | 確認方法 | アラート条件 |
|---------|---------|-------------|
| SQS メッセージ滞留 | ApproximateNumberOfMessages | > 100 |
| SQS DLQ メッセージ | DLQ メッセージ数 | > 0 |
| ECS タスク失敗 | ECS RunTask 失敗 | > 0 |
| ECS メモリ使用率 | MemoryUtilization | > 90% |

### Layer 5: インフラ

| 監視項目 | 確認方法 | アラート条件 |
|---------|---------|-------------|
| NAT Instance | EC2 StatusCheck | Failed |
| S3 エラー | S3 4xxErrors / 5xxErrors | > 1% |
| CloudFront エラー | CloudFront ErrorRate | > 1% |

---

## ログ確認コマンド

### Lambda APIログ
```bash
# 最新ログ確認
aws logs tail /aws/lambda/vaap-production-api --since 1h --format short

# エラーのみ
aws logs filter-log-events \
  --log-group-name /aws/lambda/vaap-production-api \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s000)

# 遅いリクエスト (> 1000ms)
aws logs filter-log-events \
  --log-group-name /aws/lambda/vaap-production-api \
  --filter-pattern "slow_request"
```

### ECS ワーカーログ
```bash
# 最新ログ
aws logs tail /ecs/vaap-production-worker --since 1h --format short

# メディア抽出結果
aws logs filter-log-events \
  --log-group-name /ecs/vaap-production-worker \
  --filter-pattern "extract_media"
```

### SQS キュー状態
```bash
# Heavy tasks キュー
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-northeast-1.amazonaws.com/271669411511/vaap-production-heavy-tasks \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

# DLQ 確認
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-northeast-1.amazonaws.com/271669411511/vaap-production-heavy-tasks-dlq \
  --attribute-names ApproximateNumberOfMessages
```

### RDS 接続テスト
```bash
# Lambda 経由
curl https://d3qlbagx7gq5sp.cloudfront.net/api/health

# 直接 (踏み台経由)
psql "host=vaap-production-db.cxwsa6mgcgg6.ap-northeast-1.rds.amazonaws.com \
  port=5432 dbname=vaap user=vaap_admin" \
  -c "SELECT COUNT(*) FROM ads;"
```

---

## 障害対応フローチャート

```
「サイトが見えない」
  ├── CloudFront 502/503?
  │     └── S3 が空 → frontend を再デプロイ
  ├── API が死んでる?
  │     ├── Lambda が起動しない → CloudWatch Logs 確認
  │     ├── RDS 接続エラー → セキュリティグループ確認
  │     └── Lambda タイムアウト → メモリ増加 or コールドスタート
  └── フロントのJSエラー → DevTools Console 確認

「データが表示されない」
  ├── API は200を返す?
  │     ├── NO → Lambda ログ確認
  │     └── YES → レスポンスにデータが入ってるか?
  │           ├── NO → DB にデータがあるか?
  │           │     ├── NO → クロールが必要
  │           │     └── YES → SQL クエリに問題
  │           └── YES → フロントの描画ロジックに問題
  └── 特定のジャンルだけ空?
        └── classify_ads が未実行 → Planner 1 に連絡

「画像が壊れる」
  ├── /media/thumbnail/{id} を直接叩く
  │     ├── 200 → フロントの img タグの問題
  │     ├── 403 → 外部URLの権限問題 → S3 キャッシュに切替
  │     ├── 404 → thumbnail_url が NULL → メディア抽出が必要
  │     └── 500 → media.py のバグ → Planner 2 に連絡
  └── 全画像が壊れる? → CloudFront キャッシュ invalidation

「クロールが動かない」
  ├── SQS にメッセージが入る?
  │     ├── NO → dispatcher.py のバグ
  │     └── YES → ECS タスクが起動する?
  │           ├── NO → Lambda trigger のログ確認
  │           └── YES → タスクが失敗する?
  │                 ├── Playwright エラー → Chromium 設定確認
  │                 ├── メモリ不足 → ECS タスク定義のメモリ増加
  │                 └── ネットワークエラー → NAT Instance 確認
  └── Meta API エラー → トークン有効期限確認
```

---

## 日次ヘルスチェック（手動）

```bash
#!/bin/bash
echo "=== VAAP Daily Health Check ==="
echo "Date: $(date)"

echo ""
echo "--- Frontend ---"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" https://d3qlbagx7gq5sp.cloudfront.net)
echo "CloudFront: $HTTP"

echo ""
echo "--- API ---"
HEALTH=$(curl -s https://d3qlbagx7gq5sp.cloudfront.net/api/health)
echo "Health: $HEALTH"

echo ""
echo "--- Data ---"
SUMMARY=$(curl -s https://d3qlbagx7gq5sp.cloudfront.net/api/v1/rankings/dashboard-summary 2>/dev/null)
echo "Dashboard: $SUMMARY" | head -5

echo ""
echo "--- NAT Instance ---"
aws ec2 describe-instance-status --instance-ids i-02e8893b4193a114e \
  --query 'InstanceStatuses[0].InstanceState.Name' --output text 2>/dev/null || echo "Check failed"

echo ""
echo "--- SQS DLQ ---"
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-northeast-1.amazonaws.com/271669411511/vaap-production-heavy-tasks-dlq \
  --attribute-names ApproximateNumberOfMessages \
  --query 'Attributes.ApproximateNumberOfMessages' --output text 2>/dev/null || echo "Check failed"

echo ""
echo "=== Done ==="
```
