# Agent A Task: Full Data Pipeline Execution + Quality Report

## Goal
Run ALL analysis scripts on the full 308 ad dataset to ensure every ad has complete metadata.
Then generate a comprehensive quality report.

## What to do

### 1. Run pipeline scripts in order
Execute these scripts IN ORDER (each depends on previous):

```bash
# Phase 1: Core classification
python scripts/classify_fine_genre.py
python scripts/extract_product_names.py
python scripts/auto_categorize.py

# Phase 2: Creative analysis
python scripts/analyze_creative_elements.py  (if exists)
python scripts/reanalyze_all_ads.py

# Phase 3: Metrics
python scripts/estimate_initial_metrics.py
python scripts/aggregate_metrics.py
python scripts/snapshot_metrics.py

# Phase 4: Advanced analysis
python scripts/extract_keywords.py
python scripts/power_words.py
python scripts/analyze_title_structure.py

# Phase 5: Scoring
python scripts/score_new_ads.py (if exists)
python scripts/calibrate_hit_scores.py (if exists)

# Phase 6: Scenario
python scripts/extract_scenario_templates.py
python scripts/build_scenario_database.py

# Phase 7: Reports
python scripts/data_health_report.py
python scripts/export_ads_csv.py --format both
```

If any script doesn't exist or fails, skip it and continue.

### 2. Fix any gaps found
After running data_health_report.py:
- If any NULL categories remain → fix them
- If any ads missing fine_genre → re-classify
- If any ads missing creative_analysis → re-analyze
- If any ads missing ranking_metrics → re-aggregate

### 3. Create comprehensive status report
Print final status showing:
- Total ads, ads with each key field populated
- Fine genre distribution
- Scenario archetype distribution
- Hit score distribution
- Data quality grade

## Constraints
- English-only print, flag_modified
- No rankings.py/frontend/media.py changes
- Run from backend/ directory
