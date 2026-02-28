# Agent A Task: Fine-Grained Genre & Product Classification

## Reference
The user wants granularity like professional ad analysis tools:
- NOT just "beauty" or "health" but specific like: 医療痩身, ダイエットサプリ, 美容クリニック, 脱毛サロン, etc.
- Product name extraction from ad title (e.g. "サクラクリニック マンジャロ", "auravita ウゴービ")

## What to do

### 1. Fine-grained genre classifier
`backend/scripts/classify_fine_genre.py`

Define detailed genre taxonomy (Japanese ad market):
```
医療痩身 (Medical Weight Loss): GLP-1, マンジャロ, ウゴービ, 痩身クリニック, 医療ダイエット
ダイエットサプリ (Diet Supplement): サプリ, 酵素, 燃焼, 代謝, ファスティング
美容クリニック (Beauty Clinic): 美容整形, ヒアルロン酸, ボトックス, 二重, 美容外科
スキンケア (Skincare): 化粧水, 美容液, クレンジング, 保湿, 美白クリーム
脱毛 (Hair Removal): 脱毛, 医療脱毛, 光脱毛, VIO, 全身脱毛
育毛・AGA (Hair Growth): 育毛, AGA, 薄毛, 発毛, ミノキシジル
フィットネス (Fitness): ジム, パーソナル, トレーニング, RIZAP, ボディメイク
ヨガ・ピラティス (Yoga): ヨガ, ピラティス, ストレッチ, マインドフルネス
プロテイン (Protein): プロテイン, BCAA, HMB, 筋肉サプリ
健康食品 (Health Food): 青汁, コラーゲン, 乳酸菌, 酵素ドリンク
EC通販 (EC/Shopping): 通販, ショッピング, セール, 割引
アプリ (App): アプリ, ダウンロード, インストール
金融・投資 (Finance): 投資, FX, 仮想通貨, クレジットカード, ローン
教育・スクール (Education): スクール, 講座, 資格, プログラミング, 英会話
不動産 (Real Estate): マンション, 不動産, 賃貸, 住宅
転職・求人 (Jobs): 転職, 求人, バイト, 就職
その他 (Other): above に当てはまらないもの
```

For each ad:
1. Scan title + description for keywords
2. Score each genre by keyword match count
3. Assign the best matching fine_genre
4. Store in ad_metadata["fine_genre"] = "医療痩身" etc.
5. Store ad_metadata["fine_genre_en"] = "medical_weight_loss" (for API)

### 2. Product name extractor
`backend/scripts/extract_product_names.py`

From each ad's title:
1. Extract the product/brand name:
   - If title has a known brand pattern (カタカナ + カタカナ): extract it
   - If title starts with a brand name before a space/separator: extract it
   - Common patterns: "【ブランド名】", "ブランド名 - ", "ブランド名｜"
2. Store in ad_metadata["product_name"]
3. Cross-reference with advertiser_name for validation
4. Print: extracted X product names out of Y ads

### 3. Genre-specific crawl keywords
`backend/config/genre_crawl_keywords.json`
```json
{
  "医療痩身": ["GLP-1 ダイエット", "マンジャロ クリニック", "医療痩身"],
  "ダイエットサプリ": ["ダイエットサプリ", "痩せるサプリ", "脂肪燃焼サプリ"],
  "美容クリニック": ["美容クリニック", "美容整形", "二重整形"],
  "脱毛": ["医療脱毛", "全身脱毛", "脱毛サロン"],
  ...etc for each genre
}
```
This config will be used by the crawl system to get genre-specific ads.

### 4. Metrics estimator
`backend/scripts/estimate_metrics.py`

For ads where we have impressions/spend data:
- Calculate estimated_total_views (from impressions or reach)
- Calculate estimated_spend_total (from spend * estimated_days_running)
- Calculate view_increase_daily = impressions / days_running
- Calculate spend_increase_daily = spend / days_running
- Store in ad_metadata["estimated_metrics"]:
```json
{
  "total_views": 10997,
  "view_increase_daily": 523,
  "estimated_total_spend_jpy": 43988,
  "spend_increase_daily_jpy": 2095,
  "like_increase_daily": 12
}
```

For ads WITHOUT these metrics, estimate from:
- duration_days * estimated_daily_impressions (from metadata)
- estimated_cpm_jpy from metadata * impressions / 1000

## Constraints
- English-only print, flag_modified, no rankings.py/frontend/media.py changes
