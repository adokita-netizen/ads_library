# Agent D Task: Media API Enhancement & Asset Pipeline

## What to do

### 1. Media search endpoint
Add to media.py:

`GET /media/search`
- Query: q (text search in titles), genre, format (video|image), quality_min (0-100), page, page_size
- Search across all ads with media
- Return media-rich results:
```json
{
  "items": [
    {
      "ad_id": 1, "title": "...", "genre": "skincare",
      "thumbnail_url": "/media/thumbnail/1",
      "image_url": "/media/image/1",
      "has_video": true,
      "quality_score": 85,
      "hit_score": 72
    }
  ],
  "total": 150
}
```

### 2. Media batch endpoint
`POST /media/batch`
- Body: { "ad_ids": [1,2,3,4,5], "include": ["thumbnail", "image", "video_url"] }
- Returns all media URLs for given ads in one request (reduce API calls)

### 3. Asset package endpoint
`POST /media/asset-package`
- Body: { "ad_ids": [1,2,3], "format": "zip_manifest" }
- Returns manifest of all downloadable assets for given ads
- Include thumbnails, images, LP screenshots if available

### 4. Media timeline endpoint
`GET /media/timeline`
- Query: days (default 30)
- Returns daily media cache statistics:
```json
{
  "timeline": [
    {"date": "2026-02-28", "new_thumbnails": 5, "new_images": 3, "total_cached": 450}
  ]
}
```

### 5. Create media analysis aggregator
Create `backend/scripts/aggregate_media_analysis.py`:
- Combine all media analysis results:
  - Color analysis from thumbnails
  - Video metadata
  - Quality scores
  - Format classifications
- Create comprehensive `exports/media_analysis_report.json`
- Print summary dashboard

## Constraints
- English-only print
- Only modify media.py and scripts/
- No rankings.py or frontend changes
