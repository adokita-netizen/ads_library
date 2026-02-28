# Agent D Task: Fresh Ad Crawl Execution

## Background
We only have 177 stale ads. The user needs FRESH ads from Meta Ad Library NOW.
The crawl infrastructure already exists: POST /api/v1/ads/crawl with CrawlRequest schema.

## What to do

### 1. Create a bulk crawl script
`backend/scripts/bulk_crawl.py`

Use the existing crawl endpoint (or import crawl logic directly) to crawl fresh ads.

Keywords to crawl (Japanese ad market):
- ダイエット, 美容, 脱毛, サプリ, フィットネス
- 化粧品, ホワイトニング, エステ, プロテイン, 育毛
- スキンケア, 健康食品, 筋トレ, ヨガ, 脂肪燃焼

For each keyword:
- Crawl facebook and instagram platforms
- limit_per_platform = 50
- auto_analyze = True
- Sleep 2 seconds between keywords

### 2. Post-crawl media download
After crawl completes, run the existing `download_media_cache.py` logic on NEW ads only (ads where thumbnail_s3_key IS NULL).

### 3. Post-crawl creative analysis
Run `analyze_creative_elements.py` logic on new ads (where ad_metadata has no "creative_analysis" key).

### 4. Report results
Print: total new ads crawled, media cached, analyzed.

## Constraints
- INSTRUCTIONS.md conflict rules apply
- English-only print statements
- Do NOT modify rankings.py or frontend/
- Use requests library to call localhost:8000 API, OR import crawl logic directly
- Handle errors gracefully (some keywords may return 0 results)
