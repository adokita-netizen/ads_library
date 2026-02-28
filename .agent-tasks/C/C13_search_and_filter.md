# Agent C Task: Advanced Search, Filter & Sort API

## Goal
Powerful search and filtering so users can find exactly the ads they want.

## What to do

### 1. Advanced search endpoint
`GET /rankings/search` (if not already added in C10)

Full search with all filters:
- `q`: full-text search (title, description, advertiser_name) - use SQL LIKE
- `genre`: filter by category/genre
- `creative_type`: image/video/carousel
- `hook_type`: from creative_analysis
- `cta_type`: from creative_analysis
- `offer_type`: from creative_analysis
- `emotion`: from creative_analysis
- `min_score`, `max_score`: hit_score range
- `min_longevity_days`: minimum days running
- `is_hit`: boolean - only hit ads
- `is_active`: boolean - currently active ads
- `has_video`: boolean - only video ads
- `advertiser`: filter by advertiser name
- `platform`: facebook/instagram
- `date_from`, `date_to`: created_at range
- `sort`: score_desc, score_asc, date_desc, date_asc, longevity_desc
- `page`, `per_page`: pagination (default 20, max 100)

Return format: { total, page, per_page, ads: [...] }
Each ad includes resolved thumbnail/image/video URLs.

### 2. Autocomplete endpoint
`GET /rankings/autocomplete`
- `q`: partial text
- `field`: advertiser/genre/keyword
- Return top 10 matches
- Used for search suggestions in frontend

### 3. Saved search endpoint
`POST /rankings/saved-searches` - save a search query
`GET /rankings/saved-searches` - list saved searches
- Store in backend/data/saved_searches.json

## Constraints
- Only modify rankings.py
