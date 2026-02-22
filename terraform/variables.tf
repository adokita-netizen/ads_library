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
  description = "Lambda function memory in MB"
  type        = number
  default     = 512
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
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
