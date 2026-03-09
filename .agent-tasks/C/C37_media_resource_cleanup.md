# C37: メディアAPI リソースリーク修正

## 問題
- ファイルストリーミング時のハンドルリーク（close 漏れ）
- ZIP生成時の一時ファイルが削除されないケース
- パストラバーサル攻撃の防御不足（`../` を含むファイル名）

## 対象ファイル
- `backend/app/api/endpoints/media.py`

## 修正

### 1. ファイルハンドルの確実な close
```python
# Before
f = open(filepath, "rb")
return StreamingResponse(f, media_type="video/mp4")

# After — generator でラップして確実に close
async def file_stream(path: str):
    f = open(path, "rb")
    try:
        while chunk := f.read(8192):
            yield chunk
    finally:
        f.close()

return StreamingResponse(file_stream(filepath), media_type="video/mp4")
```

### 2. ZIP 一時ファイルの cleanup
```python
import tempfile
import os

@router.get("/media/download-zip")
async def download_zip(ad_ids: list[str]):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    try:
        _create_zip(tmp.name, ad_ids)
        return FileResponse(
            tmp.name,
            media_type="application/zip",
            background=BackgroundTask(os.unlink, tmp.name)
        )
    except Exception:
        os.unlink(tmp.name)
        raise
```

### 3. パストラバーサル防御
```python
import os

def _safe_filename(filename: str) -> str:
    """ディレクトリトラバーサルを防止"""
    # パス区切り文字と親ディレクトリ参照を除去
    basename = os.path.basename(filename)
    if not basename or basename.startswith("."):
        raise HTTPException(400, "Invalid filename")
    return basename

# 使用箇所
safe_name = _safe_filename(requested_file)
full_path = os.path.join(MEDIA_DIR, safe_name)
if not os.path.abspath(full_path).startswith(os.path.abspath(MEDIA_DIR)):
    raise HTTPException(403, "Access denied")
```

## 制約
- `media.py` のみ修正
- 既存のエンドポイントインターフェースは維持
