# ==================== EventBridge Scheduler ====================

data "aws_caller_identity" "current" {}

locals {
  api_lambda_arn  = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.name_prefix}-api"
  api_lambda_name = "${local.name_prefix}-api"
}

# Daily crawl: 03:00 JST = 18:00 UTC → SQS heavy queue
resource "aws_scheduler_schedule" "daily_crawl" {
  name       = "${local.name_prefix}-daily-crawl"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 18 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_sqs_queue.heavy_tasks.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    input = jsonencode({
      task = "crawl_ads"
      kwargs = {
        query              = ""
        platforms          = ["youtube", "tiktok", "facebook", "instagram", "yahoo", "x_twitter", "line", "pinterest", "smartnews", "google_ads", "gunosy"]
        category           = null
        limit_per_platform = 50
        auto_analyze       = true
      }
    })
  }
}

# Daily rankings: 05:00 JST = 20:00 UTC → Light tasks Lambda
resource "aws_scheduler_schedule" "daily_rankings" {
  name       = "${local.name_prefix}-daily-rankings"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 20 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_lambda_function.light_tasks.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    input = jsonencode({
      task   = "compute_rankings"
      kwargs = {}
    })
  }
}

# Daily alerts: 06:00 JST = 21:00 UTC → Light tasks Lambda
resource "aws_scheduler_schedule" "daily_alerts" {
  name       = "${local.name_prefix}-daily-alerts"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 21 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_lambda_function.light_tasks.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    input = jsonencode({
      task   = "detect_alerts"
      kwargs = {}
    })
  }
}

# Daily ops health check: 07:00 JST = 22:00 UTC -> Light tasks Lambda
resource "aws_scheduler_schedule" "daily_ops_health_check" {
  name       = "${local.name_prefix}-daily-ops-health-check"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 22 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_lambda_function.light_tasks.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    input = jsonencode({
      task   = "daily_ops_health_check"
      kwargs = {}
    })
  }
}

# Weekly MLOps retrain: Monday 02:30 JST = Sunday 17:30 UTC -> ECS worker
resource "aws_scheduler_schedule" "weekly_mlops_retrain" {
  name       = "${local.name_prefix}-weekly-mlops-retrain"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(30 17 ? * SUN *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.worker.arn
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = [aws_subnet.public_1.id, aws_subnet.public_2.id]
        security_groups  = [aws_security_group.ecs.id]
        assign_public_ip = true
      }
    }

    input = jsonencode({
      containerOverrides = [
        {
          name    = "${local.name_prefix}-worker"
          command = ["mlops_retrain", "{\"min_accuracy\":0.6,\"max_accuracy_drop\":0.03}"]
        }
      ]
    })
  }
}

# Daily MLOps monitoring: 01:00 JST = 16:00 UTC -> ECS worker
resource "aws_scheduler_schedule" "daily_mlops_monitoring" {
  name       = "${local.name_prefix}-daily-mlops-monitoring"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 16 * * ? *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.worker.arn
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = [aws_subnet.public_1.id, aws_subnet.public_2.id]
        security_groups  = [aws_security_group.ecs.id]
        assign_public_ip = true
      }
    }

    input = jsonencode({
      containerOverrides = [
        {
          name    = "${local.name_prefix}-worker"
          command = ["mlops_monitoring", "{}"]
        }
      ]
    })
  }
}

# Daily genre rotation crawl: 04:00 JST weekdays = 19:00 UTC Mon-Fri → Lambda
resource "aws_scheduler_schedule" "daily_genre_crawl" {
  name       = "${local.name_prefix}-daily-genre-crawl"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 19 ? * MON-FRI *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = local.api_lambda_arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    input = jsonencode({
      action             = "crawl"
      rotate_genre       = true
      platforms          = ["facebook", "instagram"]
      limit_per_platform = 20
    })
  }
}

resource "aws_lambda_permission" "eventbridge_genre_crawl" {
  statement_id  = "AllowEventBridgeGenreCrawl"
  action        = "lambda:InvokeFunction"
  function_name = local.api_lambda_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.daily_genre_crawl.arn
}

# Weekly media extraction: 04:00 JST Monday = 19:00 UTC Sunday → Lambda
resource "aws_scheduler_schedule" "weekly_media_extraction" {
  name       = "${local.name_prefix}-weekly-media-extraction"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 19 ? * SUN *)"
  schedule_expression_timezone = "UTC"

  target {
    arn      = local.api_lambda_arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    input = jsonencode({
      action   = "extract_media"
      limit    = 100
      statuses = ["pending", "pending_heavy"]
    })
  }
}

resource "aws_lambda_permission" "eventbridge_media_extraction" {
  statement_id  = "AllowEventBridgeMediaExtraction"
  action        = "lambda:InvokeFunction"
  function_name = local.api_lambda_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.weekly_media_extraction.arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "eventbridge_rankings" {
  statement_id  = "AllowEventBridgeRankings"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.light_tasks.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.daily_rankings.arn
}

resource "aws_lambda_permission" "eventbridge_alerts" {
  statement_id  = "AllowEventBridgeAlerts"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.light_tasks.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.daily_alerts.arn
}

resource "aws_lambda_permission" "eventbridge_ops_health_check" {
  statement_id  = "AllowEventBridgeOpsHealthCheck"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.light_tasks.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.daily_ops_health_check.arn
}
