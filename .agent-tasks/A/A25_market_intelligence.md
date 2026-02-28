# Agent A Task: Market Intelligence & Competitive Analysis Scripts

## What to do

### 1. Market share analysis
Create `backend/scripts/analyze_market_share.py`:
- Calculate advertiser market share by:
  - Ad count share per genre
  - Estimated spend share per genre
  - Hit ad share per genre
- Identify market leaders, challengers, niche players
- Output to `exports/market_share.json`
- Print market share table per genre

### 2. Trend velocity tracker
Create `backend/scripts/track_trend_velocity.py`:
- For each genre, calculate:
  - Ad growth rate (ads per week, trend direction)
  - Score trajectory (improving/declining/stable)
  - Spend trajectory
  - New entrant rate (new advertisers per week)
- Classify each genre: 急成長, 安定, 衰退, 新興
- Output to `exports/trend_velocity.json`
- Print genre status dashboard

### 3. Creative fatigue detector
Create `backend/scripts/detect_creative_fatigue.py`:
- For each creative pattern (hook+cta combo):
  - Track usage over time
  - Detect if performance is declining (fatigue signal)
  - Flag overused patterns (>10 ads with same structure)
- Output to `exports/creative_fatigue.json`
- Print: "X patterns showing fatigue, Y patterns still fresh"

### 4. Opportunity finder
Create `backend/scripts/find_opportunities.py`:
- Find underserved niches:
  - Genres with high demand (many ads) but low quality (low avg score)
  - Hook types rarely used in high-performing genres
  - CTA types with high hit rate but low adoption
  - Advertisers with improving trajectory
- Output to `exports/opportunities.json`
- Print top 10 opportunities with reasoning

## Constraints
- English-only print, flag_modified
- No rankings.py/frontend/media.py changes
- Run from backend/ directory
