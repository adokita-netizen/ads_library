# Agent B Task: Bookmarks, Collections & Creative Download

## Goal
Users can save, organize, and download their favorite ad creatives.

## What to do

### 1. Bookmark functionality
- Add bookmark icon (heart/star) on every ad card
- Click to bookmark/unbookmark (POST/DELETE /api/v1/rankings/bookmarks)
- "Bookmarks" tab in main navigation showing saved ads
- Add optional note when bookmarking

### 2. Collections UI
Create `frontend/src/components/dashboard/CollectionsView.tsx`:
- Create new collection (name + description)
- Drag or "Add to collection" button on ad cards
- Collection page showing all ads in a collection
- Edit/delete collections

### 3. Creative download
- Download button on each ad card and in detail modal
- Click = download the creative image/video directly
- For images: triggers /api/v1/media/download/{ad_id}
- For videos: triggers /api/v1/media/download/{ad_id} (video file)
- Bulk download: select multiple -> "Download ZIP" button
  - POST /api/v1/media/bulk-download with selected ad_ids
  - Show progress indicator
  - Auto-trigger download when ZIP ready

### 4. Export buttons in toolbar
- "Export CSV" button -> GET /api/v1/rankings/export/csv (browser download)
- "Export JSON" button -> GET /api/v1/rankings/export/json
- "Export Report" button -> GET /api/v1/rankings/export/report
- Place in a dropdown menu or toolbar at top of dashboard

### 5. Alerts panel
Create `frontend/src/components/dashboard/AlertsPanel.tsx`:
- Show notifications: new high-score ads, trend changes
- Data from GET /api/v1/rankings/alerts
- Bell icon in header with badge count
- Dropdown panel showing recent alerts

## Constraints
- Only frontend/src/, Tailwind, fetchApi, build must pass
