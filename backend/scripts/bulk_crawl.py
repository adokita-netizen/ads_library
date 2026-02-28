#!/usr/bin/env python3
"""Bulk crawl fresh ads from Meta Ad Library via direct crawl logic.

Crawls 15 Japanese ad-market keywords across facebook and instagram,
then runs post-crawl media download and creative analysis on new ads.

Run from the backend directory:
    cd backend
    python -u scripts/bulk_crawl.py

Note: Use -u flag for unbuffered output when running in background.
"""

import asyncio
import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Configuration ────────────────────────────────────────────────────────

KEYWORDS = [
    "\u30c0\u30a4\u30a8\u30c3\u30c8",        # diet
    "\u7f8e\u5bb9",                            # beauty
    "\u8131\u6bdb",                            # hair removal
    "\u30b5\u30d7\u30ea",                      # supplements
    "\u30d5\u30a3\u30c3\u30c8\u30cd\u30b9",    # fitness
    "\u5316\u7ca7\u54c1",                      # cosmetics
    "\u30db\u30ef\u30a4\u30c8\u30cb\u30f3\u30b0",  # whitening
    "\u30a8\u30b9\u30c6",                      # esthetics
    "\u30d7\u30ed\u30c6\u30a4\u30f3",          # protein
    "\u80b2\u6bdb",                            # hair growth
    "\u30b9\u30ad\u30f3\u30b1\u30a2",          # skincare
    "\u5065\u5eb7\u98df\u54c1",                # health food
    "\u7b4b\u30c8\u30ec",                      # muscle training
    "\u30e8\u30ac",                            # yoga
    "\u8102\u80aa\u71c3\u713c",                # fat burning
]

PLATFORMS = ["facebook", "instagram"]
LIMIT_PER_PLATFORM = 20
SLEEP_BETWEEN_KEYWORDS = 3  # seconds

# Media download settings
REQUEST_DELAY = 0.3
REQUEST_TIMEOUT = 10
BATCH_SIZE = 20

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")


# ── Phase 1: Bulk Crawl (direct import, no HTTP) ────────────────────────

def _flush():
    """Flush stdout for unbuffered progress in background mode."""
    sys.stdout.flush()


def _save_crawled_ads(crawl_results: dict) -> int:
    """Save crawled ads to DB. Returns count of newly saved ads."""
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum, AdCategoryEnum
    from app.tasks.crawl_tasks import _map_platform

    session = SyncSessionLocal()
    saved = 0
    try:
        for platform, crawled_ads in crawl_results.items():
            for crawled_ad in crawled_ads:
                if crawled_ad.external_id:
                    existing = session.query(Ad).filter(
                        Ad.external_id == crawled_ad.external_id
                    ).first()
                    if existing:
                        continue

                has_direct_media = bool(crawled_ad.image_urls or crawled_ad.video_url)
                if has_direct_media:
                    extraction_status = "skipped"
                elif crawled_ad.snapshot_url:
                    extraction_status = "pending"
                else:
                    extraction_status = "skipped"

                dest_url = crawled_ad.destination_url
                if not dest_url:
                    dest_url = (crawled_ad.metadata or {}).get("destination_url")

                ad_category = None
                if crawled_ad.category:
                    try:
                        ad_category = AdCategoryEnum(crawled_ad.category)
                    except ValueError:
                        ad_category = AdCategoryEnum.OTHER

                ad = Ad(
                    external_id=crawled_ad.external_id,
                    title=crawled_ad.title,
                    description=crawled_ad.description,
                    platform=_map_platform(platform),
                    creative_type=crawled_ad.creative_type,
                    video_url=crawled_ad.video_url,
                    snapshot_url=crawled_ad.snapshot_url,
                    thumbnail_url=crawled_ad.thumbnail_url,
                    image_url=crawled_ad.image_urls[0] if crawled_ad.image_urls else None,
                    image_s3_keys={"urls": crawled_ad.image_urls} if len(crawled_ad.image_urls) > 1 else None,
                    destination_url=dest_url,
                    category=ad_category,
                    media_extraction_status=extraction_status,
                    advertiser_name=crawled_ad.advertiser_name,
                    advertiser_url=crawled_ad.advertiser_url,
                    brand_name=crawled_ad.brand_name,
                    duration_seconds=crawled_ad.duration_seconds,
                    view_count=crawled_ad.view_count,
                    like_count=crawled_ad.like_count,
                    spend=crawled_ad.spend,
                    impressions=crawled_ad.impressions,
                    reach=crawled_ad.reach,
                    cpc=crawled_ad.cpc,
                    cpm=crawled_ad.cpm,
                    frequency=crawled_ad.frequency,
                    first_seen_at=crawled_ad.first_seen_at,
                    last_seen_at=crawled_ad.last_seen_at,
                    tags=crawled_ad.tags,
                    ad_metadata=crawled_ad.metadata,
                    status=AdStatusEnum.PENDING,
                )
                session.add(ad)
                saved += 1

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return saved


