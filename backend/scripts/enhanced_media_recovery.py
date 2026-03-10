#!/usr/bin/env python3
"""Enhanced media recovery v1.5 — Network intercept + image validation + fallback URLs.

Targets:
  1. render_ad URLs with no image (144 ads) → retry with ads/library fallback
  2. ads_library URLs with no image (153 ads) → enhanced Playwright extraction
  3. thumbnail_url NULL but image_url exists (62 ads) → copy image_url
  4. creative_type=unknown with no media (190 ads) → re-extract

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/enhanced_media_recovery.py [--phase N] [--limit N] [--dry-run]
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
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    db_path = os.path.join(BASE_DIR, "vaap_local.db")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Session = sessionmaker(bind=engine)
    return Session()


def phase1_thumbnail_copy(session, dry_run=False):
    """Phase 1: Copy image_url to thumbnail_url where thumbnail is NULL."""
    from sqlalchemy import text

    rows = session.execute(text(
        "SELECT id, image_url FROM ads "
        "WHERE image_url IS NOT NULL AND thumbnail_url IS NULL"
    )).fetchall()
    print(f"\n=== Phase 1: thumbnail copy ({len(rows)} ads) ===")

    if dry_run:
        print(f"  [DRY RUN] Would copy image_url → thumbnail_url for {len(rows)} ads")
        return len(rows), 0

    count = 0
    for ad_id, image_url in rows:
        session.execute(text(
            "UPDATE ads SET thumbnail_url = :img, updated_at = datetime('now') WHERE id = :id"
        ), {"img": image_url, "id": ad_id})
        count += 1

    session.commit()
    print(f"  Copied: {count}")
    return count, 0


def phase2_fix_unknown_with_media(session, dry_run=False):
    """Phase 2: Fix creative_type=unknown for ads that actually have media."""
    from sqlalchemy import text

    rows = session.execute(text(
        "SELECT id, image_url, video_url FROM ads "
        "WHERE creative_type = 'unknown' AND (image_url IS NOT NULL OR video_url IS NOT NULL)"
    )).fetchall()
    print(f"\n=== Phase 2: Fix unknown types ({len(rows)} ads) ===")

    if dry_run:
        print(f"  [DRY RUN] Would fix creative_type for {len(rows)} ads")
        return len(rows), 0

    count = 0
    for ad_id, image_url, video_url in rows:
        if video_url:
            new_type = "video"
        elif image_url:
            new_type = "image"
        else:
            continue

        session.execute(text(
            "UPDATE ads SET creative_type = :ct, updated_at = datetime('now') WHERE id = :id"
        ), {"ct": new_type, "id": ad_id})
        count += 1

    session.commit()
    print(f"  Fixed: {count}")
    return count, 0


def phase3_render_ad_recovery(session, limit=0, dry_run=False):
    """Phase 3: Re-extract render_ad URLs with ads/library fallback."""
    from sqlalchemy import text
    from app.services.media_extraction import MediaExtractor

    rows = session.execute(text(
        "SELECT id, external_id, snapshot_url FROM ads "
        "WHERE snapshot_url LIKE '%render_ad%' AND image_url IS NULL "
        "ORDER BY id LIMIT :limit"
    ), {"limit": limit if limit > 0 else 99999}).fetchall()
    print(f"\n=== Phase 3: render_ad recovery ({len(rows)} ads) ===")

    if dry_run:
        print(f"  [DRY RUN] Would re-extract {len(rows)} render_ad ads")
        return 0, len(rows)

    if not rows:
        return 0, 0

    extractor = MediaExtractor(timeout=30.0)
    success = 0
    failed = 0

    for i, (ad_id, external_id, snapshot_url) in enumerate(rows):
        try:
            # v1.5: Pass external_id for ads/library fallback
            extracted = asyncio.run(
                extractor.extract(snapshot_url, use_playwright=True, external_id=external_id)
            )

            updates = {}
            if extracted.image_urls:
                updates["image_url"] = extracted.image_urls[0]
                updates["thumbnail_url"] = extracted.thumbnail_url or extracted.image_urls[0]
            if extracted.video_urls:
                updates["video_url"] = extracted.video_urls[0]
            if extracted.creative_type != "unknown":
                updates["creative_type"] = extracted.creative_type
            if extracted.destination_url:
                updates["destination_url"] = extracted.destination_url

            if updates:
                set_parts = [f"{k} = :{k}" for k in updates]
                set_parts.append("updated_at = datetime('now')")
                sql = f"UPDATE ads SET {', '.join(set_parts)} WHERE id = :id"
                updates["id"] = ad_id
                session.execute(text(sql), updates)
                success += 1
                print(f"  [{i+1}/{len(rows)}] OK id={ad_id} type={extracted.creative_type} "
                      f"method={extracted.extraction_method}")
            else:
                failed += 1
                reason = extracted.restriction_reason or extracted.debug_stage or "no_media"
                if (i + 1) % 20 == 0:
                    print(f"  [{i+1}/{len(rows)}] FAIL id={ad_id} reason={reason}")

        except Exception as e:
            failed += 1
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(rows)}] ERROR id={ad_id}: {str(e)[:80]}")

        if (i + 1) % 10 == 0:
            try:
                session.commit()
            except Exception:
                session.rollback()

        time.sleep(1.0)

    try:
        session.commit()
    except Exception:
        session.rollback()

    print(f"  Success: {success}, Failed: {failed}")
    return success, failed


def phase4_ads_library_recovery(session, limit=0, dry_run=False):
    """Phase 4: Re-extract ads_library URLs with enhanced Playwright."""
    from sqlalchemy import text
    from app.services.media_extraction import MediaExtractor

    rows = session.execute(text(
        "SELECT id, external_id, snapshot_url FROM ads "
        "WHERE snapshot_url LIKE '%ads/library%' AND image_url IS NULL "
        "ORDER BY id LIMIT :limit"
    ), {"limit": limit if limit > 0 else 99999}).fetchall()
    print(f"\n=== Phase 4: ads_library recovery ({len(rows)} ads) ===")

    if dry_run:
        print(f"  [DRY RUN] Would re-extract {len(rows)} ads_library ads")
        return 0, len(rows)

    if not rows:
        return 0, 0

    extractor = MediaExtractor(timeout=45.0)
    success = 0
    failed = 0

    for i, (ad_id, external_id, snapshot_url) in enumerate(rows):
        try:
            extracted = asyncio.run(
                extractor.extract(snapshot_url, use_playwright=True, external_id=external_id)
            )

            updates = {}
            if extracted.image_urls:
                updates["image_url"] = extracted.image_urls[0]
                updates["thumbnail_url"] = extracted.thumbnail_url or extracted.image_urls[0]
            if extracted.video_urls:
                updates["video_url"] = extracted.video_urls[0]
            if extracted.creative_type != "unknown":
                updates["creative_type"] = extracted.creative_type
            if extracted.destination_url:
                updates["destination_url"] = extracted.destination_url

            if updates:
                set_parts = [f"{k} = :{k}" for k in updates]
                set_parts.append("updated_at = datetime('now')")
                sql = f"UPDATE ads SET {', '.join(set_parts)} WHERE id = :id"
                updates["id"] = ad_id
                session.execute(text(sql), updates)
                success += 1
                print(f"  [{i+1}/{len(rows)}] OK id={ad_id} type={extracted.creative_type} "
                      f"imgs={len(extracted.image_urls)} vids={len(extracted.video_urls)}")
            else:
                failed += 1
                reason = extracted.restriction_reason or extracted.debug_stage or "no_media"
                if (i + 1) % 20 == 0:
                    print(f"  [{i+1}/{len(rows)}] FAIL id={ad_id} reason={reason}")

        except Exception as e:
            failed += 1
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(rows)}] ERROR id={ad_id}: {str(e)[:80]}")

        if (i + 1) % 10 == 0:
            try:
                session.commit()
            except Exception:
                session.rollback()

        time.sleep(1.5)

    try:
        session.commit()
    except Exception:
        session.rollback()

    print(f"  Success: {success}, Failed: {failed}")
    return success, failed


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enhanced media recovery v1.5")
    parser.add_argument("--phase", type=int, default=0, help="Run specific phase (1-4), 0=all")
    parser.add_argument("--limit", type=int, default=0, help="Limit per phase")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    session = _get_session()
    total_success = 0
    total_failed = 0

    try:
        phases = {
            1: ("Thumbnail copy", phase1_thumbnail_copy),
            2: ("Fix unknown types", phase2_fix_unknown_with_media),
            3: ("render_ad recovery", lambda s, dr: phase3_render_ad_recovery(s, args.limit, dr)),
            4: ("ads_library recovery", lambda s, dr: phase4_ads_library_recovery(s, args.limit, dr)),
        }

        run_phases = [args.phase] if args.phase > 0 else [1, 2, 3, 4]

        print("=" * 60)
        print("Enhanced Media Recovery v1.5")
        print(f"Phases: {run_phases}")
        print(f"Limit: {args.limit or 'unlimited'}")
        print(f"Dry run: {args.dry_run}")
        print("=" * 60)

        for p in run_phases:
            name, func = phases[p]
            print(f"\n{'='*40}")
            print(f"Starting Phase {p}: {name}")
            print(f"{'='*40}")
            s, f = func(session, args.dry_run)
            total_success += s
            total_failed += f

    finally:
        session.close()

    print(f"\n{'='*60}")
    print(f"RECOVERY COMPLETE")
    print(f"Total success: {total_success}")
    print(f"Total failed:  {total_failed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
