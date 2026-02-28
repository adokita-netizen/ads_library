# Agent A Task: Advertiser Profiling & Competitor Analysis

## Goal
Build advertiser-level analytics. Who are the top advertisers? What patterns do winners use?

## What to do

### 1. Advertiser profiler script
`backend/scripts/profile_advertisers.py`
- Group ads by advertiser_name
- For each advertiser compute:
  - total_ads, hit_ads, hit_rate
  - avg_score, max_score
  - dominant_genre, dominant_hook, dominant_cta
  - creative_types distribution (video vs image)
  - avg_longevity (how long their ads run)
  - active_ads_count (currently running)
- Store in ad_metadata["advertiser_profile"] for each ad
- Export to `backend/exports/advertiser_profiles.json`

### 2. Competitor matrix
`backend/scripts/build_competitor_matrix.py`
- For each genre, rank advertisers by: ad count, hit rate, avg score
- Identify "dominant players" per genre (top 3)
- Build cross-genre overlap matrix
- Export to `backend/exports/competitor_matrix.json`

### 3. Ad pattern evolution
`backend/scripts/analyze_ad_evolution.py`
- For advertisers with 3+ ads, track how their creative strategy changes over time
- Identify: did they switch hooks? Change CTAs? Test different emotions?
- Export insights to `backend/exports/ad_evolution.json`

### 4. Winning formula report
`backend/scripts/winning_formula.py`
- Combine all analysis: what EXACT combination (hook + CTA + offer + emotion + creative_type) produces the highest hit rate?
- Rank top 20 formulas
- For each formula, list example ads
- Export to `backend/exports/winning_formulas.json`

## Constraints
- English-only print, flag_modified for metadata, no rankings.py/frontend changes
