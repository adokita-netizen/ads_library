# Agent D: Instructions

## Your Role
Backend media engineer.
Responsible for video URL extraction, thumbnail quality, media completeness, and crawling services.

## ★ Current Directive (Round 2) ★
**Follow PLANNER1_DATA_FOUNDATION_R2.md + D_R2_*.md for task priorities.**
Round 2 tasks (D-R2-1~6) take priority. Scheduled crawl -> video processing -> Phase 2.

---

## Task List

### COMPLETED
- ~~D1: Media Quality Pipeline~~
- ~~D2: Crawling Improvement~~
- ~~D3: Image Proxy~~
- ~~D4: 403 Thumbnail Re-fetch~~
- ~~D5: Fresh Crawl~~
- ~~D6: Media Pipeline Production~~

### Pending (Planner 1 assigns priority)
- D7: scheduled_crawl
- D8: video_processing
- D9: creative_asset_management
- D10: aws_media_infra
- D11: aws_rekognition
- D12: lp_crawler
- D13: aws_transcribe_comprehend
- D14: media_precision (aggressive recovery)
- D15: genre_specific_crawl
- D16: scenario_assets
- D17: full_media_pipeline
- D18: crawl_scheduler
- D19: video_analysis
- D20: creative_intelligence
- D21: advanced_crawling

### Continuous Improvement Tasks (Agent D)
Prioritize Agent D items from `CONTINUOUS_IMPROVEMENT_BACKLOG.md`.

- D22: CI-038 Add duplicate-start guard for crawl jobs (P0)
- D23: CI-054 Adaptive suppression control for HTTP 429 spikes (P0)
- D24: CI-004 Standardize crawl failure reason codes (P1)
- D25: CI-010 Nightly re-validation for media URL reachability (P1)
- D26: CI-042 Optimize thumbnail fetch fallback order (P1)
- D27: CI-046 JSON structured logging for crawl/media tasks (P1)
- D28: CI-058 Improve retry/requeue strategy for transient media failures (P1)

Recommended order:
1. D22
2. D23
3. D24
4. D27
5. D26

### Continuous Improvement Tasks (Agent D, Batch 3)
Add Agent D items from Batch 3 in `CONTINUOUS_IMPROVEMENT_BACKLOG.md`.

- D70: CI-064 Auto-throttle by crawl source health score (P0)
- D71: CI-080 Proxy/egress health checks automation (P0)
- D72: CI-068 Media duplicate detection via hash compare (P1)
- D73: CI-072 Standardize compliance/access-control crawl logs (P1)
- D74: CI-084 Snapshot fallback capture queue (P1)
- D75: CI-088 DLQ replay tool for failed media pipeline items (P1)
- D76: CI-076 Retry budget dashboard for crawl/media retries (P2)

Recommended order:
1. D70
2. D71
3. D72
4. D73
5. D75

### Continuous Improvement Tasks (Agent D, Batch 4)
Add Agent D items from Batch 4 in CONTINUOUS_IMPROVEMENT_BACKLOG.md.

- D80: CI-094 Re-prioritize crawl targets by outcome value (P0)
- D81: CI-110 Emergency suppression mode for 429/5xx spikes (P0)
- D82: CI-098 Optimize layered timeout settings for media fetch (P1)
- D83: CI-102 Strengthen blocked-domain/path guardrails (P1)
- D84: CI-114 Automate sampling for crawl result verification (P1)
- D85: CI-118 Version media extractors and track quality delta (P1)
- D86: CI-106 Report failure patterns by platform/source (P2)

Recommended order:
1. D80
2. D81
3. D82
4. D83
5. D84
### Continuous Improvement Tasks (Agent D, Batch 5)
Add Agent D items from Batch 5 in CONTINUOUS_IMPROVEMENT_BACKLOG.md.

- D90: CI-121 Pin list crawling to latest-first retrieval (P0)
- D91: CI-122 Add extraction-accuracy validation against source content (P0)
- D92: CI-126 Add recrawl fallback when collected count is below 30 (P1)

Recommended order:
1. D90
2. D91
3. D92

### Continuous Improvement Tasks (Agent D, Batch 6)
Add Agent D items from Batch 6 in CONTINUOUS_IMPROVEMENT_BACKLOG.md.

- D93: CI-131 Add schema validation for crawl results before DB insert (P0)
- D94: CI-135 Add metrics collection for media processing pipeline (P1)
- D95: CI-139 Automate crawl proxy rotation strategy (P2)

Recommended order:
1. D93
2. D94
3. D95

### 🅰️ ABC Priority Tasks (2026-03-05 Added)

