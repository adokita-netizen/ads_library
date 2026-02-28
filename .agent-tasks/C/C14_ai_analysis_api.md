# Agent C Task: AI-Powered Analysis API (Rekognition + Predictions)

## Goal
API endpoints to serve AI analysis results: Rekognition data, hit predictions, creative intelligence.

## What to do

### 1. Creative intelligence endpoint
Add to rankings.py:
`GET /rankings/creative-intelligence/{ad_id}`
- Return full creative intelligence object from ad_metadata["creative_intelligence"]
- Include: visual elements, text overlay, sentiment, key phrases, strengths, weaknesses
- Fallback: return creative_analysis if full intelligence not available

### 2. Hit prediction endpoint
`GET /rankings/predict-hit/{ad_id}`
- Return hit prediction from ad_metadata["hit_prediction"]
- Include: probability, confidence, positive/negative factors, recommendation

`POST /rankings/predict-hit`
- Body: { hook_type, cta_type, offer_type, emotion, creative_type, text_length, ... }
- Run prediction on custom input (for planning new creatives)
- Return: predicted hit probability + recommendations

### 3. LP analysis endpoint
`GET /rankings/lp-analysis/{ad_id}`
- Return LP data, LP score, LP alignment score, funnel score
- Include LP screenshot URL (via media proxy)
- Include LP CTA buttons, form fields, testimonials found

`GET /rankings/lp-benchmark`
- Return LP score benchmarks by genre
- Correlation data: LP score vs ad hit rate

### 4. Competitor intelligence endpoint
`GET /rankings/competitors`
- List top competitors with stats
- Params: genre filter, sort_by
- Return: name, ad_count, hit_rate, strategy summary, trend

`GET /rankings/competitor/{name}`
- Deep profile of specific competitor
- All their ads, strategy evolution, predicted next move

`GET /rankings/market-gaps`
- Return under-served opportunities
- Genres, hooks, CTAs that are underused but effective

### 5. Recommendation endpoint
`GET /rankings/recommendations`
- Query: genre (required)
- Return: ideal creative formula for that genre
- Based on feature importance + winning formulas
- Example: "For beauty genre: use pain_point hook + line_add CTA + fear emotion. Include before/after and testimonials. Keep text 100-200 chars."

## Constraints
- Only modify rankings.py
- Graceful fallback when AI data not available
