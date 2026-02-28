#!/usr/bin/env python3
"""Ad pattern evolution analyzer.

For advertisers with 3+ ads, track how their creative strategy changes over time:
  - Did they switch hooks?
  - Change CTAs?
  - Test different emotions?
  - Shift creative types?

Exports insights to backend/exports/ad_evolution.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/analyze_ad_evolution.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


def _get_created_at(ad: Ad) -> datetime:
    """Get created_at with timezone awareness."""
    dt = ad.first_seen_at or ad.created_at
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt or datetime.now(timezone.utc)


def _detect_changes(timeline: list[dict], field: str) -> list[dict]:
    """Detect when a field value changes across the timeline.

    Returns a list of change events.
    """
    changes = []
    prev_value = None

    for entry in timeline:
        value = entry.get(field, "none")
        if prev_value is not None and value != prev_value:
            changes.append({
                "from": prev_value,
                "to": value,
                "ad_id": entry["ad_id"],
                "date": entry["date"],
                "score_after": entry["score"],
            })
        prev_value = value

    return changes


def _compute_field_diversity(values: list[str]) -> float:
    """Compute diversity score (0-1) for a list of values.

    1.0 = all different, 0.0 = all same.
    """
    if len(values) <= 1:
        return 0.0
    unique = len(set(values))
    return round((unique - 1) / (len(values) - 1), 2)


def analyze_advertiser_evolution(advertiser: str, ads: list[Ad]) -> dict:
    """Analyze how an advertiser's creative strategy evolved over time."""
    # Sort ads by creation date
    sorted_ads = sorted(ads, key=_get_created_at)

    # Build timeline
    timeline = []
    for ad in sorted_ads:
        ca = (ad.ad_metadata or {}).get("creative_analysis", {})
        entry = {
            "ad_id": ad.id,
            "date": _get_created_at(ad).isoformat(),
            "title": (ad.title or "")[:60],
            "score": _get_score(ad),
            "is_hit": _is_hit(ad),
            "creative_type": ad.creative_type or "unknown",
            "hook_type": ca.get("hook_type", "none"),
            "cta_type": ca.get("cta_type", "none"),
            "offer_type": ca.get("offer_type", "none"),
            "emotion": ca.get("emotion", "neutral"),
        }
        timeline.append(entry)

    # Detect strategy changes
    hook_changes = _detect_changes(timeline, "hook_type")
    cta_changes = _detect_changes(timeline, "cta_type")
    emotion_changes = _detect_changes(timeline, "emotion")
    offer_changes = _detect_changes(timeline, "offer_type")
    type_changes = _detect_changes(timeline, "creative_type")

    # Field diversity
    hooks = [e["hook_type"] for e in timeline]
    ctas = [e["cta_type"] for e in timeline]
    emotions = [e["emotion"] for e in timeline]
    offers = [e["offer_type"] for e in timeline]
    types = [e["creative_type"] for e in timeline]

    # Score trend: first half vs second half
    half = len(timeline) // 2
    first_half_scores = [e["score"] for e in timeline[:half]] if half > 0 else []
    second_half_scores = [e["score"] for e in timeline[half:]] if half > 0 else []
    first_avg = round(sum(first_half_scores) / len(first_half_scores), 1) if first_half_scores else 0
    second_avg = round(sum(second_half_scores) / len(second_half_scores), 1) if second_half_scores else 0

    if second_avg > first_avg + 5:
        score_trend = "improving"
    elif first_avg > second_avg + 5:
        score_trend = "declining"
    else:
        score_trend = "stable"

    # Identify experimentation level
    total_changes = len(hook_changes) + len(cta_changes) + len(emotion_changes)
    if total_changes >= len(timeline):
        experimentation = "high"
    elif total_changes >= len(timeline) * 0.5:
        experimentation = "medium"
    else:
        experimentation = "low"

    # Generate insights
    insights = []

    if hook_changes:
        from_to = Counter(f"{c['from']} -> {c['to']}" for c in hook_changes)
        top_switch = from_to.most_common(1)[0]
        insights.append(f"Hook switch: {top_switch[0]} ({top_switch[1]}x)")

    if cta_changes:
        from_to = Counter(f"{c['from']} -> {c['to']}" for c in cta_changes)
        top_switch = from_to.most_common(1)[0]
        insights.append(f"CTA switch: {top_switch[0]} ({top_switch[1]}x)")

    if emotion_changes:
        from_to = Counter(f"{c['from']} -> {c['to']}" for c in emotion_changes)
        top_switch = from_to.most_common(1)[0]
        insights.append(f"Emotion shift: {top_switch[0]} ({top_switch[1]}x)")

    if score_trend == "improving":
        insights.append(f"Performance improving: avg {first_avg} -> {second_avg}")
    elif score_trend == "declining":
        insights.append(f"Performance declining: avg {first_avg} -> {second_avg}")

    # Dominant patterns
    dominant_hook = Counter(hooks).most_common(1)[0][0] if hooks else "none"
    dominant_cta = Counter(ctas).most_common(1)[0][0] if ctas else "none"

    return {
        "advertiser": advertiser,
        "total_ads": len(ads),
        "date_range": {
            "first": timeline[0]["date"] if timeline else None,
            "last": timeline[-1]["date"] if timeline else None,
        },
        "score_trend": score_trend,
        "experimentation_level": experimentation,
        "diversity": {
            "hook": _compute_field_diversity(hooks),
            "cta": _compute_field_diversity(ctas),
            "emotion": _compute_field_diversity(emotions),
            "offer": _compute_field_diversity(offers),
            "creative_type": _compute_field_diversity(types),
        },
        "dominant_patterns": {
            "hook": dominant_hook,
            "cta": dominant_cta,
        },
        "changes": {
            "hook_changes": len(hook_changes),
            "cta_changes": len(cta_changes),
            "emotion_changes": len(emotion_changes),
            "offer_changes": len(offer_changes),
            "type_changes": len(type_changes),
            "total_strategy_shifts": total_changes,
        },
        "change_details": {
            "hook": hook_changes,
            "cta": cta_changes,
            "emotion": emotion_changes,
        },
        "insights": insights,
        "timeline": timeline,
    }


