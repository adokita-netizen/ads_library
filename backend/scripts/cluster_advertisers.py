#!/usr/bin/env python3
"""Advertiser clustering by behavior patterns.

Groups advertisers into 4 behavioral clusters:
  1. Heavy hitters:      many ads (>= 5), high average score (>= 40)
  2. Niche specialists:  few genres (<= 2), high hit rate (>= 40%)
  3. Spray and pray:     many genres (>= 3), low hit rate (< 30%)
  4. Rising stars:       recent ads (first_seen_at in last 30 days), improving scores
  Fallback: "other"

Priority: Heavy hitter > Niche specialist > Spray and pray > Rising star > other

Output: exports/advertiser_clusters.json
Format: {"clusters": {"heavy_hitters": [...], ...}, "summary": {...}}

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/cluster_advertisers.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_score(ad: Ad) -> float:
    """Get hit score from ad_metadata, default 0."""
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_hit(ad: Ad) -> bool:
    """Check if ad is a hit or mega_hit."""
    return (ad.ad_metadata or {}).get("hit_level", "none") in ("hit", "mega_hit")


def _get_genre(ad: Ad) -> str:
    """Get fine_genre_en from ad_metadata, falling back to category."""
    meta = ad.ad_metadata or {}
    fg = meta.get("fine_genre_en")
    if fg and fg != "other":
        return fg
    if ad.category:
        return ad.category.value
    return "unknown"


def _safe_mean(values: list[float]) -> float:
    """Return mean or 0 if empty."""
    return round(mean(values), 2) if values else 0.0


def _make_aware(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is timezone-aware (UTC). Returns None for None input."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _get_first_seen(ad: Ad) -> datetime | None:
    """Get first_seen_at as a timezone-aware datetime."""
    return _make_aware(ad.first_seen_at)


# ---------------------------------------------------------------------------
# Build per-advertiser profile
# ---------------------------------------------------------------------------

def build_advertiser_profiles(ads: list[Ad]) -> dict[str, dict]:
    """Group all ads by advertiser_name and compute per-advertiser metrics.

    Returns: {advertiser_name: profile_dict}
    """
    groups: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        name = ad.advertiser_name
        if not name or name.strip() == "":
            continue
        groups[name].append(ad)

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    profiles: dict[str, dict] = {}
    for name, group_ads in groups.items():
        total_ads = len(group_ads)
        scores = [_get_score(a) for a in group_ads]
        avg_score = _safe_mean(scores)
        max_score = round(max(scores), 1) if scores else 0.0

        hits = sum(1 for a in group_ads if _is_hit(a))
        hit_rate = round(hits / total_ads * 100, 1) if total_ads else 0.0

        # Unique genres (fine_genre_en)
        genres = set(_get_genre(a) for a in group_ads)
        genre_count = len(genres)

        # Date range
        first_seen_dates = [_get_first_seen(a) for a in group_ads]
        first_seen_dates = [d for d in first_seen_dates if d is not None]
        earliest_first_seen = min(first_seen_dates) if first_seen_dates else None
        latest_first_seen = max(first_seen_dates) if first_seen_dates else None

        # Is this advertiser "recent"? All first_seen_at within last 30 days
        all_recent = False
        if first_seen_dates:
            all_recent = all(d >= thirty_days_ago for d in first_seen_dates)

        # Score trend: compare newer half vs older half
        # Sort ads by first_seen_at for trend calculation
        dated_ads = [(a, _get_first_seen(a)) for a in group_ads]
        dated_ads = [(a, d) for a, d in dated_ads if d is not None]
        dated_ads.sort(key=lambda x: x[1])

        improving_scores = False
        if len(dated_ads) >= 2:
            mid = len(dated_ads) // 2
            older_scores = [_get_score(a) for a, _ in dated_ads[:mid]]
            newer_scores = [_get_score(a) for a, _ in dated_ads[mid:]]
            older_avg = _safe_mean(older_scores)
            newer_avg = _safe_mean(newer_scores)
            improving_scores = newer_avg > older_avg
        elif len(dated_ads) == 1:
            # Single ad with a score > 0 counts as "not declining"
            improving_scores = _get_score(dated_ads[0][0]) > 0

        profiles[name] = {
            "advertiser_name": name,
            "total_ads": total_ads,
            "avg_score": avg_score,
            "max_score": max_score,
            "hit_count": hits,
            "hit_rate": hit_rate,
            "genre_count": genre_count,
            "genres": sorted(genres),
            "earliest_first_seen": earliest_first_seen.isoformat() if earliest_first_seen else None,
            "latest_first_seen": latest_first_seen.isoformat() if latest_first_seen else None,
            "all_recent": all_recent,
            "improving_scores": improving_scores,
        }

    return profiles


# ---------------------------------------------------------------------------
# Clustering logic
# ---------------------------------------------------------------------------

def classify_advertiser(profile: dict) -> str:
    """Classify a single advertiser into a cluster.

    Priority order (check in this order, first match wins):
      1. Heavy hitter:      total_ads >= 5  AND  avg_score >= 40
      2. Niche specialist:  genre_count <= 2  AND  hit_rate >= 40%
      3. Spray and pray:    genre_count >= 3  AND  hit_rate < 30%
      4. Rising star:       all ads first_seen_at in last 30 days  AND  improving scores
      5. other
    """
    total_ads = profile["total_ads"]
    avg_score = profile["avg_score"]
    hit_rate = profile["hit_rate"]
    genre_count = profile["genre_count"]
    all_recent = profile["all_recent"]
    improving = profile["improving_scores"]

    # 1. Heavy hitters
    if total_ads >= 5 and avg_score >= 40:
        return "heavy_hitters"

    # 2. Niche specialists
    if genre_count <= 2 and hit_rate >= 40:
        return "niche_specialists"

    # 3. Spray and pray
    if genre_count >= 3 and hit_rate < 30:
        return "spray_and_pray"

    # 4. Rising stars
    if all_recent and improving:
        return "rising_stars"

    return "other"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("ADVERTISER CLUSTERING")
    print("Executed at: %s" % datetime.now(timezone.utc).isoformat())
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print("Total ads in database: %d" % total)

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Build profiles
        print("\nBuilding advertiser profiles...")
        profiles = build_advertiser_profiles(ads)
        print("Unique advertisers: %d" % len(profiles))

        if not profiles:
            print("No advertisers with a name found. Exiting.")
            return

        # Classify each advertiser
        print("Classifying advertisers into clusters...")
        cluster_groups: dict[str, list[dict]] = defaultdict(list)

        for name, profile in profiles.items():
            cluster = classify_advertiser(profile)
            profile["cluster"] = cluster
            cluster_groups[cluster].append(profile)

        # ── Print summary table ──────────────────────────────────────
        cluster_order = [
            "heavy_hitters",
            "niche_specialists",
            "spray_and_pray",
            "rising_stars",
            "other",
        ]

        print("\n" + "=" * 60)
        print("CLUSTER SUMMARY")
        print("=" * 60)
        print("  %-20s %6s %8s %8s %8s %8s" % (
            "Cluster", "Count", "Pct", "AvgAds", "AvgScr", "AvgHR%",
        ))
        print("  " + "-" * 60)

        summary: dict[str, dict] = {}
        for cluster_name in cluster_order:
            members = cluster_groups.get(cluster_name, [])
            count = len(members)
            pct = count / len(profiles) * 100 if profiles else 0

            if members:
                avg_ads = _safe_mean([float(m["total_ads"]) for m in members])
                avg_score = _safe_mean([m["avg_score"] for m in members])
                avg_hr = _safe_mean([m["hit_rate"] for m in members])
            else:
                avg_ads = avg_score = avg_hr = 0.0

            print("  %-20s %6d %7.1f%% %8.1f %8.1f %7.1f%%" % (
                cluster_name, count, pct, avg_ads, avg_score, avg_hr,
            ))

            summary[cluster_name] = {
                "count": count,
                "percentage": round(pct, 1),
                "avg_ads": avg_ads,
                "avg_score": avg_score,
                "avg_hit_rate": avg_hr,
            }

        # ── Print example advertisers per cluster ────────────────────
        print("\n" + "=" * 60)
        print("EXAMPLE ADVERTISERS PER CLUSTER")
        print("=" * 60)

        for cluster_name in cluster_order:
            members = cluster_groups.get(cluster_name, [])
            if not members:
                continue

            print("\n  --- %s (%d advertisers) ---" % (
                cluster_name.upper().replace("_", " "), len(members),
            ))

            # Sort by avg_score descending and show top 5
            top = sorted(members, key=lambda m: m["avg_score"], reverse=True)[:5]
            for i, m in enumerate(top, 1):
                name_safe = m["advertiser_name"][:30].encode("ascii", "replace").decode("ascii")
                print("    %d. %-30s ads=%3d score=%.1f hit_rate=%.1f%% genres=%d" % (
                    i, name_safe,
                    m["total_ads"], m["avg_score"], m["hit_rate"], m["genre_count"],
                ))

        # ── Export ────────────────────────────────────────────────────
        os.makedirs(EXPORTS_DIR, exist_ok=True)

        export_data = {
            "clusters": {},
            "summary": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_advertisers": len(profiles),
                "cluster_counts": {c: len(cluster_groups.get(c, [])) for c in cluster_order},
                "cluster_details": summary,
            },
        }

        for cluster_name in cluster_order:
            members = cluster_groups.get(cluster_name, [])
            sorted_members = sorted(members, key=lambda m: m["avg_score"], reverse=True)
            export_data["clusters"][cluster_name] = sorted_members

        export_path = os.path.join(EXPORTS_DIR, "advertiser_clusters.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        print("\nExported to: %s" % export_path)
        print("\nDone!")

    except Exception as e:
        session.rollback()
        print("FATAL ERROR: %s" % e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
