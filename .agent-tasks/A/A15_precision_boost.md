# Agent A Task: Precision Boost - Data Completeness & Scoring Accuracy

## Current Issues
- 72 ads have NULL category (all newly crawled)
- 71 ads missing creative_analysis
- Hit scoring is basic rule-based, needs calibration
- No validation of scoring accuracy

## What to do

### 1. Auto-categorize uncategorized ads
`backend/scripts/auto_categorize.py`
- For 72 ads with NULL category:
  - Use title + description keywords to classify:
    - diet/weight: ダイエット,痩せ,体重,減量,脂肪
    - beauty/skincare: 美容,スキンケア,化粧,美白,肌
    - health: 健康,サプリ,栄養,ビタミン
    - fitness: フィットネス,ジム,筋トレ,プロテイン,ヨガ
    - hair: 育毛,脱毛,髪,ヘアケア
    - other: everything else
  - Map to AdCategoryEnum values
  - Commit updates
  - Print classification distribution

### 2. Run creative analysis on all unanalyzed ads
`backend/scripts/analyze_new_ads.py`
- Import analyze_ad from analyze_creative_elements.py
- Process all 71 ads missing creative_analysis
- Also re-validate the existing 177 analyses (check for "none" values that could be better classified)
- Print: analyzed X new, validated Y existing, fixed Z

### 3. Hit score calibration
`backend/scripts/calibrate_hit_scores.py`
- Analyze current score distribution
- Check: are scores too clustered? Too spread? Too many hits? Too few?
- Recalibrate scoring weights if needed:
  - longevity_score: should long-running really get 40 points max?
  - spend_score: are estimates reliable?
  - What about impression count weight?
- Compute score percentile ranks (top 10%, 25%, 50%)
- Update ProductRanking with calibrated scores
- Store calibration metadata in exports/score_calibration.json

### 4. Japanese text quality check
`backend/scripts/japanese_text_quality.py`
- Check all titles/descriptions for encoding issues
- Detect ads with non-Japanese text (English-only ads from global crawl)
- Flag non-Japanese ads in ad_metadata["language"] = "en" etc.
- Check for truncated/incomplete text
- Print quality report

### 5. Dedup accuracy check
`backend/scripts/check_duplicates.py`
- Find ads with identical or near-identical titles
- Find ads with same advertiser + similar title (Levenshtein or simple ratio)
- Flag duplicates in ad_metadata["is_duplicate"] = true
- Print: found X potential duplicate groups

## Constraints
- English-only print, flag_modified, no rankings.py/frontend/media.py changes
