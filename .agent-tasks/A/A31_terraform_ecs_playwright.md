# A31: Terraform ECS タスク定義更新（Playwright対応）

## 目的
Playwright + Chromium を積んだ Worker コンテナに合わせて ECS タスク定義を更新。
メモリ・CPU・環境変数・ヘルスチェック等を調整。

## 対象ファイル
- `terraform/ecs.tf`

## タスク

### 1. メモリ・CPU 増加
Playwright + Chromium はメモリを多く消費する。現在 8GB / 2vCPU だが確認が必要。

```hcl
# 現在の設定を確認し、必要なら調整
resource "aws_ecs_task_definition" "worker" {
  cpu    = "2048"   # 2 vCPU (維持 or 4096に増加)
  memory = "8192"   # 8GB (Playwright + CV + Whisper で必要)
}
```

### 2. 環境変数追加
```hcl
environment = [
  # 既存変数に追加
  {
    name  = "PLAYWRIGHT_BROWSERS_PATH"
    value = "/opt/playwright-browsers"
  },
  {
    name  = "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"
    value = ""  # デフォルトのまま（BROWSERS_PATHから自動検出）
  },
]
```

### 3. /dev/shm サイズ拡大
Chromium は共有メモリを使用。デフォルト 64MB では不足する場合がある。

```hcl
container_definitions = jsonencode([{
  # 既存設定に追加
  linuxParameters = {
    sharedMemorySize = 2048  # 2GB
  }
}])
```

### 4. タスク実行タイムアウト
Playwright ページ読み込み + メディアDL で時間がかかる場合がある。

```hcl
# sqs.tf の visibility timeout も確認
# Heavy queue: 900s (15分) — Playwright なら十分
```

## 確認方法
```bash
cd terraform/
terraform plan  # 差分確認
terraform apply  # 適用（ユーザー承認後）
```

## 制約
- `terraform/ecs.tf` のみ編集
- 既存の環境変数・シークレットを削除しない
- `terraform plan` で意図しない破壊的変更がないことを確認
