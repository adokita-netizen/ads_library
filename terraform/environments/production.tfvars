project_name = "vaap"
environment  = "production"
aws_region   = "ap-northeast-1"
db_name      = "vaap_db"
db_username  = "vaap"
# db_password should be set via TF_VAR_db_password environment variable

cors_allowed_origins = [
  "https://d3qlbagx7gq5sp.cloudfront.net",
]
