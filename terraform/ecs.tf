# ==================== ECS Cluster ====================

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Name = "${local.name_prefix}-cluster" }
}

# ==================== ECS Task Definition (RunTask only, no service) ====================

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name_prefix}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "${local.name_prefix}-worker"
      image     = "${aws_ecr_repository.worker.repository_url}:latest"
      essential = true

      environment = [
        { name = "APP_ENV", value = var.environment },
        { name = "DATABASE_URL_SYNC", value = "postgresql://${var.db_username}:${var.db_password}@${aws_db_instance.main.endpoint}/${var.db_name}" },
        { name = "DATABASE_URL", value = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.main.endpoint}/${var.db_name}" },
        { name = "STORAGE_BACKEND", value = "s3" },
        { name = "AWS_S3_BUCKET", value = aws_s3_bucket.storage.id },
        { name = "TASK_BACKEND", value = "sqs" },
        { name = "SQS_HEAVY_QUEUE_URL", value = aws_sqs_queue.heavy_tasks.url },
        { name = "SQS_LIGHT_QUEUE_URL", value = aws_sqs_queue.light_tasks.url },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])

  tags = { Name = "${local.name_prefix}-worker-task" }
}

resource "aws_cloudwatch_log_group" "ecs_worker" {
  name              = "/ecs/${local.name_prefix}-worker"
  retention_in_days = 14
}
