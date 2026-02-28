# Agent A Task: Trend Detection & Time-Series Analysis

## Goal
Detect which ad patterns are trending up/down. Predict what's working NOW vs what worked before.

## What to do

### 1. Trend detector script
`backend/scripts/detect_trends.py`
- Group ads by first_seen_at week
- For each week, compute: avg_score, hit_rate, dominant_hooks, dominant_CTAs
- Identify rising trends: patterns whose hit_rate is increasing week over week
- Identify declining trends: patterns whose hit_rate is decreasing
- Store in `backend/exports/trend_report.json`

### 2. Seasonal pattern analysis
`backend/scripts/seasonal_patterns.py`
- Analyze which genres/hooks/CTAs perform better in which month
- Compute month-over-month changes
- Export to `backend/exports/seasonal_patterns.json`

### 3. Ad longevity predictor
`backend/scripts/longevity_predictor.py`
- Based on creative features (hook, CTA, emotion, creative_type), predict expected longevity
- Simple rule-based model: which features correlate with long-running ads?
- Score each feature by its correlation with longevity_class
- Export feature importance to `backend/exports/longevity_factors.json`

### 4. Fresh vs stale analysis
`backend/scripts/fresh_vs_stale.py`
- Compare ads from last 7 days vs older ads
- Are newer ads using different patterns?
- What's changing in the market?
- Export to `backend/exports/fresh_vs_stale.json`

## Constraints
- English-only print, flag_modified, no rankings.py/frontend changes
