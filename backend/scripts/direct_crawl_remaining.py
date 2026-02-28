"""Direct crawl - remaining keywords (skip already done ones)."""
import sys
import os
import time
import asyncio
import requests as http_requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, AdStatusEnum
from app.tasks.crawl_tasks import _crawl_platforms, _map_platform, get_connected_platforms

KEYWORDS = [
    "\u8131\u6bdb",              # hair removal
    "\u30b5\u30d7\u30ea",        # supplement
    "\u30d5\u30a3\u30c3\u30c8\u30cd\u30b9",  # fitness
    "\u5316\u7ca7\u54c1",        # cosmetics
    "\u30db\u30ef\u30a4\u30c8\u30cb\u30f3\u30b0",  # whitening
    "\u30a8\u30b9\u30c6",        # esthetics
    "\u30d7\u30ed\u30c6\u30a4\u30f3",  # protein
    "\u80b2\u6bdb",              # hair growth
    "\u30b9\u30ad\u30f3\u30b1\u30a2",  # skincare
    "\u5065\u5eb7\u98df\u54c1",  # health food
    "\u7b4b\u30c8\u30ec",        # muscle training
    "\u30e8\u30ac",              # yoga
    "\u8102\u80aa\u71c3\u713c",  # fat burning
]

PLATFORMS = ["facebook", "instagram"]
LIMIT = 30  # Reduced to avoid timeout
MEDIA_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media_cache")


def download_media(ad):
    for url_field, s3_field, subdir in [
        ("thumbnail_url", "thumbnail_s3_key", "thumbnails"),
        ("image_url", "image_s3_key", "images"),
    ]:
        url = getattr(ad, url_field, None)
        if not url:
            continue
        existing = getattr(ad, s3_field, None)
        if existing and "media_cache/" in str(existing):
            continue
        save_dir = os.path.join(MEDIA_CACHE_DIR, subdir)
        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, f"{ad.id}.jpg")
        try:
            r = http_requests.get(url, timeout=15, stream=True)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    for c in r.iter_content(8192):
                        f.write(c)
                if os.path.getsize(path) > 1000:
                    setattr(ad, s3_field, f"media_cache/{subdir}/{ad.id}.jpg")
                else:
                    os.remove(path)
        except Exception:
            pass


def main():
    print("=" * 60)
    print("  REMAINING KEYWORDS CRAWL")
    print("=" * 60)

    connected = get_connected_platforms()
    active = [p for p in PLATFORMS if p in connected]
    if not active:
        print("ERROR: No platforms connected!")
        return

    print(f"Platforms: {active}, Keywords: {len(KEYWORDS)}, Limit: {LIMIT}")
    total_saved = 0

    for i, kw in enumerate(KEYWORDS):
        kw_safe = kw.encode("ascii", "replace").decode("ascii")
        print(f"[{i+1}/{len(KEYWORDS)}] {kw_safe} ...", end=" ", flush=True)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(
                _crawl_platforms(kw, active, None, LIMIT)
            )
            loop.close()

            total_found = sum(len(ads) for ads in results.values())

            session = SyncSessionLocal()
            saved = 0
            try:
                for platform, crawled_ads in results.items():
                    for ca in crawled_ads:
                        if ca.external_id:
                            exists = session.query(Ad).filter(Ad.external_id == ca.external_id).first()
                            if exists:
                                continue

                        has_media = bool(ca.image_urls or ca.video_url)
                        dest = ca.destination_url or (ca.metadata or {}).get("destination_url")

                        ad_cat = None
                        if ca.category:
                            from app.models.ad import AdCategoryEnum
                            try:
                                ad_cat = AdCategoryEnum(ca.category)
                            except ValueError:
                                ad_cat = AdCategoryEnum.OTHER

                        ad = Ad(
                            external_id=ca.external_id,
                            title=ca.title,
                            description=ca.description,
                            platform=_map_platform(platform),
                            creative_type=ca.creative_type,
                            video_url=ca.video_url,
                            snapshot_url=ca.snapshot_url,
                            thumbnail_url=ca.thumbnail_url,
                            image_url=ca.image_urls[0] if ca.image_urls else None,
                            image_s3_keys={"urls": ca.image_urls} if len(ca.image_urls) > 1 else None,
                            destination_url=dest,
                            category=ad_cat,
                            media_extraction_status="skipped" if has_media else ("pending" if ca.snapshot_url else "skipped"),
                            advertiser_name=ca.advertiser_name,
                            advertiser_url=ca.advertiser_url,
                            brand_name=ca.brand_name,
                            duration_seconds=ca.duration_seconds,
                            view_count=ca.view_count,
                            like_count=ca.like_count,
                            spend=ca.spend,
                            impressions=ca.impressions,
                            reach=ca.reach,
                            cpc=ca.cpc,
                            cpm=ca.cpm,
                            frequency=ca.frequency,
                            first_seen_at=ca.first_seen_at,
                            last_seen_at=ca.last_seen_at,
                            tags=ca.tags,
                            ad_metadata=ca.metadata,
                            status=AdStatusEnum.PENDING,
                        )
                        session.add(ad)
                        saved += 1

                session.commit()

                # Download media
                if saved > 0:
                    new_ads = session.query(Ad).order_by(Ad.id.desc()).limit(saved).all()
                    for ad in new_ads:
                        download_media(ad)
                    session.commit()

                print(f"found={total_found} saved={saved}")
                total_saved += saved

            except Exception as e:
                session.rollback()
                print(f"DB error: {str(e)[:60]}")
            finally:
                session.close()

        except Exception as e:
            print(f"CRAWL error: {str(e)[:80]}")

        time.sleep(3)

    print(f"\nTotal new ads: {total_saved}")
    session = SyncSessionLocal()
    print(f"DB total: {session.query(Ad).count()}")
    session.close()


if __name__ == "__main__":
    main()
