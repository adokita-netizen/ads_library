# Agent A Task: Production Data Quality & Export System

## Goal
All ad data must be complete, accurate, and exportable. No NULL scores, no missing analysis.

## What to do

### 1. Comprehensive data fixer
`backend/scripts/production_data_fix.py`

Run ALL fixes in one script:
- Fill ALL NULL hit_scores (recompute with scoring v2)
- Fill ALL NULL longevity_class
- Fill ALL NULL last_seen_at
- Fill ALL NULL first_seen_at (set to created_at)
- Run creative_analysis on ALL ads missing it
- Verify ad_metadata is valid JSON for all ads
- Set media_status based on actual cached files in media_cache/
- Print: "X/Y ads fully complete (100% data quality)"

### 2. Enhanced CSV/JSON export
Update `backend/scripts/export_ads_csv.py` to include:
- ALL creative_analysis fields (hook_type, cta_type, offer_type, emotion, etc.)
- hit_score, longevity_class, creative_type
- media_status, has_cached_thumbnail, has_cached_video
- destination_url, advertiser_name
- Output both CSV and JSON formats
- Add command-line args: --format csv|json|both --output-dir path

### 3. Auto-scoring on new ads
`backend/scripts/score_new_ads.py`
- Find ads where hit_score is NULL or 0
- Compute hit_score using the v2 formula
- Run creative_analysis if missing
- Compute longevity_class if missing
- This script should be idempotent (safe to run multiple times)

### 4. Final data health report
Update data_health_report.py to also check:
- Media cache coverage (thumbnails, images, videos)
- Creative analysis coverage
- Score distribution histogram
- Target: Grade A (>90% fill rate)

## Constraints
- INSTRUCTIONS.md conflict rules apply
- English-only print statements
- Do NOT modify rankings.py, frontend/, or media.py
- Use flag_modified for ad_metadata
