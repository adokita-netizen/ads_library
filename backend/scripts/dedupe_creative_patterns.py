#!/usr/bin/env python3
"""Deduplicate and group ads by creative pattern fingerprint.

Finds ads that share the same creative structure (hook_type + cta_type +
fine_genre from ad_metadata) and groups them into pattern clusters.  Each
cluster is ranked by performance using latest_hit_score.

Outputs:
  - backend/exports/creative_pattern_groups.json
  - Console frequency table (top 20 patterns by count)

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/dedupe_creative_patterns.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from app.core.database import SyncSessionLocal  # noqa: E402
from app.models.ad import Ad  # noqa: E402


# ── Constants ─────────────────────────────────────────────────────────────

HIT_SCORE_THRESHOLD = 60  # Ads with score >= this are considered "hits"


# ── Helper Functions ──────────────────────────────────────────────────────


def _get_score(ad: Ad) -> float:
    """Extract latest_hit_score from ad_metadata, default 0."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0))
    except (ValueError, TypeError):
        return 0.0


def _get_fingerprint(ad: Ad) -> tuple[str, str, str] | None:
    """Build creative fingerprint from ad_metadata fields.

    Returns (hook_type, cta_type, fine_genre) or None if all three are
    missing/empty.
    """
    meta = ad.ad_metadata or {}
    hook = str(meta.get("hook_type", "") or "").strip().lower()
    cta = str(meta.get("cta_type", "") or "").strip().lower()
    genre = str(meta.get("fine_genre", "") or "").strip().lower()

    # Skip ads that have none of the three fields populated
    if not hook and not cta and not genre:
        return None

    return (hook or "unknown", cta or "unknown", genre or "unknown")


def _fingerprint_key(fp: tuple[str, str, str]) -> str:
    """Convert fingerprint tuple to readable string key."""
    return f"{fp[0]}+{fp[1]}+{fp[2]}"


def _safe_mean(values: list[float]) -> float:
    """Return mean of values, or 0.0 if empty."""
    return mean(values) if values else 0.0


def _hit_rate(ads_group: list[Ad]) -> float:
    """Fraction of ads with score >= HIT_SCORE_THRESHOLD."""
    if not ads_group:
        return 0.0
    hits = sum(1 for a in ads_group if _get_score(a) >= HIT_SCORE_THRESHOLD)
    return round(hits / len(ads_group), 4)


# ── Core Logic ────────────────────────────────────────────────────────────


def build_pattern_groups(ads: list[Ad]) -> dict[tuple, list[Ad]]:
    """Group ads by their creative fingerprint.

    Returns a dict mapping fingerprint tuple -> list of Ad objects,
    sorted within each group by score descending.
    """
    groups: dict[tuple, list[Ad]] = defaultdict(list)

    for ad in ads:
        fp = _get_fingerprint(ad)
        if fp is None:
            continue
        groups[fp].append(ad)

    # Sort each group by score descending (best performer first)
    for fp in groups:
        groups[fp].sort(key=lambda a: _get_score(a), reverse=True)

    return dict(groups)


def build_export_data(groups: dict[tuple, list[Ad]]) -> dict:
    """Build the JSON-serializable export structure."""
    patterns = []

    for fp, ads_in_group in groups.items():
        scores = [_get_score(a) for a in ads_in_group]
        avg_score = round(_safe_mean(scores), 1)
        hit_r = _hit_rate(ads_in_group)
        count = len(ads_in_group)

        best_ad = ads_in_group[0]   # already sorted desc by score
        worst_ad = ads_in_group[-1]

        patterns.append({
            "fingerprint": _fingerprint_key(fp),
            "hook_type": fp[0],
            "cta_type": fp[1],
            "genre": fp[2],
            "count": count,
            "avg_score": avg_score,
            "hit_rate": round(hit_r, 4),
            "best_ad": {
                "id": best_ad.id,
                "title": best_ad.title or "",
                "score": _get_score(best_ad),
            },
            "worst_ad": {
                "id": worst_ad.id,
                "title": worst_ad.title or "",
                "score": _get_score(worst_ad),
            },
            "ad_ids": [a.id for a in ads_in_group],
        })

    # Sort patterns by count descending, then avg_score descending
    patterns.sort(key=lambda p: (-p["count"], -p["avg_score"]))

    total_ads = sum(p["count"] for p in patterns)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_patterns": len(patterns),
        "total_ads": total_ads,
        "patterns": patterns,
    }


# ── Console Output ────────────────────────────────────────────────────────


