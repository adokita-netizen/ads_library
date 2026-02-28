"""Fix creative_type inconsistencies across all ads.

Rules:
1. video_url is set but creative_type != "video" -> set to "video"
2. image_s3_keys has multiple images -> set to "carousel"
3. creative_type is NULL or "unknown" -> infer from available data:
   - video_url present -> "video"
   - image_s3_keys with multiple URLs -> "carousel"
   - image_url or thumbnail_url present -> "image"
   - else -> "unknown"
4. Print summary of all corrections

Run from the backend directory:
    cd backend
    python scripts/fix_creative_types.py
"""

import sys

sys.path.insert(0, ".")

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Helpers ────────────────────────────────────────────────────────


def _count_carousel_images(ad: Ad) -> int:
    """Count how many images are in image_s3_keys."""
    keys = ad.image_s3_keys
    if not keys or not isinstance(keys, dict):
        return 0
    urls = keys.get("urls", [])
    if isinstance(urls, list):
        return len(urls)
    return 0


def _infer_creative_type(ad: Ad) -> str:
    """Infer the correct creative_type based on available media data."""
    has_video = bool(ad.video_url)
    carousel_count = _count_carousel_images(ad)
    has_image = bool(ad.image_url)
    has_thumbnail = bool(ad.thumbnail_url)

    if has_video:
        return "video"
    if carousel_count > 1:
        return "carousel"
    if has_image or has_thumbnail:
        return "image"
    return "unknown"


# ── Main ──────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        all_ads = session.query(Ad).all()
        total = len(all_ads)
        print(f"Total ads: {total}")
        print()

        # Current distribution
        type_before = {}
        for ad in all_ads:
            ct = ad.creative_type or "null"
            type_before[ct] = type_before.get(ct, 0) + 1

        print("BEFORE - creative_type distribution:")
        for ct, count in sorted(type_before.items()):
            print(f"  {ct}: {count}")
        print()

        # Track corrections
        stats = {
            "video_url_but_not_video": 0,
            "carousel_detected": 0,
            "null_to_video": 0,
            "null_to_image": 0,
            "null_to_carousel": 0,
            "null_to_unknown": 0,
            "already_correct": 0,
        }

        corrections = []

        for ad in all_ads:
            old_type = ad.creative_type or "null"
            new_type = old_type
            reason = None

            # Rule 1: video_url present but creative_type is not "video"
            if ad.video_url and old_type != "video":
                new_type = "video"
                reason = "video_url_but_not_video"
                stats["video_url_but_not_video"] += 1

            # Rule 2: image_s3_keys has multiple images -> carousel
            elif _count_carousel_images(ad) > 1 and old_type != "carousel":
                new_type = "carousel"
                reason = "carousel_detected"
                stats["carousel_detected"] += 1

            # Rule 3: NULL or unknown -> infer
            elif old_type in ("null", "unknown", None) or ad.creative_type is None:
                inferred = _infer_creative_type(ad)
                if inferred != old_type:
                    new_type = inferred
                    if inferred == "video":
                        reason = "null_to_video"
                        stats["null_to_video"] += 1
                    elif inferred == "image":
                        reason = "null_to_image"
                        stats["null_to_image"] += 1
                    elif inferred == "carousel":
                        reason = "null_to_carousel"
                        stats["null_to_carousel"] += 1
                    else:
                        reason = "null_to_unknown"
                        stats["null_to_unknown"] += 1
                else:
                    stats["already_correct"] += 1
                    continue
            else:
                stats["already_correct"] += 1
                continue

            # Apply the correction
            if reason and new_type != old_type:
                ad.creative_type = new_type
                corrections.append({
                    "ad_id": ad.id,
                    "old": old_type,
                    "new": new_type,
                    "reason": reason,
                })

                # Update ad_metadata with correction record
                meta = dict(ad.ad_metadata or {})
                meta["creative_type_fixed"] = True
                meta["creative_type_fix_reason"] = reason
                meta["creative_type_old"] = old_type
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

        session.commit()

        # Print corrections
        total_fixed = len(corrections)
        print("=" * 60)
        print("CREATIVE TYPE FIX RESULTS")
        print("=" * 60)
        print(f"Total ads:           {total}")
        print(f"Total corrected:     {total_fixed}")
        print(f"Already correct:     {stats['already_correct']}")
        print()

        if corrections:
            print("Corrections detail:")
            for c in corrections:
                print(f"  Ad {c['ad_id']}: {c['old']} -> {c['new']} ({c['reason']})")
            print()

        print("Correction breakdown:")
        print(f"  video_url present but type!=video: {stats['video_url_but_not_video']}")
        print(f"  carousel detected (multi-image):   {stats['carousel_detected']}")
        print(f"  null/unknown -> video:             {stats['null_to_video']}")
        print(f"  null/unknown -> image:             {stats['null_to_image']}")
        print(f"  null/unknown -> carousel:          {stats['null_to_carousel']}")
        print(f"  null/unknown -> unknown (no data): {stats['null_to_unknown']}")
        print()

        # After distribution
        type_after = {}
        for ad in all_ads:
            ct = ad.creative_type or "null"
            type_after[ct] = type_after.get(ct, 0) + 1

        print("AFTER - creative_type distribution:")
        for ct, count in sorted(type_after.items()):
            print(f"  {ct}: {count}")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
