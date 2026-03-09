param(
  [string]$Tag = "",
  [string]$Region = "ap-northeast-1",
  [string]$AccountId = "271669411511"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Tag)) {
  $Tag = "a100-worker-" + (Get-Date -Format "yyyyMMdd-HHmmss")
}

$repo = "$AccountId.dkr.ecr.$Region.amazonaws.com/vaap-production-worker"
$image = "${repo}:$Tag"

Write-Host "Check Docker daemon..."
docker info --format "{{.ServerVersion}}" | Out-Null

Write-Host "Login ECR..."
aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "$AccountId.dkr.ecr.$Region.amazonaws.com"

Write-Host "Build worker image: $image"
docker build --platform linux/amd64 -f docker/Dockerfile.worker -t $image -t "$repo`:latest" .

Write-Host "Verify worker image can run mlops_monitoring..."
docker run --rm --entrypoint python $image -m app.tasks.runner mlops_monitoring "{}"

Write-Host "Push images..."
docker push $image
docker push "$repo`:latest"

Write-Host "Update ECS task definition image..."
$taskDef = aws ecs describe-task-definition --task-definition vaap-production-worker --query 'taskDefinition' --output json
$newTaskDef = $taskDef | ConvertFrom-Json
$newTaskDef.containerDefinitions[0].image = $image
$newTaskDef.PSObject.Properties.Remove("taskDefinitionArn")
$newTaskDef.PSObject.Properties.Remove("revision")
$newTaskDef.PSObject.Properties.Remove("status")
$newTaskDef.PSObject.Properties.Remove("requiresAttributes")
$newTaskDef.PSObject.Properties.Remove("compatibilities")
$newTaskDef.PSObject.Properties.Remove("registeredAt")
$newTaskDef.PSObject.Properties.Remove("registeredBy")

$tmp = New-TemporaryFile
$newTaskDef | ConvertTo-Json -Depth 100 | Set-Content -Path $tmp -Encoding utf8NoBOM
$registered = aws ecs register-task-definition --cli-input-json "file://$tmp"
Remove-Item $tmp -Force

$registeredTaskDef = $registered | ConvertFrom-Json
$taskDefinitionArn = $registeredTaskDef.taskDefinition.taskDefinitionArn
if ([string]::IsNullOrWhiteSpace($taskDefinitionArn)) {
  throw "Failed to resolve registered task definition ARN"
}

Write-Host "Verify registered task definition points at new worker image..."
$registeredImage = aws ecs describe-task-definition `
  --task-definition $taskDefinitionArn `
  --query "taskDefinition.containerDefinitions[?name=='vaap-production-worker'].image | [0]" `
  --output text

if ($registeredImage -ne $image) {
  throw "Worker task definition image mismatch: $registeredImage"
}

Write-Host "Done. New worker image tag: $Tag"
