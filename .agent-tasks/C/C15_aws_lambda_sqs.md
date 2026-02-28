# Agent C Task: AWS SQS Queue Integration for Async Processing

## Goal
Use AWS SQS for async task processing. Crawls, analysis, media downloads should be queued and processed reliably.

## What to do

### 1. SQS task dispatcher
Update or create `backend/app/tasks/dispatcher.py`:
- Detect if SQS is configured (AWS credentials + queue URL in env)
- If SQS available: dispatch tasks to SQS queue
- If not: fallback to inline processing
- Task types: crawl, analyze, download_media, score

### 2. SQS worker
`backend/scripts/sqs_worker.py`
- Poll SQS queue for messages
- Process each task:
  - "crawl": run crawl logic
  - "analyze": run creative analysis
  - "download_media": download and cache media
  - "score": recompute hit scores
- Delete message after successful processing
- Dead letter queue for failed tasks

### 3. Task status tracking
Add to rankings.py:
`GET /rankings/tasks` - list recent async tasks with status
`GET /rankings/tasks/{task_id}` - get specific task status + result

### 4. Webhook/callback
- After async task completes, optionally call a webhook URL
- Configurable in backend/.env: WEBHOOK_URL=https://...
- Useful for Slack notifications or frontend auto-refresh

### 5. Config
Add to backend/.env:
```
AWS_SQS_QUEUE_URL=https://sqs.ap-northeast-1.amazonaws.com/xxx/vaap-tasks
AWS_SQS_DLQ_URL=https://sqs.ap-northeast-1.amazonaws.com/xxx/vaap-tasks-dlq
WEBHOOK_URL=
```

## Constraints
- Only modify rankings.py for API endpoints
- Can create/modify files in app/tasks/ and scripts/
- boto3, English-only, graceful fallback if SQS not configured
