#!/usr/bin/env python3
"""CI-088: DLQ replay tool for failed media pipeline items.

Re-queues ads with failed media extraction status for retry.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/replay_failed_media.py [--limit N] [--dry-run]
"""

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_session():
    """Get DB session with SQLite fallback."""
    try:
        from app.core.database import SyncSessionLocal
        session = SyncSessionLocal()
        session.execute(__import__("sqlalchemy").text("SELECT 1"))
        return session
    except Exception:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        db_path = os.path.join(BASE_DIR, "vaap_local.db")
        engine = create_engine(f"sqlite:///{db_path}")
        Session = sessionmaker(bind=engine)
        return Session()


def replay_failed(limit: int = 50, dry_run: bool = False):
    from app.models.ad import Ad, MediaExtractionStatus
    from sqlalchemy.orm.attributes import flag_modified

    session = _get_session()

    failed_ads = (
        session.query(Ad)
        .filter(Ad.media_extraction_status == MediaExtractionStatus.FAILED)
        .order_by(Ad.updated_at.desc())
        .limit(limit)
        .all()
    )

    print(f"Found {len(failed_ads)} failed media extractions")

    if dry_run:
        for ad in failed_ads:
            meta = ad.ad_metadata or {}
            print(f"  Ad {ad.id}: {ad.title or 'no title'} - retry_count={meta.get('media_retry_count', 0)}")
        print("(dry-run mode, no changes made)")
        return

    replayed = 0
    for ad in failed_ads:
        meta = dict(ad.ad_metadata or {})
        retry_count = meta.get("media_retry_count", 0)

        # Skip if already retried 3+ times
        if retry_count >= 3:
            print(f"  Skip ad {ad.id}: max retries reached ({retry_count})")
            continue

        # Reset status to pending for re-extraction
        ad.media_extraction_status = MediaExtractionStatus.PENDING
        meta["media_retry_count"] = retry_count + 1
        meta["dlq_replayed_at"] = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")
        replayed += 1

    try:
        session.commit()
    except Exception:
        session.rollback()
    session.close()

    print(f"Replayed {replayed}/{len(failed_ads)} ads (reset to PENDING)")


if __name__ == "__main__":
    limit_val = 50
    dry_run_mode = "--dry-run" in sys.argv
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit_val = int(sys.argv[idx + 1])
    replay_failed(limit=limit_val, dry_run=dry_run_mode)
