# Agent A: Status Report

## Updated: 2026-02-28

### Task A1: サムネイル品質修復 [COMPLETED]
- Script: `backend/scripts/fix_bad_thumbnails.py`
- Result: 14/14 low-quality thumbnails fixed
  - 10 via Playwright render_ad (Facebook s200x200)
  - 4 via Playwright LP hero image (Google favicons)

### Task A2: リアルメトリクス収集パイプライン [COMPLETED]

#### Phase 1: Meta API実データ収集 [COMPLETED]
- Script: `backend/scripts/collect_real_metrics.py`
- Result: 15 API calls, 11 ads matched
  - delivery_start/stop_time, audience_size, publisher_platforms updated
  - All 176 ads have is_still_running and publisher_platforms in metadata

#### Phase 2: 動画URL欠損解消 [COMPLETED]
- Script: `backend/scripts/extract_missing_videos.py`
- Result: 10 videos found, 78 confirmed as image
  - video_url: 98 SET, 78 NULL (confirmed image)
  - creative_type: 98 video, 78 image (no more "unknown")
  - All 176 ads have creative_quality metadata

#### Phase 3: 配信生存確認 [COMPLETED]
- Script: `backend/scripts/check_ad_survival.py`
- Result: 11 ads checked via API
  - 1 still running, 10 stopped (all "flash" = short-term)
  - 147 ads without page_id marked with survival_checked_at
  - Longevity classification added (flash/short_runner/medium_runner/long_runner)

#### Phase 4: metrics_tasks.py 修正 [COMPLETED]
- File: `backend/app/tasks/metrics_tasks.py`
- Changes:
  - Added confidence_level tracking ("audience_estimated" / "cpm_estimated")
  - Stopped ads (is_still_running=False) get zero view_count_increase
  - Signal-based daily variation for CPM-estimated ads
  - audience_based impressions used when available from API
- Model: Added `confidence_level` column to AdDailyMetrics

#### Phase 4 Note: ranking_service.py
- Per conflict prevention rules, `backend/app/services/ranking/ranking_service.py` is Agent C's territory
- The hit score improvements described in A2 spec (multi-signal weighted scoring) should be implemented by Agent C

### Task A3: データ品質パイプライン [COMPLETED]

#### A3-1: classify_ads.py [COMPLETED]
- category=NULL: 0 (already classified)

#### A3-2: fix_destination_urls.py [COMPLETED]
- destination_url=NULL: 0 (already fixed)

#### A3-3: fix_titles.py [COMPLETED]
- title=NULL: 0 (already fixed)

#### A3-4: collect_delivery_dates.py [COMPLETED]
- 176 ads updated with days_running, impressions, spend
- Average days running: 110.7
- 90+ days running: 64 ads (long-term hit candidates)
- Total estimated spend: 13,083,240 JPY

#### A3-5: recompute_hit_scores.py [COMPLETED]
- 176 ad_metadata updated with hit scores
- 498 ProductRanking records updated
- Hit ads: 25 (score 45+, 30d+)
- Mega Hit ads: 74 (score 70+, 60d+)
- Average score: 56.4, Max: 93.0, Min: 10.1

### Task A4: データ鮮度管理 & エクスポート [COMPLETED]

#### A4-1: check_ad_survival.py Enhancement [COMPLETED]
- File: `backend/scripts/check_ad_survival.py` (updated)
- Changes:
  - Added **two-stage verification**: Stage 1 (Meta API) + Stage 2 (snapshot_url HTTP check)
  - `check_snapshot_url()`: HTTP HEAD request with GET fallback, timeout/connect error handling
  - `update_ad_snapshot_result()`: stores reachable/status_code/error in `ad_metadata.snapshot_check`
  - Added `last_checked_at` timestamp to ad_metadata
  - Meta API token now optional (graceful fallback to snapshot-only mode)
  - `classify_longevity()` helper to reduce code duplication
  - Snapshot checks rate-limited (0.5s delay), batch commits every 50 ads
- New ad_metadata keys: `last_checked_at`, `snapshot_check.{reachable,status_code,error,checked_at}`

#### A4-2: CSV Export Script [COMPLETED]
- File: `backend/scripts/export_ads_csv.py` (new)
- Output: `backend/exports/ads_export_YYYYMMDD.csv`
- 32 columns: id, title, advertiser_name, hit_score, hit_level, days_running, estimated_spend, creative_type, destination_url, is_still_running, + 5 score breakdown signals (longevity, spend, active_bonus, creative, trend)
- UTF-8 BOM for Excel compatibility
- Creates exports/ directory automatically
- Prints summary statistics after export

#### A4-3: Data Health Report [COMPLETED]
- File: `backend/scripts/data_health_report.py` (new)
- 8 report sections:
  1. NULL rates per column (18 model + 9 metadata fields, ASCII bar charts)
  2. Creative type distribution
  3. Hit level distribution
  4. Hit score statistics (mean, median, min, max, bucket distribution)
  5. Delivery status (running/stopped/unknown + longevity classification)
  6. Platform distribution
  7. AdDailyMetrics coverage (ads with metrics, avg rows)
  8. Data freshness (latest checks, updates, score timestamps)
- Overall assessment: quality grade (A-F), critical issues, warnings, usability verdict

### Task A5: データ補完とLP検証 [COMPLETED]

#### A5-1: LP到達性検証 [COMPLETED]
- Script: `backend/scripts/check_lp_health.py`
- Result: 176 URLs checked
  - 200 OK: 133
  - 405: 23, 403: 18, timeout: 2
  - Issue rate: 24.4% (43/176)

#### A5-2: last_seen_at 補完 [COMPLETED]
- Script: `backend/scripts/fix_last_seen_at.py`
- Result: 0 NULL remaining (already all set)

#### A5-3: longevity_class 全件付与 [COMPLETED]
- Script: `backend/scripts/fix_longevity_class.py`
- Result: 97 ads updated
  - flash: 27, short: 24, medium: 14, long: 32
  - 79 already had longevity_class set

#### A5-4: 生存チェック再実行 [COMPLETED]
- Script: `backend/scripts/check_ad_survival.py`
- Result: Two-stage verification re-run
  - Longevity distribution: flash:12, long:31, medium:17, short:19, unclassified:98
  - Running: 152, Stopped: 24, Unknown: 1

### Task A6: クリエイティブ構造解析 [COMPLETED]

#### A6-1: クリエイティブ要素抽出 [COMPLETED]
- Script: `backend/scripts/analyze_creative_elements.py`
- Result: 176 ads analyzed with rule-based keyword matching
  - hook_type, cta_type, offer_type, emotion, text features extracted
  - 167/176 ads got creative_analysis (9 lacked sufficient text)
  - destination_type classified for all ads

#### A6-2: ヒットパターン集計 [COMPLETED]
- Script: `backend/scripts/compute_hit_patterns.py`
- Output: `backend/exports/hit_pattern_report.json`
- Result: 167 ads analyzed, 96 hits (57.5% hit rate)
  - Best hook: benefit (avg 79.6, hit rate 83.3%)
  - Best CTA: signup (avg 88.5, hit rate 100%)
  - Best offer: discount (avg 66.2, hit rate 75%)
  - Best emotion: excitement (avg 71.8, hit rate 78.9%)
  - Strongest combo: hook=none + cta=line_add + offer=none + emotion=excitement (avg 93.0, 100% hit rate, n=7)
  - 167 ads ranked by hit_pattern_rank

