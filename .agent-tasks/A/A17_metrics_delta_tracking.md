# Agent A Task: Metrics Delta Tracking (再生増加数)

## Concept
Professional ad tools track view counts OVER TIME and compute daily deltas.
Example: If an ad had 2,100,000 views yesterday and 2,300,000 today, the 再生増加数 = 200,000.

This requires:
1. Periodic snapshots of metrics (views, spend, likes)
2. Delta computation between snapshots
3. Storage of historical data

## What to do

### 1. Metrics snapshot script
`backend/scripts/snapshot_metrics.py`

For each ad, take a snapshot of current metrics:
- Store in ad_metadata["metrics_history"]:
```json
[
  {"date": "2026-02-28", "views": 10997, "spend_jpy": 43988, "likes": 52},
  {"date": "2026-02-27", "views": 9500, "spend_jpy": 38000, "likes": 45},
  ...
]
```
- Keep last 30 snapshots max (trim oldest)
- Compute deltas:
  - view_increase = latest_views - previous_views
  - spend_increase = latest_spend - previous_spend
  - like_increase = latest_likes - previous_likes
- Store current deltas in ad_metadata["current_deltas"]:
```json
{
  "view_increase_daily": 1497,
  "spend_increase_daily_jpy": 5988,
  "like_increase_daily": 7,
  "view_increase_weekly": 8500,
  "spend_increase_weekly_jpy": 34000,
  "snapshot_date": "2026-02-28"
}
```

### KEY FORMULA: 予想消化額 = 再生増加数 × CPM
- CPM = Cost Per Mille (cost per 1000 impressions)
- Default CPM estimate: ¥800 for Japanese market (can be overridden per genre)
- Example: view_increase=200,000, CPM=¥2.4 → spend_increase = 200,000 × 2.4 = ¥480,000
- Or using CPM: spend = (view_increase / 1000) × CPM_jpy

### 2. Initial metrics estimation
`backend/scripts/estimate_initial_metrics.py`

For ads where we don't have real-time tracking yet:
- Estimate total_views from: impressions, reach, view_count, or estimated_daily_impressions * days_running
- Estimate total_spend_jpy from: spend field, or estimated_cpm_jpy * impressions / 1000
- Estimate likes from: like_count field or impressions * 0.005 (0.5% engagement rate estimate)
- Store estimates in ad_metadata["estimated_metrics"]
- Flag as estimated: ad_metadata["metrics_source"] = "estimated"

### 3. Re-crawl for metric updates
`backend/scripts/recrawl_metrics.py`

For existing ads in DB:
- Re-crawl using external_id to get updated metrics from Meta API
- Compare new metrics vs stored metrics
- Compute deltas
- Update metrics_history with new snapshot
- Print: updated X ads, avg view increase Y, avg spend increase Z

### 4. Metrics aggregation
`backend/scripts/aggregate_metrics.py`

Compute aggregate metrics for rankings:
- For each ad:
  - total_views (best available: real or estimated)
  - view_increase (daily delta, or 0 if only one snapshot)
  - total_spend_jpy
  - spend_increase_jpy
  - like_increase
- Store in ad_metadata["ranking_metrics"]:
```json
{
  "total_views": 10997,
  "view_increase": 1497,
  "total_spend_jpy": 43988,
  "spend_increase_jpy": 5988,
  "like_increase": 7,
  "period": "daily"
}
```

This data is what the pro ranking table uses for its columns.

## Constraints
- English-only print, flag_modified
- No rankings.py/frontend/media.py changes
- Metrics history capped at 30 entries per ad
