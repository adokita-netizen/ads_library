#!/usr/bin/env bash
set -euo pipefail

DB_INSTANCE_ID="${1:-vaap-production-db}"
DATE_TAG="$(date +%Y%m%d-%H%M%S)"
SNAPSHOT_ID="${2:-${DB_INSTANCE_ID}-manual-${DATE_TAG}}"

echo "Creating RDS snapshot..."
echo "  DB instance: ${DB_INSTANCE_ID}"
echo "  Snapshot ID: ${SNAPSHOT_ID}"

aws rds create-db-snapshot \
  --db-instance-identifier "${DB_INSTANCE_ID}" \
  --db-snapshot-identifier "${SNAPSHOT_ID}"

echo "Snapshot request submitted: ${SNAPSHOT_ID}"
