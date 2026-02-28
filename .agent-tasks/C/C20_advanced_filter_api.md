# Agent C Task: Advanced Filter & Failure Analysis API

## What to do

### 1. Enhanced pro-ranking filter support
Update the pro-ranking endpoint (if C18 done) or add new:

`GET /rankings/pro-ranking` additional query params:
- video_format: video|image|carousel|all
- destination_type: 公式サイト|記事LP|ECサイト|LINE追加|アプリDL|SNS
- destination_domain: partial domain match (e.g., "line.me")
- view_count_min, view_count_max: filter by total views
- like_count_min, like_count_max: filter by likes
- spend_min_jpy, spend_max_jpy: filter by estimated spend
- date_from, date_to: filter by first_seen_at
- exclude_advertisers: comma-separated advertiser names to exclude
- exclude_domains: comma-separated domains to exclude

### 2. Success vs Failure analysis endpoint
`GET /rankings/success-failure-analysis`
- Query: genre (optional), platform (optional)
- Split ads into success (hit_score >= 60) and failure (hit_score < 40)
- For each group compute:
  - count, percentage
  - avg_views, avg_spend, avg_likes, avg_score
  - top_hooks: { hook_type: count, hit_rate }
  - top_ctas: { cta_type: count, hit_rate }
  - top_offers: { offer_type: count }
  - top_emotions: { emotion: count }
  - common_destination_types: { type: count }
  - representative_ads: top 5 by score (with thumbnails)
- Also return:
  - key_differences: list of elements that differ most between success/failure
  - reuse_points: actionable insights (e.g., "質問型フックのヒット率は80%。積極的に使用を推奨")

Response:
```json
{
  "success": {
    "count": 45,
    "percentage": 35.2,
    "avg_score": 72.5,
    "avg_views": 15000,
    "patterns": { "hooks": {...}, "ctas": {...} },
    "representative_ads": [...]
  },
  "failure": {
    "count": 50,
    "percentage": 39.1,
    "avg_score": 25.3,
    "avg_views": 2000,
    "patterns": { "hooks": {...}, "ctas": {...} },
    "representative_ads": [...]
  },
  "key_differences": [
    { "element": "hook_type", "success_top": "question", "failure_top": "none", "impact": "high" }
  ],
  "reuse_points": [
    "質問型フックのヒット率は80%。悩み訴求と組み合わせると効果的",
    "LINE追加CTAは記事LPとの組み合わせで最高パフォーマンス"
  ]
}
```

### 3. Element breakdown endpoint
`GET /rankings/element-breakdown`
- Query: genre (optional), element_type (hook|cta|offer|emotion|all)
- Returns per-element statistics:
```json
{
  "hooks": [
    { "type": "question", "label": "質問型", "count": 25, "hit_rate": 0.80, "avg_score": 68, "vs_overall": "+15%" },
    { "type": "benefit", "label": "ベネフィット提示", "count": 18, "hit_rate": 0.72, "avg_score": 65, "vs_overall": "+7%" }
  ],
  "ctas": [...],
  "offers": [...],
  "emotions": [...]
}
```

### 4. Destination type statistics
`GET /rankings/destination-stats`
- Returns ad count and performance by destination type:
```json
{
  "destination_types": [
    { "type": "記事LP", "count": 45, "hit_rate": 0.62, "avg_score": 58 },
    { "type": "公式サイト", "count": 30, "hit_rate": 0.45, "avg_score": 48 },
    { "type": "ECサイト", "count": 15, "hit_rate": 0.53, "avg_score": 52 },
    { "type": "LINE追加", "count": 25, "hit_rate": 0.72, "avg_score": 65 }
  ],
  "top_domains": [
    { "domain": "line.me", "count": 25, "hit_rate": 0.72 },
    { "domain": "example-clinic.jp", "count": 8, "hit_rate": 0.88 }
  ]
}
```

## Constraints
- Only modify rankings.py
- Use existing helpers
- All print() must be English only
