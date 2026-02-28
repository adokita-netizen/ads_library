"""Detect similar creatives using perceptual image hashing.

Compares thumbnails using perceptual hash (dhash) to group similar creatives:
  1. Compute perceptual hash (dhash) for each cached thumbnail
  2. Compare hashes to find similar images (Hamming distance <= threshold)
  3. Group similar creatives together
  4. Store groups in ad_metadata["similar_ads"] = [list of ad_ids]
  5. This helps identify ad variations / A-B tests

Uses Pillow for image hashing. Skips gracefully if not installed.

Run from the backend directory:
    cd backend
    python scripts/detect_similar_creatives.py
"""

import os
import sys
import logging
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
HASH_SIZE = 16              # dhash dimension (16x16 = 256-bit hash)
HAMMING_THRESHOLD = 12      # max Hamming distance to consider similar
BATCH_SIZE = 20             # commit every N rows

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")

# ── Pillow check ──────────────────────────────────────────────────────
_pillow_available = False
try:
    from PIL import Image
    _pillow_available = True
except ImportError:
    pass


def compute_dhash(image_path: str, hash_size: int = HASH_SIZE) -> int | None:
    """Compute difference hash (dhash) for an image.

    The dhash algorithm:
    1. Resize to (hash_size+1) x hash_size grayscale
    2. Compare adjacent horizontal pixels
    3. Each comparison generates 1 bit

    Returns an integer hash value, or None on error.
    """
    if not _pillow_available:
        return None
    try:
        with Image.open(image_path) as img:
            # Convert to grayscale and resize
            img = img.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
            pixels = list(img.getdata())

        # Compute horizontal gradient
        hash_val = 0
        for row in range(hash_size):
            for col in range(hash_size):
                offset = row * (hash_size + 1) + col
                # Compare pixel to its right neighbor
                if pixels[offset] > pixels[offset + 1]:
                    hash_val |= 1 << (row * hash_size + col)

        return hash_val
    except Exception as e:
        logger.debug("dhash failed for %s: %s", image_path, e)
        return None


def hamming_distance(hash1: int, hash2: int) -> int:
    """Compute Hamming distance between two integer hashes."""
    return bin(hash1 ^ hash2).count("1")


def find_image_path(ad_id: int) -> str | None:
    """Find the best available image file for an ad (thumbnail preferred)."""
    thumb_path = os.path.join(THUMB_DIR, f"{ad_id}.jpg")
    if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 100:
        return thumb_path

    img_path = os.path.join(IMAGE_DIR, f"{ad_id}.jpg")
    if os.path.exists(img_path) and os.path.getsize(img_path) > 100:
        return img_path

    return None


