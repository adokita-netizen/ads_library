# VAAP Deploy Rollback

## Scope
This runbook covers rollback for:
- Lambda/API image (`vaap-production-api`, `vaap-production-sqs-ecs-trigger`, `vaap-production-light-tasks`)
- Worker ECS task image (`vaap-production-worker`)
- Frontend static assets (`s3://vaap-production-frontend` + CloudFront)

## 1. Lambda/API rollback
1. Find last known-good image tag in ECR:
   - repository: `vaap-production-api`
2. Update each Lambda function to that tag:
   - `vaap-production-api`
   - `vaap-production-sqs-ecs-trigger`
   - `vaap-production-light-tasks`
3. Wait for update completion:
   - `aws lambda wait function-updated --function-name <name>`
4. Re-run health check (`/health`) via Lambda invoke payload.

## 2. Worker rollback
1. Find last known-good image tag in ECR:
   - repository: `vaap-production-worker`
2. Register a new ECS task definition revision pointing to that image.
3. Update service to use the new revision.
4. Confirm running task health and log stability.

## 3. Frontend rollback
1. Restore previous build artifact to `s3://vaap-production-frontend`.
2. Invalidate CloudFront:
   - `aws cloudfront create-invalidation --distribution-id ERPIU1B8ZZ5ZA --paths "/*"`
3. Verify `/` and key pages load correctly.

## 4. Database rollback policy
- Migrations run during deploy and must be backward compatible.
- If a non-compatible migration was applied, use the migration emergency plan before app rollback.

## 5. Validation checklist
- API `/health` returns `200` with `{"status":"healthy"}`.
- Worker tasks are stable (no restart loops).
- Frontend pages load and API calls succeed.
- Error rates in CloudWatch return to baseline.
