# RDS Restore Runbook

## Preconditions
- AWS CLI configured for production account.
- Target snapshot exists (`aws rds describe-db-snapshots`).
- Maintenance window approved.

## A. Restore from DB snapshot
1. Choose snapshot ID:
   - `aws rds describe-db-snapshots --db-instance-identifier vaap-production-db`
2. Restore to a temporary instance:
   - `aws rds restore-db-instance-from-db-snapshot --db-instance-identifier vaap-production-db-restore --db-snapshot-identifier <snapshot-id> --db-instance-class db.t4g.micro --publicly-accessible false`
3. Wait until available:
   - `aws rds wait db-instance-available --db-instance-identifier vaap-production-db-restore`
4. Validate connectivity and schema.

## B. Point-in-time recovery (PITR)
1. Identify recovery timestamp (UTC).
2. Run:
   - `aws rds restore-db-instance-to-point-in-time --source-db-instance-identifier vaap-production-db --target-db-instance-identifier vaap-production-db-pitr --restore-time <ISO8601-UTC> --use-latest-restorable-time`
3. Wait until available and validate data consistency.

## C. Cutover checklist
- Security group and subnet group match production requirements.
- Application DB URL updated to restored instance endpoint.
- Run API health checks and critical queries.
- Monitor error rate and connection pool metrics for at least 30 minutes.

## D. Cleanup
- Keep old instance until rollback confidence is met.
- Delete temporary restore instances when validated.
- Record incident timeline and recovery point.