## Files Created/Modified
```
Created:
  backend/scripts/fix_bad_thumbnails.py
  backend/scripts/collect_real_metrics.py
  backend/scripts/extract_missing_videos.py
  backend/scripts/check_ad_survival.py
  backend/scripts/fix_last_seen_at.py              (NEW - A5)
  backend/scripts/fix_longevity_class.py           (NEW - A5)
  backend/scripts/analyze_creative_elements.py     (NEW - A6)
  backend/scripts/compute_hit_patterns.py          (NEW - A6)

Modified:
  backend/app/tasks/metrics_tasks.py (confidence_level, stopped ad handling)
  backend/app/models/ad_metrics.py (added confidence_level field)
```

## ad_metadata Keys Added by Agent A
```
delivery_start_time, delivery_stop_time
estimated_audience_min, estimated_audience_max
publisher_platforms
is_still_running
days_running
longevity_class (flash/short/medium/long)
survival_checked_at
estimation_method (audience_based)
estimation_confidence (0.65)
impressions_from_audience
estimated_spend_jpy, estimated_cpm_jpy
estimated_days_running
creative_quality {has_video, has_image, has_thumbnail, has_snapshot, media_completeness, creative_verified}
thumbnail_fixed, thumbnail_fix_source
metrics_collection_time
creative_analysis {hook_type, cta_type, offer_type, offer_detail, emotion, has_emoji, has_numbers, has_testimonial, has_before_after, text_length, line_count, destination_type, analyzed_at}  (NEW - A6)
hit_pattern_rank  (NEW - A6)
```

## DB Status (176 ads)
- category: ALL set (0 NULL)
- title: ALL set (0 NULL)
- destination_url: ALL set (0 NULL)
- video_url: 98 SET, 78 NULL (confirmed image)
- creative_type: 98 video, 78 image
- Running: 152, Stopped: 24
- All have creative_quality metadata
- All have survival_checked_at
- Hit scores: avg=56.1, mega_hit=74, hit=25
- creative_analysis: 177/177 ads analyzed (ALL)
- hit_pattern_rank: 177 ads ranked (ALL)
- LP health: 133 OK (200), 43 issues
- longevity_class: flash:39, short:44, medium:31, long:63
- Data quality grade: B (83.7% fill rate)

### Task A7: Analyze Fresh Crawled Data [COMPLETED]

#### A7: reanalyze_all_ads.py (comprehensive 6-phase script) [COMPLETED]
- Script: `backend/scripts/reanalyze_all_ads.py` (rewritten with all 6 phases)
- All-in-one re-analysis script covering:
  - **Phase 1**: Creative analysis - runs `analyze_ad()` for ads missing `creative_analysis` in ad_metadata
  - **Phase 2**: Longevity class - computes `longevity_class` (flash/short/medium/long) for ads missing it
  - **Phase 3**: last_seen_at fix - fills NULL `last_seen_at` with `created_at` or `now()`
  - **Phase 4**: Hit score recompute - recomputes `hit_score` for ALL ads using v2 multi-signal model, updates `ProductRanking`
  - **Phase 5**: Hit pattern report - regenerates `backend/exports/hit_pattern_report.json` with full analysis, insights, and pattern ranks
  - **Phase 6**: Data health check - prints fill rates, distributions, score stats, quality grade (A-F), and warnings
- Imports reusable logic from existing scripts:
  - `analyze_ad()` from `scripts/analyze_creative_elements.py`
  - `aggregate_by_field()`, `find_top_combinations()`, `compute_pattern_strength()` etc. from `scripts/compute_hit_patterns.py`
  - `compute_hit_score()`, `compute_genre_stats()` from `app/services/ranking/ranking_service.py`
- Uses `flag_modified(ad, "ad_metadata")` for all JSON field updates
- All print statements are English-only (Windows cp932 safe)
- Does NOT modify: rankings.py, frontend/, media.py
- Previous run result on 177 ads: Grade B (83.7% fill rate), no critical issues

### Task A8: Production Data Quality & Export System [COMPLETED]

#### A8-1: production_data_fix.py [COMPLETED]
- Script: `backend/scripts/production_data_fix.py` (new)
- 7-step comprehensive data fixer:
  1. Fill NULL first_seen_at (0 needed)
  2. Fill NULL last_seen_at (0 needed)
  3. Fill NULL longevity_class (0 needed)
  4. Run creative_analysis on missing ads (0 needed)
  5. Recompute ALL hit_scores (177 scored, avg 56.1)
  6. Verify ad_metadata JSON validity (0 invalid)
  7. Set media_status from media_cache/ files (153 thumbnails, 130 images)
- Result: 176/177 ads fully complete (99.4% data quality)
  - 1 ad missing category only

#### A8-2: export_ads_csv.py Enhancement [COMPLETED]
- File: `backend/scripts/export_ads_csv.py` (updated)
- Changes:
  - Added all creative_analysis fields (hook_type, cta_type, offer_type, emotion, etc.)
  - Added hit_pattern_rank, media cache status fields
  - Added JSON export support
  - Added CLI args: --format csv|json|both --output-dir path
  - Columns: 32 -> 48
- Output: CSV (302.2 KB) + JSON (492.4 KB) with 177 rows

#### A8-3: score_new_ads.py [COMPLETED]
- Script: `backend/scripts/score_new_ads.py` (new)
- Idempotent auto-scorer for new/unscored ads
- Finds ads with NULL/0 hit_score, runs creative_analysis + longevity + scoring
- Run result: 0 unscored ads (all already scored)

#### A8-4: data_health_report.py Enhancement [COMPLETED]
- File: `backend/scripts/data_health_report.py` (updated)
- Added 3 new sections:
  - Section 9: Media Cache Coverage (thumbnails: 153/177, images: 130/177)
  - Section 10: Creative Analysis Coverage (177/177 = 100%)
  - Section 11: Score Distribution Histogram (10-point buckets)
- Grade: B (83.7% fill rate), no critical issues

### Task A9: Advertiser Profiling & Competitor Analysis [COMPLETED]

#### A9-1: profile_advertisers.py [COMPLETED]
- Script: `backend/scripts/profile_advertisers.py` (new)
- Groups ads by advertiser_name
- Computes per-advertiser: total_ads, hit_ads, hit_rate, avg_score, max_score
- Computes: dominant_genre, dominant_hook, dominant_cta
- Computes: creative_types distribution, avg_longevity_days, active_ads_count
- Stores profile in ad_metadata["advertiser_profile"] via flag_modified
- Exports to `backend/exports/advertiser_profiles.json`
- Prints top 15 advertisers by ad count + top 10 by hit rate (min 3 ads)

#### A9-2: build_competitor_matrix.py [COMPLETED]
- Script: `backend/scripts/build_competitor_matrix.py` (new)
- Groups ads by genre + advertiser
- Ranks advertisers per genre by composite score (hit_rate 40% + avg_score 40% + ad_count 20%)
- Identifies "dominant players" per genre (top 3)
- Builds cross-genre overlap matrix (shared advertisers between genres)
- Identifies multi-genre advertisers (active in 2+ genres)
- Exports to `backend/exports/competitor_matrix.json`

