# DB スキーマ視点 — テーブル設計の問題と最適化

## 現在のテーブル構成 (16モデル)

```
ads                    ← コア。全広告データ
ad_metrics             ← 日次メトリクス (未活用の可能性)
product_rankings       ← ヒットスコア・ランキング
ad_analysis            ← テキスト検出・書き起こし分析
users                  ← ユーザーアカウント
api_keys               ← APIキー管理
landing_pages          ← LP データ
crawl_jobs             ← クロールジョブ追跡
campaigns              ← キャンペーン管理
meta_ad_accounts       ← Meta アカウント同期
meta_campaigns         ← Meta キャンペーン
ab_tests               ← A/B テスト
optimizations          ← 最適化記録
predictions            ← パフォーマンス予測
creatives              ← クリエイティブアセット
competitive_intel      ← 競合情報
```

---

## ads テーブル — 最重要テーブルの分析

### カラム構成（推定）
```sql
ads (
  id                    SERIAL PRIMARY KEY,
  ad_id                 VARCHAR       -- Meta Ad Library ID
  title                 TEXT          -- 広告タイトル
  description           TEXT          -- 広告テキスト
  advertiser_name       VARCHAR       -- 広告主名
  platform              VARCHAR       -- facebook/instagram/youtube/tiktok
  status                VARCHAR       -- active/inactive/unknown
  category              VARCHAR       -- ジャンル（美容/健康食品/...）

  -- メディア
  snapshot_url          TEXT          -- Meta Ad Library スナップショット
  image_url             TEXT          -- 直接画像URL
  video_url             TEXT          -- 直接動画URL
  thumbnail_url         TEXT          -- サムネイルURL
  thumbnail_s3_key      VARCHAR       -- S3キャッシュ
  image_s3_key          VARCHAR       -- S3画像キャッシュ
  image_s3_keys         JSONB         -- カルーセル画像
  creative_type         VARCHAR       -- video/image/carousel

  -- メディアメタデータ
  duration_seconds      INTEGER       -- 動画長
  resolution_width      INTEGER       -- 解像度幅
  resolution_height     INTEGER       -- 解像度高
  file_size_bytes       BIGINT        -- ファイルサイズ
  media_extraction_status VARCHAR     -- pending/completed/failed

  -- 遷移先
  destination_url       TEXT          -- LP URL

  -- JSONB メタデータ（全エージェントが書き込む巨大フィールド）
  ad_metadata           JSONB         -- ★ 問題の温床

  -- タイムスタンプ
  created_at            TIMESTAMP
  updated_at            TIMESTAMP
)
```

---

## 問題 1: ad_metadata が肥大化

### 現状
ad_metadata に25+のキーが格納されている:

```json
{
  // Agent A のキー (8個)
  "estimated_audience_min": 10000,
  "estimated_audience_max": 50000,
  "publisher_platforms": ["facebook", "instagram"],
  "delivery_start_time": "2025-12-01",
  "delivery_stop_time": null,
  "is_still_running": true,
  "estimation_method": "audience_range",
  "impressions_from_audience": 30000,
  "last_checked_at": "2026-02-28T10:00:00",
  "snapshot_check": "ok",
  "longevity_class": "long_runner",
  "survival_checked_at": "2026-02-28",

  // Agent C のキー (7個)
  "latest_hit_score": 72.5,
  "latest_score_breakdown": {"longevity": 30, "spend": 20, ...},
  "hit_level": "hit",
  "is_hit": true,
  "lp_status": "alive",
  "lp_checked_at": "2026-02-28",
  "data_completeness": 0.85,
  "score_updated_at": "2026-02-28",

  // Agent D のキー (5個)
  "creative_quality": "high",
  "thumbnail_fixed": true,
  "media_urls_backfilled": true,
  "extraction_method": "playwright",
  "media_extraction_status": "completed",
  "media_completeness_score": 0.9
}
```

### リスク
1. **JSONB は型安全でない** — キー名のtypoでサイレント失敗
2. **インデックスが効きにくい** — `WHERE ad_metadata->>'is_hit' = 'true'` は遅い
3. **マイグレーション困難** — カラム追加と違い、JSONBの変更は追跡できない
4. **エージェント間の上書きリスク** — flag_modified パターンを忘れると消える

