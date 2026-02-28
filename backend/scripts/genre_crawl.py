"""Genre-specific ad crawl script.

Crawls ads by fine genre/product category (e.g. medical weight loss,
diet supplements, beauty clinics, etc.).  Each genre has its own set
of search keywords.  After crawl, new ads are tagged with fine_genre
metadata and media is downloaded immediately.

Usage:
    # Crawl a single genre
    python scripts/genre_crawl.py --genre medical_weight_loss

    # Crawl all genres
    python scripts/genre_crawl.py --all

    # List available genres
    python scripts/genre_crawl.py --list
"""

import sys
import os
import json
import time
import argparse
import asyncio
import requests as http_requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, AdStatusEnum
from app.tasks.crawl_tasks import _crawl_platforms, _map_platform, get_connected_platforms
from sqlalchemy.orm.attributes import flag_modified

# ── Config paths ─────────────────────────────────────────────────────
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "genre_crawl_keywords.json",
)
MEDIA_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "media_cache",
)

# ── Built-in defaults (used when config file does not exist) ─────────
DEFAULT_GENRE_KEYWORDS = {
    "medical_weight_loss": {
        "label": "medical weight loss",
        "keywords": [
            "GLP-1 \u30c0\u30a4\u30a8\u30c3\u30c8",
            "\u30de\u30f3\u30b8\u30e3\u30ed \u75e9\u8eab",
            "\u533b\u7642\u75e9\u8eab \u30af\u30ea\u30cb\u30c3\u30af",
            "\u30a6\u30b4\u30fc\u30d3",
        ],
    },
    "diet_supplement": {
        "label": "diet supplement",
        "keywords": [
            "\u30c0\u30a4\u30a8\u30c3\u30c8\u30b5\u30d7\u30ea",
            "\u75e9\u305b\u308b\u30b5\u30d7\u30ea",
            "\u8102\u80aa\u71c3\u713c \u30b5\u30d7\u30ea\u30e1\u30f3\u30c8",
        ],
    },
    "beauty_clinic": {
        "label": "beauty clinic",
        "keywords": [
            "\u7f8e\u5bb9\u30af\u30ea\u30cb\u30c3\u30af \u6574\u5f62",
            "\u4e8c\u91cd \u7f8e\u5bb9\u5916\u79d1",
            "\u30d2\u30a2\u30eb\u30ed\u30f3\u9178 \u6ce8\u5165",
        ],
    },
    "skincare": {
        "label": "skincare",
        "keywords": [
            "\u30b9\u30ad\u30f3\u30b1\u30a2 \u7f8e\u5bb9\u6db2",
            "\u5316\u7ca7\u6c34 \u304a\u3059\u3059\u3081",
            "\u7f8e\u767d \u30af\u30ea\u30fc\u30e0",
        ],
    },
    "hair_removal": {
        "label": "hair removal",
        "keywords": [
            "\u533b\u7642\u8131\u6bdb",
            "\u5168\u8eab\u8131\u6bdb \u30b5\u30ed\u30f3",
            "VIO\u8131\u6bdb",
        ],
    },
    "hair_growth": {
        "label": "hair growth / AGA",
        "keywords": [
            "AGA \u30af\u30ea\u30cb\u30c3\u30af",
            "\u80b2\u6bdb\u5264",
            "\u8584\u6bdb \u6cbb\u7642",
        ],
    },
    "fitness": {
        "label": "fitness",
        "keywords": [
            "\u30d1\u30fc\u30bd\u30ca\u30eb\u30b8\u30e0",
            "RIZAP",
            "\u30c0\u30a4\u30a8\u30c3\u30c8 \u30b8\u30e0",
        ],
    },
    "protein": {
        "label": "protein / HMB",
        "keywords": [
            "\u30d7\u30ed\u30c6\u30a4\u30f3 \u304a\u3059\u3059\u3081",
            "HMB \u30b5\u30d7\u30ea",
            "\u7b4b\u8089 \u30b5\u30d7\u30ea\u30e1\u30f3\u30c8",
        ],
    },
    "health_food": {
        "label": "health food",
        "keywords": [
            "\u9752\u6c41",
            "\u30b3\u30e9\u30fc\u30b2\u30f3 \u30c9\u30ea\u30f3\u30af",
            "\u9175\u7d20 \u30b5\u30d7\u30ea",
        ],
    },
    "finance": {
        "label": "finance",
        "keywords": [
            "FX \u53e3\u5ea7\u958b\u8a2d",
            "\u6295\u8cc7 \u30a2\u30d7\u30ea",
            "\u30af\u30ec\u30b8\u30c3\u30c8\u30ab\u30fc\u30c9",
        ],
    },
    "education": {
        "label": "education",
        "keywords": [
            "\u30d7\u30ed\u30b0\u30e9\u30df\u30f3\u30b0 \u30b9\u30af\u30fc\u30eb",
            "\u82f1\u4f1a\u8a71 \u30aa\u30f3\u30e9\u30a4\u30f3",
            "\u8cc7\u683c \u8b1b\u5ea7",
        ],
    },
}