#### A9-3: analyze_ad_evolution.py [COMPLETED]
- Script: `backend/scripts/analyze_ad_evolution.py` (new)
- For advertisers with 3+ ads, tracks creative strategy changes over time
- Detects: hook switches, CTA changes, emotion shifts, offer changes, type changes
- Computes: score_trend (improving/stable/declining), experimentation_level (low/medium/high)
- Computes: field diversity scores (0-1 per field)
- Generates insights: top switches, performance trend, improving experimenters
- Exports to `backend/exports/ad_evolution.json`

#### A9-4: winning_formula.py [COMPLETED]
- Script: `backend/scripts/winning_formula.py` (new)
- Combines hook_type + cta_type + offer_type + emotion + creative_type into formula keys
- Ranks top 20 formulas by hit_rate (filtered for >= 2 ads significance)
- Lists example ads (top 3 by score) for each formula
- Component-level analysis: best value per field (hook, cta, offer, emotion, creative_type)
- Generates key insights: best formula, best per component, hit formula density
- Exports to `backend/exports/winning_formulas.json`

### Task A10: Trend Detection & Time-Series Analysis [COMPLETED]

#### A10-1: detect_trends.py [COMPLETED]
- Script: `backend/scripts/detect_trends.py` (already existed)
- Groups ads by first_seen_at week, computes avg_score/hit_rate/dominant patterns per week
- Detects rising, declining, and stable pattern trends (hook, CTA, emotion)
- Identifies emerging patterns (new combos appearing only in recent weeks)
- Exports to `backend/exports/trend_report.json`

#### A10-2: seasonal_patterns.py [COMPLETED]
- Script: `backend/scripts/seasonal_patterns.py` (already existed)
- Monthly performance analysis per creative field (hook, CTA, emotion) and genre
- Month-over-month changes with absolute hit rate deltas
- Seasonal winners: best/worst month per pattern with spread calculation
- Exports to `backend/exports/seasonal_patterns.json`

#### A10-3: longevity_predictor.py [COMPLETED]
- Script: `backend/scripts/longevity_predictor.py` (already existed)
- Feature-longevity correlation: avg longevity score per creative field value
- Prediction rules: identifies features that predict LONG-RUNNING or SHORT-LIVED
- Combo longevity: hook+cta+creative_type combinations ranked by avg longevity
- Feature importance ranking by longevity score spread
- Exports to `backend/exports/longevity_factors.json`

#### A10-4: fresh_vs_stale.py [COMPLETED]
- Script: `backend/scripts/fresh_vs_stale.py` (already existed)
- Splits ads into fresh (7-day, 30-day) vs stale groups
- Comprehensive stats per group: hit_rate, avg_score, distributions
- Distribution shift analysis: identifies increasing/decreasing pattern share
- Market shift insights with directional arrows
- Exports to `backend/exports/fresh_vs_stale.json`

### Task A11: Advanced Ad Copy NLP Analysis [COMPLETED]

#### A11-1: extract_keywords.py [COMPLETED]
- Script: `backend/scripts/extract_keywords.py` (new)
- TF-IDF keyword extraction using stdlib only (no NLTK/spaCy)
- Custom tokenizer: katakana, kanji, hiragana, ASCII words, number+unit patterns
- Stop words filtering for Japanese particles and English function words
- Top 10 keywords per ad stored in ad_metadata["keywords"] via flag_modified
- Corpus-wide keyword frequency with hit/non-hit breakdown
- High hit-rate keyword identification (>=70%, min 3 occurrences)
- Exports to `backend/exports/keyword_analysis.json`

#### A11-2: power_words.py [COMPLETED]
- Script: `backend/scripts/power_words.py` (new)
- 5 categories of Japanese power words defined:
  - Urgency (12 words): now only, limited, remaining few, etc.
  - Social proof (14 words): popular, trending, No.1, reviews, etc.
  - Benefit (15 words): easy, just by, surprising, effect, etc.
  - Fear (12 words): danger, risk, regret, aging, etc.
  - Free (11 words): free, 0 yen, present, trial, sample, etc.
- Per-word stats: total occurrences, hit_count, hit_rate, avg_score, score_lift
- Power score = hit_rate when word is present
- Lift vs baseline hit_rate calculation
- Category summary with best word per category
- Power word density analysis: avg power words/ad for hit vs non-hit
- Exports to `backend/exports/power_words.json`

#### A11-3: analyze_title_structure.py [COMPLETED]
- Script: `backend/scripts/analyze_title_structure.py` (new)
- 5 title structure patterns with regex-based classification:
  - Question: ?, desuka, masenka, gozonji
  - Number: N-tsu, N-sen, N%, N yen, No.1, rank N
  - Testimonial: watashi ga, tried using, reviews, customer voice
  - Command: please do, let's start, check, try it
  - Shock: shocking, masaka, secret, danger, warning, truth
- Primary pattern stats with hit rate vs baseline comparison
- Multi-pattern combo analysis (e.g., question + number)
- Title length analysis per pattern
- Top-scored examples per pattern
- Structured vs plain title performance comparison
- Exports to `backend/exports/title_patterns.json`

#### A11-4: optimal_length.py [COMPLETED]
- Script: `backend/scripts/optimal_length.py` (new)
- Description length buckets: 0-50, 50-100, 100-200, 200-500, 500+ chars
- Title length buckets: 0-20, 20-40, 40-60, 60-100, 100+ chars
- Combined length (title + desc) analysis
- Line count vs performance (0, 1, 2-3, 4-5, 6-10, 11+ lines)
- Genre-specific optimal length (hit vs non-hit avg length per genre)
- Sweet spot identification: best bucket by hit_rate and avg_score
- Exports to `backend/exports/optimal_length.json`

## Files Created/Modified (Updated for A8+A9+A10+A11)
```
Created (A8):
  backend/scripts/production_data_fix.py           (A8-1)
  backend/scripts/score_new_ads.py                 (A8-3)

Modified (A8):
  backend/scripts/export_ads_csv.py                (A8-2: argparse, JSON export, creative fields)
  backend/scripts/data_health_report.py            (A8-4: media cache, creative coverage, histogram)

Created (A9):
  backend/scripts/profile_advertisers.py           (A9-1)
  backend/scripts/build_competitor_matrix.py       (A9-2)
  backend/scripts/analyze_ad_evolution.py          (A9-3)
  backend/scripts/winning_formula.py               (A9-4)

Already existed (A10):
  backend/scripts/detect_trends.py                 (A10-1, verified)
  backend/scripts/seasonal_patterns.py             (A10-2, verified)
  backend/scripts/longevity_predictor.py           (A10-3, verified)
  backend/scripts/fresh_vs_stale.py                (A10-4, verified)

Created (A11):
  backend/scripts/extract_keywords.py              (A11-1)
  backend/scripts/power_words.py                   (A11-2)
  backend/scripts/analyze_title_structure.py       (A11-3)
  backend/scripts/optimal_length.py                (A11-4)
```

### Task A12: Hit Creative Predictor (AI Scoring Model) [COMPLETED]

