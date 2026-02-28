#!/usr/bin/env python3
"""Competitive report generator: markdown report on top advertisers.

For each top-20 advertiser (by ad count):
  - Ad count, hit rate, avg score
  - Top genre, preferred creative style (hook/cta)
  - Trend direction (growing/stable/declining)
  - Estimated monthly spend

Generates a markdown report with sections:
  Overview, Top Performers, Genre Dominance, Trend Analysis, Key Findings

Exports to backend/exports/competitive_report.md

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/generate_competitive_report.py
"""

import io
import os
import sys
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)


# -- Helpers -----------------------------------------------------------


def _get_score(ad: Ad) -> float:
    """Get hit score from ad_metadata, default 0."""
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_hit(ad: Ad) -> bool:
    """Check if ad is a hit or mega_hit."""
    return (ad.ad_metadata or {}).get("hit_level", "none") in ("hit", "mega_hit")


def _safe_mean(values: list[float]) -> float:
    """Return mean or 0 if empty."""
    return round(mean(values), 1) if values else 0.0


def _most_common(items: list[str]) -> str:
    """Return most common item, or 'N/A' if empty."""
    if not items:
        return "N/A"
    counter = Counter(items)
    return counter.most_common(1)[0][0]


def _get_genre(ad: Ad) -> str:
    """Get fine_genre from ad_metadata, fall back to category."""
    meta = ad.ad_metadata or {}
    fine_genre = meta.get("fine_genre")
    if fine_genre and str(fine_genre).strip():
        return str(fine_genre).strip()
    if ad.category:
        return str(ad.category.value)
    return "other"


def _get_first_seen(ad: Ad) -> datetime | None:
    """Get first_seen_at datetime."""
    return ad.first_seen_at


def _compute_trend(ads: list[Ad]) -> str:
    """Determine trend direction by comparing recent vs older ad scores.

    Split ads into two halves by first_seen_at.  If the recent half has
    a meaningfully higher average score, the trend is 'growing'; if lower,
    'declining'; otherwise 'stable'.
    """
    dated_ads = [
        (a, _get_first_seen(a))
        for a in ads
        if _get_first_seen(a) is not None
    ]
    if len(dated_ads) < 2:
        return "stable"

    dated_ads.sort(key=lambda x: x[1])
    mid = len(dated_ads) // 2
    older_scores = [_get_score(a) for a, _ in dated_ads[:mid]]
    recent_scores = [_get_score(a) for a, _ in dated_ads[mid:]]

    older_avg = _safe_mean(older_scores)
    recent_avg = _safe_mean(recent_scores)

    diff = recent_avg - older_avg
    # Threshold: 5 points difference is meaningful
    if diff > 5:
        return "growing"
    elif diff < -5:
        return "declining"
    return "stable"


def _estimate_monthly_spend(ads: list[Ad]) -> float:
    """Estimate monthly spend: total spend / months active."""
    total_spend = 0.0
    first_dates = []
    last_dates = []

    for ad in ads:
        if ad.spend is not None:
            total_spend += ad.spend
        fs = _get_first_seen(ad)
        if fs is not None:
            first_dates.append(fs)
            # Use last_seen_at if available, otherwise first_seen_at
            ls = ad.last_seen_at if ad.last_seen_at else fs
            last_dates.append(ls)

    if total_spend == 0 or not first_dates or not last_dates:
        return 0.0

    earliest = min(first_dates)
    latest = max(last_dates)
    days_active = (latest - earliest).days
    months_active = max(days_active / 30.0, 1.0)

    return round(total_spend / months_active, 2)


def _get_creative_style(ads: list[Ad]) -> dict:
    """Extract preferred hook and CTA from ad_metadata."""
    hooks = []
    ctas = []
    for ad in ads:
        meta = ad.ad_metadata or {}
        ca = meta.get("creative_analysis", {})
        if isinstance(ca, dict):
            h = ca.get("hook_type")
            if h and str(h) != "none":
                hooks.append(str(h))
            c = ca.get("cta_type")
            if c and str(c) != "none":
                ctas.append(str(c))
    return {
        "preferred_hook": _most_common(hooks),
        "preferred_cta": _most_common(ctas),
    }


