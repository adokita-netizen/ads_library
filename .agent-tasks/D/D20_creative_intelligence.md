# Agent D Task: Creative Intelligence & Visual Analysis

## What to do

### 1. Color analysis script
Create `backend/scripts/analyze_thumbnail_colors.py`:
- For each cached thumbnail in media_cache/thumbnails/:
  - Read image using Pillow (PIL)
  - Extract dominant colors (top 5)
  - Classify color scheme: warm/cool/neutral/vibrant/muted
  - Detect if image has text overlay (high contrast regions)
- Store in ad_metadata.color_analysis = {"dominant_colors": ["#FF5722", "#FFF"], "scheme": "warm", "has_text": true}
- Use flag_modified
- If Pillow not available, generate mock data from file size heuristics
- Print summary: X thumbnails analyzed, color scheme distribution

### 2. Creative format classifier
Create `backend/scripts/classify_creative_format.py`:
- For each ad, classify creative format:
  - Video types: 実写, アニメ, スライドショー, UGC風, インタビュー
  - Image types: 商品写真, ビフォーアフター, テキスト主体, イラスト, コラージュ
- Use keyword matching in title + description + existing metadata
- Store in ad_metadata.creative_format = {"type": "video", "subtype": "ugc_style", "confidence": 0.8}
- Print distribution table

### 3. Media comparison endpoint
Add to media.py:

`GET /media/compare/{ad_id_1}/{ad_id_2}`
- Returns visual comparison data:
```json
{
  "ad1": {"id": 1, "thumbnail": "/media/thumbnail/1", "format": "video", "colors": ["#FF5722"]},
  "ad2": {"id": 2, "thumbnail": "/media/thumbnail/2", "format": "image", "colors": ["#2196F3"]},
  "visual_similarity": 0.35,
  "same_format": false,
  "same_color_scheme": false
}
```

`GET /media/gallery`
- Query: genre (optional), format (optional), sort_by (quality|recency), page, page_size
- Returns paginated media gallery:
```json
{
  "items": [
    {"ad_id": 1, "thumbnail_url": "/media/thumbnail/1", "title": "...", "genre": "skincare", "quality_score": 85}
  ],
  "total": 308,
  "page": 1
}
```

### 4. Creative asset export
Create `backend/scripts/export_creative_assets.py`:
- Export all creative analysis data to a single JSON
- Include: format classification, color analysis, video metadata, thumbnail quality
- Output to `exports/creative_intelligence_report.json`
- Print summary statistics

## Constraints
- English-only print, flag_modified
- Only modify media.py and scripts/
- No rankings.py or frontend changes
- If Pillow not available, use mock/heuristic data