def run_bulk_crawl() -> dict:
    """Crawl all keywords directly (no HTTP API). Returns summary dict."""
    from app.tasks.crawl_tasks import _crawl_platforms

    print("=" * 60)
    print("  PHASE 1: BULK CRAWL (direct mode)")
    print("=" * 60)
    print(f"  Keywords: {len(KEYWORDS)}")
    print(f"  Platforms: {', '.join(PLATFORMS)}")
    print(f"  Limit per platform: {LIMIT_PER_PLATFORM}")
    print()
    _flush()

    results = {
        "success": 0,
        "failed": 0,
        "total_new_ads": 0,
        "errors": [],
    }

    for i, keyword in enumerate(KEYWORDS):
        kw_label = keyword.encode("unicode_escape").decode("ascii")
        label = f"[{i + 1}/{len(KEYWORDS)}]"

        try:
            print(f"  {label} Crawling: {kw_label} ...")
            _flush()
            start = time.time()

            crawl_results = asyncio.run(
                _crawl_platforms(
                    query=keyword,
                    platforms=PLATFORMS,
                    category=None,
                    limit_per_platform=LIMIT_PER_PLATFORM,
                )
            )

            # Count raw results
            total_crawled = sum(len(ads) for ads in crawl_results.values())
            elapsed = time.time() - start
            print(f"         Crawled {total_crawled} ads in {elapsed:.1f}s")
            _flush()

            # Save to DB
            saved = _save_crawled_ads(crawl_results)
            results["success"] += 1
            results["total_new_ads"] += saved
            print(f"         Saved {saved} new ads to DB")
            _flush()

        except Exception as e:
            results["failed"] += 1
            err_str = str(e).encode("unicode_escape").decode("ascii")
            results["errors"].append(f"{kw_label}: {err_str[:150]}")
            print(f"         FAILED: {err_str[:200]}")
            _flush()

        # Sleep between keywords
        if i < len(KEYWORDS) - 1:
            time.sleep(SLEEP_BETWEEN_KEYWORDS)

    print()
    print(f"  Crawl Summary: {results['success']} success, "
          f"{results['failed']} failed, "
          f"{results['total_new_ads']} new ads saved")
    if results["errors"]:
        print(f"  Errors:")
        for err in results["errors"]:
            print(f"    - {err}")
    print()
    _flush()

    return results


# ── Phase 2: Post-Crawl Media Download ──────────────────────────────────

