# コスト最適化視点 — AWSコストを最小限に抑える

## 現在のコスト構成（推定: $20-45/月）

| リソース | タイプ | 月額 | 最適化余地 |
|----------|--------|------|-----------|
| RDS | db.t3.micro | ~$15 | ★★★ |
| NAT Instance | t4g.nano | ~$4 | ★☆☆ |
| Lambda (API) | per-request | ~$1-5 | ★★☆ |
| Lambda (trigger) | per-request | ~$0.5 | ☆☆☆ |
| ECS Fargate | per-task | ~$0-20 | ★★☆ |
| S3 | storage + transfer | ~$1-3 | ☆☆☆ |
| CloudFront | transfer | ~$0-2 | ☆☆☆ |
| API Gateway | per-request | ~$0-1 | ☆☆☆ |
| SQS | per-message | ~$0.01 | ☆☆☆ |
| CloudWatch | logs | ~$1-3 | ★☆☆ |

---

## 最大コスト: RDS ($15/月)

### 問題
- db.t3.micro は常時起動 → 使わない時間もコストが発生
- 58件しかデータがないので、RDS はオーバースペック

### 最適化オプション

**オプション A: RDS を止める（開発時のみ起動）**
```bash
# 停止（最大7日間）
aws rds stop-db-instance --db-instance-identifier vaap-production-db
# → $0/月（停止中はストレージ費のみ ~$1-2）

# 起動
aws rds start-db-instance --db-instance-identifier vaap-production-db
# → 起動に3-5分かかる
```
**注意**: 7日後に自動起動される。Lambda 用の定期停止を設定。

**オプション B: Aurora Serverless v2**
- 使った分だけ課金（0 ACU = $0）
- 最小 0.5 ACU ≈ $40/月 → 58件には高い
- 500件以上のアクティブ利用なら検討

**オプション C: SQLite + S3（極限コスト削減）**
- SQLite ファイルを S3 に保存
- Lambda で読み込み
- 58件なら十分
- $0.50/月
- **デメリット**: 書き込み競合、マイグレーション困難

### 推奨
- 開発フェーズ: **RDS を使わない時に停止**（手動 or Lambda スケジューラー）
- 本番フェーズ: db.t3.micro のまま維持

---

## 2番目のコスト: ECS Fargate

### 問題
- タスク実行時のみ課金だが、1タスクあたり $0.01-0.05
- 大量のメディア抽出 → コストが増加

### 最適化
- バッチ処理: 1タスクで複数広告を処理（1広告1タスクではなく）
- メモリ最適化: 4096MB → 2048MB で十分なら半額
- CPU最適化: 1024 vCPU で十分なら

### ECS タスク定義の確認
```bash
# 現在の設定
aws ecs describe-task-definition --task-definition vaap-production-worker \
  --query 'taskDefinition.{cpu:cpu,memory:memory}' --output table
```

---

## 3番目のコスト: Lambda

### 問題
- コールドスタートが頻繁 → 実行時間が長い → コスト増
- 重い依存パッケージ → メモリ使用量大 → コスト増

### 最適化
- **requirements 分離** (VIEW_DEPENDENCY_AUDIT.md 参照)
  - Lambda用: ~50MB → コールドスタート 1-2秒
  - Worker用: ~4GB → ECS のみ
- **Lambda メモリ設定**: 現在 256MB? → 128MB で試す
  - メモリ半分 = コスト半分
  - ただしコールドスタートが遅くなる可能性

### Lambda Power Tuning
```bash
# AWS Lambda Power Tuning ツールで最適メモリを見つける
# https://github.com/alexcasalboni/aws-lambda-power-tuning
```

---

## 無料枠の活用

### AWS Free Tier (12ヶ月)
- Lambda: 月100万リクエスト + 400,000 GB-秒 → ほぼ無料
- S3: 5GB ストレージ + 2万GET → ほぼ無料
- CloudFront: 1TB/月 → ほぼ無料
- SQS: 100万メッセージ → ほぼ無料
- CloudWatch: 5GBログ → ほぼ無料

### Always Free
- Lambda: 月100万リクエスト（永久無料）
- DynamoDB: 25GB + 25 WCU/RCU（永久無料） → 将来の検討対象

---

## コスト削減ロードマップ

### 即座に ($15 → $5)
1. RDS を使わない時に停止（週末/夜間）
2. CloudWatch ログの保持期間を短縮（90日→30日）

### 1ヶ月以内 ($5 → $3)
3. Lambda requirements 分離 → メモリ削減
4. ECS タスクのメモリ最適化

### 3ヶ月以内
5. CloudFront キャッシュ最適化 → Lambda 呼び出し削減
6. RDS Reserved Instance（1年契約で40%オフ）

---

## コストアラート設定

```bash
# AWS Budgets でアラート設定
aws budgets create-budget \
  --account-id 271669411511 \
  --budget '{
    "BudgetName": "vaap-monthly",
    "BudgetLimit": {"Amount": "50", "Unit": "USD"},
    "TimeUnit": "MONTHLY",
    "BudgetType": "COST"
  }' \
  --notifications-with-subscribers '[{
    "Notification": {
      "NotificationType": "ACTUAL",
      "ComparisonOperator": "GREATER_THAN",
      "Threshold": 80,
      "ThresholdType": "PERCENTAGE"
    },
    "Subscribers": [{
      "SubscriptionType": "EMAIL",
      "Address": "your@email.com"
    }]
  }]'
```

---

## 月額コスト目標

| フェーズ | 広告数 | 目標コスト |
|---------|--------|-----------|
| 開発中 | 58 | < $10/月 |
| v0.1 | 200 | < $25/月 |
| v1.0 | 2000 | < $75/月 |
| v2.0 | 5000 | < $150/月 |
