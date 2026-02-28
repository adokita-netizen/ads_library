# Agent C Task: Report Generation API

## Goal
Generate comprehensive analysis reports (JSON/HTML) that users can download and share.

## What to do

### 1. Full report generation
Add to rankings.py:

`POST /rankings/reports/generate`
Body:
```json
{
  "type": "full|genre|competitor|creative",
  "genre": "optional genre filter",
  "advertiser": "optional advertiser filter",
  "date_from": "2024-01-01",
  "date_to": "2024-12-31",
  "format": "json|html"
}
```

Report includes:
- Executive summary (total ads, hit rate, top patterns)
- Genre analysis (breakdown by genre)
- Creative analysis (hook/CTA/emotion distributions, winning combos)
- Advertiser analysis (top performers, strategies)
- Trend analysis (what's rising/falling)
- LP analysis (scores, benchmarks)
- Recommendations (what to do next)

### 2. Report templates
For HTML format, generate a clean HTML page with:
- CSS styling (inline, no external deps)
- Charts rendered as SVG or CSS bars
- Tables with data
- Print-friendly layout

### 3. Report history
`GET /rankings/reports` - list generated reports
- Store report metadata in backend/data/reports/
- Each report saved as {report_id}.json or {report_id}.html

`GET /rankings/reports/{report_id}` - download specific report

### 4. Scheduled report
`GET /rankings/reports/weekly-digest`
- Auto-generated weekly summary
- New ads this week, hit rate changes, new patterns detected
- Can be called by scheduler to generate + send via webhook

## Constraints
- Only modify rankings.py
- For HTML: generate inline (no template engine needed, just f-strings)
- Store reports in backend/data/reports/ (create dir if needed)
