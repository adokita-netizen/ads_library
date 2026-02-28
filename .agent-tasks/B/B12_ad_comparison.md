# Agent B Task: Ad Comparison & Side-by-Side View

## Goal
Users should compare ads side by side to understand what makes winners different.

## What to do

### 1. Comparison view
Create `frontend/src/components/dashboard/AdComparisonView.tsx`:
- Select 2-4 ads from any list (checkbox)
- Click "Compare" button
- Side-by-side display:
  - Creative preview (image/video) for each
  - Score comparison bar
  - Hook type, CTA, offer, emotion badges
  - Key metrics: longevity, impressions, score
  - Highlight differences in green/red
- Data from POST /api/v1/rankings/compare

### 2. Similar ads panel
Create `frontend/src/components/dashboard/SimilarAdsPanel.tsx`:
- When viewing an ad detail, show "Similar Ads" section
- Grid of similar ads with thumbnails
- Click to navigate
- Data from GET /api/v1/rankings/similar/{ad_id}

### 3. A/B test detector
In AdComparisonView:
- If 2+ ads are from same advertiser with similar title
- Show "Possible A/B Test" badge
- Compare performance metrics to show which variant won

### 4. Integration
- Add compare checkbox to ad cards in gallery and list views
- Add "Compare Selected" button in toolbar
- Add SimilarAdsPanel to AdDetailModal

## Constraints
- Only frontend/src/ files, Tailwind CSS
- Build must pass
