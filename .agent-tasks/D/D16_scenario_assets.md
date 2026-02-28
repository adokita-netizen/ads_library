# Agent D Task: Scenario Asset Support

## Concept
Support the ad scenario builder with reference creative assets and template images.

## What to do

### 1. Reference ad media collector
`backend/scripts/collect_reference_media.py`

For scenario templates, collect reference creative media:
- Find top 5 ads per genre (highest hit_score)
- Ensure all have cached thumbnails and images
- Create `media_cache/reference/{genre_en}/` directory structure
- Copy best creatives into reference folders
- Generate a reference_media.json index:
```json
{
  "medical_weight_loss": {
    "reference_ads": [
      {
        "ad_id": 123,
        "thumbnail": "/api/v1/media/thumbnail/123",
        "image": "/api/v1/media/image/123",
        "video": "/api/v1/media/video/123",
        "score": 85,
        "title": "...",
        "archetype": "before_after"
      }
    ]
  }
}
```

### 2. Reference media endpoint
Add to media.py:
`GET /media/reference/{genre_en}`
- Returns list of reference creative assets for a genre
- Include thumbnail URLs, scores, titles
- Used by scenario builder to show example creatives

### 3. Scenario export endpoint
Add to media.py:
`POST /media/scenario-export`
- Body: { "scenario": {...}, "format": "text" }
- Generates formatted text/HTML of the scenario
- Returns downloadable file
- Formats:
  - "text": Plain text with clear section headers
  - "html": Formatted HTML with color-coded sections
  - "brief": Creative brief format (concise, action-oriented)

### 4. Scenario thumbnail generator
`backend/scripts/generate_scenario_thumbnails.py`
- For each scenario archetype, generate a representative SVG thumbnail
- Simple graphics showing the scenario flow (Hook→Problem→Solution→Proof→CTA)
- Store in `media_cache/scenario_thumbnails/`
- Used as visual icons in the scenario builder UI

## Constraints
- English-only print, no rankings.py/frontend changes
- Only modify media.py and scripts/ and config/
