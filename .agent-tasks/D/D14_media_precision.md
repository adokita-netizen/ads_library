# Agent D Task: Media Precision - Improve Cache Rate & Quality

## Current Issues
- Thumbnail cache rate: only 63% (158/248)
- 90 ads with no cached thumbnail
- Some cached files may be corrupt (HTML error pages saved as .jpg)
- New ads from crawl may have expired CDN URLs already

## What to do

### 1. Aggressive media recovery
`backend/scripts/aggressive_media_recovery.py`
- For all 90 uncached ads:
  - Phase 1: Try thumbnail_url again (some may have been temp failures)
  - Phase 2: Try image_url as thumbnail fallback
  - Phase 3: Try snapshot_url og:image (parse HTML for meta tags)
  - Phase 4: Use snapshot_url direct (Facebook ad library page screenshot via Playwright)
- Track success/failure per phase
- Target: >85% cache rate

### 2. Media quality validator
`backend/scripts/validate_media_files.py`
- Check ALL cached files:
  - Is it a valid image? (check magic bytes: FF D8 FF for JPEG, 89 50 4E 47 for PNG)
  - Is the file >5KB? (tiny files are likely error pages)
  - Is it an HTML page saved as .jpg? (check first bytes for "<html" or "<!DOCTYPE")
  - Is the image >100x100 pixels? (too small = probably icon/placeholder)
- Delete invalid files, reset s3_key to NULL
- Print: validated X, deleted Y invalid, cache rate now Z%

### 3. Thumbnail quality improvement
`backend/scripts/improve_thumbnails.py`
- For cached thumbnails:
  - Resize to consistent dimensions (640x360 or 400x400)
  - Convert PNG to JPEG for consistency
  - Optimize JPEG quality (85%)
- This ensures consistent display in the dashboard
- Use Pillow (PIL) library

### 4. Update media.py for better fallback
In media.py endpoints, improve fallback logic:
- If requested thumbnail not found, try returning image instead
- If image not found, return a proper placeholder image (create a simple SVG/PNG)
- Add `GET /media/status/{ad_id}` endpoint:
  ```json
  {
    "ad_id": 123,
    "thumbnail": {"cached": true, "size_kb": 45, "valid": true},
    "image": {"cached": false},
    "video": {"cached": false},
    "overall": "partial"
  }
  ```

## Constraints
- English-only print, no rankings.py/frontend changes
- Use Pillow for image operations (skip if not installed)
- Only modify media.py and scripts/
