# Agent C: ステータス

## 2026-03-09 C117 / C118 Completion Update
- Tasks:
  - `C117_meta_data_contract_and_freshness_api.md`
  - `C118_meta_token_runtime_and_health_contract.md`
- 変更:
  - `backend/app/api/endpoints/rankings.py`
    - Meta freshness / provenance 共通 helper を追加
    - `metric_source / creative_source / lp_source`
    - `metric_status / creative_status / lp_status`
    - `freshness_status / last_meta_success_at / meta_quality_state / meta_recovery_reason`
    を detail / rankings list / `search-simple` で共通返却
    - `get_meta_freshness(ad_id)` を追加し、単一広告の freshness contract を取得可能にした
    - `_db_session_scope` フックを追加し、契約テスト差し替えに対応
  - `backend/app/api/endpoints/settings.py`
    - 既存の token health contract が C118 要件を満たすことを再検証
- 検証:
  - `backend: python -m py_compile app/api/endpoints/rankings.py`
  - `backend: python -m pytest tests/test_c117_meta_data_contract.py tests/test_meta_token_info_contract.py -q` => `6 passed`

## 2026-03-09 Runtime Recovery Follow-up
- Scope:
  - `search-simple` の `hit_score` を scalar に固定
  - `metric_status / creative_status / lp_status` で source=`missing` を `missing` 扱いに修正
  - stale backend process を再起動してローカル API を修正版コードへ切替
- Live verify:
  - `GET /api/v1/rankings/search-simple?q=&page=1&page_size=3`
  - `GET /api/v1/ads/11/media`
  - `GET /api/v1/ads/40/media`
  - `GET /api/v1/media/thumbnail/11`
  - `POST /api/v1/rankings/quick-crawl`
- Result:
  - search-simple の tuple leak 解消
  - thumbnail / image creative / video creative / LP info / quick-crawl をローカルで確認

## 2026-03-03 Immediate Execution (C50)
- Priority: `P0`
- Start now: `.agent-tasks/C/C50_media_retry_dispatch_and_topic_api.md`
- Scope:
  - Finalize and test retry-dispatch behavior for `needs_media_retry`
  - Expose topic fields in list/detail APIs
  - Add topic filter for ranking/search endpoints
- Test:
  - Contract tests for pending + retry mixed cases
  - Regression check for quick-crawl -> extraction -> reflected listing
- Handoff to B:
  - Stable API contract examples + error codes

## Current Tasks
- [x] C: Media URL backfill — **DONE**
- [x] C2: Hit score accuracy improvement (multi-signal model) — **DONE**
- [x] C2-fix: Hit score threshold fix (v2: longevity-focused) — **DONE**
- [x] C3: Analysis API pipeline (5 endpoints) — **DONE**
- [x] C4: API response integration + deprecation fix — **DONE**
- [x] C5: Trend analysis & genre comparison API (4 endpoints) — **DONE**
- [x] C6: Data quality & LP health API — **DONE**
- [x] C7: Thumbnail/image URL resolution fix — **DONE**
- [x] C8: Hit pattern analysis API (4 endpoints) — **DONE**
- [x] C9: Realtime crawl API (4 endpoints) — **DONE**
- [x] C10: Production API & download support — **DONE**
- [x] C11: Advanced Analytics API (9 endpoints) — **DONE**
- [x] C12: Alerts & Bookmarks API (11 endpoints) — **DONE**
- [x] C13: Advanced Search, Filter & Sort API (3 endpoints + search enhancement) — **DONE**
- [x] C14: AI-Powered Analysis API (10 endpoints) — **DONE**
- [x] C15: Async Task Status API (2 endpoints) — **DONE**
- [x] C16: Report Generation API (4 endpoints + HTML reports) — **DONE**
- [x] C17: Precision improvements - API accuracy & filtering — **DONE**
- [x] C18: Pro Ranking API (hit-line + pro-ranking) — **DONE**
- [x] C19: Scenario Generation API (8 endpoints) — **DONE**
- [x] C20: Advanced Filter & Failure Analysis API (3 endpoints) — **DONE**
- [x] C21: Reports & Alerts API (already implemented) — **DONE**
- [x] C22: Benchmark & Comparison API (already implemented) — **DONE**
- [x] C23: User Preferences & Notification API (already implemented) — **DONE**
- [x] C24: Similarity, Calendar, Timeline & Duplicates API (5 endpoints) — **DONE**
- [x] C25: Webhook, Bulk Ops & Integration API (8 endpoints) — **DONE**
- [x] C26: Creative Intelligence & Template API (5 endpoints) — **DONE**
- [x] C27: Analytics Dashboard & AI Insights API (4 endpoints) — **DONE**
- [x] C28: Realtime Updates & Advanced Search API (4 endpoints) — **DONE**
- [x] C35: Rankings Query Performance Optimization — **DONE**
- [x] C36: Ads API Security & Validation Hardening — **DONE**
- [x] C37: Media API Resource Leak / Traversal Hardening — **DONE**
- [x] C38: AI Chat API (Round 2) — **DONE**
- [x] C39: Alert Notification API (Round 2) — **DONE**
- [x] C40: External Integration API (Round 2) — **DONE**

- [x] C60: Empty error handler fix (ads.py + media.py) — **DONE**
- [x] C61: Backend test coverage (16 new contract tests) — **DONE**
- [x] C62: API documentation (ErrorResponse schema + openapi.json export) — **DONE**
- [x] C63: Load testing scripts (load_test.py + generate_test_data.py) — **DONE**

## All tasks completed (C ~ C40, C60~C63). 136+ routes total.

---

## C60: Empty Error Handler Fix — Completion Report (2026-03-05)

### Status: COMPLETED

### Files Updated
- `backend/app/api/endpoints/ads.py` — 2 silent `except: pass` replaced with logger.warning
- `backend/app/api/endpoints/media.py` — 10 silent `except: pass` replaced with logger.warning/debug

### Changes
- All `except Exception: pass` patterns now log with context (ad_id, s3_key, error message)
- Non-critical fallbacks use `logger.debug`, important failures use `logger.warning`
- No functional behavior changes — same fallback logic preserved
- Only `ValueError`/`OSError` in tight loops (filename parsing, file size) left as-is

### Verification
- [x] `python -m py_compile` both files
- [x] Full test suite: 415 passed (no regressions)

---

## C61: Backend Test Coverage — Completion Report (2026-03-05)

### Status: COMPLETED

### Files Created
- `backend/tests/test_api_contract_ads.py` — 10 contract tests
- `backend/tests/test_api_contract_media.py` — 6 contract tests

### Coverage
- Ads: list, detail(404), data-integrity, connected-platforms, upload validation
- Media: thumbnail, image, video, ad-all, crawl-history, gallery
- All use async SQLite sessions matching production endpoint signatures

### Verification
- [x] 16/16 new tests pass
- [x] Full suite: 415 passed, 2 pre-existing failures unchanged

---

## C62: API Documentation — Completion Report (2026-03-05)

### Status: COMPLETED

### Files Created/Updated
- `backend/app/schemas/error.py` — ErrorResponse, ErrorBody, ErrorDetail models
- `backend/app/main.py` — Global 422/500 response model registration
- `backend/openapi.json` — Exported (370KB, 341 paths, 373 endpoints)

### Findings
- All 373 endpoints already had response schemas, tags, and descriptions
- Added structured ErrorResponse to OpenAPI components

---

## C63: Load Testing — Completion Report (2026-03-05)

### Status: COMPLETED

### Files Created
- `backend/scripts/load_test.py` — Multi-endpoint concurrent load test (stdlib only)
- `backend/scripts/generate_test_data.py` — Dummy data generator (1K-10K ads)

### Usage
```bash
# Generate 10K test ads
python scripts/generate_test_data.py --count 10000

# Run load test (30s, 10 concurrent)
python scripts/load_test.py --base-url http://localhost:8000 --concurrency 10 --duration 30

# Cleanup test data
python scripts/generate_test_data.py --cleanup
```

---

## C37: Media API Resource Leak / Traversal Hardening -- Completion Report (2026-03-03)

### Status: COMPLETED

### Files Updated
- `backend/app/api/endpoints/media.py`

### Changes
- `scenario-export` generated filename now sanitized via `_safe_export_slug()` to prevent path traversal.
- Added `BackgroundTask` cleanup to delete exported scenario files after response is sent.
- Added `_cleanup_file()` helper for best-effort temp file cleanup logging.

### Verification
- [x] `python -m py_compile backend/app/api/endpoints/media.py` success

---

## C36: Ads API Security & Validation Hardening -- Completion Report (2026-03-03)

### Status: COMPLETED

### Files Updated
- `backend/app/api/endpoints/ads.py`

### Changes
- Added strict MIME allowlist for uploads:
  - `video/mp4`, `video/webm`, `video/quicktime`
- Upload size overflow now returns `413` (was `400`).
- Converted `/ads/thumbnails/fetch-all` to async non-blocking execution with:
  - `asyncio.to_thread(...)`
  - `asyncio.wait_for(..., timeout=600)`
  - explicit `504` timeout response

### Verification
- [x] `python -m py_compile backend/app/api/endpoints/ads.py` success

---

## C35: Rankings Query Performance Optimization -- Completion Report (2026-03-03)

### Status: COMPLETED

### Files Verified
- `backend/app/api/endpoints/rankings.py`

### Verification Notes
- Pagination cap/validation and export row limits already present (`MAX_PAGE_SIZE`, `_validate_limit`, `validate_pagination`).
- SQL profiling hook (`_query_counter`) and endpoint-level profiling flags already present.
- N+1-related query reduction for `hit-ads` reflected in prior C-R2-4 implementation.

---

## C20: Advanced Filter & Failure Analysis API -- Completion Report (2026-02-28)

### Status: COMPLETED

### Endpoints Added (3 total)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 1 | `/rankings/success-failure-analysis` | GET | Splits ads into success (hit_score>=60) and failure (hit_score<40) groups. Per group: count, percentage, avg_views, avg_spend, avg_likes, avg_score, top hooks/CTAs/offers/emotions, common destination types, representative top-5 ads. Returns key_differences and actionable reuse_points in Japanese. |
| 2 | `/rankings/element-breakdown` | GET | Per-element statistics: hooks, CTAs, offers, emotions. Each with type, Japanese label, count, hit_rate, avg_score, vs_overall percentage comparison. Filterable by genre and element_type (hook/cta/offer/emotion/all). |
| 3 | `/rankings/destination-stats` | GET | Ad count and performance by destination type (記事LP, ECサイト, LINE追加, etc.). Includes top domains with count and hit_rate. Uses _classify_destination() from C18. |

### Helper Functions Added

| Function | Description |
|----------|-------------|
| `_group_stats(ads, field)` | Aggregates stats by a field value from creative_analysis. Returns per-value count, hit_rate, avg_score. |
| `_HOOK_LABELS` | Constant mapping hook_type keys to Japanese labels (質問型, 悩み訴求型, etc.) |

### Verification
- [x] All 3 endpoints return correct data via curl
- [x] success-failure-analysis returns key_differences and reuse_points
- [x] element-breakdown computes vs_overall comparison correctly
- [x] destination-stats uses _classify_destination() from C18
- [x] Only rankings.py modified

---

## C19: Scenario Generation API -- Completion Report (2026-02-28)

### Status: COMPLETED

### Endpoints Added (8 total)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 1 | `/rankings/scenario-archetypes` | GET | Returns all 8 scenario archetypes with Japanese names, descriptions, hit_rate, best genres, example counts. |
| 2 | `/rankings/scenario-templates` | GET | Templates grouped by genre. Loads from scenario_database.json if available, falls back to _SCENARIO_ARCHETYPES. Each template includes archetype_name, hit_rate, avg_score, structure, best_hooks, best_ctas, power_words. |
| 3 | `/rankings/generate-scenario` | POST | Template-based scenario generation. Body: genre_en, product_name, target_audience, key_benefit, cta_type, archetype, duration_seconds, platform. Returns complete scenario with hook, problem, solution, proof, CTA, full_script, power_words, predicted_score, reference_ads. |
| 4 | `/rankings/scenario-variations` | POST | Generate N variations of a base scenario with different hooks and CTAs. Each variation has predicted_score. |
| 5 | `/rankings/saved-scenarios` | GET | List all saved scenarios from backend/data/saved_scenarios.json. |
| 6 | `/rankings/saved-scenarios` | POST | Save a scenario. Body: name, scenario, genre. Stored with UUID-based ID and timestamp. |
| 7 | `/rankings/saved-scenarios/{id}` | DELETE | Delete a saved scenario by ID. |
| 8 | `/rankings/predict-scenario-performance` | POST | Predict performance of a scenario description. Uses genre hit data + power word analysis + hook/CTA effectiveness. Returns predicted_score, hit_probability, suggestions, strengths, weaknesses. |

### Constants Added

| Constant | Description |
|----------|-------------|
| `_SCENARIO_ARCHETYPES` | 8 archetype definitions (problem_solution, before_after, testimonial, authority, urgency, comparison, tutorial, lifestyle) |
| `_HOOK_TEMPLATES` | 7 hook templates with {placeholders} for shock, question, benefit, pain_point, social_proof, urgency, comparison |
| `_CTA_TEMPLATES` | 7 CTA templates with {placeholders} for line_add, free_consultation, limited_offer, download, purchase, signup, trial |

### Design Decisions
- Template-based generation only (no external AI API calls per constraint)
- Scenario database loaded from `backend/exports/scenario_database.json` with fallback
- Saved scenarios stored in `backend/data/saved_scenarios.json`
- Power word analysis uses common Japanese ad power words (衝撃, 簡単, 無料, 今すぐ, etc.)
- Predicted score computed from genre hit data + hook/CTA effectiveness + power word density

### Verification
- [x] All 8 endpoints return correct data via curl
- [x] Template-based generation fills placeholders correctly
- [x] Saved scenarios persist in JSON file
- [x] Only rankings.py modified

---

## C17: Precision Improvements - API Accuracy & Filtering -- Completion Report (2026-02-28)

### Status: COMPLETED

### Summary

Comprehensive precision improvements across all major ranking/search/display endpoints. Added data quality metadata, dynamic percentile-based hit thresholds, search relevance scoring, genre accuracy for NULL categories, and enhanced health-check/score-distribution endpoints.

### Changes Made

#### 1. New Helper Functions (6 total)

| Function | Description |
|----------|-------------|
| `_build_data_quality(ad)` | Returns `{has_thumbnail, has_creative_analysis, has_category, has_lp, has_description, completeness_pct}` for each ad |
| `_compute_dynamic_thresholds(scores)` | Computes percentile-based thresholds: p80 = big_hit, p60 = hit. Returns big_hit_threshold, hit_threshold, p25, p50, p75, p80, p90 |
| `_classify_hit_dynamic(score, thresholds)` | Classifies ad as "big_hit", "hit", or "normal" using dynamic percentile thresholds |
| `_is_quality_ad(ad)` | Filters ads: excludes `is_duplicate=true` and non-Japanese (`language != "ja"` when set) |
| `_resolve_genre_label(ad)` | Returns genre label with `"(uncategorized)"` for NULL category ads |

#### 2. data_quality Field Added to Ad Responses (6 endpoints)

| Endpoint | Change |
|----------|--------|
| `GET /rankings/products` | ads_map + items now include `data_quality` |
| `GET /rankings/products` (fallback) | Items include `data_quality` |
| `GET /rankings/hit-ads` | Items include `data_quality` |
| `GET /rankings/hit-ads` (fallback) | Items include `data_quality` |
| `GET /rankings/fresh-ads` | Results include `data_quality` |
| `GET /rankings/search` | Ad-type results include `data_quality` |

#### 3. Dynamic Hit Thresholds (Percentile-Based)

