#!/usr/bin/env python3
"""Export structured JSON data for presentation slides.

Queries the VAAP ads database and generates a 6-slide presentation
data file with executive summary, genre breakdown, top ads, creative
patterns, market trends, and recommendations.

Output: backend/exports/presentation_data.json

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/export_presentation_data.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path setup -- allow importing app.* from the backend root
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.ad import Ad  # noqa: E402
from app.core.database import SyncSessionLocal  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value, default=0.0):
    """Return a float, falling back to *default* for None / non-numeric."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _meta(ad, key, default=None):
    """Safely extract a key from ad.ad_metadata (JSON dict)."""
    meta = ad.ad_metadata
    if not isinstance(meta, dict):
        return default
    return meta.get(key, default)


def _round2(value):
    return round(value, 2) if value is not None else 0.0


def _is_hit(hit_level):
    """Return True if the hit_level indicates a successful ad."""
    return hit_level not in ("unknown", "low", "", None)


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _collect_ads(session):
    """Fetch all ads and return a list of lightweight dicts."""
    ads = session.query(Ad).all()
    result = []
    for ad in ads:
        result.append({
            "id": ad.id,
            "title": ad.title or "",
            "advertiser_name": ad.advertiser_name or "",
            "category": ad.category.value if ad.category else "other",
            "view_count": _safe_int(ad.view_count),
            "spend": _safe_float(ad.spend),
            "score": _safe_float(_meta(ad, "latest_hit_score")),
            "fine_genre": _meta(ad, "fine_genre", "unknown"),
            "hit_level": _meta(ad, "hit_level", "unknown"),
            "hook_type": _meta(ad, "hook_type", "unknown"),
            "cta_type": _meta(ad, "cta_type", "unknown"),
            "created_at": (
                ad.created_at.isoformat() if ad.created_at else None
            ),
        })
    return result


# ---------------------------------------------------------------------------
# Slide builders
# ---------------------------------------------------------------------------

def _build_slide_1(ads):
    """Slide 1: Executive summary."""
    total = len(ads)
    if total == 0:
        return {
            "slide_number": 1,
            "title": "Executive Summary",
            "subtitle": "VAAP Ad Performance Overview",
            "content_type": "summary",
            "data": {
                "total_ads": 0,
                "overall_hit_rate": 0.0,
                "top_genre_by_hit_rate": "N/A",
                "avg_score": 0.0,
            },
        }

    scores = [a["score"] for a in ads]
    avg_score = _round2(sum(scores) / total)

    # Hit rate: proportion of ads whose hit_level indicates success
    hit_count = sum(1 for a in ads if _is_hit(a["hit_level"]))
    overall_hit_rate = _round2(hit_count / total * 100)

    # Top genre by hit rate
    genre_hits = defaultdict(lambda: {"hits": 0, "total": 0})
    for a in ads:
        g = a["fine_genre"]
        genre_hits[g]["total"] += 1
        if _is_hit(a["hit_level"]):
            genre_hits[g]["hits"] += 1

    top_genre = "N/A"
    best_rate = -1.0
    for g, counts in genre_hits.items():
        if counts["total"] >= 1:
            rate = counts["hits"] / counts["total"]
            if rate > best_rate:
                best_rate = rate
                top_genre = g

    return {
        "slide_number": 1,
        "title": "Executive Summary",
        "subtitle": "VAAP Ad Performance Overview",
        "content_type": "summary",
        "data": {
            "total_ads": total,
            "overall_hit_rate": overall_hit_rate,
            "top_genre_by_hit_rate": top_genre,
            "avg_score": avg_score,
        },
    }


