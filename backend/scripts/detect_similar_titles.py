#!/usr/bin/env python3
"""Detect similar ad titles using character trigram Jaccard similarity.

Compares all ad titles pairwise:
  1. Extract character trigrams from each normalized title
  2. Compute Jaccard similarity between trigram sets
  3. Threshold: > 0.6 = "similar", > 0.85 = "near_duplicate"
  4. Group similar ads into clusters using Union-Find
  5. Export clusters to exports/similar_ad_clusters.json
  6. Update ad_metadata["similar_ads"] for each ad with similar titles

No external NLP libraries required -- pure stdlib + SQLAlchemy.

Run from the backend directory:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/detect_similar_titles.py
"""

import json
import os
import re
import sys
from collections import defaultdict
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# ── Config ──────────────────────────────────────────────────────────────────

SIMILAR_THRESHOLD = 0.6          # Jaccard >= 0.6  -> "similar"
NEAR_DUPLICATE_THRESHOLD = 0.85  # Jaccard >= 0.85 -> "near_duplicate"
TRIGRAM_N = 3                    # character n-gram size
BATCH_SIZE = 50                  # commit every N metadata updates

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
EXPORT_PATH = os.path.join(EXPORT_DIR, "similar_ad_clusters.json")


# ── Text Processing ─────────────────────────────────────────────────────────


def normalize_title(text: str) -> str:
    """Normalize title for trigram comparison.

    Lowercases, collapses whitespace, and strips common bracket/punctuation
    noise so that trivially different titles are treated equally.
    """
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"\s+", " ", t)
    # Remove common decorative brackets / punctuation
    t = re.sub(r"[【】「」『』（）()\[\]{}\"']", "", t)
    return t


