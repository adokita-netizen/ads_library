#!/usr/bin/env python3
"""Recalculate all ad scores with improved hybrid algorithm.

Applies the recommended Method 3 (Hybrid + Recency) scoring:
  - 60% percentile normalization of raw hit_score
  - 20% genre-relative z-score
  - 20% recency boost (active ads, recently stopped)

Stores results in ad_metadata and outputs a before/after comparison.

Usage:
    cd C:/Users/ishit/ads_library/backend

    # Dry run (no DB writes, just report):
    python scripts/recalculate_scores.py --dry-run

    # Apply new scores to database:
    python scripts/recalculate_scores.py
"""

import io
import json
import math
import os
import sys
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def _mean(vals):
    return sum(vals) / len(vals) if vals else 0.0


def _stdev(vals):
    n = len(vals)
    if n < 2:
        return 0.0
    m = sum(vals) / n
    return (sum((x - m) ** 2 for x in vals) / (n - 1)) ** 0.5


def _median(vals):
    if not vals:
        return 0.0
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _percentile(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * p / 100
    f, c = math.floor(k), math.ceil(k)
    return s[f] * (c - k) + s[c] * (k - f) if f != c else s[int(k)]


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def _extract(ad: Ad) -> dict:
    meta = ad.ad_metadata or {}
    try:
        score = float(meta.get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        score = 0.0

    genre = meta.get("fine_genre_en") or "other"

    days_running = meta.get("days_running", 0)
    if days_running == 0 and ad.first_seen_at:
        now = datetime.now(timezone.utc)
        first = ad.first_seen_at
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        days_running = max(0, (now - first).days)

    is_still_running = meta.get("is_still_running", ad.last_seen_at is None)

    days_since_last_seen = None
    if ad.last_seen_at:
        last = ad.last_seen_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        days_since_last_seen = max(0, (datetime.now(timezone.utc) - last).days)

    return {
        "id": ad.id,
        "raw_score": score,
        "genre": genre,
        "days_running": days_running,
        "is_still_running": is_still_running,
        "days_since_last_seen": days_since_last_seen,
        "hit_level": meta.get("hit_level", "none"),
    }


# ---------------------------------------------------------------------------
# Hybrid scoring algorithm (Method 3)
# ---------------------------------------------------------------------------

def compute_hybrid_scores(data: list[dict]) -> dict[int, dict]:
    """Compute hybrid scores for all ads.

    Returns: {ad_id: {"new_score": float, "components": {...}, ...}}
    """
    n = len(data)
    if n == 0:
        return {}

    all_raw = sorted(d["raw_score"] for d in data)

    # Pre-compute genre stats
    genre_groups: dict[str, list[dict]] = defaultdict(list)
    for d in data:
        genre_groups[d["genre"]].append(d)

    genre_stats = {}
    for genre, g_data in genre_groups.items():
        scores = [d["raw_score"] for d in g_data]
        genre_stats[genre] = {"mean": _mean(scores), "stdev": _stdev(scores)}

    results = {}
    for d in data:
        # Component 1: Percentile base (60%)
        below = sum(1 for s in all_raw if s < d["raw_score"])
        equal = sum(1 for s in all_raw if s == d["raw_score"])
        percentile_score = (below + 0.5 * equal) / n * 100

        # Component 2: Genre-relative z-score (20%)
        genre = d["genre"]
        st = genre_stats[genre]
        if st["stdev"] > 0:
            z = (d["raw_score"] - st["mean"]) / st["stdev"]
            genre_score = _clamp(z * 20 + 50, 0, 100)
        else:
            genre_score = 50.0

        # Component 3: Recency boost (20%)
        recency_score = 0.0
        if d["is_still_running"]:
            if d["days_running"] >= 60:
                recency_score = 100.0
            elif d["days_running"] >= 30:
                recency_score = 80.0
            elif d["days_running"] >= 14:
                recency_score = 60.0
            else:
                recency_score = 40.0
        elif d["days_since_last_seen"] is not None:
            if d["days_since_last_seen"] <= 7:
                recency_score = 30.0
            elif d["days_since_last_seen"] <= 30:
                recency_score = 15.0
            else:
                recency_score = 5.0

        # Combine
        combined = (
            percentile_score * 0.60
            + genre_score * 0.20
            + recency_score * 0.20
        )
        combined = _clamp(combined, 0, 100)

        # Determine new hit level
        if combined >= 75 and d["days_running"] >= 60:
            new_hit_level = "mega_hit"
            new_is_hit = True
        elif combined >= 50 and d["days_running"] >= 30:
            new_hit_level = "hit"
            new_is_hit = True
        else:
            new_hit_level = "none"
            new_is_hit = False

        results[d["id"]] = {
            "new_score": round(combined, 2),
            "raw_score": d["raw_score"],
            "genre": genre,
            "genre_mean": round(st["mean"], 2),
            "genre_stdev": round(st["stdev"], 2),
            "components": {
                "percentile_base": round(percentile_score, 2),
                "genre_relative": round(genre_score, 2),
                "recency_boost": round(recency_score, 2),
            },
            "new_hit_level": new_hit_level,
            "new_is_hit": new_is_hit,
            "old_hit_level": d["hit_level"],
        }

    return results


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------

def _print_dist(scores, total, label):
    """Print distribution summary."""
    print(f"\n  {label}:")
    print(f"    Mean:   {_mean(scores):.1f}")
    print(f"    Median: {_median(scores):.1f}")
    print(f"    StdDev: {_stdev(scores):.1f}")
    print(f"    P10:    {_percentile(scores, 10):.1f}")
    print(f"    P25:    {_percentile(scores, 25):.1f}")
    print(f"    P75:    {_percentile(scores, 75):.1f}")
    print(f"    P90:    {_percentile(scores, 90):.1f}")
    print(f"    IQR:    {_percentile(scores, 75) - _percentile(scores, 25):.1f}")


def _print_histogram(scores, total, label):
    """Print histogram."""
    print(f"\n  {label}:")
    buckets = Counter()
    for s in scores:
        bucket = min(int(s // 10) * 10, 90)
        buckets[f"{bucket}-{bucket + 9}"] += 1
    max_count = max(buckets.values()) if buckets else 1
    for lo in range(0, 100, 10):
        key = f"{lo}-{lo + 9}"
        count = buckets.get(key, 0)
        pct = count / total * 100
        bar = "#" * int(count / max(max_count, 1) * 40)
        print(f"    {key:>7s}: {count:>5d} ({pct:>5.1f}%) |{bar}")


def _print_three_tier(scores, total, label):
    """Print three-tier distribution."""
    above = sum(1 for s in scores if s > 70)
    mid = sum(1 for s in scores if 30 <= s <= 70)
    below = sum(1 for s in scores if s < 30)
    print(f"\n  {label}:")
    print(f"    Above 70 (strong): {above:>5d} ({above / total * 100:>5.1f}%)  target ~20%")
    print(f"    30-70 (mid):       {mid:>5d} ({mid / total * 100:>5.1f}%)  target ~60%")
    print(f"    Below 30 (weak):   {below:>5d} ({below / total * 100:>5.1f}%)  target ~20%")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Recalculate ad scores with hybrid algorithm")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report only, do not write to database",
    )
    args = parser.parse_args()

    print("=" * 64)
    print("  Recalculate Scores - Hybrid Algorithm (Percentile + Genre + Recency)")
    print(f"  Executed at: {datetime.now(timezone.utc).isoformat()}")
    print(f"  Mode: {'DRY RUN (no DB writes)' if args.dry_run else 'LIVE (will update DB)'}")
    print("=" * 64)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads loaded: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Extract data
        data = [_extract(ad) for ad in ads]
        raw_scores = [d["raw_score"] for d in data]

        # Compute new scores
        print("\nComputing hybrid scores...")
        score_map = compute_hybrid_scores(data)
        new_scores = [score_map[d["id"]]["new_score"] for d in data]

        # ---- BEFORE distribution ----
        print(f"\n{'=' * 64}")
        print(f"  BEFORE (Current hit_score)")
        print(f"{'=' * 64}")
        _print_dist(raw_scores, total, "Distribution Stats")
        _print_histogram(raw_scores, total, "Histogram")
        _print_three_tier(raw_scores, total, "Three-Tier Split")

        # ---- AFTER distribution ----
        print(f"\n{'=' * 64}")
        print(f"  AFTER (Hybrid Recalculated)")
        print(f"{'=' * 64}")
        _print_dist(new_scores, total, "Distribution Stats")
        _print_histogram(new_scores, total, "Histogram")
        _print_three_tier(new_scores, total, "Three-Tier Split")

        # ---- Hit level changes ----
        print(f"\n{'=' * 64}")
        print(f"  HIT LEVEL CHANGES")
        print(f"{'=' * 64}")

        old_hits = Counter(d["hit_level"] for d in data)
        new_hits = Counter(score_map[d["id"]]["new_hit_level"] for d in data)

        print(f"\n  {'Level':<15s} {'Before':>10s} {'After':>10s} {'Change':>10s}")
        print(f"  {'-' * 47}")
        for level in ["mega_hit", "hit", "none"]:
            before = old_hits.get(level, 0)
            after = new_hits.get(level, 0)
            change = after - before
            sign = "+" if change > 0 else ""
            print(f"  {level:<15s} {before:>10d} {after:>10d} {sign}{change:>9d}")

        # Transitions
        transitions = Counter()
        for d in data:
            old = d["hit_level"]
            new = score_map[d["id"]]["new_hit_level"]
            if old != new:
                transitions[f"{old} -> {new}"] += 1

        if transitions:
            print(f"\n  Hit level transitions:")
            for transition, count in transitions.most_common():
                print(f"    {transition}: {count}")

        # ---- Side-by-side comparison ----
        print(f"\n{'=' * 64}")
        print(f"  SIDE-BY-SIDE COMPARISON")
        print(f"{'=' * 64}")

        iqr_before = _percentile(raw_scores, 75) - _percentile(raw_scores, 25)
        iqr_after = _percentile(new_scores, 75) - _percentile(new_scores, 25)
        spread_before = _percentile(raw_scores, 90) - _percentile(raw_scores, 10)
        spread_after = _percentile(new_scores, 90) - _percentile(new_scores, 10)

        print(f"\n  {'Metric':<25s} {'Before':>10s} {'After':>10s} {'Improvement':>12s}")
        print(f"  {'-' * 59}")
        print(f"  {'Mean':<25s} {_mean(raw_scores):>10.1f} {_mean(new_scores):>10.1f}")
        print(f"  {'Median':<25s} {_median(raw_scores):>10.1f} {_median(new_scores):>10.1f}")
        print(f"  {'StdDev':<25s} {_stdev(raw_scores):>10.1f} {_stdev(new_scores):>10.1f}")
        print(f"  {'IQR':<25s} {iqr_before:>10.1f} {iqr_after:>10.1f} "
              f"{'x' + str(round(iqr_after / max(iqr_before, 0.1), 1)):>12s}")
        print(f"  {'P10-P90 spread':<25s} {spread_before:>10.1f} {spread_after:>10.1f} "
              f"{'x' + str(round(spread_after / max(spread_before, 0.1), 1)):>12s}")

        # ---- Top 10 biggest movers ----
        print(f"\n{'=' * 64}")
        print(f"  TOP 10 BIGGEST SCORE CHANGES")
        print(f"{'=' * 64}")

        movers = []
        for d in data:
            info = score_map[d["id"]]
            change = info["new_score"] - d["raw_score"]
            movers.append({
                "id": d["id"],
                "raw": d["raw_score"],
                "new": info["new_score"],
                "change": change,
                "genre": d["genre"],
                "old_level": d["hit_level"],
                "new_level": info["new_hit_level"],
            })

        movers.sort(key=lambda x: abs(x["change"]), reverse=True)

        print(f"\n  {'ID':>5s} {'Raw':>7s} {'New':>7s} {'Delta':>7s} {'Genre':<20s} {'Level Change':<20s}")
        print(f"  {'-' * 68}")
        for m in movers[:10]:
            level_change = f"{m['old_level']} -> {m['new_level']}" if m["old_level"] != m["new_level"] else "-"
            sign = "+" if m["change"] > 0 else ""
            print(
                f"  {m['id']:>5d} "
                f"{m['raw']:>7.1f} "
                f"{m['new']:>7.1f} "
                f"{sign}{m['change']:>6.1f} "
                f"{m['genre']:<20s} "
                f"{level_change:<20s}"
            )

        # ---- Apply to database ----
        if not args.dry_run:
            print(f"\n{'=' * 64}")
            print(f"  APPLYING TO DATABASE...")
            print(f"{'=' * 64}")

            updated = 0
            now_iso = datetime.now(timezone.utc).isoformat()

            for ad in ads:
                info = score_map.get(ad.id)
                if not info:
                    continue

                meta = dict(ad.ad_metadata or {})

                # Store new calibrated score alongside original
                meta["recalculated_score"] = info["new_score"]
                meta["recalculated_hit_level"] = info["new_hit_level"]
                meta["recalculated_is_hit"] = info["new_is_hit"]
                meta["score_recalculation"] = {
                    "algorithm": "hybrid_v3",
                    "original_hit_score": info["raw_score"],
                    "components": info["components"],
                    "genre": info["genre"],
                    "genre_mean": info["genre_mean"],
                    "genre_stdev": info["genre_stdev"],
                    "recalculated_at": now_iso,
                }

                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                updated += 1

            session.commit()
            print(f"  Updated {updated} ads in database.")
            print(f"  New scores stored in ad_metadata['recalculated_score']")
            print(f"  Original scores preserved in ad_metadata['latest_hit_score']")
        else:
            print(f"\n  DRY RUN complete. No database changes made.")
            print(f"  Run without --dry-run to apply changes.")

        # Export comparison report
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)
        out_path = os.path.join(export_dir, "score_recalculation_report.json")

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "dry_run" if args.dry_run else "applied",
            "total_ads": total,
            "algorithm": "hybrid_v3 (60% percentile + 20% genre + 20% recency)",
            "before": {
                "mean": round(_mean(raw_scores), 2),
                "median": round(_median(raw_scores), 2),
                "stdev": round(_stdev(raw_scores), 2),
                "iqr": round(iqr_before, 2),
                "p10_p90_spread": round(spread_before, 2),
            },
            "after": {
                "mean": round(_mean(new_scores), 2),
                "median": round(_median(new_scores), 2),
                "stdev": round(_stdev(new_scores), 2),
                "iqr": round(iqr_after, 2),
                "p10_p90_spread": round(spread_after, 2),
            },
            "hit_level_changes": {
                "before": dict(old_hits),
                "after": dict(new_hits),
                "transitions": dict(transitions),
            },
            "top_movers": [
                {
                    "id": m["id"],
                    "raw_score": m["raw"],
                    "new_score": m["new"],
                    "delta": round(m["change"], 2),
                    "genre": m["genre"],
                }
                for m in movers[:20]
            ],
        }

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Report exported: {out_path}")
        print("\nDone.")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
