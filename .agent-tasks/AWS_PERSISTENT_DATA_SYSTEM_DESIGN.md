# AWS 永続データ蓄積システム設計（ads_library）

最終更新: 2026-03-02

## 目的
- 広告データを日次で途切れなく収集し、長期保存し、異常時に即検知できる状態を作る。
- AWSクレジットを活用しつつ、運用破綻を防ぐガードレールを先に入れる。

## 現在の基盤（既存）
- 収集実行: EventBridge Scheduler -> SQS -> Lambda/ECS
- 処理:
  - heavy: `SQS heavy` -> `Lambda trigger` -> `ECS RunTask`
  - light: `SQS light` -> `Lambda light`
- 保存:
  - 構造化データ: RDS PostgreSQL
  - メディア: S3 (+ CloudFront 配信)

## 今回追加した永続運用要素

## 1. データ保持強化
- RDS
  - バックアップ保持を変数化（デフォルト30日）
  - `max_allocated_storage` を変数化（デフォルト200GB）
  - `copy_tags_to_snapshot = true`
  - Performance Insights を有効化可能（デフォルトtrue）
- S3
  - ライフサイクルを長期保持向けに拡張
  - `STANDARD_IA` -> `GLACIER_IR` へ段階遷移
  - 非現行バージョンの遷移/期限を設定
- SQS
  - 本キュー retention: 4日（デフォルト）
  - DLQ retention: 14日（デフォルト）

## 2. 監視・通知
- SNSトピック（運用アラート）を追加
- CloudWatch Alarm 追加:
  - heavy/light DLQの滞留
  - heavy/light queue の oldest age
  - RDS CPU高騰
  - RDS 空き容量低下
  - 各LambdaのError発生

## 3. コストガードレール
- AWS Budget（月次コスト）をTerraform化
- `alert_email` 設定時のみ有効化
- しきい値は変数化（デフォルト80%）

## 4. 運用パラメータ（terraform.tfvars 推奨）
```hcl
alert_email                    = "ops@example.com"
enable_budget_guardrails       = true
monthly_budget_limit_usd       = 800
budget_alert_threshold_percent = 80

rds_backup_retention_days      = 30
rds_max_allocated_storage      = 400
rds_performance_insights_enabled = true

s3_transition_to_ia_days       = 30
s3_transition_to_glacier_days  = 180
s3_noncurrent_transition_days  = 30
s3_noncurrent_expiration_days  = 365

sqs_message_retention_seconds  = 345600
sqs_dlq_retention_seconds      = 1209600
```

## 5. デプロイ手順
1. `cd terraform`
2. `terraform fmt`
3. `terraform init`
4. `terraform plan -out tfplan`
5. `terraform apply tfplan`
6. SNSメール承認リンクをクリック

## 6. 受け入れ基準
- 日次収集が止まっても、DLQ通知で15分以内に検知できる
- RDS容量不足/高負荷を事前検知できる
- 月次予算超過前に通知される
- 1年分以上のメディア履歴を低コスト階層で保持できる

