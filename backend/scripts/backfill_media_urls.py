"""Backfill missing image_url / video_url for ads.

Many ads have NULL image_url / video_url even though the data can be
recovered from other fields.  This script fills the gaps in three phases:

  Phase 1: thumbnail_url → image_url  (instant, no HTTP)
  Phase 2: snapshot_url  → MediaExtractor (HTTP + BS4, rate-limited)
  Phase 3: ad_metadata   → video_url / og_video extraction (no HTTP)

Batch-commits every BATCH_SIZE rows and prints before/after statistics.

Run from the backend directory:
    cd backend
    python scripts/backfill_media_urls.py
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, ".")

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal, is_in_memory_mode
from app.models.ad import Ad
from app.services.media_extraction import MediaExtractor


def _get_session() -> Session:
    """Get a DB session, connecting to vaap_local.db if SQLite fallback is active."""
    if not is_in_memory_mode():
        return SyncSessionLocal()
    db_path = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")
    if not os.path.exists(db_path):
        raise RuntimeError(f"vaap_local.db not found at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return sessionmaker(bind=engine)()

# ── Config ────────────────────────────────────────────────────────
BATCH_SIZE = 10
REQUEST_DELAY = 1.5  # seconds between HTTP requests in Phase 2


# ── Helpers ───────────────────────────────────────────────────────

def _count_nulls(session) -> dict:
    """Return NULL counts for image_url and video_url."""
    total = session.query(func.count(Ad.id)).scalar()
    img_null = session.query(func.count(Ad.id)).filter(Ad.image_url.is_(None)).scalar()
    vid_null = session.query(func.count(Ad.id)).filter(Ad.video_url.is_(None)).scalar()
    return {"total": total, "image_url_null": img_null, "video_url_null": vid_null}


def _print_stats(label: str, stats: dict):
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  Total ads:          {stats['total']}")
    print(f"  image_url NULL:     {stats['image_url_null']}")
    print(f"  video_url NULL:     {stats['video_url_null']}")
    print()


# ── Phase 1: thumbnail_url → image_url ───────────────────────────

def phase1_thumbnail_copy(session) -> int:
    """Copy thumbnail_url into image_url where image_url is NULL."""
    print("-- Phase 1: thumbnail_url -> image_url ------------------")

    ads = (
        session.query(Ad)
        .filter(Ad.image_url.is_(None), Ad.thumbnail_url.isnot(None))
        .all()
    )

    if not ads:
        print("  No candidates found. Skipping.\n")
        return 0

    count = 0
    for i, ad in enumerate(ads):
        ad.image_url = ad.thumbnail_url
        count += 1
        if (i + 1) % BATCH_SIZE == 0:
            session.commit()

    session.commit()
    print(f"  Copied {count} records.\n")
    return count


# ── Phase 2: snapshot_url → MediaExtractor ────────────────────────

def phase2_snapshot_extract(session) -> dict:
    """Use MediaExtractor (HTTP only) to fill image_url / video_url from snapshot_url.

    Only targets render_ad URLs (with access_token) because plain
    ads/library URLs return 403 from Facebook.
    """
    print("-- Phase 2: snapshot_url -> MediaExtractor ---------------")

    from sqlalchemy import or_

    ads = (
        session.query(Ad)
        .filter(
            Ad.snapshot_url.like("%render_ad%"),
            or_(Ad.image_url.is_(None), Ad.video_url.is_(None)),
        )
        .all()
    )

    if not ads:
        print("  No candidates found. Skipping.\n")
        return {"attempted": 0, "image_filled": 0, "video_filled": 0, "failed": 0}

    total = len(ads)
    print(f"  Candidates: {total}")

    extractor = MediaExtractor(timeout=20.0)
    stats = {"attempted": total, "image_filled": 0, "video_filled": 0, "failed": 0}

    for i, ad in enumerate(ads):
        label = f"  [{i + 1}/{total}] Ad {ad.id}"
        try:
            # HTTP-only extraction (no Playwright — faster, less resource-heavy)
            extracted = asyncio.run(extractor.extract(ad.snapshot_url, use_playwright=False))

            updated = False

            if not ad.image_url and extracted.image_urls:
                ad.image_url = extracted.image_urls[0]
                stats["image_filled"] += 1
                updated = True

            if not ad.video_url and extracted.video_urls:
                ad.video_url = extracted.video_urls[0]
                stats["video_filled"] += 1
                updated = True

            if not ad.thumbnail_url and extracted.thumbnail_url:
                ad.thumbnail_url = extracted.thumbnail_url

            if extracted.creative_type != "unknown" and (
                not ad.creative_type or ad.creative_type == "unknown"
            ):
                ad.creative_type = extracted.creative_type

            status = "OK" if updated else "no media"
            print(f"{label}: {status}")

        except Exception as e:
            stats["failed"] += 1
            print(f"{label}: ERROR {e}")

        # Batch commit
        if (i + 1) % BATCH_SIZE == 0:
            session.commit()

        # Rate limit
        if i + 1 < total:
            time.sleep(REQUEST_DELAY)

    session.commit()

    print(f"  image_url filled: {stats['image_filled']}")
    print(f"  video_url filled: {stats['video_filled']}")
    print(f"  Failed:           {stats['failed']}\n")
    return stats


# ── Phase 3: ad_metadata → video_url ─────────────────────────────

def phase3_metadata_video(session) -> int:
    """Extract video_url from ad_metadata fields (video_url, og_video, og:video, etc.)."""
    print("-- Phase 3: ad_metadata -> video_url --------------------")

    ads = (
        session.query(Ad)
        .filter(
            Ad.video_url.is_(None),
            Ad.ad_metadata.isnot(None),
        )
        .all()
    )

    if not ads:
        print("  No candidates found. Skipping.\n")
        return 0

    VIDEO_KEYS = ["video_url", "og_video", "og:video", "og:video:url", "video_src"]

    count = 0
    for i, ad in enumerate(ads):
        meta = ad.ad_metadata
        if not isinstance(meta, dict):
            continue

        video = None
        for key in VIDEO_KEYS:
            val = meta.get(key)
            if val and isinstance(val, str) and val.startswith("http"):
                video = val
                break

        if video:
            ad.video_url = video
            if not ad.creative_type or ad.creative_type == "unknown":
                ad.creative_type = "video"
            count += 1

        if (i + 1) % BATCH_SIZE == 0:
            session.commit()

    session.commit()
    print(f"  Extracted {count} video URLs from metadata.\n")
    return count


# ── Main ──────────────────────────────────────────────────────────

def main():
    session = _get_session()
    try:
        before = _count_nulls(session)
        _print_stats("BEFORE", before)

        p1 = phase1_thumbnail_copy(session)
        p2 = phase2_snapshot_extract(session)
        p3 = phase3_metadata_video(session)

        after = _count_nulls(session)
        _print_stats("AFTER", after)

        # Summary
        print("-- Summary -------------------------------------------------")
        print(f"  Phase 1 (thumbnail->image):   {p1} filled")
        print(f"  Phase 2 (snapshot extract):   image={p2['image_filled']}  video={p2['video_filled']}  failed={p2['failed']}")
        print(f"  Phase 3 (metadata->video):     {p3} filled")
        print()
        img_delta = before["image_url_null"] - after["image_url_null"]
        vid_delta = before["video_url_null"] - after["video_url_null"]
        print(f"  image_url NULL: {before['image_url_null']} -> {after['image_url_null']}  (-{img_delta})")
        print(f"  video_url NULL: {before['video_url_null']} -> {after['video_url_null']}  (-{vid_delta})")
        print()

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
