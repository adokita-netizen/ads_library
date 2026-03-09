#!/usr/bin/env python3
"""Batch crawl Japanese market ads by genre-specific keywords.

Crawls the Meta Ad Library for Japanese-language ads across 10 market
genres, each with curated keyword lists.  Results are auto-classified
by genre and stored in the project's SQLite / PostgreSQL database.

Usage:
    cd backend
    python -u scripts/batch_crawl_japanese.py              # all genres
    python -u scripts/batch_crawl_japanese.py --genre beauty
    python -u scripts/batch_crawl_japanese.py --list
    python -u scripts/batch_crawl_japanese.py --genre finance --limit 30
"""

import sys
import io
import os
import time
import argparse
import asyncio

# Windows cp932 compatibility
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Genre keyword configuration for the Japanese market
# ---------------------------------------------------------------------------

GENRE_KEYWORDS = {
    "health_food": {
        "label": "Health Food",
        "category": "health",
        "keywords": [
            "\u30d7\u30ed\u30c6\u30a4\u30f3",          # protein
            "\u30b5\u30d7\u30ea\u30e1\u30f3\u30c8",      # supplement
            "\u9752\u6c41",                              # aojiru (green juice)
            "\u30d3\u30bf\u30df\u30f3",                  # vitamin
        ],
    },
    "beauty": {
        "label": "Beauty",
        "category": "beauty",
        "keywords": [
            "\u5316\u7ca7\u54c1",                        # cosmetics
            "\u7f8e\u5bb9\u6db2",                        # beauty serum
            "\u30b9\u30ad\u30f3\u30b1\u30a2",            # skincare
            "\u30b3\u30b9\u30e1",                        # cosme
            "\u307e\u3064\u6bdb\u7f8e\u5bb9\u6db2",      # eyelash serum
            "\u30b7\u30df\u53d6\u308a",                  # spot removal
        ],
    },
    "hair_removal": {
        "label": "Hair Removal",
        "category": "beauty",
        "keywords": [
            "\u533b\u7642\u8131\u6bdb",                  # medical hair removal
            "\u8131\u6bdb",                              # hair removal
            "\u5168\u8eab\u8131\u6bdb",                  # full-body hair removal
            "VIO \u8131\u6bdb",                          # VIO hair removal
        ],
    },
    "aga": {
        "label": "AGA / FAGA",
        "category": "beauty",
        "keywords": [
            "AGA",                                       # hair loss treatment
            "FAGA",                                      # female hair loss treatment
            "\u80b2\u6bdb\u5264",                        # hair growth tonic
            "\u8584\u6bdb \u6cbb\u7642",                # hair thinning treatment
        ],
    },
    "diet": {
        "label": "Diet",
        "category": "health",
        "keywords": [
            "\u75e9\u305b\u308b",                        # yaseru (lose weight)
            "\u30c0\u30a4\u30a8\u30c3\u30c8",            # diet
            "\u8102\u80aa\u71c3\u713c",                  # fat burning
            "\u533b\u7642\u30c0\u30a4\u30a8\u30c3\u30c8",  # medical diet
            "\u30e1\u30c7\u30a3\u30ab\u30eb\u30c0\u30a4\u30a8\u30c3\u30c8",  # medical diet
            "GLP-1",                                     # GLP-1
            "\u80a5\u6e80\u5916\u6765",                  # obesity clinic
            "\u30de\u30f3\u30b8\u30e3\u30ed",            # Mounjaro
        ],
    },
    "fitness": {
        "label": "Fitness",
        "category": "health",
        "keywords": [
            "\u30b8\u30e0",                              # gym
            "\u30d1\u30fc\u30bd\u30ca\u30eb\u30c8\u30ec\u30fc\u30cb\u30f3\u30b0",  # personal training
            "\u7b4b\u30c8\u30ec",                        # muscle training
            "\u30d4\u30e9\u30c6\u30a3\u30b9",            # pilates
            "\u30de\u30b7\u30f3\u30d4\u30e9\u30c6\u30a3\u30b9",  # reformer pilates
            "\u30e8\u30ac",                              # yoga
            "\u30db\u30c3\u30c8\u30e8\u30ac",            # hot yoga
            "\u5973\u6027\u5c02\u7528\u30b8\u30e0",      # women-only gym
            "24\u6642\u9593\u30b8\u30e0",                # 24-hour gym
        ],
    },
    "finance": {
        "label": "Finance",
        "category": "finance",
        "keywords": [
            "\u6295\u8cc7",                              # investment
            "FX",                                        # FX
            "\u4eee\u60f3\u901a\u8ca8",                  # cryptocurrency
            "\u4fdd\u967a",                              # insurance
            "\u30ab\u30fc\u30c9\u30ed\u30fc\u30f3",      # card loan
        ],
    },
    "ec": {
        "label": "EC / E-Commerce",
        "category": "ec_d2c",
        "keywords": [
            "\u901a\u8ca9",                              # mail order / online shop
            "\u30b7\u30e7\u30c3\u30d7",                  # shop
            "\u30bb\u30fc\u30eb",                        # sale
            "\u9001\u6599\u7121\u6599",                  # free shipping
        ],
    },
    "app": {
        "label": "App",
        "category": "app",
        "keywords": [
            "\u30a2\u30d7\u30ea",                        # app
            "\u30b2\u30fc\u30e0",                        # game
            "\u30de\u30c3\u30c1\u30f3\u30b0",            # matching
        ],
    },
    "education": {
        "label": "Education",
        "category": "education",
        "keywords": [
            "\u82f1\u4f1a\u8a71",                        # English conversation
            "\u8cc7\u683c",                              # qualification / certification
            "\u30d7\u30ed\u30b0\u30e9\u30df\u30f3\u30b0",  # programming
            "\u587e",                                    # cram school
        ],
    },
    "real_estate": {
        "label": "Real Estate",
        "category": "real_estate",
        "keywords": [
            "\u30de\u30f3\u30b7\u30e7\u30f3",            # mansion / condo
            "\u4f4f\u5b85",                              # housing
            "\u5f15\u8d8a\u3057",                        # moving
        ],
    },
    "jobs": {
        "label": "Jobs / Recruitment",
        "category": "other",
        "keywords": [
            "\u6c42\u4eba",                              # job listing
            "\u8ee2\u8077",                              # career change
            "\u5c31\u8077",                              # employment
            "\u30d0\u30a4\u30c8",                        # part-time job
        ],
    },
}

