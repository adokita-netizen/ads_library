"""
Recompute hit scores for all ads using multi-signal model (v2).

5 signals (delivery duration / spend / active bonus / creative quality / trend)
are used for scoring, updating ad_metadata and ProductRanking.

v2 changes: delivery days as top signal (0-40pts), audience/platforms removed,
            active bonus independent (0-20pts), spend threshold lowered

Run: cd C:/Users/ishit/ads_library/backend && python scripts/recompute_hit_scores.py
"""

import sys
import os

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import sync_session_scope
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics, ProductRanking
from app.services.ranking.ranking_service import compute_hit_score, compute_genre_stats

JST = timezone(timedelta(hours=9))


def main():
    print("=" * 60)
    print("Hit Score Recomputation Script (Multi-Signal Model)")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    with sync_session_scope() as session:
        ads = session.query(Ad).all()
        total_ads = len(ads)
        print(f"\nTotal ads: {total_ads}")

        if total_ads == 0:
            print("No ads found. Exiting.")
            return

        # Period: last 30 days
        yesterday = (datetime.now(JST) - timedelta(days=1)).date()
        period_start = yesterday - timedelta(days=29)
        period_end = yesterday
        print(f"Score calculation period: {period_start} -> {period_end}")

        # Pre-compute genre statistics
        print("\nComputing genre statistics...")
        genre_stats = compute_genre_stats(session, period_start, period_end)
        for g, s in genre_stats.items():
            print(f"  {g}: ads={s['ad_count']}, max_spend={s['max_spend']:.0f}")

        # Pre-fetch all ad metrics
        print("\nFetching metrics...")
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
        print(f"  {len(all_metrics)} metric rows fetched")

        # Track statistics
        hit_count = 0
        mega_hit_count = 0
        scores = []
        top_ads = []
        updated_count = 0

        print("\nComputing scores...")
        for ad in ads:
            # Get metrics and genre stats for this ad
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

            # Update ad_metadata with Agent C's keys only
            meta = dict(ad.ad_metadata or {})
            meta["latest_hit_score"] = score
            meta["latest_score_breakdown"] = breakdown
            meta["hit_level"] = hit_level
            meta["is_hit"] = is_hit
            meta["score_updated_at"] = datetime.now(timezone.utc).isoformat()
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated_count += 1

            if hit_level == "hit":
                hit_count += 1
            elif hit_level == "mega_hit":
                mega_hit_count += 1

            # Compute days_running for display
            days_running = meta.get("days_running", 0)
            if days_running == 0 and ad.first_seen_at:
                now = datetime.now(timezone.utc)
                first = ad.first_seen_at
                if first.tzinfo is None:
                    first = first.replace(tzinfo=timezone.utc)
                days_running = max(1, (now - first).days)

            top_ads.append({
                "id": ad.id,
                "title": (ad.title or "")[:50],
                "advertiser": (ad.advertiser_name or "")[:30],
                "score": score,
                "hit_level": hit_level,
                "days_running": days_running,
                "is_still_running": meta.get("is_still_running", ad.last_seen_at is None),
            })

        # Update ProductRanking records if they exist
        rankings_updated = 0
        rankings = session.query(ProductRanking).all()
        # Build a lookup from ad scores
        ad_scores = {ad["id"]: ad for ad in top_ads}
        for ranking in rankings:
            ad_info = ad_scores.get(ranking.ad_id)
            if ad_info:
                ranking.hit_score = ad_info["score"]
                ranking.is_hit = ad_info["hit_level"] in ("hit", "mega_hit")
                # Store hit_level and score_breakdown in extra_metadata
                ad_obj = session.query(Ad).get(ranking.ad_id)
                ad_meta = (ad_obj.ad_metadata or {}) if ad_obj else {}
                extra = dict(ranking.extra_metadata or {})
                extra["hit_level"] = ad_info["hit_level"]
                extra["score_breakdown"] = ad_meta.get("latest_score_breakdown", {})
                ranking.extra_metadata = extra
                flag_modified(ranking, "extra_metadata")
                rankings_updated += 1

        session.commit()

        # Sort top ads by score descending
        top_ads.sort(key=lambda x: x["score"], reverse=True)

        # Print statistics
        avg_score = sum(scores) / len(scores) if scores else 0
        print(f"\n{'=' * 60}")
        print("Statistics Summary")
        print(f"{'=' * 60}")
        print(f"  Total ads:              {total_ads}")
        print(f"  ad_metadata updated:    {updated_count}")
        print(f"  ProductRanking updated: {rankings_updated}")
        print(f"  Hit ads:                {hit_count}  (30+ days & score 45+)")
        print(f"  Mega-hit ads:           {mega_hit_count}  (60+ days & score 70+)")
        print(f"  Average hit score:      {avg_score:.1f}")
        print(f"  Max score:              {max(scores):.1f}")
        print(f"  Min score:              {min(scores):.1f}")

        print(f"\n{'=' * 60}")
        print("Top 10 Hit Ads")
        print(f"{'=' * 60}")
        for i, ad_info in enumerate(top_ads[:10], 1):
            still = "active" if ad_info["is_still_running"] else "stopped"
            level_label = {
                "mega_hit": "*** MEGA HIT",
                "hit": "** HIT",
                "none": "- normal",
            }.get(ad_info["hit_level"], "- normal")
            title_safe = ad_info['title'].encode('ascii', 'replace').decode('ascii')
            adv_safe = ad_info['advertiser'].encode('ascii', 'replace').decode('ascii')
            print(
                f"  {i:2d}. [ID:{ad_info['id']:>4d}] "
                f"score:{ad_info['score']:>5.1f}  "
                f"days:{ad_info['days_running']:>4d} ({still})  "
                f"{level_label}"
            )
            print(f"      {title_safe}")
            if adv_safe:
                print(f"      advertiser: {adv_safe}")

        # Distribution summary
        score_ranges = {
            "0-19": 0, "20-39": 0, "40-59": 0,
            "60-79": 0, "80-100": 0,
        }
        for s in scores:
            if s < 20:
                score_ranges["0-19"] += 1
            elif s < 40:
                score_ranges["20-39"] += 1
            elif s < 60:
                score_ranges["40-59"] += 1
            elif s < 80:
                score_ranges["60-79"] += 1
            else:
                score_ranges["80-100"] += 1

        print(f"\n{'=' * 60}")
        print("Score Distribution")
        print(f"{'=' * 60}")
        for range_label, count in score_ranges.items():
            bar = "#" * (count * 2)
            print(f"  {range_label:>7s}: {count:>3d} {bar}")

        print(f"\nDone!")


if __name__ == "__main__":
    main()
