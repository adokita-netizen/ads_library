# ==================== SQS Queues ====================

# Heavy tasks queue → ECS RunTask
resource "aws_sqs_queue" "heavy_tasks" {
  name                       = "${local.name_prefix}-heavy-tasks"
  visibility_timeout_seconds = 900 # 15 minutes (ECS task duration)
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 10

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.heavy_tasks_dlq.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${local.name_prefix}-heavy-tasks" }
}

resource "aws_sqs_queue" "heavy_tasks_dlq" {
  name                      = "${local.name_prefix}-heavy-tasks-dlq"
  message_retention_seconds = 604800 # 7 days

  tags = { Name = "${local.name_prefix}-heavy-tasks-dlq" }
}

# Light tasks queue → Lambda
resource "aws_sqs_queue" "light_tasks" {
  name                       = "${local.name_prefix}-light-tasks"
  visibility_timeout_seconds = 360 # 6 minutes (Lambda timeout + margin)
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 10

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.light_tasks_dlq.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${local.name_prefix}-light-tasks" }
}

resource "aws_sqs_queue" "light_tasks_dlq" {
  name                      = "${local.name_prefix}-light-tasks-dlq"
  message_retention_seconds = 604800 # 7 days

  tags = { Name = "${local.name_prefix}-light-tasks-dlq" }
}