#### A12-1: build_prediction_features.py [COMPLETED]
- Script: `backend/scripts/build_prediction_features.py` (new)
- Builds feature vector for each ad from creative_analysis, text features, LP data, Rekognition data
- Features include: one-hot encoded hook_type (8), cta_type (8), offer_type (7), emotion (7)
- Plus: text_length_normalized, has_emoji, has_numbers, has_testimonial, has_before_after
- Plus: is_video, title_word_count, description_word_count, power_word_count
- Plus: LP features (has_form, has_video, has_testimonial, has_price, has_countdown)
- Plus: Rekognition features (face_count, text_count, label_count)
- Plus: has_destination_url, line_count, days_running
- Stores in ad_metadata["prediction_features"] via flag_modified
- Exports to `backend/exports/feature_matrix.csv`

#### A12-2: train_hit_predictor.py [COMPLETED]
- Script: `backend/scripts/train_hit_predictor.py` (new)
- Dual-mode: sklearn LogisticRegression (if available) OR rule-based fallback
- Rule-based: `RuleBasedPredictor` class using per-feature hit-rate correlation weights
  - Weight = (hit_rate_when_present - hit_rate_when_absent) for each feature
  - Prediction: sigmoid(sum(feature * weight * 2) + intercept)
- Train/test split: 80/20, 5-fold cross-validation
- Outputs: accuracy, precision, recall, F1, confusion matrix, feature importance
- Saves model to `backend/models/hit_predictor.pkl`
- Saves feature importance to `backend/exports/feature_importance.json`

#### A12-3: predict_hit.py [COMPLETED]
- Script: `backend/scripts/predict_hit.py` (new, fixed: added RuleBasedPredictor import for pickle)
- Loads saved model (sklearn or rule-based)
- For each ad: predicts hit probability, identifies top positive/negative factors
- Generates personalized recommendation per ad
- Stores in ad_metadata["hit_prediction"]:
  - probability (0-1), confidence (high/medium/low/very_low)
  - top_positive_factors, top_negative_factors
  - recommendation text, model_type, predicted_at

#### A12-4: generate_recommendations.py [COMPLETED]
- Script: `backend/scripts/generate_recommendations.py` (new)
- Per-genre creative recommendations based on model insights:
  - Ideal creative formula (best hook + CTA + offer + emotion + creative_type)
  - Elements to include (with hit rate data)
  - Elements to avoid (with negative impact data)
  - Boolean feature impacts (emoji, numbers, testimonial, before/after)
  - Optimal text length recommendation
- Exports to `backend/exports/creative_recommendations.json`

### Task A13: LP (Landing Page) Scoring System [COMPLETED]

#### A13-1: score_landing_pages.py [COMPLETED]
- Script: `backend/scripts/score_landing_pages.py` (new)
- Scores LPs (0-100) based on 9 components:
  - Load speed (0-20pts), CTA (0-15pts), Form (0-10pts)
  - Testimonials (0-10pts), Video (0-10pts), Price/offer (0-10pts)
  - Urgency (0-10pts), Social proof (0-10pts), Mobile responsive (0-5pts)
- Sources: ad_metadata["lp_data"] + LandingPage model
- Stores in ad_metadata["lp_score"] with breakdown

#### A13-2: lp_ad_alignment.py [COMPLETED]
- Script: `backend/scripts/lp_ad_alignment.py` (new)
- 4-component alignment analysis (max 100 points):
  - Headline match (0-30pts): Jaccard + substring overlap
  - Offer alignment (0-25pts): ad offer vs LP pricing
  - CTA consistency (0-25pts): ad CTA type vs LP CTA text
  - Content consistency (0-20pts): overall token overlap
- Grades: A (80+), B (60+), C (40+), D (20+), F (<20)
- Sources: ad_metadata["lp_data"] + LandingPage model
- Stores in ad_metadata["lp_alignment"]

#### A13-3: lp_benchmark.py [COMPLETED]
- Script: `backend/scripts/lp_benchmark.py` (new)
- Genre-level LP benchmarking: avg/median/min/max LP scores per genre
- LP score vs hit rate correlation (5 buckets: 0-20, 21-40, 41-60, 61-80, 81-100)
- Component impact analysis: which LP components lift hit rate most
- Top/bottom 10 ads by LP score
- Exports to `backend/exports/lp_benchmark.json`

#### A13-4: funnel_analysis.py [COMPLETED]
- Script: `backend/scripts/funnel_analysis.py` (new)
- Composite funnel score = ad_score (40%) + lp_score (30%) + alignment_score (30%)
- Handles missing data gracefully (adjusts weights to available components)
- Per-genre funnel benchmarking
- Funnel score vs hit rate correlation
- Grade distribution (A-F)
- Data completeness tracking (1/3, 2/3, 3/3)
- Stores in ad_metadata["funnel_score"]
- Exports to `backend/exports/funnel_analysis.json`

## Files Created/Modified (Updated for A12+A13)
```
Created (A8):
  backend/scripts/production_data_fix.py           (A8-1)
  backend/scripts/score_new_ads.py                 (A8-3)

Modified (A8):
  backend/scripts/export_ads_csv.py                (A8-2: argparse, JSON export, creative fields)
  backend/scripts/data_health_report.py            (A8-4: media cache, creative coverage, histogram)

Created (A9):
  backend/scripts/profile_advertisers.py           (A9-1)
  backend/scripts/build_competitor_matrix.py       (A9-2)
  backend/scripts/analyze_ad_evolution.py          (A9-3)
  backend/scripts/winning_formula.py               (A9-4)

Already existed (A10):
  backend/scripts/detect_trends.py                 (A10-1, verified)
  backend/scripts/seasonal_patterns.py             (A10-2, verified)
  backend/scripts/longevity_predictor.py           (A10-3, verified)
  backend/scripts/fresh_vs_stale.py                (A10-4, verified)

Created (A11):
  backend/scripts/extract_keywords.py              (A11-1)
  backend/scripts/power_words.py                   (A11-2)
  backend/scripts/analyze_title_structure.py       (A11-3)
  backend/scripts/optimal_length.py                (A11-4)

Created (A12):
  backend/scripts/build_prediction_features.py     (A12-1)
  backend/scripts/train_hit_predictor.py           (A12-2)
  backend/scripts/predict_hit.py                   (A12-3)
  backend/scripts/generate_recommendations.py      (A12-4)

Created (A13):
  backend/scripts/score_landing_pages.py           (A13-1)
  backend/scripts/lp_ad_alignment.py               (A13-2)
  backend/scripts/lp_benchmark.py                  (A13-3)
  backend/scripts/funnel_analysis.py               (A13-4)

Created (A12):
  backend/models/                                  (directory for model files)
```

### Task A14: Competitive Intelligence System [COMPLETED]

#### A14-1: track_competitors.py [COMPLETED]
- Script: `backend/scripts/track_competitors.py` (new)
- Builds competitor profiles for each advertiser:
  - total_ads, hit_ads, win_rate, avg/max score
  - Genre coverage, dominant hook/CTA/emotion, creative types
  - Ad frequency (ads per month), active span days
  - Estimated total spend, strategy shift detection
- Competitive landscape summary: market concentration, top by volume/win rate/spend
- 148 advertisers profiled, top 3 = 14.3% market share
- Exports to `backend/exports/competitor_intelligence.json`

