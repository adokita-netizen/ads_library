# Agent A Task: Advanced Ad Copy NLP Analysis

## Goal
Deep analysis of ad copy text. What words, phrases, structures make ads hit?

## What to do

### 1. Keyword extraction
`backend/scripts/extract_keywords.py`
- For each ad, extract top keywords from title + description
- Use TF-IDF or simple frequency analysis (no external NLP library needed)
- Store top 10 keywords in ad_metadata["keywords"]
- Build corpus-wide keyword frequency table
- Export to `backend/exports/keyword_analysis.json`

### 2. Power words analysis
`backend/scripts/power_words.py`
- Define lists of Japanese "power words" by category:
  - Urgency: 今だけ, 限定, 残りわずか, 急いで, 本日限り
  - Social proof: 人気, 話題, 売上No.1, 満足度, レビュー
  - Benefit: 簡単, たった, だけで, 驚きの, 実感
  - Fear: 危険, 知らないと, 損, 後悔, 老化
  - Free: 無料, 0円, タダ, プレゼント, 特典
- Count occurrences in hit vs non-hit ads
- Calculate "power score" for each word (hit_rate when present)
- Export to `backend/exports/power_words.json`

### 3. Title structure analysis
`backend/scripts/analyze_title_structure.py`
- Classify title patterns:
  - Question type: ～ですか？～してませんか？
  - Number type: 3つの理由, 5選, 90%が
  - Testimonial: 私が～した結果, ～した体験談
  - Command: ～してください, ～しよう
  - Shock: 衝撃, まさか, 知らなかった
- Compute hit rate per pattern
- Export to `backend/exports/title_patterns.json`

### 4. Description length optimization
`backend/scripts/optimal_length.py`
- Analyze: what description length (chars) correlates with highest hit rate?
- Bucket by: 0-50, 50-100, 100-200, 200-500, 500+ chars
- Find sweet spot
- Export to `backend/exports/optimal_length.json`

## Constraints
- English-only print, flag_modified, no rankings.py/frontend changes
- Use only stdlib + regex (no NLTK, spaCy, etc.)
