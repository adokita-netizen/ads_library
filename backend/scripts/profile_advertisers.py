#!/usr/bin/env python3
"""Advertiser profiler: build per-advertiser analytics.

Groups ads by advertiser_name and computes:
  - total_ads, hit_ads, hit_rate
  - avg_score, max_score
  - dominant_genre, dominant_hook, dominant_cta
  - creative_types distribution (video vs image)
  - avg_longevity (how long their ads run)
  - active_ads_count (currently running)

Stores profile in ad_metadata["advertiser_profile"] for each ad.
Exports to backend/exports/advertiser_profiles.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/profile_advertisers.py
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)


def _get_score(ad: Ad) -> float:
    """Get hit score from ad_metadata, default 0."""
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_hit(ad: Ad) -> bool:
    """Check if ad is a hit or mega_hit."""
    return (ad.ad_metadata or {}).get("hit_level", "none") in ("hit", "mega_hit")


def _most_common(items: list[str]) -> str:
    """Return most common item, or 'none' if empty."""
    if not items:
        return "none"
    counter = Counter(items)
    return counter.most_common(1)[0][0]


def _safe_mean(values: list[float]) -> float:
    """Return mean or 0 if empty."""
    return round(mean(values), 1) if values else 0.0


def build_advertiser_profile(advertiser: str, ads: list[Ad]) -> dict:
    """Build a profile dict for one advertiser."""
    total_ads = len(ads)
    hit_ads = sum(1 for a in ads if _is_hit(a))
    hit_rate = round(hit_ads / total_ads * 100, 1) if total_ads > 0 else 0.0
    scores = [_get_score(a) for a in ads]

    # Genre from category
    genres = [
        str(a.category.value) for a in ads
        if a.category is not None
    ]

    # Hook/CTA from creative_analysis
    hooks = []
    ctas = []
    for a in ads:
        ca = (a.ad_metadata or {}).get("creative_analysis", {})
        if ca.get("hook_type") and ca["hook_type"] != "none":
            hooks.append(ca["hook_type"])
        if ca.get("cta_type") and ca["cta_type"] != "none":
            ctas.append(ca["cta_type"])

    # Creative type distribution
    creative_types = Counter(a.creative_type or "unknown" for a in ads)

    # Longevity
    days_list = []
    for a in ads:
        days = (a.ad_metadata or {}).get("days_running")
        if days is not None:
            try:
                days_list.append(int(days))
            except (ValueError, TypeError):
                pass

    # Active ads
    active = sum(
        1 for a in ads
        if (a.ad_metadata or {}).get("is_still_running") is True
    )

    # Platform distribution
    platforms = Counter(
        a.platform.value if a.platform else "unknown"
        for a in ads
    )

    return {
        "advertiser_name": advertiser,
        "total_ads": total_ads,
        "hit_ads": hit_ads,
        "hit_rate": hit_rate,
        "avg_score": _safe_mean(scores),
        "max_score": round(max(scores), 1) if scores else 0.0,
        "dominant_genre": _most_common(genres),
        "dominant_hook": _most_common(hooks),
        "dominant_cta": _most_common(ctas),
        "creative_types": dict(creative_types.most_common()),
        "avg_longevity_days": _safe_mean([float(d) for d in days_list]),
        "active_ads_count": active,
        "platforms": dict(platforms.most_common()),
        "profiled_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    print("=" * 60)
    print("ADVERTISER PROFILER")
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

        # Group by advertiser_name
        advertiser_groups: dict[str, list[Ad]] = {}
        no_advertiser = 0
        for ad in ads:
            name = ad.advertiser_name
            if not name or name.strip() == "":
                no_advertiser += 1
                continue
            advertiser_groups.setdefault(name, []).append(ad)

        print(f"Unique advertisers: {len(advertiser_groups)}")
        print(f"Ads without advertiser_name: {no_advertiser}")

        # Build profiles
        profiles = {}
        for advertiser, group_ads in advertiser_groups.items():
            profile = build_advertiser_profile(advertiser, group_ads)
            profiles[advertiser] = profile

        # Sort by total_ads descending
        sorted_advertisers = sorted(
            profiles.values(),
            key=lambda p: p["total_ads"],
            reverse=True,
        )

        # Store in ad_metadata
        print(f"\nStoring profiles in ad_metadata...")
        updated = 0
        for ad in ads:
            name = ad.advertiser_name
            if name and name in profiles:
                meta = dict(ad.ad_metadata or {})
                meta["advertiser_profile"] = profiles[name]
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                updated += 1

        session.commit()
        print(f"  Updated {updated} ads with advertiser_profile")

        # Export to JSON
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        export_path = os.path.join(EXPORTS_DIR, "advertiser_profiles.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(sorted_advertisers, f, ensure_ascii=False, indent=2)
        print(f"  Exported to: {export_path}")

        # Print top advertisers
        print(f"\n{'=' * 60}")
        print("TOP 15 ADVERTISERS BY AD COUNT")
        print(f"{'=' * 60}")
        print(f"  {'#':>2s} {'Advertiser':<30s} {'Ads':>4s} {'Hits':>4s} {'Rate':>6s} {'AvgSc':>6s} {'Active':>6s}")
        print(f"  {'-' * 70}")

        for i, p in enumerate(sorted_advertisers[:15], 1):
            name_safe = p["advertiser_name"][:28].encode("ascii", "replace").decode("ascii")
            print(
                f"  {i:>2d} {name_safe:<30s} "
                f"{p['total_ads']:>4d} {p['hit_ads']:>4d} "
                f"{p['hit_rate']:>5.1f}% {p['avg_score']:>5.1f} "
                f"{p['active_ads_count']:>6d}"
            )

        # Top by hit rate (min 3 ads)
        top_by_hit_rate = sorted(
            [p for p in sorted_advertisers if p["total_ads"] >= 3],
            key=lambda p: p["hit_rate"],
            reverse=True,
        )

        print(f"\n{'=' * 60}")
        print("TOP 10 ADVERTISERS BY HIT RATE (min 3 ads)")
        print(f"{'=' * 60}")
        for i, p in enumerate(top_by_hit_rate[:10], 1):
            name_safe = p["advertiser_name"][:28].encode("ascii", "replace").decode("ascii")
            print(
                f"  {i:>2d} {name_safe:<30s} "
                f"ads={p['total_ads']:>3d} "
                f"hit_rate={p['hit_rate']:>5.1f}% "
                f"avg_score={p['avg_score']:>5.1f}"
            )

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
