# Agent D Task: Video Analysis Pipeline & Media Intelligence

## What to do

### 1. Video metadata extractor
Create `backend/scripts/extract_video_metadata.py`:
- For each ad with video_url in DB:
  - Extract duration from URL patterns or metadata
  - Classify format: vertical (9:16), horizontal (16:9), square (1:1)
  - Detect if it's a slideshow vs real video (from file size/duration ratio)
- Store in ad_metadata.video_analysis = {"duration_sec": 30, "format": "vertical", "type": "real_video"}
- Use flag_modified
- Print English only

### 2. Thumbnail quality scorer
Create `backend/scripts/score_thumbnails.py`:
- For each cached thumbnail in media_cache/thumbnails/:
  - Check image dimensions
  - Check file size (too small = likely placeholder)
  - Check if image is mostly single color (placeholder detection)
  - Score 0-100 for quality
- Store in ad_metadata.thumbnail_quality = {"score": 85, "dimensions": "1200x628", "issues": []}
- Output summary to `exports/thumbnail_quality_report.json`

### 3. Media endpoint enhancements
In media.py, add or fix:

`GET /media/stats`
- Returns aggregate media statistics:
```json
{
  "total_ads": 308,
  "thumbnails": {"cached": 187, "valid": 175, "placeholder": 12},
  "images": {"cached": 130, "valid": 116, "invalid": 14},
  "videos": {"with_url": 250, "cached": 88},
  "cache_size_mb": 456,
  "quality_score_avg": 72
}
```

`GET /media/ad/{ad_id}/all`
- Returns all media for a specific ad:
```json
{
  "ad_id": 1,
  "thumbnail": {"url": "/media/thumbnail/1", "cached": true, "quality": 85},
  "image": {"url": "/media/image/1", "cached": true, "quality": 90},
  "video": {"url": "...", "cached": false, "duration_sec": 30},
  "lp_screenshot": {"url": "/media/lp-screenshot/1", "available": true}
}
```

### 4. Batch media revalidation
Create `backend/scripts/revalidate_media.py`:
- Re-check all cached media files
- Remove corrupted/broken files
- Update cache manifest
- Print summary of actions taken

## Constraints
- English-only print
- Only modify media.py and scripts/
- No rankings.py or frontend changes
- Use flag_modified for DB updates