**Priority A (Critical):**
- D36: Batch process ~50 PENDING media extractions (run Playwright pipeline for all remaining ads)
- D96: Creative Library Recovery & Download Completeness

Recommended order:
1. **D36** (blocker: ads without media cannot display properly)
2. **D96** (blocker: ads may be viewable but still not downloadable)

### Phase 2 (Product Enhancement)
- D33: intelligent_crawl_orchestration (priority queue + adaptive rate limit + circuit breaker)
- D34: video_intelligence_pipeline (keyframe extraction + CV analysis + auto-thumbnail)
- D35: multi_platform_crawl_expansion (YouTube/TikTok/X production-ready crawlers)

### Code Quality Fixes — COMPLETED by Planner D (2026-03-01)
- [x] media_tasks.py (D29): exponential backoff, session.rollback before retry, retrying/failed status split
- [x] media_extraction.py (D30): try-finally browser.close(), no more zombie processes
- [x] crawl_tasks.py (D31): _merge_crawled_data() for duplicate protection, no null overwrites
- [x] meta_crawler.py (D32): 429 rate limit with Retry-After, 401 token expiry critical log
- [x] thumbnail_fetcher.py: Event loop cleanup — COMPLETED (asyncio.run() replaces manual loop)

---

## Required Reading Before Starting
```
backend/app/services/media_extraction.py   <-- MediaExtractor
backend/app/tasks/media_tasks.py           <-- Celery media tasks
backend/app/services/thumbnail_fetcher.py  <-- ThumbnailFetcher
backend/app/services/crawling/             <-- Crawler group
backend/app/tasks/crawl_tasks.py           <-- Crawl tasks
backend/app/tasks/runner.py                <-- ECS task runner
backend/app/models/ad.py                   <-- Ad model
```

---

## CONFLICT PREVENTION RULES

### Files You CAN Edit (Agent D exclusive)
```
backend/scripts/extract_missing_videos.py
backend/scripts/backfill_media_urls.py
backend/scripts/fix_bad_thumbnails.py
backend/scripts/update_media_status.py
backend/scripts/fix_creative_types.py
backend/app/services/media_extraction.py
backend/app/services/thumbnail_fetcher.py
backend/app/services/crawling/               <-- all files
backend/app/tasks/crawl_tasks.py
backend/app/tasks/media_tasks.py
backend/app/tasks/runner.py                  <-- ECS entry point
docker/Dockerfile.worker
```

### Files You MUST NOT Edit
```
# Agent A (data quality / metrics)
backend/scripts/classify_ads.py
backend/scripts/fix_destination_urls.py
backend/scripts/fix_titles.py
backend/scripts/collect_delivery_dates.py
backend/scripts/collect_real_metrics.py
backend/scripts/check_ad_survival.py
backend/app/tasks/metrics_tasks.py

# Agent B (frontend)
frontend/                                    <-- never touch

# Agent C (scoring / ranking API)
backend/app/services/ranking/
backend/app/api/endpoints/rankings.py
backend/app/services/competitive/
backend/app/services/prediction/
backend/scripts/recompute_hit_scores.py
backend/scripts/check_lp_health.py
```

### Shared File: lambda_handler.py
- Agent D may ONLY modify `_run_crawl()` function tail
- Agent C owns: new actions, new functions
- Coordinate via COORDINATION_LOG.md

### Ad Model Write Permissions
```
ad.video_url
ad.image_url
ad.thumbnail_url
ad.thumbnail_s3_key
ad.image_s3_key
ad.image_s3_keys
ad.creative_type
ad.media_extraction_status
ad.duration_seconds
ad.resolution_width/height
ad.file_size_bytes
```

### ad_metadata Keys (Agent D writes)
```python
meta["thumbnail_fixed"] = True
meta["creative_quality"] = "high"
meta["extraction_method"] = "playwright"
meta["media_urls_backfilled"] = True
meta["media_quality_issues"] = [...]
meta["media_extraction_status"] = "..."
meta["media_completeness_score"] = 0.85
```

### ad_metadata Keys You MUST NOT Write
```
days_running, is_still_running, estimated_*        <-- Agent A
latest_hit_score, hit_level, is_hit, latest_score_breakdown  <-- Agent C
```

### ad_metadata Update Pattern (mandatory)
```python
from sqlalchemy.orm.attributes import flag_modified
meta = dict(ad.ad_metadata or {})
meta["your_key"] = "your_value"
ad.ad_metadata = meta
flag_modified(ad, "ad_metadata")
session.commit()
```

### cp932 Encoding
- Print statements: English ONLY


