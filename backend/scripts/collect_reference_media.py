"""Collect reference media for scenario builder.

Finds top 5 ads per genre (by hit_score), ensures they have cached
thumbnails/images, copies best creatives into reference folders,
and generates a reference_media.json index.

Usage:
    cd backend
    python scripts/collect_reference_media.py
"""

import os
import sys
import json
import shutil
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# ── Config ────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
REFERENCE_DIR = os.path.join(CACHE_DIR, "reference")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "genre_crawl_keywords.json")

TOP_N = 5  # Number of top ads per genre

# Scenario archetypes for mapping
ARCHETYPES = [
    "before_after",
    "testimonial",
    "problem_solution",
    "demonstration",
    "urgency_scarcity",
    "educational",
    "comparison",
    "storytelling",
]


def load_genres() -> dict:
    """Load genre definitions from config."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("genres", {})
    print("WARNING: genre config not found at %s" % CONFIG_PATH)
    return {}


def _has_cached_media(ad_id: int) -> dict:
    """Check which media types are cached for an ad.

    Returns dict with 'thumbnail', 'image', 'video' paths (or None).
    """
    result = {}

    thumb_path = os.path.join(THUMB_DIR, f"{ad_id}.jpg")
    result["thumbnail"] = thumb_path if os.path.exists(thumb_path) else None

    img_path = os.path.join(IMAGE_DIR, f"{ad_id}.jpg")
    result["image"] = img_path if os.path.exists(img_path) else None

    video_path = None
    for ext in ("mp4", "webm", "mov"):
        vp = os.path.join(VIDEO_DIR, f"{ad_id}.{ext}")
        if os.path.exists(vp):
            video_path = vp
            break
    result["video"] = video_path

    return result


def _guess_archetype(ad: Ad) -> str:
    """Guess the scenario archetype from ad metadata and content."""
    meta = ad.ad_metadata or {}
    title = (ad.title or "").lower()
    desc = (ad.description or "").lower()
    text = title + " " + desc

    # Simple keyword-based archetype detection
    if any(w in text for w in ["before", "after", "befor", "result"]):
        return "before_after"
    if any(w in text for w in ["review", "testimonial", "voice", "customer"]):
        return "testimonial"
    if any(w in text for w in ["problem", "trouble", "worry", "concern"]):
        return "problem_solution"
    if any(w in text for w in ["demo", "how to", "show", "watch"]):
        return "demonstration"
    if any(w in text for w in ["limited", "now", "today", "hurry", "last"]):
        return "urgency_scarcity"
    if any(w in text for w in ["learn", "study", "know", "guide", "tip"]):
        return "educational"
    if any(w in text for w in ["vs", "compare", "better", "difference"]):
        return "comparison"

    return "storytelling"


def collect_reference_media():
    """Main collection logic."""
    genres = load_genres()
    if not genres:
        print("No genres found. Exiting.")
        return

    print("Loaded %d genres from config" % len(genres))

    session = SyncSessionLocal()
    try:
        all_ads = session.query(Ad).all()
        print("Total ads in database: %d" % len(all_ads))

        # Group ads by genre (from ad_metadata.fine_genre_en)
        genre_ads: dict[str, list] = {g: [] for g in genres}

        for ad in all_ads:
            meta = ad.ad_metadata or {}
            fg_en = meta.get("fine_genre_en", "")
            if fg_en in genre_ads:
                score = 0
                # Try latest_hit_score from metadata first
                try:
                    score = float(meta.get("latest_hit_score", 0) or 0)
                except (ValueError, TypeError):
                    score = 0
                genre_ads[fg_en].append((ad, score))

        # Build reference index
        reference_index: dict = {}
        total_copied = 0

        for genre_key, ads_with_scores in genre_ads.items():
            if not ads_with_scores:
                print("  [%s] No ads found, skipping" % genre_key)
                continue

            # Sort by score descending, take top N
            ads_with_scores.sort(key=lambda x: x[1], reverse=True)
            top_ads = ads_with_scores[:TOP_N]

            # Create reference directory for this genre
            genre_ref_dir = os.path.join(REFERENCE_DIR, genre_key)
            os.makedirs(genre_ref_dir, exist_ok=True)

            genre_refs = []
            for ad, score in top_ads:
                media = _has_cached_media(ad.id)

                # Skip if no media at all
                if not media["thumbnail"] and not media["image"]:
                    continue

                # Copy best creative into reference folder
                copied_files = {}
                if media["thumbnail"]:
                    dest = os.path.join(genre_ref_dir, f"{ad.id}_thumb.jpg")
                    shutil.copy2(media["thumbnail"], dest)
                    copied_files["thumbnail"] = dest
                    total_copied += 1

                if media["image"]:
                    dest = os.path.join(genre_ref_dir, f"{ad.id}_image.jpg")
                    shutil.copy2(media["image"], dest)
                    copied_files["image"] = dest
                    total_copied += 1

                if media["video"]:
                    ext = os.path.splitext(media["video"])[1]
                    dest = os.path.join(genre_ref_dir, f"{ad.id}_video{ext}")
                    shutil.copy2(media["video"], dest)
                    copied_files["video"] = dest
                    total_copied += 1

                archetype = _guess_archetype(ad)

                ref_entry = {
                    "ad_id": ad.id,
                    "thumbnail": f"/api/v1/media/thumbnail/{ad.id}",
                    "image": f"/api/v1/media/image/{ad.id}",
                    "score": round(score, 1),
                    "title": ad.title or "",
                    "archetype": archetype,
                    "platform": ad.platform.value if hasattr(ad.platform, "value") else str(ad.platform),
                    "advertiser": ad.advertiser_name or "",
                }

                if media["video"]:
                    ref_entry["video"] = f"/api/v1/media/video/{ad.id}"

                genre_refs.append(ref_entry)

            if genre_refs:
                genre_info = genres.get(genre_key, {})
                reference_index[genre_key] = {
                    "label": genre_info.get("label", genre_key),
                    "reference_ads": genre_refs,
                }
                print("  [%s] Collected %d reference ads (top score: %.1f)" % (
                    genre_key, len(genre_refs),
                    genre_refs[0]["score"] if genre_refs else 0
                ))
            else:
                print("  [%s] No ads with cached media found" % genre_key)

        # Write reference_media.json
        os.makedirs(REFERENCE_DIR, exist_ok=True)
        index_path = os.path.join(REFERENCE_DIR, "reference_media.json")
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "top_n": TOP_N,
            "genres": reference_index,
        }
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print("")
        print("Reference media collection complete:")
        print("  Genres with references: %d / %d" % (
            len(reference_index), len(genres)
        ))
        print("  Total files copied: %d" % total_copied)
        print("  Index file: %s" % index_path)

    except Exception as e:
        print("ERROR: %s" % str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    collect_reference_media()