def main() -> None:
    print("=" * 60)
    print("AD PATTERN EVOLUTION ANALYZER")
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

        # Group by advertiser (only those with 3+ ads)
        advertiser_groups: dict[str, list[Ad]] = defaultdict(list)
        for ad in ads:
            name = ad.advertiser_name
            if name and name.strip():
                advertiser_groups[name].append(ad)

        qualifying = {
            name: group for name, group in advertiser_groups.items()
            if len(group) >= 3
        }

        print(f"Total advertisers: {len(advertiser_groups)}")
        print(f"Advertisers with 3+ ads: {len(qualifying)}")

        if not qualifying:
            print("No advertisers with 3+ ads found. Exiting.")
            return

        # Analyze each qualifying advertiser
        evolutions = []
        for advertiser, group_ads in sorted(qualifying.items(),
                                             key=lambda x: -len(x[1])):
            evolution = analyze_advertiser_evolution(advertiser, group_ads)
            evolutions.append(evolution)

        # Export
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        export_path = os.path.join(EXPORTS_DIR, "ad_evolution.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(evolutions, f, ensure_ascii=False, indent=2)
        print(f"\nExported to: {export_path}")

        # Print summary
        print(f"\n{'=' * 60}")
        print("EVOLUTION ANALYSIS RESULTS")
        print(f"{'=' * 60}")
        print(f"  {'Advertiser':<30s} {'Ads':>4s} {'Trend':<12s} {'Exp':>6s} {'Shifts':>6s}")
        print(f"  {'-' * 65}")

        for evo in evolutions:
            adv_safe = evo["advertiser"][:28].encode("ascii", "replace").decode("ascii")
            print(
                f"  {adv_safe:<30s} "
                f"{evo['total_ads']:>4d} "
                f"{evo['score_trend']:<12s} "
                f"{evo['experimentation_level']:>6s} "
                f"{evo['changes']['total_strategy_shifts']:>6d}"
            )

        # Insights summary
        print(f"\n{'=' * 60}")
        print("KEY EVOLUTION INSIGHTS")
        print(f"{'=' * 60}")

        # Count trends
        trend_counts = Counter(e["score_trend"] for e in evolutions)
        print(f"\n  Score Trends:")
        for trend, count in trend_counts.most_common():
            print(f"    {trend:<12s}: {count}")

        exp_counts = Counter(e["experimentation_level"] for e in evolutions)
        print(f"\n  Experimentation Levels:")
        for level, count in exp_counts.most_common():
            print(f"    {level:<12s}: {count}")

        # Most interesting: high experimentation + improving
        improving_experimenters = [
            e for e in evolutions
            if e["score_trend"] == "improving"
            and e["experimentation_level"] in ("medium", "high")
        ]
        if improving_experimenters:
            print(f"\n  Improving experimenters (testing + improving):")
            for e in improving_experimenters:
                adv_safe = e["advertiser"][:40].encode("ascii", "replace").decode("ascii")
                print(f"    - {adv_safe} ({e['total_ads']} ads, {e['changes']['total_strategy_shifts']} shifts)")

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
