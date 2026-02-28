# Agent C Task: Professional Ad Ranking API (Like 動画広告分析プロ)

## Reference
Replicate a professional ad analysis tool with these exact features:

### Hit Line Concept (CRITICAL)
"ヒットライン" = for each genre/product, calculate the average views of the TOP 20% creatives.
Any ad that exceeds this threshold gets "ヒットライン超え" badge.
This must be computed per fine_genre, not globally.

### Pro Database Table
Columns: 順位, サムネイル, 商材名, ジャンル, 再生増加数, 累計再生回数, 予想消化増加額, 累計予想消化額, いいね増加

### Search with Autocomplete
When user types "ダイエット", suggest:
- "ダイエット" → すべてから検索
- "ダイエット補助 で絞り込み" → ジャンル
- "ダイエットサプリ で絞り込み" → ジャンル
- "ダイエットドリンク で絞り込み" → ジャンル
- "A→ダイエット○○ で絞り込み" → 商材

### Comprehensive Genre List
ゲーム, サウナ, ジム・フィットネス, ショッピング, ストリーミングコンテンツサイト,
ソーシャルコンタクト, ネットショッピング, ペットその他, 印刷サービス, 害虫駆除,
観光スポットチケット, 給付金, 公益慈善, 公共サービス, 写真撮影, 趣味教養,
宿・ホテル, 生活サービス業, 占い, 宅食, 旅行, 恋愛・結婚, 法務・財務支援,
債務整理, 士業相談, 医療痩身, ダイエットサプリ, 美容クリニック, スキンケア,
脱毛, 育毛・AGA, フィットネス, ヨガ・ピラティス, プロテイン, 健康食品,
EC通販, アプリ, 金融・投資, 教育・スクール, 不動産, 転職・求人,
美容液, コスメ, ホワイトニング, エステ, マッチングアプリ, 宅配, 保険,
クリニック, 整体・整骨, 歯科, メンズ美容, レディースクリニック

## What to do

### 1. Hit line computation
Add to rankings.py:

`GET /rankings/hit-line`
- Query: fine_genre (optional, if omitted return all genres)
- For each fine_genre:
  - Get all ads in that genre
  - Sort by total_views (or impressions) desc
  - Take top 20%
  - Compute average views of that top 20% = HIT LINE threshold
  - Return: { genre, hit_line_views, hit_line_spend, ad_count, top20_count }

### 2. Pro ranking endpoint
`GET /rankings/pro-ranking`
Query params:
- fine_genre, platform, sort_by, period (7d/30d/all), page, per_page
- search_text: full-text search

Response:
```json
{
  "total": 150,
  "hit_line": { "views": 8500, "spend_jpy": 34000 },
  "fine_genres": ["医療痩身", "ダイエットサプリ", ...],
  "ads": [
    {
      "rank": 1,
      "ad_id": 123,
      "thumbnail_url": "/api/v1/media/thumbnail/123",
      "video_duration_seconds": 29,
      "platform": "facebook",
      "product_name": "サクラクリニック マンジャロ",
      "advertiser_name": "医療法人春陽会",
      "fine_genre": "医療痩身",
      "view_increase": 0,
      "total_views": 10997,
      "spend_increase_jpy": 0,
      "total_spend_jpy": 43988,
      "like_increase": 0,
      "is_above_hit_line": true,
      "hit_score": 85,
      "creative_type": "video",
      "destination_type": "記事LP",
      "destination_url": "https://...",
      "management_id": "N00123",
      "download_url": "/api/v1/media/download/123"
    }
  ]
}

### Spend Calculation Formula
予想消化額 = 再生増加数 × CPM
- Use estimated_cpm_jpy from ad_metadata if available
- Default CPM: ¥800 for Japanese market
- spend_increase_jpy = (view_increase / 1000) * cpm_jpy
- total_spend_jpy = (total_views / 1000) * cpm_jpy

### Destination Type Classification
From destination_url, classify:
- "公式サイト" = corporate/official domain
- "記事LP" = article-style landing page (contains /article, /lp, long path)
- "ECサイト" = e-commerce (amazon, rakuten, shopify, stores.jp)
- "LINE追加" = line.me links
- "アプリDL" = app store links (apps.apple.com, play.google.com)
- "SNS" = social media links
- Use ad_metadata["destination_type"] if already classified
```

### 3. Smart autocomplete with genre suggestions
`GET /rankings/smart-autocomplete`
- query: partial text (e.g. "ダイエット")
- Return:
```json
{
  "text_search": { "label": "ダイエット - すべてから検索", "type": "text" },
  "genre_matches": [
    { "label": "ダイエットサプリ で絞り込み", "type": "genre", "key": "ダイエットサプリ", "count": 15 },
    { "label": "ダイエット補助 で絞り込み", "type": "genre", "key": "ダイエット補助", "count": 8 }
  ],
  "product_matches": [
    { "label": "auravita ウゴービ で絞り込み", "type": "product", "key": "auravita ウゴービ", "count": 3 }
  ],
  "advertiser_matches": [
    { "label": "ONE MEDICAL株式会社 で絞り込み", "type": "advertiser", "key": "ONE MEDICAL株式会社", "count": 5 }
  ]
}
```

### 4. Search collection (saved filters)
`POST /rankings/search-collections` - save filter preset
- Body: { name: str, filters: { genre, platform, search_text, sort_by, period } }
- Store in backend/data/search_collections.json

`GET /rankings/search-collections` - list saved presets
`DELETE /rankings/search-collections/{id}` - delete preset

### 5. Genre master list endpoint
`GET /rankings/genre-master`
- Return the full genre taxonomy with:
  - Japanese name, English key, ad count, hit_line_views
  - Parent category (大カテゴリ: 美容系, 健康系, ビジネス系, 生活系, etc.)
  - Grouped by parent for sidebar display

## Constraints
- Only modify rankings.py
- Use _resolve_thumbnail_url etc. helpers
- Store genre master as a constant dict in rankings.py
