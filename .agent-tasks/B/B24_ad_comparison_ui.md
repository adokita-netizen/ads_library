# Agent B Task: Ad Comparison Tool & Advertiser Profile UI

## What to do

### 1. Ad Comparison Tool
Create `frontend/src/components/dashboard/AdComparisonTool.tsx`:
- Side-by-side comparison of 2-5 ads
- Select ads from search or recent list
- Comparison grid showing:
  - Thumbnail side by side
  - メトリクス比較 (score, views, spend, longevity)
  - クリエイティブ要素比較 (hook type, CTA, format)
  - パーセンタイル順位 (percentile rank bars)
- Radar chart (pure CSS/SVG) comparing key metrics
- "勝者" badge on the best-performing ad
- インサイト section with AI-generated insights
- Fetch from `POST /api/v1/rankings/compare-ads`
- Fallback to mock data if API unavailable

### 2. Advertiser Profile View
Create `frontend/src/components/dashboard/AdvertiserProfile.tsx`:
- Full-page advertiser deep-dive
- Header: advertiser name, total ads, hit rate, total spend
- ジャンル分布 chart (bar/donut)
- 月別推移 timeline chart (CSS bar chart)
- クリエイティブスタイル: preferred hooks, CTAs, avg duration
- トップ広告 list with scores and thumbnails
- Fetch from `GET /api/v1/rankings/advertiser/{name}/profile`
- Mock data fallback

### 3. Integration
- Add "比較" view type to page.tsx
- Add "比較ツール" to Sidebar (comparison icon)
- Make advertiser names clickable in ProRankingTable → opens AdvertiserProfile
- Add "比較に追加" button on ad cards

### 4. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS, fetchApi
- Build MUST pass
- Japanese UI text
- Mock data with TODO for unavailable APIs
