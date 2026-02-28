# Agent B Task: Real-Time Dashboard & Live KPI Cards

## What to do

### 1. Dashboard KPI Header
Create `frontend/src/components/dashboard/DashboardKPI.tsx`:
- Horizontal card row at top of ProRankingView
- 6 KPI cards in a grid:
  - 総広告数 (total ads) - large number + "件"
  - 新着7日 (new in 7 days) - with green up arrow if > 0
  - ヒット広告 (hit ads) - count + percentage badge
  - アクティブ広告 (active ads) - count
  - 平均スコア (avg score) - with color indicator (red/yellow/green)
  - 推定消化額 (total spend) - ¥ formatted with 万/億 suffix
- Fetch from `/api/v1/rankings/dashboard-kpi`
- Auto-refresh every 60 seconds
- Skeleton loading state
- Compact design, max height 80px per card

### 2. Live Activity Feed
Create `frontend/src/components/dashboard/ActivityFeed.tsx`:
- Small sidebar panel or bottom strip
- Shows recent changes:
  - "新規広告検出: [title]"
  - "スコア変動: [advertiser] +15pt"
  - "ヒットライン突破: [title]"
- Auto-refresh every 30 seconds
- Max 10 items, newest first
- Click item to open ad detail
- Fetch from `/api/v1/rankings/alerts?limit=10`

### 3. Integration
- Add DashboardKPI to top of ProRankingView (above the search/filter bar)
- Add ActivityFeed as collapsible right panel or bottom bar in ProRankingView
- Ensure responsive layout

### 4. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS, fetchApi
- Build MUST pass
- Japanese UI text
