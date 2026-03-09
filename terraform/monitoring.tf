# ==================== Alerts (SNS + CloudWatch) ====================

resource "aws_sns_topic" "ops_alerts" {
  name = "${local.name_prefix}-ops-alerts"
}

resource "aws_sns_topic_subscription" "ops_alerts_email" {
  count = var.alert_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.ops_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "sqs_heavy_dlq_messages" {
  alarm_name          = "${local.name_prefix}-heavy-dlq-visible"
  alarm_description   = "Heavy task DLQ has messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.heavy_tasks_dlq.name
  }
}

resource "aws_cloudwatch_metric_alarm" "sqs_light_dlq_messages" {
  alarm_name          = "${local.name_prefix}-light-dlq-visible"
  alarm_description   = "Light task DLQ has messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.light_tasks_dlq.name
  }
}

resource "aws_cloudwatch_metric_alarm" "sqs_heavy_oldest_age" {
  alarm_name          = "${local.name_prefix}-heavy-queue-oldest-age"
  alarm_description   = "Heavy queue oldest message age is too high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 900
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.heavy_tasks.name
  }
}

resource "aws_cloudwatch_metric_alarm" "sqs_light_oldest_age" {
  alarm_name          = "${local.name_prefix}-light-queue-oldest-age"
  alarm_description   = "Light queue oldest message age is too high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 600
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.light_tasks.name
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu_high" {
  alarm_name          = "${local.name_prefix}-rds-cpu-high"
  alarm_description   = "RDS CPU utilization is high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_free_storage_low" {
  alarm_name          = "${local.name_prefix}-rds-free-storage-low"
  alarm_description   = "RDS free storage is low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5368709120 # 5 GiB
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.main.id
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_api_errors" {
  alarm_name          = "${local.name_prefix}-lambda-api-errors"
  alarm_description   = "API Lambda has errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    FunctionName = "${local.name_prefix}-api"
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_api_error_rate_high" {
  alarm_name          = "${local.name_prefix}-lambda-api-error-rate-high"
  alarm_description   = "API Lambda error rate is above 5%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  metric_query {
    id          = "error_rate"
    expression  = "IF(invocations>0, (errors/invocations)*100, 0)"
    label       = "API Lambda Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "Errors"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions = {
        FunctionName = "${local.name_prefix}-api"
      }
    }
  }

  metric_query {
    id = "invocations"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 300
      stat        = "Sum"
      dimensions = {
        FunctionName = "${local.name_prefix}-api"
      }
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_light_errors" {
  alarm_name          = "${local.name_prefix}-lambda-light-errors"
  alarm_description   = "Light-task Lambda has errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    FunctionName = "${local.name_prefix}-light-tasks"
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_trigger_errors" {
  alarm_name          = "${local.name_prefix}-lambda-trigger-errors"
  alarm_description   = "SQS->ECS trigger Lambda has errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    FunctionName = "${local.name_prefix}-sqs-ecs-trigger"
  }
}

resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx_high" {
  alarm_name          = "${local.name_prefix}-api-gateway-5xx-high"
  alarm_description   = "HTTP API 5XX errors detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "5xx"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    ApiId = aws_apigatewayv2_api.main.id
    Stage = "$default"
  }
}

resource "aws_cloudwatch_metric_alarm" "mlops_drift_high" {
  alarm_name          = "${local.name_prefix}-mlops-drift-high"
  alarm_description   = "MLOps monitoring detected high feature drift"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DriftMaxAbs"
  namespace           = "VAAP/MLOps"
  period              = 86400
  statistic           = "Maximum"
  threshold           = 0.15
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "mlops_accuracy_low" {
  alarm_name          = "${local.name_prefix}-mlops-accuracy-low"
  alarm_description   = "Latest deployed model test accuracy is below threshold"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ModelTestAccuracy"
  namespace           = "VAAP/MLOps"
  period              = 86400
  statistic           = "Average"
  threshold           = 0.60
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.ops_alerts.arn]
  ok_actions          = [aws_sns_topic.ops_alerts.arn]

  dimensions = {
    Environment = var.environment
  }
}

resource "aws_cloudwatch_dashboard" "ops_overview" {
  dashboard_name = "${local.name_prefix}-ops-overview"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Lambda API - Invocations / Errors"
          view   = "timeSeries"
          region = var.aws_region
          stat   = "Sum"
          period = 300
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.api.function_name],
            [".", "Errors", ".", "."]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Lambda API - Duration (p95)"
          view   = "timeSeries"
          region = var.aws_region
          stat   = "p95"
          period = 300
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.api.function_name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "HTTP API - Requests / 4xx / 5xx"
          view   = "timeSeries"
          region = var.aws_region
          stat   = "Sum"
          period = 300
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiId", aws_apigatewayv2_api.main.id, "Stage", "$default"],
            [".", "4xx", ".", ".", ".", "."],
            [".", "5xx", ".", ".", ".", "."]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "HTTP API - Latency"
          view   = "timeSeries"
          region = var.aws_region
          stat   = "p95"
          period = 300
          metrics = [
            ["AWS/ApiGateway", "Latency", "ApiId", aws_apigatewayv2_api.main.id, "Stage", "$default"],
            [".", "IntegrationLatency", ".", ".", ".", "."]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "RDS - CPU / Connections / Free Storage"
          view   = "timeSeries"
          region = var.aws_region
          period = 300
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.main.id],
            [".", "DatabaseConnections", ".", "."],
            [".", "FreeStorageSpace", ".", "."]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "SQS - Queue Depth / DLQ / Oldest Age"
          view   = "timeSeries"
          region = var.aws_region
          stat   = "Average"
          period = 300
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.heavy_tasks.name],
            [".", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.light_tasks.name],
            [".", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.heavy_tasks_dlq.name],
            [".", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.light_tasks_dlq.name],
            [".", "ApproximateAgeOfOldestMessage", "QueueName", aws_sqs_queue.heavy_tasks.name],
            [".", "ApproximateAgeOfOldestMessage", "QueueName", aws_sqs_queue.light_tasks.name]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 12
        height = 6
        properties = {
          title  = "MLOps - Drift / Accuracy"
          view   = "timeSeries"
          region = var.aws_region
          period = 86400
          metrics = [
            ["VAAP/MLOps", "DriftMaxAbs", "Environment", var.environment],
            [".", "ModelTestAccuracy", ".", "."]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 18
        width  = 12
        height = 6
        properties = {
          title  = "MLOps - Feature Rows / Drift Warning"
          view   = "timeSeries"
          region = var.aws_region
          period = 86400
          stat   = "Maximum"
          metrics = [
            ["VAAP/MLOps", "FeatureRows", "Environment", var.environment],
            [".", "DriftWarning", ".", "."]
          ]
        }
      }
    ]
  })
}

# ==================== Cost Guardrails (AWS Budget) ====================

resource "aws_budgets_budget" "monthly_cost" {
  count = var.enable_budget_guardrails ? 1 : 0

  name         = "${local.name_prefix}-monthly-cost"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = var.budget_alert_threshold_percent
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_sns_topic_arns  = [aws_sns_topic.ops_alerts.arn]
    subscriber_email_addresses = var.alert_email != "" ? [var.alert_email] : []
  }
}
