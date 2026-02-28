# Agent B Task: LP Analysis Dashboard

## Goal
Show LP analysis in the dashboard. Users can see LP screenshots, scores, and optimization tips.

## What to do

### 1. LP viewer in ad detail
Add to AdDetailModal:
- LP screenshot preview (from /api/v1/media/lp-screenshot/{ad_id})
- Click to view full screenshot in lightbox
- LP score gauge (0-100)
- LP elements checklist: form, CTA, testimonials, video, price, countdown
- "Open LP" button (external link)

### 2. LP analysis panel
Create `frontend/src/components/dashboard/LPAnalysisPanel.tsx`:
- LP score distribution chart
- Genre benchmark comparison
- LP elements that correlate with high hit rate
- LP alignment score (ad <-> LP consistency)
- Data from GET /api/v1/rankings/lp-analysis/{ad_id}
- Data from GET /api/v1/rankings/lp-benchmark

### 3. Funnel view
Create `frontend/src/components/dashboard/FunnelView.tsx`:
- Visual funnel: Ad Creative -> LP -> Conversion
- For each selected ad, show:
  - Ad score (left)
  - LP score (middle)
  - Funnel score (right, combined)
  - Arrow flow between stages
- Highlight weak points in the funnel

### 4. LP comparison
Create `frontend/src/components/dashboard/LPComparison.tsx`:
- Select 2-3 ads to compare their LPs
- Side by side LP screenshots
- Score comparison bars
- Element checklist comparison

### 5. Integration
Add "LP Analysis" tab to main dashboard navigation

## Constraints
- Only frontend/src/, Tailwind, fetchApi, build must pass
