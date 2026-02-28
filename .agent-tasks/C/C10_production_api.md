# Agent C Task: Production-Ready API & Download Support

## Goal
All APIs must work reliably, return complete data, and support export/download features.

## What to do

### 1. Export API endpoints
Add to rankings.py:

`GET /rankings/export/csv` - export all ads as CSV download
- Query params: genre, min_score, date_from, date_to
- Return as StreamingResponse with Content-Disposition header
- Include: all ad fields + creative_analysis + hit_score

`GET /rankings/export/json` - same but JSON format

`GET /rankings/export/report` - export hit pattern analysis report as JSON
- Include: hit factors, winning patterns, genre comparison, creative DNA stats

### 2. Ad detail API improvements
Update existing endpoints to always include:
- thumbnail_url: resolved via _resolve_thumbnail_url (proxy URL)
- image_url: resolved via _resolve_image_url (proxy URL)
- video_url: add _resolve_video_url helper (check media_cache/videos/{ad_id}.mp4)
- creative_analysis: from ad_metadata
- media_status: cached/uncached/partial
- download_urls: { thumbnail, image, video } pointing to /media/download/{ad_id}

### 3. Search & filter API
`GET /rankings/search`
- Full-text search across title, description, advertiser_name
- Filters: genre, creative_type, hook_type, cta_type, emotion, min_score, date_range
- Sort: score_desc, date_desc, longevity_desc
- Pagination: page, per_page
- Return same format as hit-ads with all resolved URLs

### 4. Dashboard stats API improvements
Update /rankings/dashboard-summary to include:
- total_ads (all time)
- fresh_ads_count (last 7 days)
- media_cache_rate (% with cached thumbnails)
- avg_hit_score
- top_genres, top_hooks, top_ctas

## Constraints
- INSTRUCTIONS.md conflict rules apply
- Only modify rankings.py
- Use StreamingResponse for CSV export (import from starlette.responses)
- English-only in code comments
