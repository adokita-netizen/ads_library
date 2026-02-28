# Agent B Task: Heatmap & Advanced Analytics Visualization

## What to do

### 1. Performance Heatmap
Create `frontend/src/components/dashboard/PerformanceHeatmap.tsx`:
- Genre × Time matrix heatmap (pure CSS grid)
- Rows: genres (top 15), Columns: weeks (last 12 weeks)
- Cell color: green (high performance) to red (low performance) based on avg hit_score
- Hover tooltip: "スキンケア - Week 5: 平均スコア 65, 広告数 12, ヒット率 58%"
- Legend showing color scale
- Click cell → filter ProRankingTable to that genre+week
- Fetch from `/api/v1/rankings/trends/weekly` or mock data

### 2. Funnel Visualization
Create `frontend/src/components/dashboard/FunnelChart.tsx`:
- Ad funnel: 全広告 → アクティブ → ヒットライン超え → メガヒット
- Horizontal funnel bars with counts and percentages
- Drop-off rate between each stage
- Pure CSS/SVG (no chart library)
- Click funnel stage → filter to that segment

### 3. Scatter Plot (Score vs Views)
Create `frontend/src/components/dashboard/ScatterPlot.tsx`:
- Pure SVG scatter plot
- X-axis: hit_score, Y-axis: estimated views
- Dots colored by genre
- Hover shows ad info tooltip
- Quadrant labels: "高スコア・高再生" (top-right), "低スコア・高再生" (top-left), etc.
- Click dot → open ad detail
- Responsive sizing

### 4. Distribution Charts
Create `frontend/src/components/dashboard/DistributionChart.tsx`:
- Reusable histogram/bar distribution component
- Props: data, bins, label, color
- Use for: score distribution, spend distribution, view count distribution
- Pure SVG, responsive
- Show mean/median lines

### 5. Analytics Dashboard Page
Create `frontend/src/components/dashboard/AnalyticsDashboard.tsx`:
- Combine all visualizations:
  - Top row: FunnelChart + KPI summary
  - Middle: PerformanceHeatmap (full width)
  - Bottom row: ScatterPlot + DistributionChart (score)
- Period selector: 7日/30日/90日/全期間
- Genre filter dropdown
- Fetch from `/api/v1/rankings/analytics/overview` or mock

### 6. Integration
- Wire "analysis" view in page.tsx to AnalyticsDashboard
- Add as tab in HitAdAnalysisView

### 7. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS
- Pure SVG/CSS for all charts (NO chart libraries)
- Build MUST pass
- Japanese UI text
