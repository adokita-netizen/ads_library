# A98: 本番監視ダッシュボード構築

## 優先度: 🅱️ B（重要）

## 問題
- CloudWatch/Prometheus設定は存在するが、可視化ダッシュボードが未構築
- 障害発生時に状況把握が困難

## 対象ファイル
- `terraform/monitoring.tf`
- `terraform/cloudwatch.tf`（あれば）
- `backend/app/core/config.py`（メトリクス設定）

## タスク

### Task 1: CloudWatchダッシュボード作成
- Lambda: 呼び出し回数、エラー率、実行時間、コールドスタート数
- ECS: CPU/メモリ使用率、タスク数、ヘルスチェック
- RDS: 接続数、CPU、ストレージ残量、クエリ遅延
- API Gateway: 4xx/5xx率、レイテンシ、リクエスト数
- SQS: キュー長、処理遅延、DLQメッセージ数

### Task 2: アラートルール設定
- Lambda エラー率 > 5% → 通知
- RDS CPU > 80% → 通知
- SQS DLQ > 0 → 通知
- ECSタスク異常停止 → 通知

### Task 3: Terraform定義
- ダッシュボード/アラートをTerraformで管理
- `terraform/monitoring.tf` に追記

## 完了条件
- [x] CloudWatchダッシュボードで主要メトリクスが確認できる（`vaap-production-ops-overview` を `aws cloudwatch get-dashboard` で確認）
- [x] 異常時にアラートが発報される（`vaap-production-api-gateway-5xx-high` を ALARM→OK 手動遷移で確認）
- [x] Terraformで管理されている（手動設定なし）

## 制約
- 追加コストを最小限に抑える（CloudWatch基本料金内で収める）

## Status
Completed (2026-03-05, 実環境ダッシュボード存在確認 + アラーム遷移確認まで完了)
