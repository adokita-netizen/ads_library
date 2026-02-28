#!/usr/bin/env python3
"""Auto-scoring for new/unscored ads. Idempotent - safe to run multiple times.

Finds ads where hit_score is NULL or 0, then:
  1. Runs creative_analysis if missing
  2. Computes longevity_class if missing
  3. Computes hit_score using v2 multi-signal model

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/score_new_ads.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics, ProductRanking
from app.services.ranking.ranking_service import compute_hit_score, compute_genre_stats
from scripts.analyze_creative_elements import analyze_ad

JST = timezone(timedelta(hours=9))


def _classify_longevity(days: int) -> str:
    if days >= 91:
        return "long"
    elif days >= 31:
        return "medium"
    elif days >= 8:
        return "short"
    else:
        return "flash"


def main() -> None:
    print("=" * 60)
    print("AUTO-SCORING FOR NEW ADS")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        all_ads = session.query(Ad).all()
        total = len(all_ads)
        print(f"Total ads in database: {total}")

        # Find ads that need scoring
        needs_scoring = []
        for ad in all_ads:
            meta = ad.ad_metadata or {}
            score = meta.get("latest_hit_score")
            if score is None or score == 0:
                needs_scoring.append(ad)

        print(f"Ads needing scoring: {len(needs_scoring)}")

        if not needs_scoring:
            print("All ads already have hit_scores. Nothing to do.")
            return

        now = datetime.now(timezone.utc)
        creative_added = 0
        longevity_added = 0

        # Step 1: Fill creative_analysis if missing
        print(f"\n--- Step 1: Creative Analysis ---")
        for ad in needs_scoring:
            meta = dict(ad.ad_metadata or {})
            if not meta.get("creative_analysis"):
                analysis = analyze_ad(ad)
                meta["creative_analysis"] = analysis
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                creative_added += 1
        session.commit()
        print(f"  Newly analyzed: {creative_added}")

        # Step 2: Fill longevity_class if missing
        print(f"\n--- Step 2: Longevity Class ---")
        for ad in needs_scoring:
            meta = dict(ad.ad_metadata or {})
            if not meta.get("longevity_class"):
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
                longevity_added += 1
        session.commit()
        print(f"  Newly classified: {longevity_added}")

        # Step 3: Compute hit_score
        print(f"\n--- Step 3: Compute Hit Scores ---")
        # Re-fetch to get updated metadata
        needs_scoring_ids = [ad.id for ad in needs_scoring]
        needs_scoring = session.query(Ad).filter(Ad.id.in_(needs_scoring_ids)).all()

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

        scored = 0
        hit_count = 0
        mega_hit_count = 0

        for ad in needs_scoring:
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

            meta = dict(ad.ad_metadata or {})
            meta["latest_hit_score"] = score
            meta["latest_score_breakdown"] = breakdown
            meta["hit_level"] = hit_level
            meta["is_hit"] = is_hit
            meta["score_updated_at"] = now.isoformat()
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            scored += 1
            if hit_level == "hit":
                hit_count += 1
            elif hit_level == "mega_hit":
                mega_hit_count += 1

            title_safe = (ad.title or "")[:40].encode("ascii", "replace").decode("ascii")
            print(f"    [ID:{ad.id:>4d}] score={score:.1f} level={hit_level} - {title_safe}")

        session.commit()

        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Ads processed:       {len(needs_scoring)}")
        print(f"  Creative analysis:   {creative_added} added")
        print(f"  Longevity class:     {longevity_added} added")
        print(f"  Hit scores computed: {scored}")
        print(f"  Hit: {hit_count}, Mega-hit: {mega_hit_count}")

        # Verify
        remaining = sum(
            1 for ad in session.query(Ad).all()
            if (ad.ad_metadata or {}).get("latest_hit_score") in (None, 0)
        )
        print(f"  Remaining unscored:  {remaining}")

        if remaining == 0:
            print("  All ads now have hit_scores!")

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
