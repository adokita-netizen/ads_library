# Agent D Task: Scheduled Crawl & Auto-Pipeline

## Goal
Crawl should run automatically on schedule, not just manually. Build the automation layer.

## What to do

### 1. Crawl scheduler script
`backend/scripts/scheduled_crawl.py`
- Reads keyword list from `backend/config/crawl_keywords.json`
- For each keyword: call crawl API, wait for completion
- After all crawls: run media download, creative analysis, scoring
- Log results to `backend/logs/crawl_YYYYMMDD.log`
- Can be run via cron/Task Scheduler

### 2. Keyword config file
`backend/config/crawl_keywords.json`
```json
{
  "keywords": ["ダイエット", "美容", "脱毛", "サプリ", ...],
  "platforms": ["facebook", "instagram"],
  "limit_per_platform": 50,
  "schedule_interval_hours": 24
}
```

### 3. Crawl dedup logic
`backend/scripts/dedup_crawled_ads.py`
- Find duplicate ads (same external_id or same title+advertiser)
- Keep the one with most data, mark others as duplicate in ad_metadata
- Print dedup report

### 4. Crawl history tracker
Add to media.py or create new endpoint:
`GET /media/crawl-history` - return crawl stats over time (daily counts, new vs duplicate)

## Constraints
- English-only print, no rankings.py/frontend changes
