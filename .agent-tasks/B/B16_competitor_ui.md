# Agent B Task: Competitor Intelligence UI

## Goal
Competitive analysis dashboard. Track competitors, see their strategies, find market gaps.

## What to do

### 1. Competitor leaderboard
Create `frontend/src/components/dashboard/CompetitorDashboard.tsx`:
- Table: advertiser name, ad count, hit rate, avg score, top genre, trend
- Sort by any column
- Click to expand: show their recent ads
- Star icon to add to watchlist
- Data from GET /api/v1/rankings/competitors

### 2. Competitor deep dive
Create `frontend/src/components/dashboard/CompetitorProfile.tsx`:
- Full page for a single competitor:
  - Stats overview cards
  - Creative strategy timeline (how their hooks/CTAs changed)
  - Genre distribution pie chart
  - All their ads in gallery view
  - Hit rate trend over time
- Data from GET /api/v1/rankings/competitor/{name}

### 3. Market gaps view
Create `frontend/src/components/dashboard/MarketGaps.tsx`:
- Opportunity matrix: under-served genres vs over-saturated
- Unused but effective combinations
- "Blue ocean" recommendations
- Data from GET /api/v1/rankings/market-gaps

### 4. Competitive alerts
In the alerts panel (from B13):
- "New ad from [watched competitor]" notifications
- "Competitor changed strategy" alerts
- "[Competitor] entered new genre" alerts

### 5. Integration
Add "Competitors" tab to main navigation

## Constraints
- Only frontend/src/, Tailwind, fetchApi, build must pass
