# Agent B Task: Calendar View & Ad Timeline Visualization

## What to do

### 1. Calendar View
Create `frontend/src/components/dashboard/CalendarView.tsx`:
- Monthly calendar grid showing ad activity
- Each day cell shows:
  - Number of new ads detected
  - Color intensity based on volume (heat map style)
  - Small dots for hit ads (gold) vs regular (gray)
- Click day → show list of ads from that day
- Month navigation (prev/next)
- Legend: 新規広告数, ヒット広告, 通常広告
- Fetch from `/api/v1/rankings/pro-ranking` with date filters
- Mock data fallback with realistic dates

### 2. Ad Timeline
Create `frontend/src/components/dashboard/AdTimeline.tsx`:
- Horizontal timeline showing ad lifecycle
- Each ad = horizontal bar from first_seen to last_seen (or today if still active)
- Color coded by genre
- Hover shows: title, score, views, advertiser
- Filter by genre, advertiser, score range
- Zoom controls: week/month/quarter view
- "アクティブ広告のみ" toggle
- Fetch top 50 ads from `/api/v1/rankings/pro-ranking?sort_by=score&page_size=50`

### 3. Trend Sparklines
Create `frontend/src/components/dashboard/TrendSparkline.tsx`:
- Reusable mini chart component (60px x 20px)
- Pure SVG, no chart library
- Props: data (number[]), color, showDot (latest point)
- Use in ProRankingTable cells for inline trend visualization

### 4. Integration
- Add "calendar" view type to page.tsx
- Add "カレンダー" to Sidebar with calendar icon
- Add AdTimeline as a tab option in HitAdAnalysisView
- Use TrendSparkline in ProRankingTable score column

### 5. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS, fetchApi
- Pure SVG for charts (no chart libraries)
- Build MUST pass
- Japanese UI text
