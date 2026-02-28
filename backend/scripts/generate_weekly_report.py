#!/usr/bin/env python3
"""Generate automated weekly report in Markdown.

Outputs: backend/exports/weekly_report_YYYY-MM-DD.md

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/generate_weekly_report.py
"""

import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.database import SyncSessionLocal
from app.models.ad import Ad


def _score(ad):
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _genre(ad):
    g = (ad.ad_metadata or {}).get("fine_genre_en", "")
    if g:
        return g
    return ad.category.value if ad.category else "other"


def _safe(ad, mx=40):
    t = ad.title or "(no title)"
    s = t.encode("ascii", errors="replace").decode("ascii")
    return s[:mx - 3] + "..." if len(s) > mx else s


def _hit(ad):
    return (ad.ad_metadata or {}).get("hit_level", "none") in ("hit", "mega_hit")


def _views(ad):
    rm = (ad.ad_metadata or {}).get("ranking_metrics", {})
    v = rm.get("total_views", 0) or 0
    return int(v or ad.view_count or 0)


def _make_aware(dt):
    """Ensure datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def sec_summary(ads, cut):
    n = len(ads)
    new = sum(1 for a in ads if a.first_seen_at and _make_aware(a.first_seen_at) >= cut)
    hits = sum(1 for a in ads if _hit(a))
    dupes = sum(1 for a in ads if (a.ad_metadata or {}).get("is_duplicate"))
    hr = "%.1f%%" % (hits * 100 / n) if n else "0%"
    lines = [
        "## Summary\n",
        "| Metric | Value |",
        "|--------|-------|",
        "| Total ads | %d |" % n,
        "| New (7d) | %d |" % new,
        "| Hit ads | %d (%s) |" % (hits, hr),
        "| Duplicates | %d |" % dupes,
        "",
    ]
    return "\n".join(lines)


def sec_top(ads, top_n=15):
    sa = sorted(ads, key=_score, reverse=True)[:top_n]
    lines = [
        "## Top Performers\n",
        "| # | ID | Score | Genre | Views | Title |",
        "|---|----|----|----|----|----| ",
    ]
    for i, ad in enumerate(sa, 1):
        lines.append("| %d | %d | %.1f | %s | %s | %s |" % (
            i, ad.id, _score(ad), _genre(ad),
            "{:,}".format(_views(ad)), _safe(ad, 35)))
    lines.append("")
    return "\n".join(lines)


def sec_new(ads, cut):
    na = sorted(
        [a for a in ads if a.first_seen_at and _make_aware(a.first_seen_at) >= cut],
        key=_score, reverse=True)
    lines = [
        "## New Ads This Week\n",
        "Total new: %d\n" % len(na),
    ]
    if not na:
        lines.append("No new ads.\n")
        return "\n".join(lines)
    lines.extend([
        "| ID | Score | Genre | Title |",
        "|----|----|----|----| ",
    ])
    for ad in na[:20]:
        lines.append("| %d | %.1f | %s | %s |" % (
            ad.id, _score(ad), _genre(ad), _safe(ad)))
    if len(na) > 20:
        lines.append("\n...and %d more" % (len(na) - 20))
    lines.append("")
    return "\n".join(lines)


def sec_tiers(ads):
    tiers = defaultdict(int)
    for ad in ads:
        t = (ad.ad_metadata or {}).get("score_calibration", {}).get("tier", "unknown")
        tiers[t] += 1
    lines = [
        "## Score Distribution\n",
        "| Tier | Count |",
        "|------|-------|",
    ]
    for t in ["top", "high", "mid", "low", "bottom", "unknown"]:
        if t in tiers:
            lines.append("| %s | %d |" % (t, tiers[t]))
    lines.append("")
    return "\n".join(lines)


def sec_genres(ads):
    bg = defaultdict(list)
    for ad in ads:
        bg[_genre(ad)].append(ad)
    lines = [
        "## Genre Trends\n",
        "| Genre | Count | Avg Score | Hit Rate | Top Score |",
        "|-------|-------|-----------|----------|-----------|",
    ]
    for g in sorted(bg):
        a = bg[g]
        n = len(a)
        sc = [_score(x) for x in a]
        avg = mean(sc) if sc else 0
        hits = sum(1 for x in a if _hit(x))
        hr = (hits / n * 100) if n else 0
        top = max(sc) if sc else 0
        lines.append("| %s | %d | %.1f | %.1f%% | %.1f |" % (g, n, avg, hr, top))
    lines.append("")
    return "\n".join(lines)


def sec_quality(ads):
    n = len(ads)
    if n == 0:
        return "## Data Quality\n\nNo ads.\n"
    checks = [
        ("title", lambda a: bool(a.title)),
        ("description", lambda a: bool(a.description)),
        ("advertiser", lambda a: bool(a.advertiser_name)),
        ("category", lambda a: a.category is not None),
        ("creative_analysis", lambda a: bool((a.ad_metadata or {}).get("creative_analysis"))),
        ("fine_genre", lambda a: bool((a.ad_metadata or {}).get("fine_genre_en"))),
        ("ranking_metrics", lambda a: bool((a.ad_metadata or {}).get("ranking_metrics"))),
        ("scenario_structure", lambda a: bool((a.ad_metadata or {}).get("scenario_structure"))),
        ("product_name", lambda a: bool((a.ad_metadata or {}).get("product_name"))),
        ("text_quality", lambda a: bool((a.ad_metadata or {}).get("text_quality"))),
    ]
    lines = [
        "## Data Quality\n",
        "| Field | Fill Rate |",
        "|-------|-----------|",
    ]
    for fn, ck in checks:
        filled = sum(1 for a in ads if ck(a))
        lines.append("| %s | %d/%d (%.1f%%) |" % (fn, filled, n, filled / n * 100))
    lines.append("")
    return "\n".join(lines)


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        now = datetime.now(timezone.utc)
        cut = now - timedelta(days=7)
        ds = now.strftime("%Y-%m-%d")
        print("Generating weekly report for %s" % ds)
        print("Total ads: %d" % len(ads))

        sections = [
            "# Weekly Ad Report - %s\n" % ds,
            "Generated: %s\n" % now.isoformat(),
            sec_summary(ads, cut),
            sec_top(ads),
            sec_new(ads, cut),
            sec_tiers(ads),
            sec_genres(ads),
            sec_quality(ads),
        ]
        rpt = "\n".join(sections)

        edir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
        os.makedirs(edir, exist_ok=True)
        op = os.path.join(edir, "weekly_report_%s.md" % ds)
        with open(op, "w", encoding="utf-8") as f:
            f.write(rpt)
        print("Report exported to %s" % op)

        print()
        print("=" * 60)
        print("Weekly Report Summary - %s" % ds)
        print("=" * 60)
        print("  Total ads:     %d" % len(ads))
        print("  New this week: %d" % sum(1 for a in ads if a.first_seen_at and _make_aware(a.first_seen_at) >= cut))
        print("  Hit ads:       %d" % sum(1 for a in ads if _hit(a)))
        top3 = sorted(ads, key=_score, reverse=True)[:3]
        print("  Top 3 scores:  %s" % ", ".join("%.1f" % _score(a) for a in top3))
        print("=" * 60)
    finally:
        session.close()


if __name__ == "__main__":
    main()
