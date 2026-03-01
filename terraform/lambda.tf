# ==================== Lambda Functions ====================

# API Lambda (FastAPI via Mangum)
resource "aws_lambda_function" "api" {
  function_name = "${local.name_prefix}-api"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:latest"
  memory_size   = var.lambda_memory_size
  timeout       = var.lambda_timeout

  image_config {
    command = ["lambda_handler.handler"]
  }

  vpc_config {
    subnet_ids         = [aws_subnet.private_1.id, aws_subnet.private_2.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      APP_ENV             = var.environment
      DB_SECRET_ARN       = aws_secretsmanager_secret.db_password.arn
      DB_USERNAME         = var.db_username
      DB_ENDPOINT         = aws_db_instance.main.endpoint
      DB_NAME             = var.db_name
      CORS_ORIGINS        = join(",", var.cors_allowed_origins)
      STORAGE_BACKEND     = "s3"
      AWS_S3_BUCKET       = aws_s3_bucket.storage.id
      TASK_BACKEND        = "sqs"
      SQS_HEAVY_QUEUE_URL = aws_sqs_queue.heavy_tasks.url
      SQS_LIGHT_QUEUE_URL = aws_sqs_queue.light_tasks.url
      META_ACCESS_TOKEN   = var.meta_access_token
    }
  }

  tags = { Name = "${local.name_prefix}-api" }
}

# SQS → ECS RunTask Trigger Lambda
resource "aws_lambda_function" "sqs_ecs_trigger" {
  function_name = "${local.name_prefix}-sqs-ecs-trigger"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:latest"
  memory_size   = 256
  timeout       = 60

  image_config {
    command = ["sqs_ecs_trigger.handler"]
  }

  # NOT in VPC — needs to call ECS API directly
  environment {
    variables = {
      ECS_CLUSTER         = aws_ecs_cluster.main.name
      ECS_TASK_DEFINITION = "${local.name_prefix}-worker"
      ECS_CONTAINER_NAME  = "${local.name_prefix}-worker"
      ECS_SUBNETS         = join(",", [aws_subnet.public_1.id, aws_subnet.public_2.id])
      ECS_SECURITY_GROUPS = aws_security_group.ecs.id
    }
  }

  tags = { Name = "${local.name_prefix}-sqs-ecs-trigger" }
}

# Light Tasks Lambda (SQS + EventBridge)
resource "aws_lambda_function" "light_tasks" {
  function_name = "${local.name_prefix}-light-tasks"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:latest"
  memory_size   = var.lambda_light_memory_size
  timeout       = var.lambda_light_timeout

  image_config {
    command = ["light_task_handler.handler"]
  }

  vpc_config {
    subnet_ids         = [aws_subnet.private_1.id, aws_subnet.private_2.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      APP_ENV             = var.environment
      DB_SECRET_ARN       = aws_secretsmanager_secret.db_password.arn
      DB_USERNAME         = var.db_username
      DB_ENDPOINT         = aws_db_instance.main.endpoint
      DB_NAME             = var.db_name
      STORAGE_BACKEND     = "s3"
      AWS_S3_BUCKET       = aws_s3_bucket.storage.id
      TASK_BACKEND        = "sqs"
      SQS_HEAVY_QUEUE_URL = aws_sqs_queue.heavy_tasks.url
      SQS_LIGHT_QUEUE_URL = aws_sqs_queue.light_tasks.url
    }
  }

  tags = { Name = "${local.name_prefix}-light-tasks" }
}

# ==================== SQS Event Source Mappings ====================

resource "aws_lambda_event_source_mapping" "heavy_tasks" {
  event_source_arn        = aws_sqs_queue.heavy_tasks.arn
  function_name           = aws_lambda_function.sqs_ecs_trigger.arn
  batch_size              = 1
  enabled                 = true
  function_response_types = ["ReportBatchItemFailures"]
}

resource "aws_lambda_event_source_mapping" "light_tasks" {
  event_source_arn = aws_sqs_queue.light_tasks.arn
  function_name    = aws_lambda_function.light_tasks.arn
  batch_size       = 1
  enabled          = true
}

# ==================== CloudWatch Log Groups ====================

resource "aws_cloudwatch_log_group" "lambda_api" {
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "lambda_trigger" {
  name              = "/aws/lambda/${local.name_prefix}-sqs-ecs-trigger"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "lambda_light" {
  name              = "/aws/lambda/${local.name_prefix}-light-tasks"
  retention_in_days = 14
}