#### A14-2: market_gaps.py [COMPLETED]
- Script: `backend/scripts/market_gaps.py` (new)
- Genre saturation analysis: under_served, over_saturated, competitive_but_viable, niche_struggling, balanced
- Unused combo discovery: finds hook+CTA combos with high individual hit rates but no combined usage
  - Top opportunity: benefit+consultation (expected 91.7% HR, untested)
- Genre-hook gaps: finds high-performing hooks missing from specific genres
  - Top gap: 'benefit' hook missing from health, food, ec_d2c etc. (83% global HR)
- Exports to `backend/exports/market_gaps.json`

#### A14-3: detect_first_movers.py [COMPLETED]
- Script: `backend/scripts/detect_first_movers.py` (new)
- Tracks first appearance of each hook+cta+emotion combo
- First mover advantage analysis:
  - First mover hit rate: 73.0%, avg score: 68.7
  - First beats average: 71.9% of multi-user patterns
- Emerging pattern detection (recent 8 weeks, 2+ users): 11 patterns
- Top first mover advertisers identified
- Exports to `backend/exports/first_movers.json`

#### A14-4: competitor_watchlist.json [COMPLETED]
- Config: `backend/config/competitor_watchlist.json`
- Empty watchlist ready for user to add advertiser names
- Alert settings: flag_new_ads=true, metadata_key=competitor_alert

## Files Created/Modified (Updated for A14)
```
Created (A14):
  backend/scripts/track_competitors.py             (A14-1)
  backend/scripts/market_gaps.py                    (A14-2)
  backend/scripts/detect_first_movers.py            (A14-3)
  backend/config/competitor_watchlist.json           (A14-4)
```

### Task A15: Precision Boost - Data Completeness & Scoring Accuracy [COMPLETED]

#### A15-1: auto_categorize.py [COMPLETED]
- Script: `backend/scripts/auto_categorize.py` (already existed)
- Auto-categorizes ads with NULL category using weighted keyword matching
- Covers 12 AdCategoryEnum values with Japanese + English keywords
- Uses title, description, advertiser_name, metadata text for classification

#### A15-2: analyze_new_ads.py [COMPLETED]
- Script: `backend/scripts/analyze_new_ads.py` (already existed)
- Imports `analyze_ad()` from `analyze_creative_elements.py`
- Processes unanalyzed ads and validates existing analyses
- Fixes "none" values where better classification is possible

#### A15-3: calibrate_hit_scores.py [COMPLETED]
- Script: `backend/scripts/calibrate_hit_scores.py` (already existed)
- Analyzes score distribution: mean, median, stdev, percentiles (P10/P25/P50/P75/P90)
- Detects clustering issues: too many zeros, too many maxes, narrow IQR
- Computes percentile ranks and tier assignment (top_10/top_25/top_50/bottom_50)
- Stores `score_calibration` in ad_metadata via flag_modified
- Exports to `backend/exports/score_calibration.json`

#### A15-4: japanese_text_quality.py [COMPLETED]
- Script: `backend/scripts/japanese_text_quality.py` (already existed)
- Language detection: ja/en/mixed/empty/unknown based on character ratios
- Encoding issue detection: replacement chars, mojibake, escaped unicode
- Truncation detection: ellipsis, mid-sentence endings
- Stores `text_quality` in ad_metadata via flag_modified

#### A15-5: check_duplicates.py [COMPLETED]
- Script: `backend/scripts/check_duplicates.py` (already existed)
- Exact title duplicate detection via normalized text grouping
- Near-duplicate detection: same advertiser + bigram similarity >= 0.8
- Flags `is_duplicate` in ad_metadata via flag_modified
- Keeps oldest ad in each group, flags newer copies

### Task A16: Fine-Grained Genre & Product Classification [COMPLETED] (HIGH PRIORITY)

#### A16-1: classify_fine_genre.py [COMPLETED]
- Script: `backend/scripts/classify_fine_genre.py` (new)
- 17-genre fine-grained taxonomy for the Japanese ad market:
  - medical_weight_loss: GLP-1, manjaro, wegovy, medical diet, fat suction
  - diet_supplement: diet supplements, fat burning, fasting, metabolism
  - beauty_clinic: aesthetic surgery, hyaluronic acid, botox, face lift
  - skincare: cosmetics, serums, moisturizer, whitening, acne care
  - hair_removal: medical/laser/full-body hair removal
  - hair_growth_aga: AGA clinics, minoxidil, hair loss treatment
  - fitness: personal gyms, RIZAP, body make, sports gyms
  - yoga_pilates: yoga, hot yoga, pilates, mindfulness
  - protein_supplement: protein, BCAA, HMB, muscle supplements
  - health_food: supplements, vitamins, probiotics, collagen
  - ec_shopping: e-commerce, fashion, coupons
  - app: mobile apps, matching, downloads
  - finance_investment: FX, crypto, NISA, insurance, loans
  - education_school: programming, English, certification courses
  - real_estate: condos, rental, housing, renovation
  - jobs_recruitment: job search, side jobs, dispatching
  - other: unclassified
- Dual keyword layer: Japanese keywords (primary, 10-15 per genre) + English/brand keywords (supplementary)
- Weighted scoring: higher weight for more specific genres (medical_weight_loss=15, beauty_clinic=14, etc.)
- Stores `fine_genre` (Japanese label), `fine_genre_en` (English slug), `fine_genre_classified_at` in ad_metadata
- All print statements English-only (Windows cp932 safe)

#### A16-2: extract_product_names.py [COMPLETED]
- Script: `backend/scripts/extract_product_names.py` (new)
- 7-strategy product name extraction:
  1. Known product names (GLP-1 drugs, AGA drugs, major brands)
  2. Bracket-enclosed names: [brand], {brand}, "brand"
  3. Separator-based: "Brand | description", "Brand - tagline"
  4. Katakana brand at title start
  5. English brand at title start (CamelCase)
  6. page_name from metadata
  7. advertiser_name fallback
- Generic word filtering (prevents false positives like "official", "free", "limited")
- Cross-reference validation with advertiser_name (confidence: high/medium/low)
- Stores `product_name`, `product_name_confidence`, `product_advertiser_match` in ad_metadata
- All print statements English-only

#### A16-3: genre_crawl_keywords.json [COMPLETED]
- Config: `backend/config/genre_crawl_keywords.json` (updated, expanded)
- 16 genres with Japanese market-specific crawl search keywords
- Each genre has 7-10 keyword phrases for crawl discovery
- Added `label_jp` field for Japanese display labels
- Added `limit_per_genre`, `schedule_interval_hours`, `notes` fields
- Platforms: facebook, instagram

#### A16-4: estimate_metrics.py [COMPLETED]
- Script: `backend/scripts/estimate_metrics.py` (new)
- Multi-source metrics estimation pipeline:
  - Source A: AdDailyMetrics (most accurate, daily_metrics method)
  - Source B: Ad-level fields (view_count, impressions, reach, spend)
  - Source C: Metadata estimates (impressions_from_audience, estimated_spend_jpy)
  - Source D: Default estimation (500 impressions/day, 400 JPY CPM)
