# Agent C Task: User Preferences, Export & Notification API

## What to do

### 1. User preferences endpoint
`GET /rankings/user-preferences`
- Returns user preferences from `backend/data/user_preferences.json`
```json
{
  "default_genre": null,
  "default_period": "monthly",
  "default_sort": "score_desc",
  "notifications_enabled": true,
  "notification_types": ["new_hit", "score_change", "competitor"],
  "watched_advertisers": ["advertiser1", "advertiser2"],
  "watched_genres": ["skincare", "diet_supplement"],
  "theme": "light",
  "items_per_page": 20,
  "auto_refresh": true,
  "auto_refresh_interval": 60
}
```

`PUT /rankings/user-preferences`
- Update preferences (partial update, merge with existing)

### 2. Export enhancement endpoints
`GET /rankings/export/report`
- Query: format (html|pdf_data), genre (optional), days (default 30)
- Returns formatted HTML report or structured data for PDF generation
- Include: KPI summary, genre breakdown, top ads table, creative patterns

`GET /rankings/export/advertiser-report/{advertiser_name}`
- Returns advertiser-specific report data

### 3. Notification subscription
`POST /rankings/notifications/subscribe`
- Body: { "type": "new_hit", "genre": "skincare", "threshold": 70 }
- Save to `backend/data/notification_subscriptions.json`

`GET /rankings/notifications/subscriptions`
- List active subscriptions

`DELETE /rankings/notifications/subscriptions/{sub_id}`
- Remove subscription

### 4. Data freshness endpoint
`GET /rankings/data-freshness`
- Returns:
```json
{
  "last_crawl": "2026-02-28T10:00:00",
  "next_scheduled": "2026-03-01T10:00:00",
  "total_ads": 308,
  "ads_last_24h": 5,
  "ads_last_7d": 45,
  "crawl_status": "idle",
  "data_quality_grade": "B",
  "fill_rates": {"fine_genre": 95, "creative_analysis": 88, "ranking_metrics": 100}
}
```

## Constraints
- Only modify rankings.py
- Store state in backend/data/
- All print() English only