def download_file(url: str, dest_path: str) -> bool:
    """Download a single file. Returns True on success."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.status_code == 403:
            return False
        if resp.status_code != 200:
            return False

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = os.path.getsize(dest_path)
        if file_size < 100:
            os.remove(dest_path)
            return False

        return True

    except Exception:
        return False


def run_media_download() -> dict:
    """Download media for NEW ads (thumbnail_s3_key IS NULL)."""
    from sqlalchemy.orm.attributes import flag_modified
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    print("=" * 60)
    print("  PHASE 2: MEDIA DOWNLOAD (new ads only)")
    print("=" * 60)

    os.makedirs(THUMB_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)

    session = SyncSessionLocal()
    stats = {"thumb_ok": 0, "thumb_skip": 0, "img_ok": 0, "img_skip": 0}

    try:
        # Only process ads where thumbnail_s3_key IS NULL (new/uncached ads)
        ads = session.query(Ad).filter(
            Ad.thumbnail_s3_key.is_(None)
        ).order_by(Ad.id).all()

        total = len(ads)
        print(f"  Ads needing media download: {total}")

        if total == 0:
            print("  No new ads need media download.")
            print()
            return stats

        for i, ad in enumerate(ads):
            ad_id = ad.id

            # Thumbnail
            thumb_path = os.path.join(THUMB_DIR, f"{ad_id}.jpg")
            if ad.thumbnail_url and not os.path.exists(thumb_path):
                if download_file(ad.thumbnail_url, thumb_path):
                    ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                    stats["thumb_ok"] += 1
                else:
                    stats["thumb_skip"] += 1
                time.sleep(REQUEST_DELAY)
            elif ad.thumbnail_url and os.path.exists(thumb_path):
                if not ad.thumbnail_s3_key:
                    ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                stats["thumb_ok"] += 1

            # Image
            img_path = os.path.join(IMAGE_DIR, f"{ad_id}.jpg")
            if ad.image_url and not os.path.exists(img_path):
                if download_file(ad.image_url, img_path):
                    ad.image_s3_key = f"media_cache/images/{ad_id}.jpg"
                    stats["img_ok"] += 1
                else:
                    stats["img_skip"] += 1
                time.sleep(REQUEST_DELAY)
            elif ad.image_url and os.path.exists(img_path):
                if not ad.image_s3_key:
                    ad.image_s3_key = f"media_cache/images/{ad_id}.jpg"
                stats["img_ok"] += 1

            # Update metadata
            if ad.thumbnail_s3_key or ad.image_s3_key:
                meta = dict(ad.ad_metadata or {})
                meta["media_cached"] = True
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

            # Batch commit
            if (i + 1) % BATCH_SIZE == 0:
                session.commit()
                print(f"    Committed batch {i + 1}/{total}")

        session.commit()

        print(f"  Thumbnails: {stats['thumb_ok']} downloaded, {stats['thumb_skip']} failed")
        print(f"  Images:     {stats['img_ok']} downloaded, {stats['img_skip']} failed")
        print()

    except Exception as e:
        session.rollback()
        err_str = str(e).encode("unicode_escape").decode("ascii")
        print(f"  ERROR in media download: {err_str}")
    finally:
        session.close()

    return stats


# ── Phase 3: Post-Crawl Creative Analysis ───────────────────────────────

def run_creative_analysis() -> int:
    """Run creative analysis on new ads (missing creative_analysis in metadata)."""
    from sqlalchemy.orm.attributes import flag_modified
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    # Import the analyze_ad function from the existing script
    sys.path.insert(0, os.path.join(BASE_DIR, "scripts"))
    from analyze_creative_elements import analyze_ad

    print("=" * 60)
    print("  PHASE 3: CREATIVE ANALYSIS (new ads only)")
    print("=" * 60)

    session = SyncSessionLocal()
    analyzed = 0

    try:
        # Get all ads and filter in Python for those missing creative_analysis
        # (JSONB key check is complex across databases)
        all_ads = session.query(Ad).order_by(Ad.id).all()

        candidates = []
        for ad in all_ads:
            meta = ad.ad_metadata or {}
            if "creative_analysis" not in meta:
                candidates.append(ad)

        total = len(candidates)
        print(f"  Ads needing creative analysis: {total}")

        if total == 0:
            print("  No new ads need creative analysis.")
            print()
            return 0

        for i, ad in enumerate(candidates):
            try:
                analysis = analyze_ad(ad)

                meta = dict(ad.ad_metadata or {})
                meta["creative_analysis"] = analysis
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                analyzed += 1

            except Exception as e:
                err_str = str(e).encode("unicode_escape").decode("ascii")
                print(f"    Warning: analysis failed for ad {ad.id}: {err_str}")

            # Batch commit
            if (i + 1) % BATCH_SIZE == 0:
                session.commit()
                print(f"    Committed batch {i + 1}/{total}")

        session.commit()
        print(f"  Analyzed: {analyzed}/{total} ads")
        print()

    except Exception as e:
        session.rollback()
        err_str = str(e).encode("unicode_escape").decode("ascii")
        print(f"  ERROR in creative analysis: {err_str}")
    finally:
        session.close()

    return analyzed


# ── Phase 4: Final Report ───────────────────────────────────────────────

def print_final_report(crawl_results: dict, media_stats: dict, analyzed_count: int):
    """Print the final summary report."""
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        total_ads = session.query(Ad).count()
        with_thumb = session.query(Ad).filter(Ad.thumbnail_s3_key.isnot(None)).count()
        with_img = session.query(Ad).filter(Ad.image_s3_key.isnot(None)).count()
        with_video = session.query(Ad).filter(Ad.video_url.isnot(None)).count()
    finally:
        session.close()

    print("=" * 60)
    print("  FINAL REPORT")
    print("=" * 60)
    print()
    print(f"  Crawl Results:")
    print(f"    Keywords processed:   {len(KEYWORDS)}")
    print(f"    Successful crawls:    {crawl_results['success']}")
    print(f"    Failed crawls:        {crawl_results['failed']}")
    print(f"    Skipped:              {crawl_results['skipped']}")
    print()
    print(f"  Media Download:")
    print(f"    Thumbnails cached:    {media_stats.get('thumb_ok', 0)}")
    print(f"    Thumbnails failed:    {media_stats.get('thumb_skip', 0)}")
    print(f"    Images cached:        {media_stats.get('img_ok', 0)}")
    print(f"    Images failed:        {media_stats.get('img_skip', 0)}")
    print()
    print(f"  Creative Analysis:")
    print(f"    Ads analyzed:         {analyzed_count}")
    print()
    print(f"  Database State:")
    print(f"    Total ads:            {total_ads}")
    print(f"    With thumbnail_s3_key: {with_thumb}")
    print(f"    With image_s3_key:     {with_img}")
    print(f"    With video_url:        {with_video}")
    print()
    print("=" * 60)
    print("  BULK CRAWL COMPLETE")
    print("=" * 60)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 60)
    print("  VAAP BULK CRAWL SCRIPT (direct mode)")
    print("  Fresh Ad Crawl + Media Download + Creative Analysis")
    print("=" * 60)
    print()
    _flush()

    # Count ads before crawl
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad
    try:
        session = SyncSessionLocal()
        ads_before = session.query(Ad).count()
        session.close()
        print(f"  Ads before crawl: {ads_before}")
    except Exception:
        ads_before = 0
        print("  Warning: Could not count ads before crawl (DB not available)")
    print()
    _flush()

    # Phase 1: Bulk crawl (direct)
    crawl_results = run_bulk_crawl()

    # Count ads after crawl
    try:
        session = SyncSessionLocal()
        ads_after = session.query(Ad).count()
        session.close()
        new_ads = ads_after - ads_before
        print(f"  Ads after crawl: {ads_after} (new: {new_ads})")
    except Exception:
        new_ads = 0
        print("  Warning: Could not count ads after crawl")
    print()
    _flush()

    # Phase 2: Media download
    media_stats = run_media_download()

    # Phase 3: Creative analysis
    analyzed_count = run_creative_analysis()

    # Phase 4: Final report
    print_final_report(crawl_results, media_stats, analyzed_count)


if __name__ == "__main__":
    main()
