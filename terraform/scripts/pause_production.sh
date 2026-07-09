# One-time production pause commands for 2026-07-09.
# Triggered by terraform/pause_production_once.tf during GitHub Actions Terraform apply.

set +e
set +u
set +o pipefail
REGION="${AWS_REGION:-ap-northeast-1}"
PREFIX="vaap-production"
RUN_ID="pause-20260709"

echo "[$RUN_ID] Pausing AWS resources in $REGION with prefix $PREFIX"

run() {
  echo "+ $*"
  "$@"
  local code=$?
  if [ "$code" -ne 0 ]; then
    echo "WARN: command failed with exit $code: $*"
  fi
  return 0
}

# Block new Lambda invocations. Zero reserved concurrency is the documented
# reversible way to throttle a function to no executions.
for fn in "$PREFIX-api" "$PREFIX-sqs-ecs-trigger" "$PREFIX-light-tasks"; do
  run aws lambda put-function-concurrency \
    --region "$REGION" \
    --function-name "$fn" \
    --reserved-concurrent-executions 0
done

# Disable SQS event source mappings to avoid polling/retry loops while paused.
for fn in "$PREFIX-sqs-ecs-trigger" "$PREFIX-light-tasks"; do
  aws lambda list-event-source-mappings \
    --region "$REGION" \
    --function-name "$fn" \
    --query 'EventSourceMappings[].UUID' \
    --output text | tr '\t' '\n' | while read -r uuid; do
      [ -n "$uuid" ] && run aws lambda update-event-source-mapping \
        --region "$REGION" \
        --uuid "$uuid" \
        --no-enabled
    done
done

# Disable every EventBridge Scheduler schedule under the production prefix,
# including schedules that may exist in AWS but are not in the current repo.
TMPDIR="$(mktemp -d)"
if aws scheduler list-schedules --region "$REGION" --output json > "$TMPDIR/schedules.json"; then
  python - "$TMPDIR/schedules.json" > "$TMPDIR/schedule-list.txt" <<'PY'
import json, sys
prefix = "vaap-production-"
data = json.load(open(sys.argv[1], encoding="utf-8"))
for item in data.get("Schedules", []):
    name = item.get("Name", "")
    if name.startswith(prefix):
        print(name + "\t" + item.get("GroupName", "default"))
PY

  while IFS=$'\t' read -r name group; do
    [ -z "$name" ] && continue
    echo "Disabling schedule $group/$name"
    if ! aws scheduler get-schedule \
      --region "$REGION" \
      --name "$name" \
      --group-name "$group" \
      --output json > "$TMPDIR/get-$name.json"; then
      echo "WARN: could not read schedule $group/$name"
      continue
    fi
    python - "$TMPDIR/get-$name.json" "$TMPDIR/update-$name.json" <<'PY'
import json, sys
src, dst = sys.argv[1:3]
data = json.load(open(src, encoding="utf-8"))
allowed = [
    "Name", "GroupName", "ScheduleExpression", "ScheduleExpressionTimezone",
    "StartDate", "EndDate", "Description", "FlexibleTimeWindow", "Target",
    "KmsKeyArn", "ActionAfterCompletion"
]
out = {k: data[k] for k in allowed if k in data and data[k] is not None}
out["State"] = "DISABLED"
json.dump(out, open(dst, "w", encoding="utf-8"))
PY
    run aws scheduler update-schedule \
      --region "$REGION" \
      --cli-input-json "file://$TMPDIR/update-$name.json"
  done < "$TMPDIR/schedule-list.txt"
else
  echo "WARN: scheduler list-schedules failed"
fi

# Stop any currently running ECS tasks; there is no ECS service in this module,
# but ad-hoc/scheduled Fargate tasks can remain active after schedules stop.
TASKS=$(aws ecs list-tasks \
  --region "$REGION" \
  --cluster "$PREFIX-cluster" \
  --desired-status RUNNING \
  --query 'taskArns[]' \
  --output text 2>/dev/null)
for task in $TASKS; do
  run aws ecs stop-task \
    --region "$REGION" \
    --cluster "$PREFIX-cluster" \
    --task "$task" \
    --reason "$RUN_ID"
done

# Stop the NAT EC2 instance by tag. Do not terminate/delete anything.
NAT_IDS=$(aws ec2 describe-instances \
  --region "$REGION" \
  --filters "Name=tag:Name,Values=$PREFIX-nat-instance" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[].Instances[].InstanceId' \
  --output text 2>/dev/null)
if [ -n "$NAT_IDS" ]; then
  run aws ec2 stop-instances --region "$REGION" --instance-ids $NAT_IDS
else
  echo "No NAT instance found by tag $PREFIX-nat-instance"
fi

# Stop the RDS DB instance. RDS may auto-restart after the AWS maximum stop window.
STATUS=$(aws rds describe-db-instances \
  --region "$REGION" \
  --db-instance-identifier "$PREFIX-db" \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text 2>/dev/null)
echo "RDS $PREFIX-db status: ${STATUS:-unknown}"
case "$STATUS" in
  available)
    run aws rds stop-db-instance --region "$REGION" --db-instance-identifier "$PREFIX-db"
    ;;
  stopped|stopping)
    echo "RDS already $STATUS"
    ;;
  *)
    echo "Skipping RDS stop because status is not available/stopped/stopping: ${STATUS:-unknown}"
    ;;
esac

echo "[$RUN_ID] Pause commands submitted. Final quick status:"
run aws lambda get-function-concurrency --region "$REGION" --function-name "$PREFIX-api"
run aws rds describe-db-instances --region "$REGION" --db-instance-identifier "$PREFIX-db" --query 'DBInstances[0].DBInstanceStatus' --output text
run aws ecs list-tasks --region "$REGION" --cluster "$PREFIX-cluster" --desired-status RUNNING --query 'length(taskArns)' --output text
