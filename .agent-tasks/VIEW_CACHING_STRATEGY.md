# キャッシュ戦略視点 — レスポンス高速化とコスト削減

## なぜキャッシュが必要か

- PRO DATABASE テーブル: 毎回全件JOINクエリ → 重い
- ダッシュボード集計: 毎回SQLで再計算 → 無駄
- サムネイル配信: S3 → CloudFront で既にCDNキャッシュあり
- Meta API: レートリミット 200 calls/hour → キャッシュで節約

---

## キャッシュ層の設計

### 層別キャッシュ戦略

```
[ブラウザ] → [CloudFront] → [API Gateway] → [Lambda/FastAPI] → [DB]
   L1           L2              L3              L4              L5

L1: ブラウザキャッシュ (Cache-Control ヘッダー)
L2: CDN キャッシュ (CloudFront TTL)
L3: API Gateway キャッシュ (有料、使わない)
L4: アプリケーションキャッシュ (インメモリ / Redis)
L5: DB クエリキャッシュ (PostgreSQL)
```

### L1: ブラウザキャッシュ

```python
# 静的アセット → 長期キャッシュ
# Next.js の静的エクスポートでハッシュ付きファイル名
# Cache-Control: public, max-age=31536000, immutable

# API レスポンス → 短期キャッシュ
@router.get("/rankings/pro-ranking")
async def pro_ranking():
    response = JSONResponse(content=data)
    response.headers["Cache-Control"] = "public, max-age=300"  # 5分
    response.headers["ETag"] = compute_etag(data)
    return response
```

### L2: CloudFront キャッシュ

```
現状の設定確認:
  フロントエンド: S3 → CloudFront → ブラウザ（静的ファイル）
  API: CloudFront → API Gateway → Lambda

推奨設定:
  /api/v1/rankings/pro-ranking  → TTL 300秒（5分）
  /api/v1/rankings/dashboard-*  → TTL 600秒（10分）
  /api/v1/ads/*/thumbnail       → TTL 86400秒（24時間）
  /api/v1/rankings/quick-crawl  → TTL 0（キャッシュしない）
  /api/v1/media/*               → TTL 3600秒（1時間）
```

### L4: アプリケーションキャッシュ

#### Lambda の場合の制約
```
Lambda はリクエスト間でメモリを共有しない（コールドスタート時）
→ グローバル変数キャッシュは同一インスタンスでのみ有効
→ ウォームスタート時は前回の値が残る

対策:
1. 単純な辞書キャッシュ + TTL（Lambda内インメモリ）
2. ElastiCache Redis（別途コスト）
3. DynamoDB TTL（サーバーレスでスケール）
```

#### インメモリキャッシュ（Lambda用、最小コスト）
```python
# app/core/cache.py
import time
from functools import wraps

_cache = {}

def cached(ttl_seconds: int = 300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{kwargs}"
            now = time.time()
            if key in _cache:
                value, expires = _cache[key]
                if now < expires:
                    return value
            result = await func(*args, **kwargs)
            _cache[key] = (result, now + ttl_seconds)
            return result
        return wrapper
    return decorator

# 使用例
@cached(ttl_seconds=300)
async def get_dashboard_summary(db):
    # 重い集計クエリ
    ...
```

---

## エンドポイント別キャッシュ設計

### 高頻度アクセス（毎回キャッシュ）

| エンドポイント | TTL | キャッシュキー | 無効化条件 |
|---------------|-----|--------------|-----------|
| /pro-ranking | 5分 | page+sort+filters | 新しいスコア計算後 |
| /dashboard-summary | 10分 | なし（1種類） | 新しいクロール後 |
| /categories | 1時間 | なし | カテゴリ更新後 |
| /genre-distribution | 10分 | なし | スコア計算後 |

### 低頻度アクセス（キャッシュ不要）

