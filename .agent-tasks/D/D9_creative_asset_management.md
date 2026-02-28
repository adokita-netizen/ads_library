# Agent D Task: Creative Asset Management System

## Goal
Organize all creative assets with proper metadata, dedup, and cleanup.

## What to do

### 1. Asset inventory endpoint
Add to media.py:
`GET /media/inventory` - return complete media status:
- total_ads, cached_thumbnails, cached_images, cached_videos, cached_frames
- total_cache_size_mb
- missing_media_ads (list of ad_ids with no cached media at all)

### 2. Media cleanup script
`backend/scripts/media_cleanup.py`
- Remove orphaned files (files in media_cache/ that don't match any ad_id)
- Remove corrupt files (0 bytes, not valid image/video)
- Remove duplicates (same file hash)
- Print cleanup report

### 3. Batch media re-download
`backend/scripts/batch_redownload.py`
- For ads with failed media (no cached file + original URL 403):
  - Try re-crawling the ad (re-fetch from Meta API to get fresh URLs)
  - If fresh URL found, download and cache
- Print: recovered X, still missing Y

### 4. Creative similarity detection
`backend/scripts/detect_similar_creatives.py`
- Compare thumbnails using perceptual hash (dhash/phash)
- Group similar creatives together
- Store groups in ad_metadata["similar_ads"] = [list of ad_ids]
- This helps identify ad variations/A-B tests
- Use Pillow for image hashing

## Constraints
- English-only print, no rankings.py/frontend changes
- Use Pillow (PIL) for image operations
