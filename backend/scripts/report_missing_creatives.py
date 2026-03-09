"""Report remaining ads that still lack downloadable creative assets."""

from __future__ import annotations

from collections import Counter

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


def main() -> None:
    session = SyncSessionLocal()
    try:
        rows = (
            session.query(Ad)
            .filter(
                (Ad.image_s3_key.is_(None) | (Ad.image_s3_key == "")),
                (Ad.thumbnail_s3_key.is_(None) | (Ad.thumbnail_s3_key == "")),
                (Ad.video_s3_key.is_(None) | (Ad.video_s3_key == "")),
                (Ad.s3_key.is_(None) | (Ad.s3_key == "")),
            )
            .order_by(Ad.id.desc())
            .all()
        )
        print("missing_creative_total", len(rows))
        status_counts = Counter(str(row.media_extraction_status or "") for row in rows)
        print("status_breakdown", dict(status_counts))
        for row in rows[:50]:
            print(
                {
                    "id": int(row.id),
                    "creative_type": str(row.creative_type or ""),
                    "media_extraction_status": str(row.media_extraction_status or ""),
                    "snapshot_url": str(row.snapshot_url or "")[:120],
                    "image_url": str(row.image_url or "")[:80],
                    "thumbnail_url": str(row.thumbnail_url or "")[:80],
                    "external_id": str(row.external_id or ""),
                }
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()
