# Agent C Task: Crawl Status API & Trend Refresh

## Background
Users need to trigger crawls from the dashboard and see progress. Also need trend analysis to update with fresh data.

## What to do

### 1. Crawl status endpoint
Add to rankings.py:

`GET /rankings/crawl-status`
- Query CrawlJob table for recent jobs (last 24h)
- Return: job_id, status, query, total_ads_found, created_at
- This lets frontend show crawl history and progress

### 2. Quick-crawl endpoint
Add to rankings.py:

`POST /rankings/quick-crawl`
- Takes: { query: str, limit: int = 20 }
- Internally calls the crawl logic (import from crawl_tasks or use _inline_crawl)
- Returns: { new_ads_count: int, keywords_searched: list }
- This is a simplified crawl trigger for the dashboard

### 3. Refresh trend data endpoint
`POST /rankings/refresh-trends`
- Recomputes trend scores for all ads based on latest data
- Returns: { updated_count: int }

### 4. Fresh ads endpoint
`GET /rankings/fresh-ads`
- Returns ads crawled in the last 7 days, sorted by created_at desc
- Include thumbnail_url resolution, hit_score, creative_type
- Pagination: page, per_page params

## Constraints
- INSTRUCTIONS.md conflict rules apply
- Only modify rankings.py (your territory)
- Use _resolve_thumbnail_url and _resolve_image_url helpers
- English-only print statements in scripts
