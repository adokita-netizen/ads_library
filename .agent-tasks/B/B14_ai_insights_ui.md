# Agent B Task: AI Insights & Creative Intelligence UI

## Goal
Display all AI analysis results beautifully. Show Rekognition labels, hit predictions, and creative recommendations.

## What to do

### 1. Creative Intelligence panel
Create `frontend/src/components/dashboard/CreativeIntelligence.tsx`:
- When viewing ad detail, show AI analysis:
  - Visual elements detected (labels with confidence bars)
  - Text detected in image (OCR results)
  - Face/emotion analysis
  - Sentiment badge (positive/negative/neutral)
  - Key phrases highlighted
- Data from GET /api/v1/rankings/creative-intelligence/{ad_id}

### 2. Hit Prediction display
Create `frontend/src/components/dashboard/HitPrediction.tsx`:
- Big probability gauge (0-100%) with color coding
  - 80%+ = green "HIGH HIT POTENTIAL"
  - 50-80% = yellow "MODERATE"
  - <50% = red "LOW"
- Positive factors (green badges)
- Negative factors (red badges)
- Recommendation text box
- "How to improve" suggestions
- Data from GET /api/v1/rankings/predict-hit/{ad_id}

### 3. Creative builder/planner
Create `frontend/src/components/dashboard/CreativePlanner.tsx`:
- Select: genre, hook_type, cta_type, offer_type, emotion, creative_type
- Click "Predict Hit Rate"
- Shows predicted probability + recommendations
- "Show example hits with this formula" -> list of matching ads
- Data from POST /api/v1/rankings/predict-hit

### 4. Recommendation dashboard
Create `frontend/src/components/dashboard/Recommendations.tsx`:
- Select genre dropdown
- Show "Winning Formula" for that genre
- Ideal hook, CTA, offer, emotion combination
- Do's and Don'ts list
- Example winning ads carousel
- Data from GET /api/v1/rankings/recommendations?genre=xxx

### 5. Integration
Add to AdDetailModal: CreativeIntelligence + HitPrediction panels
Add to main dashboard: CreativePlanner + Recommendations sections

## Constraints
- Only frontend/src/, Tailwind, fetchApi, build must pass
