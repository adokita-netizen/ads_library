# Agent C Task: Reports, Alerts & Missing API Endpoints

## What to do

### 1. Reports endpoint
`GET /rankings/report-summary`
- Returns comprehensive report data:
```json
{
  "overview": {
    "total_ads": 308,
    "hit_ads": 84,
    "hit_rate": 27.3,
    "total_estimated_spend_jpy": 13499850,
    "avg_hit_score": 56.1,
    "top_genre": "skincare",
    "data_date_range": { "from": "2025-12-01", "to": "2026-02-28" }
  },
  "genre_performance": [
    { "genre": "skincare", "genre_jp": "スキンケア", "ad_count": 43, "hit_rate": 0.65, "avg_score": 62, "top_archetype": "testimonial_story", "avg_spend_jpy": 45000 }
  ],
  "top_advertisers": [
    { "name": "...", "ad_count": 12, "hit_rate": 0.75, "avg_score": 68, "total_spend_jpy": 540000 }
  ],
  "creative_patterns": {
    "winning_combos": [...],
    "hook_performance": [...],
    "cta_performance": [...]
  }
}
```

### 2. Alerts system
`GET /rankings/alerts`
- Query: limit (default 20), unread_only (bool)
- Auto-generate alerts from data:
  - New hit ads (score >= 70 created in last 7 days)
  - Score changes (ads whose score changed significantly)
  - Competitor alerts (new ads from watched advertisers)
  - Crawl completion alerts
- Store read status in backend/data/alerts.json

`POST /rankings/alerts/{alert_id}/read`
- Mark alert as read

`POST /rankings/alerts/read-all`
- Mark all alerts as read

### 3. Bookmarks CRUD
`GET /rankings/bookmarks`
- List bookmarked ad IDs (from backend/data/bookmarks.json)

`POST /rankings/bookmarks`
- Body: { "ad_id": 123 }
- Add bookmark

`DELETE /rankings/bookmarks/{ad_id}`
- Remove bookmark

### 4. Dashboard KPI endpoint
`GET /rankings/dashboard-kpi`
- Quick KPI numbers for dashboard header:
```json
{
  "total_ads": 308,
  "new_ads_7d": 45,
  "hit_ads": 84,
  "active_ads": 200,
  "avg_score": 56.1,
  "top_genre": "skincare",
  "total_spend_jpy": 13499850,
  "data_freshness": "2026-02-28"
}
```

### 5. Missing endpoint fixes
Check if these endpoints exist and work. If not, add them:
- `GET /rankings/trends/weekly` - weekly trend data
- `GET /rankings/trends/market-overview` - market overview stats
- `GET /rankings/genre-comparison` - genre comparison data
- `GET /rankings/dashboard-summary` - dashboard summary

## Constraints
- Only modify rankings.py
- Store state files in backend/data/ (create dir if needed)
- All print() English only
