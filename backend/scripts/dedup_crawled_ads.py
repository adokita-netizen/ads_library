#!/usr/bin/env python3
"""Deduplicate crawled ads.

Finds duplicate ads by:
  1. Same external_id (exact match)
  2. Same title + advertiser_name combination

For each group of duplicates:
  - Keeps the ad with the most data (highest completeness score)
  - Marks others with ad_metadata["is_duplicate"] = True
  - Links duplicates to the kept ad via ad_metadata["duplicate_of"] = kept_id

Prints a dedup report at the end.

Run from the backend directory:
    cd backend
    python scripts/dedup_crawled_ads.py
"""

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal, is_in_memory_mode
from app.models.ad import Ad


def _get_session() -> Session:
    """Get a DB session, connecting to vaap_local.db if SQLite fallback is active."""
    if not is_in_memory_mode():
        return SyncSessionLocal()
    db_path = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")
    if not os.path.exists(db_path):
        raise RuntimeError(f"vaap_local.db not found at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return sessionmaker(bind=engine)()


def compute_completeness(ad: Ad) -> int:
    """Compute a data completeness score for an ad. Higher = more data."""
    score = 0

    if ad.title:
        score += 10
    if ad.description:
        score += 8
    if ad.video_url:
        score += 15
    if ad.image_url:
        score += 10
    if ad.thumbnail_url:
        score += 5
    if ad.thumbnail_s3_key:
        score += 10
    if ad.image_s3_key:
        score += 10
    if ad.destination_url:
        score += 5
    if ad.advertiser_name:
        score += 5
    if ad.brand_name:
        score += 3
    if ad.duration_seconds:
        score += 3
    if ad.view_count:
        score += 3
    if ad.like_count:
        score += 2
    if ad.creative_type and ad.creative_type != "unknown":
        score += 3
    if ad.category:
        score += 3

    # Bonus for rich metadata
    meta = ad.ad_metadata or {}
    if meta.get("creative_analysis"):
        score += 5
    if meta.get("creative_quality"):
        score += 3

    return score


def find_duplicates_by_external_id(session) -> list[list[Ad]]:
    """Find groups of ads sharing the same external_id."""
    all_ads = session.query(Ad).filter(
        Ad.external_id.isnot(None),
        Ad.external_id != "",
    ).order_by(Ad.external_id).all()

    groups = defaultdict(list)
    for ad in all_ads:
        # Skip ads already marked as duplicate
        meta = ad.ad_metadata or {}
        if meta.get("is_duplicate"):
            continue
        groups[ad.external_id].append(ad)

    # Return only groups with duplicates (2+ ads)
    return [group for group in groups.values() if len(group) >= 2]


def find_duplicates_by_title_advertiser(session) -> list[list[Ad]]:
    """Find groups of ads sharing the same title + advertiser_name."""
    all_ads = session.query(Ad).filter(
        Ad.title.isnot(None),
        Ad.title != "",
        Ad.advertiser_name.isnot(None),
        Ad.advertiser_name != "",
    ).order_by(Ad.title).all()

    groups = defaultdict(list)
    for ad in all_ads:
        meta = ad.ad_metadata or {}
        if meta.get("is_duplicate"):
            continue
        key = (ad.title.strip().lower(), ad.advertiser_name.strip().lower())
        groups[key].append(ad)

    return [group for group in groups.values() if len(group) >= 2]


def mark_duplicates(session, dup_groups: list[list[Ad]], method: str) -> int:
    """Mark duplicates in each group. Keep the one with highest completeness.

    Returns count of ads marked as duplicate.
    """
    marked = 0

    for group in dup_groups:
        # Sort by completeness (descending), then by id (ascending = older = prefer)
        scored = [(compute_completeness(ad), -ad.id, ad) for ad in group]
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

        keeper = scored[0][2]
        duplicates = [item[2] for item in scored[1:]]

        for dup_ad in duplicates:
            meta = dict(dup_ad.ad_metadata or {})
            meta["is_duplicate"] = True
            meta["duplicate_of"] = keeper.id
            meta["dedup_method"] = method
            dup_ad.ad_metadata = meta
            flag_modified(dup_ad, "ad_metadata")
            marked += 1

    return marked


def main():
    session = _get_session()

    try:
        total_ads = session.query(Ad).count()
        print("=" * 60)
        print("AD DEDUPLICATION REPORT")
        print("=" * 60)
        print(f"Total ads in database: {total_ads}")
        print()

        # Count already-marked duplicates
        all_ads = session.query(Ad).all()
        already_dup = sum(1 for ad in all_ads
                          if (ad.ad_metadata or {}).get("is_duplicate"))
        print(f"Already marked as duplicate: {already_dup}")
        print()

        # Phase 1: Deduplicate by external_id
        print("--- Phase 1: Dedup by external_id ---")
        ext_id_groups = find_duplicates_by_external_id(session)
        print(f"Duplicate groups found (external_id): {len(ext_id_groups)}")

        if ext_id_groups:
            for i, group in enumerate(ext_id_groups[:10]):
                ext_id = group[0].external_id
                ids = [ad.id for ad in group]
                scores = [compute_completeness(ad) for ad in group]
                print(f"  Group {i+1}: external_id={ext_id}, "
                      f"ad_ids={ids}, scores={scores}")

            if len(ext_id_groups) > 10:
                print(f"  ... and {len(ext_id_groups) - 10} more groups")

        marked_ext = mark_duplicates(session, ext_id_groups, "external_id")
        print(f"Marked as duplicate (external_id): {marked_ext}")
        session.commit()
        print()

        # Phase 2: Deduplicate by title + advertiser
        print("--- Phase 2: Dedup by title + advertiser ---")
        title_groups = find_duplicates_by_title_advertiser(session)
        print(f"Duplicate groups found (title+advertiser): {len(title_groups)}")

        if title_groups:
            for i, group in enumerate(title_groups[:10]):
                title_preview = (group[0].title or "")[:50]
                adv = group[0].advertiser_name or "unknown"
                ids = [ad.id for ad in group]
                safe_title = title_preview.encode("unicode_escape").decode("ascii")
                safe_adv = adv.encode("unicode_escape").decode("ascii")
                print(f"  Group {i+1}: title={safe_title}..., "
                      f"advertiser={safe_adv}, ad_ids={ids}")

            if len(title_groups) > 10:
                print(f"  ... and {len(title_groups) - 10} more groups")

        marked_title = mark_duplicates(session, title_groups, "title_advertiser")
        print(f"Marked as duplicate (title+advertiser): {marked_title}")
        session.commit()
        print()

        # Summary
        total_marked = marked_ext + marked_title
        print("=" * 60)
        print("DEDUP SUMMARY")
        print("=" * 60)
        print(f"Total ads:                {total_ads}")
        print(f"Previously marked dup:    {already_dup}")
        print(f"Newly marked dup:         {total_marked}")
        print(f"  - by external_id:       {marked_ext}")
        print(f"  - by title+advertiser:  {marked_title}")
        print(f"Unique ads remaining:     {total_ads - already_dup - total_marked}")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        err_str = str(e).encode("unicode_escape").decode("ascii")
        print(f"FATAL ERROR: {err_str}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
