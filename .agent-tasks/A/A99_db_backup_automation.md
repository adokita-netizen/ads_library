# A99: DBバックアップ自動化

## 優先度: 🅱️ B（重要）

## 問題
- RDS PostgreSQLのバックアップが明示的に設定されていない
- データロスのリスクがある

## 対象ファイル
- `terraform/rds.tf`

## タスク

### Task 1: RDS自動バックアップ設定
```hcl
resource "aws_db_instance" "vaap_db" {
  # 既存設定に追加
  backup_retention_period = 7           # 7日間保持
  backup_window           = "03:00-04:00"  # JST 12:00-13:00
  copy_tags_to_snapshot   = true
  delete_automated_backups_on_deletion = false
}
```

### Task 2: 手動スナップショット取得スクリプト
```bash
aws rds create-db-snapshot \
  --db-instance-identifier vaap-production-db \
  --db-snapshot-identifier vaap-manual-$(date +%Y%m%d)
```

### Task 3: 復元手順書
- スナップショットからの復元手順
- ポイントインタイムリカバリの手順
- 復元後の接続設定確認チェックリスト

## 完了条件
- [x] RDS自動バックアップが7日間保持で設定されている
- [x] Terraformで管理されている
- [x] 復元手順書が作成されている
- [x] テスト復元が1回実行されている（`rds:vaap-production-db-2026-03-04-17-05` から `vaap-production-db-restore-a99` を復元し `available` 確認）

## 制約
- バックアップウィンドウは低トラフィック時間帯に設定
- ストレージコスト増を最小限にする

## Status
Completed (2026-03-05, infra設定/runbook/実環境テスト復元1回を完了)
