# Agent C Task: Benchmark, Comparison & Advanced Analytics API

## What to do

### 1. Genre benchmarks endpoint
`GET /rankings/genre-benchmarks`
- Query: genre (optional, returns all if empty)
- Returns percentile benchmarks for each genre:
```json
{
  "benchmarks": {
    "skincare": {
      "hit_score": {"median": 45, "p25": 30, "p75": 62, "p90": 78, "count": 43},
      "view_count": {"median": 15000, "p25": 5000, "p75": 45000, "p90": 120000},
      "spend_jpy": {"median": 30000, "p25": 10000, "p75": 80000, "p90": 200000},
      "longevity_days": {"median": 21, "p25": 7, "p75": 45, "p90": 90}
    }
  }
}
```
- Compute from live DB data using numpy-free percentile calculation

### 2. Ad comparison endpoint
`POST /rankings/compare-ads`
- Body: { "ad_ids": [1, 2, 3] } (2-5 ads)
- Returns side-by-side comparison:
```json
{
  "ads": [
    {
      "id": 1, "title": "...", "advertiser": "...",
      "metrics": { "hit_score": 72, "views": 50000, "spend_jpy": 120000, "longevity_days": 45 },
      "creative": { "hook_type": "question", "cta_type": "urgency", "format": "video" },
      "percentile_rank": { "hit_score": 85, "views": 72, "spend": 60 }
    }
  ],
  "winner": { "id": 1, "reasons": ["Highest hit score", "Best view-to-spend ratio"] },
  "insights": ["Ad 1 uses question hook which has 23% higher hit rate in skincare genre"]
}
```

### 3. Advertiser deep-dive endpoint
`GET /rankings/advertiser/{advertiser_name}/profile`
- Returns advertiser analytics:
```json
{
  "name": "...",
  "total_ads": 15,
  "active_ads": 8,
  "hit_rate": 0.6,
  "avg_score": 58,
  "total_spend_jpy": 1200000,
  "genres": [{"genre": "skincare", "count": 8}],
  "creative_style": { "preferred_hooks": [...], "preferred_ctas": [...], "avg_duration": 30 },
  "timeline": [{"month": "2026-01", "ads": 5, "avg_score": 55}],
  "top_ads": [{"id": 1, "title": "...", "score": 82}]
}
```

### 4. Trend forecast endpoint
`GET /rankings/trends/forecast`
- Query: genre (optional), metric (default "ad_count")
- Returns simple linear projection:
```json
{
  "historical": [{"week": "2026-W05", "value": 45}, ...],
  "forecast": [{"week": "2026-W10", "value": 52, "confidence": 0.7}],
  "trend": "increasing",
  "change_rate_weekly": 3.2
}
```

## Constraints
- Only modify rankings.py
- All print() English only
- Use existing DB session patterns
- No numpy/scipy - implement percentile calculation manually
