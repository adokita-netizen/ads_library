variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "vaap"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "vaap_db"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "vaap"
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "lambda_memory_size" {
  description = "API Lambda function memory in MB"
  type        = number
  default     = 1024
}

variable "lambda_timeout" {
  description = "API Lambda function timeout in seconds"
  type        = number
  default     = 300
}

variable "lambda_light_memory_size" {
  description = "Light Tasks Lambda function memory in MB"
  type        = number
  default     = 512
}

variable "lambda_light_timeout" {
  description = "Light Tasks Lambda function timeout in seconds"
  type        = number
  default     = 300
}

variable "worker_cpu" {
  description = "ECS worker task CPU units (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "worker_memory" {
  description = "ECS worker task memory in MB"
  type        = number
  default     = 4096
}

variable "cors_allowed_origins" {
  description = "Allowed CORS origins for API Gateway"
  type        = list(string)
  default     = ["https://d3qlbagx7gq5sp.cloudfront.net", "http://localhost:3000"]
}

variable "domain_name" {
  description = "Optional custom domain name for CloudFront"
  type        = string
  default     = ""
}

variable "nat_instance_type" {
  description = "NAT instance type"
  type        = string
  default     = "t4g.nano"
}

variable "meta_access_token" {
  description = "Meta Ad Library API access token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "alert_email" {
  description = "Email for AWS operational alerts (SNS/Budget). Leave empty to disable email subscription."
  type        = string
  default     = ""
}

variable "enable_budget_guardrails" {
  description = "Enable monthly AWS cost budget alerts."
  type        = bool
  default     = true
}

variable "monthly_budget_limit_usd" {
  description = "Monthly AWS budget limit (USD) for alerting."
  type        = number
  default     = 500
}

variable "budget_alert_threshold_percent" {
  description = "Budget alert threshold percentage."
  type        = number
  default     = 80
}

variable "rds_backup_retention_days" {
  description = "RDS automated backup retention days."
  type        = number
  default     = 7
}

variable "rds_max_allocated_storage" {
  description = "RDS max autoscaled storage in GB."
  type        = number
  default     = 200
}

variable "rds_performance_insights_enabled" {
  description = "Enable RDS Performance Insights."
  type        = bool
  default     = true
}

variable "s3_transition_to_ia_days" {
  description = "Days before transitioning S3 current objects to STANDARD_IA."
  type        = number
  default     = 30
}

variable "s3_transition_to_glacier_days" {
  description = "Days before transitioning S3 current objects to GLACIER_IR."
  type        = number
  default     = 180
}

variable "s3_noncurrent_transition_days" {
  description = "Days before transitioning S3 noncurrent object versions to GLACIER_IR."
  type        = number
  default     = 30
}

variable "s3_noncurrent_expiration_days" {
  description = "Days before expiring noncurrent S3 object versions."
  type        = number
  default     = 365
}

variable "sqs_message_retention_seconds" {
  description = "Message retention for primary SQS queues."
  type        = number
  default     = 345600
}

variable "sqs_dlq_retention_seconds" {
  description = "Message retention for SQS dead-letter queues."
  type        = number
  default     = 1209600
}