DEFAULT_PLATFORMS = ["facebook", "instagram"]
DEFAULT_LIMIT = 50


# ── Load config ──────────────────────────────────────────────────────

def load_genre_config():
    """Load genre keywords from config file, falling back to defaults."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            genres = data.get("genres", {})
            platforms = data.get("platforms", DEFAULT_PLATFORMS)
            limit = data.get("limit_per_platform", DEFAULT_LIMIT)
            print(f"Loaded genre config from {CONFIG_PATH}")
            print(f"  Genres: {len(genres)}, Platforms: {platforms}, Limit: {limit}")
            return genres, platforms, limit
        except Exception as e:
            print(f"WARNING: Failed to load config ({e}), using defaults")

    print("Genre config file not found, using built-in defaults")
    return DEFAULT_GENRE_KEYWORDS, DEFAULT_PLATFORMS, DEFAULT_LIMIT


# ── Media download ───────────────────────────────────────────────────

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


# ── Core crawl logic (reusable from API endpoint) ────────────────────

def crawl_genre(genre_key, genre_info, platforms, limit_per_platform):
    """Crawl a single genre. Returns dict with results.

    Parameters:
        genre_key: e.g. "medical_weight_loss"
        genre_info: dict with "label" and "keywords" keys
        platforms: list of platform names
        limit_per_platform: max ads per platform per keyword

    Returns:
        dict with keys: genre_key, label, total_found, total_saved,
                        media_downloaded, keyword_results
    """
    label = genre_info.get("label", genre_key)
    keywords = genre_info.get("keywords", [])

    result = {
        "genre_key": genre_key,
        "label": label,
        "total_found": 0,
        "total_saved": 0,
        "media_downloaded": {"thumbnails": 0, "images": 0},
        "keyword_results": [],
    }

    if not keywords:
        print(f"  No keywords for genre '{genre_key}', skipping")
        return result

    for kw_idx, keyword in enumerate(keywords):
        kw_safe = keyword.encode("ascii", "replace").decode("ascii")
        print(
            f"  [{kw_idx + 1}/{len(keywords)}] Keyword: {kw_safe} ...",
            end=" ",
            flush=True,
        )

        kw_result = {"keyword": kw_safe, "found": 0, "saved": 0}

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            crawl_results = loop.run_until_complete(
                _crawl_platforms(keyword, platforms, None, limit_per_platform)
            )
            loop.close()

            ad_count = sum(len(ads) for ads in crawl_results.values())
            kw_result["found"] = ad_count
            result["total_found"] += ad_count
            print(f"found {ad_count}", end=" ", flush=True)

            # Save to DB
            session = SyncSessionLocal()
            saved = 0
            new_ad_ids = []
            try:
                for platform, crawled_ads in crawl_results.items():
                    for crawled_ad in crawled_ads:
                        # Dedup by external_id
                        if crawled_ad.external_id:
                            existing = session.query(Ad).filter(
                                Ad.external_id == crawled_ad.external_id
                            ).first()
                            if existing:
                                # Tag existing ad with genre if not already set
                                _tag_ad_genre(existing, genre_key, label, session)
                                continue

                        has_direct_media = bool(
                            crawled_ad.image_urls or crawled_ad.video_url
                        )
                        extraction_status = "skipped" if has_direct_media else (
                            "pending" if crawled_ad.snapshot_url else "skipped"
                        )

                        dest_url = crawled_ad.destination_url
                        if not dest_url:
                            dest_url = (crawled_ad.metadata or {}).get(
                                "destination_url"
                            )

                        ad_category = None
                        if crawled_ad.category:
                            from app.models.ad import AdCategoryEnum
                            try:
                                ad_category = AdCategoryEnum(crawled_ad.category)
                            except ValueError:
                                ad_category = AdCategoryEnum.OTHER

                        # Build initial metadata with genre tags
                        ad_meta = dict(crawled_ad.metadata or {})
                        ad_meta["fine_genre"] = label
                        ad_meta["fine_genre_en"] = genre_key
                        ad_meta["crawl_source"] = "genre_crawl"

                        ad = Ad(
                            external_id=crawled_ad.external_id,
                            title=crawled_ad.title,
                            description=crawled_ad.description,
                            platform=_map_platform(platform),
                            creative_type=crawled_ad.creative_type,
                            video_url=crawled_ad.video_url,
                            snapshot_url=crawled_ad.snapshot_url,
                            thumbnail_url=crawled_ad.thumbnail_url,
                            image_url=(
                                crawled_ad.image_urls[0]
                                if crawled_ad.image_urls
                                else None
                            ),
                            image_s3_keys=(
                                {"urls": crawled_ad.image_urls}
                                if len(crawled_ad.image_urls) > 1
                                else None
                            ),
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
                            ad_metadata=ad_meta,
                            status=AdStatusEnum.PENDING,
                        )
                        session.add(ad)
                        session.flush()  # get ad.id
                        new_ad_ids.append(ad.id)
                        saved += 1

                session.commit()
                kw_result["saved"] = saved
                result["total_saved"] += saved
                print(f"-> saved {saved} new")

                # Download media for newly saved ads
                if new_ad_ids:
                    new_ads = (
                        session.query(Ad)
                        .filter(Ad.id.in_(new_ad_ids))
                        .all()
                    )
                    thumb_ok = 0
                    img_ok = 0
                    for ad in new_ads:
                        dl = download_media_for_ad(ad)
                        if dl["thumbnail"]:
                            thumb_ok += 1
                        if dl["image"]:
                            img_ok += 1
                    session.commit()
                    result["media_downloaded"]["thumbnails"] += thumb_ok
                    result["media_downloaded"]["images"] += img_ok
                    if thumb_ok or img_ok:
                        print(
                            f"    Media: {thumb_ok} thumbnails, "
                            f"{img_ok} images cached"
                        )

            except Exception as db_err:
                session.rollback()
                print(f"DB error: {db_err}")
            finally:
                session.close()

        except Exception as e:
            err_msg = str(e)[:80]
            print(f"ERROR: {err_msg}")

        result["keyword_results"].append(kw_result)
        time.sleep(2)

    return result


def _tag_ad_genre(ad, genre_key, label, session):
    """Add fine_genre metadata to an existing ad (if not already tagged)."""
    meta = dict(ad.ad_metadata or {})
    existing_genre = meta.get("fine_genre_en")
    if existing_genre == genre_key:
        return  # already tagged with this genre

    # If already tagged with a different genre, append to list
    genres_list = meta.get("fine_genres_en", [])
    if isinstance(genres_list, list):
        if genre_key not in genres_list:
            genres_list.append(genre_key)
    else:
        genres_list = [genre_key]

    if not existing_genre:
        meta["fine_genre"] = label
        meta["fine_genre_en"] = genre_key
    meta["fine_genres_en"] = genres_list
    meta["crawl_source"] = "genre_crawl"

    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")


# ── CLI entrypoint ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Genre-specific ad crawl")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--genre",
        type=str,
        help="Genre key to crawl (e.g. medical_weight_loss)",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Crawl all genres",
    )
    group.add_argument(
        "--list",
        action="store_true",
        help="List available genres and exit",
    )
    args = parser.parse_args()

    genres, platforms, limit = load_genre_config()

    # List mode
    if args.list:
        print("\nAvailable genres:")
        for key, info in genres.items():
            label = info.get("label", key)
            kw_count = len(info.get("keywords", []))
            print(f"  {key:30s} ({label}, {kw_count} keywords)")
        return

    # Check connected platforms
    connected = get_connected_platforms()
    print(f"Connected platforms: {connected}")
    active = [p for p in platforms if p in connected]
    if not active:
        print("ERROR: No platforms connected! Set Meta API token first.")
        return
    print(f"Active platforms: {active}")
    print(f"Limit per platform: {limit}")

    # Determine which genres to crawl
    if args.all:
        genre_keys = list(genres.keys())
    else:
        if args.genre not in genres:
            print(f"ERROR: Unknown genre '{args.genre}'")
            print(f"Available: {', '.join(genres.keys())}")
            return
        genre_keys = [args.genre]

    print()
    print("=" * 60)
    print("  GENRE-SPECIFIC CRAWL")
    print(f"  Genres: {len(genre_keys)}")
    print("=" * 60)
    print()

    all_results = []

    for gi, genre_key in enumerate(genre_keys):
        genre_info = genres[genre_key]
        label = genre_info.get("label", genre_key)
        kw_count = len(genre_info.get("keywords", []))
        print(f"[Genre {gi + 1}/{len(genre_keys)}] {genre_key} ({label}, {kw_count} keywords)")
        print("-" * 50)

        genre_result = crawl_genre(genre_key, genre_info, active, limit)
        all_results.append(genre_result)
        print()

    # Final summary
    print("=" * 60)
    print("  GENRE CRAWL COMPLETE")
    print("=" * 60)

    grand_found = 0
    grand_saved = 0
    grand_thumbs = 0
    grand_images = 0

    for r in all_results:
        grand_found += r["total_found"]
        grand_saved += r["total_saved"]
        grand_thumbs += r["media_downloaded"]["thumbnails"]
        grand_images += r["media_downloaded"]["images"]
        print(
            f"  {r['genre_key']:30s} found={r['total_found']:4d}  "
            f"saved={r['total_saved']:4d}  "
            f"thumbs={r['media_downloaded']['thumbnails']}  "
            f"images={r['media_downloaded']['images']}"
        )

    print()
    print(f"  Total found:  {grand_found}")
    print(f"  Total saved:  {grand_saved}")
    print(f"  Thumbnails:   {grand_thumbs}")
    print(f"  Images:       {grand_images}")

    # DB stats
    session = SyncSessionLocal()
    total_ads = session.query(Ad).count()
    genre_ads = 0
    try:
        all_ads = session.query(Ad).all()
        for ad in all_ads:
            if (ad.ad_metadata or {}).get("crawl_source") == "genre_crawl":
                genre_ads += 1
    except Exception:
        pass
    session.close()

    print()
    print(f"  DB total ads: {total_ads}")
    print(f"  Genre-tagged ads: {genre_ads}")


if __name__ == "__main__":
    main()
