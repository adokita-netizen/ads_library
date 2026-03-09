# バックアップ・災害復旧視点 — データを守り、障害から復旧する

## なぜ重要か

VAAP のデータは再取得が困難:
- Meta APIのレートリミット（200 calls/hour）で大量再クロールは数日かかる
- 配信停止した広告はAd Libraryから消える → 二度と取得できない
- 動画URLは数週間で無効化される → S3にキャッシュしていないと消失

---

## 現状のバックアップ体制

### RDS PostgreSQL
```
現在の設定（推定）:
  自動バックアップ: 有効（デフォルト7日間保持）
  スナップショット: 手動未設定
  Multi-AZ: 無効（コスト削減）
  リードレプリカ: なし
```

### S3
```
  バージョニング: 未確認
  ライフサイクルポリシー: 未設定
  クロスリージョンレプリケーション: なし
```

### Lambda / ECS
```
  コードはGitHub管理
  環境変数: terraform で管理
  復旧: terraform apply で再構築可能
```

---

## バックアップ設計

### Tier 1: データベース（最重要）

#### 自動バックアップ
```hcl
# terraform/rds.tf
resource "aws_db_instance" "vaap" {
  # ...
  backup_retention_period = 14        # 14日間保持
  backup_window          = "03:00-04:00"  # JST 12:00-13:00
  copy_tags_to_snapshot  = true
  delete_automated_backups_on_termination = false
}
```

#### 手動スナップショット（リリース前）
```bash
# 大きな変更前に手動スナップショット
aws rds create-db-snapshot \
  --db-instance-identifier vaap-production-db \
  --db-snapshot-identifier vaap-pre-release-$(date +%Y%m%d)
```

#### 論理バックアップ（pg_dump）
```bash
# 毎日のダンプ → S3
pg_dump -h vaap-production-db.cxwsa6mgcgg6.ap-northeast-1.rds.amazonaws.com \
  -U vaap_user -d vaap \
  --format=custom \
  --file=vaap-$(date +%Y%m%d).dump

aws s3 cp vaap-$(date +%Y%m%d).dump \
  s3://vaap-backups/db/vaap-$(date +%Y%m%d).dump
```

### Tier 2: メディアファイル

```
S3 バケットのバージョニング有効化:
  aws s3api put-bucket-versioning \
    --bucket vaap-production-media \
    --versioning-configuration Status=Enabled

ライフサイクルポリシー:
  - 90日後に Glacier に移行
  - 365日後に Glacier Deep Archive
  - 削除マーカー後30日で完全削除
```

### Tier 3: インフラ設定

```
terraform state:
  → S3 バックエンド + DynamoDB ロック（既存）
  → state ファイルのバージョニング有効

GitHub:
  → コードの全履歴
  → ブランチ保護ルール
```

---

## 災害シナリオと復旧手順

### シナリオ 1: DBデータ破損
**原因**: バグのあるマイグレーション、誤ったUPDATE文
**RTO**: 30分 / **RPO**: 最大24時間

```
復旧手順:
1. 問題の特定
   → PostgreSQL ログ確認
   → 影響範囲の特定

2a. ポイントインタイムリカバリ（推奨）
   aws rds restore-db-instance-to-point-in-time \
     --source-db-instance-identifier vaap-production-db \
     --target-db-instance-identifier vaap-recovery-db \
     --restore-time "2025-03-01T12:00:00Z"

2b. スナップショットから復旧
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier vaap-recovery-db \
     --db-snapshot-identifier vaap-pre-release-20250301

3. 新DBのエンドポイントをterraformに反映
4. Lambda/ECS の環境変数を更新
5. データ整合性確認
```

### シナリオ 2: Lambda 障害
**原因**: デプロイミス、依存パッケージ破損
**RTO**: 5分 / **RPO**: 0

```
復旧手順:
1. 直前バージョンにロールバック
   aws lambda update-function-code \
     --function-name vaap-production-api \
     --s3-bucket vaap-deploy \
     --s3-key previous-lambda.zip

2. or terraform で前のコミットからデプロイ
   git checkout HEAD~1 -- terraform/lambda.tf
   terraform apply
```

### シナリオ 3: ECS Worker 停止
**原因**: OOM、Playwright クラッシュ、ECR イメージ不整合
**RTO**: 10分 / **RPO**: 0（SQSにメッセージ残存）

```
復旧手順:
1. ECS タスク状態確認
   aws ecs describe-tasks --cluster vaap-production --tasks ...

2. CloudWatch ログ確認
   aws logs get-log-events --log-group-name /ecs/vaap-worker

3. タスク強制再起動
   aws ecs update-service \
     --cluster vaap-production \
     --service vaap-production-worker \
     --force-new-deployment

4. SQS DLQ 確認 → 失敗メッセージを再投入
```

### シナリオ 4: Meta APIトークン失効
**原因**: 60日の有効期限切れ
**RTO**: 即時（手動対応に依存）/ **RPO**: N/A

```
復旧手順:
1. Graph API Explorer で新トークン取得
2. 長期トークンに交換
3. VAAP設定APIで更新
4. クロールテスト実行
```

### シナリオ 5: NAT インスタンス障害
**原因**: t4g.nano の障害、iptables 設定消失
**RTO**: 30分 / **RPO**: 0

```
復旧手順:
1. インスタンス状態確認
   aws ec2 describe-instances --instance-ids i-02e8893b4193a114e

2. iptables 再設定
   sudo iptables -t nat -A POSTROUTING -o ens5 -j MASQUERADE
   sudo iptables -A FORWARD -i ens5 -o ens5 -m state \
     --state RELATED,ESTABLISHED -j ACCEPT
   sudo iptables -A FORWARD -i ens5 -o ens5 -j ACCEPT

3. ECS Worker の通信確認
```

---

## 定期バックアップスケジュール

| 対象 | 頻度 | 保持期間 | 方法 |
|------|------|---------|------|
| RDS 自動バックアップ | 毎日 | 14日 | AWS自動 |
| RDS 手動スナップショット | リリース前 | 90日 | 手動 |
| pg_dump 論理バックアップ | 週1回 | 30日 | Lambda/CronJob |
| S3 メディア | リアルタイム | バージョニング | AWS自動 |
| terraform state | 変更ごと | バージョニング | S3 |
| GitHub コード | pushごと | 無期限 | Git |

---

## 復旧テスト

### 四半期ごとに実施すべきテスト
```
1. RDS スナップショットからの復旧テスト
   → 復旧用DBインスタンスを起動
   → データ整合性確認
   → 削除

2. pg_dump からのリストアテスト
   → ローカル or テスト環境で pg_restore
   → レコード数確認

3. terraform destroy + apply テスト
   → テスト環境でインフラ再構築
   → 全サービスの動作確認

4. Lambda ロールバックテスト
   → 意図的に壊したコードをデプロイ
   → 前バージョンにロールバック
   → 応答確認
```

---

## 監視とアラート

### バックアップ失敗の検知
```bash
# RDS バックアップイベントの監視
aws rds describe-events \
  --source-type db-instance \
  --source-identifier vaap-production-db \
  --duration 1440

# CloudWatch アラーム
# - RDS FreeStorageSpace < 5GB → WARNING
# - RDS FreeStorageSpace < 1GB → CRITICAL
# - ECS RunningTaskCount == 0 → CRITICAL
# - SQS ApproximateAgeOfOldestMessage > 3600 → WARNING
```