| エンドポイント | 理由 |
|---------------|------|
| /quick-crawl | 副作用あり（DB書き込み） |
| /export/* | 毎回最新データ必要 |
| /settings/* | 設定変更を即反映 |

### 重いがキャッシュ効果大

| エンドポイント | 現在の応答時間（推定） | キャッシュ後 |
|---------------|---------------------|------------|
| /pro-ranking (全件) | 2-5秒 | 50ms |
| /dashboard-summary | 3-10秒 | 50ms |
| /hit-analysis-data | 5-15秒 | 100ms |
| /genre-comparison | 2-5秒 | 50ms |

---

## キャッシュ無効化戦略

### イベント駆動無効化
```python
# データ変更時にキャッシュをクリア

def invalidate_ranking_cache():
    """ランキング関連のキャッシュを全クリア"""
    keys_to_delete = [k for k in _cache if "ranking" in k or "dashboard" in k]
    for k in keys_to_delete:
        del _cache[k]

# クロール完了時
async def on_crawl_complete():
    invalidate_ranking_cache()

# スコア再計算時
async def on_score_recalculated():
    invalidate_ranking_cache()
```

### 時間ベース無効化
```
- ランキングデータ: 5分 TTL
- 集計データ: 10分 TTL
- マスターデータ（カテゴリ等）: 1時間 TTL
- メディアURL: 24時間 TTL
```

---

## サムネイル/メディアのキャッシュ

### 現状
```
snapshot_url (Meta) → Playwright → 動画/画像URL抽出 → DB保存
                                                      ↓
サムネイルURL → フロントで <img src={url}> → 外部サーバーから直接取得
```

### 問題
- 外部URLは消える可能性がある
- 毎回外部サーバーにリクエスト → 遅い
- CORS問題

### 改善案
```
外部URL → Lambda/Worker がダウンロード → S3にアップロード → CloudFront経由で配信
                                         ↓
                              s3://vaap-media/{ad_id}/thumbnail.jpg
                              s3://vaap-media/{ad_id}/video.mp4
                                         ↓
                              https://cdn.vaap.jp/media/{ad_id}/thumbnail.jpg
```

### S3キャッシュのコスト見積もり
```
1000広告 × 平均1MB（サムネイル） = 1GB → S3: $0.023/月
1000広告 × 平均50MB（動画）     = 50GB → S3: $1.15/月
CloudFront 転送量: 100GB/月      → $8.50/月
合計: 約$10/月
```

---

## フロントエンドのキャッシュ

### React Query / SWR パターン
```typescript
// 現状: useEffect + fetch → 毎回取得

// 改善: SWR パターン
import useSWR from 'swr'

function ProRankingTable() {
  const { data, error, isLoading } = useSWR(
    '/api/v1/rankings/pro-ranking?page=1',
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      refreshInterval: 300000,  // 5分
      dedupingInterval: 60000,  // 1分以内の同一リクエストは重複排除
    }
  )
}
```

### Next.js 静的エクスポートの制約
```
現状: next export → 完全静的HTML
→ SSR/ISRは使えない
→ クライアントサイドフェッチのみ

対策:
- API レスポンスをブラウザの Cache API で保存
- IndexedDB に広告データをキャッシュ（オフライン対応）
- Service Worker でキャッシュ戦略制御
```

---

## 実装優先度

```
[Phase 1: 即効] コスト: 0円
1. CloudFront の Cache-Control ヘッダー設定
2. Lambda インメモリキャッシュ（辞書 + TTL）
3. フロントの SWR/React Query 導入

[Phase 2: 中期] コスト: ~$10/月
4. サムネイルの S3 キャッシュ
5. ETag ベースの条件付きリクエスト

[Phase 3: 長期] コスト: ~$50/月
6. ElastiCache Redis（データ量が増えた場合）
7. DynamoDB キャッシュテーブル
```

---

## キャッシュの監視

### メトリクス
```
cache_hit_rate  = cache_hits / (cache_hits + cache_misses)
目標: > 80%

cache_size_bytes  → メモリ使用量（Lambda は 512MB制限）
cache_evictions   → TTL切れの頻度
```

### CloudFront のキャッシュヒット率確認
```bash
# CloudWatch で確認
aws cloudwatch get-metric-statistics \
  --namespace AWS/CloudFront \
  --metric-name CacheHitRate \
  --dimensions Name=DistributionId,Value=ERPIU1B8ZZ5ZA \
  --start-time $(date -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average
```