PLATFORMS = ["facebook", "instagram"]
DEFAULT_LIMIT = 20
SLEEP_BETWEEN_KEYWORDS = 3  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flush():
    sys.stdout.flush()


def _safe_label(text: str) -> str:
    """Return an ASCII-safe representation of text for console output."""
    try:
        return text.encode("ascii", "replace").decode("ascii")
    except Exception:
        return repr(text)


def _classify_genre(crawled_ad, genre_key: str, genre_info: dict) -> dict:
    """Build metadata dict with genre classification for a crawled ad."""
    meta = dict(crawled_ad.metadata or {})
    meta["jp_genre"] = genre_info.get("label", genre_key)
    meta["jp_genre_key"] = genre_key
    meta["crawl_source"] = "batch_crawl_japanese"
    meta["language_filter"] = "ja"
    return meta


def _append_unique(values: list[str], value: str | None) -> list[str]:
    normalized = str(value or "").strip()
    if not normalized:
        return values
    if normalized not in values:
        values.append(normalized)
    return values


def _get_session():
    """Get DB session with SQLite fallback for local ops scripts."""
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
        session_factory = sessionmaker(bind=engine)
        return session_factory()


def _patch_local_task_sessions():
    """Force crawl tasks to use local SQLite when primary DB is unavailable."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.tasks import crawl_tasks as crawl_tasks_module

        db_path = os.path.join(BASE_DIR, "vaap_local.db")
        if not os.path.exists(db_path):
            return

        engine = create_engine(f"sqlite:///{db_path}")
        local_session = sessionmaker(bind=engine)
        crawl_tasks_module.SyncSessionLocal = local_session

        import app.core.database as db_module

        db_module.SyncSessionLocal = local_session
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core crawl + save
# ---------------------------------------------------------------------------

def crawl_and_save_genre(genre_key: str, genre_info: dict, platforms: list,
                         limit_per_platform: int) -> dict:
    """Crawl all keywords for one genre.  Returns summary dict."""
    from app.models.ad import Ad, AdStatusEnum, AdCategoryEnum, MediaExtractionStatus
    from app.tasks.crawl_tasks import _crawl_platforms, _map_platform, _extract_destination_url, _extract_text_fallback
    from sqlalchemy.orm.attributes import flag_modified

    label = genre_info.get("label", genre_key)
    keywords = genre_info.get("keywords", [])
    category_str = genre_info.get("category")

    result = {
        "genre_key": genre_key,
        "label": label,
        "total_found": 0,
        "total_saved": 0,
        "errors": [],
    }

    if not keywords:
        print(f"  No keywords for genre '{genre_key}', skipping")
        return result

    for kw_idx, keyword in enumerate(keywords):
        kw_label = _safe_label(keyword)
        tag = f"  [{kw_idx + 1}/{len(keywords)}]"
        print(f"{tag} Keyword: {kw_label} ...", end=" ", flush=True)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            crawl_results = loop.run_until_complete(
                _crawl_platforms(keyword, platforms, None, limit_per_platform)
            )
            loop.close()

            ad_count = sum(len(ads) for ads in crawl_results.values())
            result["total_found"] += ad_count
            print(f"found {ad_count}", end=" ", flush=True)

            # Save to DB
            session = _get_session()
            saved = 0
            try:
                for platform, crawled_ads in crawl_results.items():
                    for crawled_ad in crawled_ads:
                        # Skip if external_id already exists
                        if crawled_ad.external_id:
                            existing = session.query(Ad).filter(
                                Ad.external_id == crawled_ad.external_id
                            ).first()
                            if existing:
                                # Tag existing ad with genre info
                                meta = dict(existing.ad_metadata or {})
                                genres_list = meta.get("jp_genres", [])
                                if genre_key not in genres_list:
                                    genres_list.append(genre_key)
                                meta["jp_genres"] = genres_list
                                if "jp_genre_key" not in meta:
                                    meta["jp_genre_key"] = genre_key
                                    meta["jp_genre"] = label
                                meta["source_keyword"] = keyword
                                search_terms = list(meta.get("jp_search_terms", []))
                                _append_unique(search_terms, keyword)
                                _append_unique(search_terms, crawled_ad.metadata.get("crawl_query") if crawled_ad.metadata else None)
                                _append_unique(search_terms, meta.get("crawl_query"))
                                meta["jp_search_terms"] = search_terms
                                aliases = list(meta.get("crawl_query_aliases", []))
                                for term in search_terms:
                                    _append_unique(aliases, term)
                                meta["crawl_query_aliases"] = aliases
                                existing.ad_metadata = meta
                                flag_modified(existing, "ad_metadata")
                                continue

                        # Determine media extraction status
                        has_direct_media = bool(
                            crawled_ad.image_urls or crawled_ad.video_url
                        )
                        if has_direct_media:
                            extraction_status = MediaExtractionStatus.SKIPPED
                        elif crawled_ad.snapshot_url:
                            extraction_status = MediaExtractionStatus.PENDING
                        else:
                            extraction_status = MediaExtractionStatus.SKIPPED

                        dest_url = _extract_destination_url(crawled_ad)
                        title, description = _extract_text_fallback(crawled_ad)

                        # Map category
                        ad_category = None
                        if category_str:
                            try:
                                ad_category = AdCategoryEnum(category_str)
                            except ValueError:
                                ad_category = AdCategoryEnum.OTHER
                        elif crawled_ad.category:
                            try:
                                ad_category = AdCategoryEnum(crawled_ad.category)
                            except ValueError:
                                ad_category = AdCategoryEnum.OTHER

                        # Build metadata with genre classification
                        ad_meta = _classify_genre(crawled_ad, genre_key, genre_info)
                        ad_meta["jp_genres"] = [genre_key]
                        ad_meta["source_keyword"] = keyword
                        ad_meta["jp_search_terms"] = []
                        _append_unique(ad_meta["jp_search_terms"], keyword)
                        _append_unique(ad_meta["jp_search_terms"], ad_meta.get("crawl_query"))
                        ad_meta["crawl_query_aliases"] = list(ad_meta["jp_search_terms"])
                        if dest_url:
                            ad_meta["destination_url"] = dest_url
                            ad_meta.setdefault("destination_type", "LP")

                        ad = Ad(
                            external_id=crawled_ad.external_id,
                            title=title,
                            description=description,
                            platform=_map_platform(platform),
                            creative_type=crawled_ad.creative_type,
                            video_url=crawled_ad.video_url,
                            snapshot_url=crawled_ad.snapshot_url,
                            thumbnail_url=crawled_ad.thumbnail_url,
                            image_url=(
                                crawled_ad.image_urls[0]
                                if crawled_ad.image_urls else None
                            ),
                            image_s3_keys=(
                                {"urls": crawled_ad.image_urls}
                                if len(crawled_ad.image_urls) > 1 else None
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
                        saved += 1

                session.commit()
                result["total_saved"] += saved
                print(f"-> saved {saved} new")
                _flush()

            except Exception as db_err:
                session.rollback()
                err_msg = str(db_err)[:120]
                result["errors"].append(f"{kw_label}: DB error: {err_msg}")
                print(f"DB ERROR: {err_msg}")
                _flush()
            finally:
                session.close()

        except Exception as e:
            err_msg = str(e)[:120]
            result["errors"].append(f"{kw_label}: {err_msg}")
            print(f"ERROR: {err_msg}")
            _flush()

        # Rate-limit between keywords
        if kw_idx < len(keywords) - 1:
            time.sleep(SLEEP_BETWEEN_KEYWORDS)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    _patch_local_task_sessions()

    parser = argparse.ArgumentParser(
        description="Batch crawl Japanese market ads by genre"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--genre", type=str,
        help="Single genre key to crawl (e.g. beauty, finance)",
    )
    group.add_argument(
        "--all", action="store_true", default=True,
        help="Crawl all genres (default)",
    )
    group.add_argument(
        "--list", action="store_true",
        help="List available genres and exit",
    )
    parser.add_argument(
        "--limit", type=int, default=DEFAULT_LIMIT,
        help=f"Limit per platform per keyword (default: {DEFAULT_LIMIT})",
    )
    args = parser.parse_args()

    # --list mode
    if args.list:
        print()
        print("Available Japanese market genres:")
        print("-" * 60)
        for key, info in GENRE_KEYWORDS.items():
            kw_count = len(info.get("keywords", []))
            cat = info.get("category", "other")
            print(f"  {key:20s}  {info['label']:24s}  category={cat:12s}  keywords={kw_count}")
        print()
        return

    # Determine which genres to crawl
    if args.genre:
        if args.genre not in GENRE_KEYWORDS:
            print(f"ERROR: Unknown genre '{args.genre}'")
            print(f"Available: {', '.join(GENRE_KEYWORDS.keys())}")
            return
        genre_keys = [args.genre]
    else:
        genre_keys = list(GENRE_KEYWORDS.keys())

    # Check connected platforms
    from app.tasks.crawl_tasks import get_connected_platforms
    connected = get_connected_platforms()
    active = [p for p in PLATFORMS if p in connected]

    print()
    print("=" * 70)
    print("  JAPANESE MARKET BATCH CRAWL")
    print("=" * 70)
    print(f"  Connected platforms: {connected}")
    print(f"  Active platforms:    {active}")
    print(f"  Genres to crawl:     {len(genre_keys)}")
    print(f"  Limit per platform:  {args.limit}")
    total_kw = sum(len(GENRE_KEYWORDS[g]["keywords"]) for g in genre_keys)
    print(f"  Total keywords:      {total_kw}")
    print()
    _flush()

    if not active:
        print("ERROR: No platforms connected. Set Meta API token first.")
        print("  Go to Settings > API Keys in the web UI, or set META_ACCESS_TOKEN env var.")
        return

    # Crawl each genre
    all_results = []
    start_time = time.time()

    for gi, genre_key in enumerate(genre_keys):
        genre_info = GENRE_KEYWORDS[genre_key]
        label = genre_info["label"]
        kw_count = len(genre_info["keywords"])
        print(f"[Genre {gi + 1}/{len(genre_keys)}] {genre_key} ({label}, {kw_count} keywords)")
        print("-" * 50)

        genre_result = crawl_and_save_genre(
            genre_key, genre_info, active, args.limit
        )
        all_results.append(genre_result)
        print()
        _flush()

    elapsed = time.time() - start_time

    # Final summary
    print("=" * 70)
    print("  BATCH CRAWL COMPLETE")
    print("=" * 70)
    print()

    grand_found = 0
    grand_saved = 0
    grand_errors = 0
    for r in all_results:
        grand_found += r["total_found"]
        grand_saved += r["total_saved"]
        grand_errors += len(r["errors"])
        err_marker = f"  ({len(r['errors'])} errors)" if r["errors"] else ""
        print(
            f"  {r['genre_key']:20s}  found={r['total_found']:4d}  "
            f"saved={r['total_saved']:4d}{err_marker}"
        )

    print()
    print(f"  Total found:    {grand_found}")
    print(f"  Total saved:    {grand_saved}")
    print(f"  Total errors:   {grand_errors}")
    print(f"  Elapsed time:   {elapsed:.1f}s")
    print()

    # DB stats
    try:
        from app.models.ad import Ad

        session = _get_session()
        total_ads = session.query(Ad).count()
        session.close()
        print(f"  DB total ads:   {total_ads}")
    except Exception:
        pass

    # Print errors if any
    if grand_errors > 0:
        print()
        print("  Errors:")
        for r in all_results:
            for err in r["errors"]:
                print(f"    [{r['genre_key']}] {err}")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
