# A32: デプロイスクリプト作成 & E2Eテスト

## 目的
Playwright 対応 Worker イメージのビルド → ECR push → ECS 更新 → Lambda 更新 → E2E テストを一括実行するスクリプト。

## 対象ファイル
- `backend/scripts/deploy_worker.sh` (新規作成)
- `backend/scripts/test_media_pipeline.py` (新規作成)

## タスク

### 1. deploy_worker.sh
```bash
#!/bin/bash
set -euo pipefail

REGION="ap-northeast-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/vaap-worker"
IMAGE_TAG="${1:-latest}"

echo "=== Building Worker Image ==="
docker build -f docker/Dockerfile.worker -t vaap-worker:${IMAGE_TAG} .

echo "=== ECR Login ==="
aws ecr get-login-password --region ${REGION} | \
  docker login --username AWS --password-stdin ${ECR_REPO}

echo "=== Pushing to ECR ==="
docker tag vaap-worker:${IMAGE_TAG} ${ECR_REPO}:${IMAGE_TAG}
docker push ${ECR_REPO}:${IMAGE_TAG}

echo "=== Updating ECS Task Definition ==="
# 新リビジョン登録（最新イメージを使用）
aws ecs describe-task-definition \
  --task-definition vaap-worker \
  --query 'taskDefinition.{containerDefinitions:containerDefinitions,family:family,taskRoleArn:taskRoleArn,executionRoleArn:executionRoleArn,networkMode:networkMode,cpu:cpu,memory:memory,requiresCompatibilities:requiresCompatibilities,runtimePlatform:runtimePlatform}' \
  --output json > /tmp/task-def.json

aws ecs register-task-definition --cli-input-json file:///tmp/task-def.json

echo "=== Deploy Complete ==="
echo "Image: ${ECR_REPO}:${IMAGE_TAG}"
```

### 2. test_media_pipeline.py — E2Eパイプラインテスト
```python
"""E2E test: Lambda → SQS → ECS → Playwright → DB update."""
import json
import time
import boto3
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

def test_pipeline(ad_id: int = None, limit: int = 1):
    """
    1. DB から pending 広告を取得（or 指定 ad_id）
    2. Lambda invoke (action=extract_media)
    3. 60秒待機
    4. DB で media_extraction_status を確認
    """
    session = SyncSessionLocal()

    # Step 1: テスト対象の広告を特定
    if ad_id:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
    else:
        ad = session.query(Ad).filter(
            Ad.media_extraction_status == "pending",
            Ad.snapshot_url.isnot(None),
        ).first()

    if not ad:
        print("No pending ads found")
        return

    print(f"Testing with ad_id={ad.id}, snapshot_url={ad.snapshot_url[:80]}...")

    # Step 2: Lambda invoke
    client = boto3.client("lambda", region_name="ap-northeast-1")
    response = client.invoke(
        FunctionName="vaap-production-api",
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "extract_media",
            "limit": limit,
        }),
    )
    result = json.loads(response["Payload"].read())
    print(f"Lambda response: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # Step 3: 待機 & ポーリング
    for i in range(12):  # 最大2分
        time.sleep(10)
        session.expire_all()
        ad = session.query(Ad).filter(Ad.id == ad.id).first()
        status = ad.media_extraction_status
        print(f"  [{i*10}s] status={status}")
        if status in ("completed", "enriched", "failed"):
            break

    # Step 4: 結果表示
    print(f"\n=== Result ===")
    print(f"  status: {ad.media_extraction_status}")
    print(f"  image_url: {ad.image_url}")
    print(f"  video_url: {ad.video_url}")
    print(f"  creative_type: {ad.creative_type}")
    print(f"  image_s3_key: {ad.image_s3_key}")

    session.close()

if __name__ == "__main__":
    import sys
    ad_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    test_pipeline(ad_id=ad_id)
```

## 確認方法
```bash
# デプロイ
chmod +x backend/scripts/deploy_worker.sh
bash backend/scripts/deploy_worker.sh latest

# E2Eテスト
cd backend
python -m scripts.test_media_pipeline
```

## 制約
- `backend/scripts/` にのみファイル作成
- 本番DBに対してのテストなので、limit=1 で慎重に実行
