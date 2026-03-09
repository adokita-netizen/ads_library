#!/usr/bin/env python3
"""Batch Playwright image extraction for render_ad URLs.

Extracts images from Facebook render_ad pages using Playwright (JS rendering).
Updates image_url in DB for ads that have render_ad snapshot_url but no image.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/batch_playwright_extract.py [--limit N] [--offset N]
"""

import asyncio
import io
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_session():
    """Always use vaap_local.db directly to avoid fallback DB mismatch."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_path = os.path.join(BASE_DIR, "vaap_local.db")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Session = sessionmaker(bind=engine)
    return Session()


def main(limit: int = 0, offset: int = 0):
    from app.models.ad import Ad
    from app.services.media_extraction import MediaExtractor
    from sqlalchemy import text

    session = _get_session()

    query = text(
        "SELECT id, snapshot_url FROM ads "
        "WHERE snapshot_url LIKE '%render_ad%' AND image_url IS NULL "
        "ORDER BY id "
        "LIMIT :limit OFFSET :offset"
    )
    params = {"limit": limit if limit > 0 else 99999, "offset": offset}
    rows = session.execute(query, params).fetchall()
    total = len(rows)
    print(f"Playwright batch: {total} ads to process (offset={offset})")

    if total == 0:
        print("Nothing to do.")
        session.close()
        return

    extractor = MediaExtractor(timeout=20.0)
    success = 0
    failed = 0
    batch_size = 20

    for i, (ad_id, snapshot_url) in enumerate(rows):
        try:
            extracted = asyncio.run(
                extractor.extract(snapshot_url, use_playwright=True)
            )
            if extracted.image_urls:
                img_url = extracted.image_urls[0]
                session.execute(
                    text("UPDATE ads SET image_url = :img, updated_at = datetime('now') WHERE id = :id"),
                    {"img": img_url, "id": ad_id},
                )
                success += 1
                if (i + 1) % 50 == 0:
                    print(f"  [{i+1}/{total}] OK={success} FAIL={failed}")
            else:
                failed += 1

        except Exception as e:
            failed += 1
            err = str(e)[:60]
            if (i + 1) % 100 == 0:
                print(f"  [{i+1}/{total}] ERROR: {err}")

        # Batch commit
        if (i + 1) % batch_size == 0:
            try:
                session.commit()
            except Exception:
                session.rollback()

        # Rate limit
        time.sleep(0.5)

    # Final commit
    try:
        session.commit()
    except Exception:
        session.rollback()

    session.close()
    print(f"\n=== Batch Playwright Extraction Results ===")
    print(f"Total: {total}")
    print(f"Success: {success}")
    print(f"Failed: {failed}")
    print(f"Success rate: {success/total*100:.1f}%")


if __name__ == "__main__":
    limit_val = 0
    offset_val = 0
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit_val = int(sys.argv[idx + 1])
    if "--offset" in sys.argv:
        idx = sys.argv.index("--offset")
        if idx + 1 < len(sys.argv):
            offset_val = int(sys.argv[idx + 1])
    main(limit=limit_val, offset=offset_val)
