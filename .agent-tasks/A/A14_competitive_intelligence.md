# Agent A Task: Competitive Intelligence System

## Goal
Track competitors, detect their strategies, and provide actionable competitive insights.

## What to do

### 1. Competitor tracking
`backend/scripts/track_competitors.py`
- Identify top advertisers (by ad count and score)
- For each competitor:
  - Ad frequency (how often they launch new ads)
  - Creative strategy shifts (hooks/CTAs changing over time)
  - Genre coverage (which markets they're in)
  - Estimated spend level (based on ad longevity * reach estimates)
  - Win rate (% of their ads that are hits)
- Export to `backend/exports/competitor_intelligence.json`

### 2. Market gap analysis
`backend/scripts/market_gaps.py`
- Identify under-served genres (few ads but high hit rate)
- Identify over-saturated genres (many ads, low hit rate)
- Find hook/CTA combinations NOT being used but likely effective
- Export to `backend/exports/market_gaps.json`

### 3. First-mover detection
`backend/scripts/detect_first_movers.py`
- Detect when a new creative pattern appears for the first time
- Track if early adopters of new patterns get higher hit rates
- Identify emerging patterns to jump on
- Export to `backend/exports/first_movers.json`

### 4. Competitor alert config
`backend/config/competitor_watchlist.json`
- List of advertiser names to track closely
- When new ads from these advertisers appear, flag them
- Store alerts in ad_metadata for the new ads

## Constraints
- English-only print, flag_modified, no rankings.py/frontend changes
