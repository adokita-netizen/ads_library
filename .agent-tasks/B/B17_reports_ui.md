# Agent B Task: Report Generation & Export UI

## Goal
Users can generate, view, and download comprehensive reports from the dashboard.

## What to do

### 1. Report generator page
Create `frontend/src/components/dashboard/ReportGenerator.tsx`:
- Select report type: Full Analysis, Genre Report, Competitor Report, Creative Report
- Filter options: genre, advertiser, date range
- Format: JSON or HTML
- "Generate Report" button
- Loading spinner during generation
- Download button when ready
- Data from POST /api/v1/rankings/reports/generate

### 2. Report viewer
Create `frontend/src/components/dashboard/ReportViewer.tsx`:
- If HTML format: render in iframe
- If JSON format: formatted display with collapsible sections
- Print button (window.print())
- Share button (copy link)

### 3. Report history
- List of previously generated reports
- Click to re-download
- Delete old reports
- Data from GET /api/v1/rankings/reports

### 4. Dashboard header toolbar
Create a consistent top toolbar with:
- Search input
- Export dropdown (CSV, JSON, Report)
- Crawl button
- Alerts bell icon
- Settings gear icon
- All on one clean toolbar bar

### 5. Navigation system
Implement proper tab/page navigation:
- Overview (main dashboard)
- Gallery (creative gallery)
- Analytics (trends, charts)
- LP Analysis
- Competitors
- Reports
- Bookmarks
- Settings

Use URL-based navigation or tab state management.

## Constraints
- Only frontend/src/, Tailwind, fetchApi, build must pass
