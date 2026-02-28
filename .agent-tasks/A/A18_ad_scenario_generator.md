# Agent A Task: Ad Scenario Template Generator

## Concept
「圧倒的に削減。誰でも簡単に広告のシナリオが作成できる！」
Analyze winning ad patterns and generate reusable scenario templates.
Users can select a genre + product type and get a complete ad script/scenario.

## What to do

### 1. Scenario template extractor
`backend/scripts/extract_scenario_templates.py`

Analyze existing hit ads (score >= 60) to extract scenario structures:
- For each hit ad, decompose into scenario components:
  - **Hook** (opening 0-3s): What grabs attention? Question? Shock? Benefit?
  - **Problem** (3-8s): What pain point is addressed?
  - **Solution** (8-15s): How does the product solve it?
  - **Proof** (15-22s): Testimonials? Before/After? Data?
  - **CTA** (22-30s): What action is requested?
- Group similar structures into "scenario archetypes"
- Rank archetypes by average hit_score

Store in ad_metadata["scenario_structure"]:
```json
{
  "archetype": "problem_solution",
  "hook_type": "question",
  "hook_text_example": "あなたの肌、本当に大丈夫？",
  "problem_keywords": ["悩み", "肌荒れ"],
  "solution_approach": "product_demo",
  "proof_type": "before_after",
  "cta_type": "line_add",
  "estimated_duration_seconds": 29,
  "scenario_score": 85
}
```

### 2. Genre-specific scenario database
`backend/scripts/build_scenario_database.py`

For each fine_genre, generate:
```json
{
  "genre": "医療痩身",
  "genre_en": "medical_weight_loss",
  "top_scenarios": [
    {
      "archetype_name": "Before/After変身型",
      "archetype_en": "before_after_transformation",
      "hit_rate": 0.78,
      "avg_score": 72.5,
      "sample_count": 15,
      "structure": {
        "hook": {"type": "shock", "template": "【衝撃】{期間}で{数字}kg痩せた方法"},
        "problem": {"template": "{ターゲット}の悩みを提示"},
        "solution": {"template": "{商品名}の特徴を3つ紹介"},
        "proof": {"template": "ビフォーアフター写真 + 利用者の声"},
        "cta": {"template": "{CTA文言} → {遷移先}"}
      },
      "best_hooks": ["衝撃の結果", "たった{期間}で", "もう悩まない"],
      "best_ctas": ["今すぐ無料相談", "LINE追加で特典GET", "初回限定{割引}%OFF"],
      "power_words": ["驚き", "簡単", "たった", "今だけ"],
      "example_ad_ids": [123, 456, 789]
    }
  ],
  "recommended_duration": 29,
  "recommended_format": "video",
  "genre_power_words": ["GLP-1", "マンジャロ", "医療", "痩身"],
  "avoid_words": [],
  "optimal_text_length": {"title": 35, "description": 120}
}
```

Export to: `backend/exports/scenario_database.json`

### 3. Scenario text generator
`backend/scripts/generate_scenario_text.py`

Given a genre + product info, generate a complete ad scenario:
- Input: genre_en, product_name, target_audience, key_benefit, cta_type
- Output: Complete scenario with:
  - Title options (3 variations)
  - Hook text (3 variations)
  - Body text (problem + solution + proof)
  - CTA text (3 variations)
  - Recommended power words
  - Estimated performance score
  - Duration recommendation
  - Reference hit ads

Usage:
```bash
python scripts/generate_scenario_text.py --genre medical_weight_loss --product "サクラクリニック" --benefit "1ヶ月で-5kg" --cta line_add
```

The generator uses rule-based templates from the scenario database (NOT AI API calls).
Fill in {placeholders} with provided product info.
Score each generated scenario based on how closely it matches winning patterns.

### 4. Scenario variation generator
`backend/scripts/generate_scenario_variations.py`

From one base scenario, generate N variations:
- Hook variations: swap hook type (question→shock, benefit→question, etc.)
- CTA variations: different CTA types
- Tone variations: formal/casual/urgent
- Length variations: 15s/30s/60s
- Platform-specific: Facebook vs Instagram vs TikTok adjustments

Each variation gets a predicted hit probability based on the trained model.

## Constraints
- English-only print, flag_modified
- No rankings.py/frontend/media.py changes
- Use existing data from ad_metadata (creative_analysis, keywords, power_words, hit_prediction)
- Template-based generation, no external AI API calls required
