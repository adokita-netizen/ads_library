#!/usr/bin/env python3
"""Genre-relative score calibration v2.

For each genre, computes z-score normalization of hit_score, then maps
to a 0-100 scale centered at 50.  Ensures a healthy target distribution:
  ~20% above 70 (hit), ~60% in 30-70, ~20% below 30.

Stores results in ad_metadata["calibrated_score"] and
ad_metadata["score_calibration_v2"].

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/calibrate_scores_v2.py
"""

import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_score(ad):
    """Extract latest_hit_score from ad_metadata, default 0."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _get_genre(ad):
    """Extract fine_genre_en from ad_metadata, default 'other'."""
    meta = ad.ad_metadata or {}
    return meta.get("fine_genre_en") or "other"


def _safe_mean(values):
    """Arithmetic mean (pure Python)."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _safe_stdev(values):
    """Sample standard deviation (pure Python, no external libs)."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return variance ** 0.5 if variance > 0 else 0.0


def _clamp(value, lo=0.0, hi=100.0):
    return max(lo, min(hi, value))


def _print_distribution(scores, total, label):
    """Print three-tier distribution summary."""
    above70 = sum(1 for s in scores if s > 70)
    mid = sum(1 for s in scores if 30 <= s <= 70)
    below30 = sum(1 for s in scores if s < 30)
    print(f"\n--- {label} ---")
    print(f"  Above 70 (hit):  {above70:>5d} ({above70 / total * 100:>5.1f}%)  target ~20%")
    print(f"  30-70 (mid):     {mid:>5d} ({mid / total * 100:>5.1f}%)  target ~60%")
    print(f"  Below 30 (low):  {below30:>5d} ({below30 / total * 100:>5.1f}%)  target ~20%")
    return above70, mid, below30


def _print_bucket_histogram(scores, total, label):
    """Print 10-wide bucket histogram."""
    buckets = Counter()
    for s in scores:
        b = min(int(s // 10) * 10, 90)
        key = f"{b}-{b + 9}"
        buckets[key] += 1

    print(f"\n--- {label} ---")
    for lo in range(0, 100, 10):
        key = f"{lo}-{lo + 9}"
        count = buckets.get(key, 0)
        pct = count / total * 100 if total else 0
        bar = "#" * int(pct / 2)
        print(f"  {key:>7s}: {count:>5d} ({pct:>5.1f}%) {bar}")


# ---------------------------------------------------------------------------
# Main calibration
# ---------------------------------------------------------------------------

def main():
    print("=" * 64)
    print("  Hit Score Calibration v2  --  Genre-Relative Normalization")
    print(f"  Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 64)

    session = SyncSessionLocal()
    try:
        # ------------------------------------------------------------------
        # 1. Load all ads
        # ------------------------------------------------------------------
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads loaded: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # ------------------------------------------------------------------
        # 2. Group by fine_genre_en
        # ------------------------------------------------------------------
        genre_ads = defaultdict(list)
        for ad in ads:
            genre = _get_genre(ad)
            genre_ads[genre].append(ad)

        print(f"Distinct genres: {len(genre_ads)}")

        # ------------------------------------------------------------------
        # 3. For each genre: compute mean and std of hit_score
        # ------------------------------------------------------------------
        genre_stats = {}
        for genre, g_ads in genre_ads.items():
            scores = [_get_score(a) for a in g_ads]
            g_mean = _safe_mean(scores)
            g_std = _safe_stdev(scores)
            genre_stats[genre] = {
                "mean": g_mean,
                "std": g_std,
                "count": len(scores),
            }

        print(f"\n{'Genre':<30s} {'Count':>6s} {'Mean':>8s} {'StdDev':>8s}")
        print("-" * 56)
        for genre, st in sorted(genre_stats.items(), key=lambda x: -x[1]["count"]):
            print(f"  {genre:<28s} {st['count']:>6d} {st['mean']:>8.1f} {st['std']:>8.1f}")

        # ------------------------------------------------------------------
        # Before-calibration distribution
        # ------------------------------------------------------------------
        before_raw = [_get_score(a) for a in ads]
        _print_distribution(before_raw, total, "Before Calibration (raw hit_score)")
        _print_bucket_histogram(before_raw, total, "Bucket Distribution (Before)")

        # ------------------------------------------------------------------
        # 4. For each ad: calibrated = (score - genre_mean) / genre_std * 20 + 50
        #    Handle genre_std == 0 -> use raw score scaled to 50
        # 5. Clamp to 0-100
        # ------------------------------------------------------------------
        calibrated_map = {}  # ad.id -> calibrated score (float)
        for ad in ads:
            score = _get_score(ad)
            genre = _get_genre(ad)
            st = genre_stats[genre]

            if st["std"] == 0.0:
                # All scores in this genre are identical (or single ad).
                # Use raw score scaled to 50 (center of distribution).
                calibrated = 50.0
            else:
                z = (score - st["mean"]) / st["std"]
                calibrated = z * 20 + 50

            calibrated = _clamp(calibrated, 0.0, 100.0)
            calibrated_map[ad.id] = round(calibrated, 2)

        # ------------------------------------------------------------------
        # 6. Ensure distribution: ~20% above 70, ~60% in 30-70, ~20% below 30
        #    Use rank-based remapping to enforce the target distribution.
        # ------------------------------------------------------------------
        sorted_ids = sorted(calibrated_map.keys(), key=lambda aid: calibrated_map[aid])
        n = len(sorted_ids)
        p20 = int(n * 0.20)
        p80 = int(n * 0.80)

        final_map = {}
        for rank, ad_id in enumerate(sorted_ids):
            if rank < p20:
                # Bottom ~20%: map to 0-29
                frac = rank / max(p20, 1)
                final_map[ad_id] = round(frac * 29.0, 2)
            elif rank < p80:
                # Middle ~60%: map to 30-70
                frac = (rank - p20) / max(p80 - p20, 1)
                final_map[ad_id] = round(30.0 + frac * 40.0, 2)
            else:
                # Top ~20%: map to 71-100
                frac = (rank - p80) / max(n - p80, 1)
                final_map[ad_id] = round(71.0 + frac * 29.0, 2)

        # ------------------------------------------------------------------
        # 7. Store in ad_metadata["calibrated_score"] and
        #    ad_metadata["score_calibration_v2"]
        # 8. Use flag_modified for all DB updates
        # ------------------------------------------------------------------
        updated = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        for ad in ads:
            new_score = final_map[ad.id]
            raw_score = _get_score(ad)
            genre = _get_genre(ad)
            st = genre_stats[genre]

            meta = dict(ad.ad_metadata or {})
            meta["calibrated_score"] = new_score
            meta["score_calibration_v2"] = {
                "original_hit_score": raw_score,
                "genre": genre,
                "genre_mean": round(st["mean"], 2),
                "genre_std": round(st["std"], 2),
                "z_calibrated": calibrated_map[ad.id],
                "final_calibrated": new_score,
                "calibrated_at": now_iso,
            }
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

        session.commit()
        print(f"\nUpdated {updated} ads in database.")

        # ------------------------------------------------------------------
        # 9. Print before/after distribution comparison
        # ------------------------------------------------------------------
        after_scores = [final_map[ad.id] for ad in ads]
        _print_distribution(after_scores, total, "After Calibration (calibrated_score)")
        _print_bucket_histogram(after_scores, total, "Bucket Distribution (After)")

        # Side-by-side comparison
        b_above70 = sum(1 for s in before_raw if s > 70)
        b_mid = sum(1 for s in before_raw if 30 <= s <= 70)
        b_below30 = sum(1 for s in before_raw if s < 30)
        a_above70 = sum(1 for s in after_scores if s > 70)
        a_mid = sum(1 for s in after_scores if 30 <= s <= 70)
        a_below30 = sum(1 for s in after_scores if s < 30)

        print(f"\n--- Before vs After Comparison ---")
        print(f"  {'Tier':<15s} {'Before':>12s} {'After':>12s} {'Target':>10s}")
        print(f"  {'Above 70':<15s} {b_above70:>5d} ({b_above70/total*100:>4.1f}%) "
              f"{a_above70:>5d} ({a_above70/total*100:>4.1f}%) {'~20%':>10s}")
        print(f"  {'30-70':<15s} {b_mid:>5d} ({b_mid/total*100:>4.1f}%) "
              f"{a_mid:>5d} ({a_mid/total*100:>4.1f}%) {'~60%':>10s}")
        print(f"  {'Below 30':<15s} {b_below30:>5d} ({b_below30/total*100:>4.1f}%) "
              f"{a_below30:>5d} ({a_below30/total*100:>4.1f}%) {'~20%':>10s}")

        print(f"\nDone. {updated} ads calibrated across {len(genre_stats)} genres.")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
