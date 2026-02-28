#!/usr/bin/env python3
"""Production data fixer: ensure ALL ads have complete data.

Runs all fixes in one script:
  1. Fill NULL first_seen_at (set to created_at)
  2. Fill NULL last_seen_at
  3. Fill NULL longevity_class
  4. Run creative_analysis on ads missing it
  5. Fill NULL hit_scores (recompute with scoring v2)
  6. Verify ad_metadata is valid JSON
  7. Set media_status based on actual cached files in media_cache/
  8. Print completeness summary

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/production_data_fix.py
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics, ProductRanking
from app.services.ranking.ranking_service import compute_hit_score, compute_genre_stats
from scripts.analyze_creative_elements import analyze_ad

JST = timezone(timedelta(hours=9))

MEDIA_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "media_cache",
)


def _classify_longevity(days: int) -> str:
    if days >= 91:
        return "long"
    elif days >= 31:
        return "medium"
    elif days >= 8:
        return "short"
    else:
        return "flash"


def _scan_media_cache() -> dict[str, set[str]]:
    """Scan media_cache/ directories and return sets of ad IDs that have cached files."""
    result: dict[str, set[str]] = {}
    for subdir in ["thumbnails", "images", "videos"]:
        dirpath = os.path.join(MEDIA_CACHE_DIR, subdir)
        if os.path.isdir(dirpath):
            files = set()
            for f in os.listdir(dirpath):
                # Extract ad ID from filename (e.g., "123.jpg" -> "123")
                name = Path(f).stem
                files.add(name)
            result[subdir] = files
        else:
            result[subdir] = set()
    return result


def main() -> None:
    print("=" * 60)
    print("PRODUCTION DATA FIXER")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"Total ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        now = datetime.now(timezone.utc)

        # ── Fix 1: NULL first_seen_at ───────────────────────────────
        print(f"\n--- Fix 1: NULL first_seen_at ---")
        first_seen_fixed = 0
        for ad in ads:
            if ad.first_seen_at is None:
                ad.first_seen_at = ad.created_at or now
                first_seen_fixed += 1
        session.commit()
        print(f"  Fixed: {first_seen_fixed}")

        # ── Fix 2: NULL last_seen_at ────────────────────────────────
        print(f"\n--- Fix 2: NULL last_seen_at ---")
        last_seen_fixed = 0
        for ad in ads:
            if ad.last_seen_at is None:
                meta = ad.ad_metadata or {}
                is_running = meta.get("is_still_running")
                if is_running is True:
                    ad.last_seen_at = now
                elif is_running is False and meta.get("survival_checked_at"):
                    try:
                        ad.last_seen_at = datetime.fromisoformat(
                            meta["survival_checked_at"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        ad.last_seen_at = ad.created_at or now
                else:
                    ad.last_seen_at = ad.created_at or now
                last_seen_fixed += 1
        session.commit()
        print(f"  Fixed: {last_seen_fixed}")

        # ── Fix 3: NULL longevity_class ─────────────────────────────
        print(f"\n--- Fix 3: NULL longevity_class ---")
        longevity_fixed = 0
        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            if meta.get("longevity_class"):
                continue

            days = meta.get("days_running")
            if days is None:
                if ad.first_seen_at:
                    first = ad.first_seen_at
                    if first.tzinfo is None:
                        first = first.replace(tzinfo=timezone.utc)
                    end = ad.last_seen_at or now
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                    days = max(1, (end - first).days)
                else:
                    days = 1
                meta["days_running"] = days

            meta["longevity_class"] = _classify_longevity(days)
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            longevity_fixed += 1

        session.commit()
        print(f"  Fixed: {longevity_fixed}")

        # ── Fix 4: Missing creative_analysis ────────────────────────
        print(f"\n--- Fix 4: Missing creative_analysis ---")
        creative_fixed = 0
        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            if meta.get("creative_analysis"):
                continue

            analysis = analyze_ad(ad)
            meta["creative_analysis"] = analysis
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            creative_fixed += 1

        session.commit()
        print(f"  Fixed: {creative_fixed}")

        # ── Fix 5: Recompute ALL hit_scores ─────────────────────────
        print(f"\n--- Fix 5: Recompute hit_scores (ALL ads) ---")
        # Re-fetch ads with updated metadata
        ads = session.query(Ad).all()

        yesterday = (datetime.now(JST) - timedelta(days=1)).date()
        period_start = yesterday - timedelta(days=29)
        period_end = yesterday

        genre_stats = compute_genre_stats(session, period_start, period_end)

        all_metrics = (
            session.query(AdDailyMetrics)
            .filter(
                AdDailyMetrics.metric_date >= period_start,
                AdDailyMetrics.metric_date <= period_end,
            )
            .order_by(AdDailyMetrics.metric_date)
            .all()
        )
        ad_metrics_map: dict[int, list] = {}
        for m in all_metrics:
            ad_metrics_map.setdefault(m.ad_id, []).append(m)

        hit_count = 0
        mega_hit_count = 0
        scores = []

        for ad in ads:
            ad_metrics = ad_metrics_map.get(ad.id, [])
            genre = None
            if ad_metrics:
                genre = ad_metrics[0].genre
            if not genre and ad.category:
                genre = str(ad.category.value)
            genre = genre or "other"
            g_stats = genre_stats.get(genre, {})

            score, is_hit, hit_level, breakdown = compute_hit_score(
                ad, metrics=ad_metrics, genre_stats=g_stats,
            )
            scores.append(score)

            meta = dict(ad.ad_metadata or {})
            meta["latest_hit_score"] = score
            meta["latest_score_breakdown"] = breakdown
            meta["hit_level"] = hit_level
            meta["is_hit"] = is_hit
            meta["score_updated_at"] = now.isoformat()
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            if hit_level == "hit":
                hit_count += 1
            elif hit_level == "mega_hit":
                mega_hit_count += 1

        # Update ProductRanking
        rankings = session.query(ProductRanking).all()
        ad_score_map = {ad.id: ad for ad in ads}
        rankings_updated = 0
        for ranking in rankings:
            ad_obj = ad_score_map.get(ranking.ad_id)
            if ad_obj:
                ad_meta = ad_obj.ad_metadata or {}
                ranking.hit_score = ad_meta.get("latest_hit_score", 0)
                ranking.is_hit = ad_meta.get("hit_level") in ("hit", "mega_hit")
                extra = dict(ranking.extra_metadata or {})
                extra["hit_level"] = ad_meta.get("hit_level")
                extra["score_breakdown"] = ad_meta.get("latest_score_breakdown", {})
                ranking.extra_metadata = extra
                flag_modified(ranking, "extra_metadata")
                rankings_updated += 1

        session.commit()
        avg_score = sum(scores) / len(scores) if scores else 0
        print(f"  Scored: {total}, Hit: {hit_count}, Mega-hit: {mega_hit_count}")
        print(f"  Avg: {avg_score:.1f}, Max: {max(scores):.1f}, Min: {min(scores):.1f}")
        print(f"  ProductRanking updated: {rankings_updated}")

        # ── Fix 6: Verify ad_metadata JSON validity ─────────────────
        print(f"\n--- Fix 6: Verify ad_metadata JSON validity ---")
        # Re-fetch after all updates
        ads = session.query(Ad).all()
        invalid_json = 0
        fixed_json = 0
        for ad in ads:
            if ad.ad_metadata is None:
                ad.ad_metadata = {}
                flag_modified(ad, "ad_metadata")
                fixed_json += 1
                continue
            try:
                # Verify it's a valid dict
                if not isinstance(ad.ad_metadata, dict):
                    json.loads(json.dumps(ad.ad_metadata))
                    invalid_json += 1
            except (TypeError, json.JSONDecodeError):
                ad.ad_metadata = {}
                flag_modified(ad, "ad_metadata")
                fixed_json += 1
                invalid_json += 1

        session.commit()
        print(f"  Invalid JSON: {invalid_json}, Fixed: {fixed_json}")

        # ── Fix 7: Set media_status from cached files ───────────────
        print(f"\n--- Fix 7: Media cache status ---")
        media_cache = _scan_media_cache()
        print(f"  Cached thumbnails: {len(media_cache['thumbnails'])}")
        print(f"  Cached images: {len(media_cache['images'])}")
        print(f"  Cached videos: {len(media_cache['videos'])}")

        media_updated = 0
        has_thumb = 0
        has_image = 0
        has_video = 0

        for ad in ads:
            ad_id_str = str(ad.id)
            cached_thumb = ad_id_str in media_cache["thumbnails"]
            cached_image = ad_id_str in media_cache["images"]
            cached_video = ad_id_str in media_cache["videos"]

            if cached_thumb:
                has_thumb += 1
            if cached_image:
                has_image += 1
            if cached_video:
                has_video += 1

            meta = dict(ad.ad_metadata or {})
            media_status = meta.get("media_cache_status", {})
            new_status = {
                "has_cached_thumbnail": cached_thumb,
                "has_cached_image": cached_image,
                "has_cached_video": cached_video,
                "checked_at": now.isoformat(),
            }

            if media_status != new_status:
                meta["media_cache_status"] = new_status
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                media_updated += 1

        session.commit()
        print(f"  Ads with cached thumbnail: {has_thumb}/{total}")
        print(f"  Ads with cached image: {has_image}/{total}")
        print(f"  Ads with cached video: {has_video}/{total}")
        print(f"  Media status updated: {media_updated}")

        # ── Final completeness check ────────────────────────────────
        print(f"\n{'=' * 60}")
        print("COMPLETENESS CHECK")
        print(f"{'=' * 60}")

        ads = session.query(Ad).all()
        complete = 0
        checks = {
            "title": 0,
            "description": 0,
            "category": 0,
            "creative_type": 0,
            "first_seen_at": 0,
            "last_seen_at": 0,
            "hit_score": 0,
            "longevity_class": 0,
            "creative_analysis": 0,
        }

        for ad in ads:
            meta = ad.ad_metadata or {}
            ok = True

            if ad.title:
                checks["title"] += 1
            else:
                ok = False
            if ad.description:
                checks["description"] += 1
            else:
                ok = False
            if ad.category:
                checks["category"] += 1
            else:
                ok = False
            if ad.creative_type:
                checks["creative_type"] += 1
            else:
                ok = False
            if ad.first_seen_at:
                checks["first_seen_at"] += 1
            else:
                ok = False
            if ad.last_seen_at:
                checks["last_seen_at"] += 1
            else:
                ok = False
            if meta.get("latest_hit_score") is not None:
                checks["hit_score"] += 1
            else:
                ok = False
            if meta.get("longevity_class"):
                checks["longevity_class"] += 1
            else:
                ok = False
            if meta.get("creative_analysis"):
                checks["creative_analysis"] += 1
            else:
                ok = False

            if ok:
                complete += 1

        print(f"\n  Field completeness:")
        for field, count in checks.items():
            pct = count / total * 100 if total > 0 else 0
            status = "OK" if count == total else "INCOMPLETE"
            print(f"    {field:<22s} {count:>5d}/{total} ({pct:>5.1f}%) {status}")

        pct_complete = complete / total * 100 if total > 0 else 0
        print(f"\n  {complete}/{total} ads fully complete ({pct_complete:.1f}% data quality)")

        if complete == total:
            print("  ALL ADS ARE FULLY COMPLETE!")
        else:
            print(f"  {total - complete} ads need attention.")

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
