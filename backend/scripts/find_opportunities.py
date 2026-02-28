#!/usr/bin/env python3
"""Find underserved niches and high-potential opportunities in the ad database.

Identifies four types of opportunities:
  1. Underserved genres: high volume but low avg score = room for quality improvement
  2. Untested hooks: hook types rarely used in high-performing genres
  3. Underutilized CTAs: CTA types with high hit rate but low adoption
  4. Rising advertisers: advertisers whose recent ads score higher than older ones

Each opportunity is scored 0-100 based on potential impact.

Outputs:
  - backend/exports/opportunities.json

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/find_opportunities.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_score(ad: Ad) -> float:
    """Get hit score from ad_metadata, default 0."""
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _get_genre(ad: Ad) -> str | None:
    """Get fine_genre from ad_metadata."""
    return (ad.ad_metadata or {}).get("fine_genre")


def _get_hook(ad: Ad) -> str | None:
    """Get hook_type from ad_metadata."""
    return (ad.ad_metadata or {}).get("hook_type")


def _get_cta(ad: Ad) -> str | None:
    """Get cta_type from ad_metadata."""
    return (ad.ad_metadata or {}).get("cta_type")


def _get_hit_level(ad: Ad) -> str:
    """Get hit_level from ad_metadata, default 'none'."""
    return (ad.ad_metadata or {}).get("hit_level", "none")


def _is_hit(ad: Ad) -> bool:
    """Check if ad is a hit or mega_hit."""
    return _get_hit_level(ad) in ("hit", "mega_hit")


def _safe_avg(vals: list[float]) -> float:
    """Return average or 0.0 if empty."""
    return round(sum(vals) / len(vals), 1) if vals else 0.0


def _hit_rate(hits: int, total: int) -> float:
    """Calculate hit rate percentage."""
    if total == 0:
        return 0.0
    return round(hits / total * 100, 1)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp a value to [lo, hi]."""
    return max(lo, min(hi, value))


# ── 1. Underserved Genres ────────────────────────────────────────────────


