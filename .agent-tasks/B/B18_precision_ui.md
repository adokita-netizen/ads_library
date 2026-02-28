# Agent B Task: UI Precision - Better Display & Data Quality Indicators

## Current Issues
- Users can't tell which ads have complete data vs incomplete
- Non-Japanese ads may show up confusingly
- Score visualization doesn't show confidence/reliability
- No way to see data quality at a glance

## What to do

### 1. Data quality indicators on ad cards
In all ad card components:
- Add small quality badge (green/yellow/red circle):
  - Green: has thumbnail + analysis + category + LP (complete)
  - Yellow: missing 1-2 fields (partial)
  - Red: missing 3+ fields (incomplete)
- Tooltip on hover showing what's missing
- Based on data_quality field in API response (if available) or computed client-side

### 2. Score confidence display
When showing hit scores:
- If ad has < 7 days of data, show score with "provisional" label
- If ad has no spend data, add footnote "estimated"
- Color coding: high confidence scores are bold, low confidence are muted/gray
- In AdDetailModal, show "Score breakdown" with confidence level per factor

### 3. Language filter
- Add "Japanese only" toggle/checkbox in filter panel
- Default: ON (show only Japanese ads)
- When off: show all ads with language badge (JP/EN/etc.)
- Based on ad_metadata.language field or title character detection

### 4. Duplicate indicator
- If ad is flagged as duplicate (ad_metadata.is_duplicate):
  - Show "Duplicate" badge in muted color
  - Option to hide duplicates (default: hidden)
  - "Show duplicates" toggle in filter panel

### 5. Empty state improvements
- When no ads match filters: show helpful message with suggestions
- When media fails to load: show proper placeholder with "Image unavailable" text
- When API returns error: show specific error message + retry button

### 6. Build verification
Run `npx next build --no-lint` and fix ALL errors.

## Constraints
- Only frontend/src/ files, Tailwind, fetchApi, build must pass
