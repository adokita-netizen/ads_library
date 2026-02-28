# Agent C タスク: サムネイルURL解決の修正

## 背景（最重要）
`_resolve_thumbnail_url()` (rankings.py内) は現在、S3キーがNULLのため
毎回期限切れのFacebook CDN URLを返している。
Agent Dが `/api/v1/media/thumbnail/{ad_id}` エンドポイントを作成するので、
そちらを優先的に返すように修正する。

## やること

### 1. _resolve_thumbnail_url() の修正
現在の実装（S3 presigned → CDN URLフォールバック）を修正：

```python
def _resolve_thumbnail_url(ad: Ad) -> str:
    # Priority 1: Local cache proxy (Agent D が作成するエンドポイント)
    # thumbnail_s3_key に "media_cache/" が入っていればプロキシURLを返す
    if ad.thumbnail_s3_key and "media_cache/" in ad.thumbnail_s3_key:
        return f"/api/v1/media/thumbnail/{ad.id}"

    # Priority 2: S3 presigned URL (MinIO/AWS が使える場合)
    if ad.thumbnail_s3_key:
        try:
            storage = get_storage_client()
            return storage.get_presigned_url(ad.thumbnail_s3_key)
        except Exception:
            pass

    # Priority 3: Original URL (may be expired)
    if ad.thumbnail_url:
        return ad.thumbnail_url
    if ad.image_url:
        return ad.image_url
    return ad.snapshot_url or ""
```

### 2. hit-ads レスポンスの image_url も同様に修正
image_url フィールドも、image_s3_key に "media_cache/" が入っていれば
`/api/v1/media/image/{ad_id}` を返すようにする。

`_resolve_image_url(ad)` ヘルパーを追加：
```python
def _resolve_image_url(ad: Ad) -> str:
    if ad.image_s3_key and "media_cache/" in ad.image_s3_key:
        return f"/api/v1/media/image/{ad.id}"
    return ad.image_url or ad.thumbnail_url or ""
```

hit-adsレスポンス内の `"image_url": ad.image_url` を `"image_url": _resolve_image_url(ad)` に変更。

### 3. API レスポンスの高速化
hit-ads の N+1 クエリを確認。176件のSELECTが遅い場合：
- eager loadingの追加
- 不要なJOINの削除
- レスポンスサイズの最適化

## 制約
- INSTRUCTIONS.md のコンフリクト防止ルール厳守
- 修正ファイル: `backend/app/api/endpoints/rankings.py` のみ
- import確認: `python -c "from app.api.endpoints.rankings import router"`
