# Finalize production pause after all Terraform-managed resources settle.
# This runs the same non-destructive pause script after Terraform has completed
# any resource modifications/replacements from the plan, so late-created NAT or
# RDS state transitions are handled at the end of apply.

resource "terraform_data" "pause_production_finalize_20260709" {
  input = {
    reason     = "finalize production AWS spend pause after terraform resource changes"
    script_sha = filesha256("${path.module}/scripts/pause_production.sh")
    run_id     = "finalize-20260709"
  }

  depends_on = [
    aws_db_instance.main,
    aws_instance.nat,
    aws_eip_association.nat,
    aws_lambda_function.api,
    aws_lambda_function.sqs_ecs_trigger,
    aws_lambda_function.light_tasks,
    aws_lambda_event_source_mapping.heavy_tasks,
    aws_lambda_event_source_mapping.light_tasks,
    aws_scheduler_schedule.daily_crawl,
    aws_scheduler_schedule.daily_rankings,
    aws_scheduler_schedule.daily_alerts,
    aws_scheduler_schedule.daily_ops_health_check,
    aws_scheduler_schedule.weekly_mlops_retrain,
    aws_scheduler_schedule.daily_mlops_monitoring,
    aws_scheduler_schedule.daily_genre_crawl,
    aws_scheduler_schedule.weekly_media_extraction,
    aws_ecs_task_definition.worker,
  ]

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = "bash ${path.module}/scripts/pause_production.sh"
  }
}
