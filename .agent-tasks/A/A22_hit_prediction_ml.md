# Agent A Task: Hit Prediction Model & Scoring Enhancement

## What to do

### 1. Feature engineering script
Create `backend/scripts/build_feature_matrix.py`:
- Extract features from all 308 ads for prediction:
  - Title length, word count, power word count
  - Hook type (one-hot encoded as numeric)
  - CTA type (one-hot encoded as numeric)
  - Genre (encoded)
  - Has video (0/1), has LP (0/1)
  - Advertiser ad count, advertiser avg score
  - Day of week first seen, month first seen
  - Title sentiment keywords count (positive/negative)
- Output: `exports/feature_matrix.json` with feature names + values per ad
- Print feature importance summary

### 2. Simple hit predictor (no ML libraries needed)
Create `backend/scripts/simple_hit_predictor.py`:
- Rule-based scoring using weighted features
- Weights learned from correlation with actual hit_score:
  - For each feature, compute correlation with hit_score
  - Use correlation as weight
- Predict hit probability for each ad
- Compare prediction vs actual: accuracy, precision, recall
- Store weights in `exports/predictor_weights.json`
- Print confusion matrix (text format)

### 3. Score calibration v2
Create `backend/scripts/calibrate_scores_v2.py`:
- Load current hit_scores from DB
- Apply genre-relative scoring: score = (ad_score - genre_avg) / genre_std * 20 + 50
- Normalize to 0-100 range
- Ensure distribution: ~20% above 70 (hit), ~60% in 30-70, ~20% below 30
- Update DB with calibrated scores
- Print before/after distribution

### 4. Cohort analysis script
Create `backend/scripts/cohort_analysis.py`:
- Group ads by first_seen week
- Track cohort metrics over time: avg score, survival rate, view growth
- Identify: do newer ads perform better/worse than older ones?
- Output to `exports/cohort_analysis.json`

## Constraints
- English-only print, flag_modified
- No external ML libraries (no sklearn, tensorflow, etc)
- No rankings.py/frontend/media.py changes