- **hit-ads** and **hit-ads fallback**: Compute dynamic thresholds from all ad scores. Each item gets a `dynamic_hit_level` field ("big_hit"/"hit"/"normal"). Response includes `dynamic_thresholds` object.
- **score-distribution**: Enhanced with `p25`, `p50`, `p75`, `p90` percentile stats and `dynamic_thresholds` showing current big_hit/hit boundaries.
- Logic: Top 20% of scores = big_hit, 20-40% = hit, rest = normal.

#### 4. Search Precision Improvements

| Change | Detail |
|--------|--------|
| `include_duplicates` parameter | New bool param (default: `false`). Excludes ads where `ad_metadata["is_duplicate"] == true` |
| Non-Japanese exclusion | Excludes ads where `ad_metadata["language"]` is set and not "ja" |
| Relevance scoring | Each ad result gets `relevance_score`: exact title match (+100), partial title (+70), description match (+30), advertiser match (+20), Japanese language boost (+10) |
| `match_field` enrichment | Shows where match occurred: `title_exact`, `title`, `description`, `advertiser` |
| `sort_by=relevance` | New sort option that orders results by computed relevance_score |

#### 5. Genre Accuracy

- NULL category ads now display as `"(uncategorized)"` instead of `"other"`, `"uncategorized"`, or `"未分類"` (inconsistent across endpoints)
- `_resolve_genre_label(ad)` standardizes genre resolution across all endpoints
- Updated in: hit-ads, hit-ads fallback, products fallback, fresh-ads, search, score-distribution, genre-comparison, dashboard-summary, creative-dna, copy-analysis, hit-factors, genre-winning-patterns, market-overview, competitors, recommendations, reports

#### 6. Enhanced health-check Endpoint

- Added 5 more endpoint checks: `/hit-ads`, `/fresh-ads`, `/quality-summary`, `/search`, `/db-connectivity`
- Fixed reference to non-existent `get_creative_type_analysis` (now correctly calls `get_creative_analysis`)
- Database connectivity check reports total_ads, null_category_count, has_data

#### 7. Enhanced score-distribution Endpoint

- Added percentile fields: `p25`, `p50`, `p75`, `p90` in both `stats` object and top-level aliases
- Added `dynamic_thresholds` object: `big_hit_threshold`, `hit_threshold`, description
- Histogram buckets unchanged (0-10, 10-20, ..., 90-100)
- By-genre now uses `(uncategorized)` for NULL category ads

### Quality Filtering Applied To

| Endpoint | Duplicates Excluded | Non-Japanese Excluded |
|----------|--------------------|-----------------------|
| hit-ads (main) | Yes | Yes |
| hit-ads (fallback) | Yes | Yes |
| fresh-ads | Yes | Yes |
| search | Yes (by default, `include_duplicates=false`) | Yes |

### Files Modified

| File | Change |
|------|--------|
| `backend/app/api/endpoints/rankings.py` | 6 new helper functions, data_quality in 6 endpoints, dynamic thresholds in 3 endpoints, search precision (3 new features), genre label standardization (~15 locations), health-check enhancement, score-distribution enhancement |

### Verification Checklist
- [x] Only rankings.py modified (Agent C exclusive territory)
- [x] No frontend files modified
- [x] No Agent A/B territory files modified
- [x] Existing endpoint behavior preserved (all new fields are additions, no removals)
- [x] `include_duplicates` defaults to `false` (backward compatible since it only excludes flagged duplicates)
- [x] Agent A ad_metadata keys read-only (is_duplicate, language only read, never written)
- [x] NULL category handled consistently as "(uncategorized)" across all endpoints
- [x] Dynamic thresholds computed from actual score distribution (no arbitrary cutoffs)
- [x] Health-check tests 11 endpoints including DB connectivity

*Last updated: 2026-02-28 (C20 completed)*

---

## C13: Advanced Search, Filter & Sort API -- Completion Report (2026-02-28)

### Status: COMPLETED

### Changes Made

#### 1. Enhanced existing `GET /rankings/search` endpoint

Added 6 new filter parameters and 2 new sort options to the existing search endpoint:

| New Parameter | Type | Description |
|---------------|------|-------------|
| `offer_type` | string | Filter by offer_type from creative_analysis |
| `max_score` | float | Maximum hit_score filter |
| `min_longevity_days` | int | Minimum days_running filter |
| `is_hit` | bool | Filter to only hit ads (or only non-hit) |
| `is_active` | bool | Filter to only currently active (still running) ads |
| `has_video` | bool | Filter to only ads with video |
| `sort_by=date_asc` | string | New sort option: oldest first |
| `sort_by=score_asc` | string | New sort option: lowest score first |

#### 2. New Endpoints Added (3 total)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 1 | `/rankings/autocomplete` | GET | Autocomplete suggestions for advertiser, genre, or keyword fields. Params: `q` (required), `field` (advertiser/genre/keyword), `limit` (1-50). Returns top matches by frequency. |
| 2 | `/rankings/saved-searches` | POST | Save a search query. Body: `{name, query, filters}`. Stored in `backend/data/saved_searches.json`. |
| 3 | `/rankings/saved-searches` | GET | List all saved searches from JSON file. |

#### 3. Infrastructure Added

- `_SAVED_SEARCHES_FILE` constant for saved searches JSON file path
- `_SavedSearchBody` Pydantic model for saved search creation
- `_load_saved_searches()` and `_save_saved_searches()` helper functions

### Files Modified

| File | Change |
|------|--------|
| `backend/app/api/endpoints/rankings.py` | Enhanced search endpoint (6 new params, 2 sort options), added 3 new endpoints, 1 Pydantic model, 2 helper functions, 1 file path constant |

### Verification Checklist
- [x] Only rankings.py modified
- [x] Existing search behavior preserved (all new params are optional)
- [x] offer_type, max_score, min_longevity_days, is_hit, is_active, has_video filters implemented
- [x] score_asc and date_asc sort options added
- [x] Autocomplete supports advertiser, genre, keyword fields
- [x] Saved searches use backend/data/saved_searches.json
- [x] No Agent A/B files modified

---

## C14: AI-Powered Analysis API -- Completion Report (2026-02-28)

### Status: COMPLETED

### Endpoints Added (10 total)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 1 | `/rankings/creative-intelligence/{ad_id}` | GET | Full creative intelligence from ad_metadata["creative_intelligence"]. Returns visual_elements, text_overlay, sentiment, key_phrases, labels, dominant_colors, faces_detected, strengths, weaknesses. Falls back to creative_analysis if creative_intelligence unavailable. |
| 2 | `/rankings/predict-hit/{ad_id}` | GET | Hit prediction from ad_metadata["hit_prediction"]. Returns probability, confidence, positive/negative factors, recommendation. Falls back to heuristic prediction from hit_score and creative_analysis. |
| 3 | `/rankings/predict-hit` | POST | Custom hit prediction for planning new creatives. Body: {hook_type, cta_type, offer_type, emotion, creative_type, text_length, has_testimonial, ...}. Compares against historical patterns to predict hit probability. Returns field_insights and recommendations. |
| 4 | `/rankings/lp-analysis/{ad_id}` | GET | Full LP analysis for an ad. Includes LP score, conversion/trust/urgency scores, CTA buttons, sections, form fields, testimonials, screenshot URL, funnel alignment score. Uses LandingPage + LPAnalysis models. |
| 5 | `/rankings/lp-benchmark` | GET | LP score benchmarks by genre. Correlation data: hit vs non-hit average LP scores. Supports genre filter. Falls back to ad_metadata["lp_score"] if LPAnalysis not available. |
| 6 | `/rankings/competitors` | GET | List top competitors with stats. Returns: name, ad_count, hit_rate, avg_score, strategy_summary, trend, top_hook, top_cta, recent_ad_count_30d. Sort by: ad_count, hit_rate, avg_score. Genre filter. |
| 7 | `/rankings/competitor/{name}` | GET | Deep competitor profile. All ads, strategy evolution (monthly timeline), creative element counters (hooks/CTAs/offers/emotions), genre distribution, predicted_next_move. |
| 8 | `/rankings/market-gaps` | GET | Under-served opportunities. Finds hooks, CTAs, offers, and genres that are underused but show high hit rates. Identifies gaps by comparing usage frequency against effectiveness. |
| 9 | `/rankings/recommendations` | GET | Ideal creative formula for a genre (required param). Returns best hook, CTA, offer, emotion, text length, effective boolean features. Includes human-readable recommendations and full options lists with hit rates. |

### Infrastructure Added

- `_PredictHitBody` Pydantic model for POST predict-hit

### Design Decisions

- **creative-intelligence**: Three-level fallback: creative_intelligence -> creative_analysis -> "none" message
- **predict-hit GET**: Returns stored ML prediction from ad_metadata if available; heuristic fallback derives probability from hit_score and creative signals
- **predict-hit POST**: Matches input parameters against all historical ads, computes field-level match rates and overall predicted probability
- **lp-analysis**: Uses LandingPage + LPAnalysis + LPSection models for full analysis; computes funnel_alignment_score showing ad-to-LP consistency
- **lp-benchmark**: Two-source approach - prefers LPAnalysis model, falls back to ad_metadata lp_score
- **competitors**: Strategy summary built from most common hook + CTA; trend based on 30-day ad volume ratio
- **competitor/{name}**: Includes predicted_next_move based on most recent 5 ads' patterns
- **market-gaps**: Identifies elements used less than 50% of average frequency but with above-average hit rates
- **recommendations**: Requires minimum 2 samples per element for "best" selection; falls back to most common if insufficient data

### Files Modified

| File | Change |
|------|--------|
| `backend/app/api/endpoints/rankings.py` | Added 10 new endpoints, 1 Pydantic model |

### Verification Checklist
- [x] Only rankings.py modified
- [x] All 10 endpoints added (creative-intelligence, predict-hit GET/POST, lp-analysis, lp-benchmark, competitors, competitor/{name}, market-gaps, recommendations)
- [x] Graceful fallbacks when AI data not available
- [x] Uses existing helpers: _resolve_thumbnail_url, _resolve_image_url, _resolve_video_url, _build_ad_detail
- [x] LP analysis uses LandingPage, LPAnalysis, LPSection models from app.models.landing_page
- [x] No Agent A/B territory files modified
- [x] All endpoints use sync_session_scope() context manager
- [x] Error handling: 404 for missing ads/competitors

*Last updated: 2026-02-28 (C13 + C14 completed)*

---

## C10: Production API & Download Support -- Completion Report (2026-02-28)

### Status: COMPLETED

### Summary

All C10 requirements were already partially implemented by prior tasks (C9, C8). This task completed the remaining enhancements: video URL resolution consistency, media status tracking, download URL generation, and enriching all ad detail responses with creative_analysis, media_status, and download_urls.

### Changes Made

#### 1. New Helper Functions (3 total)

| Function | Location | Description |
|----------|----------|-------------|
| `_resolve_media_status(ad)` | Line 77-100 | Returns `cached`, `partial`, or `uncached` based on whether thumbnail and main media (image/video) have local cache entries in `media_cache/` |
| `_build_download_urls(ad)` | Line 103-115 | Returns `{thumbnail, image, video}` dict with `/api/v1/media/download/{ad_id}/{type}` URLs (empty string if no media available) |
| `_resolve_video_url(ad)` | Line 70-74 | Already existed; now consistently used everywhere instead of raw `ad.video_url or ""` |

#### 2. Video URL Resolution Fix (5 occurrences fixed)

All `ad.video_url or ""` references in response builders replaced with `_resolve_video_url(ad)`:

| Endpoint/Function | Lines Changed |
|-------------------|---------------|
| `get_product_rankings` (ads_map builder) | `ad_url` and `video_url` fields |
| `_fallback_ad_list` | `ad_url` and `video_url` fields |
| `get_hit_ads` (ProductRanking path) | `ad_url` and `video_url` fields |
| `_fallback_hit_ads` | `ad_url` and `video_url` fields |
| `get_fresh_ads` | `video_url` field |

#### 3. Ad Detail Response Enrichment (7 response builders enhanced)

Added `creative_analysis`, `media_status`, and `download_urls` to all ad detail responses:

| Response Builder | Endpoint |
|-----------------|----------|
| `get_product_rankings` ads_map | `GET /rankings/products` |
| `get_product_rankings` items | `GET /rankings/products` (from ads_map) |
| `_fallback_ad_list` | `GET /rankings/products` (fallback) |
| `get_hit_ads` items | `GET /rankings/hit-ads` |
| `_fallback_hit_ads` | `GET /rankings/hit-ads` (fallback) |
| `pro_search` ad results | `GET /rankings/search` |
| `get_fresh_ads` | `GET /rankings/fresh-ads` |
| `_build_full_ad_row` | Export endpoints (`/export/csv`, `/export/json`) |

#### 4. Export Endpoints (already existed, enhanced)

The following export endpoints were already created in a prior session:

| Endpoint | Method | Status |
|----------|--------|--------|
| `GET /rankings/export/csv` | StreamingResponse CSV | Already existed; now includes creative_analysis, media_status, download_urls via _build_full_ad_row |
| `GET /rankings/export/json` | StreamingResponse JSON | Already existed; now includes creative_analysis, media_status, download_urls via _build_full_ad_row |
| `GET /rankings/export/report` | StreamingResponse JSON | Already existed; hit factors, winning patterns, genre comparison |

#### 5. Search API (already existed, enhanced)

`GET /rankings/search` already had full-text search, all requested filters, pagination, and sorting. Now enhanced with `media_status` and `download_urls` in ad-type results.

#### 6. Dashboard Summary (already complete)

`GET /rankings/dashboard-summary` already included all requested fields: `total_ads`, `fresh_ads_count`, `media_cache_rate`, `avg_hit_score`, `top_genres`, `top_hooks`, `top_ctas`.

### Files Modified

| File | Change |
|------|--------|
| `backend/app/api/endpoints/rankings.py` | Added 2 new helper functions (`_resolve_media_status`, `_build_download_urls`); fixed 5 raw `ad.video_url` references to use `_resolve_video_url(ad)`; added `creative_analysis`, `media_status`, `download_urls` to 8 response builders |

### Verification Checklist
- [x] Only rankings.py modified (Agent C exclusive territory)
- [x] No frontend files modified
- [x] No Agent A/B territory files modified
- [x] `_resolve_video_url` used consistently everywhere (no raw `ad.video_url or ""` in responses)
- [x] `_resolve_media_status` returns cached/partial/uncached
- [x] `_build_download_urls` generates proper `/api/v1/media/download/` paths
- [x] All 7+ response builders now include creative_analysis, media_status, download_urls
- [x] Export endpoints use StreamingResponse (already implemented)
- [x] English-only in code comments and function docstrings
- [x] Agent A ad_metadata keys read-only (not modified)
- [x] No new imports needed (all already available at file top)
- [x] Existing endpoint behavior preserved (additions only, no removals)

---

## C9: Realtime Crawl API -- Completion Report (2026-02-28)

### Status: COMPLETED

### Endpoints Added (4 total)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 1 | `/rankings/crawl-status` | GET | Returns recent crawl jobs from last N hours (default 24h). Queries CrawlJob table, returns job_id, status, query, platforms, total_ads_found, progress info, timestamps. Params: `hours` (1-168, default 24), `limit` (1-100, default 20). |
| 2 | `/rankings/quick-crawl` | POST | Simplified crawl trigger for dashboard. Creates CrawlJob tracking record, runs `_inline_crawl` from ads.py for facebook+tiktok platforms, updates job status on completion/failure. Params: `query` (required), `limit` (1-100, default 20). Returns job_id, new_ads_count, keywords_searched, platforms. |
| 3 | `/rankings/refresh-trends` | POST | Recomputes hit_score and trend_score for ALL ads using `compute_hit_score_with_details()` with fresh genre_stats and last 30 days of metrics. Updates existing ProductRanking rows or creates new ones. Also stores latest_hit_score and latest_trend_score in ad_metadata (without overwriting Agent A keys). Returns updated_count. |
| 4 | `/rankings/fresh-ads` | GET | Returns ads crawled in last N days (default 7), sorted by created_at desc. Includes thumbnail/image URL resolution via helpers, hit_score from ProductRanking, creative_type, longevity info. Supports pagination (page, per_page) and filters (platform, creative_type). |

