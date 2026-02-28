# Agent C Task: Creative Intelligence & Template API

## What to do

### 1. Creative brief generation endpoint
`POST /rankings/creative-brief`
- Body: { "genre": "skincare", "target": "20代女性", "goal": "cv", "budget": "medium" }
- Returns generated creative brief:
```json
{
  "recommended_hooks": [{"type": "question", "example": "...?", "hit_rate": 0.65}],
  "recommended_ctas": [{"type": "urgency", "example": "今すぐ...", "hit_rate": 0.58}],
  "power_words": ["驚きの", "たった", "今だけ"],
  "structure": {"sections": ["hook", "problem", "solution", "proof", "cta"]},
  "reference_ads": [{"id": 1, "title": "...", "score": 82}],
  "predicted_score": 65,
  "genre_insights": "skincare genre has 65% hit rate with question hooks"
}
```

### 2. Copy variations endpoint
`POST /rankings/copy-variations`
- Body: { "title": "original title", "genre": "skincare", "variations": 5 }
- Returns title variations:
```json
{
  "original": "original title",
  "variations": [
    {"title": "...", "hook_type": "question", "tone": "casual", "predicted_score": 68},
    {"title": "...", "hook_type": "number", "tone": "professional", "predicted_score": 72}
  ]
}
```

### 3. Pattern effectiveness endpoint
`GET /rankings/pattern-effectiveness`
- Query: genre (optional)
- Returns pattern effectiveness matrix:
```json
{
  "hook_cta_matrix": {
    "question": {"urgency": {"count": 12, "avg_score": 68, "hit_rate": 0.58}},
    "number": {"benefit": {"count": 8, "avg_score": 72, "hit_rate": 0.62}}
  },
  "golden_combos": [
    {"hook": "question", "cta": "urgency", "genre": "skincare", "hit_rate": 0.65}
  ],
  "avoid_combos": [
    {"hook": "shock", "cta": "soft", "hit_rate": 0.12, "reason": "Low engagement"}
  ]
}
```

### 4. Readability scoring endpoint
`POST /rankings/score-readability`
- Body: { "title": "some ad title", "genre": "skincare" }
- Returns readability analysis:
```json
{
  "score": 78,
  "factors": {
    "length": {"value": 35, "optimal": true, "score": 10},
    "has_numbers": true,
    "power_word_count": 2,
    "has_question": false,
    "kanji_ratio": 0.3
  },
  "suggestions": ["質問形式のフックを追加すると+12%のヒット率向上が期待できます"],
  "genre_benchmark": {"avg_score": 62, "percentile": 75}
}
```

### 5. Template marketplace endpoint
`GET /rankings/template-marketplace`
- Query: genre, sort_by (hit_rate|popularity|newest), page, page_size
- Returns community templates:
```json
{
  "templates": [
    {
      "id": "t_001",
      "name": "美容系・質問型フック",
      "genre": "skincare",
      "archetype": "testimonial_story",
      "hit_rate": 0.65,
      "usage_count": 23,
      "preview": "なぜ○○は△△なのか？...",
      "tags": ["高CVR", "初心者向け"]
    }
  ],
  "total": 45
}
```

## Constraints
- Only modify rankings.py
- All print() English only
- Use existing helper functions
