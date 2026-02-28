# Agent A Task: Advanced Text Analytics & Copy Analysis

## What to do

### 1. Title pattern mining
Create `backend/scripts/mine_title_patterns.py`:
- Extract common title patterns/templates from all 308 ads
- Find: [数字] + [keyword] patterns (e.g., "3つの理由", "たった1分で")
- Find: question patterns (〜ですか？〜しませんか？)
- Find: before/after patterns (〜から〜へ, ビフォーアフター)
- Find: authority patterns (医師監修, 専門家推奨)
- Rank patterns by hit rate
- Output to `exports/title_patterns_v2.json`
- Print top 20 patterns with hit rates

### 2. CTA effectiveness analysis
Create `backend/scripts/analyze_cta_effectiveness.py`:
- Deep analysis of CTA types and their performance
- For each CTA type: count, avg score, hit rate, avg views, avg spend
- Cross-tabulate CTA × genre for genre-specific effectiveness
- Identify: best CTA per genre, worst CTA per genre
- Output to `exports/cta_effectiveness.json`
- Print effectiveness matrix

### 3. Hook-to-conversion analysis
Create `backend/scripts/hook_conversion_analysis.py`:
- Analyze which hook types lead to highest estimated spend (proxy for conversion)
- Hook × CTA combination effectiveness matrix
- Find the "golden combination" per genre
- Output to `exports/hook_cta_matrix.json`
- Print: "Best combination for [genre]: [hook] + [cta] (hit rate: X%)"

### 4. Readability scorer
Create `backend/scripts/score_readability.py`:
- Score each ad's title readability:
  - Character count (optimal: 25-50 chars)
  - Contains numbers? (+5)
  - Contains power words? (+3 per word)
  - Contains question? (+5)
  - Excessive kanji ratio? (-5)
  - Too many symbols? (-3)
- Store in ad_metadata.readability_score = {"score": 78, "factors": {...}}
- Use flag_modified
- Print distribution and correlation with hit_score

## Constraints
- English-only print, flag_modified
- No external NLP libraries
- No rankings.py/frontend/media.py changes