### Files Modified

| File | Change |
|------|--------|
| `backend/app/api/endpoints/rankings.py` | Added 4 new endpoints at end of file (lines 2514-2833). Three new section headers: "Crawl Status & Quick-Crawl", "Trend Refresh", "Fresh Ads". |
| `C/.agent-tasks/C/status.md` | Updated with C9 completion report |

### Key Design Decisions
- `quick-crawl` imports `_inline_crawl` from `app.api.endpoints.ads` (as specified in task) rather than duplicating crawl logic
- `quick-crawl` creates and updates CrawlJob records in separate sessions (tracking_session/update_session) to ensure the job record is created even if crawl fails
- `refresh-trends` creates new ProductRanking with proper required fields (period_start, period_end, rank_position) when no existing ranking exists
- `refresh-trends` uses `flag_modified(ad, "ad_metadata")` pattern for JSON field updates (per INSTRUCTIONS.md)
- `fresh-ads` batch-fetches ProductRankings to avoid N+1 queries, keeps highest hit_score when multiple rankings exist
- All endpoints reuse existing helpers: `_resolve_thumbnail_url()`, `_resolve_image_url()`, `_extract_longevity_info()`, `_clean_advertiser()`, `_derive_product_name()`, `_resolve_platform_filter()`
- CrawlJob status enum properly handled with `.value` attribute check
- All log messages and print statements in English

### Verification Checklist
- [x] Only rankings.py modified (Agent C exclusive territory)
- [x] No frontend files modified
- [x] No ads.py, media.py, or Agent A/B territory files modified
- [x] Uses _resolve_thumbnail_url and _resolve_image_url helpers
- [x] English-only log/print statements
- [x] Agent A ad_metadata keys not overwritten (only reads; writes only latest_hit_score, latest_trend_score)
- [x] flag_modified pattern used for ad_metadata updates
- [x] CrawlJob model imported from app.models.crawl_job
- [x] Existing endpoints untouched (addition only)
- [x] Proper error handling (try/except with rollback)
- [x] Pagination support on fresh-ads endpoint

---

## C8: Hit Pattern Analysis API -- Completion Report (2026-02-28)

### Status: COMPLETED

### Endpoints Added (4 total)

| # | Endpoint | Description |
|---|----------|-------------|
| 1 | `GET /rankings/hit-factors` | Creative element hit rate aggregation. Per-field (hook_type, cta_type, offer_type, emotion, text_length, destination_type) count/hit_rate/avg_score. Plus top 10 winning combinations (hook+cta+offer, min 3 samples). Supports `?genre=` and `?platform=` filters. |
| 2 | `GET /rankings/creative-dna/{ad_id}` | Individual ad creative analysis detail. Returns creative_analysis fields, pattern_hit_rate (hit rate of ads with same hook+cta+offer combo), pattern_rank (rank among all patterns), similar_hits (top 5 hit ads with same pattern). 404 if ad not found, graceful response if creative_analysis absent. |
| 3 | `GET /rankings/copy-analysis` | Text feature effect analysis. Compares hit vs non-hit ads on: avg description length, emoji usage hit rate, number usage hit rate, testimonial effect, before/after effect. Each feature includes sample counts. Supports `?genre=` and `?platform=` filters. |
| 4 | `GET /rankings/genre-winning-patterns` | Genre-specific winning patterns. Per-field winners (all factor+bool fields sorted by hit_rate), top 10 combinations (min 2 samples), genre-level hit rate. Supports `?genre=` and `?platform=` filters. Works without genre filter (analyzes all ads). |

### Files Modified

| File | Change |
|------|--------|
| `backend/app/api/endpoints/rankings.py` | Added section "Hit Pattern Analysis (C8)" (lines 1963-2427): 2 helper functions (`_get_creative_analysis`, `_is_hit_ad`), 2 module-level constants (`_FACTOR_FIELDS`, `_BOOL_FIELDS`), 4 new endpoint functions |

### Helper Functions Added

| Function | Purpose |
|----------|---------|
| `_get_creative_analysis(ad)` | Safely extracts `ad_metadata["creative_analysis"]` dict, returns None if absent or not a dict |
| `_is_hit_ad(ad)` | Consistent hit classification: checks hit_level metadata first, then score thresholds (hit: score>=45 & days>=30, mega_hit: score>=70 & days>=60) |

### Data Source
- Reads `ad_metadata["creative_analysis"]` written by Agent A
- Fields consumed: hook_type, cta_type, offer_type, offer_detail, emotion, has_emoji, has_numbers, has_testimonial, has_before_after, text_length, destination_type
- **Read-only** -- does NOT write to ad_metadata (Agent A territory)

### Design Decisions
- Ads without `creative_analysis` are gracefully skipped (not errors)
- Empty data returns empty dicts/arrays (never errors)
- Winning combinations require minimum sample counts (3 for hit-factors, 2 for genre-winning-patterns) to avoid noise
- Pattern rank in creative-dna requires minimum 2 samples per pattern
- Hit classification reuses existing codebase logic (score thresholds + hit_level metadata)
- No new imports added (all dependencies already imported at file top)
- All endpoints follow existing patterns: `sync_session_scope()`, `_resolve_platform_filter()`, `compute_hit_score()`, etc.

### Verification Checklist
- [x] Existing endpoints untouched (addition only, no modifications to lines 1-1961)
- [x] No new imports needed (all functions already available)
- [x] Agent A ad_metadata keys read-only (not modified)
- [x] creative_analysis absent = graceful skip (not error)
- [x] Empty data = empty response (not error)
- [x] No frontend files modified
- [x] No Agent A/B territory files touched
- [x] All helper functions defined before use
- [x] Consistent hit classification with rest of codebase

### Manual Verification Command
```
cd C:/Users/ishit/ads_library/backend && python -c "from app.api.endpoints.rankings import router; print(f'Routes loaded: {len(router.routes)}')"
```
Expected: 24 routes (20 existing + 4 new)

---

## C7: サムネイルURL修正 — Completion Report (2026-02-28)

### Changes
| # | Change | Detail |
|---|--------|--------|
| 1 | `_resolve_thumbnail_url()` rewritten | Priority: media_cache proxy > S3 presigned > CDN URL > image_url > snapshot_url |
| 2 | `_resolve_image_url()` added | Priority: media_cache proxy > image_url > thumbnail_url |
| 3 | All `image_url` references updated | 4 occurrences changed from `ad.image_url` to `_resolve_image_url(ad)` |

### Verified
- [x] 20 routes loaded without errors
- [x] Both helper functions importable
- [x] All image_url fields in responses use _resolve_image_url()

---

## C6: Data Quality & LP Health API -- Completion Report (2026-02-28)

### Status: COMPLETED

### Deliverables

| # | Item | Type | Description |
|---|------|------|-------------|
| 1 | `backend/scripts/check_lp_health.py` | New script | HEAD requests to all destination_urls, records lp_status and lp_checked_at in ad_metadata |
| 2 | `GET /rankings/lp-health` | New endpoint | LP health summary: total_checked, status_200, status_redirect, status_error, unchecked, health_rate, status_distribution, problem_ads list |
| 3 | `GET /rankings/quality-summary` | New endpoint | Data completeness scoring (0-100) per ad with 10 criteria, avg_completeness, completeness_distribution buckets, low_quality_ads list |
| 4 | hit-ads destination_url fix | Bug fix | Changed from `metadata.get("destination_url")` to `ad.destination_url or metadata.get("destination_url")` in both main and fallback paths |

### Files Modified

| File | Change |
|------|--------|
| `backend/scripts/check_lp_health.py` | **NEW** - LP health check script (HEAD requests, rate-limited, flag_modified pattern) |
| `backend/app/api/endpoints/rankings.py` | Added `flag_modified` import (L15), fixed destination_url source in hit-ads main path (L546) and fallback path (L629), added `/lp-health` endpoint (L1724-1787), added `/quality-summary` endpoint (L1793-1948) |

### check_lp_health.py Details
- HEAD requests to each destination_url with 10s timeout
- Rate limited: 0.5s between requests
- Handles: timeout, connection_error, too_many_redirects, ssl_error
- Records in ad_metadata: `lp_status`, `lp_checked_at`, `lp_final_url` (if redirected), `lp_error_detail` (on error)
- Commits every 100 ads to avoid large transactions
- Progress logging every 50 ads
- All print statements in English (cp932 safe)
- Uses flag_modified pattern for ad_metadata updates

### Quality Summary Scoring Criteria (10 items, 10pts each = 100 max)
1. title present (+10)
2. description present (+10)
3. destination_url present (+10)
4. LP reachable / lp_status=200 (+10)
5. thumbnail_url or thumbnail_s3_key present (+10)
6. image_url or image_s3_key present (+10)
7. video_url or s3_key present (+10, video ads only; non-video gets free points)
8. category set (+10)
9. score_breakdown in metadata (+10)
10. days_running > 0 (+10)

Stores `data_completeness` score in ad_metadata for each ad.

### hit-ads destination_url Fix
- **Before**: `metadata.get("destination_url", "")` -- read from JSON metadata only
- **After**: `ad.destination_url or metadata.get("destination_url", "")` -- prioritizes the Ad column (which is the canonical source), falls back to metadata
- Fixed in both main ProductRanking path and `_fallback_hit_ads()` path
- `description` field was already present in both paths (confirmed OK)

### Verification Checklist
- [x] Script uses flag_modified pattern for ad_metadata updates
- [x] Agent C ad_metadata keys only: lp_status, lp_checked_at, lp_final_url, lp_error_detail, data_completeness
- [x] Agent A keys not modified (read-only)
- [x] All print statements in English
- [x] Existing endpoints untouched (additions only)
- [x] flag_modified import added to rankings.py
- [x] No frontend files modified
- [x] No Agent A/B territory files touched
- [x] Empty database handled gracefully (both endpoints)
- [x] Problem ads and low quality ads limited to 100 entries in response

### Note
- Script execution requires bash permission. Run manually: `cd C:/Users/ishit/ads_library/backend && python scripts/check_lp_health.py`
- The `/rankings/lp-health` API will show `unchecked` count until the script is run
- The `/rankings/quality-summary` API works independently (LP reachability is just one of 10 criteria)

---

## C5: Trend Analysis & Genre Comparison API -- Completion Report (2026-02-28)

### Status: COMPLETED

### Endpoints Added (4 total)

| # | Endpoint | Description |
|---|----------|-------------|
| 1 | `GET /rankings/genre-comparison` | Per-genre (ad_category) stats: ad_count, active_count, avg_score, hit/mega_hit counts & rates, avg_days_running. NULL genres grouped as "uncategorized". Sorted by ad_count descending. |
| 2 | `GET /rankings/duration-brackets` | Delivery duration bracket analysis: 0-7d, 8-14d, 15-30d, 31-60d, 61-90d, 91d+. Per bracket: count, avg_score, hit_rate. Shows correlation between duration and performance. |
| 3 | `GET /rankings/creative-analysis` | Creative type (video/image/carousel/unknown) comparison: ad_count, avg_score, hit_rate, avg_days_running. Auto-infers type from video_url/image_url when creative_type is missing. Sorted by ad_count descending. |
| 4 | `GET /rankings/dashboard-summary` | Single API call returning all dashboard KPIs: total_ads, active_ads, hit_count, mega_hit_count, avg_score, avg_days_running, top_genre (highest hit_rate with min 3 ads), top_creative_type (highest hit_rate with min 3 ads). |

### Files Modified

| File | Change |
|------|--------|
| `backend/app/api/endpoints/rankings.py` | Added 4 new endpoint functions (lines 1426-1717), section header "Trend & Comparison Endpoints (C5)" |

### Design Decisions
- Reuses existing helpers: `_extract_longevity_info()`, `compute_hit_score()`, `sync_session_scope()`
- Hit classification consistent with rest of codebase: hit = score>=45 & days>=30, mega_hit = score>=70 & days>=60
- `genre-comparison` uses `hit_level` from metadata when available, falls back to threshold-based classification
- `creative-analysis` auto-infers creative type from `video_url`/`image_url` when `creative_type` is null/unknown
- `dashboard-summary` requires minimum 3 ads per genre/creative_type to qualify for "top" selection (avoids noise)
- All endpoints handle empty database gracefully
- No new imports or external dependencies added

### Verification Checklist
- [x] Existing endpoints untouched (addition only, no modifications to lines 1-1424)
- [x] No new imports added (all functions used already imported at file top)
- [x] Agent A keys in ad_metadata read-only (not modified)
- [x] No frontend files modified
- [x] No Agent A/B territory files touched
- [x] Edge cases handled: empty ads list, missing metadata, days_running=0, NULL genre/creative_type
- [x] 18 routes loaded (14 existing + 4 new)
- [x] Integration test results:
  - genre-comparison: beauty(108ads, avg=62.2, hit=61.1%), ec_d2c(22ads, hit=72.7%), other(16ads)
  - duration-brackets: 91d+(63ads, avg=90.4, hit=100%), 0-7d(39ads, avg=15.4, hit=0%)
  - creative-analysis: video(98ads, avg=50.4, hit=44.9%), image(78ads, avg=63.9, hit=70.5%)
  - dashboard-summary: total=176, active=151, hit=99, mega=74, top_genre=ec_d2c, top_creative=image

---

## C4: APIレスポンス統合 — Completion Report (v2, 2026-02-28)

### Status: COMPLETED (actual implementation applied)

Previous status was inaccurate -- fallback paths were missing score_breakdown and regex= was still present.

| Task | Change |
|------|--------|
| 1. hit-ads ProductRanking path | Already had score_breakdown (L515/L530) - confirmed OK |
| 2. hit-ads fallback `_fallback_hit_ads()` | `_breakdown` renamed to `breakdown`, `"score_breakdown": breakdown` added (L593/L613) |
| 3. products ProductRanking path | Already had score_breakdown (L308/L325) - confirmed OK |
| 4. products fallback `_fallback_ad_list()` | `_breakdown` renamed to `breakdown`, `"score_breakdown": breakdown` added (L425/L449) |
| 5. regex -> pattern (5 occurrences) | L248, L655, L665, L856, L1253 all changed |

### Verified
- [x] Zero `regex=` occurrences remaining in rankings.py
- [x] `score_breakdown` present in all 4 response paths (products PR, products fallback, hit-ads PR, hit-ads fallback)
- [x] No existing response fields removed (addition only)
- [x] No frontend files modified

### recompute実行結果 (2026-02-28 12:44)
```
Total: 176, Avg: 56.4, Max: 93.0, Min: 12.1
Hit: 25件, Mega Hit: 74件
Score distribution: 0-19=36, 20-39=26, 40-59=30, 60-79=17, 80-100=67
```

---

## C3: Analysis API Pipeline — Completion Report

### Endpoints Added (5 total)

| # | Endpoint | Description |
|---|----------|-------------|
| 1 | `GET /rankings/score-breakdown/{ad_id}` | Per-ad score breakdown with enriched signal details |
| 2 | `GET /rankings/score-distribution` | Score distribution buckets + stats (mean/median/max/min) + by-genre |
| 3 | `GET /rankings/advertiser-detail?advertiser_name=X` | Advertiser aggregate analysis with hit/non-hit ad lists |
| 4 | `GET /rankings/top-advertisers?limit=20&sort_by=total_spend` | Advertiser-level ranking (sortable by spend/score/count) |
| 5 | `GET /rankings/longevity-analysis` | Scatter data + bucketed days_running vs hit_score correlation |

### Files Modified

| File | Change |
|------|--------|
| `backend/app/services/ranking/ranking_service.py` | Added `compute_hit_score_with_details()`, `_describe_creative()`, `_describe_trend()` helper functions |
| `backend/app/api/endpoints/rankings.py` | Added 5 new endpoint functions, updated import to include `compute_hit_score_with_details` |

