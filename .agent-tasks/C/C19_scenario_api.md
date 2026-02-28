# Agent C Task: Ad Scenario Generation API

## Concept
「圧倒的に削減。誰でも簡単に広告のシナリオが作成できる！」
API endpoints for ad scenario generation, template browsing, and scenario saving.

## What to do

### 1. Scenario templates endpoint
`GET /rankings/scenario-templates`
- Query params: genre (optional), archetype (optional)
- Returns available scenario templates grouped by genre
- Each template: archetype_name, hit_rate, avg_score, structure, example_ad_ids
- Data source: `backend/exports/scenario_database.json` (created by Agent A)
- If file doesn't exist, return fallback templates from SCENARIO_FALLBACK constant

Response:
```json
{
  "genres": [
    {
      "genre": "医療痩身",
      "genre_en": "medical_weight_loss",
      "templates": [
        {
          "archetype_name": "Before/After変身型",
          "archetype_en": "before_after_transformation",
          "hit_rate": 0.78,
          "avg_score": 72.5,
          "structure": {...},
          "best_hooks": [...],
          "best_ctas": [...],
          "power_words": [...],
          "example_ad_ids": [...]
        }
      ]
    }
  ]
}
```

### 2. Generate scenario endpoint
`POST /rankings/generate-scenario`
- Body:
```json
{
  "genre_en": "medical_weight_loss",
  "product_name": "サクラクリニック",
  "target_audience": "30代女性",
  "key_benefit": "1ヶ月で-5kg",
  "cta_type": "line_add",
  "archetype": "before_after_transformation",
  "duration_seconds": 30,
  "platform": "instagram"
}
```
- Returns complete generated scenario:
```json
{
  "scenario": {
    "title_options": [
      "【衝撃】たった1ヶ月で-5kg！サクラクリニックの秘密",
      "30代女性必見！医療痩身で確実に痩せる方法",
      "もう無理なダイエットは不要。サクラクリニックのGLP-1"
    ],
    "hook": {
      "type": "shock",
      "text": "【衝撃】たった1ヶ月で-5kgを実現",
      "duration": "0:00-0:03"
    },
    "problem": {
      "text": "30代になって痩せにくくなった...何をしても体重が落ちない...",
      "duration": "0:03-0:08"
    },
    "solution": {
      "text": "サクラクリニックのGLP-1医療痩身なら、無理な運動や食事制限なしで-5kg",
      "duration": "0:08-0:18"
    },
    "proof": {
      "text": "すでに1,000名以上が体験。Before/After写真で効果を実感",
      "duration": "0:18-0:25"
    },
    "cta": {
      "type": "line_add",
      "text": "今すぐLINE追加で無料カウンセリング予約",
      "duration": "0:25-0:30"
    },
    "full_script": "complete narration text...",
    "power_words_used": ["衝撃", "たった", "簡単", "今すぐ"],
    "predicted_score": 72,
    "confidence": "medium",
    "reference_ads": [{"ad_id": 123, "score": 85, "similarity": 0.8}]
  }
}
```

### 3. Scenario variations endpoint
`POST /rankings/scenario-variations`
- Body: { "base_scenario": {...from generate}, "variation_count": 5 }
- Returns N variations with different hooks/CTAs/tones
- Each variation has predicted_score

### 4. Save scenario endpoint
`POST /rankings/saved-scenarios`
- Body: { "name": "キャンペーン1月", "scenario": {...}, "genre": "medical_weight_loss" }
- Store in `backend/data/saved_scenarios.json`
- Returns: { "id": "sc_001", "name": "...", "saved_at": "..." }

`GET /rankings/saved-scenarios`
- List all saved scenarios

`DELETE /rankings/saved-scenarios/{id}`
- Delete saved scenario

### 5. Scenario archetypes reference
`GET /rankings/scenario-archetypes`
- Returns all available archetypes with descriptions:
  - problem_solution: 問題提示→解決型
  - before_after_transformation: ビフォーアフター変身型
  - testimonial_story: 体験談ストーリー型
  - authority_expert: 権威・専門家推薦型
  - urgency_limited: 緊急性・限定型
  - comparison: 比較型（他社比較、自分比較）
  - tutorial_howto: ハウツー・使い方型
  - lifestyle: ライフスタイル提案型
- Each with hit_rate, best_genres, example count

### 6. Scenario performance predictor
`POST /rankings/predict-scenario-performance`
- Body: { "title": "...", "description": "...", "hook_type": "question", "cta_type": "line_add", "genre": "medical_weight_loss" }
- Uses existing hit prediction model + power word analysis
- Returns: { "predicted_score": 72, "hit_probability": 0.65, "suggestions": [...], "strengths": [...], "weaknesses": [...] }

## Implementation Notes
- Load scenario_database.json at module level (with caching)
- If scenario DB doesn't exist, use SCENARIO_FALLBACK with basic templates
- Template-based generation: fill {placeholders} with user input
- Score prediction uses existing feature importance data
- Store saved scenarios in backend/data/saved_scenarios.json (create data/ dir if needed)

## Constraints
- Only modify rankings.py
- Use existing helpers (_resolve_thumbnail_url, _safe_json, etc.)
- All print() must be English only
- Template-based generation (no external AI API calls)