def main():
    if not _pillow_available:
        print("=" * 60)
        print("  Pillow (PIL) is not installed.")
        print("  Install with: pip install Pillow")
        print("  Skipping similarity detection.")
        print("=" * 60)
        return

    print("=" * 60)
    print("  Creative Similarity Detection (dhash)")
    print(f"  Hash size: {HASH_SIZE}x{HASH_SIZE} = {HASH_SIZE * HASH_SIZE}-bit")
    print(f"  Hamming threshold: {HAMMING_THRESHOLD}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        total = len(ads)
        print(f"\nTotal ads: {total}")

        # Phase 1: Compute hashes for all ads with cached images
        print("\nPhase 1: Computing perceptual hashes...")
        ad_hashes: dict[int, int] = {}  # ad_id -> hash_value
        skipped = 0

        for i, ad in enumerate(ads):
            img_path = find_image_path(ad.id)
            if not img_path:
                skipped += 1
                continue

            h = compute_dhash(img_path)
            if h is not None:
                ad_hashes[ad.id] = h

            if (i + 1) % 50 == 0:
                print(f"  Hashed {i + 1}/{total} ads...")

        print(f"  Hashed: {len(ad_hashes)} ads")
        print(f"  Skipped (no image): {skipped}")
        print(f"  Failed (hash error): {total - skipped - len(ad_hashes)}")

        if len(ad_hashes) < 2:
            print("\nNot enough hashed images to compare. Exiting.")
            return

        # Phase 2: Compare all pairs and group similar ones
        print("\nPhase 2: Comparing image pairs...")
        ad_id_list = list(ad_hashes.keys())
        n = len(ad_id_list)

        # Build similarity groups using Union-Find
        parent: dict[int, int] = {aid: aid for aid in ad_id_list}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]  # path compression
                x = parent[x]
            return x

        def union(x: int, y: int):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        comparisons = 0
        matches = 0

        for i in range(n):
            for j in range(i + 1, n):
                aid_a = ad_id_list[i]
                aid_b = ad_id_list[j]
                dist = hamming_distance(ad_hashes[aid_a], ad_hashes[aid_b])
                comparisons += 1

                if dist <= HAMMING_THRESHOLD:
                    union(aid_a, aid_b)
                    matches += 1

            if (i + 1) % 50 == 0:
                print(f"  Compared {i + 1}/{n} ads ({comparisons} pairs, {matches} matches)...")

        print(f"  Total comparisons: {comparisons}")
        print(f"  Similar pairs found: {matches}")

        # Phase 3: Build groups from Union-Find
        groups: dict[int, list[int]] = defaultdict(list)
        for aid in ad_id_list:
            root = find(aid)
            groups[root].append(aid)

        # Filter to only groups with 2+ members
        similar_groups = {root: members for root, members in groups.items() if len(members) >= 2}

        print(f"\nPhase 3: Found {len(similar_groups)} similarity groups")

        if not similar_groups:
            print("No similar creatives detected.")
            return

        # Print group details
        for group_id, (root, members) in enumerate(sorted(similar_groups.items()), 1):
            print(f"\n  Group {group_id} ({len(members)} ads): {members[:10]}{'...' if len(members) > 10 else ''}")

        # Phase 4: Store in ad_metadata
        print(f"\nPhase 4: Updating ad_metadata['similar_ads']...")
        updated = 0

        # Create a lookup: ad_id -> list of similar ad_ids
        similarity_map: dict[int, list[int]] = {}
        for root, members in similar_groups.items():
            for aid in members:
                # Similar ads = all group members except self
                similar_ids = [m for m in members if m != aid]
                similarity_map[aid] = similar_ids

        # Update database
        ad_lookup = {ad.id: ad for ad in ads}
        for ad_id, similar_ids in similarity_map.items():
            ad = ad_lookup.get(ad_id)
            if not ad:
                continue

            meta = dict(ad.ad_metadata or {})
            meta["similar_ads"] = similar_ids
            meta["similarity_group_size"] = len(similar_ids) + 1
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

            if updated % BATCH_SIZE == 0:
                session.commit()
                print(f"  Committed batch ({updated} ads updated)...")

        session.commit()

        # ── Summary ──
        print(f"\n{'=' * 60}")
        print(f"  SIMILARITY DETECTION RESULTS")
        print(f"{'=' * 60}")
        print(f"  Ads analyzed:          {len(ad_hashes)}")
        print(f"  Similarity groups:     {len(similar_groups)}")
        print(f"  Ads in groups:         {sum(len(m) for m in similar_groups.values())}")
        print(f"  Ads updated:           {updated}")
        print()
        print(f"  Largest group:         {max(len(m) for m in similar_groups.values())} ads")
        print(f"  Average group size:    {sum(len(m) for m in similar_groups.values()) / len(similar_groups):.1f}")
        print()

        # Distribution of group sizes
        size_dist: dict[int, int] = defaultdict(int)
        for members in similar_groups.values():
            size_dist[len(members)] += 1
        print(f"  Group size distribution:")
        for size in sorted(size_dist.keys()):
            print(f"    {size} ads: {size_dist[size]} groups")
        print(f"{'=' * 60}")

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        logger.exception("detect_similar_creatives failed")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
