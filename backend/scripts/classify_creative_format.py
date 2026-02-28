#!/usr/bin/env python3
"""Classify creative format for each ad using keyword matching.

Classifies ads into creative format categories:
  Video: live_action, animation, slideshow, ugc_style, interview
  Image: product_photo, before_after, text_heavy, illustration, collage

Uses keyword matching in title + description + existing metadata.
Stores in ad_metadata.creative_format.

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/classify_creative_format.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media_cache")
)


# ── Video subtype rules ──────────────────────────────────────────────

VIDEO_RULES: list[tuple[str, list[str], float]] = [
    ("ugc_style", [
        "UGC", "user generated", "vlog", "review",
        "unboxing", "haul", "try on", "real voice",
        "real user", "customer voice",
    ], 0.85),
    ("interview", [
        "interview", "talk", "conversation",
        "expert", "doctor", "specialist",
        "Q&A", "ask",
    ], 0.80),
    ("animation", [
        "animation", "anime", "animated", "cartoon",
        "motion graphic", "CG", "3D",
        "infographic", "explainer",
    ], 0.85),
    ("slideshow", [
        "slide", "carousel", "swipe",
        "step by step", "comparison",
    ], 0.75),
    ("live_action", [
        "model", "actress", "talent",
        "shoot", "filming", "scene",
        "real", "lifestyle",
    ], 0.70),
]

# ── Image subtype rules ──────────────────────────────────────────────

IMAGE_RULES: list[tuple[str, list[str], float]] = [
    ("before_after", [
        "before", "after", "B/A", "transformation",
        "change", "result", "comparison",
    ], 0.90),
    ("text_heavy", [
        "text", "copy", "headline",
        "message", "banner", "typography",
    ], 0.75),
    ("illustration", [
        "illustration", "illust", "drawing",
        "manga", "comic", "character", "mascot",
    ], 0.85),
    ("collage", [
        "collage", "grid", "mosaic",
        "multi", "compilation",
    ], 0.80),
    ("product_photo", [
        "product", "item", "package",
        "bottle", "tube", "box",
        "supplement", "cream", "serum",
        "device", "gadget",
    ], 0.70),
]


def _match_keywords(text: str, keywords: list[str]) -> int:
    """Count how many keywords match in the text (case-insensitive)."""
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


def _classify_ad(ad: Ad) -> dict:
    """Classify an ad's creative format."""
    # Build text corpus from title, description, and metadata
    parts = []
    if ad.title:
        parts.append(ad.title)
    if ad.description:
        parts.append(ad.description)

    meta = ad.ad_metadata or {}
    ca = meta.get("creative_analysis", {})
    if isinstance(ca, dict):
        for key in ("hook_type", "cta_type", "offer_type", "emotion"):
            val = ca.get(key, "")
            if val:
                parts.append(str(val))

    # NLP data
    nlp = meta.get("nlp", {})
    if isinstance(nlp, dict):
        keywords = nlp.get("keywords", [])
        if isinstance(keywords, list):
            parts.extend([str(k) for k in keywords])

    text = " ".join(parts)

    # Determine primary type from creative_type field or metadata
    is_video = False
    creative_type_str = (ad.creative_type or "").lower()
    if "video" in creative_type_str:
        is_video = True
    elif ad.video_url:
        is_video = True
    elif ad.duration_seconds and ad.duration_seconds > 0:
        is_video = True

    # Also check for cached video
    if not is_video:
        for ext in ("mp4", "webm", "mov"):
            vid_path = os.path.join(CACHE_DIR, "videos", "%d.%s" % (ad.id, ext))
            if os.path.exists(vid_path):
                is_video = True
                break

    primary_type = "video" if is_video else "image"

    # Match against rules
    rules = VIDEO_RULES if is_video else IMAGE_RULES

    best_subtype = "unknown"
    best_score = 0
    best_confidence = 0.5

    for subtype, keywords, base_conf in rules:
        match_count = _match_keywords(text, keywords)
        if match_count > best_score:
            best_score = match_count
            best_subtype = subtype
            best_confidence = min(1.0, base_conf + match_count * 0.05)

    # Default subtypes if no match
    if best_score == 0:
        if is_video:
            best_subtype = "live_action"
            best_confidence = 0.4
        else:
            best_subtype = "product_photo"
            best_confidence = 0.4

    return {
        "type": primary_type,
        "subtype": best_subtype,
        "confidence": round(best_confidence, 2),
        "classified_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print("Loaded %d ads for classification" % len(ads))

        classified = 0
        type_counts = {}
        subtype_counts = {}

        for ad in ads:
            result = _classify_ad(ad)

            meta = ad.ad_metadata or {}
            meta["creative_format"] = result
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            t = result["type"]
            s = result["subtype"]
            type_counts[t] = type_counts.get(t, 0) + 1
            key = "%s/%s" % (t, s)
            subtype_counts[key] = subtype_counts.get(key, 0) + 1
            classified += 1

        session.commit()

        print("\n=== Creative Format Classification Summary ===")
        print("Classified: %d ads" % classified)
        print("\nType Distribution:")
        for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            pct = count / max(classified, 1) * 100
            bar = "#" * min(int(pct / 2), 40)
            print("  %-10s %4d (%5.1f%%)  %s" % (t, count, pct, bar))

        print("\nSubtype Distribution:")
        for key, count in sorted(subtype_counts.items(), key=lambda x: -x[1]):
            pct = count / max(classified, 1) * 100
            bar = "#" * min(int(pct / 2), 40)
            print("  %-25s %4d (%5.1f%%)  %s" % (key, count, pct, bar))

    except Exception as e:
        session.rollback()
        print("ERROR: %s" % str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
