#!/usr/bin/env python3
"""Weekly digest generator - auto-generate email-style weekly summary.

Sections:
  - Top 5 new ads (highest score from last 7 days)
  - Score movers (biggest increases/decreases per advertiser)
  - New advertisers entering the market
  - Genre of the week (most new ads)
  - Creative tip of the week (highest hit-rate pattern)

Output: backend/exports/weekly_digest_YYYY-MM-DD.json

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/generate_weekly_digest.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_aware(dt):
    """Ensure a datetime is timezone-aware (default UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _get_score(ad):
    """Extract latest_hit_score from ad_metadata, defaulting to 0."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _get_genre(ad):
    """Extract fine_genre from ad_metadata."""
    meta = ad.ad_metadata or {}
    return meta.get("fine_genre") or meta.get("fine_genre_en") or "other"


def _get_hit_level(ad):
    """Extract hit_level from ad_metadata."""
    meta = ad.ad_metadata or {}
    return meta.get("hit_level", "none")


def _first_seen_aware(ad):
    """Return timezone-aware first_seen_at (fallback to created_at)."""
    return _make_aware(ad.first_seen_at) or _make_aware(ad.created_at)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_top_new_ads(this_week_ads, limit=5):
    """Top N new ads from this week ranked by score."""
    ranked = sorted(this_week_ads, key=_get_score, reverse=True)
    result = []
    for ad in ranked[:limit]:
        result.append({
            "id": ad.id,
            "title": (ad.title or "")[:100],
            "advertiser": (ad.advertiser_name or "")[:60],
            "score": round(_get_score(ad), 1),
            "genre": _get_genre(ad),
            "view_count": ad.view_count or 0,
            "spend": round(ad.spend, 2) if ad.spend else 0,
            "first_seen_at": str(_first_seen_aware(ad)),
        })
    return result


def _build_score_movers(this_week_ads, older_ads):
    """Compare average scores per advertiser: recent week vs older period.

    Returns {"up": [...], "down": [...]}.
    """
    # Build per-advertiser score lists for each period
    recent_scores = defaultdict(list)
    for ad in this_week_ads:
        name = ad.advertiser_name
        if name:
            recent_scores[name].append(_get_score(ad))

    older_scores = defaultdict(list)
    for ad in older_ads:
        name = ad.advertiser_name
        if name:
            older_scores[name].append(_get_score(ad))

    # Only consider advertisers present in both periods
    common = set(recent_scores.keys()) & set(older_scores.keys())
    changes = []
    for adv in common:
        avg_recent = sum(recent_scores[adv]) / len(recent_scores[adv])
        avg_older = sum(older_scores[adv]) / len(older_scores[adv])
        delta = avg_recent - avg_older
        changes.append({
            "advertiser": adv[:60],
            "avg_score_recent": round(avg_recent, 1),
            "avg_score_older": round(avg_older, 1),
            "change": round(delta, 1),
            "recent_ads": len(recent_scores[adv]),
        })

    changes.sort(key=lambda x: x["change"], reverse=True)

    up = changes[:5] if changes else []
    down = list(reversed(changes[-5:])) if len(changes) >= 5 else list(reversed(changes))
    # Only include truly negative movers
    down = [d for d in down if d["change"] < 0]

    return {"up": up, "down": down}


def _build_new_advertisers(this_week_ads, older_ads):
    """Advertisers whose first ad appeared in the last 7 days."""
    this_week_names = {ad.advertiser_name for ad in this_week_ads if ad.advertiser_name}
    older_names = {ad.advertiser_name for ad in older_ads if ad.advertiser_name}
    new_names = sorted(this_week_names - older_names)
    return new_names[:30]


def _build_genre_of_week(this_week_ads):
    """Genre with the most new ads this week."""
    if not this_week_ads:
        return {"genre": "none", "new_ads": 0}

    genre_counter = Counter(_get_genre(ad) for ad in this_week_ads)
    top_genre, count = genre_counter.most_common(1)[0]
    return {"genre": top_genre, "new_ads": count}


def _build_creative_tip(this_week_ads, all_ads):
    """Identify the pattern with the highest hit rate among recent winning ads.

    Looks at genre + creative_type combinations from top-scoring ads.
    Falls back to all-time data when this week has too few ads.
    """
    # Determine pool of ads to analyze
    pool = this_week_ads if len(this_week_ads) >= 5 else all_ads
    if not pool:
        return {
            "pattern": "insufficient data",
            "hit_rate": 0,
            "tip": "Not enough ads to generate a creative tip.",
        }

    # Group by pattern (genre + creative_type)
    pattern_stats = defaultdict(lambda: {"total": 0, "hits": 0, "scores": []})
    for ad in pool:
        genre = _get_genre(ad)
        ctype = (ad.creative_type or "unknown").lower()
        pattern_key = f"{genre} / {ctype}"
        score = _get_score(ad)
        hit_level = _get_hit_level(ad)

        pattern_stats[pattern_key]["total"] += 1
        pattern_stats[pattern_key]["scores"].append(score)
        if hit_level in ("hit", "mega_hit"):
            pattern_stats[pattern_key]["hits"] += 1

    # Filter patterns with at least 3 ads for statistical relevance
    qualified = {
        k: v for k, v in pattern_stats.items() if v["total"] >= 3
    }

    if not qualified:
        # Relax: allow any pattern with >= 1 ad
        qualified = pattern_stats

    # Find pattern with highest hit rate
    best_pattern = None
    best_rate = -1
    for pattern, stats in qualified.items():
        rate = stats["hits"] / stats["total"] if stats["total"] > 0 else 0
        if rate > best_rate or (rate == best_rate and stats["total"] > (pattern_stats.get(best_pattern, {}).get("total", 0))):
            best_rate = rate
            best_pattern = pattern

    if best_pattern is None:
        return {
            "pattern": "no clear pattern",
            "hit_rate": 0,
            "tip": "No dominant pattern found this week.",
        }

    avg_score = sum(qualified[best_pattern]["scores"]) / len(qualified[best_pattern]["scores"])
    hit_pct = round(best_rate * 100, 1)

    tip_text = (
        f"The '{best_pattern}' combination has a {hit_pct}% hit rate "
        f"(avg score {avg_score:.0f}) across {qualified[best_pattern]['total']} ads. "
        f"Consider creating similar content in this genre and format."
    )

    return {
        "pattern": best_pattern,
        "hit_rate": hit_pct,
        "tip": tip_text,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    today_str = now.strftime("%Y-%m-%d")

    print("=" * 60)
    print("VAAP Weekly Digest Generator")
    print(f"Generated at : {now.isoformat()}")
    print(f"Week ending  : {today_str}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        all_ads = session.query(Ad).all()
        total = len(all_ads)
        print(f"\nTotal ads in library: {total}")

        if total == 0:
            print("No ads found. Nothing to generate.")
            return

        # Partition ads into this-week vs older
        this_week_ads = []
        older_ads = []
        for ad in all_ads:
            fs = _first_seen_aware(ad)
            if fs and fs >= week_ago:
                this_week_ads.append(ad)
            else:
                older_ads.append(ad)

        print(f"This week's ads  : {len(this_week_ads)}")
        print(f"Older ads        : {len(older_ads)}")

        # --- Build each section ---
        top_new = _build_top_new_ads(this_week_ads)
        score_movers = _build_score_movers(this_week_ads, older_ads)
        new_advertisers = _build_new_advertisers(this_week_ads, older_ads)
        genre_week = _build_genre_of_week(this_week_ads)
        creative_tip = _build_creative_tip(this_week_ads, all_ads)

        digest = {
            "generated_at": now.isoformat(),
            "week_ending": today_str,
            "sections": {
                "top_new_ads": top_new,
                "score_movers": score_movers,
                "new_advertisers": new_advertisers,
                "genre_of_week": genre_week,
                "creative_tip": creative_tip,
            },
        }

        # --- Print summary ---
        print("\n" + "-" * 40)
        print("TOP 5 NEW ADS")
        print("-" * 40)
        if top_new:
            for i, ad_info in enumerate(top_new, 1):
                print(f"  {i}. [id={ad_info['id']}] score={ad_info['score']:.1f}  "
                      f"{ad_info['title'][:55]}")
                print(f"     advertiser: {ad_info['advertiser']}")
        else:
            print("  (no new ads this week)")

        print("\n" + "-" * 40)
        print("SCORE MOVERS")
        print("-" * 40)
        if score_movers["up"]:
            print("  Rising:")
            for m in score_movers["up"]:
                print(f"    {m['advertiser']}: {m['avg_score_older']:.1f} -> "
                      f"{m['avg_score_recent']:.1f} ({m['change']:+.1f})")
        if score_movers["down"]:
            print("  Declining:")
            for m in score_movers["down"]:
                print(f"    {m['advertiser']}: {m['avg_score_older']:.1f} -> "
                      f"{m['avg_score_recent']:.1f} ({m['change']:+.1f})")
        if not score_movers["up"] and not score_movers["down"]:
            print("  (not enough overlapping advertisers to compare)")

        print("\n" + "-" * 40)
        print("NEW ADVERTISERS")
        print("-" * 40)
        print(f"  {len(new_advertisers)} new advertiser(s) entered the market")
        for name in new_advertisers[:10]:
            print(f"    - {name[:50]}")
        if len(new_advertisers) > 10:
            print(f"    ... and {len(new_advertisers) - 10} more")

        print("\n" + "-" * 40)
        print("GENRE OF THE WEEK")
        print("-" * 40)
        print(f"  {genre_week['genre']}: {genre_week['new_ads']} new ads")

        print("\n" + "-" * 40)
        print("CREATIVE TIP OF THE WEEK")
        print("-" * 40)
        print(f"  Pattern : {creative_tip['pattern']}")
        print(f"  Hit rate: {creative_tip['hit_rate']}%")
        print(f"  Tip     : {creative_tip['tip']}")

        # --- Export ---
        export_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports",
        )
        os.makedirs(export_dir, exist_ok=True)

        out_path = os.path.join(export_dir, f"weekly_digest_{today_str}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(digest, f, ensure_ascii=False, indent=2, default=str)

        print("\n" + "=" * 60)
        print(f"Digest exported to: {out_path}")
        print("=" * 60)

    except Exception as exc:
        print(f"ERROR: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
