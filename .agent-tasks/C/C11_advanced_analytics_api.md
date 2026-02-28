# Agent C Task: Advanced Analytics API

## Goal
API endpoints for deep analytics: advertiser analysis, trend data, competitor insights.

## What to do

### 1. Advertiser analytics endpoints
Add to rankings.py:

`GET /rankings/advertisers` - list all advertisers with stats
- Fields: name, ad_count, hit_count, hit_rate, avg_score, top_genre, active_ads
- Sort by: ad_count, hit_rate, avg_score
- Pagination support

`GET /rankings/advertiser/{name}/ads` - get all ads by specific advertiser
- Full ad details with resolved media URLs
- Sort by score desc

`GET /rankings/advertiser/{name}/profile` - advertiser profile
- Creative strategy summary: dominant hooks, CTAs, emotions
- Performance over time
- Genre distribution

### 2. Trend API endpoints
`GET /rankings/trends/weekly` - weekly trend data
- For each of last 12 weeks: ad_count, avg_score, hit_rate, top_hooks
- Used for trend charts on frontend

`GET /rankings/trends/rising-patterns` - patterns gaining popularity
- Hooks/CTAs/emotions whose usage or hit rate is increasing

`GET /rankings/trends/market-overview` - current market snapshot
- Total active ads, avg score, genre distribution, creative type split

### 3. Comparison API
`POST /rankings/compare` - compare 2-5 ads side by side
- Body: { ad_ids: [1, 2, 3] }
- Return: full details of each ad + comparative analysis
- Highlight differences in hooks, CTAs, scores

`GET /rankings/similar/{ad_id}` - find similar ads
- Based on same advertiser, same genre, or similar creative analysis
- Return top 10 similar ads

### 4. Report generation API
`POST /rankings/generate-report`
- Body: { genre?: str, advertiser?: str, date_range?: str }
- Generate comprehensive analysis report as JSON
- Include: summary stats, hit patterns, winning formulas, recommendations

## Constraints
- Only modify rankings.py, use existing helpers
