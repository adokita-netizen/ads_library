# Agent C Task: Webhook, Integration & Bulk Operations API

## What to do

### 1. Webhook management
`POST /rankings/webhooks`
- Body: { "url": "https://...", "events": ["new_hit", "score_change"], "name": "Slack通知" }
- Store in `backend/data/webhooks.json`
- Return webhook_id

`GET /rankings/webhooks`
- List all registered webhooks

`DELETE /rankings/webhooks/{webhook_id}`
- Remove webhook

`POST /rankings/webhooks/test/{webhook_id}`
- Send test payload to webhook URL
- Return success/failure

### 2. Bulk operations
`POST /rankings/bulk/tag`
- Body: { "ad_ids": [1,2,3], "tags": ["winner", "reference"] }
- Add tags to ad_metadata.tags for each ad
- Use flag_modified

`POST /rankings/bulk/export`
- Body: { "ad_ids": [1,2,3], "format": "csv"|"json", "fields": ["title","score","genre"] }
- Return downloadable data

`POST /rankings/bulk/compare`
- Body: { "ad_ids": [1,2,3,4,5] } (2-10 ads)
- Extended version of compare-ads with more detailed analysis

### 3. Integration status endpoint
`GET /rankings/integrations/status`
- Returns status of all integrations:
```json
{
  "meta_api": {"connected": true, "last_sync": "2026-02-28", "token_valid": true},
  "webhooks": {"active": 2, "last_triggered": "2026-02-28"},
  "crawl": {"status": "idle", "last_run": "2026-02-28", "next_scheduled": null},
  "data": {"total_ads": 308, "quality_grade": "B"}
}
```

### 4. Search analytics endpoint
`GET /rankings/search-analytics`
- Track and return popular search terms (from search-collections + autocomplete usage)
```json
{
  "popular_genres": [{"genre": "skincare", "search_count": 45}],
  "popular_keywords": [{"keyword": "美容", "count": 23}],
  "trending_searches": ["ダイエット", "脱毛"],
  "total_searches_7d": 156
}
```

### 5. Health check enhancement
Enhance the existing health check endpoint:
`GET /rankings/system-health`
- Returns comprehensive system health:
```json
{
  "api": "ok",
  "database": "ok",
  "media_cache": {"status": "ok", "size_mb": 456},
  "data_freshness": {"newest_ad": "2026-02-28", "oldest_ad": "2025-12-01"},
  "endpoints_count": 50,
  "uptime_info": "running"
}
```

## Constraints
- Only modify rankings.py
- Store state in backend/data/
- All print() English only
- No actual HTTP calls for webhooks (just store config + mock test)
