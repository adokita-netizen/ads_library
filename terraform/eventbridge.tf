# ==================== EventBridge Scheduler ====================

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
