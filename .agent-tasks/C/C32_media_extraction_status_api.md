# C32: メディア抽出ステータス & バッチAPI

## 目的
メディア抽出パイプラインの進捗を確認し、バッチ操作をトリガーできるAPIエンドポイント群。
B34 (フロントエンドダッシュボード) のバックエンド。

## 対象ファイル
- `backend/app/api/endpoints/rankings.py` (末尾に追加)

## タスク

### 1. GET /rankings/media-extraction-status
メディア抽出の全体サマリーを返す。

```python
@router.get("/media-extraction-status")
async def get_media_extraction_status(db: AsyncSession = Depends(get_db)):
    """Media extraction pipeline status summary."""
    from sqlalchemy import text, func

    # ステータス別カウント
    rows = db.execute(text("""
        SELECT media_extraction_status, count(*)
        FROM ads
        GROUP BY media_extraction_status
    """)).fetchall()

    status_counts = {r[0] or "null": r[1] for r in rows}
    total = sum(status_counts.values())
    completed = status_counts.get("completed", 0) + status_counts.get("enriched", 0)

    return {
        "total_ads": total,
        "completed": completed,
        "pending": status_counts.get("pending", 0),
        "pending_heavy": status_counts.get("pending_heavy", 0),
        "dispatched": status_counts.get("dispatched", 0),
        "failed": status_counts.get("failed", 0),
        "skipped": status_counts.get("skipped", 0),
        "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
        "status_breakdown": status_counts,
    }
```

### 2. GET /rankings/media-extraction-ads
ステータス別の広告一覧（ページネーション付き）。

```python
@router.get("/media-extraction-ads")
async def get_media_extraction_ads(
    status: str = "pending",
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List ads by media extraction status."""
    offset = (page - 1) * per_page

    rows = db.execute(text("""
        SELECT id, title, advertiser_name, creative_type,
               media_extraction_status, snapshot_url, image_url, video_url,
               image_s3_key, thumbnail_s3_key
        FROM ads
        WHERE media_extraction_status = :status
        ORDER BY id
        LIMIT :limit OFFSET :offset
    """), {"status": status, "limit": per_page, "offset": offset}).fetchall()

    total = db.execute(text("""
        SELECT count(*) FROM ads WHERE media_extraction_status = :status
    """), {"status": status}).scalar()

    return {
        "ads": [
            {
                "id": r[0], "title": r[1], "advertiser_name": r[2],
                "creative_type": r[3], "status": r[4],
                "has_snapshot": bool(r[5]), "has_image": bool(r[6]),
                "has_video": bool(r[7]), "has_s3_image": bool(r[8]),
                "has_s3_thumbnail": bool(r[9]),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
```

### 3. POST /rankings/batch-extract-media
バッチメディア抽出をトリガー。

```python
@router.post("/batch-extract-media")
async def batch_extract_media(
    limit: int = 50,
    statuses: list[str] = ["pending", "pending_heavy"],
    db: AsyncSession = Depends(get_db),
):
    """Dispatch batch media extraction tasks to SQS → ECS."""
    from app.tasks.dispatcher import dispatch_task

    rows = db.execute(text("""
        SELECT id FROM ads
        WHERE media_extraction_status = ANY(:statuses)
        AND (snapshot_url IS NOT NULL OR external_id IS NOT NULL)
        ORDER BY id
        LIMIT :limit
    """), {"statuses": statuses, "limit": limit}).fetchall()

    dispatched = []
    errors = []
    for row in rows:
        try:
            result = dispatch_task("extract_media", ad_id=row[0])
            dispatched.append({"ad_id": row[0], "message_id": result.id})
        except Exception as e:
            errors.append({"ad_id": row[0], "error": str(e)})

    return {
        "dispatched": len(dispatched),
        "errors": len(errors),
        "details": dispatched[:20],
    }
```

### 4. POST /rankings/retry-failed-media
失敗した抽出をリトライ。

```python
@router.post("/retry-failed-media")
async def retry_failed_media(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Reset failed extractions to pending and re-dispatch."""
    # Reset status
    db.execute(text("""
        UPDATE ads SET media_extraction_status = 'pending'
        WHERE media_extraction_status = 'failed'
        LIMIT :limit
    """), {"limit": limit})
    db.commit()

    # Re-dispatch
    return await batch_extract_media(limit=limit, statuses=["pending"], db=db)
```

## 制約
- `rankings.py` 末尾に追加のみ
- 既存エンドポイントを修正しない
- dispatch_task を使用（直接 SQS/ECS を叩かない）