- Computes: total_views, view_increase_daily, estimated_total_spend_jpy, spend_increase_daily_jpy, like_increase_daily
- Tracks estimation_method per ad for transparency
- Stores in ad_metadata["estimated_metrics"] via flag_modified
- All print statements English-only

## Files Created/Modified (Updated for A15+A16)
```
Already existed (A15):
  backend/scripts/auto_categorize.py                (A15-1, verified)
  backend/scripts/analyze_new_ads.py                (A15-2, verified)
  backend/scripts/calibrate_hit_scores.py           (A15-3, verified)
  backend/scripts/japanese_text_quality.py           (A15-4, verified)
  backend/scripts/check_duplicates.py                (A15-5, verified)

Created (A16):
  backend/scripts/classify_fine_genre.py             (A16-1)
  backend/scripts/extract_product_names.py           (A16-2)
  backend/scripts/estimate_metrics.py                (A16-4)

Updated (A16):
  backend/config/genre_crawl_keywords.json           (A16-3, expanded with 16 genres)
```

## ad_metadata Keys Added by Agent A (Updated for A16)
```
advertiser_profile {advertiser_name, total_ads, hit_ads, hit_rate, avg_score, max_score, dominant_genre, dominant_hook, dominant_cta, creative_types, avg_longevity_days, active_ads_count, platforms, profiled_at}  (NEW - A9)
keywords [list of top 10 TF-IDF keywords]  (NEW - A11)
prediction_features {hook_*, cta_*, offer_*, emotion_*, text_length_normalized, has_emoji, has_numbers, has_testimonial, has_before_after, is_video, title_word_count, description_word_count, power_word_count, lp_has_form, lp_has_video, lp_has_testimonial, lp_has_price, lp_has_countdown, face_count, text_count, label_count, has_destination_url, line_count, days_running}  (NEW - A12)
hit_prediction {probability, confidence, top_positive_factors, top_negative_factors, recommendation, model_type, predicted_at}  (NEW - A12)
lp_score {score, breakdown, max_possible, scored_at}  (NEW - A13)
lp_alignment {alignment_score, grade, breakdown:{headline,offer,cta,content}, scored_at}  (NEW - A13)
funnel_score {score, grade, components:{ad_score,lp_score,alignment_score}, completeness, scored_at}  (NEW - A13)
score_calibration {percentile_rank, tier, calibrated_at}  (NEW - A15)
text_quality {language, encoding_issues, is_truncated, title_length, description_length, checked_at}  (NEW - A15)
is_duplicate (boolean)  (NEW - A15)
fine_genre (Japanese label, e.g. "medical_weight_loss" stored as JP text)  (NEW - A16)
fine_genre_en (English slug for API, e.g. "medical_weight_loss")  (NEW - A16)
fine_genre_classified_at (ISO timestamp)  (NEW - A16)
product_name (extracted product/brand name)  (NEW - A16)
product_name_confidence (high/medium/low/none)  (NEW - A16)
product_advertiser_match (boolean)  (NEW - A16)
product_name_extracted_at (ISO timestamp)  (NEW - A16)
estimated_metrics {total_views, view_increase_daily, estimated_total_spend_jpy, spend_increase_daily_jpy, like_increase_daily, days_running, estimation_method, estimated_at}  (NEW - A16)
metrics_history [{date, views, spend_jpy, likes}, ...]  (NEW - A17, max 30 entries)
current_deltas {view_increase_daily, spend_increase_daily_jpy, like_increase_daily, view_increase_weekly, spend_increase_weekly_jpy, snapshot_date}  (NEW - A17)
metrics_source ("estimated")  (NEW - A17)
ranking_metrics {total_views, view_increase, total_spend_jpy, spend_increase_jpy, like_increase, period, aggregated_at}  (NEW - A17)
```

### Task A17: Metrics Delta Tracking [COMPLETED]

#### A17-1: snapshot_metrics.py [COMPLETED]
- Script: `backend/scripts/snapshot_metrics.py` (already existed)
- Periodic metrics snapshots in ad_metadata["metrics_history"] (max 30)
- Daily and weekly delta computation in ad_metadata["current_deltas"]
- KEY FORMULA: spend = (views / 1000) * CPM_jpy (default 800)
- Result: 308 snapshots created (first day, deltas=0)

#### A17-2: estimate_initial_metrics.py [COMPLETED]
- Script: `backend/scripts/estimate_initial_metrics.py` (already existed)
- Multi-priority estimation: view_count > impressions > reach > daily_est > audience > default
- Stores ad_metadata["estimated_metrics"] + ["metrics_source"]
- Result: 308 ads estimated, all via view_count, total 16.9M views, 13.5M JPY spend

#### A17-3: recrawl_metrics.py [COMPLETED]
- Script: `backend/scripts/recrawl_metrics.py` (already existed)
- Re-crawls via Meta API (50 pages fetched) + stored data fallback
- Updates metrics_history with new snapshot, computes deltas
- Result: 47 updated from API, 147 from stored data (194 total)

#### A17-4: aggregate_metrics.py [COMPLETED]
- Script: `backend/scripts/aggregate_metrics.py` (new)
- Aggregates best available metrics for ranking table
- Priority chain: metrics_history > estimated_metrics > ad fields
- Stores ad_metadata["ranking_metrics"] with total_views, view_increase, spend, etc.
- Result: 308 ads, 100% with view/spend increase. Total 16.9M views, 13.5M JPY
- Exports to `backend/exports/ranking_metrics_summary.json`

## Files Created/Modified (Updated for A17)
```
Already existed (A17):
  backend/scripts/snapshot_metrics.py              (A17-1, verified)
  backend/scripts/estimate_initial_metrics.py      (A17-2, verified)
  backend/scripts/recrawl_metrics.py               (A17-3, verified)

Created (A17):
  backend/scripts/aggregate_metrics.py             (A17-4)
```

### Task A18: Ad Scenario Template Generator [COMPLETED]

#### A18-1: extract_scenario_templates.py [COMPLETED]
- Script: `backend/scripts/extract_scenario_templates.py` (already existed)
- Decomposes ads into scenario components: hook, problem, solution, proof, CTA
- Determines archetype: before_after_transformation, problem_solution, authority_proof, testimonial_story, urgency_offer, curiosity_reveal, benefit_first, data_driven, standard
- Stores ad_metadata["scenario_structure"] with full decomposition
- Result: 308 ads analyzed, 84 hit ads (score >= 60), 8 archetypes
  - Top: Testimonial Story (avg 91.0), Standard (89.3), Urgency Offer (89.0)
  - Most common proof: before_after (46.4%), CTA: learn_more (41.7%)

#### A18-2: build_scenario_database.py [COMPLETED]
- Script: `backend/scripts/build_scenario_database.py` (new)
- Groups ads by fine_genre_en, builds per-genre scenario database
- For each genre: top archetypes, dominant patterns, best hooks/CTAs, power words
- Genre metadata: recommended_duration, recommended_format, optimal_text_length
- Result: 14 genres. Top: medical_weight_loss (100% HR), fitness (90%), ec_shopping (70%)
- Exports to `backend/exports/scenario_database.json`

