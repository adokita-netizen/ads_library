#!/usr/bin/env python3
"""Find and fix ads with missing key fields: creative_analysis, ranking_metrics, fine_genre.

For each field, reports before/after fill rates and applies rule-based fixes:
  1. creative_analysis -- generate from title keywords using the same approach
     as analyze_creative_elements.py (hook_type, cta_type, offer_type, emotion)
  2. ranking_metrics   -- compute from view_count, spend, like_count and
     estimated_metrics / metrics_history / current_deltas
  3. fine_genre        -- classify from title/advertiser using keyword matching
     via classify_fine_genre.py

Commits in batches for safety.  Prints before/after fill rates for each field.

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/fix_data_gaps.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# Re-use the full analysis logic from the existing creative-elements script
from scripts.analyze_creative_elements import analyze_ad
# Re-use the full genre classification logic
from scripts.classify_fine_genre import classify_fine_genre


# ---------------------------------------------------------------------------
# Ranking-metrics helpers (mirrors aggregate_metrics.py logic)
# ---------------------------------------------------------------------------

def _best_total_views(ad: Ad) -> int:
    """Pick the best total-views number from all available sources."""
    meta = ad.ad_metadata or {}
    # Priority 1: metrics_history (snapshot crawl)
    history = meta.get("metrics_history", [])
    if history and history[0].get("views", 0) > 0:
        return int(history[0]["views"])
    # Priority 2: estimated_metrics (from estimate_metrics.py)
    est = meta.get("estimated_metrics", {})
    if est.get("total_views", 0) > 0:
        return int(est["total_views"])
    # Priority 3: direct ad columns
    if ad.view_count and ad.view_count > 0:
        return int(ad.view_count)
    if ad.impressions and ad.impressions > 0:
        return int(ad.impressions)
    return 0


def _best_total_spend(ad: Ad) -> float:
    """Pick the best total-spend number from all available sources."""
    meta = ad.ad_metadata or {}
    history = meta.get("metrics_history", [])
    if history and history[0].get("spend_jpy", 0) > 0:
        return float(history[0]["spend_jpy"])
    est = meta.get("estimated_metrics", {})
    if est.get("estimated_total_spend_jpy", 0) > 0:
        return float(est["estimated_total_spend_jpy"])
    if ad.spend and ad.spend > 0:
        return float(ad.spend)
    return 0.0


def _best_total_likes(ad: Ad) -> int:
    """Pick the best total-likes number from all available sources."""
    meta = ad.ad_metadata or {}
    history = meta.get("metrics_history", [])
    if history and history[0].get("likes", 0) > 0:
        return int(history[0]["likes"])
    if ad.like_count and ad.like_count > 0:
        return int(ad.like_count)
    return 0


def _best_view_increase(ad: Ad) -> int:
    """Pick the best daily view-increase number."""
    meta = ad.ad_metadata or {}
    deltas = meta.get("current_deltas", {})
    if deltas.get("view_increase_daily", 0) > 0:
        return int(deltas["view_increase_daily"])
    est = meta.get("estimated_metrics", {})
    if est.get("view_increase_daily", 0) > 0:
        return int(est["view_increase_daily"])
    return 0


def _best_spend_increase(ad: Ad) -> float:
    """Pick the best daily spend-increase number."""
    meta = ad.ad_metadata or {}
    deltas = meta.get("current_deltas", {})
    if deltas.get("spend_increase_daily_jpy", 0) > 0:
        return float(deltas["spend_increase_daily_jpy"])
    est = meta.get("estimated_metrics", {})
    if est.get("spend_increase_daily_jpy", 0) > 0:
        return float(est["spend_increase_daily_jpy"])
    return 0.0


def _best_like_increase(ad: Ad) -> int:
    """Pick the best daily like-increase number."""
    meta = ad.ad_metadata or {}
    deltas = meta.get("current_deltas", {})
    if deltas.get("like_increase_daily", 0) > 0:
        return int(deltas["like_increase_daily"])
    est = meta.get("estimated_metrics", {})
    if est.get("like_increase_daily", 0) > 0:
        return int(est["like_increase_daily"])
    return 0


def compute_ranking_metrics(ad: Ad) -> dict:
    """Compute ranking_metrics dict from all available data sources."""
    return {
        "total_views": _best_total_views(ad),
        "view_increase": _best_view_increase(ad),
        "total_spend_jpy": round(_best_total_spend(ad), 2),
        "spend_increase_jpy": round(_best_spend_increase(ad), 2),
        "total_likes": _best_total_likes(ad),
        "like_increase": _best_like_increase(ad),
        "period": "daily",
        "aggregated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BATCH_SIZE = 200


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Fix Data Gaps Script")
    print("Executed at: %s" % datetime.now(timezone.utc).isoformat())
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print("\nTotal ads in database: %d" % total)

        if total == 0:
            print("No ads found. Exiting.")
            return

        # ── Measure BEFORE fill rates ──────────────────────────────
        before_creative = sum(
            1 for a in ads if (a.ad_metadata or {}).get("creative_analysis")
        )
        before_ranking = sum(
            1 for a in ads if (a.ad_metadata or {}).get("ranking_metrics")
        )
        before_genre = sum(
            1 for a in ads if (a.ad_metadata or {}).get("fine_genre_en")
        )

        print("\n--- BEFORE Fill Rates ---")
        print("  creative_analysis : %d/%d (%.1f%%)" % (
            before_creative, total, before_creative / total * 100 if total else 0))
        print("  ranking_metrics   : %d/%d (%.1f%%)" % (
            before_ranking, total, before_ranking / total * 100 if total else 0))
        print("  fine_genre        : %d/%d (%.1f%%)" % (
            before_genre, total, before_genre / total * 100 if total else 0))

        # ── Fix 1: Missing creative_analysis ───────────────────────
        print("\n--- Fix 1: Missing creative_analysis ---")
        creative_fixed = 0
        batch_count = 0

        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            if meta.get("creative_analysis"):
                continue

            analysis = analyze_ad(ad)
            meta["creative_analysis"] = analysis
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            creative_fixed += 1
            batch_count += 1

            if batch_count >= BATCH_SIZE:
                session.commit()
                batch_count = 0

        if batch_count > 0:
            session.commit()
            batch_count = 0

        print("  Fixed: %d ads" % creative_fixed)

        # ── Fix 2: Missing ranking_metrics ─────────────────────────
        print("\n--- Fix 2: Missing ranking_metrics ---")
        ranking_fixed = 0

        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            if meta.get("ranking_metrics"):
                continue

            ranking = compute_ranking_metrics(ad)
            meta["ranking_metrics"] = ranking
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            ranking_fixed += 1
            batch_count += 1

            if batch_count >= BATCH_SIZE:
                session.commit()
                batch_count = 0

        if batch_count > 0:
            session.commit()
            batch_count = 0

        print("  Fixed: %d ads" % ranking_fixed)

        # ── Fix 3: Missing fine_genre ──────────────────────────────
        print("\n--- Fix 3: Missing fine_genre ---")
        genre_fixed = 0

        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            if meta.get("fine_genre_en"):
                continue

            slug, jp_label = classify_fine_genre(ad)
            meta["fine_genre"] = jp_label
            meta["fine_genre_en"] = slug
            meta["fine_genre_classified_at"] = datetime.now(timezone.utc).isoformat()
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            genre_fixed += 1
            batch_count += 1

            if batch_count >= BATCH_SIZE:
                session.commit()
                batch_count = 0

        if batch_count > 0:
            session.commit()
            batch_count = 0

        print("  Fixed: %d ads" % genre_fixed)

        # ── Measure AFTER fill rates ───────────────────────────────
        after_creative = sum(
            1 for a in ads if (a.ad_metadata or {}).get("creative_analysis")
        )
        after_ranking = sum(
            1 for a in ads if (a.ad_metadata or {}).get("ranking_metrics")
        )
        after_genre = sum(
            1 for a in ads if (a.ad_metadata or {}).get("fine_genre_en")
        )

        print("\n--- AFTER Fill Rates ---")
        print("  creative_analysis : %d/%d (%.1f%%)" % (
            after_creative, total, after_creative / total * 100 if total else 0))
        print("  ranking_metrics   : %d/%d (%.1f%%)" % (
            after_ranking, total, after_ranking / total * 100 if total else 0))
        print("  fine_genre        : %d/%d (%.1f%%)" % (
            after_genre, total, after_genre / total * 100 if total else 0))

        # ── Summary ────────────────────────────────────────────────
        print("\n--- Summary ---")
        print("  creative_analysis : %d -> %d (fixed %d)" % (
            before_creative, after_creative, creative_fixed))
        print("  ranking_metrics   : %d -> %d (fixed %d)" % (
            before_ranking, after_ranking, ranking_fixed))
        print("  fine_genre        : %d -> %d (fixed %d)" % (
            before_genre, after_genre, genre_fixed))
        total_fixed = creative_fixed + ranking_fixed + genre_fixed
        print("  Total fields fixed: %d" % total_fixed)

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print("ERROR: %s" % e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
