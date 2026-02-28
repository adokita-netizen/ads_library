#!/usr/bin/env python3
"""Market share analysis by advertiser and genre.

Calculates ad count share, estimated spend share, and hit ad share
per genre (fine_genre from ad_metadata). Identifies market leaders,
challengers, and niche players based on ranking position.

Output: backend/exports/market_share.json

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/analyze_market_share.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

HIT_LEVELS = ("hit", "mega_hit")


def _get_genre(ad):
    """Extract fine_genre from ad_metadata, defaulting to 'other'."""
    meta = ad.ad_metadata or {}
    return meta.get("fine_genre") or "other"


def _is_hit(ad):
    """Check whether the ad has hit_level of 'hit' or 'mega_hit'."""
    meta = ad.ad_metadata or {}
    return meta.get("hit_level") in HIT_LEVELS


def safe_pct(part, whole):
    """Calculate percentage safely, returning 0 when whole is 0."""
    return round(part / whole * 100, 1) if whole > 0 else 0.0


def _assign_role(rank):
    """Assign market role based on ranking position within a genre.

    rank 1        -> leader
    rank 2 or 3   -> challenger
    rank 4+       -> niche
    """
    if rank == 1:
        return "leader"
    elif rank <= 3:
        return "challenger"
    else:
        return "niche"


def main():
    print("=" * 60)
    print("Market Share Analysis")
    print("Generated at: {}".format(datetime.now(timezone.utc).isoformat()))
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print("\nTotal ads loaded: {}".format(total))

        if total == 0:
            print("No ads found. Exiting.")
            return

        # ----------------------------------------------------------
        # Phase 1: Aggregate data per genre x advertiser
        # ----------------------------------------------------------
        genre_adv = defaultdict(lambda: defaultdict(lambda: {
            "ad_count": 0,
            "spend": 0.0,
            "hit_count": 0,
        }))

        genre_totals = defaultdict(lambda: {
            "ad_count": 0,
            "spend": 0.0,
            "hit_count": 0,
        })

        for ad in ads:
            genre = _get_genre(ad)
            adv = ad.advertiser_name or "unknown"
            spend = ad.spend or 0.0
            hit = _is_hit(ad)

            genre_adv[genre][adv]["ad_count"] += 1
            genre_adv[genre][adv]["spend"] += spend
            if hit:
                genre_adv[genre][adv]["hit_count"] += 1

            genre_totals[genre]["ad_count"] += 1
            genre_totals[genre]["spend"] += spend
            if hit:
                genre_totals[genre]["hit_count"] += 1

        # ----------------------------------------------------------
        # Phase 2: Build per-genre market share with role assignment
        # ----------------------------------------------------------
        by_genre = {}

        for genre in sorted(genre_totals.keys()):
            gt = genre_totals[genre]
            advs = genre_adv[genre]

            # Build advertiser list sorted by ad_count descending
            adv_list = []
            for adv_name, data in advs.items():
                adv_list.append({
                    "name": adv_name,
                    "ad_count": data["ad_count"],
                    "spend": data["spend"],
                    "hit_count": data["hit_count"],
                })

            # Sort by ad_count descending, then by spend descending as tiebreaker
            adv_list.sort(key=lambda x: (x["ad_count"], x["spend"]), reverse=True)

            # Compute shares and assign roles based on rank
            advertisers_out = []
            for rank, entry in enumerate(adv_list, start=1):
                ad_share = safe_pct(entry["ad_count"], gt["ad_count"])
                spend_share = safe_pct(entry["spend"], gt["spend"])
                hit_share = safe_pct(entry["hit_count"], gt["hit_count"])
                role = _assign_role(rank)

                advertisers_out.append({
                    "name": entry["name"],
                    "ad_count": entry["ad_count"],
                    "ad_share": ad_share,
                    "spend_share": spend_share,
                    "hit_share": hit_share,
                    "role": role,
                })

            by_genre[genre] = {
                "total_ads": gt["ad_count"],
                "total_spend": round(gt["spend"], 2),
                "advertisers": advertisers_out,
            }

        # ----------------------------------------------------------
        # Phase 3: Print market share table per genre
        # ----------------------------------------------------------
        for genre in sorted(by_genre.keys()):
            gdata = by_genre[genre]
            if gdata["total_ads"] < 2:
                continue

            print("\n--- {} (total: {} ads, {} advertisers) ---".format(
                genre, gdata["total_ads"], len(gdata["advertisers"])))
            print("  {:<30s} {:>5s} {:>8s} {:>10s} {:>9s} {:>9s} {:<12s}".format(
                "Advertiser", "Ads", "AdShr%", "SpendShr%", "HitShr%", "Hits", "Role"))
            print("  {} {} {} {} {} {} {}".format(
                "-" * 30, "-" * 5, "-" * 8, "-" * 10, "-" * 9, "-" * 9, "-" * 12))

            for adv in gdata["advertisers"][:15]:
                name = adv["name"][:30]
                print("  {:<30s} {:>5d} {:>7.1f}% {:>9.1f}% {:>8.1f}% {:>9d} {:<12s}".format(
                    name,
                    adv["ad_count"],
                    adv["ad_share"],
                    adv["spend_share"],
                    adv["hit_share"],
                    adv.get("hit_count", 0) if "hit_count" in adv else 0,
                    adv["role"],
                ))

        # ----------------------------------------------------------
        # Phase 4: Overall leaders across all genres
        # ----------------------------------------------------------
        print("\n--- Overall Leaders (all genres) ---")

        all_advs = defaultdict(lambda: {
            "total_ads": 0,
            "total_spend": 0.0,
            "hit_count": 0,
            "genres": set(),
        })

        for ad in ads:
            adv = ad.advertiser_name or "unknown"
            genre = _get_genre(ad)
            all_advs[adv]["total_ads"] += 1
            all_advs[adv]["total_spend"] += ad.spend or 0.0
            if _is_hit(ad):
                all_advs[adv]["hit_count"] += 1
            all_advs[adv]["genres"].add(genre)

        # Sort by total_ads descending
        top_advs = sorted(all_advs.items(), key=lambda x: x[1]["total_ads"], reverse=True)

        overall_leaders = []
        for adv_name, data in top_advs[:20]:
            ad_share = safe_pct(data["total_ads"], total)
            print("  {:<35s} ads={:>4d} ({:>5.1f}%) hits={:>3d} spend={:>10.0f} genres={}".format(
                adv_name[:35],
                data["total_ads"],
                ad_share,
                data["hit_count"],
                data["total_spend"],
                len(data["genres"]),
            ))
            overall_leaders.append({
                "name": adv_name,
                "total_ads": data["total_ads"],
                "genres": sorted(data["genres"]),
                "total_spend": round(data["total_spend"], 2),
            })

        # ----------------------------------------------------------
        # Phase 5: Export to JSON
        # ----------------------------------------------------------
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports"
        )
        os.makedirs(export_dir, exist_ok=True)

        # Remove internal hit_count from advertiser entries before export
        # (not part of the output spec)
        export_by_genre = {}
        for genre, gdata in by_genre.items():
            clean_advs = []
            for adv in gdata["advertisers"]:
                clean_advs.append({
                    "name": adv["name"],
                    "ad_count": adv["ad_count"],
                    "ad_share": adv["ad_share"],
                    "spend_share": adv["spend_share"],
                    "hit_share": adv["hit_share"],
                    "role": adv["role"],
                })
            export_by_genre[genre] = {
                "total_ads": gdata["total_ads"],
                "total_spend": gdata["total_spend"],
                "advertisers": clean_advs,
            }

        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "by_genre": export_by_genre,
            "overall_leaders": overall_leaders,
        }

        out_path = os.path.join(export_dir, "market_share.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)

        print("\nExported to: {}".format(out_path))
        print("Genres analyzed: {}".format(len(by_genre)))
        print("Done.")

    except Exception as e:
        print("ERROR: {}".format(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
