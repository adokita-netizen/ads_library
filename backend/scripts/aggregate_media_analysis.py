#!/usr/bin/env python3
"""Aggregate all media analysis results into a comprehensive report.

Combines:
  - Color analysis from thumbnails
  - Video metadata
  - Quality scores
  - Format classifications
  - Creative analysis
  - Rekognition data

Output: exports/media_analysis_report.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/aggregate_media_analysis.py
"""

import os
import sys
import json
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

EXPORTS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "exports")
)
CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media_cache")
)


def main():
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        print("Loaded %d ads" % len(ads))

        # Aggregation counters
        color_schemes = defaultdict(int)
        format_types = defaultdict(int)
        format_subtypes = defaultdict(int)
        quality_scores = []
        video_durations = []
        has_text_count = 0
        no_text_count = 0

        # Genre-level aggregation
        genre_media = defaultdict(lambda: {
            "count": 0,
            "video_count": 0,
            "image_count": 0,
            "avg_quality": [],
            "color_schemes": defaultdict(int),
            "formats": defaultdict(int),
        })

        # Per-ad detail
        ad_details = []

        # Rekognition aggregation
        all_labels = defaultdict(int)
        label_ad_count = 0

        for ad in ads:
            meta = ad.ad_metadata or {}
            genre = meta.get("fine_genre_en", "unknown")
            gm = genre_media[genre]
            gm["count"] += 1

            detail = {"ad_id": ad.id, "genre": genre}

            # Color analysis
            ca = meta.get("color_analysis")
            if isinstance(ca, dict):
                scheme = ca.get("scheme", "unknown")
                color_schemes[scheme] += 1
                gm["color_schemes"][scheme] += 1
                detail["color_scheme"] = scheme

                if ca.get("has_text"):
                    has_text_count += 1
                else:
                    no_text_count += 1

            # Creative format
            cf = meta.get("creative_format")
            if isinstance(cf, dict):
                ftype = cf.get("type", "unknown")
                fsubtype = cf.get("subtype", "unknown")
                format_types[ftype] += 1
                format_subtypes["%s/%s" % (ftype, fsubtype)] += 1
                gm["formats"][ftype] += 1
                detail["format"] = "%s/%s" % (ftype, fsubtype)

                if ftype == "video":
                    gm["video_count"] += 1
                else:
                    gm["image_count"] += 1

            # Quality scores
            tq = meta.get("thumbnail_quality")
            if isinstance(tq, dict) and "score" in tq:
                try:
                    score = float(tq["score"])
                    quality_scores.append(score)
                    gm["avg_quality"].append(score)
                    detail["quality_score"] = score
                except (ValueError, TypeError):
                    pass

            # Video metadata
            va = meta.get("video_analysis")
            if isinstance(va, dict) and "duration_sec" in va:
                try:
                    dur = float(va["duration_sec"])
                    video_durations.append(dur)
                    detail["duration_sec"] = dur
                except (ValueError, TypeError):
                    pass

            # Rekognition labels
            rek = meta.get("rekognition")
            if isinstance(rek, dict):
                labels = rek.get("labels", [])
                if labels:
                    label_ad_count += 1
                    for label_item in labels:
                        if isinstance(label_item, dict):
                            name = label_item.get("Name", label_item.get("name", ""))
                        else:
                            name = str(label_item)
                        if name:
                            all_labels[name] += 1

            ad_details.append(detail)

        # Compute genre-level averages
        genre_summary = {}
        for genre, gm in sorted(genre_media.items(), key=lambda x: -x[1]["count"]):
            avg_q = (
                round(sum(gm["avg_quality"]) / len(gm["avg_quality"]), 1)
                if gm["avg_quality"] else 0
            )
            genre_summary[genre] = {
                "count": gm["count"],
                "video_count": gm["video_count"],
                "image_count": gm["image_count"],
                "avg_quality": avg_q,
                "top_color_schemes": dict(sorted(
                    gm["color_schemes"].items(), key=lambda x: -x[1])[:3]),
                "format_breakdown": dict(gm["formats"]),
            }

        # Build report
        avg_quality = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0
        avg_duration = round(sum(video_durations) / len(video_durations), 1) if video_durations else 0

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_ads": len(ads),
                "with_color_analysis": sum(color_schemes.values()),
                "with_format_classification": sum(format_types.values()),
                "with_quality_score": len(quality_scores),
                "with_video_metadata": len(video_durations),
                "with_rekognition": label_ad_count,
                "avg_quality_score": avg_quality,
                "avg_video_duration_sec": avg_duration,
                "text_overlay_detected": has_text_count,
                "no_text_overlay": no_text_count,
            },
            "distributions": {
                "color_schemes": dict(sorted(color_schemes.items(), key=lambda x: -x[1])),
                "format_types": dict(sorted(format_types.items(), key=lambda x: -x[1])),
                "format_subtypes": dict(sorted(format_subtypes.items(), key=lambda x: -x[1])),
                "top_rekognition_labels": dict(sorted(all_labels.items(), key=lambda x: -x[1])[:30]),
            },
            "genre_breakdown": genre_summary,
            "quality_histogram": _build_histogram(quality_scores),
            "duration_histogram": _build_duration_histogram(video_durations),
        }

        output_path = os.path.join(EXPORTS_DIR, "media_analysis_report.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # Print dashboard
        print("\n" + "=" * 60)
        print("  MEDIA ANALYSIS DASHBOARD")
        print("=" * 60)

        print("\nOverview:")
        print("  Total Ads:           %d" % len(ads))
        print("  With Color Analysis: %d" % sum(color_schemes.values()))
        print("  With Format Class:   %d" % sum(format_types.values()))
        print("  With Quality Score:  %d (avg: %.1f)" % (len(quality_scores), avg_quality))
        print("  With Video Metadata: %d (avg: %.1fs)" % (len(video_durations), avg_duration))
        print("  With Rekognition:    %d" % label_ad_count)

        print("\nColor Schemes:")
        for scheme, count in sorted(color_schemes.items(), key=lambda x: -x[1]):
            pct = count / max(len(ads), 1) * 100
            bar = "#" * min(int(pct), 40)
            print("  %-10s %4d (%5.1f%%)  %s" % (scheme, count, pct, bar))

        print("\nFormat Types:")
        for ftype, count in sorted(format_types.items(), key=lambda x: -x[1]):
            pct = count / max(len(ads), 1) * 100
            bar = "#" * min(int(pct), 40)
            print("  %-10s %4d (%5.1f%%)  %s" % (ftype, count, pct, bar))

        print("\nTop Genres by Ad Count:")
        for genre, info in list(genre_summary.items())[:10]:
            print("  %-25s %4d ads  (avg Q: %.1f)" % (
                genre[:25], info["count"], info["avg_quality"]))

        print("\nOutput: %s" % output_path)

    except Exception as e:
        print("ERROR: %s" % str(e))
        raise
    finally:
        session.close()


def _build_histogram(scores: list[float]) -> dict[str, int]:
    """Build quality score histogram in 10-point buckets."""
    hist = {}
    for s in scores:
        bucket = "%d-%d" % (int(s // 10) * 10, int(s // 10) * 10 + 10)
        hist[bucket] = hist.get(bucket, 0) + 1
    return dict(sorted(hist.items()))


def _build_duration_histogram(durations: list[float]) -> dict[str, int]:
    """Build video duration histogram."""
    hist = {}
    for d in durations:
        if d < 6:
            bucket = "0-6s"
        elif d < 15:
            bucket = "6-15s"
        elif d < 30:
            bucket = "15-30s"
        elif d < 60:
            bucket = "30-60s"
        else:
            bucket = "60s+"
        hist[bucket] = hist.get(bucket, 0) + 1
    return dict(sorted(hist.items()))


if __name__ == "__main__":
    main()
