# D-R2-2: Video Processing Pipeline (D8)
# 優先度: P0 | 前提: なし | ブロック: D-R2-6

## 目的
動画ダウンロード→メタデータ抽出→S3アップロードのパイプラインを完成させる。

## 対象ファイル (全て Agent D 専有)
- `backend/app/tasks/media_tasks.py` (修正)
- `backend/app/services/media_extraction.py` (修正)

## 現状確認
- D26 で video DL + S3 upload は実装済み (100MB limit, 60s timeout)
- ad.py に video_s3_key カラム追加済み
- 不足: duration_seconds, resolution, file_size の自動取得

## 実装

### Step 1: 動画メタデータ抽出
```python
# media_tasks.py に追加

import subprocess
import json

def extract_video_metadata(video_path: str) -> dict:
    """ffprobe で動画メタデータを取得"""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return {}

        data = json.loads(result.stdout)
        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
            {}
        )

        return {
            "duration_seconds": float(data.get("format", {}).get("duration", 0)),
            "resolution_width": int(video_stream.get("width", 0)),
            "resolution_height": int(video_stream.get("height", 0)),
            "codec": video_stream.get("codec_name", ""),
            "file_size_bytes": int(data.get("format", {}).get("size", 0)),
            "bitrate": int(data.get("format", {}).get("bit_rate", 0)),
            "fps": eval(video_stream.get("r_frame_rate", "0/1")) if video_stream.get("r_frame_rate") else 0,
        }
    except Exception as e:
        logger.warning(f"ffprobe failed: {e}")
        return {}
```

### Step 2: Playwright ベースのフォールバック
```python
def extract_video_metadata_playwright(page, video_element) -> dict:
    """ffprobe が使えない場合、Playwright で動画メタデータを取得"""
    try:
        meta = page.evaluate("""(el) => ({
            duration: el.duration,
            width: el.videoWidth,
            height: el.videoHeight,
        })""", video_element)

        return {
            "duration_seconds": meta.get("duration", 0),
            "resolution_width": meta.get("width", 0),
            "resolution_height": meta.get("height", 0),
        }
    except:
        return {}
```

### Step 3: media_tasks.py の extract_media_task に統合
```python
# extract_media_task() の動画ダウンロード後に追加:

if video_path and os.path.exists(video_path):
    # メタデータ抽出
    video_meta = extract_video_metadata(video_path)

    if video_meta:
        ad.duration_seconds = video_meta.get("duration_seconds")
        ad.resolution_width = video_meta.get("resolution_width")
        ad.resolution_height = video_meta.get("resolution_height")
        ad.file_size_bytes = video_meta.get("file_size_bytes")

        # ad_metadata にも詳細を保存
        meta = dict(ad.ad_metadata or {})
        meta["video_codec"] = video_meta.get("codec")
        meta["video_bitrate"] = video_meta.get("bitrate")
        meta["video_fps"] = video_meta.get("fps")
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")

    # S3 アップロード (D26 で実装済み)
    s3_key = upload_to_s3(video_path, ad.id)
    ad.video_s3_key = s3_key

    session.commit()
```

### Step 4: 既存動画のメタデータバックフィル
```python
# 既存の video_url があるが duration_seconds が NULL の広告に対して
# HTTP で動画をダウンロード → メタデータ抽出 → DB更新

# backend/scripts/backfill_video_metadata.py (Agent D 専有)
def backfill():
    session = SyncSessionLocal()
    ads = session.query(Ad).filter(
        Ad.video_url != None,
        Ad.duration_seconds == None
    ).all()

    print(f"Found {len(ads)} videos without metadata")

    for ad in ads:
        # 動画をダウンロード (一時ファイル)
        # メタデータ抽出
        # DB更新
        ...

    session.commit()
    session.close()
```

### Step 5: Dockerfile.worker に ffprobe 追加
```dockerfile
# docker/Dockerfile.worker に追加
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
```

## 完了条件
- [ ] extract_video_metadata() が動画からメタデータを正しく抽出する
- [ ] duration_seconds, resolution_width/height, file_size_bytes が Ad レコードに保存される
- [ ] Playwright フォールバックが動作する
- [ ] 既存動画のメタデータバックフィルが完了
- [ ] Dockerfile.worker に ffprobe がインストールされている
- [ ] status.md に記録
