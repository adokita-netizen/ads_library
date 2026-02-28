# Agent A Task: Duplicate & Similar Ad Detection

## What to do

### 1. Title similarity detector
Create `backend/scripts/detect_similar_titles.py`:
- Compare all ad titles pairwise using character n-gram similarity
- Jaccard similarity on character trigrams (no external libraries)
- Threshold: similarity > 0.6 = "similar", > 0.85 = "near duplicate"
- Group similar ads into clusters
- Store in `exports/similar_ad_clusters.json`:
```json
[
  {
    "cluster_id": 1,
    "similarity": 0.92,
    "ads": [{"id": 1, "title": "..."}, {"id": 5, "title": "..."}],
    "same_advertiser": true
  }
]
```
- Update ad_metadata.similar_ads = [5, 12, 34] for each ad
- Print summary: X clusters found, Y ads are near-duplicates

### 2. Advertiser variant detector
Create `backend/scripts/detect_advertiser_variants.py`:
- Find ads from same advertiser that are variants of each other
- Group by advertiser → compare titles within group
- Identify A/B test pairs (very similar titles, different hooks/CTAs)
- Store in `exports/ab_test_pairs.json`
- Print: "Found X likely A/B test pairs across Y advertisers"

### 3. Creative pattern deduplication
Create `backend/scripts/dedupe_creative_patterns.py`:
- Find ads with identical creative structure (same hook_type + cta_type + genre)
- Group by creative fingerprint
- Rank each group by performance
- Store in `exports/creative_pattern_groups.json`
- Print pattern frequency table

### 4. Update ad metadata with similarity data
Create `backend/scripts/update_similarity_metadata.py`:
- Read all cluster files from exports/
- Update each ad's ad_metadata with:
  - similar_ad_ids: list of similar ad IDs
  - duplicate_cluster_id: cluster ID if near-duplicate
  - ab_test_group: group ID if likely A/B variant
  - creative_fingerprint: hash of creative structure
- Use flag_modified

## Constraints
- English-only print, flag_modified
- No external NLP libraries
- No rankings.py/frontend/media.py changes
