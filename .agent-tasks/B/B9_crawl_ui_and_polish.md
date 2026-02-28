# Agent B Task: Crawl UI & Dashboard Polish

## Background
We're adding fresh crawl capability. The dashboard needs a way to trigger crawls and display fresh ads. Also overall UI polish needed.

## What to do

### 1. Crawl trigger panel
Add a "New Crawl" section to the dashboard:
- Input field for search keyword
- "Crawl Now" button that calls POST /api/v1/rankings/quick-crawl
- Show loading spinner during crawl
- Show result: "X new ads found"
- Recent crawl history list (from GET /api/v1/rankings/crawl-status)

### 2. Fresh ads section
Add a "Latest Ads" tab/section:
- Calls GET /api/v1/rankings/fresh-ads
- Shows ads crawled in last 7 days
- Same card format as existing ad list but with "NEW" badge
- Auto-refresh after crawl completes

### 3. Overall UI polish
- Ensure all images use the proxy URL pattern (/api/v1/media/thumbnail/{ad_id})
- Add loading skeletons for all data-heavy sections
- Ensure the creative gallery view from B8 works correctly
- Fix any TypeScript errors or build warnings

### 4. Build verification
Run `npx next build --no-lint` and fix any errors.

## Constraints
- INSTRUCTIONS.md conflict rules apply
- Only modify files in frontend/src/
- Do NOT modify backend files
- Use existing fetchApi pattern from lib/api.ts
- Tailwind CSS only (no inline styles)
