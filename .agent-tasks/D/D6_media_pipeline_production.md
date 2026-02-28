# Agent D Task: Production-Ready Media Pipeline

## Goal
Make ALL creatives (images, videos, thumbnails) reliably viewable and downloadable. No broken images. No 403s.

## What to do

### 1. Auto-cache on crawl hook
`backend/scripts/auto_media_cache.py`

After any crawl completes, automatically:
- Download thumbnail_url -> media_cache/thumbnails/{ad_id}.jpg
- Download image_url -> media_cache/images/{ad_id}.jpg
- For video ads: download video_url -> media_cache/videos/{ad_id}.mp4 (if size < 50MB)
- Update thumbnail_s3_key, image_s3_key in DB
- Skip already-cached ads

### 2. Video proxy endpoint
Add to media.py:

`GET /media/video/{ad_id}` - serve cached video files
`GET /media/creative/{ad_id}` - smart endpoint that returns the best available media:
  - If video exists: return video
  - If image exists: return image
  - If thumbnail exists: return thumbnail
  - Else: return 404

### 3. Bulk download endpoint
Add to media.py:

`GET /media/download/{ad_id}` - force-download (Content-Disposition: attachment) the creative
`POST /media/bulk-download` - takes list of ad_ids, creates a ZIP file, returns download URL

### 4. Media health check
`backend/scripts/media_health_check.py`
- Scan all ads, report: cached vs uncached for thumbnails/images/videos
- Validate cached files (not corrupt, not too small)
- Delete invalid cached files and reset s3_key to NULL
- Print summary report

## Constraints
- INSTRUCTIONS.md conflict rules apply
- English-only print statements
- Only modify media.py and scripts/ (your territory)
- Do NOT modify rankings.py or frontend/
- Use streaming for large video files (FileResponse with media_type)
- ZIP creation should use zipfile module, store in media_cache/downloads/
