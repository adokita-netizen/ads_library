# ==================== RDS PostgreSQL ====================

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet"
  subnet_ids = [aws_subnet.private_1.id, aws_subnet.private_2.id]

  tags = { Name = "${local.name_prefix}-db-subnet-group" }
}

resource "aws_db_instance" "main" {
  identifier     = "${local.name_prefix}-db"
  engine         = "postgres"
  engine_version = "15"
  instance_class = var.db_instance_class

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  allocated_storage     = 20
  max_allocated_storage = 50
  storage_type          = "gp3"
  storage_encrypted     = true

  multi_az               = false
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period   = 7
  backup_window             = "17:00-18:00" # 02:00-03:00 JST
  maintenance_window        = "sun:18:00-sun:19:00"
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name_prefix}-db-final"
  deletion_protection       = true

  performance_insights_enabled = false

  tags = { Name = "${local.name_prefix}-db" }
}