def char_trigrams(text: str) -> set[str]:
    """Extract the set of character trigrams from *text*.

    Returns an empty set if the text is too short to form any trigram.
    """
    if len(text) < TRIGRAM_N:
        return set()
    return {text[i:i + TRIGRAM_N] for i in range(len(text) - TRIGRAM_N + 1)}


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard index: |A & B| / |A | B|.

    Returns 0.0 when either set is empty.
    """
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return 0.0
    return intersection / union


# ── Union-Find ──────────────────────────────────────────────────────────────


class UnionFind:
    """Weighted Union-Find with path compression."""

    def __init__(self, elements):
        self.parent = {e: e for e in elements}
        self.rank = {e: 0 for e in elements}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # path compression
            x = self.parent[x]
        return x

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        # Union by rank
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def groups(self) -> dict[int, list[int]]:
        """Return {root: [members]} for all groups with 2+ members."""
        clusters: dict[int, list[int]] = defaultdict(list)
        for elem in self.parent:
            clusters[self.find(elem)].append(elem)
        return {r: sorted(members) for r, members in clusters.items()
                if len(members) >= 2}


# ── Main ────────────────────────────────────────────────────────────────────


def main():
    print("=" * 60)
    print("  Similar Title Detection (Trigram Jaccard)")
    print(f"  Similar threshold:        {SIMILAR_THRESHOLD}")
    print(f"  Near-duplicate threshold: {NEAR_DUPLICATE_THRESHOLD}")
    print(f"  N-gram size:              {TRIGRAM_N}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        total = len(ads)
        print(f"\nTotal ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # ── Phase 1: Build trigram sets ──────────────────────────────────

        print("\nPhase 1: Building trigram sets...")
        ad_trigrams: dict[int, set[str]] = {}
        ad_titles: dict[int, str] = {}       # id -> original title
        ad_advertisers: dict[int, str] = {}   # id -> advertiser_name
        skipped = 0

        for ad in ads:
            norm = normalize_title(ad.title or "")
            if len(norm) < TRIGRAM_N:
                skipped += 1
                continue
            tg = char_trigrams(norm)
            if tg:
                ad_trigrams[ad.id] = tg
                ad_titles[ad.id] = ad.title or ""
                ad_advertisers[ad.id] = (ad.advertiser_name or "").strip()

        valid_count = len(ad_trigrams)
        print(f"  Titles with valid trigrams: {valid_count}")
        print(f"  Skipped (title too short):  {skipped}")

        if valid_count < 2:
            print("\nNot enough titles to compare. Exiting.")
            return

        # ── Phase 2: Pairwise comparison ─────────────────────────────────

        print("\nPhase 2: Pairwise comparison...")
        ad_ids = sorted(ad_trigrams.keys())
        n = len(ad_ids)
        total_pairs = n * (n - 1) // 2
        print(f"  Ads to compare: {n} ({total_pairs} pairs)")

        # Store per-pair similarity for cluster max_similarity lookup
        pair_similarities: dict[tuple[int, int], float] = {}
        similar_count = 0
        near_dup_pair_count = 0

        uf = UnionFind(ad_ids)
        progress_step = max(1, n // 20)

        for idx, (i, j) in enumerate(combinations(range(n), 2)):
            aid_a = ad_ids[i]
            aid_b = ad_ids[j]
            sim = jaccard_similarity(ad_trigrams[aid_a], ad_trigrams[aid_b])

            if sim > SIMILAR_THRESHOLD:
                uf.union(aid_a, aid_b)
                pair_key = (min(aid_a, aid_b), max(aid_a, aid_b))
                pair_similarities[pair_key] = round(sim, 4)
                similar_count += 1
                if sim > NEAR_DUPLICATE_THRESHOLD:
                    near_dup_pair_count += 1

            # Progress report
            if i > 0 and i % progress_step == 0 and j == i + 1:
                print(f"  Progress: row {i}/{n} "
                      f"({similar_count} similar pairs so far)...")

        print(f"  Total pairs compared:          {total_pairs}")
        print(f"  Similar pairs (>{SIMILAR_THRESHOLD}):       {similar_count}")
        print(f"  Near-duplicate pairs (>{NEAR_DUPLICATE_THRESHOLD}): {near_dup_pair_count}")

        # ── Phase 3: Build clusters ──────────────────────────────────────

        print("\nPhase 3: Building clusters from Union-Find...")
        cluster_groups = uf.groups()  # {root: [member_ids]}
        print(f"  Clusters found: {len(cluster_groups)}")

        if not cluster_groups:
            print("No similar titles detected. Exiting.")
            return

        # ── Phase 4: Compute cluster metadata & export ───────────────────

        print("\nPhase 4: Computing cluster metadata and exporting...")
        export_clusters = []
        cluster_id = 0

        # Sort clusters by size descending for readability
        sorted_clusters = sorted(cluster_groups.values(), key=len, reverse=True)

        for members in sorted_clusters:
            cluster_id += 1

            # Find max similarity within this cluster
            max_sim = 0.0
            for a, b in combinations(members, 2):
                pair_key = (min(a, b), max(a, b))
                sim = pair_similarities.get(pair_key, 0.0)
                if sim > max_sim:
                    max_sim = sim

            # Determine cluster type based on max similarity
            cluster_type = "near_duplicate" if max_sim > NEAR_DUPLICATE_THRESHOLD else "similar"

            # Check if all ads share the same advertiser
            advertisers_in_cluster = {
                ad_advertisers[aid]
                for aid in members
                if ad_advertisers.get(aid, "")
            }
            same_advertiser = (len(advertisers_in_cluster) == 1)

            cluster_entry = {
                "cluster_id": cluster_id,
                "max_similarity": round(max_sim, 4),
                "type": cluster_type,
                "ads": [
                    {"id": aid, "title": ad_titles.get(aid, "")}
                    for aid in members
                ],
                "same_advertiser": same_advertiser,
            }
            export_clusters.append(cluster_entry)

            # Print top clusters inline
            if cluster_id <= 10:
                label = "NEAR-DUP" if cluster_type == "near_duplicate" else "SIMILAR"
                adv_label = "same-adv" if same_advertiser else "diff-adv"
                print(f"  Cluster {cluster_id}: {len(members)} ads, "
                      f"max_sim={max_sim:.4f}, {label}, {adv_label}")
                for aid in members[:3]:
                    title_preview = ad_titles.get(aid, "")[:70]
                    print(f"    - [ID {aid}] {title_preview}")
                if len(members) > 3:
                    print(f"    ... and {len(members) - 3} more")

        if len(sorted_clusters) > 10:
            print(f"  ... ({len(sorted_clusters) - 10} more clusters)")

        # Ensure export directory exists and write JSON
        os.makedirs(EXPORT_DIR, exist_ok=True)

        with open(EXPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(export_clusters, f, ensure_ascii=False, indent=2)

        print(f"\n  Exported {len(export_clusters)} clusters to: {EXPORT_PATH}")

        # ── Phase 5: Update ad_metadata["similar_ads"] ───────────────────

        print("\nPhase 5: Updating ad_metadata['similar_ads']...")

        # Build lookup: ad_id -> sorted list of similar ad_ids (cluster peers)
        similarity_map: dict[int, list[int]] = {}
        for members in cluster_groups.values():
            for aid in members:
                similarity_map[aid] = sorted([m for m in members if m != aid])

        ad_lookup = {ad.id: ad for ad in ads}
        updated = 0

        for ad_id, similar_ids in similarity_map.items():
            ad = ad_lookup.get(ad_id)
            if not ad:
                continue

            meta = dict(ad.ad_metadata or {})
            meta["similar_ads"] = similar_ids
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

            if updated % BATCH_SIZE == 0:
                session.commit()
                print(f"  Committed batch ({updated} ads updated)...")

        session.commit()
        print(f"  Total ads updated: {updated}")

        # ── Summary ──────────────────────────────────────────────────────

        near_dup_clusters = [c for c in export_clusters if c["type"] == "near_duplicate"]
        similar_clusters = [c for c in export_clusters if c["type"] == "similar"]
        near_dup_ads = sum(len(c["ads"]) for c in near_dup_clusters)
        similar_only_ads = sum(len(c["ads"]) for c in similar_clusters)
        total_clustered = near_dup_ads + similar_only_ads

        print(f"\n{'=' * 60}")
        print(f"  SIMILAR TITLE DETECTION RESULTS")
        print(f"{'=' * 60}")
        print(f"  {len(export_clusters)} clusters found, "
              f"{near_dup_ads} ads are near-duplicates, "
              f"{similar_only_ads} ads have similar titles")
        print(f"{'=' * 60}")
        print(f"  Ads analyzed:              {valid_count}")
        print(f"  Total clusters:            {len(export_clusters)}")
        print(f"    Near-duplicate clusters:  {len(near_dup_clusters)}")
        print(f"    Similar-only clusters:    {len(similar_clusters)}")
        print(f"  Total ads in clusters:     {total_clustered}")
        print(f"    Near-duplicate ads:       {near_dup_ads}")
        print(f"    Similar-only ads:         {similar_only_ads}")
        print(f"  Metadata updated:          {updated} ads")

        if export_clusters:
            largest = max(len(c["ads"]) for c in export_clusters)
            avg_size = total_clustered / len(export_clusters)
            print(f"  Largest cluster:           {largest} ads")
            print(f"  Average cluster size:      {avg_size:.1f}")

        # Size distribution
        size_dist: dict[int, int] = defaultdict(int)
        for c in export_clusters:
            size_dist[len(c["ads"])] += 1
        if size_dist:
            print(f"\n  Cluster size distribution:")
            for size in sorted(size_dist.keys()):
                print(f"    {size} ads: {size_dist[size]} cluster(s)")

        print(f"\n  Export file: {EXPORT_PATH}")
        print(f"{'=' * 60}")

    except Exception as e:
        session.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
