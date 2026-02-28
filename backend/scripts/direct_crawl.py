"""Direct crawl script - bypasses HTTP API for speed.

Calls the crawler directly via Python imports, no API timeout issues.
Downloads media immediately after crawl.
"""
import sys
import os
import time
import asyncio
import uuid
import requests as http_requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, AdStatusEnum
from app.tasks.crawl_tasks import _crawl_platforms, _map_platform, get_connected_platforms
from sqlalchemy.orm.attributes import flag_modified

KEYWORDS = [
    "\u30c0\u30a4\u30a8\u30c3\u30c8",         # diet
    "\u7f8e\u5bb9",                             # beauty
    "\u8131\u6bdb",                             # hair removal
    "\u30b5\u30d7\u30ea",                       # supplement
    "\u30d5\u30a3\u30c3\u30c8\u30cd\u30b9",     # fitness
    "\u5316\u7ca7\u54c1",                       # cosmetics
    "\u30db\u30ef\u30a4\u30c8\u30cb\u30f3\u30b0", # whitening
    "\u30a8\u30b9\u30c6",                       # esthetics
    "\u30d7\u30ed\u30c6\u30a4\u30f3",           # protein
    "\u80b2\u6bdb",                             # hair growth
    "\u30b9\u30ad\u30f3\u30b1\u30a2",           # skincare
    "\u5065\u5eb7\u98df\u54c1",                 # health food
    "\u7b4b\u30c8\u30ec",                       # muscle training
    "\u30e8\u30ac",                             # yoga
    "\u8102\u80aa\u71c3\u713c",                 # fat burning
]

PLATFORMS = ["facebook", "instagram"]
LIMIT_PER_PLATFORM = 50
MEDIA_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media_cache")


def download_media_for_ad(ad):
    """Download thumbnail and image for a single ad."""
    downloaded = {"thumbnail": False, "image": False}

    for media_type, url_field, s3_field, subdir in [
        ("thumbnail", "thumbnail_url", "thumbnail_s3_key", "thumbnails"),
        ("image", "image_url", "image_s3_key", "images"),
    ]:
        url = getattr(ad, url_field, None)
        if not url:
            continue

        existing_key = getattr(ad, s3_field, None)
        if existing_key and "media_cache/" in str(existing_key):
            downloaded[media_type] = True
            continue

        save_dir = os.path.join(MEDIA_CACHE_DIR, subdir)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"{ad.id}.jpg")

        try:
            resp = http_requests.get(url, timeout=15, stream=True)
            if resp.status_code == 200:
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)
                file_size = os.path.getsize(save_path)
                if file_size > 1000:
                    setattr(ad, s3_field, f"media_cache/{subdir}/{ad.id}.jpg")
                    downloaded[media_type] = True
                else:
                    os.remove(save_path)
        except Exception:
            pass

    return downloaded


def main():
    print("=" * 60)
    print("  DIRECT CRAWL - Bypass API, call crawler directly")
    print("=" * 60)

    # Check connected platforms
    connected = get_connected_platforms()
    print(f"Connected platforms: {connected}")

    active = [p for p in PLATFORMS if p in connected]
    if not active:
        print("ERROR: No platforms connected! Set Meta API token first.")
        print("Use the settings API to add your Meta access_token.")
        return

    print(f"Active platforms: {active}")
    print(f"Keywords: {len(KEYWORDS)}")
    print(f"Limit per platform: {LIMIT_PER_PLATFORM}")
    print()

    total_saved = 0
    crawl_results = []

    for i, keyword in enumerate(KEYWORDS):
        kw_safe = keyword.encode("ascii", "replace").decode("ascii")
        print(f"[{i+1}/{len(KEYWORDS)}] Crawling: {kw_safe} ...", end=" ", flush=True)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(
                _crawl_platforms(keyword, active, None, LIMIT_PER_PLATFORM)
            )
            loop.close()

            # Count results
            ad_count = sum(len(ads) for ads in results.values())
            print(f"found {ad_count} ads", end=" ", flush=True)

            # Save to DB
            session = SyncSessionLocal()
            saved = 0
            try:
                for platform, crawled_ads in results.items():
                    for crawled_ad in crawled_ads:
                        if crawled_ad.external_id:
                            existing = session.query(Ad).filter(
                                Ad.external_id == crawled_ad.external_id
                            ).first()
                            if existing:
                                continue

                        has_direct_media = bool(crawled_ad.image_urls or crawled_ad.video_url)
                        extraction_status = "skipped" if has_direct_media else (
                            "pending" if crawled_ad.snapshot_url else "skipped"
                        )

                        dest_url = crawled_ad.destination_url
                        if not dest_url:
                            dest_url = (crawled_ad.metadata or {}).get("destination_url")

                        ad_category = None
                        if crawled_ad.category:
                            from app.models.ad import AdCategoryEnum
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
                print(f"-> saved {saved} new")
                total_saved += saved
                crawl_results.append((kw_safe, ad_count, saved))

                # Download media for newly saved ads
                if saved > 0:
                    new_ads = session.query(Ad).order_by(Ad.id.desc()).limit(saved).all()
                    thumb_ok = 0
                    img_ok = 0
                    for ad in new_ads:
                        dl = download_media_for_ad(ad)
                        if dl["thumbnail"]:
                            thumb_ok += 1
                        if dl["image"]:
                            img_ok += 1
                    session.commit()
                    print(f"    Media: {thumb_ok} thumbnails, {img_ok} images cached")

            except Exception as db_err:
                session.rollback()
                print(f"DB error: {db_err}")
            finally:
                session.close()

        except Exception as e:
            err_msg = str(e)[:80]
            print(f"ERROR: {err_msg}")
            crawl_results.append((kw_safe, 0, 0))

        time.sleep(2)

    # Final summary
    print()
    print("=" * 60)
    print("  CRAWL COMPLETE")
    print("=" * 60)
    print(f"  Total new ads saved: {total_saved}")
    print()
    print("  Per-keyword results:")
    for kw, found, saved in crawl_results:
        print(f"    {kw}: found={found}, saved={saved}")

    # Final DB stats
    session = SyncSessionLocal()
    total_ads = session.query(Ad).count()
    cached_thumbs = session.query(Ad).filter(
        Ad.thumbnail_s3_key.isnot(None),
        Ad.thumbnail_s3_key != "",
    ).count()
    has_video = session.query(Ad).filter(Ad.video_url.isnot(None)).count()
    session.close()

    print()
    print(f"  DB total: {total_ads} ads")
    print(f"  Cached thumbnails: {cached_thumbs}")
    print(f"  Has video_url: {has_video}")


if __name__ == "__main__":
    main()
