# Agent A Task: A/B Testing & Statistical Comparison Framework

## What to do

### 1. Create AB comparison script
Create `backend/scripts/ab_compare_ads.py`:
- Compare two groups of ads statistically
- Input: group_a filter (genre, archetype, etc), group_b filter
- Output: statistical comparison (t-test, effect size, confidence intervals)
- Metrics compared: hit_score, views, spend, engagement_rate
- Print results in English

### 2. Create benchmark computation script
Create `backend/scripts/compute_benchmarks.py`:
- For each genre: compute median, p25, p75, p90 for key metrics
- Metrics: hit_score, view_count, like_count, comment_count, spend, longevity_days
- Store results in `exports/genre_benchmarks.json`
- Format:
```json
{
  "skincare": {
    "hit_score": {"median": 45, "p25": 30, "p75": 62, "p90": 78},
    "view_count": {"median": 15000, "p25": 5000, "p75": 45000, "p90": 120000}
  }
}
```

### 3. Create automated weekly report script
Create `backend/scripts/generate_weekly_report.py`:
- Generate markdown report summarizing last 7 days
- Sections: New ads, Top performers, Score changes, Genre trends
- Output to `exports/weekly_report_YYYY-MM-DD.md`
- Include tables and statistics
- Cron-compatible (no interactive input)

### 4. Create cross-genre analysis script
Create `backend/scripts/cross_genre_analysis.py`:
- Find patterns that work across genres
- Identify universal winning hooks, CTAs, offers
- Compare genre-specific vs universal patterns
- Output to `exports/cross_genre_patterns.json`

## Constraints
- English-only print, flag_modified for DB updates
- No rankings.py/frontend/media.py changes
- Run from backend/ directory