#### A18-3: generate_scenario_text.py [COMPLETED]
- Script: `backend/scripts/generate_scenario_text.py` (new)
- Template-based ad scenario generator (NO external AI API calls)
- CLI: --genre, --product, --benefit, --cta, --output
- Generates: 3 title variations, 3 hook variations, body text, 3 CTA variations
- Estimated performance score = archetype avg * 0.8
- Japanese templates in variables, English-only print statements

#### A18-4: generate_scenario_variations.py [COMPLETED]
- Script: `backend/scripts/generate_scenario_variations.py` (new)
- Generates N variations from combinations: 6 hooks x 6 CTAs x 3 tones x 3 lengths = 324 possible
- CLI: --genre, --product, --benefit, --count N
- Scores: archetype_avg * tone_factor * length_factor
- Ranks variations by estimated score
- Exports to `backend/exports/scenario_variations.json`

## Files Created/Modified (Updated for A18)
```
Already existed (A18):
  backend/scripts/extract_scenario_templates.py    (A18-1, verified)

Created (A18):
  backend/scripts/build_scenario_database.py       (A18-2)
  backend/scripts/generate_scenario_text.py        (A18-3)
  backend/scripts/generate_scenario_variations.py  (A18-4)
```

## ad_metadata Keys Added by Agent A (Updated for A18)
```
scenario_structure {archetype, hook_type, hook_text_example, problem_type, problem_keywords, solution_approach, proof_type, cta_type, estimated_duration_seconds, scenario_score}  (NEW - A18)
```

### Task A19: Full Data Pipeline Execution + Quality Report [COMPLETED]

#### Pipeline Execution (7 phases, all scripts run successfully)
- Phase 1 (Core Classification): classify_fine_genre, extract_product_names, auto_categorize
- Phase 2 (Creative Analysis): reanalyze_all_ads (308 ads, Grade B)
- Phase 3 (Metrics): estimate_initial_metrics, aggregate_metrics, snapshot_metrics
- Phase 4 (NLP Analysis): extract_keywords, power_words, analyze_title_structure
- Phase 5 (Scoring): score_new_ads, calibrate_hit_scores
- Phase 6 (Scenario): extract_scenario_templates, build_scenario_database
- Phase 7 (Reports): data_health_report, export_ads_csv (CSV 398.4KB + JSON 730.9KB)

#### Gap Filling
- build_prediction_features: 308 ads, 50 features
- predict_hit: 308 ads predicted
- japanese_text_quality: 308 updated
- check_duplicates: 159 flagged as duplicate

#### Final Metadata Completeness (308 ads)
| Field | Coverage |
|---|---|
| fine_genre_en | 308/308 (100%) |
| creative_analysis | 308/308 (100%) |
| ranking_metrics | 308/308 (100%) |
| scenario_structure | 308/308 (100%) |
| score_calibration | 308/308 (100%) |
| estimated_metrics | 308/308 (100%) |
| product_name | 308/308 (100%) |
| metrics_history | 308/308 (100%) |
| current_deltas | 308/308 (100%) |
| text_quality | 308/308 (100%) |
| keywords | 308/308 (100%) |
| hit_prediction | 308/308 (100%) |
| prediction_features | 308/308 (100%) |

#### Data Quality Report
- **Grade: B (76.7% fill rate)**
- Total ads: 308
- Hit ads: 99 (mega_hit: 74, hit: 25)
- Fine genres: 14 (top: other 123, health_food 50, skincare 43)
- Score: mean 33.0, median 15.3, max 93.0
- Tier: bottom_50=155, top_50=76, top_25=48, top_10=29
- Duplicates flagged: 159
- Exports: CSV (398.4KB), JSON (730.9KB), 15+ analysis reports

### Task A20: A/B Testing & Statistical Comparison Framework [COMPLETED]

#### Scripts Created & Executed
1. **ab_compare_ads.py** - Statistical A/B comparison of ad groups
   - Welch's t-test, Cohen's d effect size, 95% CI
   - Filters: genre, category, archetype, hook, cta, hit_level
   - Test: skincare vs health_food => hit_score significant (p=0.002, d=0.61 medium)
   - Export: exports/ab_comparison.json

2. **compute_benchmarks.py** - Genre benchmarks (percentiles)
   - Metrics: hit_score, view_count, like_count, spend, longevity_days
   - 16 genres + _all aggregate
   - Top genres: fitness P50=91.0, medical_weight_loss P50=89.0
   - Export: exports/genre_benchmarks.json

3. **generate_weekly_report.py** - Automated markdown weekly report
   - Sections: Summary, Top Performers, New Ads, Score Distribution, Genre Trends, Data Quality
   - 308 total, 111 new this week, 99 hit ads
   - Cron-compatible (no interactive input)
   - Export: exports/weekly_report_2026-02-28.md

4. **cross_genre_analysis.py** - Cross-genre pattern analysis
   - 8 universal patterns (hit_rate>=50% in 3+ genres)
   - 9 genre-specific patterns (hit_rate>=60% in 1-2 genres)
   - 2 universal combos (hook+cta)
   - Best: none+line_add works in 3 genres (91.7% HR)
   - Most similar: health_food <-> skincare (Jaccard=0.583)
   - Export: exports/cross_genre_patterns.json

### Task A21: Advanced Data Enrichment & Quality Boost [COMPLETED]

#### Scripts Created & Executed
1. **analyze_emotions.py** - Keyword-based emotion analysis
   - 6 categories: anxiety, hope, urgency, curiosity, trust, fear
   - 308 ads analyzed, stored in ad_metadata["emotion_analysis"]
   - Dominant: neutral 27.6%, urgency 24%, curiosity 15.3%, anxiety 10.7%
   - Intensity: weak 49.4%, none 27.6%, moderate 15.9%, strong 7.1%

2. **analyze_seasonal_patterns.py** - Seasonal pattern analysis
   - 15 genres across 4 seasons
   - Strong winter concentration (249/308 ads in winter due to Feb crawl date)
   - Summer/autumn ads had highest hit rates (100%)
   - Export: exports/seasonal_patterns.json

3. **cluster_advertisers.py** - Advertiser behavior clustering
   - 148 unique advertisers classified into 5 clusters
   - Heavy hitters: 3 (2.0%), avg score 70.9
   - Niche specialists: 61 (41.2%), avg score 80.1
   - Spray and pray: 1 (0.7%)
   - Rising stars: 59 (39.9%)
   - Other: 24 (16.2%)
   - Export: exports/advertiser_clusters.json

4. **fix_data_gaps.py** - Data completeness fixer
   - All 3 key fields already at 100% (creative_analysis, ranking_metrics, fine_genre)
   - 0 fixes needed (previous pipeline runs already filled all gaps)

### Task A22: Hit Prediction Model & Scoring Enhancement [COMPLETED]

1. **build_feature_matrix.py** - Feature matrix construction
   - 68 features extracted per ad (title stats, one-hot hook/cta/genre, has_video, has_lp, advertiser metrics, emotion scores)
   - 308 ads processed
   - Export: exports/feature_matrix.json

2. **simple_hit_predictor.py** - Correlation-weighted hit predictor
   - Pearson correlation weights: top features = advertiser_avg_score (r=0.99), month_first_seen (r=0.72), genre_beauty (r=0.56)
   - Accuracy: 81.49%, Precision: 64.10%, Recall: 99.01%, F1: 77.82%
   - Confusion matrix: TP=100, FP=56, TN=151, FN=1
   - Export: exports/predictor_weights.json