### Design Decisions
- Used pure Python for median/mean (no NumPy dependency)
- Reuses existing `compute_hit_score()`, `_extract_longevity_info()`, `_clean_advertiser()`, `_derive_product_name()`, `_resolve_thumbnail_url()`, `_escape_like()` functions
- All new endpoints use `sync_session_scope()` context manager (consistent with existing endpoints)
- `compute_hit_score_with_details()` wraps `compute_hit_score()` and adds max/detail per signal
- All log/error messages in English (cp932 safe)
- No changes to frontend, tasks, or collector scripts

### Verification Checklist
- [x] Existing endpoints (`/products`, `/hit-ads`, `/genre-summary`, `/search`, `/export/*`) untouched
- [x] No new imports that could cause circular dependencies
- [x] Agent A keys in ad_metadata read-only (not modified)
- [x] Consistent response format matching task specification
- [x] Edge cases handled (no ads, missing metadata, days_running=0)
- [x] Removed duplicate `compute_hit_score_with_details()` (my version vs other agent's)
- [x] All 14 routes load without import errors
- [x] Integration test passed: score-breakdown(90.0/mega_hit), distribution(176 ads), top-advertisers(97), longevity-buckets(OK)

---

## C2-fix: ヒットスコア閾値修正 — 完了レポート

### 問題
- 最高スコアが59点 → 176件中60点すら超えない
- mega_hit 0件（閾値70、データ不足で到達不可能）
- ヒット12件のみ（99件が30日以上配信しているのに12件だけ）
- 原因: audience(0-20)とtrend(0-10)が常に0点、spend閾値が高すぎ

### 修正内容

#### 旧モデル（v1）→ 新モデル（v2）
| シグナル | v1 配点 | v2 配点 | 変更理由 |
|---------|---------|---------|----------|
| longevity（配信日数） | 0-25 | **0-40** | 最もデータがある指標を重視 |
| spend（消化額） | 0-25 | **0-20** | 閾値も 50万→20万 に下げた |
| audience（オーディエンス） | 0-20 | **削除** | データが全件0のため無意味 |
| platforms（配信面） | 0-10 | **削除** | データ不足 |
| active_bonus（配信中） | 含まれていた | **0-20** | 独立シグナルに昇格 |
| creative（品質） | 0-10 | 0-10 | 据え置き |
| trend（トレンド） | 0-10 | 0-10 | 据え置き、メトリクス1件でも加点 |

#### 配信日数スコア (Signal 1: 0-40点)
```
14日=5点, 30日=15点, 60日=25点, 90日=35点, 120日+=40点
```

#### 消化額スコア (Signal 2: 0-20点) — 閾値を大幅に下げた
```
1万以上=5点, 5万以上=10点, 10万以上=15点, 20万以上=20点
```

#### 配信中ボーナス (Signal 3: 0-20点) — 新設
```
配信中 + 7日=5点, 14日=10点, 30日=15点, 60日+=20点
停止中 = 0点
```

#### ヒット判定閾値
| レベル | v1条件 | v2条件 |
|--------|--------|--------|
| `hit` | score≥55 AND 14日以上 | **score≥45 AND 30日以上** |
| `mega_hit` | score≥70 AND 30日以上 | **score≥70 AND 60日以上** |

### 期待されるスコア分布（典型ケース）
- 120日配信中 + 10万消化 + 動画あり = 40+15+20+10+0 = **85点 (mega_hit)**
- 60日配信中 + 5万消化 + 動画あり = 25+10+20+10+0 = **65点 (hit)**
- 30日配信中 + 1万消化 + 画像のみ = 15+5+15+3+0 = **38点 (none → あと7点でhit)**
- 90日配信停止 + spend不明 = 35+0+0+10+0 = **45点 (hit)**

### 変更ファイル
| ファイル | 変更 |
|---------|------|
| `backend/app/services/ranking/ranking_service.py` | `compute_hit_score()` v2化 |
| `backend/scripts/recompute_hit_scores.py` | 表示メッセージ修正 |

### 確認事項
- [x] `compute_rankings()` が `compute_hit_score()` を各広告に対して正しく呼んでいる (L388-398)
- [x] 結果が `ProductRanking.hit_score`, `is_hit`, `extra_metadata` に保存される (L420-426)
- [x] `POST /rankings/compute` が `compute_all_rankings()` を呼んでいる (L220-221)
- [x] `flag_modified` を使っている (recompute_hit_scores.py L104)
- [x] Agent A のキーは読み取りのみ（上書きなし）

---

## C: メディアURL補完 — 完了レポート

### 成果物
| ファイル | 種別 | 状態 |
|---------|------|------|
| `backend/scripts/backfill_media_urls.py` | 新規 | 作成済み・実行済み |
| `backend/app/tasks/crawl_tasks.py` `_inline_enrich` | 修正 | video src抽出を追加 |

### 結論
- image_url: 全件補完済み (0 NULL)
- video_url: 88件NULL（73件=image広告で正常、15件=unknown→トークン更新必要）

---

---

## C11: Advanced Analytics API -- Completion Report (2026-02-28)

### Status: COMPLETED

### Endpoints Added (9 total)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 1 | `/rankings/advertisers` | GET | List all advertisers with stats: name, ad_count, hit_count, hit_rate, avg_score, top_genre, active_ads. Sort by: ad_count, hit_rate, avg_score. Pagination support. |
| 2 | `/rankings/advertiser/{name}/ads` | GET | Get all ads by specific advertiser with full ad details and resolved media URLs. Sort by: score_desc, date_desc, views_desc. Pagination. |
| 3 | `/rankings/advertiser/{name}/profile` | GET | Advertiser profile with creative strategy summary: dominant hooks, CTAs, emotions, offers. Performance over time (monthly timeline), genre distribution, platform distribution. |
| 4 | `/rankings/trends/weekly` | GET | Weekly trend data for last 12 weeks. Per week: ad_count, avg_score, hit_rate, hit_count, top_hooks. Returned in chronological order. |
| 5 | `/rankings/trends/rising-patterns` | GET | Patterns gaining popularity. Compares last 4 weeks vs previous 4 weeks. Rising hooks, CTAs, emotions with usage_change and hit_rate_change. |
| 6 | `/rankings/trends/market-overview` | GET | Current market snapshot: total active ads, avg score, genre distribution with share, creative type split, platform distribution, hit summary. |
| 7 | `/rankings/compare` | POST | Compare 2-5 ads side by side. Body: {ad_ids: [1,2,3]}. Returns full details + comparative analysis (score range, hooks/CTAs/emotions used, same_hook/cta/emotion flags, best_ad_id). |
| 8 | `/rankings/similar/{ad_id}` | GET | Find similar ads based on same advertiser (+30), same genre (+20), same hook (+15), same CTA (+15), same offer (+10), same emotion (+10). Returns top N with similarity_score. |
| 9 | `/rankings/generate-report` | POST | Generate comprehensive analysis report. Body: {genre?, advertiser?, date_range?}. Returns: summary stats, hit patterns (top hooks/CTAs), winning formulas, text recommendations. |

### Helper Function Added

| Function | Description |
|----------|-------------|
| `_build_ad_detail(ad)` | Builds a complete ad detail dict with all resolved media URLs, creative_analysis, bookmark info. Reused across C11/C12 endpoints for consistency. |

---

## C12: Alerts & Bookmarks API -- Completion Report (2026-02-28)

### Status: COMPLETED

### Endpoints Added (11 total)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 1 | `/rankings/bookmarks` | POST | Bookmark an ad. Stores bookmarked, bookmark_note, bookmark_tags, bookmarked_at in ad_metadata. Uses flag_modified pattern. |
| 2 | `/rankings/bookmarks` | GET | List all bookmarked ads with full details. Filter by tag. Sort by bookmark date. Pagination. Returns available_tags for filtering. |
| 3 | `/rankings/bookmarks/{ad_id}` | DELETE | Remove bookmark from ad. Clears bookmarked, bookmark_note, bookmark_tags, bookmarked_at from ad_metadata. |
| 4 | `/rankings/collections` | POST | Create a collection. Body: {name, description?}. Stored in backend/data/collections.json. |
| 5 | `/rankings/collections` | GET | List all collections with ad counts. |
| 6 | `/rankings/collections/{collection_id}/ads` | POST | Add ad to collection. Body: {ad_id}. Verifies ad exists. Prevents duplicates. |
| 7 | `/rankings/collections/{collection_id}` | GET | Get collection with all ads (full details via _build_ad_detail). |
| 8 | `/rankings/collections/{collection_id}` | DELETE | Delete a collection. |
| 9 | `/rankings/collections/{collection_id}/ads/{ad_id}` | DELETE | Remove ad from collection. |
| 10 | `/rankings/alerts` | GET | Smart alerts computed on-the-fly: high-score ads (>80) in last 24h, new ads from bookmarked advertisers, volume spikes/drops. |
| 11 | `/rankings/activity` | GET | Recent system activity: crawl jobs, new ads grouped by hour, score updates. Based on CrawlJob table + ad timestamps. |

### Collections Storage

- Collections stored in `backend/data/collections.json` (JSON file, not database)
- `_COLLECTIONS_FILE` path computed relative to rankings.py using `Path(__file__).resolve()`
- Helper functions: `_load_collections()`, `_save_collections()`
- Directory created automatically via `mkdir(parents=True, exist_ok=True)`
- Each collection has: id (uuid[:8]), name, description, ad_ids[], created_at, updated_at

### Bookmark Storage

- Bookmark data stored in `ad_metadata` JSON field of Ad model
- Keys used: `bookmarked` (bool), `bookmark_note` (str), `bookmark_tags` (list), `bookmarked_at` (ISO timestamp)
- Uses `flag_modified(ad, "ad_metadata")` pattern per INSTRUCTIONS.md
- Does NOT overwrite Agent A keys

### Files Modified

| File | Change |
|------|--------|
| `backend/app/api/endpoints/rankings.py` | Added imports (json, uuid, Path, List, JSONResponse), _COLLECTIONS_FILE constant, _build_ad_detail helper, 9 C11 endpoints, 11 C12 endpoints, 4 Pydantic models, 2 collection helper functions |

### Imports Added

| Import | Purpose |
|--------|---------|
| `json` | Collections JSON file read/write |
| `uuid` | Collection ID generation |
| `Path` | Collections file path resolution |
| `List` | Type hint for Pydantic models |
| `JSONResponse` | Error responses (404, 400) |

### Verification Checklist
- [x] Only rankings.py modified (Agent C exclusive territory)
- [x] No frontend files modified
- [x] No Agent A/B territory files modified
- [x] flag_modified used for bookmark ad_metadata changes
- [x] Agent A ad_metadata keys not overwritten (bookmarked, bookmark_note, bookmark_tags are new Agent C keys)
- [x] Collections use JSON file at backend/data/collections.json
- [x] Existing helpers reused: _resolve_thumbnail_url, _resolve_image_url, _resolve_video_url, _resolve_media_status, _build_download_urls
- [x] All endpoints use sync_session_scope() context manager
- [x] Error handling: 404 for missing ads/collections, 400 for invalid compare input
- [x] Pagination on advertisers, advertiser ads, bookmarks
- [x] No circular import issues

*Last updated: 2026-02-28 (C11 + C12 completed)*


---

## C29: Genre Analytics API -- COMPLETED (2026-03-01)
- Already implemented by previous agent session
- 4 endpoints: /genres/distribution, /genres/{genre}/details, /genres/comparison, /genres/trends

## C30: Search & Autocomplete API -- COMPLETED (2026-03-01)
- Already implemented by previous agent session
- 3 endpoints: /search/suggest, /search/facets, /search/advanced

## C31: Media Pipeline Connection -- COMPLETED (2026-03-01)
- runner.py: Added _FakeCeleryTask + _is_bound_celery_task for ECS direct execution of bind=True tasks
- media_extraction.py: Added --disable-gpu, --single-process Chromium args; domcontentloaded page load; _parse_render_ad_html method
- lambda_handler.py: Added action=extract_media handler (_run_extract_media function)

## C32: Media Extraction Status API -- COMPLETED (2026-03-01)
- 4 endpoints: /media-extraction-status, /media-extraction-ads, /batch-extract-media, /retry-failed-media
- Added to rankings.py

## C33: DLQ Monitoring API -- COMPLETED (2026-03-01)
- 3 endpoints: /dlq-status, /dlq-messages, /dlq-retry
- Added to rankings.py

## C34: ECS Task Status API -- COMPLETED (2026-03-01)
- 2 endpoints: /ecs-tasks, /ecs-tasks/recent
- Added to rankings.py

---

## C-R2-1: AI Chat API -- Completion Report (2026-03-02)

### Status: COMPLETED

### Endpoints Added (4 total)
- `POST /api/v1/ai-chat/message`
- `GET /api/v1/ai-chat/conversations`
- `GET /api/v1/ai-chat/conversations/{conversation_id}`
- `DELETE /api/v1/ai-chat/conversations/{conversation_id}`

### Files Added
- `backend/app/models/conversation.py`
- `backend/app/services/ai/intent_classifier.py`
- `backend/app/services/ai/chat_service.py`
- `backend/app/services/ai/__init__.py`
- `backend/app/api/endpoints/ai_chat.py`

### Files Updated
- `backend/app/main.py` (router + model import)
- `backend/app/models/__init__.py` (Conversation export)
- `backend/app/core/database.py` (reconnect時のmodel import)
- `backend/app/api/endpoints/__init__.py`

### Notes
- ルールベース意図分類（analyze_ad, analyze_genre, find_trends, data_stats, suggest_creative, general）
- 会話履歴は `conversations.messages(JSON)` に保存
- DB集計ベース応答 + `actions` / `related_ad_ids` を返却

### Verification
- [x] `python -m py_compile` で追加・更新ファイルの構文チェックOK
- [x] 4エンドポイント実装完了
- [x] main.py へのルーター登録完了

---

## C-R2-2: Notification API -- Completion Report (2026-03-02)

### Status: COMPLETED

### Endpoints Added (8 total)
- `GET /api/v1/rankings/notifications`
- `PUT /api/v1/rankings/notifications/{notification_id}/read`
- `PUT /api/v1/rankings/notifications/read-all`
- `DELETE /api/v1/rankings/notifications/{notification_id}`
- `POST /api/v1/rankings/alert-rules`
- `GET /api/v1/rankings/alert-rules`
- `PUT /api/v1/rankings/alert-rules/{rule_id}`
- `DELETE /api/v1/rankings/alert-rules/{rule_id}`

### Files Added
- `backend/app/api/endpoints/rankings_notifications.py`
- `backend/app/services/notification_service.py`

### Files Updated
- `backend/app/main.py` (router + model imports)
- `backend/app/models/__init__.py` (AlertRule/AlertHistory export)
- `backend/app/api/endpoints/__init__.py`

### Notes
- AlertHistory/AlertRule モデルを再利用
- 未読フィルタ、タイプフィルタ、ページング対応
- NotificationService で system rule 自動作成 + 通知生成ヘルパーを提供

### Verification
- [x] `python -m py_compile` で構文チェックOK
- [x] import smoke test OK

---

## C-R2-4: N+1 / Query Profiling -- Completion Report (2026-03-03)

### Status: COMPLETED

### Changes
- Added SQL profiling helper in `rankings.py`:
  - `_query_counter(session, endpoint)`
- Added optional profiling response field `_sql_profile` to key endpoints:
  - `GET /api/v1/rankings/hit-ads`
  - `GET /api/v1/rankings/score-distribution`
  - `GET /api/v1/rankings/genre-comparison`
  - `GET /api/v1/rankings/dashboard-summary`
- Optimized `GET /api/v1/rankings/hit-ads`:
  - Removed full-table score scan (`session.query(Ad).all()`) used only for dynamic threshold derivation
  - Threshold now derived from ranking result set (query削減)

### Notes
- Local fallback DB in this environment has missing tables, so full E2E measurement baseline could not be reproduced.
- SQL profiling logs are emitted via `sql_query_profile` logger and `_sql_profile` in response (when `profile_sql=true`).

### Verification
- [x] `python -m py_compile` success
- [x] import smoke test success

---

## C-R2-5: Pagination Limits & Timeout Policy -- Completion Report (2026-03-03)

### Status: COMPLETED

### Changes
- Added unified constants in `rankings.py`:
  - `MAX_PAGE_SIZE = 100`
  - `DEFAULT_PAGE_SIZE = 20`
  - `MAX_EXPORT_ROWS = 10000`
- Added validators:
  - `validate_pagination(page, per_page)`
  - `_validate_limit(limit, ...)`
- Applied limit cap (`<=100`) across key list APIs in rankings domain.
- Enforced export row upper bound (`<=10000`) in:
  - `GET /api/v1/rankings/export/csv`
  - `GET /api/v1/rankings/export/json`
  - `GET /api/v1/rankings/export/ads`
- Added timeout policy endpoint:
  - `GET /api/v1/rankings/timeout-policy`

### Verification
- [x] `python -m py_compile` success
- [x] import smoke test success

---

## C-R2-3: External Integration API -- Completion Report (2026-03-03)

### Status: COMPLETED

### Endpoints Added
- `POST /api/v1/integrations/slack/configure`
- `POST /api/v1/integrations/slack/test`
- `POST /api/v1/integrations/webhooks`
- `GET /api/v1/integrations/webhooks`
- `DELETE /api/v1/integrations/webhooks/{webhook_id}`
- `POST /api/v1/integrations/scheduled-export`

### Files Added
- `backend/app/api/endpoints/integrations.py`
- `backend/app/services/integrations/slack_notifier.py`
- `backend/app/services/integrations/webhook_sender.py`
- `backend/app/services/integrations/csv_exporter.py`
- `backend/app/services/integrations/__init__.py`

### Files Updated
- `backend/app/main.py` (router registration)
- `backend/app/api/endpoints/__init__.py`

### Notes
- JSONストレージベースで設定/一覧を永続化（backend/data 配下）
- Webhook送信サービスは HMAC-SHA256 署名ヘッダー対応（`X-VAAP-Signature`）
- scheduled-export 作成時、delivery.type=webhook の場合は best-effort で作成イベントを送信

### Verification
- [x] `python -m py_compile` success
- [x] import smoke test success

---

## C70: Circuit Breaker for External APIs -- Completion Report (2026-03-03)

### Status: COMPLETED

### Changes
- Added new service:
  - `backend/app/services/integrations/circuit_breaker.py`
- Applied circuit breaker to external calls:
  - `backend/app/services/integrations/slack_notifier.py`
  - `backend/app/services/integrations/webhook_sender.py`
- Updated export:
  - `backend/app/services/integrations/__init__.py`

### Behavior
- On repeated failures (threshold=3), breaker opens for 60 seconds.
- While open, calls fail fast with `error: circuit_open`.
- After timeout, one probe request is allowed (half-open), and success closes the breaker.
- API results now include `circuit_breaker` snapshot metadata.

### Verification
- [x] `python -m py_compile` success
- [x] import smoke test success

---

## C71: Structured Request Log Sampling -- Completion Report (2026-03-03)

### Status: COMPLETED

### Files Updated
- `backend/app/main.py`

### Changes
- Added request log sampling policy in API middleware:
  - Always log `5xx`
  - Always log slow requests (`>=1000ms`)
  - Sample `4xx` at 25%
  - Sample success (`2xx/3xx`) at 5%
- Added structured `request_log` payload fields:
  - `sample_reason`, `method`, `path`, `status_code`, `elapsed_ms`,
    `query_present`, `user_agent`, `request_id`, `client_ip`

### Verification
- [x] `python -m py_compile` success
- [x] helper import/runtime smoke check success

---

## C-R3-1: Claude API Integration (AI Chat 本格化) -- Completion Report (2026-03-03)

### Status: COMPLETED

### Files Added
- `backend/app/services/ai/claude_client.py`

### Files Updated
- `backend/app/services/ai/chat_service.py`
- `backend/app/api/endpoints/ai_chat.py`
- `backend/app/services/ai/__init__.py`
- `backend/app/core/config.py`

### Changes
- Claude client を追加し、Anthropic Messages API 呼び出しを実装。
- 利用制限を実装（requests/hour, tokens/day）。
- ChatService を Claude-first + rule-based fallback へ拡張。
- Anthropic APIキーを DB(platform_api_keys) または環境変数から解決。
- RAG コンテキスト（統計・ジャンル・最新広告）をプロンプトに注入。
- SSE endpoint `POST /api/v1/ai-chat/message/stream` を追加。
- レスポンスに `provider` と `usage` を追加（互換性維持）。

### Verification
- [x] `python -m py_compile backend/app/services/ai/claude_client.py backend/app/services/ai/chat_service.py backend/app/api/endpoints/ai_chat.py backend/app/core/config.py backend/app/services/ai/__init__.py` success

---

## C-R3-2: GraphQL API (オプション) -- Completion Report (2026-03-03)

### Status: COMPLETED

### Files Added
- `backend/app/api/graphql/__init__.py`
- `backend/app/api/graphql/router.py`
- `backend/app/api/graphql/schema.py`

### Files Updated
- `backend/app/main.py`
- `backend/requirements.txt`

### Changes
- GraphQL API を追加（`/api/v1/graphql`）。
- Query を実装:
  - `health`
  - `viewer`
  - `dashboardStats`
  - `topHitAds(limit, genre)`
- 認証連携:
  - `get_current_user_sync` を context に注入し `viewer` で参照。
- フォールバック:
  - `strawberry` 未導入時は 503 を返す graceful fallback を実装。

### Verification
- [x] `python -m py_compile backend/app/api/graphql/__init__.py backend/app/api/graphql/router.py backend/app/api/graphql/schema.py backend/app/main.py` success

---

## C-R3-3: API Versioning -- Completion Report (2026-03-03)

### Status: COMPLETED

### Files Added
- `backend/app/api/v2/__init__.py`
- `backend/app/api/v2/router.py`

### Files Updated
- `backend/app/main.py`
- `backend/app/core/config.py`

### Changes
- `/api/v2/` プレフィックスを導入（`api_v2_prefix`）。
- v2 endpoints 追加:
  - `GET /api/v2/version`
  - `POST /api/v2/ai-chat/message`
- Breaking change を v2 に導入:
  - AIチャット応答を `assistant` / `analysis` / `meta` 構造に再編。
- v1 非推奨化:
  - `/api/v1/*` レスポンスに `Deprecation`, `Sunset`, `Link` ヘッダーを付与。
- ルート `/` で `api_versions` を返すよう更新。

### Verification
- [x] `python -m py_compile backend/app/api/v2/__init__.py backend/app/api/v2/router.py backend/app/main.py backend/app/core/config.py` success

---

## C-R3-4: Advanced Scoring Model -- Completion Report (2026-03-03)

### Status: COMPLETED

### Files Added
- `backend/app/services/prediction/ml_scorer.py`

### Files Updated
- `backend/app/services/prediction/__init__.py`
- `backend/app/schemas/prediction.py`
- `backend/app/api/endpoints/predictions.py`

### Changes
- MLベースのヒットスコア推論サービス `MLHitScorer` を追加。
  - 学習器: XGBoost優先（未利用時は sklearn fallback）
  - 目的変数: 既存 `ProductRanking.hit_score`（ルールベースを教師信号として利用）
  - 特徴量: days_running / running状態 / media有無 / spend / 直近7日 metrics
- モデル運用機能を実装:
  - インメモリ版のモデルバージョン管理（`ml-hit-YYYYMMDDHHMMSS`）
  - 24時間以内は再学習抑制
  - 学習データ不足時は rule-only fallback
- A/Bテスト導入:
  - `ab_mode`: `auto|rule|ml`
  - `auto` は user+ad の deterministic bucketing で 50/50 振り分け
- API追加:
  - `POST /api/v1/predictions/hit-score/ml`
  - rule_score / ml_score / selected_score / model_version / ab_arm を返却

### Verification
- [x] `python -m py_compile backend/app/services/prediction/ml_scorer.py backend/app/services/prediction/__init__.py backend/app/schemas/prediction.py backend/app/api/endpoints/predictions.py` success

## 2026-03-03 C50 Progress Update (Phase 1 complete)
- Implemented topic signal helpers: `_extract_topic_signals`, `_topic_matches_filter`
- Added `topic` filter to:
  - `GET /rankings/pro-ranking`
  - `GET /rankings/search/advanced`
- Added topic fields to list/detail responses:
  - `topic_label`, `topic_confidence`, `matched_terms`, `needs_topic_review`
- Verified:
  - `python -m py_compile backend/app/api/endpoints/rankings.py` OK
  - `python -m pytest backend/tests/test_rankings_dpro_parity.py -q` => 8 passed
### C43: Quick Crawl Contract + Quality Fix - COMPLETED (2026-03-03)
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_quick_crawl_contract.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - quick-crawl入力契約に `country` を追加（default `JP`）
  - platforms未指定時デフォルトを `facebook+instagram` として明示
  - 失敗レスポンスに `error_code` / `failure_reason` / `detail` を統一追加
  - 成功レスポンスに `saved_ads_count` / `searchable_ads_count` / 差分カウントを追加
  - API契約テストを新規追加（default契約 / 成功契約 / 失敗契約）
- 検証:
  - `python -m py_compile app/api/endpoints/rankings.py tests/test_quick_crawl_contract.py` 成功
  - `python -m pytest tests/test_quick_crawl_contract.py -q` 成功（3 passed）

## 2026-03-03 C50 Progress Update (Phase 2 complete)
- Added topic facets to `GET /rankings/search/facets` response:
  - `topics: [{ name, count }]`
- Topic counts are derived from normalized topic signals, with `unknown` fallback.
- Verification:
  - `python -m py_compile backend/app/api/endpoints/rankings.py` OK
  - `python -m pytest backend/tests/test_rankings_dpro_parity.py -q` => 9 passed
## 2026-03-03 C50 Completion Update
- 追加テスト: `backend/tests/test_c50_retry_topic_contract.py`
  - `needs_media_retry` 対象が `/batch-extract-media` で dispatch されるケース
  - pending + retry 候補が混在するケース
  - `topic` フィルタで期待集合が返り、詳細に topic fields が出るケース
- 実装確認:
  - `/batch-extract-media` が `retry_candidates_dispatched` を返却
  - 再抽出失敗時 `last_media_retry_error` を ad_metadata に保存
  - 一覧/詳細に `topic_label/topic_confidence/matched_terms/needs_topic_review` を返却
- 検証:
  - `python -m pytest tests/test_c50_retry_topic_contract.py -q` 成功（3 passed）
## 2026-03-03 C44 Completion Update
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_c44_topic_classification_contract.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - `POST /rankings/classify-topic` を追加（ad_id or raw text 入力）
  - 出力: `topic_tags`, `confidence`, `evidence_terms`, `hit_drivers`, `model_version`, `scores`
  - ad_id指定時、`ad_metadata.topic_tags/topic_confidence/topic_evidence/hit_drivers` を保存
  - `GET /rankings/topic-gap-report` を追加（expected/classified/gap/false_negative_candidates）
  - トピック辞書に `ec_d2c` / `app` を追加
- 検証:
  - `python -m py_compile app/api/endpoints/rankings.py tests/test_c44_topic_classification_contract.py` 成功
  - `python -m pytest tests/test_c44_topic_classification_contract.py -q` 成功（3 passed）

## 2026-03-03 C51 Completion Update
- Task: `C51_quick_crawl_resilience_guardrails.md`
- 変更:
  - `backend/app/services/crawling/crawler_manager.py`
  - `backend/app/api/endpoints/rankings.py`
  - 非正規 crawler result（None/non-list/invalid item）で quick-crawl 全体失敗しないガードを追加
  - `skipped_invalid_count` を quick-crawl レスポンス/進捗詳細へ追加
- テスト:
  - `backend/tests/test_quick_crawl_contract.py` に invalid-result 回帰ケースを追加
- 検証:
  - `python -m pytest backend/tests/test_quick_crawl_contract.py -q` => 4 passed

## 2026-03-03 C52 Completion Update
- Task: `C52_crawl_status_diagnostics_api.md`
- 変更:
  - `backend/app/api/endpoints/rankings.py`
  - `GET /rankings/crawl-status/diagnostics` 追加
  - helper: `_classify_zero_save_cause`, `_ensure_platform_list`
- 検証:
  - `python -m pytest backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q` => 16 passed

## 2026-03-03 C53 Completion Update
- Task: `C53_platform_aware_recovery_strategy.md`
- 変更:
  - `backend/app/api/endpoints/rankings.py`
  - helper追加: `_platform_fetch_counts`, `_build_recovery_platform_batches`
  - recoveryで 0件/低件数媒体を先行バッチ再試行するロジックを追加
- 検証:
  - `python -m pytest backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q` => 17 passed

## 2026-03-03 C54 Completion Update
- Task: `C54_dynamic_platform_limit_api_integration.md`
- 変更:
  - `backend/app/api/endpoints/rankings.py`
  - `_crawl_platforms_no_expand` に `per_platform_limits` を追加
  - quick-crawl response/progress_detail に `platform_limits` を追加
- 検証:
  - `python -m pytest backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q` => 18 passed

## 2026-03-03 C55 Completion Update
- Task: `C55_platform_learning_feedback_api.md`
- 変更:
  - `backend/app/api/endpoints/rankings.py`
  - 学習辞書 load/save + learned query 優先 recovery + learning metrics 追加
  - diagnostics summary に `learned_attempts`, `learned_success_rate` を追加
- 検証:
  - `python -m pytest backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q` => 19 passed

## 2026-03-03 C56 Completion Update
- Task: `C56_query_source_diagnostics_api.md`
- 変更:
  - `backend/app/api/endpoints/rankings.py`
  - recovery attempt に `query_source` を追加
  - diagnostics summary に platform_expansion 指標を追加
- 検証:
  - `python -m pytest backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q` => 20 passed

## 2026-03-03 C57 Completion Update
- Task: `C57_learning_dictionary_prune_api_and_metrics.md`
- 変更:
  - `backend/app/api/endpoints/rankings.py`
  - `POST /rankings/learning/prune` 追加
  - diagnostics summary に `learning_entries` を追加
  - recovery前の自動prune適用
- 検証:
  - `python -m pytest backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q` => 21 passed

## 2026-03-03 C58 Completion Update
- Task: `C58_scheduled_runner_meta_boost_integration.md`
- 変更:
  - `backend/scripts/scheduled_crawl_runner.py`
  - crawl phase に `run_daily_meta_instagram_boost.py` を統合
- 検証:
  - `python -m py_compile backend/scripts/scheduled_crawl_runner.py` 成功

## 2026-03-03 C59 Completion Update
- Task: `C59_runner_phase_status_contract.md`
- 変更:
  - `backend/scripts/scheduled_crawl_runner.py`
  - phase return contract に `status` を追加し判定を統一
- 検証:
  - `python -m pytest backend/tests/test_scheduled_crawl_runner.py backend/tests/test_meta_instagram_boost.py backend/tests/test_rankings_dpro_parity.py backend/tests/test_quick_crawl_contract.py -q` => 24 passed

## 2026-03-03 C Open Slot DoD Closure Update
- Contract/API regression re-validation executed:
  - `python -m pytest tests/test_quick_crawl_contract.py tests/test_c50_retry_topic_contract.py tests/test_c44_topic_classification_contract.py tests/test_c46_quality_gate_contract.py -q`
  - result: `11 passed`
- Open Slot DoD requirement `APIテスト + E2Eテストで再発防止` validated together with frontend E2E pass set.

## 2026-03-03 C45 Completion Update
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_c45_dictionary_online_learning_contract.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - `POST /rankings/dictionary/suggest` 追加（候補語提案）
  - `POST /rankings/dictionary/review` 追加（adopt/hold/reject 永続化 + adopt時辞書反映）
  - `POST /rankings/knowledge/rebuild` 追加（知識スナップショット生成・版管理）
  - JSON永続化ファイル:
    - `backend/data/topic_dictionary_reviews.json`
    - `backend/data/topic_knowledge_snapshots.json`
- 検証:
  - `python -m py_compile app/api/endpoints/rankings.py tests/test_c45_dictionary_online_learning_contract.py` 成功
  - `python -m pytest tests/test_c45_dictionary_online_learning_contract.py -q` 成功（3 passed）

## 2026-03-03 C48 Completion Update
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_c48_ad360_contract.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - `GET /rankings/ad360/{ad_id}` を追加
  - 固定セクション `core/creative/text/analysis/lp/quality` を返却
  - 各セクションに `missing_fields[]` を付与（欠損時も構造不変）
- 検証:
  - `python -m py_compile app/api/endpoints/rankings.py tests/test_c48_ad360_contract.py` 成功
  - `python -m pytest tests/test_c48_ad360_contract.py -q` 成功（3 passed）

## 2026-03-03 C49 Completion Update
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_c49_meta_extraction_contract.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - `GET /rankings/meta-extraction/{ad_id}` 追加（creative_urls/text_fields/extract_source/quality_score/missing_fields）
  - `POST /rankings/meta-extraction/{ad_id}/retry` 追加（API→Browser→Fallback 段階実行）
  - 失敗時 `failure_reason_code` を標準化して返却
- 検証:
  - `python -m py_compile app/api/endpoints/rankings.py tests/test_c49_meta_extraction_contract.py` 成功
  - `python -m pytest tests/test_c49_meta_extraction_contract.py -q` 成功（3 passed）

## 2026-03-03 C47 Closeout Update
- C43/C44/C45/C46/C48/C49 実装 + 契約テスト通過により Full-Cycle API Taskpack を完了化。
- 代表回帰:
  - `python -m pytest tests/test_c44_topic_classification_contract.py tests/test_c45_dictionary_online_learning_contract.py tests/test_c46_quality_gate_contract.py tests/test_c48_ad360_contract.py tests/test_c49_meta_extraction_contract.py -q`

## 2026-03-03 C41/C42 Completion Update
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_c41_c42_consistency_lp_contract.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - `GET /rankings/quick-crawl/{job_id}/consistency` 追加
  - `GET /rankings/lp-info/{ad_id}` 追加
  - `POST /rankings/lp-info/refresh` 追加
  - `quick-crawl` レスポンスに `recovery_action` / `completed_at` を追加
- 検証:
  - `python -m pytest tests/test_quick_crawl_contract.py tests/test_c41_c42_consistency_lp_contract.py -q` 成功（7 passed）

## 2026-03-03 C39 Contract Test Update
- 追加ファイル:
  - `backend/tests/test_c39_notification_contract.py`
- 検証内容:
  - notifications CRUD + unread_count
  - alert-rules CRUD
  - mark-all-read と NotificationService 経路の整合
- 検証:
  - `python -m pytest tests/test_c39_notification_contract.py -q` 成功（2 passed）

## 2026-03-03 C40 Contract Test + Retry Update
- 変更ファイル:
  - `backend/app/services/integrations/webhook_sender.py`
  - `backend/tests/test_c40_external_integration_contract.py`
- 実装/検証内容:
  - WebhookSender: 例外/5xxで最大3回リトライを追加
  - HMAC署名ヘッダ `X-VAAP-Signature` を契約テストで検証
  - Slack configure/test、Webhook CRUD、scheduled-export 作成を契約テストで検証
- 検証:
  - `python -m pytest tests/test_c40_external_integration_contract.py -q` 成功（3 passed）

## 2026-03-03 C38 Contract Test Update
- 追加ファイル:
  - `backend/tests/test_c38_ai_chat_contract.py`
- 検証内容:
  - IntentClassifier の主要ルーティング
  - ChatService の会話永続化（新規/継続）
  - Claude経路の provider/usage/structured response
- 検証:
  - `python -m pytest tests/test_c38_ai_chat_contract.py -q` 成功（3 passed）

## 2026-03-03 C-R2-2/C-R2-3 Checklist Closure Update
- Evidence tests:
  - `python -m pytest tests/test_c39_notification_contract.py tests/test_c40_external_integration_contract.py -q`
  - result: `5 passed`
- Checklist close:
  - `C_R2_2_notification_api.md` completed
  - `C_R2_3_external_integration.md` completed

## 2026-03-03 C43/C44/C46/C50 Checklist Closure Update
- Evidence tests:
  - `python -m pytest tests/test_quick_crawl_contract.py tests/test_c44_topic_classification_contract.py tests/test_c46_quality_gate_contract.py tests/test_c50_retry_topic_contract.py -q`
  - result: `12 passed`
- Checklist close:
  - `C43_quick_crawl_contract_and_quality_fix.md`
  - `C44_topic_classification_api_and_gap_metrics.md`
  - `C46_quality_gate_api_for_crawl_and_classification.md`
  - `C50_media_retry_dispatch_and_topic_api.md`

## 2026-03-03 C-R2-4/C-R2-5 Checklist Closure Update
- status.md 内の既存完了報告（C-R2-4: N+1/Query Profiling, C-R2-5: Pagination/Timeout）と実装証跡を根拠に、個別タスク票の未チェック項目を完了化。
- Checklist close:
  - `C_R2_4_n_plus_1_fix.md`
  - `C_R2_5_pagination_limits.md`

## 2026-03-05 C92 Completion Update
- Task: `CI-128 / C92 APIレスポンスの snake_case/camelCase 二重出力を標準化`
- 変更ファイル:
  - `backend/app/core/response_case.py`
  - `backend/app/main.py`
  - `backend/app/core/config.py`
  - `backend/tests/test_response_case_dual_output.py`
- 実装内容:
  - snake_case/camelCase を相互に補完する共通変換 `with_dual_case_keys` を追加
  - JSONレスポンス（cookie未付与）に対し、ミドルウェアで二重キー出力を自動適用
  - 設定フラグ `api_dual_case_output`（default: true）を追加
- 検証:
  - `python -m py_compile app/main.py app/core/config.py app/core/response_case.py tests/test_response_case_dual_output.py` 成功
  - `python -m pytest tests/test_response_case_dual_output.py -q` 成功（4 passed）

## 2026-03-05 C93 Completion Update
- Task: `CI-132 / C93 APIレスポンス圧縮(gzip/brotli)を標準化`
- 変更ファイル:
  - `backend/app/core/response_compression.py`
  - `backend/app/main.py`
  - `backend/app/core/config.py`
  - `backend/tests/test_response_compression.py`
- 実装内容:
  - 圧縮判定/エンコーディング選択/圧縮処理を共通化（gzip + brotli(利用可能時)）
  - APIミドルウェアで `Accept-Encoding` に応じた圧縮を標準適用
  - `Vary: Accept-Encoding` を統一付与、`Content-Length` を再計算前提で除去
  - 圧縮制御フラグを設定に追加（enabled/min_size/gzip/brotli/level）
- 検証:
  - `python -m py_compile app/main.py app/core/config.py app/core/response_compression.py tests/test_response_compression.py` 成功
  - `python -m pytest tests/test_response_compression.py tests/test_response_case_dual_output.py -q` 成功（8 passed）

## 2026-03-05 C94 Completion Update
- Task: `CI-136 / C94 GraphQL ゲートウェイ導入検討・PoC`
- 変更ファイル:
  - `backend/tests/test_graphql_gateway_poc.py`
- 実装内容:
  - GraphQL ルーターの契約テストを追加（利用可時/未導入時フォールバック両対応）
  - `/api/v1/graphql` の疎通を PoC として自動検証
- 補足:
  - 現在のテスト環境では `strawberry` 未導入のため、503 フォールバック契約を検証
  - `strawberry` 導入環境では `schema` 実クエリ（health/viewer/topHitAds）検証コードも有効化
- 検証:
  - `python -m pytest tests/test_graphql_gateway_poc.py -q` 成功（1 passed）

## 2026-03-05 C95 Completion Update
- Task: `CI-140 / C95 APIゲートウェイでのリクエスト認証基盤導入`
- 変更ファイル:
  - `backend/app/core/gateway_auth.py`
  - `backend/app/main.py`
  - `backend/app/core/config.py`
  - `backend/tests/test_gateway_auth.py`
- 実装内容:
  - APIキー認証ヘルパーを追加（`x-api-key` / `Authorization: Bearer`）
  - 保護対象パス判定（default: `/api/v2,/api/v1/graphql`）を追加
  - `api_gateway_auth_enabled` が有効時、未認証アクセスを 401 で遮断
  - 認証キー/保護パスを環境設定で制御可能にした
- 検証:
  - `python -m py_compile app/main.py app/core/config.py app/core/gateway_auth.py tests/test_gateway_auth.py` 成功
  - `python -m pytest tests/test_gateway_auth.py tests/test_graphql_gateway_poc.py tests/test_response_compression.py tests/test_response_case_dual_output.py -q` 成功（14 passed）

## 2026-03-05 C96 Completion Update
- Task: `CI-003 APIエラーレスポンス仕様の統一`
- 変更ファイル:
  - `backend/app/main.py`
- 実装内容:
  - エラーレスポンス共通フォーマットを `code/message/request_id/details` に統一
  - `RequestValidationError` / `SQLAlchemyError` / 汎用例外で共通エンベロープを返却
  - `x-request-id` を優先採用し、未指定時はUUIDを生成
  - 全レスポンスヘッダに `X-Request-ID` を付与
  - APIゲートウェイ認証エラー(401)も同一フォーマットに統一
- 検証:
  - `python -m py_compile app/main.py` 成功
  - `python -m pytest tests/test_exception_handlers.py tests/test_gateway_auth.py -q` 成功（13 passed）

## 2026-03-05 C97 Completion Update
- Task: `CI-056 バックエンド例外分類（user/system/external）を統一`
- 変更ファイル:
  - `backend/app/main.py`
- 実装内容:
  - 例外分類ヘルパー `_classify_exception` を追加
  - 共通エラーエンベロープに `category` を追加
  - validation/user, db/system, external依存例外分類を統一
  - 既存の `request_id` 統一フォーマットと併せて返却
- 検証:
  - `python -m py_compile app/main.py` 成功
  - `python -m pytest tests/test_exception_handlers.py tests/test_gateway_auth.py -q` 成功（13 passed）

## 2026-03-05 C98 Completion Update
- Task: `CI-082 キャッシュキーのバージョニング規約を導入`
- 変更ファイル:
  - `backend/app/core/cache_key.py`
  - `backend/app/core/config.py`
  - `backend/app/services/ai/claude_client.py`
  - `backend/app/services/ai/chat_service.py`
  - `backend/tests/test_cache_key_versioning.py`
- 実装内容:
  - 共通キー生成 `build_cache_key(namespace, version, parts)` を追加
  - 設定値 `cache_key_version`（default: `v1`）を追加
  - Claude利用制限の内部キャッシュキーを `namespace:version:parts` 規約に統一
  - ChatService から `cache_key_version` を ClaudeClient に注入
- 検証:
  - `python -m py_compile app/core/cache_key.py app/core/config.py app/services/ai/claude_client.py app/services/ai/chat_service.py tests/test_cache_key_versioning.py` 成功
  - `python -m pytest tests/test_cache_key_versioning.py tests/test_gateway_auth.py tests/test_response_compression.py -q` 成功（11 passed）

## 2026-03-05 C99 Completion Update
- Task: `CI-086 DBクエリタイムアウトガードをAPI層へ導入`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/app/core/config.py`
- 実装内容:
  - `rankings.py` に DBタイムアウトガードを追加
    - PostgreSQL: `SET LOCAL statement_timeout`
    - SQLite: `PRAGMA busy_timeout`
  - すべての `/rankings` セッション開設をラッパー化
    - `_db_session_scope()` / `_open_session()`
  - 設定値 `api_db_query_timeout_ms`（default: 30000ms）を追加
- 検証:
  - `python -m py_compile app/api/endpoints/rankings.py app/core/config.py` 成功
  - `python -m pytest tests/test_rankings_dpro_parity.py tests/test_quick_crawl_contract.py -q` 成功（21 passed）

## 2026-03-05 C100 Completion Update
- Task: `CI-015 頻出GETレスポンスの短期キャッシュ導入`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_short_cache.py`
- 実装内容:
  - `/rankings/score-distribution` に 20秒TTL の短期キャッシュを追加
  - `/rankings/dashboard-summary` に 20秒TTL の短期キャッシュを追加
  - `profile_sql=true` 時はキャッシュをバイパス
  - キャッシュキーは `build_cache_key(namespace, version, parts)` 規約を利用
- 検証:
  - `python -m py_compile app/api/endpoints/rankings.py app/core/config.py tests/test_rankings_short_cache.py` 成功
  - `python -m pytest tests/test_rankings_short_cache.py tests/test_rankings_dpro_parity.py tests/test_quick_crawl_contract.py -q` 成功（22 passed）

## 2026-03-05 C101 Completion Update
- Task: `CI-032 API契約テストを追加（schema一致）`
- 変更ファイル:
  - `backend/tests/test_api_contract_rankings.py`
  - `backend/app/api/endpoints/rankings.py`（SQLite busy_timeout適用修正）
- 実装内容:
  - `/rankings/timeout-policy` 契約テスト追加
  - `/rankings/dashboard-summary` 契約テスト追加（空データ時/通常時の両契約）
  - `/rankings/score-distribution` 契約テスト追加（空データ時/通常時の両契約）
  - DBタイムアウトガードのSQLite適用を `PRAGMA busy_timeout` 形式へ修正
- 検証:
  - `python -m py_compile app/api/endpoints/rankings.py tests/test_api_contract_rankings.py` 成功
  - `python -m pytest tests/test_api_contract_rankings.py tests/test_rankings_short_cache.py tests/test_rankings_dpro_parity.py tests/test_quick_crawl_contract.py -q` 成功（25 passed）

## 2026-03-08 C102 Completion Update
- Task: `CI-040 検索APIに入力バリデーション統一`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_search_api_validation_contract.py`
- 実装内容:
  - `_normalize_search_text()` を追加し、空白のみクエリを 400 で早期拒否
  - `/rankings/search`, `/autocomplete`, `/smart-autocomplete`, `/search/suggest` に適用
  - `/autocomplete` の `field` を enum 検証対象に追加
  - `/search/facets`, `/advanced-search` の任意クエリ文字列も正規化
- 検証:
  - `python -m pytest backend/tests/test_search_api_validation_contract.py -q` 成功（11 passed）
  - `python -m pytest backend/tests/test_api_contract_rankings.py -q` 成功（3 passed）

## 2026-03-08 C103 Completion Update
- Task: `CI-096 エンドポイント別の入力スキーマ厳格化`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_search_collections_validation.py`
- 実装内容:
  - `_require_string_filter_fields()` を追加
  - `search-collections` 用 filter payload で string/object 想定フィールドの型を明示検証
  - 数値・配列・不正 nested shape を文字列化せず 400 で拒否
- 検証:
  - `python -m pytest backend/tests/test_search_collections_validation.py -q` 成功（4 passed）
  - `python -m pytest backend/tests/test_search_api_validation_contract.py -q` 成功（11 passed）

## 2026-03-08 C96 Creative Library Contract Hardening Update
- Task: `C96_creative_library_contract_and_error_codes.md`
- 変更ファイル:
  - `backend/app/schemas/ad.py`
  - `backend/app/api/endpoints/ads.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/app/api/endpoints/media.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
  - `backend/tests/test_c96_creative_library_contract.py`
- 実装内容:
  - `build_media_status_payload()` を追加し、`viewable/downloadable/has_lp/primary_type/missing_reasons` の固定構造を共通化
  - `ads.py` / `rankings.py` / `media.py` を同 helper 利用へ統一
  - `rankings` 系レスポンスに `media_status` を dict で同梱し、旧文字列互換は `media_cache_status` に分離
  - `media/status/{ad_id}` にも同じ `media_status` を追加
  - `bulk-download` / `bulk-download-file` / `download` 系で `failure_reason_code`
    - `invalid_ad_ids`
    - `no_cached_media`
    - `zip_creation_failed`
    - `download_file_missing`
    を返すよう標準化
  - `API_CONTRACT_REGISTRY.md` に creative library 契約と bulk-download error 例を追記
- 検証:
  - `python -m pytest backend/tests/test_c96_creative_library_contract.py -q` => 3 passed
  - `python -m pytest backend/tests/test_a101_creative_library_audit.py backend/tests/test_a48_topic_enrichment.py -q` => 4 passed

## 2026-03-08 C104 Completion Update
- Task: `CI-044 /rankings のレスポンスサイズ削減`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_products_compact.py`
- 実装内容:
  - `/rankings/products` に `compact=true` オプションを追加
  - compact 時は `score_breakdown`, `creative_analysis`, `download_urls`, `data_quality`, 長文テキスト系など重い付加フィールドを省略
  - fallback products レスポンスにも同じ compact ルールを適用
  - 既定レスポンスは維持し、opt-in で軽量化できる形にした
- 検証:
  - `python -m pytest backend/tests/test_rankings_products_compact.py -q` 成功（2 passed）
  - `python -m pytest backend/tests/test_api_contract_rankings.py -q` 成功（3 passed）

## 2026-03-08 C105 Completion Update
- Task: `CI-100 高負荷APIのフェイルソフト応答を整備`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_fail_soft.py`
- 実装内容:
  - `/rankings/score-distribution` と `/rankings/dashboard-summary` に fail-soft を追加
  - 通常リクエストで fresh compute が失敗した場合:
    - stale short-cache があれば `_degraded=true`, `_degraded_reason=stale_cache` 付きで返却
    - cache が無ければ最小骨格の degraded payload を返却
  - `profile_sql=true` は診断用途のため fail-soft 対象外にして例外可視性を維持
  - short cache は期限切れでも stale fallback 用に内部保持する形へ調整
- 検証:
  - `python -m pytest backend/tests/test_rankings_fail_soft.py -q` 成功（2 passed）
  - `python -m pytest backend/tests/test_rankings_short_cache.py -q` 成功（1 passed）
  - `python -m pytest backend/tests/test_api_contract_rankings.py -q` 成功（3 passed）

## 2026-03-08 C106 Completion Update
- Task: `CI-108 API保護のレート制御ポリシーを統一`
- 変更ファイル:
  - `backend/app/core/rate_limit.py`
  - `backend/app/core/config.py`
  - `backend/app/api/endpoints/auth.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rate_limit.py`
  - `backend/tests/test_rankings_rate_limit.py`
- 実装内容:
  - 共通 in-memory rate limiter を `app.core.rate_limit` に切り出し
  - policy 文字列 (`N/minute`, `N/hour`) の共通パーサを追加
  - auth API は共通 helper 利用へ移行しつつ既存 `_check_rate_limit` / store 参照を後方互換維持
  - rankings API に read/heavy 2系統のポリシーを追加
    - settings: `rate_limit_rankings_read` default `60/minute`
    - settings: `rate_limit_rankings_heavy` default `20/minute`
  - `/rankings/products`, `/hit-ads`, `/search`, `/dashboard-summary`, `/score-distribution` に共通 rate limit を適用
  - 429 時 `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Window` を返却
- 検証:
  - `python -m pytest backend/tests/test_rate_limit.py -q` 成功（17 passed）
  - `python -m pytest backend/tests/test_rankings_rate_limit.py -q` 成功（2 passed）
  - `python -m pytest backend/tests/test_api_contract_rankings.py -q` 成功（3 passed）

## 2026-03-08 C107 Completion Update
- Task: `CI-112 内部API呼び出しのトレースID連携を統一`
- 変更ファイル:
  - `backend/app/core/trace.py`
  - `backend/app/main.py`
  - `backend/app/tasks/dispatcher.py`
  - `backend/tests/test_trace_propagation.py`
- 実装内容:
  - contextvar ベースの共通 trace helper を追加
  - HTTP middleware で `request_id` を trace context にセットし、レスポンスヘッダに `X-Trace-ID` を追加
  - request sampling log も header 由来ではなく解決済み `request.state.request_id` を記録
  - `dispatch_task()` が current trace を `trace_id` として自動注入
  - Celery/SQS dispatch log と SQS message body に `trace_id` を載せるようにした
- 検証:
  - `python -m pytest backend/tests/test_trace_propagation.py -q` 成功（3 passed）
  - `python -m pytest backend/tests/test_rate_limit.py -q` 成功（17 passed）
  - `python -m pytest backend/tests/test_api_contract_rankings.py -q` 成功（3 passed）

## 2026-03-08 C108 Completion Update
- Task: `CI-116 エラーコード辞書と運用対応表を整備`
- 変更ファイル:
  - `backend/app/core/error_codes.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_error_codes.py`
- 実装内容:
  - stable な API error / failure reason code を `app.core.error_codes` に集約
  - 各 code について `category`, `http_status`, `scope`, `message`, `operator_action` を定義
  - `/rankings/error-codes` を追加し、運用向け参照 API として辞書を返却
  - `category` / `scope` フィルタで一次切り分けしやすい形に整理
  - 対象には global exception code、quality gate reason code、media failure code、cache degraded code を含めた
- 検証:
  - `python -m pytest backend/tests/test_rankings_error_codes.py -q`
  - `python -m pytest backend/tests/test_api_contract_rankings.py -q`

## 2026-03-08 C109 Completion Update
- Task: `CI-117 画面単位のローディング時間計測を可視化`
- 変更ファイル:
  - `frontend/src/app/page.tsx`
  - `frontend/src/lib/screenLoadMetrics.ts`
  - `frontend/src/lib/screenLoadMetrics.test.ts`
  - `frontend/vitest.unit.config.ts`
- 実装内容:
  - view 切替ごとに画面表示完了までの経過時間を計測する screen load metrics を追加
  - `page.tsx` で current view の切替開始時刻を保持し、画面 mount 完了時に latest/avg/max/count を更新
  - metrics は localStorage (`vaap-screen-load-metrics:v1`) に保持し、再訪後も傾向を参照可能にした
  - desktop header に current screen の latest/avg と、履歴上の最遅 screen を表示する軽量テレメトリを追加
  - frontend utility test 用に storybook 依存から分離した unit Vitest config を追加
- 検証:
  - `npx vitest run --config vitest.unit.config.ts src/lib/screenLoadMetrics.test.ts` 成功（3 passed）
  - `npx tsc --noEmit` 成功

## 2026-03-08 C110 Completion Update
- Task: `CI-118 メディア抽出器のバージョン管理を導入`
- 変更ファイル:
  - `backend/app/services/media_extraction.py`
  - `backend/app/tasks/media_tasks.py`
  - `backend/app/tasks/crawl_tasks.py`
  - `backend/app/api/endpoints/ads.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_media_extractor_versioning.py`
- 実装内容:
  - `MediaExtractor` の current version / changelog を取得する helper を追加
  - heavy extraction task と inline extraction path で `extractor_version` を共通 metadata に保存
  - `extractor_version_history` を保持して、どの version / source / status で処理したか追跡可能にした
  - `/rankings/media-extraction-status` に current version, version breakdown, changelog を追加
  - `/rankings/media-extraction-ads` に `extractor_version`, `extractor_version_history`, `creative_fetch_source` を追加
- 検証:
  - `python -m pytest backend/tests/test_media_extractor_versioning.py -q` 成功（2 passed）
  - `python -m pytest backend/tests/test_api_contract_rankings.py -q` 成功（3 passed）

## 2026-03-08 C111 Completion Update
- Task: `CI-120 API互換性ガイドラインのレビュープロセス整備`
- 変更ファイル:
  - `docs/API_COMPATIBILITY_GUIDELINES.md`
  - `.agent-tasks/api_compatibility_review_manifest.json`
  - `backend/scripts/api_compatibility_review.py`
  - `backend/tests/test_api_compatibility_review.py`
  - `README.md`
- 実装内容:
  - API 変更時の互換性ルール、change class、review checklist、rollout policy を文書化
  - critical contract tests と必須 review question を manifest 化
  - review assets の欠落を検出する checker script を追加
  - guide section と critical contract test の存在を pytest で固定し、運用フローが壊れないようにした
- 検証:
  - `python backend/scripts/api_compatibility_review.py --check` 成功
  - `python -m pytest backend/tests/test_api_compatibility_review.py -q` 成功（2 passed）

## 2026-03-08 C99/C100 Completion Update
- Task:
  - `C99 LP解決情報契約と reason code registry の固定`
  - `C100 Creative Library 契約テストとレスポンス例の整備`
- 変更ファイル:
  - `backend/app/schemas/ad.py`
  - `backend/app/api/endpoints/ads.py`
  - `backend/app/api/endpoints/media.py`
  - `backend/tests/test_c96_creative_library_contract.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - `lp_info` 共通ビルダーを追加し、`resolved_url / redirect_chain / final_domain / http_status` を固定
  - `lp_status` を `alive / redirect / dead / unreachable / unresolved` に正規化
  - Creative Library の reason code registry を共通化し、`media_status.missing_reasons` と `bulk-download.skipped_reasons` を同じ語彙で返すようにした
  - `/media/bulk-download` に `requested_count / downloaded_count / skipped_reasons` を追加し、既存 `file_count / skipped_reason_code` は後方互換として維持
  - API_CONTRACT_REGISTRY に `media_status` / `lp_info` / `bulk-download` の最新サンプルを追記
- 検証:
  - `python -m pytest tests/test_c96_creative_library_contract.py -q` 成功（5 passed）
  - `python -m pytest tests/test_c41_c42_consistency_lp_contract.py tests/test_api_contract_ads.py tests/test_api_contract_media.py -q` 成功（19 passed）

## 2026-03-08 C80 Completion Update
- Task: `CI-092 APIごとのSLO定義と違反検知を導入`
- 変更ファイル:
  - `backend/app/core/slo.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_slo_status.py`
- 実装内容:
  - endpoint pattern ごとの rolling SLO metrics を in-memory で保持し、`p95_ms` と `error_rate` を計算するよう拡張
  - 単発遅延だけでなく、window 10件以上の `p95` 逸脱と `5xx error rate` 逸脱で構造化 warning を出すようにした
  - `/api/v1/rankings/slo-status` を追加し、全 endpoint 定義または任意 path の current SLO status を参照可能にした
  - `default_target`, `bucket`, `targets`, `window`, `status` を返す契約をテストで固定
- 検証:
  - `python -m pytest tests/test_rankings_slo_status.py tests/test_api_contract_rankings.py tests/test_rankings_error_codes.py -q` 成功（8 passed）

## 2026-03-08 C72 Completion Update
- Task: `CI-066 OpenAPI仕様の自動生成と差分検知を導入`
- 変更ファイル:
  - `backend/scripts/openapi_diff.py`
  - `backend/tests/test_openapi_diff.py`
- 実装内容:
  - `app.main.app.openapi()` から current spec を生成し、コミット済み `backend/openapi.json` と比較する専用スクリプトを追加
  - added/removed/changed path と schema 数を集計し、PR で読める差分サマリを text/json で出力可能にした
  - `--check` で committed spec が stale な場合に non-zero 終了、`--write` で current spec を再生成できるようにした
  - 比較ロジックを pytest で固定し、差分検知の回帰を防止

## 2026-03-08 C73 Completion Update
- Task: `CI-070 分析系クエリの負荷分離方針を導入`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_load_separation.py`
- 実装内容:
  - rankings API 内に `ANALYTICS_LOAD_POLICY` を追加し、primary realtime と analytics deferred の 2 lane に endpoint を分類
  - `/api/v1/rankings/load-separation-policy` を追加し、lane / path / goal / strategy を返す運用向け参照 API を実装
  - primary 系には short cache / fail-soft / profile_sql bypass、analysis 系には heavy rate-limit / aggregate timeout 前提を明文化
  - path filter 付き契約テストを追加し、ポリシー定義が壊れないように固定
- 検証:
  - `python -m pytest tests/test_rankings_load_separation.py tests/test_api_contract_rankings.py -q` 成功（5 passed）

## 2026-03-08 C74 Completion Update
- Task: `CI-074 ランキング計算パラメータの検証枠組みを整備`
- 変更ファイル:
  - `backend/app/services/ranking/ranking_service.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_score_parameter_validation.py`
- 実装内容:
  - score parameter の default 定義と `validate_score_parameters()` を追加し、weights / thresholds の安全な比較条件を共通化
  - `compute_hit_score()` / `compute_hit_score_with_details()` に candidate parameter 適用経路を追加し、既定値では現行挙動を維持
  - `/api/v1/rankings/score-parameter-validation` を追加し、指定広告群に対して baseline と candidate の `hit_score / hit_level / delta` を比較できるようにした
  - invalid candidate（例: `mega_hit_score < hit_score`）は 400 で早期拒否する契約を追加
- 検証:
  - `python -m pytest tests/test_rankings_score_parameter_validation.py tests/test_api_contract_rankings.py tests/test_smoke.py -q` 成功（25 passed）

## 2026-03-08 C77 Completion Update
- Task: `CI-090 API廃止ポリシー（deprecation）を運用化`
- 変更ファイル:
  - `docs/API_COMPATIBILITY_GUIDELINES.md`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_deprecations.py`
- 実装内容:
  - deprecation registry を `rankings.py` に追加し、path / replacement / sunset_date / migration_doc / status / note を API で参照可能にした
  - `/api/v1/rankings/deprecations` を追加し、特定 path の filter を含めて運用確認しやすい形にした
  - API compatibility guideline に `Deprecation Policy` セクションを追加し、ヘッダ要件と registry 必須項目を明文化した
- 検証:
  - `python -m pytest tests/test_rankings_deprecations.py tests/test_api_compatibility_review.py tests/test_api_contract_rankings.py -q` 成功（8 passed）

## 2026-03-08 C90 Completion Update
- Task: `CI-123 抽出結果の妥当性スコアリングを導入`
- 変更ファイル:
  - `backend/app/services/ranking/extraction_scorer.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_extraction_validity_scoring.py`
- 実装内容:
  - extraction scorer を単純な素材有無スコアから、creative payload / metadata fidelity / semantic alignment / traceability の4軸 validity score に拡張
  - `/api/v1/rankings/extraction-quality` に `validity_score`, `validity_reasons`, `avg_validity_score` を返すよう変更
  - `/api/v1/rankings/media-extraction-ads` に `extract_validity_score`, `extract_validity_reasons` を追加し、retry/監査画面で再利用できるようにした
- 検証:
  - `python -m pytest tests/test_extraction_validity_scoring.py tests/test_media_extractor_versioning.py tests/test_c46_quality_gate_contract.py -q` 成功（6 passed）

## 2026-03-08 C91 Completion Update
- Task: `CI-125 日次Top30のヒット判定品質チェックを追加`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_top_hit_quality_review.py`
- 実装内容:
  - `/api/v1/rankings/top-hit-quality-review` を追加し、最新 Top-N 広告について stored 判定と recompute 判定の差分を返すようにした
  - `hit_score / hit_level / score_delta / level_changed / hit_flipped` を item 単位で返し、日次レビューの差分確認に使える形へ整理
  - summary に `score_drift_count / level_drift_count / hit_flip_count` を追加し、日次ログ・監査で変化量を把握しやすくした
- 検証:
  - `python -m pytest tests/test_top_hit_quality_review.py tests/test_api_contract_rankings.py tests/test_smoke.py -q` 成功（25 passed）

## 2026-03-08 C86 Completion Update
- Task: `CI-104 ランキング重み変更のA/B検証基盤を整備`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_score_parameter_ab_review.py`
  - `backend/tests/test_api_contract_rankings.py`
- 実装内容:
  - score parameter 比較ロジックを内部 helper に整理し、既存 `/api/v1/rankings/score-parameter-validation` からも再利用する形にした
  - `/api/v1/rankings/score-parameter-ab-review` を追加し、baseline/candidate の平均 score・hit 件数・level 分布・昇格/降格広告を集計できるようにした
  - `summary / distribution / changed_ads / items` を返す契約テストを追加し、重み変更時の A/B レビューを API だけで完結できるようにした
- 検証:
  - `python -m pytest tests/test_rankings_score_parameter_ab_review.py -q` 成功（2 passed）
  - `python -m pytest tests/test_api_contract_rankings.py tests/test_rankings_score_parameter_validation.py tests/test_top_hit_quality_review.py -q` 成功（8 passed）

## 2026-03-08 C81 Completion Update
- Task: `CI-108 API保護のレート制御ポリシーを統一`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_rate_limit.py`
  - `backend/tests/test_api_contract_rankings.py`
- 実装内容:
  - rankings 系 endpoint の read/heavy レーンを `RATE_LIMIT_POLICY` registry として整理し、helper 側も同じ定義を参照するよう統一した
  - `/api/v1/rankings/rate-limit-policy` を追加し、path ごとの policy setting / configured policy / default_requests / burst_behavior を参照可能にした
  - filter 付き contract と既存 429 制御テストを追加し、実際の制御と API 公開仕様の両方を固定した
- 検証:
  - `python -m pytest tests/test_rankings_rate_limit.py -q` 成功（4 passed）
  - `python -m pytest tests/test_api_contract_rankings.py tests/test_rankings_score_parameter_ab_review.py tests/test_rankings_score_parameter_validation.py -q` 成功（9 passed）

## 2026-03-08 C82 Completion Update
- Task: `CI-096 エンドポイント別の入力スキーマ厳格化`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_input_schema_strictness.py`
  - `backend/tests/test_api_contract_rankings.py`
- 実装内容:
  - `score-parameter-validation`, `score-parameter-ab-review`, `top-hit-quality-review` の request body を strict schema に変更し、extra field を禁止した
  - `ad_ids` と `limit` に strict int を適用し、文字列からの暗黙 coercion を避けるようにした
  - 422 contract を専用テストで固定し、schema エラーと business validation エラーの境界を明確にした
- 検証:
  - `python -m pytest tests/test_rankings_input_schema_strictness.py -q` 成功（4 passed）
  - `python -m pytest tests/test_api_contract_rankings.py tests/test_rankings_score_parameter_validation.py tests/test_rankings_score_parameter_ab_review.py tests/test_top_hit_quality_review.py -q` 成功（12 passed）

## 2026-03-08 C84 Completion Update
- Task: `CI-112 内部API呼び出しのトレースID連携を統一`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_trace_propagation.py`
  - `backend/tests/test_api_contract_rankings.py`
- 実装内容:
  - rankings 用の `TRACE_PROPAGATION_POLICY` registry と `/api/v1/rankings/trace-propagation-policy` を追加し、request_context / task_dispatch の伝播方針を API から参照可能にした
  - `lp-info/refresh`, `batch-extract-media`, `retry-failed-media`, `meta-extraction/{ad_id}/retry` の dispatch 応答に `trace_id` を含め、request -> response -> task の相関を追えるようにした
  - LP refresh の dispatch kwargs に `trace_id` が乗ることをテストで固定し、既存の trace helper / response header 契約と合わせて一貫性を確保した
- 検証:
  - `python -m pytest tests/test_rankings_trace_propagation.py tests/test_trace_propagation.py -q` 成功（5 passed）
  - `python -m pytest tests/test_api_contract_rankings.py tests/test_rankings_rate_limit.py tests/test_rankings_input_schema_strictness.py -q` 成功（15 passed）

## 2026-03-08 C83 Completion Update
- Task: `CI-100 高負荷APIのフェイルソフト応答を整備`
- 変更ファイル:
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_fail_soft.py`
  - `backend/tests/test_api_contract_rankings.py`
- 実装内容:
  - `dashboard-summary` と `score-distribution` の既存 degraded 応答を `FAIL_SOFT_POLICY` registry として整理し、fallback 順序と degraded reason code を API から参照可能にした
  - `/api/v1/rankings/fail-soft-policy` を追加し、path ごとの `mode / fallback_order / degraded_reason_codes / stale_cache_allowed / empty_payload_factory` を返すようにした
  - stale cache と empty payload fallback の既存挙動に加え、policy endpoint の filter/contract をテストで固定した
- 検証:
  - `python -m pytest tests/test_rankings_fail_soft.py -q` 成功（4 passed）
  - `python -m pytest tests/test_api_contract_rankings.py tests/test_rankings_rate_limit.py tests/test_rankings_trace_propagation.py -q` 成功（14 passed）

## 2026-03-08 C85 Completion Update
- Task: `CI-116 エラーコード辞書と運用対応表を整備`
- 変更ファイル:
  - `backend/app/core/error_codes.py`
  - `backend/tests/test_rankings_error_codes.py`
  - `backend/tests/test_api_contract_rankings.py`
- 実装内容:
  - error code registry の返却に `severity / owner / runbook / first_response` を追加し、API からそのまま運用対応表として参照できるようにした
  - category / scope ベースの default mapping を導入し、既存 code を増やさずに運用メタデータを一貫生成するようにした
  - `/api/v1/rankings/error-codes` の contract を拡張し、scope filter と運用項目の存在をテストで固定した
- 検証:
  - `python -m pytest tests/test_rankings_error_codes.py -q` 成功（3 passed）
  - `python -m pytest tests/test_api_contract_rankings.py tests/test_rankings_fail_soft.py tests/test_rankings_trace_propagation.py -q` 成功（15 passed）

## 2026-03-08 C87 Completion Update
- Task: `CI-120 API互換性ガイドラインのレビュープロセス整備`
- 変更ファイル:
  - `docs/API_COMPATIBILITY_GUIDELINES.md`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_rankings_api_compatibility_review_process.py`
  - `backend/tests/test_api_contract_rankings.py`
- 実装内容:
  - guideline に `Review Process` セクションを追加し、分類・review question・contract test 更新・docs 更新・rollout 確認の手順を明文化した
  - `.agent-tasks/api_compatibility_review_manifest.json` と guideline を読んで review readiness を返す `/api/v1/rankings/api-compatibility-review-process` を追加した
  - review readiness / missing sections / critical contract tests / review_process を contract テストで固定し、レビュー手順を API からも参照可能にした
- 検証:
  - `python -m pytest tests/test_api_compatibility_review.py tests/test_rankings_api_compatibility_review_process.py -q` 成功（3 passed）
  - `python -m pytest tests/test_api_contract_rankings.py tests/test_rankings_error_codes.py tests/test_rankings_fail_soft.py -q` 成功（17 passed）

## 2026-03-08 C112 Completion Update
- Task: `C112 real metrics contract and provenance API`
- 変更ファイル:
  - `backend/app/schemas/ad.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_api_contract_ads.py`
  - `backend/tests/test_c112_real_metrics_contract.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - `spend / impressions / reach / lp_score / extract_quality_score` に対して `*_provenance` sibling を追加し、`metric_source / metric_status / freshness_status / measured_at / confidence_label` を共通 shape で返す helper を導入した
  - `AdResponse` と rankings の `hit-ads` / fallback 経路で同じ provenance helper を使うようにして、ads と rankings で数値契約をそろえた
  - registry に `real / estimated / missing / stale` の契約と fixture 例を追記し、frontend が provenance 表示を固定 shape で扱えるようにした
- 検証:
  - `python -m pytest tests/test_c112_real_metrics_contract.py -q` 成功（1 passed）
  - `python -m pytest tests/test_api_contract_ads.py -q` 成功（11 passed）
  - `python -m pytest tests/test_api_contract_rankings.py tests/test_rankings_fail_soft.py tests/test_rankings_error_codes.py -q` 成功（17 passed）

## 2026-03-08 C113 Completion Update
- Task: `C113 language and product taxonomy contract`
- 変更ファイル:
  - `backend/app/schemas/ad.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_api_contract_ads.py`
  - `backend/tests/test_api_contract_rankings.py`
  - `backend/tests/test_c113_language_taxonomy_contract.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - `language / language_status / language_confidence / language_source / product_category / product_subcategory / exclude_from_analysis / exclude_reason` を共通 helper で正規化し、`ads` と `rankings` の返却 shape を固定した
  - `language_status` の意味を `ja / non-ja / unknown` で固定し、`_is_japanese_ad()` も同じ helper を参照するようにして JP-only 判定を一元化した
  - `hit-ads` / fallback / `rankings/search` に taxonomy fields を追加し、registry に response example と semantic 定義を追記した
- 検証:
  - `python -m pytest tests/test_c113_language_taxonomy_contract.py -q` 成功（1 passed）
  - `python -m pytest tests/test_api_contract_ads.py tests/test_api_contract_rankings.py tests/test_rankings_dpro_parity.py -q` 成功（42 passed）

## 2026-03-08 C114 Completion Update
- Task: `C114 Bedrock classification gateway contract`
- 変更ファイル:
  - `backend/app/services/ai/bedrock_classification_gateway.py`
  - `backend/app/services/ai/__init__.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_bedrock_classification_gateway_contract.py`
  - `backend/tests/test_api_contract_rankings.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - Bedrock 分類結果を `language / product_category / topic_label / confidence / reasons / model_name / classified_at` を中心とした共通 shape に正規化する gateway helper を追加した
  - `success / partial / fallback / timeout / missing` の status 語彙と `rule_fallback_used / partial_bedrock_result / timeout_fallback` などの理由コードを固定した
  - `/api/v1/rankings/bedrock-classification-gateway-contract` と `/api/v1/rankings/bedrock-classification-gateway/{ad_id}` を追加し、契約参照と ad 単位の正規化結果確認を API から行えるようにした
- 検証:
  - `python -m pytest tests/test_bedrock_classification_gateway_contract.py -q` 成功（1 passed）
  - `python -m pytest tests/test_api_contract_rankings.py tests/test_rankings_dpro_parity.py -q` 成功（32 passed）

## 2026-03-08 C115 Completion Update
- Task: `C115 Bedrock decision contract and prompt registry`
- 変更ファイル:
  - `backend/app/services/ai/bedrock_classification_gateway.py`
  - `backend/app/services/ai/__init__.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_bedrock_decision_contract.py`
  - `backend/tests/test_api_contract_rankings.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - Bedrock gateway を decision payload まで拡張し、`language / product_category / product_subcategory / topic_label / offer_type / funnel_type / priority_score / priority_reason / review_required / review_reason / confidence_band / model_name / prompt_version / classified_at` を固定 shape で返す helper を追加した
  - `rule_override -> bedrock_result -> rule_fallback` の優先順を contract に明記し、timeout / partial / invalid_json の fallback 振る舞いと review 誘導語彙を固定した
  - prompt registry を追加し、`/api/v1/rankings/bedrock-decision-contract` と `/api/v1/rankings/bedrock-prompt-registry` と `/api/v1/rankings/bedrock-decision/{ad_id}` から契約と ad 単位 payload を参照できるようにした
- 検証:
  - `python -m pytest tests/test_bedrock_decision_contract.py -q` 成功（2 passed）
  - `python -m pytest tests/test_api_contract_rankings.py -q` 成功（14 passed）

## 2026-03-08 C116 Completion Update
- Task: `C116 Bedrock review queue and priority API`
- 変更ファイル:
  - `backend/app/services/ranking/bedrock_review.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_bedrock_review_queue_priority_api.py`
  - `backend/tests/test_api_contract_rankings.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - `priority_score / review_required / review_reason / confidence_band / actual_metrics_present / actual_metrics_focus` と `rule / ai / manual` provenance を返す共通 helper を追加した
  - `/api/v1/rankings/bedrock-review-queue` と `/api/v1/rankings/high-priority-actual-metrics` を追加し、`only_high_priority / only_review_required / priority_min / q` の filter contract を固定した
  - `search-simple` と ad/list 系 payload に同じ priority / review / provenance fields を載せ、frontend が review queue と一覧を同じ語彙で扱えるようにした
- 検証:
  - `python -m pytest tests/test_bedrock_review_queue_priority_api.py -q` 成功（2 passed）
  - `python -m pytest tests/test_api_contract_rankings.py -q` 成功（16 passed）

## 2026-03-08 C117 Completion Update
- Task: `C117 Meta data contract and freshness API`
- 変更ファイル:
  - `backend/app/schemas/ad.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_api_contract_ads.py`
  - `backend/tests/test_api_contract_rankings.py`
  - `backend/tests/test_c117_meta_data_contract.py`
- 実装内容:
  - Meta 用の `metric_source / creative_source / lp_source` と `metric_status / creative_status / lp_status` を共通 helper で正規化し、ads / rankings / search の返却 shape を固定
  - `last_meta_success_at / freshness_status / meta_quality_state / meta_recovery_reason` を detail と一覧の両方で返すようにし、`real / estimated / missing / stale` の品質状態を UI/監査に渡せるようにした
  - `/api/v1/rankings/meta-freshness-contract` と `/api/v1/rankings/meta-freshness/{ad_id}` で vocabulary と ad 単位 freshness payload を参照可能にした
- 検証:
  - `python -m pytest tests/test_c117_meta_data_contract.py -q`
  - `python -m pytest tests/test_api_contract_ads.py tests/test_api_contract_rankings.py -q`

## 2026-03-08 C118 Contract Hardening Update
- Task: `C118 Meta token runtime and health contract`
- 変更ファイル:
  - `backend/app/schemas/meta_marketing.py`
  - `backend/app/api/endpoints/settings.py`
  - `backend/tests/test_meta_token_info_contract.py`
- 実装内容:
  - settings API 側に `MetaTokenHealthResponse` と `MetaTokenExchangeResponse` を追加し、`token_source / expires_at / days_remaining / is_expiring / last_validation_error` の契約を schema で固定
  - `/settings/meta/token-info` を共通 payload builder ベースに整理し、`db / env / missing` の runtime source と fallback shape を一貫化
  - `/settings/meta/exchange-token` に `token_source=db` と `exchanged=true` を含む固定 payload を追加し、長期トークン交換結果の契約を明示化
- 検証:
  - `python -m pytest tests/test_meta_token_info_contract.py -q`

## 2026-03-08 C117 Completion Update
- Task: `C117 Meta data contract and freshness API`
- 変更ファイル:
  - `backend/app/schemas/ad.py`
  - `backend/app/api/endpoints/rankings.py`
  - `backend/tests/test_c117_meta_data_contract.py`
  - `backend/tests/test_api_contract_ads.py`
  - `backend/tests/test_api_contract_rankings.py`
  - `.agent-tasks/API_CONTRACT_REGISTRY.md`
- 実装内容:
  - `metric_source / creative_source / lp_source` の Meta provenance enum と `metric_status / creative_status / lp_status / freshness_status / last_meta_success_at / meta_quality_state / meta_recovery_reason` を返す共通 helper を追加した
  - `/api/v1/rankings/meta-freshness-contract` と `/api/v1/rankings/meta-freshness/{ad_id}` を追加し、Meta freshness 契約と ad 単位の正規化結果を API から参照できるようにした
  - `ads` と `rankings` の detail / search / list 系 payload に同じ Meta freshness fields を差し込み、内部状態を API 契約では `real / estimated / missing / stale` に正規化した
- 検証:
  - `python -m pytest backend/tests/test_c117_meta_data_contract.py -q` 成功（1 passed）
  - `python -m pytest backend/tests/test_api_contract_ads.py backend/tests/test_api_contract_rankings.py -q` 成功（28 passed）
