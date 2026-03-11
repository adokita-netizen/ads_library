"""Creative family grouping via perceptual hash and text similarity.

Clusters CreativeAssets into CreativeFamily groups using:
  - Perceptual hash (phash) Hamming-distance similarity
  - Character-trigram Jaccard similarity for OCR/ASR text
  - Union-Find (disjoint set) for transitive clustering

No external dependencies beyond SQLAlchemy.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.creative_asset import CreativeAsset, CreativeFamily

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Union-Find (Disjoint Set)
# ---------------------------------------------------------------------------

class UnionFind:
    """Weighted quick-union with path compression."""

    def __init__(self) -> None:
        self._parent: dict[int, int] = {}
        self._rank: dict[int, int] = {}

    def make_set(self, x: int) -> None:
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]  # path halving
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1

    def groups(self) -> dict[int, list[int]]:
        """Return {root: [members]} mapping."""
        clusters: dict[int, list[int]] = {}
        for x in self._parent:
            root = self.find(x)
            clusters.setdefault(root, []).append(x)
        return clusters


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------

def compute_phash_similarity(hash_a: str, hash_b: str) -> float:
    """Hamming-distance-based similarity between two hex-encoded perceptual hashes.

    Returns a value in [0.0, 1.0] where 1.0 means identical hashes.
    """
    if not hash_a or not hash_b:
        return 0.0

    try:
        int_a = int(hash_a, 16)
        int_b = int(hash_b, 16)
    except ValueError:
        return 0.0

    # Determine total bits from the longer hex string (each hex char = 4 bits)
    total_bits = max(len(hash_a), len(hash_b)) * 4
    if total_bits == 0:
        return 0.0

    xor = int_a ^ int_b
    hamming_distance = bin(xor).count("1")
    return 1.0 - (hamming_distance / total_bits)


def compute_text_similarity(text_a: str, text_b: str) -> float:
    """Character-trigram Jaccard similarity.

    Returns a value in [0.0, 1.0].  Returns 0.0 when either input is empty.
    """
    if not text_a or not text_b:
        return 0.0

    def _trigrams(text: str) -> set[str]:
        t = text.strip().lower()
        if len(t) < 3:
            return {t} if t else set()
        return {t[i : i + 3] for i in range(len(t) - 2)}

    set_a = _trigrams(text_a)
    set_b = _trigrams(text_b)

    if not set_a or not set_b:
        return 0.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _combined_text(asset: CreativeAsset) -> str:
    """Merge OCR and ASR text into a single string for comparison."""
    parts: list[str] = []
    if asset.ocr_text:
        parts.append(asset.ocr_text.strip())
    if asset.asr_text:
        parts.append(asset.asr_text.strip())
    return " ".join(parts)


def _compute_centroid_phash(assets: list[CreativeAsset]) -> str | None:
    """Pick the phash closest to all others (medoid) as the centroid."""
    hashed = [a for a in assets if a.phash]
    if not hashed:
        return None
    if len(hashed) == 1:
        return hashed[0].phash

    best_asset = None
    best_total = -1.0
    for candidate in hashed:
        total = sum(
            compute_phash_similarity(candidate.phash, other.phash)
            for other in hashed
            if other.id != candidate.id
        )
        if total > best_total:
            best_total = total
            best_asset = candidate
    return best_asset.phash if best_asset else None


def _most_common_title(assets: list[CreativeAsset]) -> str | None:
    """Derive a family title from the most frequent ad title among members."""
    titles: list[str] = []
    for asset in assets:
        ad = asset.ad
        if ad and ad.title:
            titles.append(ad.title)
    if not titles:
        return None
    counter = Counter(titles)
    return counter.most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def build_creative_families(
    session: Session,
    phash_threshold: float = 0.85,
    text_threshold: float = 0.80,
) -> dict:
    """Cluster CreativeAssets into CreativeFamily groups.

    Returns ``{"families_created": int, "families_updated": int, "assets_linked": int}``.
    """

    # 1. Load eligible assets (have phash OR text)
    stmt = (
        select(CreativeAsset)
        .join(Ad, CreativeAsset.ad_id == Ad.id)
        .where(
            (CreativeAsset.phash.isnot(None))
            | (CreativeAsset.ocr_text.isnot(None))
            | (CreativeAsset.asr_text.isnot(None))
        )
    )
    assets: list[CreativeAsset] = list(session.scalars(stmt).all())
    if not assets:
        return {"families_created": 0, "families_updated": 0, "assets_linked": 0}

    # 2. Group by advertiser_name (via linked Ad)
    by_advertiser: dict[str, list[CreativeAsset]] = {}
    for asset in assets:
        ad = asset.ad
        advertiser = (ad.advertiser_name or "unknown") if ad else "unknown"
        by_advertiser.setdefault(advertiser, []).append(asset)

    families_created = 0
    families_updated = 0
    assets_linked = 0

    for advertiser, adv_assets in by_advertiser.items():
        # 3. Build Union-Find for this advertiser's assets
        uf = UnionFind()
        asset_map: dict[int, CreativeAsset] = {}
        for a in adv_assets:
            uf.make_set(a.id)
            asset_map[a.id] = a

        n = len(adv_assets)
        for i in range(n):
            for j in range(i + 1, n):
                ai, aj = adv_assets[i], adv_assets[j]

                # 3a. phash comparison
                if ai.phash and aj.phash:
                    sim = compute_phash_similarity(ai.phash, aj.phash)
                    if sim >= phash_threshold:
                        uf.union(ai.id, aj.id)
                        continue

                # 3b. Text fallback (only when at least one side lacks phash)
                if not ai.phash or not aj.phash:
                    text_i = _combined_text(ai)
                    text_j = _combined_text(aj)
                    if text_i and text_j:
                        sim = compute_text_similarity(text_i, text_j)
                        if sim >= text_threshold:
                            uf.union(ai.id, aj.id)

        # 4. Process clusters
        for _root, member_ids in uf.groups().items():
            cluster = [asset_map[mid] for mid in member_ids]

            # Determine canonical info
            family_title = _most_common_title(cluster)
            ad_ids: set[int] = set()
            platforms: set[str] = set()
            first_seen: datetime | None = None
            last_seen: datetime | None = None

            for asset in cluster:
                ad = asset.ad
                if ad:
                    ad_ids.add(ad.id)
                    if ad.platform:
                        platforms.add(ad.platform.value if hasattr(ad.platform, "value") else str(ad.platform))
                    if ad.first_seen_at:
                        if first_seen is None or ad.first_seen_at < first_seen:
                            first_seen = ad.first_seen_at
                    if ad.last_seen_at:
                        if last_seen is None or ad.last_seen_at > last_seen:
                            last_seen = ad.last_seen_at

            active_days = 0
            if first_seen and last_seen:
                active_days = max((last_seen - first_seen).days, 0)

            # Find existing family or create a new one
            # Check if any member already belongs to a family
            existing_family_id: int | None = None
            for asset in cluster:
                if asset.family_id is not None:
                    existing_family_id = asset.family_id
                    break

            if existing_family_id is not None:
                family = session.get(CreativeFamily, existing_family_id)
                if family is None:
                    # Stale FK — create new
                    family = CreativeFamily()
                    session.add(family)
                    session.flush()
                    families_created += 1
                else:
                    families_updated += 1
            else:
                family = CreativeFamily()
                session.add(family)
                session.flush()
                families_created += 1

            family.canonical_advertiser_name = advertiser
            family.family_title = family_title
            family.member_count = len(cluster)
            family.variant_count = len(ad_ids)
            family.platform_count = len(platforms)
            family.first_seen = first_seen
            family.last_seen = last_seen
            family.active_days = active_days

            # Compute centroid for membership scores
            centroid_phash = _compute_centroid_phash(cluster)
            centroid_text: str | None = None
            if not centroid_phash:
                # Use longest text as centroid proxy
                texts = [(a, _combined_text(a)) for a in cluster]
                texts_with_content = [(a, t) for a, t in texts if t]
                if texts_with_content:
                    texts_with_content.sort(key=lambda x: len(x[1]), reverse=True)
                    centroid_text = texts_with_content[0][1]

            # Assign family to each asset
            for asset in cluster:
                asset.family_id = family.id

                # Compute membership score
                score = 1.0  # default for singleton or centroid
                if centroid_phash and asset.phash:
                    score = compute_phash_similarity(asset.phash, centroid_phash)
                elif centroid_text:
                    asset_text = _combined_text(asset)
                    if asset_text:
                        score = compute_text_similarity(asset_text, centroid_text)

                asset.family_membership_score = score
                assets_linked += 1

    session.flush()
    return {
        "families_created": families_created,
        "families_updated": families_updated,
        "assets_linked": assets_linked,
    }


# ---------------------------------------------------------------------------
# Stats refresher
# ---------------------------------------------------------------------------

def update_family_stats(session: Session) -> dict:
    """Recompute aggregate statistics for every CreativeFamily.

    Returns ``{"updated": int}``.
    """
    families: list[CreativeFamily] = list(
        session.scalars(select(CreativeFamily)).all()
    )
    updated = 0

    for family in families:
        members: list[CreativeAsset] = list(
            session.scalars(
                select(CreativeAsset).where(CreativeAsset.family_id == family.id)
            ).all()
        )

        if not members:
            family.member_count = 0
            family.variant_count = 0
            family.platform_count = 0
            updated += 1
            continue

        ad_ids: set[int] = set()
        platforms: set[str] = set()
        first_seen: datetime | None = None
        last_seen: datetime | None = None

        for asset in members:
            ad: Ad | None = session.get(Ad, asset.ad_id)
            if ad is None:
                continue

            ad_ids.add(ad.id)

            if ad.platform:
                platforms.add(
                    ad.platform.value if hasattr(ad.platform, "value") else str(ad.platform)
                )

            if ad.first_seen_at:
                if first_seen is None or ad.first_seen_at < first_seen:
                    first_seen = ad.first_seen_at
            if ad.last_seen_at:
                if last_seen is None or ad.last_seen_at > last_seen:
                    last_seen = ad.last_seen_at

        family.member_count = len(members)
        family.variant_count = len(ad_ids)
        family.platform_count = len(platforms)
        family.first_seen = first_seen
        family.last_seen = last_seen
        family.active_days = (
            max((last_seen - first_seen).days, 0) if first_seen and last_seen else 0
        )
        updated += 1

    session.flush()
    return {"updated": updated}