def print_frequency_table(export_data: dict) -> None:
    """Print the top 20 patterns sorted by count with avg_score and hit_rate."""
    patterns = export_data["patterns"]
    top_n = 20

    print(f"\n{'=' * 80}")
    print(f"  TOP {min(top_n, len(patterns))} CREATIVE PATTERNS BY FREQUENCY")
    print(f"{'=' * 80}")
    print(
        f"  {'#':>3s}  {'Fingerprint':<40s} {'Count':>5s}  "
        f"{'AvgScore':>8s}  {'HitRate':>7s}"
    )
    print(f"  {'-' * 72}")

    for i, p in enumerate(patterns[:top_n], 1):
        fp_display = p["fingerprint"]
        if len(fp_display) > 38:
            fp_display = fp_display[:35] + "..."
        print(
            f"  {i:>3d}  {fp_display:<40s} {p['count']:>5d}  "
            f"{p['avg_score']:>8.1f}  {p['hit_rate']:>6.1%}"
        )

    print(f"  {'-' * 72}")


def print_summary(export_data: dict) -> None:
    """Print overall summary statistics."""
    patterns = export_data["patterns"]
    total_patterns = export_data["total_patterns"]
    total_ads = export_data["total_ads"]

    singleton_count = sum(1 for p in patterns if p["count"] == 1)
    multi_count = total_patterns - singleton_count

    print(f"\n{'=' * 80}")
    print(f"  SUMMARY")
    print(f"{'=' * 80}")
    print(f"  Total ads with fingerprint:    {total_ads}")
    print(f"  Unique patterns:               {total_patterns}")
    print(f"  Singleton patterns (count=1):  {singleton_count}")
    print(f"  Multi-ad patterns (count>=2):  {multi_count}")

    if patterns:
        largest = patterns[0]  # already sorted by count desc
        print(f"  Largest group:                 {largest['count']} ads "
              f"({largest['fingerprint']})")

        # Average group size (excluding singletons)
        multi_patterns = [p for p in patterns if p["count"] >= 2]
        if multi_patterns:
            avg_group = _safe_mean([p["count"] for p in multi_patterns])
            print(f"  Avg group size (excl single):  {avg_group:.1f}")

        # Best performing pattern (min count 3 for statistical relevance)
        significant = [p for p in patterns if p["count"] >= 3]
        if significant:
            best = max(significant, key=lambda p: p["avg_score"])
            print(
                f"  Best performing pattern:       {best['fingerprint']} "
                f"(avg_score={best['avg_score']}, n={best['count']})"
            )

    print(f"{'=' * 80}")


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 80)
    print("  Creative Pattern Deduplication")
    print(f"  Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total_db = len(ads)
        print(f"\nTotal ads in database: {total_db}")

        if total_db == 0:
            print("No ads found. Exiting.")
            return

        # Build pattern groups
        print("Building creative fingerprints (hook_type + cta_type + fine_genre)...")
        groups = build_pattern_groups(ads)

        fingerprinted = sum(len(g) for g in groups.values())
        skipped = total_db - fingerprinted
        print(f"  Ads with fingerprint: {fingerprinted}")
        print(f"  Ads skipped (no metadata): {skipped}")

        if not groups:
            print("No ads have hook_type/cta_type/fine_genre metadata. Exiting.")
            return

        # Build export data
        print("Ranking groups by performance...")
        export_data = build_export_data(groups)

        # Tag each ad with its pattern group info in ad_metadata
        print("Tagging ads with pattern_group metadata...")
        tagged = 0
        for fp, ads_in_group in groups.items():
            fp_key = _fingerprint_key(fp)
            group_size = len(ads_in_group)
            group_avg = round(
                _safe_mean([_get_score(a) for a in ads_in_group]), 1
            )

            for rank_in_group, ad in enumerate(ads_in_group, 1):
                meta = dict(ad.ad_metadata or {})
                meta["pattern_fingerprint"] = fp_key
                meta["pattern_group_size"] = group_size
                meta["pattern_group_avg_score"] = group_avg
                meta["pattern_rank_in_group"] = rank_in_group
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                tagged += 1

        session.commit()
        print(f"  Updated ad_metadata for {tagged} ads.")

        # Save JSON export
        exports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(exports_dir, exist_ok=True)
        export_path = os.path.join(exports_dir, "creative_pattern_groups.json")

        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"\nExport saved to: {export_path}")

        # Console output
        print_frequency_table(export_data)
        print_summary(export_data)

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
