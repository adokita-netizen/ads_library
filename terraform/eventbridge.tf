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
    arn      = aws_lambda_function.api.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    input = jsonencode({
      action       = "crawl"
      rotate_genre = true
      platforms    = ["facebook", "instagram"]
      limit_per_platform = 20
    })
  }
}

resource "aws_lambda_permission" "eventbridge_genre_crawl" {
  statement_id  = "AllowEventBridgeGenreCrawl"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
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
    arn      = aws_lambda_function.api.arn
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
  function_name = aws_lambda_function.api.function_name
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
