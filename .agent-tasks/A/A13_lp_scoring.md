# Agent A Task: LP (Landing Page) Scoring System

## Goal
Score landing pages for conversion optimization. Which LP elements correlate with ad success?

## What to do

### 1. LP scoring script
`backend/scripts/score_landing_pages.py`
- For each ad with lp_data in ad_metadata (set by D12):
  - Compute LP score (0-100) based on:
    - Load speed: < 3s = 20pts, 3-5s = 10pts, > 5s = 0pts
    - Has CTA button: +15pts
    - Has form: +10pts
    - Has testimonials: +10pts
    - Has video: +10pts
    - Has price/offer: +10pts
    - Has countdown/urgency: +10pts
    - Has social proof: +10pts
    - Mobile responsive (page_size < 5MB): +5pts
  - Store in ad_metadata["lp_score"]

### 2. LP-Ad alignment analysis
`backend/scripts/lp_ad_alignment.py`
- Compare ad creative with its LP:
  - Does the LP headline match the ad headline?
  - Does the LP offer match the ad offer?
  - Color scheme consistency?
  - CTA consistency (ad CTA vs LP CTA)?
- Compute alignment_score (0-100)
- Store in ad_metadata["lp_alignment"]

### 3. LP benchmark report
`backend/scripts/lp_benchmark.py`
- Compare LP scores across genres
- Which genres have the best LPs?
- Correlation between LP score and ad hit rate
- Export to `backend/exports/lp_benchmark.json`

### 4. Conversion funnel analysis
`backend/scripts/funnel_analysis.py`
- Map the flow: Ad Creative -> LP -> Conversion Action
- For each ad: ad_score + lp_score + alignment_score = funnel_score
- Rank ads by funnel_score
- Export to `backend/exports/funnel_analysis.json`

## Constraints
- English-only print, flag_modified, no rankings.py/frontend changes
