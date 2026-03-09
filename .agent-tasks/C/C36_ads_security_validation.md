# C36: 広告API セキュリティ・バリデーション強化

## 問題
- 動画アップロードエンドポイントにファイルサイズ・MIME検証がない
- `escape_like()` のSQLインジェクション対策が不十分（バックスラッシュ未エスケープ）
- `fetch_all_thumbnails` が同期的にブロック → Lambda タイムアウトリスク

## 対象ファイル
- `backend/app/api/endpoints/ads.py`

## 修正

### 1. アップロードバリデーション
```python
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_MIME_TYPES = {"video/mp4", "video/webm", "video/quicktime"}

@router.post("/ads/{ad_id}/video")
async def upload_video(ad_id: str, file: UploadFile):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported type: {file.content_type}")

    # サイズチェック（ストリーミング）
    size = 0
    chunks = []
    async for chunk in file:
        size += len(chunk)
        if size > MAX_VIDEO_SIZE:
            raise HTTPException(413, "File too large (max 100MB)")
        chunks.append(chunk)
```

### 2. escape_like の完全実装
```python
def escape_like(value: str) -> str:
    """LIKE演算子用エスケープ（バックスラッシュも処理）"""
    return (
        value
        .replace("\\", "\\\\")  # バックスラッシュ先
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
```

### 3. fetch_all_thumbnails の非同期化
```python
# 同期ループ → asyncio.gather で並行実行（同時5件制限）
import asyncio

async def fetch_all_thumbnails(ad_ids: list[str]):
    semaphore = asyncio.Semaphore(5)
    async def fetch_one(ad_id):
        async with semaphore:
            return await _fetch_thumbnail(ad_id)
    return await asyncio.gather(*[fetch_one(aid) for aid in ad_ids])
```

## 制約
- `ads.py` のみ修正
- 既存のエンドポイントパスは変更しない