def _build_slide_2(ads):
    """Slide 2: Genre breakdown table."""
    genre_map = defaultdict(list)
    for a in ads:
        genre_map[a["fine_genre"]].append(a)

    rows = []
    for genre, group in sorted(genre_map.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(group)
        avg_score = _round2(sum(a["score"] for a in group) / count)
        hit_count = sum(1 for a in group if _is_hit(a["hit_level"]))
        hit_rate = _round2(hit_count / count * 100)
        avg_views = _round2(sum(a["view_count"] for a in group) / count)
        avg_spend = _round2(sum(a["spend"] for a in group) / count)
        rows.append({
            "genre": genre,
            "count": count,
            "avg_score": avg_score,
            "hit_rate": hit_rate,
            "avg_views": avg_views,
            "avg_spend": avg_spend,
        })

    return {
        "slide_number": 2,
        "title": "Genre Breakdown",
        "subtitle": "Performance metrics by fine genre",
        "content_type": "table",
        "data": {
            "columns": ["genre", "count", "avg_score", "hit_rate", "avg_views", "avg_spend"],
            "rows": rows,
        },
    }


def _build_slide_3(ads):
    """Slide 3: Top 10 ads by score."""
    sorted_ads = sorted(ads, key=lambda a: a["score"], reverse=True)[:10]
    items = []
    for a in sorted_ads:
        items.append({
            "id": a["id"],
            "title": a["title"],
            "score": a["score"],
            "genre": a["fine_genre"],
            "advertiser": a["advertiser_name"],
            "views": a["view_count"],
        })

    return {
        "slide_number": 3,
        "title": "Top 10 Ads by Hit Score",
        "subtitle": "Highest-performing ad creatives",
        "content_type": "list",
        "data": {
            "items": items,
        },
    }


def _build_slide_4(ads):
    """Slide 4: Creative pattern insights (top patterns by hit rate from ad_metadata)."""
    if not ads:
        return {
            "slide_number": 4,
            "title": "Creative Pattern Insights",
            "subtitle": "Top creative patterns by hit rate",
            "content_type": "table",
            "data": {"hook_patterns": [], "cta_patterns": []},
        }

    def _pattern_stats(key):
        """Aggregate hit rate by a metadata pattern field."""
        bucket = defaultdict(lambda: {"hits": 0, "total": 0, "score_sum": 0.0})
        for a in ads:
            val = a[key]
            bucket[val]["total"] += 1
            bucket[val]["score_sum"] += a["score"]
            if _is_hit(a["hit_level"]):
                bucket[val]["hits"] += 1

        result = []
        for pattern, stats in bucket.items():
            total = stats["total"]
            result.append({
                "pattern": pattern,
                "count": total,
                "hit_rate": _round2(stats["hits"] / total * 100) if total else 0.0,
                "avg_score": _round2(stats["score_sum"] / total) if total else 0.0,
            })
        result.sort(key=lambda x: x["hit_rate"], reverse=True)
        return result[:10]

    return {
        "slide_number": 4,
        "title": "Creative Pattern Insights",
        "subtitle": "Top creative patterns by hit rate",
        "content_type": "table",
        "data": {
            "hook_patterns": _pattern_stats("hook_type"),
            "cta_patterns": _pattern_stats("cta_type"),
        },
    }


def _build_slide_5(ads):
    """Slide 5: Market trends (new-ads trend, score trend, genre growth)."""
    if not ads:
        return {
            "slide_number": 5,
            "title": "Market Trends",
            "subtitle": "Temporal trends and genre growth",
            "content_type": "chart",
            "data": {
                "new_ads_trend": [],
                "score_trend": [],
                "genre_growth": [],
            },
        }

    # Group ads by month (YYYY-MM)
    month_map = defaultdict(list)
    for a in ads:
        ts = a["created_at"]
        if ts:
            month_key = ts[:7]  # "YYYY-MM"
            month_map[month_key].append(a)

    sorted_months = sorted(month_map.keys())

    new_ads_trend = []
    score_trend = []
    for m in sorted_months:
        group = month_map[m]
        new_ads_trend.append({"month": m, "count": len(group)})
        avg = _round2(sum(a["score"] for a in group) / len(group))
        score_trend.append({"month": m, "avg_score": avg})

    # Genre growth: compare last two months (if available)
    genre_growth = []
    if len(sorted_months) >= 2:
        prev_month = sorted_months[-2]
        curr_month = sorted_months[-1]
        prev_genres = defaultdict(int)
        curr_genres = defaultdict(int)
        for a in month_map[prev_month]:
            prev_genres[a["fine_genre"]] += 1
        for a in month_map[curr_month]:
            curr_genres[a["fine_genre"]] += 1

        all_genres = set(prev_genres.keys()) | set(curr_genres.keys())
        for g in sorted(all_genres):
            p = prev_genres.get(g, 0)
            c = curr_genres.get(g, 0)
            change = c - p
            pct = _round2((change / p * 100) if p > 0 else (100.0 if c > 0 else 0.0))
            genre_growth.append({
                "genre": g,
                "prev_count": p,
                "curr_count": c,
                "change": change,
                "change_pct": pct,
            })
        genre_growth.sort(key=lambda x: x["change_pct"], reverse=True)

    return {
        "slide_number": 5,
        "title": "Market Trends",
        "subtitle": "Temporal trends and genre growth",
        "content_type": "chart",
        "data": {
            "new_ads_trend": new_ads_trend,
            "score_trend": score_trend,
            "genre_growth": genre_growth,
        },
    }


def _build_slide_6(ads):
    """Slide 6: Data-driven recommendations."""
    recommendations = []

    if not ads:
        recommendations.append({
            "category": "data",
            "priority": "high",
            "recommendation": "No ad data available. Start by ingesting ads into the platform.",
        })
        return {
            "slide_number": 6,
            "title": "Recommendations",
            "subtitle": "Data-driven strategic suggestions",
            "content_type": "list",
            "data": {"recommendations": recommendations},
        }

    total = len(ads)
    scores = [a["score"] for a in ads]
    avg_score = sum(scores) / total if total else 0

    # 1. Identify top-performing genre and recommend doubling down
    genre_map = defaultdict(list)
    for a in ads:
        genre_map[a["fine_genre"]].append(a)

    best_genre = None
    best_genre_score = -1.0
    for g, group in genre_map.items():
        g_avg = sum(a["score"] for a in group) / len(group)
        if g_avg > best_genre_score:
            best_genre_score = g_avg
            best_genre = g

    if best_genre:
        recommendations.append({
            "category": "genre_focus",
            "priority": "high",
            "recommendation": (
                "Double down on '{}' genre which has the highest "
                "average score ({}). "
                "Allocate more budget to creatives in this category."
            ).format(best_genre, _round2(best_genre_score)),
        })

    # 2. Identify underperforming genres with high spend
    for g, group in genre_map.items():
        g_avg_score = sum(a["score"] for a in group) / len(group)
        g_avg_spend = sum(a["spend"] for a in group) / len(group)
        if g_avg_score < avg_score * 0.7 and g_avg_spend > 0:
            recommendations.append({
                "category": "budget_optimization",
                "priority": "medium",
                "recommendation": (
                    "Review spend in '{}' genre: avg score ({}) "
                    "is below platform average ({}), "
                    "but avg spend is {}. "
                    "Consider reallocating budget to higher-performing genres."
                ).format(g, _round2(g_avg_score), _round2(avg_score), _round2(g_avg_spend)),
            })

    # 3. Hook-type recommendation
    hook_hits = defaultdict(lambda: {"hits": 0, "total": 0})
    for a in ads:
        h = a["hook_type"]
        hook_hits[h]["total"] += 1
        if _is_hit(a["hit_level"]):
            hook_hits[h]["hits"] += 1

    best_hook = None
    best_hook_rate = -1.0
    for h, stats in hook_hits.items():
        if stats["total"] >= 3:  # require minimum sample
            rate = stats["hits"] / stats["total"]
            if rate > best_hook_rate:
                best_hook_rate = rate
                best_hook = h

    if best_hook and best_hook != "unknown":
        recommendations.append({
            "category": "creative_strategy",
            "priority": "high",
            "recommendation": (
                "Use '{}' hook type more frequently -- it has the "
                "highest hit rate ({}%) among "
                "patterns with sufficient sample size."
            ).format(best_hook, _round2(best_hook_rate * 100)),
        })

    # 4. CTA-type recommendation
    cta_hits = defaultdict(lambda: {"hits": 0, "total": 0})
    for a in ads:
        c = a["cta_type"]
        cta_hits[c]["total"] += 1
        if _is_hit(a["hit_level"]):
            cta_hits[c]["hits"] += 1

    best_cta = None
    best_cta_rate = -1.0
    for c, stats in cta_hits.items():
        if stats["total"] >= 3:
            rate = stats["hits"] / stats["total"]
            if rate > best_cta_rate:
                best_cta_rate = rate
                best_cta = c

    if best_cta and best_cta != "unknown":
        recommendations.append({
            "category": "creative_strategy",
            "priority": "medium",
            "recommendation": (
                "Adopt '{}' CTA type which achieves a "
                "{}% hit rate. "
                "Test combining it with the top-performing hook type."
            ).format(best_cta, _round2(best_cta_rate * 100)),
        })

    # 5. Volume recommendation for high-score low-volume genres
    low_volume_genres = [
        g for g, group in genre_map.items()
        if len(group) < 5 and sum(a["score"] for a in group) / len(group) > avg_score
    ]
    if low_volume_genres:
        recommendations.append({
            "category": "exploration",
            "priority": "low",
            "recommendation": (
                "Genres with high scores but low volume ({}) "
                "may represent untapped opportunities. "
                "Consider increasing ad count to validate performance."
            ).format(", ".join(low_volume_genres)),
        })

    # Fallback if no specific recommendations were generated
    if not recommendations:
        recommendations.append({
            "category": "general",
            "priority": "medium",
            "recommendation": (
                "Current data shows uniform performance across genres and patterns. "
                "Increase creative variation to identify top-performing strategies."
            ),
        })

    return {
        "slide_number": 6,
        "title": "Recommendations",
        "subtitle": "Data-driven strategic suggestions",
        "content_type": "list",
        "data": {"recommendations": recommendations},
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("VAAP Presentation Data Export")
    print("=" * 60)

    # Ensure exports directory exists
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    export_dir = os.path.join(base_dir, "exports")
    os.makedirs(export_dir, exist_ok=True)

    # Query database
    session = SyncSessionLocal()
    try:
        print("Querying ads database...")
        ads = _collect_ads(session)
        print("  Loaded {} ads".format(len(ads)))
    finally:
        session.close()

    # Build slides
    slides = [
        _build_slide_1(ads),
        _build_slide_2(ads),
        _build_slide_3(ads),
        _build_slide_4(ads),
        _build_slide_5(ads),
        _build_slide_6(ads),
    ]

    # Assemble final payload
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_ads_analyzed": len(ads),
        "slides": slides,
    }

    # Write JSON
    output_path = os.path.join(export_dir, "presentation_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("  Output written to {}".format(output_path))

    # Print slide outline
    print()
    print("-" * 60)
    print("Slide Outline")
    print("-" * 60)
    for slide in slides:
        num = slide["slide_number"]
        title = slide["title"]
        subtitle = slide["subtitle"]
        ctype = slide["content_type"]
        data = slide["data"]

        print("\n  Slide {}: {}".format(num, title))
        print("    Subtitle    : {}".format(subtitle))
        print("    Content type: {}".format(ctype))

        if num == 1:
            d = data
            print("    Total ads        : {}".format(d["total_ads"]))
            print("    Overall hit rate : {}%".format(d["overall_hit_rate"]))
            print("    Top genre        : {}".format(d["top_genre_by_hit_rate"]))
            print("    Avg score        : {}".format(d["avg_score"]))

        elif num == 2:
            rows = data.get("rows", [])
            print("    Genres: {}".format(len(rows)))
            for row in rows[:5]:
                print(
                    "      {:20s}  count={:>4}  "
                    "avg_score={:>6}  hit_rate={:>5}%".format(
                        row["genre"], row["count"],
                        row["avg_score"], row["hit_rate"]
                    )
                )
            if len(rows) > 5:
                print("      ... and {} more genres".format(len(rows) - 5))

        elif num == 3:
            items = data.get("items", [])
            print("    Top ads: {}".format(len(items)))
            for item in items:
                print(
                    "      #{}  score={:>6}  {}".format(
                        item["id"], item["score"], item["title"][:40]
                    )
                )

        elif num == 4:
            hooks = data.get("hook_patterns", [])
            ctas = data.get("cta_patterns", [])
            print("    Hook patterns: {}".format(len(hooks)))
            for h in hooks[:3]:
                print(
                    "      {:20s}  hit_rate={:>5}%  count={}".format(
                        h["pattern"], h["hit_rate"], h["count"]
                    )
                )
            print("    CTA patterns : {}".format(len(ctas)))
            for c in ctas[:3]:
                print(
                    "      {:20s}  hit_rate={:>5}%  count={}".format(
                        c["pattern"], c["hit_rate"], c["count"]
                    )
                )

        elif num == 5:
            trend = data.get("new_ads_trend", [])
            growth = data.get("genre_growth", [])
            print("    Monthly data points: {}".format(len(trend)))
            if trend:
                print("    Latest month      : {} ({} ads)".format(
                    trend[-1]["month"], trend[-1]["count"]
                ))
            print("    Genre growth rows : {}".format(len(growth)))

        elif num == 6:
            recs = data.get("recommendations", [])
            print("    Recommendations: {}".format(len(recs)))
            for r in recs:
                print("      [{:>6}] {}".format(
                    r["priority"].upper(), r["recommendation"][:80]
                ))

    print()
    print("=" * 60)
    print("Export complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
