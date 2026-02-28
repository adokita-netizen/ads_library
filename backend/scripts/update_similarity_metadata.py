#!/usr/bin/env python3
"""Update ad metadata with consolidated similarity data from exported JSON files.

Reads output from the three A23 analysis scripts:
  - similar_ad_clusters.json   (title-based similarity clusters)
  - ab_test_pairs.json         (A/B test pairs within same advertiser)
  - creative_pattern_groups.json (creative fingerprint groups)

For each ad, updates ad_metadata with:
  - similar_ad_ids:       list of ad IDs with similar titles
  - duplicate_cluster_id: cluster ID if part of a near-duplicate cluster (sim > 0.85)
  - ab_test_group:        pair ID if identified as likely A/B variant
  - creative_fingerprint: human-readable string like "urgency+purchase+skincare"

Commits in batches of 50. Uses flag_modified for every updated ad.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/update_similarity_metadata.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

BATCH_SIZE = 50


def load_json_safe(path):
    """Load a JSON file safely. Returns empty list on missing file or parse error."""
    if not os.path.exists(path):
        print(f"  WARNING: File not found, skipping: {path}")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            print(f"  WARNING: Expected list in {os.path.basename(path)}, got {type(data).__name__}")
            return []
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ERROR: Failed to read {os.path.basename(path)}: {e}")
        return []


def build_similar_and_duplicate_maps(clusters):
    """Parse similar_ad_clusters.json into similarity and duplicate-cluster maps.

    Returns:
        similar_map:     dict[int, set[int]]  ad_id -> set of similar ad_ids
        dup_cluster_map: dict[int, int]        ad_id -> cluster_id (near-dup only)
    """
    similar_map = defaultdict(set)
    dup_cluster_map = {}

    for cluster in clusters:
        cluster_id = cluster.get("cluster_id", 0)
        ads_list = cluster.get("ads", [])
        ad_ids = [a.get("id") for a in ads_list if a.get("id") is not None]
        is_near_dup = cluster.get("is_near_duplicate", False)
        similarity = cluster.get("similarity", 0)

        # Use explicit similarity value when available; fall back to boolean flag
        if similarity >= 0.85:
            is_near_dup = True

        for aid in ad_ids:
            for other_id in ad_ids:
                if other_id != aid:
                    similar_map[aid].add(other_id)
            if is_near_dup:
                dup_cluster_map[aid] = cluster_id

    return similar_map, dup_cluster_map


def build_ab_test_map(pairs):
    """Parse ab_test_pairs.json into A/B test group map.

    Returns:
        ab_group_map: dict[int, int]  ad_id -> pair_id
    """
    ab_group_map = {}

    for pair in pairs:
        pair_id = pair.get("pair_id")
        if pair_id is None:
            continue

        ad_a = pair.get("ad_a", {})
        ad_b = pair.get("ad_b", {})
        ad_a_id = ad_a.get("id")
        ad_b_id = ad_b.get("id")

        if ad_a_id is not None:
            ab_group_map[ad_a_id] = pair_id
        if ad_b_id is not None:
            ab_group_map[ad_b_id] = pair_id

    return ab_group_map


def build_fingerprint_map(groups):
    """Parse creative_pattern_groups.json into fingerprint map.

    The fingerprint field in each group is "hook_type|cta_type|genre".
    Convert to human-readable form: "hook_type+cta_type+genre".

    Returns:
        fp_map: dict[int, str]  ad_id -> human-readable fingerprint string
    """
    fp_map = {}

    for group in groups:
        # Build human-readable fingerprint from components
        hook = (group.get("hook_type") or "none").strip()
        cta = (group.get("cta_type") or "none").strip()
        genre = (group.get("genre") or "other").strip()

        # Join non-empty, non-"none" components with "+"
        parts = []
        for part in [hook, cta, genre]:
            cleaned = part.lower().replace(" ", "_")
            if cleaned and cleaned != "none":
                parts.append(cleaned)

        if not parts:
            fingerprint = "unknown"
        else:
            fingerprint = "+".join(parts)

        # Map each ad in this group to the fingerprint
        ads_list = group.get("ads", [])
        for ad_entry in ads_list:
            ad_id = ad_entry.get("ad_id")
            if ad_id is not None:
                fp_map[ad_id] = fingerprint

    return fp_map


def main():
    print("=" * 60)
    print("Update Similarity Metadata")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    export_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports"
    )

    # ── Load input files ─────────────────────────────────────────────
    print(f"\nLoading cluster files from: {export_dir}")

    similar_clusters = load_json_safe(os.path.join(export_dir, "similar_ad_clusters.json"))
    ab_test_pairs = load_json_safe(os.path.join(export_dir, "ab_test_pairs.json"))
    creative_groups = load_json_safe(os.path.join(export_dir, "creative_pattern_groups.json"))

    print(f"  Similar clusters loaded:         {len(similar_clusters)}")
    print(f"  A/B test pairs loaded:           {len(ab_test_pairs)}")
    print(f"  Creative pattern groups loaded:  {len(creative_groups)}")

    # ── Build lookup maps ────────────────────────────────────────────
    print("\nBuilding lookup maps...")

    similar_map, dup_cluster_map = build_similar_and_duplicate_maps(similar_clusters)
    ab_group_map = build_ab_test_map(ab_test_pairs)
    fp_map = build_fingerprint_map(creative_groups)

    print(f"  Ads with similar IDs:            {len(similar_map)}")
    print(f"  Ads in near-duplicate clusters:  {len(dup_cluster_map)}")
    print(f"  Ads in A/B test groups:          {len(ab_group_map)}")
    print(f"  Ads with creative fingerprint:   {len(fp_map)}")

    # ── Update database ──────────────────────────────────────────────
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        updated = 0
        count_similar = 0
        count_dup_cluster = 0
        count_ab_test = 0
        count_fingerprint = 0

        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            changed = False

            # 1. similar_ad_ids
            if ad.id in similar_map:
                meta["similar_ad_ids"] = sorted(list(similar_map[ad.id]))
                count_similar += 1
                changed = True
            elif "similar_ad_ids" not in meta:
                # Initialize as empty list for ads without matches
                meta["similar_ad_ids"] = []
                changed = True

            # 2. duplicate_cluster_id
            if ad.id in dup_cluster_map:
                meta["duplicate_cluster_id"] = dup_cluster_map[ad.id]
                count_dup_cluster += 1
                changed = True
            elif "duplicate_cluster_id" in meta:
                # Remove stale cluster assignment if no longer in a near-dup cluster
                del meta["duplicate_cluster_id"]
                changed = True

            # 3. ab_test_group
            if ad.id in ab_group_map:
                meta["ab_test_group"] = ab_group_map[ad.id]
                count_ab_test += 1
                changed = True
            elif "ab_test_group" in meta:
                # Remove stale A/B group assignment
                del meta["ab_test_group"]
                changed = True

            # 4. creative_fingerprint
            if ad.id in fp_map:
                fp = fp_map[ad.id]
                if meta.get("creative_fingerprint") != fp:
                    meta["creative_fingerprint"] = fp
                    changed = True
                count_fingerprint += 1
            elif "creative_fingerprint" in meta:
                del meta["creative_fingerprint"]
                changed = True

            # Persist if anything changed
            if changed:
                meta["similarity_updated_at"] = datetime.now(timezone.utc).isoformat()
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                updated += 1

                # Batch commit every BATCH_SIZE ads
                if updated % BATCH_SIZE == 0:
                    session.commit()
                    print(f"  Committed batch {updated // BATCH_SIZE} ({updated} ads updated)...")

        # Final commit for remaining ads
        if updated % BATCH_SIZE != 0:
            session.commit()

        # ── Summary ──────────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print(f"  UPDATE SIMILARITY METADATA - SUMMARY")
        print(f"{'=' * 60}")
        print(f"  {count_similar} ads updated with similar_ad_ids")
        print(f"  {count_dup_cluster} ads in near-duplicate clusters")
        print(f"  {count_ab_test} ads in A/B test groups")
        print(f"  {count_fingerprint} ads with creative fingerprint")
        print(f"{'=' * 60}")
        print(f"  Total ads processed: {total}")
        print(f"  Total ads updated:   {updated}")
        print(f"{'=' * 60}")
        print("Done!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
