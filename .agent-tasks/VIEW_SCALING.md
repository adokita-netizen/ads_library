# スケーリング視点 — 58件→1000件→10000件で何が壊れるか

## 現在: 58件

全てが問題なく動く（はず）。メモリ内で全件処理しても大丈夫。

---

## 目標1: 500件（1ヶ月後）

### 壊れる可能性があるもの

**rankings.py の全件ロード**
- `/pro-ranking` が全件DBからロード → Python でフィルタ → ページング
- 500件なら数秒で返る
- **対策不要**: まだ大丈夫

**サムネイル取得**
- 500件 × サムネイル修復 = 500回の外部HTTP
- `fix_bad_thumbnails.py` の実行時間: ~30分
- **対策不要**: バッチ処理として許容範囲

**ヒットスコア再計算**
- `recompute_hit_scores.py` が500件を処理
- 各広告で5シグナル計算: ~1秒/件 → 約8分
- **対策不要**: バッチ処理として許容範囲

---

## 目標2: 2000件（3ヶ月後）

### 壊れ始めるもの

**rankings.py の全件ロード** ⚠️
- 2000件を全件ロードしてPythonフィルタ: 2-5秒
- ユーザーがフィルタ変えるたびに2-5秒待つ → UX悪い
- **対策**: SQLレベルでフィルタリング + LIMIT/OFFSET

**Lambda メモリ** ⚠️
- 2000件のJSON レスポンス → 数MBのメモリ使用
- Lambda のメモリ制限に近づく可能性
- **対策**: ストリーミングレスポンス or ページングの厳守

**genre-master の件数計算** ⚠️
- ジャンル別の件数をCOUNT(*) で計算 → 全テーブルスキャン
- **対策**: category にINDEX追加
```sql
CREATE INDEX idx_ads_category ON ads(category);
```

**検索** ⚠️
- LIKE検索: `WHERE title LIKE '%美容%'` → 全件スキャン
- **対策**: PostgreSQL の全文検索 or pg_trgm 拡張
```sql
CREATE INDEX idx_ads_title_trgm ON ads USING gin(title gin_trgm_ops);
```

---

## 目標3: 10000件（6ヶ月後）

### 確実に壊れるもの

**rankings.py** ❌
- 10000件の全件ロードは不可能
- **必須対策**: SQL クエリの全面書き直し
- product_rankings テーブルに事前計算結果を保存
- ページングはOFFSET/LIMITをSQLで

**dashboard-summary** ❌
- 10000件の集計を毎リクエストで計算 → タイムアウト
- **必須対策**: 事前計算テーブル or マテリアライズドビュー
```sql
CREATE MATERIALIZED VIEW dashboard_stats AS
SELECT
  COUNT(*) as total_ads,
  COUNT(*) FILTER (WHERE is_still_running) as active_ads,
  AVG(hit_score) as avg_score,
  ...
FROM ads JOIN product_rankings ON ...;

-- 1時間毎にリフレッシュ
REFRESH MATERIALIZED VIEW dashboard_stats;
```

**クロール** ❌
- 10000件のクロールには数日かかる
- Meta API のレートリミット: ~200 req/hour
- **必須対策**: 差分クロール（新規・更新分のみ）

**メディア抽出** ❌
- 10000件の Playwright 抽出 → 数日
- **必須対策**: 並列ECSタスク（複数Fargate同時実行）

**ストレージ** ⚠️
- 動画: 10000件 × 平均30MB = 300GB
- S3ストレージコスト: ~$7/月（許容範囲）
- **対策**: ライフサイクルルールで古い動画をGlacierに移行

**RDS** ⚠️
- db.t3.micro のメモリ(1GB) が不足する可能性
- **対策**: db.t3.small (2GB) にスケールアップ

---

## インデックス戦略（今から準備）

```sql
-- 必須（500件到達前に）
CREATE INDEX idx_ads_category ON ads(category);
CREATE INDEX idx_ads_platform ON ads(platform);
CREATE INDEX idx_ads_created_at ON ads(created_at DESC);
CREATE INDEX idx_product_rankings_hit_score ON product_rankings(hit_score DESC);
CREATE INDEX idx_product_rankings_ad_id ON product_rankings(ad_id);

-- 推奨（2000件到達前に）
CREATE INDEX idx_ads_advertiser ON ads(advertiser_name);
CREATE INDEX idx_ads_title_trgm ON ads USING gin(title gin_trgm_ops);
CREATE INDEX idx_ads_metadata ON ads USING gin(ad_metadata);

-- 将来（10000件到達前に）
CREATE INDEX idx_ads_destination ON ads(destination_url);
CREATE INDEX idx_ads_status ON ads(status);
CREATE INDEX idx_ads_compound ON ads(category, platform, created_at DESC);
```

---

## アーキテクチャ変更が必要なポイント

### 500件まで: 変更不要
現在のアーキテクチャで対応可能。

### 2000件: SQLチューニング
- rankings.py のクエリをSQL寄せ
- インデックス追加
- キャッシュ導入（Redis or CloudFront）

### 10000件: アーキテクチャ変更
```
現在:
  Lambda (API) → RDS (全件クエリ)

変更後:
  Lambda (API) → ElastiCache (Redis) → RDS
                      ↑
  バッチ処理が定期的にキャッシュ更新

または:
  Lambda (API) → RDS (マテリアライズドビュー)
                      ↑
  pg_cron で定期リフレッシュ
```

### 50000件以上: ElasticSearch 検討
- 全文検索、ファセット検索、集計
- PostgreSQL では限界

---

## コスト予測

| 広告数 | RDS | Lambda | S3 | ECS | 合計/月 |
|--------|-----|--------|----|----|---------|
| 58 | $15 | $1 | $1 | $2 | **$19** |
| 500 | $15 | $3 | $2 | $10 | **$30** |
| 2000 | $30 | $10 | $5 | $30 | **$75** |
| 10000 | $60 | $30 | $20 | $80 | **$190** |
| 50000 | $120 | $80 | $100 | $200 | **$500** |
