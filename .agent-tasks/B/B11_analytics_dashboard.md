# Agent B Task: Advanced Analytics Dashboard

## Goal
Professional analytics views with charts, graphs, and insights.

## What to do

### 1. Trend charts page
Create `frontend/src/components/dashboard/TrendCharts.tsx`:
- Weekly ad volume chart (bar chart)
- Hit rate trend line (line chart)
- Hook type popularity over time (stacked area chart)
- Use the data from GET /api/v1/rankings/trends/weekly
- Responsive design, looks good on all screens

### 2. Market overview panel
Create `frontend/src/components/dashboard/MarketOverview.tsx`:
- Total ads, active ads, avg score, hit rate - big stat cards
- Genre distribution pie chart
- Creative type split (video vs image) donut chart
- Data from GET /api/v1/rankings/trends/market-overview

### 3. Advertiser leaderboard
Create `frontend/src/components/dashboard/AdvertiserLeaderboard.tsx`:
- Table of top advertisers: name, ad_count, hit_rate, avg_score
- Click to expand: show their ads
- Sort by different columns
- Data from GET /api/v1/rankings/advertisers

### 4. Winning formula display
Create `frontend/src/components/dashboard/WinningFormulas.tsx`:
- Show top winning combinations (hook + CTA + offer + emotion)
- Hit rate and example count for each
- Click to see example ads
- Visual cards with color coding

### 5. Integration
Add tabs or navigation in HitAdAnalysisView.tsx:
- "Overview" (existing), "Trends", "Advertisers", "Formulas"

## Constraints
- Only frontend/src/ files, Tailwind CSS, fetchApi pattern
- Build must pass: npx next build --no-lint
