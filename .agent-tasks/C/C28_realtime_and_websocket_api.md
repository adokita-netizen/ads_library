# Agent C Task: Real-time Updates & Advanced Search API

## What to do

### 1. Long-polling updates endpoint
`GET /rankings/updates/poll`
- Query: since (ISO timestamp), types (comma-separated: new_ads,score_changes,alerts)
- Returns updates since given timestamp:
```json
{
  "updates": [
    {"type": "new_ad", "ad_id": 305, "title": "...", "timestamp": "2026-02-28T12:00:00"},
    {"type": "score_change", "ad_id": 12, "old_score": 55, "new_score": 72, "timestamp": "..."}
  ],
  "server_time": "2026-02-28T12:01:00",
  "has_more": false
}
```
- Check DB for recent changes
- Useful for frontend auto-refresh

### 2. Advanced search endpoint
`POST /rankings/advanced-search`
- Body with complex filter object:
```json
{
  "query": "美容",
  "filters": {
    "genres": ["skincare", "diet"],
    "score_range": [50, 100],
    "view_range": [10000, null],
    "spend_range": [null, 500000],
    "date_range": ["2026-01-01", "2026-02-28"],
    "hook_types": ["question", "number"],
    "cta_types": ["urgency"],
    "formats": ["video"],
    "destinations": ["official_site", "article_lp"],
    "exclude_advertisers": ["CompanyX"],
    "has_lp": true,
    "is_active": true
  },
  "sort": {"field": "score", "direction": "desc"},
  "page": 1,
  "page_size": 20
}
```
- Supports all filter combinations
- Returns same format as pro-ranking

### 3. Saved search endpoint
`POST /rankings/saved-searches`
- Body: { "name": "高スコア美容広告", "filters": {...}, "notify": true }
- Save complex search as named search
- If notify=true, include in alerts when new matching ads appear

`GET /rankings/saved-searches`
- List all saved searches with last run count

`POST /rankings/saved-searches/{id}/run`
- Execute saved search and return results

### 4. Quick stats endpoint
`GET /rankings/quick-stats/{ad_id}`
- Returns lightweight stats for hover previews:
```json
{
  "id": 1,
  "score": 72,
  "rank": 15,
  "percentile": 85,
  "genre_rank": 3,
  "trend": "up",
  "similar_count": 8
}
```

## Constraints
- Only modify rankings.py
- All print() English only
- Store saved searches in backend/data/saved_searches.json
