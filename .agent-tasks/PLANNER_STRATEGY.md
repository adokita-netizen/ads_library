# 3 Planner Strategy — VAAP Phase 2

## Current Reality (2026-03-01)

### What we HAVE:
- 160+ API endpoints implemented
- 21 frontend navigation views all routed
- 16 DB models, 12 router modules
- CV/Audio/NLP/GenerativeAI services built
- 10+ ad platform crawlers coded

### What's BLOCKING:
- **Meta API token INVALID** → can't crawl new ads
- **Only 58 ads in DB** → all features look empty
- **No actual media URLs** → snapshot_url only
- **Playwright not deployed** → can't extract media
- **dispatcher.py bug** → MessageGroupId=None

### Conclusion:
Code is 80%+ built. The bottleneck is DATA, not features.
Priority = Make existing features work with real data, NOT add new features.

---

## Planner Division (Avoid Cannibalization)

### Planner 1: DATA FOUNDATION (Agent A + Agent D)
**Goal**: Get data flowing into the system

**Immediate Tasks (Day 1)**:
1. [D] Fix dispatcher.py MessageGroupId=None bug (1 line)
2. [D] Dockerfile.worker に Playwright + Chromium 追加
3. [A] Meta API token 設定確認（user が取得後）
4. [D] Media extraction pipeline 接続 (Lambda→SQS→ECS→Playwright→DB)
5. [A] A19_full_data_pipeline.md — Run all analysis scripts on 58 ads

**Week 1 Tasks**:
6. [D] D7 — Scheduled crawl setup
7. [A] A8 — Production data quality (fix NULL scores, creative analysis)
8. [D] D14 — Media precision (aggressive recovery)
9. [A] A17 — Metrics delta tracking (再生増加数 calculation)

**Files Owned**:
- Agent A: `backend/scripts/`, `backend/app/tasks/metrics_tasks.py`
- Agent D: `backend/app/services/crawling/`, `backend/app/services/media_extraction.py`, `backend/app/tasks/crawl_tasks.py`, `backend/app/tasks/media_tasks.py`, `Dockerfile.worker`

---

### Planner 2: API VERIFICATION & GAPS (Agent C)
**Goal**: Ensure all 160+ endpoints actually work, fill logic gaps

**Immediate Tasks (Day 1)**:
1. [C] Smoke test ALL rankings endpoints with existing 58 ads
2. [C] Fix broken endpoints (return 500/404 unexpectedly)
3. [C] C10 — Production API polish (export, search, dashboard-summary)

**Week 1 Tasks**:
4. [C] Verify /rankings/pro-ranking returns correct data format for ProRankingTable
5. [C] C17 — Precision improvements (hit/non-hit filtering accuracy)
6. [C] C13 — Search & filter API (autocomplete, saved searches)
7. [C] Test /competitive, /lp-analysis, /predictions endpoints

**Files Owned**:
- Agent C: `backend/app/services/ranking/`, `backend/app/api/endpoints/rankings.py`, `backend/app/services/competitive/`, `backend/app/services/prediction/`

---

### Planner 3: FRONTEND E2E VERIFICATION & POLISH (Agent B)
**Goal**: Ensure all 21 views actually display data correctly

**Immediate Tasks (Day 1)**:
1. [B] Verify PRO DATABASE (default view) works with real API data
2. [B] Fix any TypeScript build errors (npx next build)
3. [B] Test all 21 navigation views — which ones work, which are broken?

**Week 1 Tasks**:
4. [B] B19 integration completion — ProRankingView integration into page.tsx/Sidebar.tsx (partially done per status.md)
5. [B] Fix broken views that call non-working APIs (graceful fallback)
6. [B] B21 — Advanced filters (improve existing filter panel)
7. [B] B23 — Real-time dashboard (KPI cards with actual data)

**Files Owned**:
- Agent B: `frontend/src/` (全域)

---

## Conflict Prevention Rules

### NEVER overlap:
- Planner 1 & 2: A touches scripts+tasks, C touches services+api — no overlap
- Planner 1 & 3: A/D = backend only, B = frontend only — no overlap
- Planner 2 & 3: C = backend API, B = frontend — no overlap

### Coordination Points:
1. When C changes API response format → notify B to update frontend types
2. When A/D adds new data fields → notify C to include in scoring
3. When B needs new API endpoint → request to C

### Communication Protocol:
- Each planner updates their agents' `status.md` after each task
- Cross-planner notifications go in `.agent-tasks/COORDINATION_LOG.md`

---

## Priority Matrix

| Priority | Task | Planner | Impact |
|----------|------|---------|--------|
| P0 | Meta API token setup | User + P1 | Unlocks all data collection |
| P0 | dispatcher.py bug fix | P1 (D) | Unlocks SQS pipeline |
| P0 | Playwright worker deploy | P1 (D) | Unlocks media extraction |
| P1 | Full data pipeline on 58 ads | P1 (A) | Populates all analysis fields |
| P1 | API smoke test | P2 (C) | Finds broken endpoints |
| P1 | Frontend E2E verification | P3 (B) | Finds broken views |
| P2 | Scheduled crawl | P1 (D) | Automated data freshness |
| P2 | Pro-ranking API verification | P2 (C) | Ensures main view works |
| P2 | PRO DATABASE view polish | P3 (B) | Best first impression |
| P3 | Advanced features | All | After data flows |

---

## What NOT to do (Anti-Patterns)

1. ❌ Do NOT create more task files (59 is already too many)
2. ❌ Do NOT add new features before existing ones work
3. ❌ Do NOT build advanced analytics without sufficient data (58 ads ≠ meaningful ML)
4. ❌ Do NOT parallelize A and C when C depends on A's data output
5. ❌ Do NOT write new endpoints — verify existing 160+ first

---

## Success Metrics (End of Week 1)

- [ ] Meta API token valid and crawling works
- [ ] 200+ ads in DB (from new crawl)
- [ ] All 58 existing ads have complete analysis data
- [ ] Media URLs populated (not just snapshot_url)
- [ ] PRO DATABASE view shows real, meaningful data
- [ ] All 21 navigation views either work or show graceful fallback
- [ ] 0 broken API endpoints (all return valid responses)
