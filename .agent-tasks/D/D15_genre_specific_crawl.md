# Agent D Task: Genre-Specific Crawl System

## Goal
Crawl ads by specific fine genres/product categories, not just broad keywords.
This lets users get ads specifically for 医療痩身, ダイエットサプリ, 美容クリニック, etc.

## What to do

### 1. Genre crawl script
`backend/scripts/genre_crawl.py`
- Read genre keywords from `backend/config/genre_crawl_keywords.json` (created by Agent A)
- If config doesn't exist yet, use built-in defaults:
```python
GENRE_KEYWORDS = {
    "medical_weight_loss": ["GLP-1 ダイエット", "マンジャロ 痩身", "医療痩身 クリニック", "ウゴービ"],
    "diet_supplement": ["ダイエットサプリ", "痩せるサプリ", "脂肪燃焼 サプリメント"],
    "beauty_clinic": ["美容クリニック 整形", "二重 美容外科", "ヒアルロン酸 注入"],
    "skincare": ["スキンケア 美容液", "化粧水 おすすめ", "美白 クリーム"],
    "hair_removal": ["医療脱毛", "全身脱毛 サロン", "VIO脱毛"],
    "hair_growth": ["AGA クリニック", "育毛剤", "薄毛 治療"],
    "fitness": ["パーソナルジム", "RIZAP", "ダイエット ジム"],
    "protein": ["プロテイン おすすめ", "HMB サプリ", "筋肉 サプリメント"],
    "health_food": ["青汁", "コラーゲン ドリンク", "酵素 サプリ"],
    "finance": ["FX 口座開設", "投資 アプリ", "クレジットカード"],
    "education": ["プログラミング スクール", "英会話 オンライン", "資格 講座"],
}
```
- Command-line arg: --genre medical_weight_loss (single genre) or --all (all genres)
- For each genre: crawl all keywords, tag new ads with fine_genre in ad_metadata
- Download media for new ads immediately
- Print per-genre results

### 2. Update media.py
Add endpoint:
`POST /media/genre-crawl`
- Body: { "genre_key": "medical_weight_loss" }
- Calls genre_crawl logic directly (import from script)
- Returns: { new_ads: X, genre: "医療痩身" }

### 3. Post-crawl tagging
After genre-specific crawl, automatically:
- Set ad_metadata["fine_genre"] based on which genre keywords were used
- Set ad_metadata["fine_genre_en"] for the English key
- Set ad_metadata["crawl_source"] = "genre_crawl"
- Download thumbnails/images for new ads

## Constraints
- English-only print, no rankings.py/frontend changes
- Only modify media.py and scripts/ and config/
- Handle cases where config file doesn't exist (use defaults)
