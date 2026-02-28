# Agent C Task: Precision Improvements - API Accuracy & Filtering

## Current Issues
- API may return non-Japanese ads mixed in
- Search results quality needs improvement
- Hit/non-hit boundary is arbitrary
- Genre stats unreliable when 72 ads uncategorized

## What to do

### 1. Improve hit-ads response quality
Update relevant endpoints in rankings.py:
- Filter out ads where ad_metadata["language"] != "ja" (if set, otherwise include)
- Filter out ads where ad_metadata["is_duplicate"] == true
- Add "data_quality" field to each ad response:
  ```json
  {
    "data_quality": {
      "has_thumbnail": true,
      "has_creative_analysis": true,
      "has_category": false,
      "has_lp": true,
      "completeness_pct": 75
    }
  }
  ```

### 2. Dynamic hit threshold
Update hit-ads logic:
- Instead of fixed threshold, use percentile-based:
  - Top 20% = "big_hit"
  - Top 20-40% = "hit"
  - Rest = "normal"
- Add endpoint: `GET /rankings/score-distribution`
  - Return: min, max, mean, median, p25, p50, p75, p90
  - Histogram buckets (0-10, 10-20, ..., 90-100)
  - Current hit threshold values

### 3. Search precision improvements
Update search endpoint:
- Boost exact matches in title over partial matches
- Boost Japanese ads over non-Japanese
- Add relevance scoring: title_match > description_match > advertiser_match
- Return matches with relevance_score field
- Exclude duplicates by default (add include_duplicates=false param)

### 4. Genre accuracy
When category is NULL, attempt to infer from:
- ad_metadata keywords
- advertiser_name patterns
- title keywords
Add to all endpoints that group by genre:
- "(uncategorized)" group for NULL category ads
- Don't mix uncategorized into other genres

### 5. API response validation
Add a self-check endpoint:
`GET /rankings/health-check`
- Test all major endpoints (hit-ads, fresh-ads, search, etc.)
- Return: { endpoint: status, response_time_ms, record_count }
- Flag any endpoint returning errors

## Constraints
- Only modify rankings.py
