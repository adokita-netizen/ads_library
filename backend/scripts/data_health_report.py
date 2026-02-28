"""Data health report: assess the quality and completeness of ad data.

Generates a comprehensive report showing:
  - NULL rates per column
  - creative_type distribution
  - hit_level distribution
  - Score statistics (mean, median, min, max)
  - Running vs stopped ratio
  - Media cache coverage
  - Creative analysis coverage
  - Score distribution histogram
  - Overall data quality assessment (target: Grade A)

Run from the backend directory:
    cd backend
    python scripts/data_health_report.py
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics


# ── Helper Functions ─────────────────────────────────────────────


def pct(numerator: int, denominator: int) -> str:
    """Format as percentage string."""
    if denominator == 0:
        return "N/A"
    return f"{numerator / denominator * 100:.1f}%"


def bar_chart(value: float, max_value: float, width: int = 30) -> str:
    """Create a simple ASCII bar chart."""
    if max_value <= 0:
        return ""
    filled = int(value / max_value * width)
    return "#" * filled + "." * (width - filled)


def quality_grade(fill_rate: float) -> str:
    """Grade data quality based on fill rate percentage."""
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


# ── Report Sections ──────────────────────────────────────────────


def report_null_rates(ads: list[Ad], total: int):
    """Report NULL rates for key columns."""
    print()
    print("=" * 60)
    print("SECTION 1: NULL RATES (Key Columns)")
    print("=" * 60)
    print(f"{'Column':<28s} {'Filled':>7s} {'NULL':>7s} {'Fill%':>7s}")
    print("-" * 60)

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
        ("snapshot_url", lambda a: a.snapshot_url),
        ("destination_url", lambda a: a.destination_url),
        ("external_id", lambda a: a.external_id),
        ("first_seen_at", lambda a: a.first_seen_at),
        ("last_seen_at", lambda a: a.last_seen_at),
        ("view_count", lambda a: a.view_count),
        ("like_count", lambda a: a.like_count),
        ("estimated_impressions", lambda a: a.estimated_impressions),
        ("spend", lambda a: a.spend),
    ]

    fill_rates = []
    for col_name, getter in columns:
        filled = sum(1 for a in ads if getter(a) is not None)
        null_count = total - filled
        fill_rate = (filled / total * 100) if total > 0 else 0
        fill_rates.append(fill_rate)
        bar = bar_chart(fill_rate, 100, 20)
        print(f"  {col_name:<26s} {filled:>6d} {null_count:>6d} {fill_rate:>6.1f}% {bar}")

    # Metadata-based columns
    print()
    print("Metadata fields:")
    print("-" * 60)

    meta_columns = [
        ("hit_score", "latest_hit_score"),
        ("hit_level", "hit_level"),
        ("is_still_running", "is_still_running"),
        ("days_running", "days_running"),
        ("longevity_class", "longevity_class"),
        ("score_breakdown", "latest_score_breakdown"),
        ("page_id", "page_id"),
        ("survival_checked_at", "survival_checked_at"),
        ("last_checked_at", "last_checked_at"),
    ]

    for display_name, meta_key in meta_columns:
        filled = sum(
            1 for a in ads
            if (a.ad_metadata or {}).get(meta_key) is not None
        )
        null_count = total - filled
        fill_rate = (filled / total * 100) if total > 0 else 0
        fill_rates.append(fill_rate)
        bar = bar_chart(fill_rate, 100, 20)
        print(f"  {display_name:<26s} {filled:>6d} {null_count:>6d} {fill_rate:>6.1f}% {bar}")

    # Overall average fill rate
    avg_fill = mean(fill_rates) if fill_rates else 0
    print()
    print(f"  Average fill rate: {avg_fill:.1f}%")
    return avg_fill


def report_creative_type(ads: list[Ad], total: int):
    """Report creative_type distribution."""
    print()
    print("=" * 60)
    print("SECTION 2: CREATIVE TYPE DISTRIBUTION")
    print("=" * 60)

    counts: dict[str, int] = {}
    for ad in ads:
        ct = ad.creative_type or "NULL"
        counts[ct] = counts.get(ct, 0) + 1

    max_count = max(counts.values()) if counts else 1
    for ct, count in sorted(counts.items(), key=lambda x: -x[1]):
        bar = bar_chart(count, max_count, 25)
        print(f"  {ct:<20s} {count:>5d} ({pct(count, total):>6s}) {bar}")


def report_hit_level(ads: list[Ad], total: int):
    """Report hit_level distribution."""
    print()
    print("=" * 60)
    print("SECTION 3: HIT LEVEL DISTRIBUTION")
    print("=" * 60)

    counts: dict[str, int] = {}
    for ad in ads:
        hl = (ad.ad_metadata or {}).get("hit_level", "not_scored")
        counts[hl] = counts.get(hl, 0) + 1

    max_count = max(counts.values()) if counts else 1
    for hl, count in sorted(counts.items(), key=lambda x: -x[1]):
        bar = bar_chart(count, max_count, 25)
        print(f"  {hl:<20s} {count:>5d} ({pct(count, total):>6s}) {bar}")


def report_score_stats(ads: list[Ad]):
    """Report score statistics."""
    print()
    print("=" * 60)
    print("SECTION 4: HIT SCORE STATISTICS")
    print("=" * 60)

    scores = []
    for ad in ads:
        score = (ad.ad_metadata or {}).get("latest_hit_score")
        if score is not None:
            try:
                scores.append(float(score))
            except (ValueError, TypeError):
                pass

    if not scores:
        print("  No ads with hit_score found.")
        return

    scores.sort()
    avg = mean(scores)
    med = median(scores)
    min_s = min(scores)
    max_s = max(scores)

    print(f"  Ads with score: {len(scores)}")
    print(f"  Mean:           {avg:.1f}")
    print(f"  Median:         {med:.1f}")
    print(f"  Min:            {min_s:.1f}")
    print(f"  Max:            {max_s:.1f}")

    # Score distribution buckets
    print()
    print("  Score distribution:")
    buckets = {
        "0-19": 0, "20-39": 0, "40-59": 0,
        "60-79": 0, "80-100": 0,
    }
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

    max_bucket = max(buckets.values()) if buckets else 1
    for label, count in buckets.items():
        bar = bar_chart(count, max_bucket, 25)
        print(f"    {label:>7s}: {count:>4d} {bar}")


def report_running_status(ads: list[Ad], total: int):
    """Report running vs stopped ratio."""
    print()
    print("=" * 60)
    print("SECTION 5: DELIVERY STATUS")
    print("=" * 60)

    running = 0
    stopped = 0
    unknown = 0

    for ad in ads:
        status = (ad.ad_metadata or {}).get("is_still_running")
        if status is True:
            running += 1
        elif status is False:
            stopped += 1
        else:
            unknown += 1

    print(f"  Running:  {running:>5d} ({pct(running, total):>6s})")
    print(f"  Stopped:  {stopped:>5d} ({pct(stopped, total):>6s})")
    print(f"  Unknown:  {unknown:>5d} ({pct(unknown, total):>6s})")

    # Longevity distribution
    print()
    print("  Longevity classification:")
    longevity: dict[str, int] = {}
    for ad in ads:
        lc = (ad.ad_metadata or {}).get("longevity_class", "unclassified")
        longevity[lc] = longevity.get(lc, 0) + 1

    max_lc = max(longevity.values()) if longevity else 1
    for lc, count in sorted(longevity.items(), key=lambda x: -x[1]):
        bar = bar_chart(count, max_lc, 20)
        print(f"    {lc:<18s} {count:>5d} ({pct(count, total):>6s}) {bar}")


def report_platform_distribution(ads: list[Ad], total: int):
    """Report platform distribution."""
    print()
    print("=" * 60)
    print("SECTION 6: PLATFORM DISTRIBUTION")
    print("=" * 60)

    counts: dict[str, int] = {}
    for ad in ads:
        p = ad.platform.value if ad.platform else "unknown"
        counts[p] = counts.get(p, 0) + 1

    max_count = max(counts.values()) if counts else 1
    for p, count in sorted(counts.items(), key=lambda x: -x[1]):
        bar = bar_chart(count, max_count, 25)
        print(f"  {p:<20s} {count:>5d} ({pct(count, total):>6s}) {bar}")


def report_metrics_coverage(session, ads: list[Ad]):
    """Report AdDailyMetrics coverage."""
    print()
    print("=" * 60)
    print("SECTION 7: METRICS COVERAGE")
    print("=" * 60)

    total_ads = len(ads)
    ad_ids = [a.id for a in ads]

    if not ad_ids:
        print("  No ads found.")
        return

    # Count ads that have at least one metric row
    ads_with_metrics = (
        session.query(func.count(func.distinct(AdDailyMetrics.ad_id)))
        .filter(AdDailyMetrics.ad_id.in_(ad_ids))
        .scalar()
    ) or 0

    total_metric_rows = (
        session.query(func.count(AdDailyMetrics.id))
        .filter(AdDailyMetrics.ad_id.in_(ad_ids))
        .scalar()
    ) or 0

    avg_rows = total_metric_rows / ads_with_metrics if ads_with_metrics > 0 else 0

    print(f"  Ads with metrics:    {ads_with_metrics}/{total_ads} ({pct(ads_with_metrics, total_ads)})")
    print(f"  Total metric rows:   {total_metric_rows}")
    print(f"  Avg rows per ad:     {avg_rows:.1f}")
    print(f"  Ads without metrics: {total_ads - ads_with_metrics}")


def report_data_freshness(ads: list[Ad]):
    """Report data freshness based on timestamps."""
    print()
    print("=" * 60)
    print("SECTION 8: DATA FRESHNESS")
    print("=" * 60)

    now = datetime.now(timezone.utc)

    # Last survival check
    checked_times = []
    for ad in ads:
        checked = (ad.ad_metadata or {}).get("last_checked_at") or (ad.ad_metadata or {}).get("survival_checked_at")
        if checked:
            try:
                dt = datetime.fromisoformat(checked.replace("Z", "+00:00"))
                checked_times.append(dt)
            except (ValueError, TypeError):
                pass

    if checked_times:
        latest_check = max(checked_times)
        oldest_check = min(checked_times)
        hours_since_latest = (now - latest_check).total_seconds() / 3600
        print(f"  Latest survival check: {latest_check.isoformat()} ({hours_since_latest:.1f}h ago)")
        print(f"  Oldest survival check: {oldest_check.isoformat()}")
        print(f"  Ads with check:        {len(checked_times)}/{len(ads)}")
    else:
        print("  No survival checks recorded.")

    # Last updated
    updated_times = [ad.updated_at for ad in ads if ad.updated_at]
    if updated_times:
        latest_update = max(updated_times)
        if latest_update.tzinfo is None:
            latest_update = latest_update.replace(tzinfo=timezone.utc)
        hours_since_update = (now - latest_update).total_seconds() / 3600
        print(f"  Latest record update:  {latest_update.isoformat()} ({hours_since_update:.1f}h ago)")

    # Score freshness
    score_times = []
    for ad in ads:
        scored_at = (ad.ad_metadata or {}).get("score_updated_at")
        if scored_at:
            try:
                dt = datetime.fromisoformat(scored_at.replace("Z", "+00:00"))
                score_times.append(dt)
            except (ValueError, TypeError):
                pass

    if score_times:
        latest_score = max(score_times)
        hours_since_score = (now - latest_score).total_seconds() / 3600
        print(f"  Latest score update:   {latest_score.isoformat()} ({hours_since_score:.1f}h ago)")
        print(f"  Ads with score:        {len(score_times)}/{len(ads)}")


MEDIA_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "media_cache",
)


def report_media_cache(ads: list[Ad], total: int):
    """Report media cache coverage (thumbnails, images, videos)."""
    print()
    print("=" * 60)
    print("SECTION 9: MEDIA CACHE COVERAGE")
    print("=" * 60)

    cache_stats: dict[str, set[str]] = {}
    for subdir in ["thumbnails", "images", "videos"]:
        dirpath = os.path.join(MEDIA_CACHE_DIR, subdir)
        if os.path.isdir(dirpath):
            cache_stats[subdir] = {Path(f).stem for f in os.listdir(dirpath)}
        else:
            cache_stats[subdir] = set()

    ad_ids = {str(a.id) for a in ads}

    for subdir in ["thumbnails", "images", "videos"]:
        cached = cache_stats[subdir]
        matched = cached & ad_ids
        print(f"  {subdir}:")
        print(f"    Files on disk:  {len(cached)}")
        print(f"    Matched to ads: {len(matched)}/{total} ({pct(len(matched), total)})")

    # Also check media_cache_status from metadata
    has_meta_thumb = sum(
        1 for a in ads
        if (a.ad_metadata or {}).get("media_cache_status", {}).get("has_cached_thumbnail")
    )
    has_meta_image = sum(
        1 for a in ads
        if (a.ad_metadata or {}).get("media_cache_status", {}).get("has_cached_image")
    )
    print(f"\n  From ad_metadata.media_cache_status:")
    print(f"    has_cached_thumbnail: {has_meta_thumb}/{total}")
    print(f"    has_cached_image:     {has_meta_image}/{total}")


def report_creative_analysis_coverage(ads: list[Ad], total: int):
    """Report creative analysis coverage and field distribution."""
    print()
    print("=" * 60)
    print("SECTION 10: CREATIVE ANALYSIS COVERAGE")
    print("=" * 60)

    with_analysis = sum(
        1 for a in ads if (a.ad_metadata or {}).get("creative_analysis")
    )
    without = total - with_analysis
    print(f"  Ads with creative_analysis: {with_analysis}/{total} ({pct(with_analysis, total)})")
    print(f"  Ads without:                {without}")

    if with_analysis == 0:
        return

    # Field coverage within creative_analysis
    fields = ["hook_type", "cta_type", "offer_type", "emotion",
              "destination_type", "text_length"]
    print(f"\n  Field distributions (analyzed ads only):")
    for field in fields:
        counts: dict[str, int] = {}
        for a in ads:
            ca = (a.ad_metadata or {}).get("creative_analysis", {})
            if ca:
                val = ca.get(field, "N/A")
                counts[val] = counts.get(val, 0) + 1
        if counts:
            top3 = sorted(counts.items(), key=lambda x: -x[1])[:3]
            top_str = ", ".join(f"{k}:{v}" for k, v in top3)
            print(f"    {field:<18s} top: {top_str}")


def report_score_histogram(ads: list[Ad]):
    """Print a detailed ASCII histogram of score distribution."""
    print()
    print("=" * 60)
    print("SECTION 11: SCORE DISTRIBUTION HISTOGRAM")
    print("=" * 60)

    scores = []
    for ad in ads:
        score = (ad.ad_metadata or {}).get("latest_hit_score")
        if score is not None:
            try:
                scores.append(float(score))
            except (ValueError, TypeError):
                pass

    if not scores:
        print("  No scores available.")
        return

    # 10-point buckets for detailed view
    buckets = {}
    for i in range(0, 100, 10):
        label = f"{i:>2d}-{i+9}"
        buckets[label] = 0

    for s in scores:
        idx = min(int(s // 10), 9)
        label = f"{idx*10:>2d}-{idx*10+9}"
        buckets[label] = buckets.get(label, 0) + 1

    max_count = max(buckets.values()) if buckets else 1
    for label, count in buckets.items():
        bar = "#" * int(count / max_count * 40) if max_count > 0 else ""
        print(f"  {label}: {count:>4d} {bar}")


def report_overall_assessment(avg_fill_rate: float, total: int, ads: list[Ad]):
    """Provide an overall data quality assessment."""
    print()
    print("=" * 60)
    print("OVERALL ASSESSMENT")
    print("=" * 60)

    grade = quality_grade(avg_fill_rate)
    print(f"  Data Quality Grade: {grade}")
    print(f"  Average Fill Rate:  {avg_fill_rate:.1f}%")
    print(f"  Total Records:      {total}")

    # Identify critical issues
    issues = []
    warnings = []

    # Check key fields
    no_title = sum(1 for a in ads if not a.title)
    if no_title > total * 0.1:
        issues.append(f"{no_title} ads missing title ({pct(no_title, total)})")

    no_advertiser = sum(1 for a in ads if not a.advertiser_name)
    if no_advertiser > total * 0.1:
        issues.append(f"{no_advertiser} ads missing advertiser_name ({pct(no_advertiser, total)})")

    no_score = sum(1 for a in ads if (a.ad_metadata or {}).get("latest_hit_score") is None)
    if no_score > total * 0.2:
        warnings.append(f"{no_score} ads without hit_score ({pct(no_score, total)})")

    no_survival = sum(1 for a in ads if (a.ad_metadata or {}).get("is_still_running") is None)
    if no_survival > total * 0.3:
        warnings.append(f"{no_survival} ads with unknown running status ({pct(no_survival, total)})")

    no_creative = sum(1 for a in ads if not a.creative_type)
    if no_creative > total * 0.2:
        warnings.append(f"{no_creative} ads missing creative_type ({pct(no_creative, total)})")

    no_dest = sum(1 for a in ads if not a.destination_url)
    if no_dest > total * 0.3:
        warnings.append(f"{no_dest} ads missing destination_url ({pct(no_dest, total)})")

    if issues:
        print()
        print("  CRITICAL ISSUES:")
        for issue in issues:
            print(f"    [!] {issue}")

    if warnings:
        print()
        print("  WARNINGS:")
        for warning in warnings:
            print(f"    [?] {warning}")

    if not issues and not warnings:
        print()
        print("  No critical issues detected. Data is in good shape!")

    print()
    usable = avg_fill_rate >= 50 and not issues
    if usable:
        print("  Verdict: Data IS usable for analysis.")
    else:
        print("  Verdict: Data needs improvement before reliable analysis.")


# ── Main ──────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("DATA HEALTH REPORT")
    print(f"Generated at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)

        if total == 0:
            print()
            print("No ads found in database. Nothing to report.")
            return

        print(f"Total ads in database: {total}")

        # Run all report sections
        avg_fill = report_null_rates(ads, total)
        report_creative_type(ads, total)
        report_hit_level(ads, total)
        report_score_stats(ads)
        report_running_status(ads, total)
        report_platform_distribution(ads, total)
        report_metrics_coverage(session, ads)
        report_data_freshness(ads)
        report_media_cache(ads, total)
        report_creative_analysis_coverage(ads, total)
        report_score_histogram(ads)
        report_overall_assessment(avg_fill, total, ads)

        print()
        print("Done!")

    except Exception as e:
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
