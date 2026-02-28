# Agent A Task: Advanced Data Enrichment & Quality Boost

## What to do

### 1. Emotion analysis script
Create `backend/scripts/analyze_emotions.py`:
- Analyze ad titles/descriptions for emotional triggers
- Categories: 不安 (anxiety), 希望 (hope), 緊急性 (urgency), 好奇心 (curiosity), 信頼 (trust), 恐怖 (fear)
- Score each ad 0-100 for dominant emotion
- Store in ad_metadata.emotion_analysis = {"dominant": "anxiety", "scores": {...}}
- Use keyword matching (no external AI needed)

### 2. Seasonal pattern analysis
Create `backend/scripts/analyze_seasonal_patterns.py`:
- Group ads by month/season
- Find genre×season correlations
- Identify seasonal peaks for each genre
- Output to `exports/seasonal_patterns.json`
- Format: {"skincare": {"peak_months": [6,7,8], "low_months": [12,1], "seasonal_index": {...}}}

### 3. Advertiser clustering script
Create `backend/scripts/cluster_advertisers.py`:
- Group advertisers by behavior patterns:
  - Heavy hitters (many ads, high spend)
  - Niche specialists (few genres, high hit rate)
  - Spray and pray (many genres, low hit rate)
  - Rising stars (recent, improving scores)
- Store cluster assignment in exports/advertiser_clusters.json
- Print summary table

### 4. Data completeness fixer
Create `backend/scripts/fix_data_gaps.py`:
- Find all ads with missing key fields
- For missing creative_analysis: generate from title keywords
- For missing ranking_metrics: compute from available data
- For missing fine_genre: classify from title/advertiser
- Print before/after fill rates
- Use flag_modified for all DB updates

## Constraints
- English-only print, flag_modified
- No rankings.py/frontend/media.py changes
- Run from backend/ directory
