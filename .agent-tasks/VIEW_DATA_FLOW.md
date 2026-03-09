# データフロー視点 — 広告1件がDBに入ってから画面に表示されるまで

## 全体フロー

```
[Meta Ad Library]
      ↓ crawl_ads (Agent D)
[ads テーブル] ← 生データ (title, snapshot_url, advertiser_name, ...)
      ↓ classify_ads (Agent A)
[ads.category] ← ジャンル分類
      ↓ fix_titles, fix_destination_urls (Agent A)
[ads.title, ads.destination_url] ← クレンジング
      ↓ collect_delivery_dates (Agent A)
[ads.ad_metadata.delivery_start_time/stop_time] ← 配信期間
      ↓ check_ad_survival (Agent A)
[ads.ad_metadata.is_still_running, longevity_class] ← 生存チェック
      ↓ extract_missing_videos (Agent D)
[ads.video_url, image_url, thumbnail_url] ← メディアURL
      ↓ fix_bad_thumbnails (Agent D)
[ads.thumbnail_url, thumbnail_s3_key] ← サムネイル品質
      ↓ recompute_hit_scores (Agent C)
[product_rankings テーブル] ← hit_score, trend_score, is_hit, rank
[ads.ad_metadata.latest_hit_score, hit_level] ← スコア
      ↓ rankings.py API (Agent C)
[/api/v1/rankings/pro-ranking] ← JSON レスポンス
      ↓ ProRankingTable (Agent B)
[ブラウザ画面] ← テーブル表示
```

---

## 各ステージの詳細

### Stage 1: クロール (Agent D)

**入力**: キーワード or Meta Ad Library URL
**出力**: `ads` テーブルに1行INSERT

```sql
INSERT INTO ads (
  ad_id,              -- Meta Ad Library ID
  title,              -- 広告タイトル
  advertiser_name,    -- 広告主名
  snapshot_url,       -- Meta Ad Library のスナップショットURL
  description,        -- 広告テキスト
  platform,           -- facebook/instagram/etc
  status,             -- active/inactive
  ad_metadata,        -- {} (空のJSON)
  created_at
)
```

**この時点で欠けているもの**:
- video_url, image_url, thumbnail_url → NULL
- category → NULL
- destination_url → 不完全な場合あり
- ad_metadata → ほぼ空

---

### Stage 2: データ品質 (Agent A)

**classify_ads.py**:
```python
# 入力: ads.title, ads.description
# 出力: ads.category = "美容" | "健康食品" | "ダイエット" | ...
# ロジック: キーワードマッチング + ルールベース
```

**fix_titles.py**:
```python
# 入力: ads.title (空 or 不完全)
# 出力: ads.title (クレンジング済み)
# ロジック: snapshot_url からタイトル抽出、記号除去
```

**fix_destination_urls.py**:
```python
# 入力: ads.destination_url (空 or リダイレクト前URL)
# 出力: ads.destination_url (最終URL)
# ロジック: HTTP follow redirect
```

**collect_delivery_dates.py**:
```python
# 入力: ads.snapshot_url
# 出力: ad_metadata.delivery_start_time, delivery_stop_time
# ロジック: Meta API or スクレイピング
```

**check_ad_survival.py**:
```python
# 入力: ads.snapshot_url
# 出力: ad_metadata.is_still_running, longevity_class
# ロジック: snapshot_url にアクセスして配信中かチェック
```

---

### Stage 3: メディア抽出 (Agent D)

**extract_missing_videos.py → MediaExtractor**:
```python
# Stage 3a: HTTP + BeautifulSoup
#   入力: snapshot_url
#   出力: og:image, og:video メタタグからURL抽出

# Stage 3b: Playwright (フォールバック)
#   入力: snapshot_url
#   出力: JS実行後のDOMからメディアURL抽出
#   → video_url, image_url を ads テーブルに UPDATE
```

**fix_bad_thumbnails.py → ThumbnailFetcher**:
```python
# 入力: ads.thumbnail_url (403/低品質)
# 出力: S3にアップロード → ads.thumbnail_s3_key
# ロジック: 別URLで再取得、S3にキャッシュ
```

---

### Stage 4: スコアリング (Agent C)

**recompute_hit_scores.py → RankingService**:
```python
# 入力: ads テーブルの全データ
# 出力: product_rankings テーブル + ad_metadata

# 5シグナル:
# 1. 配信継続力 (days_running → longevity score)
# 2. 推定消化額 (CPM × impressions → spend score)
# 3. 配信中ボーナス (is_still_running → bonus)
# 4. クリエイティブ品質 (creative_quality → quality score)
# 5. トレンドスコア (velocity/acceleration → trend score)

# → hit_score = weighted sum of 5 signals
# → hit_level = "mega_hit" | "hit" | "normal" | "low"
# → is_hit = hit_score >= threshold
```

---

### Stage 5: API配信 (Agent C)

**GET /rankings/pro-ranking**:
```json
{
  "items": [
    {
      "rank": 1,
      "management_id": "N-001",
      "thumbnail_url": "/api/v1/media/thumbnail/123",
      "product_name": "美容液ABC",
      "advertiser_name": "株式会社XYZ",
      "genre": "美容",
      "platform": "facebook",
      "view_increase": 10997,
      "total_views": 58432,
      "spend_increase": 43988,
      "total_spend": 215000,
      "like_increase": 234,
      "days_running": 45,
      "hit_score": 78.5,
      "hit_level": "hit",
      "is_still_running": true,
      "duration_seconds": 29,
      "destination_url": "https://example.com/lp",
      "creative_type": "video"
    }
  ],
  "total": 58,
  "page": 1,
  "per_page": 20
}
```

---

### Stage 6: フロント表示 (Agent B)

**ProRankingTable.tsx**:
```
API response → state → map() → <tr> per item
  → rank: 順位番号
  → thumbnail: <img src={proxy_url} onError={fallback}>
  → product_name: テキスト（クリックで詳細モーダル）
  → genre: カラーバッジ
  → metrics: カンマ区切り数値 + 増分表示
  → hit badge: スコアに応じた色分け
```

---

## データが欠けている場合の影響マップ

| 欠けているデータ | 影響を受けるUI | 見え方 |
|-----------------|---------------|--------|
| video_url | CreativeViewer | 静止画のみ or プレースホルダー |
| image_url | テーブルサムネイル | グレーのプレースホルダー |
| thumbnail_url | カード/ギャラリー | 壊れた画像アイコン |
| category | ジャンルサイドバー | 「未分類」に集中 |
| destination_url | LPボタン | ボタン非表示 |
| hit_score | ランキング順位 | 全部0点 or ランダム順 |
| days_running | 配信日数カラム | 0日 or 空欄 |
| is_still_running | ステータスバッジ | 全部「不明」 |
| delivery_start_time | カレンダービュー | 空のカレンダー |

---

## ボトルネック特定

```
Stage 1 (クロール)      → Meta APIトークン無効 ❌
Stage 2 (データ品質)    → スクリプトは存在、実行するだけ ⚠️
Stage 3 (メディア)      → Playwright実装済、本番未テスト ⚠️
Stage 4 (スコアリング)  → コード存在、データ不足で精度不明 ⚠️
Stage 5 (API)           → 105+エンドポイント実装済 ✅
Stage 6 (フロント)      → 22ビュー実装済 ✅

→ ボトルネックは Stage 1-3 (データ入力側)
→ Stage 5-6 (出力側) は待ち状態
```
