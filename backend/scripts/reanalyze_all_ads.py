#!/usr/bin/env python3
"""Comprehensive re-analysis script for all ads (old + newly crawled).

Performs 6 phases in sequence:
  1. Creative analysis   - Run analyze_creative_elements for ads missing it
  2. Longevity class     - Compute and set longevity_class for ads missing it
  3. last_seen_at fix    - Fill NULL last_seen_at with created_at or now()
  4. Hit score recompute - Recompute hit_score for ALL ads using v2 multi-signal model
  5. Hit pattern report  - Regenerate backend/exports/hit_pattern_report.json
  6. Data health check   - Print full data quality report and grade

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/reanalyze_all_ads.py
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics, ProductRanking
from app.services.ranking.ranking_service import compute_hit_score, compute_genre_stats

# Import creative analysis function from existing script
from scripts.analyze_creative_elements import analyze_ad

# Import hit pattern functions from existing script
from scripts.compute_hit_patterns import (
    _get_creative_analysis,
    _is_hit,
    _hit_rate,
    _safe_mean,
    _safe_median,
    aggregate_by_field,
    aggregate_boolean_field,
    find_top_combinations,
    compute_pattern_strength,
)

JST = timezone(timedelta(hours=9))

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)


# ========================================================================
# Helper functions
# ========================================================================

def _classify_longevity(days: int) -> str:
    """Classify ad longevity based on days running."""
    if days >= 91:
        return "long"
    elif days >= 31:
        return "medium"
    elif days >= 8:
        return "short"
    else:
        return "flash"


def _pct(num: int, den: int) -> str:
    if den == 0:
        return "N/A"
    return f"{num / den * 100:.1f}%"


def _bar(value: float, max_value: float, width: int = 20) -> str:
    if max_value <= 0:
        return ""
    filled = int(value / max_value * width)
    return "#" * filled + "." * (width - filled)


def _quality_grade(fill_rate: float) -> str:
    if fill_rate >= 90:
        return "A (Excellent)"
    elif fill_rate >= 70:
        return "B (Good)"
    elif fill_rate >= 50:
        return "C (Acceptable)"
    elif fill_rate >= 30:
        return "D (Poor)"
    else:
        return "F (Critical)"


# ========================================================================
# Phase 1: Creative analysis for ads missing it
# ========================================================================

def phase_1_creative_analysis(session, ads: list[Ad]) -> int:
    """Run creative_analysis on ads that are missing it. Returns count updated."""
    print()
    print("=" * 60)
    print("PHASE 1: Creative Analysis (missing ads only)")
    print("=" * 60)

    creative_added = 0
    creative_existed = 0

    for ad in ads:
        meta = dict(ad.ad_metadata or {})
        if meta.get("creative_analysis"):
            creative_existed += 1
            continue

        analysis = analyze_ad(ad)
        meta["creative_analysis"] = analysis
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")
        creative_added += 1

        if creative_added <= 5:
            title_safe = (ad.title or "")[:40].encode("ascii", "replace").decode("ascii")
            print(f"    [ID:{ad.id}] hook={analysis['hook_type']} "
                  f"cta={analysis['cta_type']} title={title_safe!r}")
        elif creative_added == 6:
            print(f"    ... (more follow)")

    session.commit()
    print(f"  Already had creative_analysis: {creative_existed}")
    print(f"  Newly analyzed: {creative_added}")
    return creative_added


# ========================================================================
# Phase 2: Fix missing longevity_class
# ========================================================================

def phase_2_longevity_class(session, ads: list[Ad]) -> int:
    """Compute and set longevity_class for ads missing it. Returns count updated."""
    print()
    print("=" * 60)
    print("PHASE 2: Longevity Classification (missing ads only)")
    print("=" * 60)

    now = datetime.now(timezone.utc)
    longevity_added = 0
    longevity_existed = 0
    class_counts: dict[str, int] = {}

    for ad in ads:
        meta = dict(ad.ad_metadata or {})

        if meta.get("longevity_class"):
            longevity_existed += 1
            lc = meta["longevity_class"]
            class_counts[lc] = class_counts.get(lc, 0) + 1
            continue

        days = meta.get("days_running")
        if days is None:
            if ad.first_seen_at:
                first = ad.first_seen_at
                if first.tzinfo is None:
                    first = first.replace(tzinfo=timezone.utc)
                end = ad.last_seen_at or now
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                days = max(1, (end - first).days)
            else:
                created = ad.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                days = max(1, (now - created).days)
            meta["days_running"] = days

        longevity = _classify_longevity(days)
        meta["longevity_class"] = longevity
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")

        class_counts[longevity] = class_counts.get(longevity, 0) + 1
        longevity_added += 1

    session.commit()
    print(f"  Already had longevity_class: {longevity_existed}")
    print(f"  Newly classified: {longevity_added}")
    print(f"  Distribution: {dict(sorted(class_counts.items()))}")
    return longevity_added


# ========================================================================
# Phase 3: Fix missing last_seen_at
# ========================================================================

def phase_3_last_seen_at(session, ads: list[Ad]) -> int:
    """Set last_seen_at for ads where it is NULL. Returns count updated."""
    print()
    print("=" * 60)
    print("PHASE 3: Fix Missing last_seen_at")
    print("=" * 60)

    now = datetime.now(timezone.utc)
    last_seen_ok = 0
    last_seen_fixed = 0
    method_counts = {"running_today": 0, "survival_checked": 0,
                     "created_at": 0, "now_fallback": 0}

    for ad in ads:
        if ad.last_seen_at is not None:
            last_seen_ok += 1
            continue

        meta = ad.ad_metadata or {}
        is_running = meta.get("is_still_running")

        if is_running is True:
            ad.last_seen_at = now
            method_counts["running_today"] += 1
        elif is_running is False and meta.get("survival_checked_at"):
            try:
                checked_str = meta["survival_checked_at"]
                ad.last_seen_at = datetime.fromisoformat(
                    checked_str.replace("Z", "+00:00")
                )
                method_counts["survival_checked"] += 1
            except (ValueError, TypeError):
                ad.last_seen_at = ad.created_at or now
                method_counts["created_at"] += 1
        elif ad.created_at:
            ad.last_seen_at = ad.created_at
            method_counts["created_at"] += 1
        else:
            ad.last_seen_at = now
            method_counts["now_fallback"] += 1

        last_seen_fixed += 1

    session.commit()
    print(f"  Already had last_seen_at: {last_seen_ok}")
    print(f"  Newly set: {last_seen_fixed}")
    if last_seen_fixed > 0:
        print(f"  Methods: {method_counts}")
    return last_seen_fixed


# ========================================================================
# Phase 4: Recompute hit_score for ALL ads
# ========================================================================

def phase_4_hit_scores(session, ads: list[Ad]) -> int:
    """Recompute hit_score for ALL ads using v2 multi-signal model. Returns count updated."""
    print()
    print("=" * 60)
    print("PHASE 4: Recompute Hit Scores (ALL ads)")
    print("=" * 60)

    total = len(ads)
    if total == 0:
        print("  No ads found. Skipping.")
        return 0

    now = datetime.now(timezone.utc)

    # Period: last 30 days
    yesterday = (datetime.now(JST) - timedelta(days=1)).date()
    period_start = yesterday - timedelta(days=29)
    period_end = yesterday
    print(f"  Score period: {period_start} -> {period_end}")

    # Pre-compute genre statistics
    genre_stats = compute_genre_stats(session, period_start, period_end)
    print(f"  Genre stats computed for {len(genre_stats)} genres")
    for g, s in genre_stats.items():
        print(f"    {g}: ads={s['ad_count']}, max_spend={s['max_spend']:.0f}")

    # Pre-fetch all ad metrics
    all_metrics = (
        session.query(AdDailyMetrics)
        .filter(
            AdDailyMetrics.metric_date >= period_start,
            AdDailyMetrics.metric_date <= period_end,
        )
        .order_by(AdDailyMetrics.metric_date)
        .all()
    )
    ad_metrics_map: dict[int, list] = {}
    for m in all_metrics:
        ad_metrics_map.setdefault(m.ad_id, []).append(m)
    print(f"  {len(all_metrics)} metric rows fetched")

    # Compute scores for all ads
    hit_count = 0
    mega_hit_count = 0
    scores: list[float] = []
    top_ads: list[dict] = []

    print("  Computing scores...")
    for ad in ads:
        ad_metrics = ad_metrics_map.get(ad.id, [])
        genre = None
        if ad_metrics:
            genre = ad_metrics[0].genre
        if not genre and ad.category:
            genre = str(ad.category.value)
        genre = genre or "other"
        g_stats = genre_stats.get(genre, {})

        score, is_hit, hit_level, breakdown = compute_hit_score(
            ad, metrics=ad_metrics, genre_stats=g_stats,
        )
        scores.append(score)

        # Update ad_metadata
        meta = dict(ad.ad_metadata or {})
        meta["latest_hit_score"] = score
        meta["latest_score_breakdown"] = breakdown
        meta["hit_level"] = hit_level
        meta["is_hit"] = is_hit
        meta["score_updated_at"] = now.isoformat()
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")

        if hit_level == "hit":
            hit_count += 1
        elif hit_level == "mega_hit":
            mega_hit_count += 1

        days_running = meta.get("days_running", 0)
        if days_running == 0 and ad.first_seen_at:
            first = ad.first_seen_at
            if first.tzinfo is None:
                first = first.replace(tzinfo=timezone.utc)
            days_running = max(1, (now - first).days)

        top_ads.append({
            "id": ad.id,
            "title": (ad.title or "")[:50],
            "score": score,
            "hit_level": hit_level,
            "days": days_running,
        })

    # Update ProductRanking records if they exist
    rankings = session.query(ProductRanking).all()
    ad_score_map = {a["id"]: a for a in top_ads}
    rankings_updated = 0
    for ranking in rankings:
        info = ad_score_map.get(ranking.ad_id)
        if info:
            ranking.hit_score = info["score"]
            ranking.is_hit = info["hit_level"] in ("hit", "mega_hit")
            ad_obj = session.query(Ad).get(ranking.ad_id)
            ad_meta = (ad_obj.ad_metadata or {}) if ad_obj else {}
            extra = dict(ranking.extra_metadata or {})
            extra["hit_level"] = info["hit_level"]
            extra["score_breakdown"] = ad_meta.get("latest_score_breakdown", {})
            ranking.extra_metadata = extra
            flag_modified(ranking, "extra_metadata")
            rankings_updated += 1

    session.commit()

    # Print statistics
    avg_score = mean(scores) if scores else 0
    print(f"  Ads scored: {total}")
    print(f"  ProductRanking updated: {rankings_updated}")
    print(f"  Hit: {hit_count}, Mega-hit: {mega_hit_count}")
    print(f"  Avg score: {avg_score:.1f}, "
          f"Max: {max(scores):.1f}, Min: {min(scores):.1f}")

    # Top 10
    top_ads.sort(key=lambda x: x["score"], reverse=True)
    print(f"\n  Top 10 Ads:")
    for i, a in enumerate(top_ads[:10], 1):
        title_safe = a["title"].encode("ascii", "replace").decode("ascii")
        print(f"    {i:2d}. [ID:{a['id']:>4d}] score:{a['score']:>5.1f} "
              f"days:{a['days']:>4d} {a['hit_level']} - {title_safe}")

    # Score distribution
    buckets = {"0-19": 0, "20-39": 0, "40-59": 0, "60-79": 0, "80-100": 0}
    for s in scores:
        if s < 20:
            buckets["0-19"] += 1
        elif s < 40:
            buckets["20-39"] += 1
        elif s < 60:
            buckets["40-59"] += 1
        elif s < 80:
            buckets["60-79"] += 1
        else:
            buckets["80-100"] += 1

    print(f"\n  Score Distribution:")
    for label, count in buckets.items():
        bar = "#" * (count * 2)
        print(f"    {label:>7s}: {count:>3d} {bar}")

    return total


# ========================================================================
# Phase 5: Recompute hit_pattern_report.json
# ========================================================================

def phase_5_hit_patterns(session, ads: list[Ad]) -> str:
    """Regenerate hit_pattern_report.json from all ads. Returns report path."""
    print()
    print("=" * 60)
    print("PHASE 5: Recompute Hit Pattern Report")
    print("=" * 60)

    analyzed = [a for a in ads if _get_creative_analysis(a)]
    print(f"  Total ads: {len(ads)}")
    print(f"  Ads with creative_analysis: {len(analyzed)}")

    if not analyzed:
        print("  ERROR: No ads have creative_analysis. Cannot generate report.")
        return ""

    hit_ads = [a for a in analyzed if _is_hit(a)]
    non_hit_ads = [a for a in analyzed if not _is_hit(a)]
    print(f"  Hit ads: {len(hit_ads)} ({_hit_rate(len(hit_ads), len(analyzed))}%)")
    print(f"  Non-hit ads: {len(non_hit_ads)}")

    # Aggregate by each field
    print("  Aggregating by creative fields...")
    hook_stats = aggregate_by_field(analyzed, "hook_type")
    cta_stats = aggregate_by_field(analyzed, "cta_type")
    offer_stats = aggregate_by_field(analyzed, "offer_type")
    emotion_stats = aggregate_by_field(analyzed, "emotion")
    dest_stats = aggregate_by_field(analyzed, "destination_type")
    text_stats = aggregate_by_field(analyzed, "text_length")

    emoji_stats = aggregate_boolean_field(analyzed, "has_emoji")
    numbers_stats = aggregate_boolean_field(analyzed, "has_numbers")
    testimonial_stats = aggregate_boolean_field(analyzed, "has_testimonial")
    before_after_stats = aggregate_boolean_field(analyzed, "has_before_after")

    # Top combinations
    print("  Finding top pattern combinations...")
    top_combos = find_top_combinations(analyzed, top_n=15)

    # Pattern strength ranks
    print("  Computing pattern strength ranks...")
    ad_ranks = compute_pattern_strength(analyzed)

    rank_updated = 0
    for ad in ads:
        rank = ad_ranks.get(ad.id)
        if rank is not None:
            meta = dict(ad.ad_metadata or {})
            meta["hit_pattern_rank"] = rank
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            rank_updated += 1

    session.commit()
    print(f"  Updated hit_pattern_rank for {rank_updated} ads.")

    # Generate insights
    insights = []

    for field_name, stats in [
        ("hook type", hook_stats),
        ("CTA type", cta_stats),
        ("offer type", offer_stats),
        ("emotional appeal", emotion_stats),
    ]:
        if stats:
            best = max(
                ((k, v) for k, v in stats.items() if v["total"] >= 3),
                key=lambda x: x[1]["avg_score"],
                default=None,
            )
            if best:
                insights.append(
                    f"Best {field_name}: '{best[0]}' "
                    f"(avg score {best[1]['avg_score']}, "
                    f"hit rate {best[1]['hit_rate']}%, "
                    f"n={best[1]['total']})"
                )

    # Boolean insights
    for field_label, bool_stats in [
        ("emoji", emoji_stats),
        ("numbers", numbers_stats),
        ("testimonial", testimonial_stats),
    ]:
        t = bool_stats.get("true", {})
        f_data = bool_stats.get("false", {})
        if t.get("total", 0) >= 3 and f_data.get("total", 0) >= 3:
            diff = t["avg_score"] - f_data["avg_score"]
            if abs(diff) >= 3:
                better = "with" if diff > 0 else "without"
                insights.append(
                    f"Ads {better} {field_label}: "
                    f"avg score {max(t['avg_score'], f_data['avg_score']):.1f} vs "
                    f"{min(t['avg_score'], f_data['avg_score']):.1f} "
                    f"(delta={abs(diff):.1f})"
                )

    if top_combos:
        top = top_combos[0]
        insights.append(
            f"Strongest pattern combo: "
            f"hook={top['hook_type']}, cta={top['cta_type']}, "
            f"offer={top['offer_type']}, emotion={top['emotion']} "
            f"(avg score {top['avg_score']}, hit rate {top['hit_rate']}%, "
            f"n={top['total']})"
        )

    # Build report
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_ads": len(ads),
        "analyzed_ads": len(analyzed),
        "hit_ads": len(hit_ads),
        "non_hit_ads": len(non_hit_ads),
        "overall_hit_rate": _hit_rate(len(hit_ads), len(analyzed)),
        "analysis": {
            "hook_type": hook_stats,
            "cta_type": cta_stats,
            "offer_type": offer_stats,
            "emotion": emotion_stats,
            "destination_type": dest_stats,
            "text_length": text_stats,
            "has_emoji": emoji_stats,
            "has_numbers": numbers_stats,
            "has_testimonial": testimonial_stats,
            "has_before_after": before_after_stats,
        },
        "top_combinations": top_combos,
        "insights": insights,
    }

    # Save report
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    report_path = os.path.join(EXPORTS_DIR, "hit_pattern_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"  Report saved to: {report_path}")

    # Print top insights
    if insights:
        print(f"\n  Key insights:")
        for i, ins in enumerate(insights, 1):
            print(f"    {i}. {ins}")

    return report_path


# ========================================================================
# Phase 6: Data health check
# ========================================================================

def phase_6_health_check(session, ads: list[Ad]):
    """Run data health check and print report."""
    print()
    print("=" * 60)
    print("PHASE 6: Data Health Check")
    print("=" * 60)

    total = len(ads)
    if total == 0:
        print("  No ads found. Skipping.")
        return

    # Direct model columns
    columns = [
        ("title", lambda a: a.title),
        ("description", lambda a: a.description),
        ("advertiser_name", lambda a: a.advertiser_name),
        ("brand_name", lambda a: a.brand_name),
        ("category", lambda a: a.category),
        ("creative_type", lambda a: a.creative_type),
        ("video_url", lambda a: a.video_url),
        ("image_url", lambda a: a.image_url),
        ("thumbnail_url", lambda a: a.thumbnail_url),
        ("destination_url", lambda a: a.destination_url),
        ("first_seen_at", lambda a: a.first_seen_at),
        ("last_seen_at", lambda a: a.last_seen_at),
    ]

    meta_columns = [
        ("hit_score", "latest_hit_score"),
        ("hit_level", "hit_level"),
        ("is_still_running", "is_still_running"),
        ("days_running", "days_running"),
        ("longevity_class", "longevity_class"),
        ("creative_analysis", "creative_analysis"),
        ("score_breakdown", "latest_score_breakdown"),
    ]

    fill_rates: list[float] = []

    print(f"\n  {'Column':<24s} {'Filled':>7s} {'NULL':>7s} {'Fill%':>7s}")
    print(f"  {'-' * 55}")

    for col_name, getter in columns:
        filled = sum(1 for a in ads if getter(a) is not None)
        null_count = total - filled
        fill_rate = (filled / total * 100) if total > 0 else 0
        fill_rates.append(fill_rate)
        bar = _bar(fill_rate, 100)
        print(f"  {col_name:<24s} {filled:>6d} {null_count:>6d} {fill_rate:>6.1f}% {bar}")

    print(f"\n  Metadata fields:")
    print(f"  {'-' * 55}")
    for display_name, meta_key in meta_columns:
        filled = sum(
            1 for a in ads
            if (a.ad_metadata or {}).get(meta_key) is not None
        )
        null_count = total - filled
        fill_rate = (filled / total * 100) if total > 0 else 0
        fill_rates.append(fill_rate)
        bar = _bar(fill_rate, 100)
        print(f"  {display_name:<24s} {filled:>6d} {null_count:>6d} {fill_rate:>6.1f}% {bar}")

    avg_fill = mean(fill_rates) if fill_rates else 0

    # Hit level distribution
    hit_levels: dict[str, int] = {}
    for ad in ads:
        hl = (ad.ad_metadata or {}).get("hit_level", "not_scored")
        hit_levels[hl] = hit_levels.get(hl, 0) + 1

    print(f"\n  Hit level distribution:")
    for hl, count in sorted(hit_levels.items(), key=lambda x: -x[1]):
        print(f"    {hl:<16s} {count:>5d} ({_pct(count, total)})")

    # Longevity distribution
    longevity: dict[str, int] = {}
    for ad in ads:
        lc = (ad.ad_metadata or {}).get("longevity_class", "unclassified")
        longevity[lc] = longevity.get(lc, 0) + 1

    print(f"\n  Longevity distribution:")
    for lc, count in sorted(longevity.items(), key=lambda x: -x[1]):
        print(f"    {lc:<16s} {count:>5d} ({_pct(count, total)})")

    # Score statistics
    scores: list[float] = []
    for ad in ads:
        score = (ad.ad_metadata or {}).get("latest_hit_score")
        if score is not None:
            try:
                scores.append(float(score))
            except (ValueError, TypeError):
                pass

    if scores:
        print(f"\n  Score statistics ({len(scores)} ads):")
        print(f"    Mean:   {mean(scores):.1f}")
        print(f"    Median: {median(scores):.1f}")
        print(f"    Min:    {min(scores):.1f}")
        print(f"    Max:    {max(scores):.1f}")

    # Overall grade
    grade = _quality_grade(avg_fill)
    print(f"\n  Average fill rate: {avg_fill:.1f}%")
    print(f"  Data Quality Grade: {grade}")

    # Issues / Warnings
    issues: list[str] = []
    no_title = sum(1 for a in ads if not a.title)
    if no_title > total * 0.1:
        issues.append(f"{no_title} ads missing title ({_pct(no_title, total)})")
    no_score = sum(1 for a in ads if (a.ad_metadata or {}).get("latest_hit_score") is None)
    if no_score > total * 0.2:
        issues.append(f"{no_score} ads without hit_score ({_pct(no_score, total)})")
    no_creative = sum(1 for a in ads if not (a.ad_metadata or {}).get("creative_analysis"))
    if no_creative > total * 0.2:
        issues.append(f"{no_creative} ads without creative_analysis ({_pct(no_creative, total)})")
    no_longevity = sum(1 for a in ads if not (a.ad_metadata or {}).get("longevity_class"))
    if no_longevity > total * 0.2:
        issues.append(f"{no_longevity} ads without longevity_class ({_pct(no_longevity, total)})")
    no_last_seen = sum(1 for a in ads if a.last_seen_at is None)
    if no_last_seen > 0:
        issues.append(f"{no_last_seen} ads with NULL last_seen_at ({_pct(no_last_seen, total)})")

    if issues:
        print(f"\n  Warnings:")
        for issue in issues:
            print(f"    [!] {issue}")
    else:
        print(f"\n  No critical issues detected. Data is in good shape!")


# ========================================================================
# Main
# ========================================================================

def main() -> None:
    print("=" * 60)
    print("COMPREHENSIVE AD RE-ANALYSIS SCRIPT")
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

        # Track updates across all phases
        summary: dict[str, object] = {}

        # Phase 1: Creative analysis
        summary["creative_analysis"] = phase_1_creative_analysis(session, ads)
        # Re-fetch to get updated metadata
        ads = session.query(Ad).all()

        # Phase 2: Longevity class
        summary["longevity_class"] = phase_2_longevity_class(session, ads)
        ads = session.query(Ad).all()

        # Phase 3: last_seen_at
        summary["last_seen_at"] = phase_3_last_seen_at(session, ads)
        ads = session.query(Ad).all()

        # Phase 4: Hit scores (ALL ads)
        summary["hit_scores"] = phase_4_hit_scores(session, ads)
        ads = session.query(Ad).all()

        # Phase 5: Hit pattern report
        summary["hit_pattern_report"] = phase_5_hit_patterns(session, ads)
        ads = session.query(Ad).all()

        # Phase 6: Data health check
        phase_6_health_check(session, ads)

        # Final summary
        print()
        print("=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        print(f"  Total ads processed:       {total}")
        print(f"  Creative analysis added:   {summary['creative_analysis']}")
        print(f"  Longevity class added:     {summary['longevity_class']}")
        print(f"  last_seen_at fixed:        {summary['last_seen_at']}")
        print(f"  Hit scores recomputed:     {summary['hit_scores']}")
        report_path = summary.get("hit_pattern_report", "")
        if report_path:
            print(f"  Hit pattern report:        {report_path}")
        print()
        print("All phases completed successfully.")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
