# Agent D Task: Crawl Scheduler & Media Optimization

## What to do

### 1. Create crawl scheduler script
Create `backend/scripts/scheduled_crawl_runner.py`:
- Cron-compatible script that runs the full crawl + analysis pipeline
- Steps:
  1. Check last crawl timestamp from `backend/data/crawl_schedule.json`
  2. If enough time has passed (configurable, default 24h), run crawl
  3. After crawl, run analysis pipeline: classify_fine_genre, extract_product_names, aggregate_metrics
  4. After analysis, run media pipeline: validate, auto-cache
  5. Log results to `backend/data/crawl_log.json`
- Print all output in English
- Exit code 0 on success, 1 on failure

### 2. Create media optimization script
Create `backend/scripts/optimize_media_cache.py`:
- Scan media_cache/ directory
- Remove duplicate files (same hash)
- Compress oversized images (> 500KB) using Pillow if available
- Remove orphaned files (no matching ad in DB)
- Report savings: files removed, space saved
- Print English only

### 3. Create crawl health monitor
Create `backend/scripts/crawl_health_monitor.py`:
- Check data freshness: how old is the newest ad?
- Check crawl coverage: are all configured pages being crawled?
- Check error rates from crawl logs
- Output health status:
  - GREEN: all good, data fresh
  - YELLOW: data > 3 days old or partial failures
  - RED: data > 7 days old or major failures
- Save to `backend/data/crawl_health.json`

### 4. Fix media.py inventory endpoint
Check GET /media/inventory endpoint works correctly:
- Should return complete media status
- Include: total_ads, thumbnails_cached, images_cached, videos_cached
- Include: cache_size_mb, orphaned_files
- Fix if broken

## Constraints
- English-only print
- Only modify media.py and scripts/
- No rankings.py or frontend changes
