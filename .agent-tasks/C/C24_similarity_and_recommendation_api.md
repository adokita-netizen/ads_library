# Agent C Task: Similarity, Recommendation & Calendar API

## What to do

### 1. Similar ads endpoint
`GET /rankings/similar-ads/{ad_id}`
- Query: limit (default 10)
- Find ads similar to the given ad based on:
  - Same genre (weight 3)
  - Same hook_type (weight 2)
  - Same cta_type (weight 2)
  - Same advertiser (weight 1)
  - Similar score (within 15 points, weight 1)
  - Similar title keywords (weight 2)
- Return scored list:
```json
{
  "source_ad": {"id": 1, "title": "..."},
  "similar_ads": [
    {"id": 5, "title": "...", "similarity_score": 0.85, "reasons": ["Same genre", "Same hook type"]}
  ]
}
```

### 2. Recommendation engine endpoint
`GET /rankings/recommendations`
- Query: based_on (bookmarks|recent|top_performing), limit (default 10)
- If bookmarks: find ads similar to bookmarked ads
- If recent: find trending ads in user's preferred genres
- If top_performing: find highest scoring undiscovered ads
```json
{
  "recommendations": [
    {"id": 5, "title": "...", "reason": "ブックマークした広告と同じジャンル", "score": 72}
  ]
}
```

### 3. Calendar data endpoint
`GET /rankings/calendar`
- Query: year, month
- Returns daily ad counts:
```json
{
  "year": 2026, "month": 2,
  "days": [
    {"day": 1, "total_ads": 5, "hit_ads": 2, "new_ads": 3, "top_ad_id": 45},
    {"day": 2, "total_ads": 8, "hit_ads": 3, "new_ads": 5, "top_ad_id": 67}
  ],
  "monthly_total": 308,
  "monthly_hits": 84
}
```

### 4. Ad timeline endpoint
`GET /rankings/timeline`
- Query: genre (optional), days (default 90), group_by (advertiser|genre)
- Returns timeline data for visualization:
```json
{
  "timeline": [
    {
      "id": 1, "title": "...", "advertiser": "...", "genre": "skincare",
      "first_seen": "2025-12-01", "last_seen": "2026-02-28",
      "duration_days": 89, "is_active": true, "score": 72
    }
  ]
}
```

### 5. Duplicate detection endpoint
`GET /rankings/duplicates`
- Query: threshold (default 0.7), limit (default 50)
- Find near-duplicate ads by title similarity
- Use character trigram Jaccard similarity (implement in Python)
```json
{
  "clusters": [
    {
      "cluster_id": 1, "similarity": 0.92,
      "ads": [{"id": 1, "title": "..."}, {"id": 5, "title": "..."}],
      "same_advertiser": true
    }
  ],
  "total_duplicates": 23
}
```

## Constraints
- Only modify rankings.py
- All print() English only
- No external ML/NLP libraries