# -- Profile builder --------------------------------------------------


def _build_advertiser_data(name: str, ads: list[Ad]) -> dict:
    """Build analytics dict for one advertiser."""
    total = len(ads)
    hit_count = sum(1 for a in ads if _is_hit(a))
    hit_rate = round(hit_count / total * 100, 1) if total > 0 else 0.0
    scores = [_get_score(a) for a in ads]
    avg_score = _safe_mean(scores)

    genres = [_get_genre(a) for a in ads]
    top_genre = _most_common(genres)

    style = _get_creative_style(ads)
    trend = _compute_trend(ads)
    monthly_spend = _estimate_monthly_spend(ads)

    total_views = sum(a.view_count or 0 for a in ads)
    total_spend = sum(a.spend or 0 for a in ads)

    return {
        "name": name,
        "ad_count": total,
        "hit_count": hit_count,
        "hit_rate": hit_rate,
        "avg_score": avg_score,
        "top_genre": top_genre,
        "preferred_hook": style["preferred_hook"],
        "preferred_cta": style["preferred_cta"],
        "trend": trend,
        "monthly_spend": monthly_spend,
        "total_spend": total_spend,
        "total_views": total_views,
    }


# -- Markdown report ---------------------------------------------------


def _generate_markdown(
    advertisers: list[dict],
    genre_dominance: dict[str, list[str]],
    total_ads: int,
    total_advertisers: int,
) -> str:
    """Generate the full markdown report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = []

    # -- Title --
    lines.append("# Competitive Analysis Report")
    lines.append("")
    lines.append("**Generated:** " + now)
    lines.append("")

    # -- Overview --
    lines.append("## Overview")
    lines.append("")
    lines.append("- **Total ads analyzed:** " + str(total_ads))
    lines.append("- **Total advertisers:** " + str(total_advertisers))
    lines.append("- **Top advertisers profiled:** " + str(len(advertisers)))
    lines.append("")

    avg_hit_rate = _safe_mean([a["hit_rate"] for a in advertisers])
    avg_score_all = _safe_mean([a["avg_score"] for a in advertisers])
    total_spend_all = sum(a["total_spend"] for a in advertisers)

    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append("| Avg hit rate (top 20) | " + str(avg_hit_rate) + "% |")
    lines.append("| Avg score (top 20) | " + str(avg_score_all) + " |")
    lines.append("| Combined spend (top 20) | " + "{:,.0f}".format(total_spend_all) + " |")
    lines.append("")

    # -- Top Performers --
    lines.append("## Top Performers")
    lines.append("")
    lines.append(
        "| Rank | Advertiser | Ads | Hit Rate | Avg Score "
        "| Top Genre | Trend | Est. Monthly Spend |"
    )
    lines.append(
        "|------|-----------|-----|----------|----------"
        "|-----------|-------|--------------------|"
    )
    for i, a in enumerate(advertisers, 1):
        name_display = a["name"][:40]
        trend_label = {
            "growing": "Growing",
            "declining": "Declining",
            "stable": "Stable",
        }.get(a["trend"], "Stable")
        lines.append(
            "| " + str(i) + " | " + name_display + " | " + str(a["ad_count"]) + " | "
            + str(a["hit_rate"]) + "% | " + str(a["avg_score"]) + " | "
            + a["top_genre"] + " | " + trend_label + " | "
            + "{:,.0f}".format(a["monthly_spend"]) + " |"
        )
    lines.append("")

    # -- Genre Dominance --
    lines.append("## Genre Dominance")
    lines.append("")
    lines.append("Which genres are dominated by which top-20 advertisers.")
    lines.append("")

    for genre, adv_names in sorted(genre_dominance.items()):
        lines.append("### " + genre)
        lines.append("")
        for name in adv_names:
            match = next((a for a in advertisers if a["name"] == name), None)
            if match:
                lines.append(
                    "- **" + name + "** -- " + str(match["ad_count"]) + " ads, "
                    "hit rate " + str(match["hit_rate"]) + "%"
                )
            else:
                lines.append("- **" + name + "**")
        lines.append("")

    # -- Trend Analysis --
    lines.append("## Trend Analysis")
    lines.append("")

    growing = [a for a in advertisers if a["trend"] == "growing"]
    declining = [a for a in advertisers if a["trend"] == "declining"]
    stable = [a for a in advertisers if a["trend"] == "stable"]

    lines.append("- **Growing:** " + str(len(growing)) + " advertisers")
    lines.append("- **Stable:** " + str(len(stable)) + " advertisers")
    lines.append("- **Declining:** " + str(len(declining)) + " advertisers")
    lines.append("")

    if growing:
        lines.append("### Growing Advertisers")
        lines.append("")
        for a in growing:
            lines.append(
                "- **" + a["name"] + "** -- avg score " + str(a["avg_score"]) + ", "
                + str(a["ad_count"]) + " ads, hit rate " + str(a["hit_rate"]) + "%"
            )
        lines.append("")

    if declining:
        lines.append("### Declining Advertisers")
        lines.append("")
        for a in declining:
            lines.append(
                "- **" + a["name"] + "** -- avg score " + str(a["avg_score"]) + ", "
                + str(a["ad_count"]) + " ads, hit rate " + str(a["hit_rate"]) + "%"
            )
        lines.append("")

    # -- Creative Style Breakdown --
    lines.append("## Creative Style Breakdown")
    lines.append("")
    lines.append("| Advertiser | Preferred Hook | Preferred CTA |")
    lines.append("|-----------|----------------|---------------|")
    for a in advertisers:
        lines.append(
            "| " + a["name"][:40] + " | " + a["preferred_hook"]
            + " | " + a["preferred_cta"] + " |"
        )
    lines.append("")

    # -- Key Findings --
    lines.append("## Key Findings")
    lines.append("")

    findings = _generate_findings(advertisers, genre_dominance)
    for i, finding in enumerate(findings, 1):
        lines.append(str(i) + ". " + finding)
    lines.append("")

    lines.append("---")
    lines.append("*Report generated by VAAP Competitive Analysis Engine*")
    lines.append("")

    return "\n".join(lines)


def _generate_findings(
    advertisers: list[dict],
    genre_dominance: dict[str, list[str]],
) -> list[str]:
    """Generate key findings from the data."""
    findings = []

    if not advertisers:
        findings.append("No advertisers found for analysis.")
        return findings

    # 1. Top advertiser
    top = advertisers[0]
    findings.append(
        "The most active advertiser is **" + top["name"] + "** with "
        + str(top["ad_count"]) + " ads and a " + str(top["hit_rate"]) + "% hit rate."
    )

    # 2. Highest hit rate
    best_hit = max(advertisers, key=lambda a: a["hit_rate"])
    if best_hit["name"] != top["name"]:
        findings.append(
            "**" + best_hit["name"] + "** has the highest hit rate at "
            + str(best_hit["hit_rate"]) + "% (from " + str(best_hit["ad_count"]) + " ads)."
        )

    # 3. Trend summary
    growing = [a for a in advertisers if a["trend"] == "growing"]
    declining = [a for a in advertisers if a["trend"] == "declining"]
    if growing:
        names = ", ".join(a["name"] for a in growing[:3])
        findings.append(
            str(len(growing)) + " advertiser(s) show a growing trend: " + names + "."
        )
    if declining:
        names = ", ".join(a["name"] for a in declining[:3])
        findings.append(
            str(len(declining)) + " advertiser(s) show a declining trend: " + names + "."
        )

    # 4. Genre concentration
    most_contested = max(
        genre_dominance.items(),
        key=lambda x: len(x[1]),
        default=("N/A", []),
    )
    if most_contested[1]:
        findings.append(
            "The most competitive genre is **" + most_contested[0] + "** with "
            + str(len(most_contested[1])) + " top-20 advertisers active in it."
        )

    # 5. Spend insight
    spenders = [a for a in advertisers if a["monthly_spend"] > 0]
    if spenders:
        top_spender = max(spenders, key=lambda a: a["monthly_spend"])
        findings.append(
            "**" + top_spender["name"] + "** has the highest estimated monthly "
            "spend at " + "{:,.0f}".format(top_spender["monthly_spend"]) + "."
        )

    # 6. Creative style insight
    hook_counter = Counter(
        a["preferred_hook"] for a in advertisers
        if a["preferred_hook"] != "N/A"
    )
    if hook_counter:
        top_hook = hook_counter.most_common(1)[0]
        findings.append(
            "The most popular hook style among top advertisers is "
            "**" + top_hook[0] + "** (used by " + str(top_hook[1]) + " advertisers)."
        )

    return findings


# -- Main --------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("COMPETITIVE REPORT GENERATOR")
    print("Executed at: " + datetime.now(timezone.utc).isoformat())
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total_ads = len(ads)
        print("Total ads in database: " + str(total_ads))

        if total_ads == 0:
            print("No ads found. Exiting.")
            return

        # -- Group by advertiser -----------------------------------
        advertiser_groups: dict[str, list[Ad]] = defaultdict(list)
        for ad in ads:
            name = ad.advertiser_name
            if name and name.strip():
                advertiser_groups[name.strip()].append(ad)

        total_advertisers = len(advertiser_groups)
        print("Unique advertisers: " + str(total_advertisers))

        # -- Top 20 by ad count ------------------------------------
        sorted_names = sorted(
            advertiser_groups.keys(),
            key=lambda n: len(advertiser_groups[n]),
            reverse=True,
        )
        top_20_names = sorted_names[:20]
        print("Profiling top " + str(len(top_20_names)) + " advertisers...")

        top_advertisers = []
        for name in top_20_names:
            data = _build_advertiser_data(name, advertiser_groups[name])
            top_advertisers.append(data)

        # -- Genre dominance map -----------------------------------
        genre_dominance: dict[str, list[str]] = defaultdict(list)
        for a in top_advertisers:
            genre_dominance[a["top_genre"]].append(a["name"])

        # -- Generate markdown -------------------------------------
        md = _generate_markdown(
            top_advertisers,
            dict(genre_dominance),
            total_ads,
            total_advertisers,
        )

        # -- Export ------------------------------------------------
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        export_path = os.path.join(EXPORTS_DIR, "competitive_report.md")
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(md)
        print("\nExported to: " + export_path)

        # -- Print key findings ------------------------------------
        findings = _generate_findings(top_advertisers, dict(genre_dominance))
        print("\n" + "=" * 60)
        print("KEY FINDINGS")
        print("=" * 60)
        for i, finding in enumerate(findings, 1):
            # Strip markdown bold markers for console output
            clean = finding.replace("**", "")
            print("  " + str(i) + ". " + clean)

        # -- Print summary table -----------------------------------
        print("\n" + "=" * 60)
        print("TOP 20 ADVERTISERS SUMMARY")
        print("=" * 60)
        print(
            "  {:>2s} {:<30s} {:>4s} "
            "{:>6s} {:>6s} {:<10s} {:>10s}".format(
                "#", "Advertiser", "Ads", "HitR", "AvgSc", "Trend", "Mo.Spend"
            )
        )
        print("  " + "-" * 74)

        for i, a in enumerate(top_advertisers, 1):
            name_safe = a["name"][:28].encode("ascii", "replace").decode("ascii")
            print(
                "  {:>2d} {:<30s} {:>4d} "
                "{:>5.1f}% {:>5.1f} "
                "{:<10s} {:>10,.0f}".format(
                    i, name_safe, a["ad_count"],
                    a["hit_rate"], a["avg_score"],
                    a["trend"], a["monthly_spend"],
                )
            )

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print("FATAL ERROR: " + str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