3. **calibrate_scores_v2.py** - Genre-relative z-score calibration
   - 308 ads calibrated with genre-relative z-scores + distribution enforcement
   - Before: 24% above 70, 16.2% mid, 59.7% below 30
   - After: 20.1% above 70, 60.1% mid, 19.8% below 30 (matches targets)
   - Stored in ad_metadata["calibrated_score"] and ad_metadata["score_calibration_v2"]

4. **cohort_analysis.py** - Weekly cohort analysis
   - 51 weekly cohorts analyzed, declining trend (r=-0.66)
   - Best cohort: 2024-W44 (avg_score=93.0, n=1)
   - Worst cohort: 2026-W09 (avg_score=5.5, n=110)
   - Average hit rate: 85.5%
   - Export: exports/cohort_analysis.json

### Task A23: Duplicate & Similar Ad Detection [COMPLETED]

1. **detect_similar_titles.py** - Title similarity via character trigram Jaccard
   - 308 ads, 305 with titles, 46360 pairwise comparisons
   - 45 clusters found, 44 near-duplicate clusters (sim>0.85)
   - 205 ads in near-duplicate clusters, 208 ads with similar titles
   - Updated ad_metadata["similar_ads"] for 208 ads
   - Export: exports/similar_ad_clusters.json

2. **detect_advertiser_variants.py** - A/B test pair detection
   - 49 advertisers with 2+ ads analyzed
   - 0 A/B test pairs (same-advertiser ads share identical hook/cta), 9 similar title pairs
   - Export: exports/ab_test_pairs.json

3. **dedupe_creative_patterns.py** - Creative pattern fingerprinting
   - 14 unique creative patterns across 308 ads
   - Largest group: unknown+unknown+other (123 ads, 1.6% hit rate)
   - Best performing: unknown+unknown+diet_supplement (avg 86.4, 100% hit rate)
   - Updated ad_metadata with pattern_fingerprint, pattern_group_size, pattern_rank_in_group
   - Export: exports/creative_pattern_groups.json

4. **update_similarity_metadata.py** - Consolidate similarity metadata
   - 208 ads updated with similar_ad_ids
   - 205 ads in near-duplicate clusters with duplicate_cluster_id
   - All 308 ads processed and stamped with similarity_updated_at

### Task A24: Advanced Text Analytics & Copy Analysis [COMPLETED]

1. **mine_title_patterns.py** - Title pattern mining
   - 22 patterns across 7 types: numeric, question, before_after, authority, urgency, emotional, benefit
   - Top hit rate: N_people (100%, n=8), N_yen (87.5%, n=8), N_percent (71.4%, n=14)
   - Export: exports/title_patterns_v2.json

2. **analyze_cta_effectiveness.py** - CTA effectiveness analysis
   - All 308 ads have cta_type=none in ad_analyses (ad_analyses not populated with CTA classification)
   - 13 genres analyzed, exported genre breakdown
   - Export: exports/cta_effectiveness.json

3. **hook_conversion_analysis.py** - Hook-to-conversion analysis
   - Same pattern: hook_type=none for all ads in ad_analyses table
   - Golden combos calculated per genre based on available data
   - Export: exports/hook_cta_matrix.json

4. **score_readability.py** - Title readability scorer
   - 308 ads scored, avg readability: 54.2, range: 0-71
   - Distribution: 0-9: 1%, 30-39: 1.6%, 40-49: 16.9%, 50-59: 41.9%, 60-69: 38.3%, 70-79: 0.3%
   - Correlation with hit_score: r=0.02 (weak)
   - Stored in ad_metadata["readability_score"]

### Task A25: Market Intelligence & Competitive Analysis [COMPLETED]

1. **analyze_market_share.py** - Market share analysis
   - 15 genres, 148 advertisers analyzed
   - Top leaders: Liven (19 ads, 2 genres), NetShort-GLN (13), カルピス健康通販 (12 ads, 7 hits)
   - Export: exports/market_share.json

2. **track_trend_velocity.py** - Trend velocity tracker
   - 4 rapid_growth: other, entertainment, ec_shopping, hair_growth_aga
   - 7 stable: health_food, skincare, beauty_clinic, app, fitness, medical_weight_loss, diet_supplement
   - 4 emerging: finance_investment, yoga_pilates, hair_removal, protein_supplement
   - Export: exports/trend_velocity.json

3. **detect_creative_fatigue.py** - Creative fatigue detection
   - 1 pattern showing fatigue (none+none: 1st half avg 59.7 → 2nd half 6.4)
   - Most ads lack classified hook/cta types, limiting granularity
   - Export: exports/creative_fatigue.json

4. **find_opportunities.py** - Opportunity finder
   - 4 underserved genres: other (56 ads, avg 2.5), entertainment (45, avg 6.6), hair_growth_aga (19, avg 15.9), app (11, avg 11.6)
   - All below market avg of 33.0
   - Export: exports/opportunities.json

### Task A26: Advanced Export & Automated Reporting [COMPLETED]

1. **export_presentation_data.py** - Presentation data export
   - 6 slides: Executive Summary, Genre Breakdown, Top 10 Ads, Creative Patterns, Market Trends, Recommendations
   - Export: exports/presentation_data.json

2. **generate_competitive_report.py** - Competitive report
   - Top 20 advertisers profiled: ad count, hit rate, avg score, genre, trend
   - Top performer: めちゃ痩せ (9 ads, 100% hit rate, score 93.0)
   - Export: exports/competitive_report.md + competitive_report.json

3. **generate_weekly_digest.py** - Weekly digest
   - 111 new ads this week, 42 new advertisers
   - Genre of the week: other (46 new ads)
   - Export: exports/weekly_digest_2026-02-28.json

4. **custom_query.py** - CLI ad-hoc query tool
   - Supports --genre, --advertiser, --min-score, --hit-only, --top, --format (csv/json/table), --sort
   - Tested: `--genre skincare --min-score 70 --top 5` = 5 results returned correctly

### Task A27: 日本語広告の大量取得 & ジャンルバランス改善 [COMPLETED]

1. **generate_crawl_keywords.py** - Crawl keyword generation
   - 15 genres analyzed, 10 underrepresented identified
   - 6 critical priority (education, jobs, real_estate, protein, hair_removal, yoga)
   - 2 high priority (finance, diet_supplement)
   - 58 total keywords generated
   - Export: exports/crawl_keywords_suggestion.json

2. **crawl_japanese_ads.py** - Meta Ad Library API crawler
   - Reads keywords from exports, fetches via Meta API (country=JP)
   - Supports DRY RUN when META_ACCESS_TOKEN not set
   - Dry run: 10 genres, 58 keywords, est. 1450 ads
   - Deduplication by external_id, auto category assignment

3. **auto_quality_check.py** - Automated quality checker
   - 308 ads checked, avg quality score: 94.6
   - 87 flagged (28.2%): 65 non-Japanese, 11 short description, 7 URL-as-title, 3 missing title
   - 0 missing categories, 0 missing fine_genre
   - Supports --fix flag for auto-correction
