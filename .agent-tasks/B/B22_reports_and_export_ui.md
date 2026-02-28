# Agent B Task: Reports Dashboard & Export UI

## What to do

### 1. Reports Dashboard
Create `frontend/src/components/dashboard/ReportsView.tsx`:

#### Summary Report Card
- Total ads count, hit ads count, hit rate %
- Total estimated spend (¥ formatted)
- Average hit score gauge
- Top performing genre
- Date range of data

#### Genre Performance Report
- Table showing each genre: ad count, hit rate, avg score, top archetype, avg spend
- Sort by any column
- Click genre → filter to that genre's ads

#### Advertiser Report
- Top 20 advertisers by ad count
- Each row: advertiser name, ad count, hit rate, avg score, total estimated spend
- Click to expand and see their ads

#### Creative Pattern Report
- Winning patterns summary (top 5 combos)
- Hook type performance chart
- CTA type performance chart
- Best performing creative type (video vs image)

#### Export Panel
- "CSV エクスポート" button → GET /api/v1/rankings/export/csv → download
- "JSON エクスポート" button → GET /api/v1/rankings/export/json → download
- "レポート生成" button → generates formatted HTML report
- Date range selector for export

### 2. Notification/Alert Panel
Create `frontend/src/components/dashboard/AlertsPanel.tsx`:
- Recent alerts list (mock data for now)
- Alert types: 新規ヒット広告, スコア変動, 競合アラート, クロール完了
- Each alert: icon, message, timestamp, action button
- Mark as read/unread
- "すべて既読" button

### 3. Collections/Bookmark View
Create `frontend/src/components/dashboard/CollectionsView.tsx`:
- Saved search collections from /api/v1/rankings/search-collections
- Each collection: name, filter summary, ad count, created date
- Click to apply filters
- Create new collection button
- Delete collection (with confirmation)
- Also show bookmarked ads (from /api/v1/rankings/bookmarks or mock)

### 4. Integration
- Add "レポート" tab to HitAdAnalysisView section navigation
- Wire up "レポート" to ReportsView
- Wire up AlertsPanel to "お知らせ" sidebar item
- Wire up CollectionsView to "マイリスト" sidebar item

### 5. Build verification
npx next build --no-lint

## Constraints
- Only frontend/src/, Tailwind CSS, fetchApi
- Build MUST pass
- Japanese UI text
- Mock data with TODO for unavailable APIs
