# Agent A Task: Analyze Fresh Crawled Data

## Background
Agent D is crawling fresh ads right now. Once new ads arrive, we need to ensure data quality and run analysis on them.

## What to do

### 1. Create a comprehensive re-analysis script
`backend/scripts/reanalyze_all_ads.py`

This script should:
1. Query all ads from DB
2. For ads missing creative_analysis in ad_metadata: run the analyze_creative_elements logic
3. For ads missing longevity_class: compute and set it
4. For ads missing last_seen_at: set to created_at or now()
5. Recompute hit_score for ALL ads using latest scoring v2 formula
6. Print summary of how many ads were updated

### 2. Update hit_pattern_report
Rerun compute_hit_patterns logic on the full dataset (old + new ads).
Export updated report to `backend/exports/hit_pattern_report.json`.

### 3. Data health check on expanded dataset
Run data_health_report logic on full dataset.
Print the new grade and fill rates.

## Constraints
- INSTRUCTIONS.md conflict rules apply
- English-only print statements
- Do NOT modify rankings.py, frontend/, or media.py
- Use flag_modified pattern for ad_metadata updates
