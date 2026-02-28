#!/usr/bin/env python3
"""Deep analysis of CTA types and their performance.

For each CTA type: count, avg_score (from latest_hit_score), hit_rate,
avg_views (from view_count), avg_spend (from spend column).
Cross-tabulates CTA x genre (fine_genre) for genre-specific effectiveness.
Identifies best and worst CTA per genre.

Outputs:
  - backend/exports/cta_effectiveness.json
  - Effectiveness matrix to stdout (genres as rows, CTA types as columns)

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/analyze_cta_effectiveness.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Helper Functions ──────────────────────────────────────────────────────


def _get_meta(ad: Ad) -> dict:
    """Return ad_metadata dict, never None."""
    return ad.ad_metadata or {}


def _is_hit(ad: Ad) -> bool:
    """Determine if an ad is a hit based on hit_level in metadata."""
    return _get_meta(ad).get("hit_level") in ("hit", "mega_hit")


def _get_score(ad: Ad) -> float:
    """Get latest_hit_score from metadata, defaulting to 0."""
    try:
        return float(_get_meta(ad).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _get_cta_type(ad: Ad) -> str | None:
    """Extract cta_type from ad_metadata (top-level or creative_analysis)."""
    meta = _get_meta(ad)
    cta = meta.get("cta_type")
    if cta and cta != "none":
        return cta
    # Fallback: check creative_analysis sub-dict
    ca = meta.get("creative_analysis")
    if isinstance(ca, dict):
        cta = ca.get("cta_type")
        if cta and cta != "none":
            return cta
    return None


def _get_fine_genre(ad: Ad) -> str | None:
    """Extract fine_genre from ad_metadata."""
    return _get_meta(ad).get("fine_genre")


def _safe_avg(values: list[float]) -> float:
    """Return average or 0.0 if empty."""
    return sum(values) / len(values) if values else 0.0


def _compute_stats(ads_group: list[Ad], cta_type: str) -> dict:
    """Compute aggregated stats for a group of ads sharing a CTA type.

    Returns dict matching the required output schema:
    {"cta_type", "count", "avg_score", "hit_rate", "avg_views", "avg_spend"}
    """
    count = len(ads_group)
    if count == 0:
        return {
            "cta_type": cta_type,
            "count": 0,
            "avg_score": 0.0,
            "hit_rate": 0.0,
            "avg_views": 0.0,
            "avg_spend": 0.0,
        }

    scores = [_get_score(a) for a in ads_group]
    hits = sum(1 for a in ads_group if _is_hit(a))
    views = [float(a.view_count) for a in ads_group if a.view_count is not None]
    spends = [float(a.spend) for a in ads_group if a.spend is not None]

    return {
        "cta_type": cta_type,
        "count": count,
        "avg_score": round(_safe_avg(scores), 2),
        "hit_rate": round(hits / count, 4),
        "avg_views": round(_safe_avg(views), 1),
        "avg_spend": round(_safe_avg(spends), 2),
    }


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("CTA Effectiveness Analysis")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # ── Group ads by CTA type and by (genre, CTA type) ──────────

        by_cta: dict[str, list[Ad]] = defaultdict(list)
        by_genre_cta: dict[str, dict[str, list[Ad]]] = defaultdict(
            lambda: defaultdict(list)
        )

        skipped = 0
        for ad in ads:
            cta_type = _get_cta_type(ad)
            if not cta_type:
                skipped += 1
                continue

            by_cta[cta_type].append(ad)

            genre = _get_fine_genre(ad) or "unknown"
            by_genre_cta[genre][cta_type].append(ad)

        included = total - skipped
        print(f"Ads with CTA type: {included}")
        print(f"Ads without CTA type (skipped): {skipped}")
        print(f"Unique CTA types: {len(by_cta)}")
        print(f"Unique genres: {len(by_genre_cta)}")

        if not by_cta:
            print("No ads with CTA type found. Exiting.")
            return

        # ── Overall CTA stats ────────────────────────────────────────

        overall: list[dict] = []
        for cta_type in sorted(by_cta.keys()):
            stats = _compute_stats(by_cta[cta_type], cta_type)
            overall.append(stats)

        # Sort by hit_rate descending, then avg_score descending
        overall.sort(key=lambda x: (x["hit_rate"], x["avg_score"]), reverse=True)

        # ── By-genre CTA stats + best/worst per genre ────────────────

        by_genre_output: dict[str, list[dict]] = {}
        best_per_genre: dict[str, dict] = {}
        worst_per_genre: dict[str, dict] = {}

        for genre in sorted(by_genre_cta.keys()):
            genre_stats: list[dict] = []
            for cta_type in sorted(by_genre_cta[genre].keys()):
                stats = _compute_stats(by_genre_cta[genre][cta_type], cta_type)
                genre_stats.append(stats)

            # Sort by hit_rate descending
            genre_stats.sort(key=lambda x: x["hit_rate"], reverse=True)
            by_genre_output[genre] = genre_stats

            # Best / worst: prefer types with count >= 2 for reliability
            eligible = [s for s in genre_stats if s["count"] >= 2]
            candidates = eligible if eligible else genre_stats

            if candidates:
                best = max(candidates, key=lambda x: (x["hit_rate"], x["avg_score"]))
                worst = min(candidates, key=lambda x: (x["hit_rate"], x["avg_score"]))
                best_per_genre[genre] = {
                    "cta_type": best["cta_type"],
                    "hit_rate": best["hit_rate"],
                }
                worst_per_genre[genre] = {
                    "cta_type": worst["cta_type"],
                    "hit_rate": worst["hit_rate"],
                }

        # ── Build report JSON ────────────────────────────────────────

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "overall": overall,
            "by_genre": by_genre_output,
            "best_per_genre": best_per_genre,
            "worst_per_genre": worst_per_genre,
        }

        # ── Save to exports ──────────────────────────────────────────

        exports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(exports_dir, exist_ok=True)
        report_path = os.path.join(exports_dir, "cta_effectiveness.json")

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\nReport saved to: {report_path}")

        # ── Print overall summary table ──────────────────────────────

        print("\n--- Overall CTA Effectiveness ---")
        print(
            f"  {'CTA Type':<18s} {'Count':>6s} {'AvgScore':>9s} "
            f"{'HitRate':>8s} {'AvgViews':>10s} {'AvgSpend':>10s}"
        )
        print(f"  {'-' * 65}")
        for entry in overall:
            print(
                f"  {entry['cta_type']:<18s} {entry['count']:>6d} "
                f"{entry['avg_score']:>9.2f} {entry['hit_rate']:>7.2%} "
                f"{entry['avg_views']:>10.1f} {entry['avg_spend']:>10.2f}"
            )

        # ── Print best/worst per genre ───────────────────────────────

        print("\n--- Best CTA per Genre ---")
        print(f"  {'Genre':<22s} {'Best CTA':<18s} {'HitRate':>8s}")
        print(f"  {'-' * 50}")
        for genre in sorted(best_per_genre.keys()):
            b = best_per_genre[genre]
            print(
                f"  {genre:<22s} {b['cta_type']:<18s} {b['hit_rate']:>7.2%}"
            )

        print("\n--- Worst CTA per Genre ---")
        print(f"  {'Genre':<22s} {'Worst CTA':<18s} {'HitRate':>8s}")
        print(f"  {'-' * 50}")
        for genre in sorted(worst_per_genre.keys()):
            w = worst_per_genre[genre]
            print(
                f"  {genre:<22s} {w['cta_type']:<18s} {w['hit_rate']:>7.2%}"
            )

        # ── Print effectiveness matrix (genres as rows, CTAs as cols) ─

        all_cta_types = sorted(by_cta.keys())
        all_genres = sorted(by_genre_cta.keys())

        if all_cta_types and all_genres:
            print("\n--- Effectiveness Matrix (hit_rate: genres x CTA types) ---")

            col_w = max(10, max(len(c) for c in all_cta_types) + 2)
            genre_col_w = max(16, max(len(g) for g in all_genres) + 2)

            # Header
            header = f"  {'Genre':<{genre_col_w}s}"
            for cta in all_cta_types:
                header += f"{cta:>{col_w}s}"
            print(header)
            print(f"  {'-' * (genre_col_w + col_w * len(all_cta_types))}")

            # Rows: one per genre
            for genre in all_genres:
                row = f"  {genre:<{genre_col_w}s}"
                for cta in all_cta_types:
                    group = by_genre_cta[genre].get(cta, [])
                    if group:
                        hits = sum(1 for a in group if _is_hit(a))
                        rate = hits / len(group)
                        cell = f"{rate:.0%}"
                    else:
                        cell = "-"
                    row += f"{cell:>{col_w}s}"
                print(row)

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
