#!/bin/bash
set -euo pipefail

# Deploy Worker image to ECR and update ECS task definition.
#
# Usage:
#   bash scripts/deploy_worker.sh [IMAGE_TAG]
#   IMAGE_TAG defaults to "latest"

REGION="ap-northeast-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/vaap-worker"
IMAGE_TAG="${1:-latest}"

echo "=== Building Worker Image ==="
docker build -f docker/Dockerfile.worker -t vaap-worker:"${IMAGE_TAG}" .

echo "=== ECR Login ==="
aws ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${ECR_REPO}"

echo "=== Pushing to ECR ==="
docker tag vaap-worker:"${IMAGE_TAG}" "${ECR_REPO}":"${IMAGE_TAG}"
docker push "${ECR_REPO}":"${IMAGE_TAG}"

echo "=== Updating ECS Task Definition ==="
aws ecs describe-task-definition \
  --task-definition vaap-worker \
  --query 'taskDefinition.{containerDefinitions:containerDefinitions,family:family,taskRoleArn:taskRoleArn,executionRoleArn:executionRoleArn,networkMode:networkMode,cpu:cpu,memory:memory,requiresCompatibilities:requiresCompatibilities,runtimePlatform:runtimePlatform}' \
  --output json > /tmp/task-def.json

aws ecs register-task-definition --cli-input-json file:///tmp/task-def.json

echo "=== Deploy Complete ==="
echo "Image: ${ECR_REPO}:${IMAGE_TAG}"
