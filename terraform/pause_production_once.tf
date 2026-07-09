# One-time reversible pause for production cost control.
# The script only disables/stops compute entry points; it does not delete data,
# buckets, database snapshots, queues, logs, images, or Terraform state.

resource "terraform_data" "pause_production_20260709" {
  input = {
    reason     = "pause production AWS spend at user request"
    script_sha = filesha256("${path.module}/scripts/pause_production.sh")
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = "bash ${path.module}/scripts/pause_production.sh"
  }
}
