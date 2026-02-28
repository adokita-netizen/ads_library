# Agent D Task: Advanced Crawling & Data Collection

## What to do

### 1. Competitor monitoring script
Create `backend/scripts/monitor_competitors.py`:
- Read watched advertisers from `backend/data/user_preferences.json` (or use top 20 by ad count)
- For each watched advertiser:
  - Count current ads, calculate avg score
  - Detect new ads in last 7 days
  - Detect score changes
- Store monitoring results in `backend/data/competitor_monitor.json`
- Generate alerts for significant changes
- Print summary table

### 2. Crawl analytics script
Create `backend/scripts/crawl_analytics.py`:
- Analyze crawl history from DB:
  - Ads per day/week/month
  - New ads discovery rate
  - Genre distribution over time
  - Advertiser entry/exit tracking
- Output to `exports/crawl_analytics.json`
- Print charts (ASCII bar charts in terminal)

### 3. LP change detector
Create `backend/scripts/detect_lp_changes.py`:
- For ads with LP URLs:
  - Hash current LP content (from cached HTML if available)
  - Compare with previous hash (store in `backend/data/lp_hashes.json`)
  - Flag changed LPs
- Store in ad_metadata.lp_changed = {"last_check": "2026-02-28", "changed": false}
- Print: "Checked X LPs, Y have changed since last check"

### 4. Media freshness checker
Create `backend/scripts/check_media_freshness.py`:
- For each cached media file:
  - Check file age
  - If > 30 days old, mark for re-download
  - Check if source URL is still accessible (HEAD request, with timeout)
- Output stale media list to `exports/stale_media.json`
- Print: "X files fresh, Y stale, Z unreachable"

### 5. Crawl configuration endpoint
Add to media.py:

`GET /media/crawl-config`
- Returns current crawl configuration from files

`PUT /media/crawl-config`
- Update crawl settings (schedule, pages, filters)
- Store in `backend/data/crawl_config.json`

## Constraints
- English-only print
- Only modify media.py and scripts/
- No rankings.py or frontend changes
- No actual HTTP requests to external URLs (mock/check local data only)
