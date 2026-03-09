#!/usr/bin/env python3
"""CI-010: Nightly re-validation for media URL reachability.

Checks image_url, video_url, thumbnail_url for all ads and flags
unreachable URLs in ad_metadata['url_health']. Optionally clears
broken URLs so re-extraction can be triggered.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/revalidate_media_urls.py [--fix] [--limit N]
"""

import io
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx


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
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "vaap_local.db",
        )
        engine = create_engine(f"sqlite:///{db_path}")
        Session = sessionmaker(bind=engine)
        return Session()


def check_url(client: httpx.Client, url: str) -> dict:
    """HEAD-check a URL and return status info."""
    try:
        resp = client.head(url, timeout=10.0, follow_redirects=True)
        return {
            "status": resp.status_code,
            "reachable": resp.status_code < 400,
            "content_type": resp.headers.get("content-type", ""),
        }
    except httpx.TimeoutException:
        return {"status": 0, "reachable": False, "error": "timeout"}
    except Exception as e:
        return {"status": 0, "reachable": False, "error": str(e)[:100]}


def revalidate(fix: bool = False, limit: int = 0):
    from app.models.ad import Ad
    from sqlalchemy.orm.attributes import flag_modified
    from sqlalchemy import or_

    session = _get_session()

    query = session.query(Ad).filter(
        or_(
            Ad.image_url.isnot(None),
            Ad.video_url.isnot(None),
            Ad.thumbnail_url.isnot(None),
        )
    )
    if limit > 0:
        query = query.limit(limit)

    ads = query.all()
    print(f"Checking {len(ads)} ads with media URLs...")

    client = httpx.Client(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            )
        },
        follow_redirects=True,
    )

    stats = {
        "checked": 0,
        "image_ok": 0, "image_broken": 0,
        "video_ok": 0, "video_broken": 0,
        "thumb_ok": 0, "thumb_broken": 0,
        "fixed": 0,
    }

    batch_size = 50
    for i, ad in enumerate(ads):
        meta = dict(ad.ad_metadata or {})
        url_health = {}
        changed = False

        for field_name, stat_prefix in [
            ("image_url", "image"),
            ("video_url", "video"),
            ("thumbnail_url", "thumb"),
        ]:
            url = getattr(ad, field_name, None)
            if not url:
                continue

            result = check_url(client, url)
            url_health[field_name] = result
            stats["checked"] += 1

            if result["reachable"]:
                stats[f"{stat_prefix}_ok"] += 1
            else:
                stats[f"{stat_prefix}_broken"] += 1
                if fix:
                    # Clear broken URL so re-extraction can pick it up
                    setattr(ad, field_name, None)
                    changed = True
                    stats["fixed"] += 1

        if url_health:
            meta["url_health"] = url_health
            meta["url_health_checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            changed = True

        if changed and (i + 1) % batch_size == 0:
            try:
                session.commit()
            except Exception:
                session.rollback()
            print(f"  Progress: {i + 1}/{len(ads)}")

        # Rate limit
        time.sleep(0.1)

    # Final commit
    try:
        session.commit()
    except Exception:
        session.rollback()

    client.close()
    session.close()

    print(f"\n=== Media URL Revalidation Results ===")
    print(f"Total URLs checked: {stats['checked']}")
    print(f"Image:     {stats['image_ok']} OK / {stats['image_broken']} broken")
    print(f"Video:     {stats['video_ok']} OK / {stats['video_broken']} broken")
    print(f"Thumbnail: {stats['thumb_ok']} OK / {stats['thumb_broken']} broken")
    if fix:
        print(f"Fixed (cleared): {stats['fixed']}")


if __name__ == "__main__":
    fix_mode = "--fix" in sys.argv
    limit_val = 0
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit_val = int(sys.argv[idx + 1])
    revalidate(fix=fix_mode, limit=limit_val)
