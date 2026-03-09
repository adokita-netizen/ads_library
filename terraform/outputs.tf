output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "cloudfront_url" {
  description = "CloudFront distribution URL"
  value       = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.main.endpoint
}

output "s3_storage_bucket" {
  description = "S3 storage bucket name"
  value       = aws_s3_bucket.storage.id
}

output "s3_frontend_bucket" {
  description = "S3 frontend bucket name"
  value       = aws_s3_bucket.frontend.id
}

output "ecr_api_repo_url" {
  description = "ECR API repository URL"
  value       = aws_ecr_repository.api.repository_url
}

output "ecr_worker_repo_url" {
  description = "ECR Worker repository URL"
  value       = aws_ecr_repository.worker.repository_url
}

output "sqs_heavy_queue_url" {
  description = "SQS heavy tasks queue URL"
  value       = aws_sqs_queue.heavy_tasks.url
}

output "sqs_light_queue_url" {
  description = "SQS light tasks queue URL"
  value       = aws_sqs_queue.light_tasks.url
}

output "ops_alerts_sns_topic_arn" {
  description = "SNS topic ARN for operational alerts"
  value       = aws_sns_topic.ops_alerts.arn
}

output "budget_guardrail_enabled" {
  description = "Whether monthly cost budget guardrail is enabled"
  value       = var.enable_budget_guardrails
}
