#!/usr/bin/env python3
"""Export all creative analysis data to a single JSON report.

Includes: format classification, color analysis, video metadata,
thumbnail quality for every ad.

Output: exports/creative_intelligence_report.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/export_creative_assets.py
"""

import os
import sys
import json
from datetime import datetime, timezone

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

        assets = []
        stats = {
            "total": len(ads),
            "with_color_analysis": 0,
            "with_creative_format": 0,
            "with_video_metadata": 0,
            "with_thumbnail_quality": 0,
            "with_creative_analysis": 0,
            "with_rekognition": 0,
        }

        format_dist = {}
        scheme_dist = {}

        for ad in ads:
            meta = ad.ad_metadata or {}

            entry = {
                "ad_id": ad.id,
                "title": ad.title or "",
                "platform": ad.platform.value if hasattr(ad.platform, "value") else str(ad.platform),
                "advertiser": ad.advertiser_name or "",
                "creative_type": ad.creative_type or "",
            }

            # Color analysis
            ca = meta.get("color_analysis")
            if isinstance(ca, dict):
                entry["color_analysis"] = ca
                stats["with_color_analysis"] += 1
                scheme = ca.get("scheme", "unknown")
                scheme_dist[scheme] = scheme_dist.get(scheme, 0) + 1

            # Creative format
            cf = meta.get("creative_format")
            if isinstance(cf, dict):
                entry["creative_format"] = cf
                stats["with_creative_format"] += 1
                fmt_key = "%s/%s" % (cf.get("type", "?"), cf.get("subtype", "?"))
                format_dist[fmt_key] = format_dist.get(fmt_key, 0) + 1

            # Video metadata
            va = meta.get("video_analysis")
            if isinstance(va, dict):
                entry["video_metadata"] = va
                stats["with_video_metadata"] += 1

            # Thumbnail quality
            tq = meta.get("thumbnail_quality")
            if isinstance(tq, dict):
                entry["thumbnail_quality"] = tq
                stats["with_thumbnail_quality"] += 1

            # Creative analysis (hook, CTA, etc.)
            cra = meta.get("creative_analysis")
            if isinstance(cra, dict):
                entry["creative_analysis"] = cra
                stats["with_creative_analysis"] += 1

            # Rekognition
            rek = meta.get("rekognition")
            if isinstance(rek, dict):
                entry["rekognition_summary"] = {
                    "label_count": len(rek.get("labels", [])),
                    "text_count": len(rek.get("text_detections", [])),
                    "face_count": len(rek.get("faces", [])),
                }
                stats["with_rekognition"] += 1

            # Check media availability
            has_thumb = os.path.exists(os.path.join(CACHE_DIR, "thumbnails", "%d.jpg" % ad.id))
            has_image = os.path.exists(os.path.join(CACHE_DIR, "images", "%d.jpg" % ad.id))
            has_video = any(
                os.path.exists(os.path.join(CACHE_DIR, "videos", "%d.%s" % (ad.id, ext)))
                for ext in ("mp4", "webm", "mov")
            )
            entry["media_available"] = {
                "thumbnail": has_thumb,
                "image": has_image,
                "video": has_video,
            }

            assets.append(entry)

        # Build report
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": stats,
            "distributions": {
                "format": format_dist,
                "color_scheme": scheme_dist,
            },
            "assets": assets,
        }

        output_path = os.path.join(EXPORTS_DIR, "creative_intelligence_report.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n=== Creative Intelligence Report ===")
        print("Output: %s" % output_path)
        print("Total ads: %d" % stats["total"])
        print("\nAnalysis Coverage:")
        for key, value in stats.items():
            if key != "total":
                pct = value / max(stats["total"], 1) * 100
                print("  %-25s %4d / %d (%5.1f%%)" % (key, value, stats["total"], pct))

        if format_dist:
            print("\nFormat Distribution:")
            for fmt, count in sorted(format_dist.items(), key=lambda x: -x[1])[:10]:
                print("  %-25s %4d" % (fmt, count))

        if scheme_dist:
            print("\nColor Scheme Distribution:")
            for scheme, count in sorted(scheme_dist.items(), key=lambda x: -x[1]):
                print("  %-15s %4d" % (scheme, count))

        print("\nDone.")

    except Exception as e:
        print("ERROR: %s" % str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
