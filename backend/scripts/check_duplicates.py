#!/usr/bin/env python3
"""Check for duplicate or near-duplicate ads.

Finds ads with identical/similar titles or same advertiser + similar title.
Uses simple string similarity (not Levenshtein, stdlib only).

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/check_duplicates.py
"""

import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Similarity Functions ─────────────────────────────────────────────────


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""
    # Remove whitespace, lowercase, strip punctuation
    t = text.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[【】「」『』（）()[\]{}]", "", t)
    return t


def simple_similarity(a: str, b: str) -> float:
    """Compute simple similarity ratio using shared character bigrams."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    # Character bigram overlap
    bigrams_a = set(a[i:i+2] for i in range(len(a) - 1))
    bigrams_b = set(b[i:i+2] for i in range(len(b) - 1))

    if not bigrams_a or not bigrams_b:
        return 0.0

    overlap = bigrams_a & bigrams_b
    return 2 * len(overlap) / (len(bigrams_a) + len(bigrams_b))


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print(f"[check_duplicates] Total ads: {len(ads)}")

        # 1. Find exact title duplicates
        title_groups: dict[str, list[Ad]] = defaultdict(list)
        for ad in ads:
            norm = normalize_text(ad.title or "")
            if norm:
                title_groups[norm].append(ad)

        exact_dupes = {k: v for k, v in title_groups.items() if len(v) > 1}
        print(f"\n  Exact title duplicates: {len(exact_dupes)} groups")
        for title, group in list(exact_dupes.items())[:5]:
            ids = [a.id for a in group]
            print(f"    IDs {ids}: '{title[:60]}'")

        # 2. Find same advertiser + similar title
        adv_groups: dict[str, list[Ad]] = defaultdict(list)
        for ad in ads:
            name = (ad.advertiser_name or "").strip()
            if name:
                adv_groups[name].append(ad)

        similar_pairs = []
        for adv, adv_ads in adv_groups.items():
            if len(adv_ads) < 2:
                continue
            for i in range(len(adv_ads)):
                for j in range(i + 1, len(adv_ads)):
                    t1 = normalize_text(adv_ads[i].title or "")
                    t2 = normalize_text(adv_ads[j].title or "")
                    if not t1 or not t2:
                        continue
                    sim = simple_similarity(t1, t2)
                    if sim >= 0.8 and t1 != t2:
                        similar_pairs.append({
                            "advertiser": adv,
                            "ad1_id": adv_ads[i].id,
                            "ad2_id": adv_ads[j].id,
                            "title1": (adv_ads[i].title or "")[:60],
                            "title2": (adv_ads[j].title or "")[:60],
                            "similarity": round(sim, 3),
                        })

        print(f"\n  Near-duplicate pairs (same advertiser, sim >= 0.8): {len(similar_pairs)}")
        for pair in similar_pairs[:5]:
            print(f"    {pair['advertiser']}: ID {pair['ad1_id']} vs {pair['ad2_id']} "
                  f"(sim={pair['similarity']})")

        # 3. Flag duplicates in metadata
        dup_ids = set()
        for title, group in exact_dupes.items():
            # Keep the first (oldest), flag the rest
            sorted_group = sorted(group, key=lambda a: a.created_at or datetime.min.replace(tzinfo=timezone.utc))
            for ad in sorted_group[1:]:
                dup_ids.add(ad.id)

        for pair in similar_pairs:
            dup_ids.add(pair["ad2_id"])

        flagged = 0
        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            is_dup = ad.id in dup_ids
            if meta.get("is_duplicate") != is_dup:
                meta["is_duplicate"] = is_dup
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                flagged += 1

        session.commit()
        print(f"\n  Flagged as duplicate: {len(dup_ids)} ads")
        print(f"  Metadata updated: {flagged} ads")

        # Summary
        print(f"\n  Summary:")
        print(f"    Exact duplicate groups: {len(exact_dupes)}")
        print(f"    Near-duplicate pairs: {len(similar_pairs)}")
        print(f"    Total flagged: {len(dup_ids)}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