### 対策案（将来）
頻繁にクエリされるキーは専用カラムに昇格:
```sql
ALTER TABLE ads ADD COLUMN hit_score FLOAT;
ALTER TABLE ads ADD COLUMN hit_level VARCHAR(20);
ALTER TABLE ads ADD COLUMN is_hit BOOLEAN DEFAULT FALSE;
ALTER TABLE ads ADD COLUMN is_still_running BOOLEAN;
ALTER TABLE ads ADD COLUMN days_running INTEGER;
ALTER TABLE ads ADD COLUMN delivery_start_date DATE;
```

---

## 問題 2: product_rankings テーブルの位置づけ

### 現状
- `ad_metrics.py` 内で定義されている
- ads テーブルと 1:1 の関係（1広告 = 1ランキングレコード）
- hit_score, trend_score, rank, is_hit を保持

### 問題
- product_rankings と ads.ad_metadata.latest_hit_score が**二重管理**
- どちらが正？ → Agent C が両方更新するが、不整合の可能性

### 対策
- product_rankings をマスターにする
- ad_metadata.latest_hit_score は product_rankings からの読取専用キャッシュ

---

## 問題 3: ad_metrics テーブルの未活用

### 設計意図
日次で広告のメトリクス（再生数、いいね数等）を記録し、時系列分析に使う。

### 現状
- テーブルは存在するがデータが入っていない（推定）
- PRO DATABASE の「再生増加数」「消化額増加」はこのテーブルが必要
- Agent A の A17_metrics_delta_tracking がこの問題を解決するタスク

### データフロー（理想）
```
Day 1: crawl → ad_metrics (views=1000, spend=50000)
Day 2: crawl → ad_metrics (views=1200, spend=55000)
  → view_increase = 200, spend_increase = 5000
Day 3: crawl → ad_metrics (views=1500, spend=62000)
  → view_increase = 300, spend_increase = 7000
```

### 現状の代替
- 増分データがないため、推定値を使っている
- `/pro-ranking` の view_increase, spend_increase は推定ロジック

---

## 問題 4: 検索インデックスの不足

### 必要なクエリパターンと対応インデックス

```sql
-- PRO DATABASE: ジャンル別ランキング
-- 必要: category + hit_score の複合インデックス
WHERE category = '美容' ORDER BY hit_score DESC LIMIT 20

-- 検索: キーワード
-- 必要: title, advertiser_name の全文検索インデックス
WHERE title ILIKE '%美容%' OR advertiser_name ILIKE '%美容%'

-- フィルター: プラットフォーム + 配信中
-- 必要: platform, status の複合インデックス
WHERE platform = 'facebook' AND status = 'active'

-- トレンド: 最新広告
-- 必要: created_at の降順インデックス
ORDER BY created_at DESC LIMIT 20

-- スコア分布: 集計
-- 必要: hit_score のインデックス
SELECT COUNT(*), FLOOR(hit_score/10)*10 as bucket FROM ...
```

### 推奨インデックス作成SQL
```sql
-- Phase 1: 即座に（58件でも効果あり）
CREATE INDEX IF NOT EXISTS idx_ads_category ON ads(category);
CREATE INDEX IF NOT EXISTS idx_ads_created_at ON ads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pr_ad_id ON product_rankings(ad_id);
CREATE INDEX IF NOT EXISTS idx_pr_hit_score ON product_rankings(hit_score DESC);

-- Phase 2: 500件到達時
CREATE INDEX IF NOT EXISTS idx_ads_platform ON ads(platform);
CREATE INDEX IF NOT EXISTS idx_ads_status ON ads(status);
CREATE INDEX IF NOT EXISTS idx_ads_advertiser ON ads(advertiser_name);
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_ads_title_trgm ON ads USING gin(title gin_trgm_ops);

-- Phase 3: 2000件到達時
CREATE INDEX IF NOT EXISTS idx_ads_compound ON ads(category, platform, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ads_metadata_hit ON ads USING btree(((ad_metadata->>'latest_hit_score')::float));
CREATE INDEX IF NOT EXISTS idx_ads_metadata_running ON ads USING btree(((ad_metadata->>'is_still_running')::boolean));
```

---

## 問題 5: マイグレーション管理

### 確認すべきこと
```bash
cd C:/Users/ishit/ads_library/backend

# 現在のマイグレーション状態
alembic current

# 未適用のマイグレーション
alembic history

# モデルとDBの差分
alembic check
```

### リスク
- エージェントがモデルにフィールド追加 → alembic migration 未作成 → 本番DBに反映されない
- 各エージェントが独立にマイグレーション作成 → コンフリクト

### 対策
- マイグレーション作成は Planner 1 (Agent A) が一括管理
- 他エージェントはモデル定義変更のみ、マイグレーションは依頼
