# Agent D Task: Full Media Pipeline + Missing Media Recovery

## Goal
Ensure ALL 308 ads have cached thumbnails and images. Run full media pipeline.

## What to do

### 1. Run media pipeline scripts
Execute in order:

```bash
# Phase 1: Validate existing media
python scripts/validate_media_files.py

# Phase 2: Auto-cache missing media
python scripts/auto_media_cache.py

# Phase 3: Aggressive recovery for still-missing
python scripts/aggressive_media_recovery.py

# Phase 4: Health check
python scripts/media_health_check.py

# Phase 5: Collect reference media for scenarios
python scripts/collect_reference_media.py

# Phase 6: Generate scenario thumbnails
python scripts/generate_scenario_thumbnails.py
```

If any script doesn't exist or fails, skip and continue.

### 2. Report final media status
After running all scripts, print:
- Total ads: 308
- Thumbnails cached: X / 308 (X%)
- Images cached: X / 308 (X%)
- Videos cached: X / 308 (X%)
- Reference media genres: X
- Scenario thumbnails: X

### 3. Fix media.py if needed
Check that all media endpoints work correctly:
- GET /media/thumbnail/{ad_id} → returns image or SVG placeholder
- GET /media/image/{ad_id} → returns image or SVG placeholder
- GET /media/video/{ad_id} → returns video or 404
- GET /media/reference/{genre_en} → returns reference list
- GET /media/scenario-thumbnail/{archetype} → returns SVG

Fix any issues found.

### 4. Create media inventory report
Create `backend/scripts/media_inventory_report.py`:
- Print table showing per-genre media coverage
- Show total cache size (MB)
- List ads with no media at all
- Show cache hit rate prediction for frontend

## Constraints
- English-only print, no rankings.py/frontend changes
- Only modify media.py and scripts/
