"""Update media_extraction_status for all ads based on actual media availability.

Recomputes D96 creative-library recovery metadata:
- `media_extraction_status`
- `media_completeness_score`
- `downloadable` / `viewable` / `has_lp`
- `media_access_tier` (`viewable_only`, `downloadable`, `downloadable_with_lp`, ...)
- `media_quality_issues` for snapshot-only / missing states

Run from the backend directory:
    cd backend
    python scripts/update_media_status.py
"""

import os
import sys

sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal, is_in_memory_mode
from app.models.ad import Ad, normalize_creative_fetch_reason


def _get_session() -> Session:
    """Get a DB session, connecting to vaap_local.db if SQLite fallback is active."""
    if not is_in_memory_mode():
        return SyncSessionLocal()
    db_path = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")
    if not os.path.exists(db_path):
        raise RuntimeError(f"vaap_local.db not found at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return sessionmaker(bind=engine)()


# ── Helpers ────────────────────────────────────────────────────────


def _compute_completeness_score(ad: Ad) -> int:
    """Compute a 0-100 media completeness score for an ad."""
    score = 0
    if ad.video_url or ad.video_s3_key or ad.s3_key:
        score += 35
    if ad.image_url or ad.image_s3_key:
        score += 30
    if ad.thumbnail_url or ad.thumbnail_s3_key:
        score += 20
    if ad.snapshot_url:
        score += 10
    if ad.destination_url:
        score += 5
    return min(score, 100)


def _is_downloadable(ad: Ad) -> bool:
    return bool(ad.video_s3_key or ad.s3_key or ad.image_s3_key or ad.thumbnail_s3_key)


def _is_viewable(ad: Ad) -> bool:
    return bool(ad.video_url or ad.image_url or ad.thumbnail_url)


def _has_lp(ad: Ad) -> bool:
    meta = ad.ad_metadata or {}
    lp_info = meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}
    return bool(ad.destination_url or lp_info.get("final_url"))


def _access_tier(ad: Ad) -> str:
    if _is_downloadable(ad):
        return "downloadable_with_lp" if _has_lp(ad) else "downloadable"
    if _is_viewable(ad):
        return "viewable_only"
    if ad.snapshot_url:
        return "snapshot_only"
    return "missing"


def _quality_issues(ad: Ad) -> list[str]:
    issues: list[str] = []
    if _access_tier(ad) == "snapshot_only":
        issues.append("snapshot_only")
    elif _access_tier(ad) == "missing":
        issues.append("media_missing")
    if _is_viewable(ad) and not _is_downloadable(ad):
        issues.append("not_downloadable")
    return issues


def _determine_status(ad: Ad) -> str:
    """Determine the correct media_extraction_status for an ad.

    Logic:
    - If ad_metadata contains extraction_error -> "failed"
    - downloadable な S3/local 対応素材があれば -> "completed"
    - viewable だが downloadable でなければ -> "enriched"
    - snapshot のみあれば -> "pending_heavy"
    - 何も無ければ -> "pending"
    """
    meta = ad.ad_metadata or {}
    reason = normalize_creative_fetch_reason(meta.get("creative_fetch_reason"))

    # Check for previous extraction errors in metadata
    if meta.get("extraction_error") or meta.get("media_extraction_error"):
        return "failed"
    if reason in {"blocked_or_expired", "download_failed"} and not _is_viewable(ad) and not ad.snapshot_url:
        return "failed"

    if _is_downloadable(ad):
        return "completed"
    if _is_viewable(ad):
        return "enriched"
    if ad.snapshot_url:
        return "pending_heavy"
    return "pending"


# ── Main ──────────────────────────────────────────────────────────


def main():
    session = _get_session()
    try:
        all_ads = session.query(Ad).all()
        total = len(all_ads)
        print(f"Total ads: {total}")
        print()

        # Current status distribution
        status_before = {}
        for ad in all_ads:
            st = ad.media_extraction_status or "null"
            status_before[st] = status_before.get(st, 0) + 1

        print("BEFORE - media_extraction_status distribution:")
        for st, count in sorted(status_before.items()):
            print(f"  {st}: {count}")
        print()

        # Process all ads
        stats = {"completed": 0, "enriched": 0, "pending": 0, "pending_heavy": 0, "failed": 0}
        updated_count = 0

        for i, ad in enumerate(all_ads):
            new_status = _determine_status(ad)
            completeness = _compute_completeness_score(ad)

            stats[new_status] = stats.get(new_status, 0) + 1

            changed = False

            # Update the column
            if ad.media_extraction_status != new_status:
                ad.media_extraction_status = new_status
                changed = True

            # Update ad_metadata
            meta = dict(ad.ad_metadata or {})
            old_meta_status = meta.get("media_extraction_status")
            old_meta_score = meta.get("media_completeness_score")
            old_access_tier = meta.get("media_access_tier")
            issues = _quality_issues(ad)
            old_issues = meta.get("media_quality_issues")

            if (
                old_meta_status != new_status
                or old_meta_score != completeness
                or old_access_tier != _access_tier(ad)
                or old_issues != issues
            ):
                meta["media_extraction_status"] = new_status
                meta["media_completeness_score"] = completeness
                meta["downloadable"] = _is_downloadable(ad)
                meta["viewable"] = _is_viewable(ad)
                meta["has_lp"] = _has_lp(ad)
                meta["media_access_tier"] = _access_tier(ad)
                meta["media_quality_issues"] = issues
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                changed = True

            if changed:
                updated_count += 1

            # Batch commit every 50 records
            if (i + 1) % 50 == 0:
                session.commit()
                print(f"  Processed {i + 1}/{total}...")

        session.commit()

        # After distribution
        status_after = {}
        for ad in all_ads:
            st = ad.media_extraction_status or "null"
            status_after[st] = status_after.get(st, 0) + 1

        print()
        print("=" * 60)
        print("MEDIA STATUS UPDATE RESULTS")
        print("=" * 60)
        print(f"Total ads processed:  {total}")
        print(f"Records updated:      {updated_count}")
        print()
        print("AFTER - media_extraction_status distribution:")
        for st, count in sorted(status_after.items()):
            print(f"  {st}: {count}")
        print()
        print("Status breakdown:")
        print(f"  completed: {stats.get('completed', 0)}")
        print(f"  enriched:  {stats.get('enriched', 0)}")
        print(f"  pending:   {stats.get('pending', 0)}")
        print(f"  p_heavy:   {stats.get('pending_heavy', 0)}")
        print(f"  failed:    {stats.get('failed', 0)}")

        # Also print completeness score distribution
        score_buckets = {"0-25": 0, "26-50": 0, "51-75": 0, "76-100": 0}
        for ad in all_ads:
            score = _compute_completeness_score(ad)
            if score <= 25:
                score_buckets["0-25"] += 1
            elif score <= 50:
                score_buckets["26-50"] += 1
            elif score <= 75:
                score_buckets["51-75"] += 1
            else:
                score_buckets["76-100"] += 1

        print()
        print("Completeness score distribution:")
        for bucket, count in score_buckets.items():
            print(f"  {bucket}: {count}")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
