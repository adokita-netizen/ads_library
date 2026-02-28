# Agent A Task: Advanced Export & Automated Reporting

## What to do

### 1. PowerPoint-style data export
Create `backend/scripts/export_presentation_data.py`:
- Generate structured JSON for presentation slides:
  - Slide 1: Executive summary (total ads, hit rate, top genre)
  - Slide 2: Genre breakdown table
  - Slide 3: Top 10 ads with scores
  - Slide 4: Creative pattern insights
  - Slide 5: Market trends
  - Slide 6: Recommendations
- Output to `exports/presentation_data.json`
- Each slide has: title, subtitle, content_type, data
- Print slide outline

### 2. Competitive report generator
Create `backend/scripts/generate_competitive_report.py`:
- For each top-20 advertiser:
  - Ad count, hit rate, avg score
  - Top genre, preferred creative style
  - Trend direction (growing/stable/declining)
  - Estimated monthly spend
- Generate markdown competitive report
- Output to `exports/competitive_report.md`
- Print key findings

### 3. Weekly digest generator
Create `backend/scripts/generate_weekly_digest.py`:
- Auto-generate weekly email-style digest:
  - This week's top 5 new ads
  - Score movers (biggest increases/decreases)
  - New advertisers entering the market
  - Genre of the week (highest growth)
  - Creative tip of the week (from winning patterns)
- Output to `exports/weekly_digest_YYYY-MM-DD.json`
- Include both Japanese and English content

### 4. Custom query builder
Create `backend/scripts/custom_query.py`:
- Command-line tool for ad-hoc queries:
  - python scripts/custom_query.py --genre skincare --min-score 70 --format csv
  - python scripts/custom_query.py --advertiser "CompanyX" --format json
  - python scripts/custom_query.py --hook question --cta urgency --top 20
- Output to stdout or file
- Support CSV and JSON output

## Constraints
- English-only print, flag_modified
- No rankings.py/frontend/media.py changes
