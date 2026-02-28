# Agent D Task: Smart Thumbnail & Visual Content Pipeline

## What to do

### 1. Smart placeholder generator
Create `backend/scripts/generate_smart_placeholders.py`:
- For ads missing thumbnails, generate informative SVG placeholders:
  - Include ad title text (truncated)
  - Genre-specific color scheme
  - Hit score badge if available
  - Advertiser name
  - Platform icon
- Store generated SVGs in media_cache/placeholders/
- Each placeholder: 400x300px, well-designed, brand-colored
- Print: "Generated X smart placeholders"

### 2. Thumbnail grid generator
Create `backend/scripts/generate_thumbnail_grid.py`:
- Create composite grid images for genres:
  - 3x3 grid of top 9 ads per genre
  - Each cell: 200x200px thumbnail
  - Genre label overlay
  - Hit rate badge
- Store in media_cache/grids/
- Use Pillow if available, else generate SVG grids
- Output: one grid per genre

### 3. Media proxy enhancement
Add to media.py:

`GET /media/placeholder/{ad_id}`
- Returns smart SVG placeholder for ads without thumbnails
- Include: title, genre color, score

`GET /media/grid/{genre}`
- Returns composite thumbnail grid for a genre
- Fallback to SVG grid if image grid not available

`GET /media/thumbnail-strip/{genre}`
- Returns horizontal strip of top 5 thumbnails for a genre
- For genre preview cards

### 4. Batch thumbnail validator
Create `backend/scripts/batch_validate_thumbnails.py`:
- Check every thumbnail file:
  - Is it a valid image? (check magic bytes)
  - Is it the right size? (not 1x1 or tiny)
  - Is it a placeholder? (mostly single color)
  - Is it corrupted? (truncated file)
- Categorize each: valid, placeholder, corrupted, missing
- Replace corrupted with smart placeholder
- Print detailed report

## Constraints
- English-only print
- Only modify media.py and scripts/
- No rankings.py or frontend changes
- If Pillow unavailable, use SVG fallback
