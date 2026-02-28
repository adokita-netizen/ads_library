# Agent B Task: Production-Ready UI & Download Features

## Goal
The dashboard must look professional, all creatives must display, and users can download/export data.

## What to do

### 1. Export/Download buttons
Add to the dashboard:
- "CSV Export" button -> calls GET /api/v1/rankings/export/csv and triggers browser download
- "JSON Export" button -> calls GET /api/v1/rankings/export/json
- "Report Export" button -> calls GET /api/v1/rankings/export/report
- Place these in a toolbar/action bar at the top of the dashboard

### 2. Creative media display fix (CRITICAL)
In ALL components that display ads:
- Always use proxy URLs: /api/v1/media/thumbnail/{ad_id} for images
- For video ads: use <video> tag with /api/v1/media/video/{ad_id} as src
- Fallback chain: video -> image -> thumbnail -> placeholder
- Add download button on each ad card (calls /api/v1/media/download/{ad_id})
- Bulk download: checkbox select multiple ads -> "Download Selected" button

### 3. Search & filter panel
Add a search/filter section:
- Search input (full-text across title, description, advertiser)
- Filter dropdowns: genre, creative_type, hook_type, emotion
- Score range slider (0-100)
- Date range picker (crawled date)
- Calls GET /api/v1/rankings/search with all params
- Results display in the same card/gallery format

### 4. Polish for production
- All loading states must have skeletons (no blank screens)
- Error states must show retry buttons
- Mobile responsive (works on phone screens)
- No console errors in browser
- Proper page title and favicon

### 5. Build verification
Run `npx next build --no-lint` and fix ALL errors.

## Constraints
- INSTRUCTIONS.md conflict rules apply
- Only modify frontend/src/ files
- Tailwind CSS only
- Use fetchApi from lib/api.ts
- For file downloads, use window.open() or create blob URL
