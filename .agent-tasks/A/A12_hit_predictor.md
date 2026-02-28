# Agent A Task: Hit Creative Predictor (AI Scoring Model)

## Goal
Build a predictive model: given a creative's features, predict if it will be a HIT. The ultimate value proposition.

## What to do

### 1. Feature engineering
`backend/scripts/build_prediction_features.py`
- For each ad, compile feature vector:
  - creative_analysis features (hook_type, cta_type, offer_type, emotion) -> one-hot encoded
  - text_length (normalized)
  - has_emoji, has_numbers, has_testimonial, has_before_after (binary)
  - creative_type (video=1, image=0)
  - title_word_count
  - description_word_count
  - power_word_count (from A11)
  - LP features if available (has_form, has_video, etc.)
  - Rekognition features if available (face_count, text_count, label_count)
- Store feature vector in ad_metadata["prediction_features"]
- Export feature matrix to `backend/exports/feature_matrix.csv`

### 2. Simple prediction model
`backend/scripts/train_hit_predictor.py`
- Use scikit-learn (or pure numpy if sklearn unavailable):
  - LogisticRegression or DecisionTree
  - Target: is_hit (boolean)
  - Train/test split: 80/20
  - Cross-validation: 5-fold
- Output:
  - Model accuracy, precision, recall, F1
  - Feature importance ranking
  - Confusion matrix
- Save model to `backend/models/hit_predictor.pkl`
- Save feature importance to `backend/exports/feature_importance.json`

### 3. Prediction script
`backend/scripts/predict_hit.py`
- Load saved model
- For new/unscored ads, predict hit probability
- Store prediction in ad_metadata["hit_prediction"]:
```json
{
  "probability": 0.78,
  "confidence": "high",
  "top_positive_factors": ["pain_point hook", "line_add CTA"],
  "top_negative_factors": ["no urgency", "long text"],
  "recommendation": "Add urgency element to boost hit probability"
}
```

### 4. Creative recommendation engine
`backend/scripts/generate_recommendations.py`
- Based on the model, for each genre:
  - What's the ideal creative formula?
  - What elements should you include?
  - What to avoid?
- Export to `backend/exports/creative_recommendations.json`

## Constraints
- English-only print, flag_modified
- If sklearn not available, use simple rule-based scoring
- No rankings.py/frontend changes
