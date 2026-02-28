# Agent C Task: Analytics Dashboard & AI Insights API

## What to do

### 1. Analytics dashboard endpoint
`GET /rankings/analytics/overview`
- Returns comprehensive analytics:
```json
{
  "period": {"from": "2025-12-01", "to": "2026-02-28"},
  "kpis": {
    "total_ads": 308, "hit_ads": 84, "hit_rate": 27.3,
    "avg_score": 56.1, "total_spend_jpy": 13499850,
    "active_advertisers": 45, "genres_covered": 14
  },
  "trends": {
    "ads_growth_weekly": 3.2,
    "score_trend": "improving",
    "spend_trend": "increasing"
  },
  "highlights": [
    {"type": "achievement", "message": "Hit rate improved 5% this month"},
    {"type": "alert", "message": "3 new competitors entered skincare genre"}
  ]
}
```

### 2. AI insights endpoint
`GET /rankings/ai-insights`
- Query: genre (optional), focus (overview|creative|competitive|opportunity)
- Returns AI-style insights generated from data patterns:
```json
{
  "insights": [
    {
      "id": "ins_001",
      "type": "opportunity",
      "title": "質問型フックの活用余地あり",
      "description": "スキンケアジャンルでは質問型フックの採用率は15%だが、ヒット率は65%と最も高い",
      "confidence": 0.85,
      "action": "質問型フックのシナリオを検討してください",
      "related_ads": [1, 5, 12]
    }
  ],
  "generated_at": "2026-02-28T12:00:00"
}
```
- Generate insights from actual data patterns (not random)
- Categories: opportunity, warning, achievement, trend

### 3. Competitive landscape endpoint
`GET /rankings/competitive-landscape`
- Query: genre (optional)
- Returns market structure analysis:
```json
{
  "market_leaders": [{"name": "...", "share": 0.15, "trend": "growing"}],
  "challengers": [{"name": "...", "share": 0.08, "trend": "stable"}],
  "niche_players": [{"name": "...", "speciality": "skincare", "hit_rate": 0.8}],
  "new_entrants": [{"name": "...", "first_seen": "2026-02-15", "ad_count": 3}],
  "genre_competition": {"low": ["genre1"], "medium": ["genre2"], "high": ["genre3"]}
}
```

### 4. Performance attribution endpoint
`GET /rankings/performance-attribution`
- Query: ad_id (optional, for single ad) or genre
- Returns what factors drive performance:
```json
{
  "factors": [
    {"factor": "hook_type", "impact": 0.35, "best_value": "question"},
    {"factor": "cta_type", "impact": 0.25, "best_value": "urgency"},
    {"factor": "genre", "impact": 0.20, "best_value": "skincare"},
    {"factor": "has_video", "impact": 0.12, "best_value": true},
    {"factor": "title_length", "impact": 0.08, "optimal_range": [25, 50]}
  ],
  "r_squared": 0.67,
  "top_insight": "Hook type is the strongest performance predictor"
}
```

## Constraints
- Only modify rankings.py
- All print() English only
- Generate insights from actual DB data, not random
- Use existing helper functions