def find_underserved_genres(ads: list[Ad]) -> list[dict]:
    """Genres with high ad volume but low average score.

    High volume signals demand.  Low average score means current creatives
    are mediocre -- opportunity for high-quality content.

    Score formula (0-100):
      volume_factor  = min(ad_count / 10, 1.0)       -- more ads = more demand
      quality_gap    = max(0, 100 - avg_score) / 100  -- lower avg = bigger gap
      opportunity    = volume_factor * quality_gap * 100
    """
    genre_ads: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        genre = _get_genre(ad)
        if genre:
            genre_ads[genre].append(ad)

    results = []
    for genre, g_ads in genre_ads.items():
        count = len(g_ads)
        if count < 3:
            continue

        scores = [_get_score(a) for a in g_ads]
        avg = _safe_avg(scores)
        hits = sum(1 for a in g_ads if _is_hit(a))
        hr = _hit_rate(hits, count)

        volume_factor = min(count / 10.0, 1.0)
        quality_gap = max(0.0, 100.0 - avg) / 100.0
        opp_score = int(_clamp(volume_factor * quality_gap * 100))

        if opp_score < 20:
            continue

        results.append({
            "type": "underserved_genre",
            "genre": genre,
            "reason": (
                f"High volume ({count} ads) but low avg score ({avg}) "
                f"suggests room for quality improvement"
            ),
            "score": opp_score,
            "recommendation": (
                "Focus on quality creative with proven patterns from "
                "similar genres"
            ),
            "detail": {
                "ad_count": count,
                "avg_score": avg,
                "hit_rate": hr,
                "hit_count": hits,
            },
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)


# ── 2. Untested Hooks in High-Performing Genres ─────────────────────────


def find_untested_hooks(ads: list[Ad]) -> list[dict]:
    """Hook types rarely used in genres that already perform well.

    If a genre has a high hit rate but never uses a particular hook type
    that works elsewhere, that is an untested opportunity.

    Score formula:
      genre_hr factor  = genre hit rate (0-1)
      hook_hr factor   = hook global hit rate (0-1)
      rarity_bonus     = 1.0 if unused, 0.5 if 1-2 uses
      score = (genre_hr * 0.4 + hook_hr * 0.4 + rarity_bonus * 0.2) * 100
    """
    genre_hooks: dict[str, dict[str, list[Ad]]] = defaultdict(lambda: defaultdict(list))
    genre_all: dict[str, list[Ad]] = defaultdict(list)
    hook_all: dict[str, list[Ad]] = defaultdict(list)

    for ad in ads:
        genre = _get_genre(ad)
        hook = _get_hook(ad)
        if genre:
            genre_all[genre].append(ad)
        if hook:
            hook_all[hook].append(ad)
        if genre and hook:
            genre_hooks[genre][hook].append(ad)

    # Genre hit rates (>= 5 ads for significance)
    genre_hr: dict[str, float] = {}
    for genre, g_ads in genre_all.items():
        if len(g_ads) >= 5:
            hits = sum(1 for a in g_ads if _is_hit(a))
            genre_hr[genre] = hits / len(g_ads)

    # Hook global hit rates (>= 3 ads for significance)
    hook_hr: dict[str, float] = {}
    for hook, h_ads in hook_all.items():
        if len(h_ads) >= 3:
            hits = sum(1 for a in h_ads if _is_hit(a))
            hook_hr[hook] = hits / len(h_ads)

    results = []
    for genre, g_hr in genre_hr.items():
        if g_hr < 0.2:
            continue
        used_hooks = genre_hooks.get(genre, {})
        for hook, h_hr in hook_hr.items():
            if h_hr < 0.2:
                continue
            usage_in_genre = len(used_hooks.get(hook, []))
            if usage_in_genre > 2:
                continue

            rarity = 1.0 if usage_in_genre == 0 else 0.5
            opp_score = int(_clamp(
                (g_hr * 0.4 + h_hr * 0.4 + rarity * 0.2) * 100
            ))

            if opp_score < 20:
                continue

            usage_label = "never used" if usage_in_genre == 0 else f"only {usage_in_genre} ad(s)"
            results.append({
                "type": "untested_hook",
                "genre": genre,
                "hook_type": hook,
                "reason": (
                    f"Hook '{hook}' ({usage_label} in '{genre}') has "
                    f"{h_hr * 100:.0f}% global hit rate but is untested in a "
                    f"genre with {g_hr * 100:.0f}% hit rate"
                ),
                "score": opp_score,
                "recommendation": (
                    f"Test '{hook}' hook in '{genre}' genre creatives"
                ),
                "detail": {
                    "genre_hit_rate": round(g_hr * 100, 1),
                    "hook_global_hit_rate": round(h_hr * 100, 1),
                    "current_usage_in_genre": usage_in_genre,
                },
            })

    return sorted(results, key=lambda x: x["score"], reverse=True)


# ── 3. Underutilized CTAs ────────────────────────────────────────────────


def find_underutilized_ctas(ads: list[Ad]) -> list[dict]:
    """CTA types with high hit rate but low adoption.

    If a CTA type has a great hit rate but very few ads use it,
    it is an underutilized tactic.

    Score formula:
      hit_rate_factor  = cta hit rate (0-1)
      scarcity_factor  = 1 - (cta_count / total_with_cta)
      score = (hit_rate_factor * 0.6 + scarcity_factor * 0.4) * 100
    """
    cta_ads: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        cta = _get_cta(ad)
        if cta:
            cta_ads[cta].append(ad)

    total_with_cta = sum(len(v) for v in cta_ads.values())
    if total_with_cta == 0:
        return []

    results = []
    for cta, c_ads in cta_ads.items():
        count = len(c_ads)
        if count < 2:
            continue

        hits = sum(1 for a in c_ads if _is_hit(a))
        hr = hits / count
        adoption = count / total_with_cta
        scores = [_get_score(a) for a in c_ads]
        avg = _safe_avg(scores)

        # Only flag if hit rate is decent and adoption is low
        if hr < 0.3 or adoption > 0.25:
            continue

        scarcity = 1.0 - adoption
        opp_score = int(_clamp((hr * 0.6 + scarcity * 0.4) * 100))

        if opp_score < 20:
            continue

        results.append({
            "type": "underutilized_cta",
            "cta_type": cta,
            "reason": (
                f"CTA '{cta}' has {hr * 100:.0f}% hit rate but only "
                f"{adoption * 100:.1f}% adoption ({count}/{total_with_cta} ads)"
            ),
            "score": opp_score,
            "recommendation": (
                f"Increase usage of '{cta}' CTA -- high hit rate with low "
                f"competition"
            ),
            "detail": {
                "ad_count": count,
                "hit_count": hits,
                "hit_rate": round(hr * 100, 1),
                "adoption_rate": round(adoption * 100, 1),
                "avg_score": avg,
            },
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)


# ── 4. Rising Advertisers ───────────────────────────────────────────────


def find_rising_advertisers(ads: list[Ad]) -> list[dict]:
    """Advertisers whose recent ads score higher than older ones.

    Split each advertiser's ads into older half and newer half by first_seen_at.
    If the newer half has a meaningfully higher average score, the advertiser
    is on an improving trajectory.

    Score formula:
      improvement = new_avg - old_avg
      consistency = min(new_count, 5) / 5   -- need enough recent ads
      baseline    = min(new_avg, 40)         -- reward already-good new avg
      score = min(improvement * 2, 60) * consistency + baseline
    """
    adv_ads: dict[str, list[Ad]] = defaultdict(list)
    for ad in ads:
        name = ad.advertiser_name
        if name:
            adv_ads[name].append(ad)

    results = []
    for advertiser, a_ads in adv_ads.items():
        if len(a_ads) < 4:
            continue

        def _sort_key(a: Ad):
            if a.first_seen_at is None:
                return datetime.min
            dt = a.first_seen_at
            if dt.tzinfo is not None:
                return dt.replace(tzinfo=None)
            return dt

        sorted_ads = sorted(a_ads, key=_sort_key)
        mid = len(sorted_ads) // 2
        older = sorted_ads[:mid]
        newer = sorted_ads[mid:]

        old_scores = [_get_score(a) for a in older]
        new_scores = [_get_score(a) for a in newer]
        old_avg = _safe_avg(old_scores)
        new_avg = _safe_avg(new_scores)

        improvement = new_avg - old_avg
        if improvement <= 5:
            continue

        consistency = min(len(newer), 5) / 5.0
        baseline = min(new_avg, 40.0)
        opp_score = int(_clamp(
            min(improvement * 2, 60.0) * consistency + baseline
        ))

        if opp_score < 20:
            continue

        results.append({
            "type": "rising_advertiser",
            "advertiser": advertiser,
            "reason": (
                f"Score improved from {old_avg} (older {len(older)} ads) to "
                f"{new_avg} (recent {len(newer)} ads), +{improvement:.1f} points"
            ),
            "score": opp_score,
            "recommendation": (
                f"Study {advertiser}'s recent creative changes for replicable "
                f"patterns"
            ),
            "detail": {
                "total_ads": len(a_ads),
                "older_count": len(older),
                "newer_count": len(newer),
                "older_avg_score": old_avg,
                "newer_avg_score": new_avg,
                "improvement": round(improvement, 1),
            },
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("OPPORTUNITY FINDER")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"Total ads loaded: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Run all four analyses
        genre_opps = find_underserved_genres(ads)
        hook_opps = find_untested_hooks(ads)
        cta_opps = find_underutilized_ctas(ads)
        rising_opps = find_rising_advertisers(ads)

        print(f"\n  Underserved genres found:    {len(genre_opps)}")
        print(f"  Untested hook opportunities: {len(hook_opps)}")
        print(f"  Underutilized CTAs:          {len(cta_opps)}")
        print(f"  Rising advertisers:          {len(rising_opps)}")

        # Merge and rank all opportunities by score
        all_opportunities = genre_opps + hook_opps + cta_opps + rising_opps
        all_opportunities.sort(key=lambda x: x["score"], reverse=True)

        # Print top 10 with reasoning
        print(f"\n{'=' * 60}")
        print("TOP 10 OPPORTUNITIES")
        print(f"{'=' * 60}")

        for i, opp in enumerate(all_opportunities[:10], 1):
            print(f"\n  #{i} [{opp['type']}] (score: {opp['score']})")
            print(f"     Reason: {opp['reason']}")
            print(f"     Action: {opp['recommendation']}")

        # Build export
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads_analyzed": total,
            "summary": {
                "underserved_genres": len(genre_opps),
                "untested_hooks": len(hook_opps),
                "underutilized_ctas": len(cta_opps),
                "rising_advertisers": len(rising_opps),
                "total_opportunities": len(all_opportunities),
            },
            "opportunities": all_opportunities,
        }

        os.makedirs(EXPORTS_DIR, exist_ok=True)
        out_path = os.path.join(EXPORTS_DIR, "opportunities.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n  Exported {len(all_opportunities)} opportunities to: {out_path}")
        print("Done!")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
