# AWS 本番デプロイガイド

VAAP を AWS にデプロイする手順です。

## 構成図

```
[ブラウザ] → [CloudFront] → [API Gateway] → [Lambda (FastAPI)]
                                                  ├→ [RDS PostgreSQL 15]
                                                  ├→ [SQS (タスクキュー)]
                                                  └→ [S3 (ストレージ)]
                                              [ECS Fargate (重い処理)]
```

---

## 前提条件

- AWS アカウント（本番用）
- AWS CLI v2 インストール済み & `aws configure` 設定済み
- Terraform >= 1.5
- Docker（ECR プッシュ用）
- GitHub リポジトリへのアクセス

---

## 1. Terraform ステートバックエンド準備

初回のみ、Terraform の状態管理用に S3 バケットと DynamoDB テーブルを作成します。

```bash
# S3 バケット（ステート保存）
aws s3api create-bucket \
  --bucket vaap-terraform-state \
  --region ap-northeast-1 \
  --create-bucket-configuration LocationConstraint=ap-northeast-1

aws s3api put-bucket-versioning \
  --bucket vaap-terraform-state \
  --versioning-configuration Status=Enabled

# DynamoDB テーブル（ステートロック）
aws dynamodb create-table \
  --table-name vaap-terraform-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-northeast-1
```

---

## 2. Terraform でインフラ構築

```bash
cd terraform

# 初期化
terraform init

# 変数ファイルを作成（必要に応じて編集）
cat > terraform.tfvars <<EOF
db_password = "your-secure-db-password"
EOF

# プランを確認
terraform plan

# インフラ構築（確認後に適用）
terraform apply
```

主なリソース:
- **Lambda x3**: API ハンドラー、軽量タスク、重量タスク
- **API Gateway**: REST API エンドポイント
- **RDS PostgreSQL 15**: `ap-northeast-1` メインDB
- **S3**: 動画/画像ストレージ
- **CloudFront**: CDN 配信
- **ECS Fargate**: ML 推論等の重い処理
- **SQS**: タスクキュー（軽量/重量）

---

## 3. GitHub Actions Secrets 設定

リポジトリの **Settings → Secrets and variables → Actions** で以下を設定:

| Secret 名 | 値 |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM ユーザーのアクセスキー |
| `AWS_SECRET_ACCESS_KEY` | IAM ユーザーのシークレットキー |
| `TF_VAR_DB_PASSWORD` | RDS データベースパスワード |

---

## 4. 初回デプロイ

### 4.1 ECR にイメージプッシュ

```bash
# ECR ログイン
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com

# ビルド & プッシュ
docker build -t vaap-api ./backend
docker tag vaap-api:latest <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/vaap-api:latest
docker push <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/vaap-api:latest
```

### 4.2 DB マイグレーション

```bash
# Lambda 経由または踏み台サーバーから実行
cd backend
DATABASE_URL="postgresql://vaap:<password>@<rds-endpoint>:5432/vaap_db" \
  alembic upgrade head
```

### 4.3 動作確認

```bash
# ヘルスチェック
curl https://<api-gateway-url>/health

# Swagger UI
# https://<api-gateway-url>/api/docs
```

---

## 5. CI/CD（自動デプロイ）

`main` ブランチへのプッシュで GitHub Actions が自動実行:

1. `.github/workflows/deploy.yml` — Lambda / ECS デプロイ
2. `.github/workflows/terraform.yml` — インフラ変更の plan & apply

---

## 注意事項

- **Lambda コールドスタート**: 初回リクエスト時に数秒の遅延が発生する場合があります
- **RDS 接続**: Lambda から VPC 内の RDS に接続するため、セキュリティグループの設定を確認してください
- **コスト管理**: RDS インスタンスサイズ、Lambda の同時実行数、CloudFront の帯域を監視してください
