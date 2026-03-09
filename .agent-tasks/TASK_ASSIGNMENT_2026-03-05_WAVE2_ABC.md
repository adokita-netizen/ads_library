# Task Assignment: 2026-03-05 Wave 2

## Current Situation Summary

### Blockers
- **Docker Desktop**: Unstable/crashed. Image rebuild/push blocked.
- **Production DB**: `crawl_jobs` table missing (migration incomplete).
- **Worker Image**: Outdated (new tasks like `mlops_monitoring` not recognized).
- **API Image**: Partially deployed (playwright added, but crawl_jobs fix not applied).

### Recently Completed
- Agent A: A96(Lambda sourceIp), A97(CI/CD), A98(monitoring dashboard), A99(DB backup). A100 blocked by Docker.
- Agent B: Frontend deploy complete. B64-B68 series and Docker-dependent deploys blocked.
- Agent C: CI-003, CI-015, CI-032, CI-056, CI-082, CI-086, CI-128, CI-132, CI-136, CI-140 all completed today.

---

## Phase 1: Unblock Production (CRITICAL - Do First)

### Agent A: Docker Recovery + Image Deploy
**Task: A-WAVE2-1 (Production Unblock)**
1. Docker Desktop recovery (WSL reset, clean restart)
2. API image rebuild with crawl_jobs migration fix + push to ECR
3. Worker image rebuild with mlops_monitoring/retrain handlers + push to ECR
4. Lambda function update to new API image
5. ECS task definition update to new worker image
6. Verify: `GET /api/v1/rankings/crawl-status` returns 200
7. Verify: ECS `mlops_monitoring` task runs successfully

**Priority: BLOCKER - nothing else matters until this is done.**

### Agent B: Frontend Polish (Docker-Independent)
**Task: B-WAVE2-1 (Mock-to-Real Cleanup - Local Only)**
1. Audit all mock data locations in frontend (`grep -r "mock\|Mock\|MOCK\|sampleData\|dummyData"`)
2. For each mock: verify the real API endpoint exists and responds correctly
3. Replace mock data with real API calls using existing `api.ts` functions
4. Fix BUG-2, BUG-3, BUG-4 (from B67 task)
5. Run `npx tsc --noEmit` to verify type safety
6. Run all E2E tests: `CI=1 npx playwright test --reporter=line`

**Priority: HIGH - can proceed independently of Docker.**

### Agent C: Backend Hardening (Docker-Independent)
**Task: C-WAVE2-1 (Error Handler + Test Coverage)**
1. C60: Fix empty `pass` error handlers in `ads.py` and `media.py`
   - Replace bare `except: pass` with proper logging + error response
   - Ensure no exceptions are silently swallowed
2. C61: Add contract tests for critical API endpoints
   - `/api/v1/ads` CRUD operations
   - `/api/v1/media` upload/download
   - `/api/v1/rankings/quick-crawl` request/response schema
3. C62: OpenAPI schema documentation
   - Add response models to all endpoints missing them
   - Verify `/docs` renders correctly

**Priority: HIGH - can proceed independently of Docker.**

---

## Phase 2: Feature Completion (After Docker Recovery)

### Agent A: Infrastructure Maturity
**Task: A-WAVE2-2**
- Complete A100 (MLOps pipeline) after worker image is updated
- CI-005: DB migration rollback procedure documentation
- CI-009: NULL/empty normalization batch

### Agent B: UX & Integration
**Task: B-WAVE2-2**
- B65: ScenarioBuilder API integration
- B66: SavedScenarios persistence
- B68: Full E2E test pass verification
- CI-021: Table operation E2E tests

### Agent C: API Quality
**Task: C-WAVE2-3**
- C63: Load testing with 10,000 records simulation
- CI-008: Hit score delta tracking on recalculation
- CI-011: LP status judgment with retry + threshold tuning

---

## Execution Order

```
NOW (Parallel):
  Agent A: Docker recovery -> API image deploy -> Worker image deploy
  Agent B: B-WAVE2-1 (mock cleanup + bug fixes)
  Agent C: C-WAVE2-1 (error handlers + tests + docs)

AFTER Docker recovery:
  Agent A: A-WAVE2-2 (A100 completion + infra)
  Agent B: B-WAVE2-2 (scenario builder + E2E)
  Agent C: C-WAVE2-3 (load testing + scoring)
```

## Agent-Specific Quick Reference

| Agent | Phase 1 Task | Depends On | Phase 2 Task |
|-------|-------------|------------|--------------|
| A | Docker recovery + deploy | Nothing | A100, CI-005, CI-009 |
| B | Mock cleanup + bug fixes | Nothing | B65, B66, B68 |
| C | Error handlers + tests + docs | Nothing | C63, CI-008, CI-011 |
