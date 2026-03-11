"""Brand resolution service — normalizes advertiser names to canonical brands.

Auto-discovers brands from advertiser_name, groups similar names,
and maintains the brand_registry master table.
"""

import re
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.brand_registry import BrandRegistry

logger = structlog.get_logger()

# Common suffixes to strip for normalization
_STRIP_SUFFIXES = [
    r"\s*(株式会社|合同会社|有限会社|一般社団法人|Inc\.|Co\.,?\s*Ltd\.?|Corp\.?|LLC|Ltd\.?)\.?\s*$",
    r"\s*公式\s*$",
    r"\s*【公式】\s*",
    r"\s*\|.*$",  # Strip everything after pipe
]

_STRIP_PREFIXES = [
    r"^(株式会社|合同会社)\s*",
]

# Common suffixes that should not cause brand split
_IGNORABLE_SUFFIXES = [
    r"[-\s]*短編ドラマ$",
    r"[-\s]*公式$",
    r"\s*【公式】$",
    r"\s*- Official$",
    r"\s*Official$",
    r"\s*\(公式\)$",
    r"\s*(株式会社|合同会社|有限会社|一般社団法人)$",
    r"\s*(Inc\.?|Co\.,?\s*Ltd\.?|Corp\.?|LLC|Ltd\.?)$",
]


def _fuzzy_match_score(name_a: str, name_b: str) -> float:
    """Character-level trigram similarity (Jaccard coefficient).

    Returns 0.0–1.0 where 1.0 means identical trigram sets.
    No external dependencies.
    """
    def _trigrams(s: str) -> set[str]:
        s = s.lower().strip()
        if len(s) < 3:
            return {s} if s else set()
        return {s[i:i + 3] for i in range(len(s) - 2)}

    a_tri = _trigrams(name_a)
    b_tri = _trigrams(name_b)
    if not a_tri and not b_tri:
        return 1.0
    if not a_tri or not b_tri:
        return 0.0
    intersection = len(a_tri & b_tri)
    union = len(a_tri | b_tri)
    return intersection / union if union else 0.0


def _strip_ignorable_suffixes(name: str) -> str:
    """Strip known ignorable suffixes for comparison purposes."""
    n = name.strip()
    for pat in _IGNORABLE_SUFFIXES:
        n = re.sub(pat, "", n, flags=re.IGNORECASE).strip()
    return n


def _is_likely_same_brand(
    name_a: str, name_b: str, threshold: float = 0.7
) -> bool:
    """Check if two brand names likely refer to the same brand.

    Uses three strategies (any match = True):
      1. Fuzzy trigram score >= threshold
      2. One name is a substring of the other (after normalization)
      3. Names differ only by common ignorable suffixes
    """
    if not name_a or not name_b:
        return False

    norm_a = _normalize_name(name_a).lower()
    norm_b = _normalize_name(name_b).lower()

    # Exact match after normalization
    if norm_a == norm_b:
        return True

    # Strategy 3: strip ignorable suffixes and compare
    stripped_a = _strip_ignorable_suffixes(norm_a)
    stripped_b = _strip_ignorable_suffixes(norm_b)
    if stripped_a and stripped_b and stripped_a == stripped_b:
        return True

    # Strategy 2: substring check
    if len(norm_a) >= 3 and len(norm_b) >= 3:
        if norm_a in norm_b or norm_b in norm_a:
            return True

    # Strategy 1: trigram similarity
    score = _fuzzy_match_score(norm_a, norm_b)
    if score >= threshold:
        return True

    return False


def _normalize_name(name: str) -> str:
    """Normalize advertiser name to canonical form."""
    if not name:
        return ""
    n = name.strip()
    for pat in _STRIP_PREFIXES:
        n = re.sub(pat, "", n)
    for pat in _STRIP_SUFFIXES:
        n = re.sub(pat, "", n, flags=re.IGNORECASE)
    # Normalize whitespace
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _extract_domain(url: str | None) -> str | None:
    """Extract root domain from URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        # Remove www prefix
        if host.startswith("www."):
            host = host[4:]
        return host if host else None
    except Exception:
        return None


def auto_discover_brands(session: Session, min_ads: int = 2) -> dict:
    """Discover and create brands from advertiser_name groupings.

    Groups by normalized advertiser_name, creates BrandRegistry entries
    for groups with >= min_ads, and links ads via brand_id.

    Returns summary dict.
    """
    # Get all unique advertiser names with counts
    rows = (
        session.query(
            Ad.advertiser_name,
            func.count(Ad.id).label("cnt"),
            func.min(Ad.first_seen_at).label("first"),
            func.max(Ad.last_seen_at).label("last"),
            func.avg(Ad.hit_proxy_score).label("avg_hp"),
        )
        .filter(Ad.advertiser_name.isnot(None), Ad.advertiser_name != "")
        .group_by(Ad.advertiser_name)
        .all()
    )

    # Group by normalized name
    groups: dict[str, list] = defaultdict(list)
    for row in rows:
        canonical = _normalize_name(row[0])
        if not canonical:
            continue
        groups[canonical].append({
            "raw_name": row[0],
            "count": row[1],
            "first_seen": row[2],
            "last_seen": row[3],
            "avg_hit_proxy": row[4],
        })

    # Second pass: fuzzy-merge similar groups
    canonical_names = list(groups.keys())
    merged_into: dict[str, str] = {}  # maps absorbed name -> surviving name
    for i in range(len(canonical_names)):
        name_i = canonical_names[i]
        if name_i in merged_into:
            continue
        for j in range(i + 1, len(canonical_names)):
            name_j = canonical_names[j]
            if name_j in merged_into:
                continue
            if _is_likely_same_brand(name_i, name_j):
                count_i = sum(v["count"] for v in groups[name_i])
                count_j = sum(v["count"] for v in groups[name_j])
                # Keep the larger group's canonical name
                if count_i >= count_j:
                    survivor, absorbed = name_i, name_j
                else:
                    survivor, absorbed = name_j, name_i
                groups[survivor].extend(groups[absorbed])
                merged_into[absorbed] = survivor
                logger.info(
                    "fuzzy_brand_merge",
                    absorbed=absorbed,
                    survivor=survivor,
                )
    # Remove absorbed groups
    for absorbed in merged_into:
        del groups[absorbed]

    # Get existing brands
    existing = {b.canonical_name: b for b in session.query(BrandRegistry).all()}

    created = 0
    updated = 0
    linked = 0

    for canonical, variants in groups.items():
        total_count = sum(v["count"] for v in variants)
        if total_count < min_ads and canonical not in existing:
            continue

        # Compute aggregated stats
        first_seen = min((v["first_seen"] for v in variants if v["first_seen"]), default=None)
        last_seen = max((v["last_seen"] for v in variants if v["last_seen"]), default=None)
        avg_hp_values = [v["avg_hit_proxy"] for v in variants if v["avg_hit_proxy"] is not None]
        avg_hp = sum(avg_hp_values) / len(avg_hp_values) if avg_hp_values else None

        aliases = list({v["raw_name"] for v in variants})

        if canonical in existing:
            brand = existing[canonical]
            brand.total_ad_count = total_count
            brand.aliases = aliases
            brand.first_seen_at = first_seen
            brand.last_seen_at = last_seen
            brand.avg_hit_proxy_score = round(avg_hp, 2) if avg_hp else None
            brand.updated_at = datetime.now(timezone.utc)
            updated += 1
        else:
            brand = BrandRegistry(
                canonical_name=canonical,
                display_name=canonical,
                aliases=aliases,
                total_ad_count=total_count,
                first_seen_at=first_seen,
                last_seen_at=last_seen,
                avg_hit_proxy_score=round(avg_hp, 2) if avg_hp else None,
            )
            session.add(brand)
            session.flush()  # Get brand.id
            created += 1

        # Link ads to brand
        for variant in variants:
            count = (
                session.query(Ad)
                .filter(Ad.advertiser_name == variant["raw_name"], Ad.brand_id.is_(None))
                .update({"brand_id": brand.id})
            )
            linked += count

    # Auto-detect domains from ad destination URLs
    brands_needing_domains = (
        session.query(BrandRegistry)
        .filter(BrandRegistry.domains.is_(None))
        .all()
    )
    for brand in brands_needing_domains:
        ads_sample = (
            session.query(Ad.destination_url)
            .filter(Ad.brand_id == brand.id, Ad.destination_url.isnot(None))
            .limit(20)
            .all()
        )
        domains = list({_extract_domain(row[0]) for row in ads_sample if _extract_domain(row[0])})
        if domains:
            brand.domains = domains

    # Auto-detect vertical from genre tags
    from app.models.creative_asset import AdGenreTag
    for brand in session.query(BrandRegistry).filter(BrandRegistry.vertical.is_(None)).all():
        top_genre = (
            session.query(AdGenreTag.genre_code, func.count(AdGenreTag.id).label("cnt"))
            .join(Ad, Ad.id == AdGenreTag.ad_id)
            .filter(Ad.brand_id == brand.id, AdGenreTag.is_primary.is_(True))
            .group_by(AdGenreTag.genre_code)
            .order_by(func.count(AdGenreTag.id).desc())
            .first()
        )
        if top_genre:
            # Map sub-genre to vertical
            genre_code = top_genre[0]
            vertical_map = {
                "beauty": "beauty", "skincare": "beauty", "hair_removal": "beauty",
                "cosmetics": "beauty", "hair_care": "beauty", "oral_care": "beauty",
                "health": "health", "diet": "health", "fitness": "health",
                "supplements": "health", "sleep": "health", "mens_health": "health",
                "finance": "finance", "insurance": "finance", "real_estate": "finance",
                "credit_card": "finance", "investment": "finance",
                "business": "business", "marketing": "business", "saas": "business",
                "education": "business", "career": "business",
                "lifestyle": "lifestyle", "food": "lifestyle", "fashion": "lifestyle",
                "pet": "lifestyle", "travel": "lifestyle",
            }
            brand.vertical = vertical_map.get(genre_code, genre_code.split("_")[0] if "_" in genre_code else genre_code)

    session.commit()
    logger.info("brand_discovery_complete", created=created, updated=updated, linked=linked)
    return {"created": created, "updated": updated, "linked": linked}


def merge_duplicate_brands(session: Session, threshold: float = 0.7) -> dict:
    """Find and merge duplicate brands in BrandRegistry using fuzzy matching.

    For each pair of brands that _is_likely_same_brand, merges the smaller
    brand into the larger one (by total_ad_count):
      - Reassigns all ads from duplicate to survivor
      - Combines aliases
      - Recomputes aggregate stats
      - Deletes the duplicate BrandRegistry row

    Returns {"merged_pairs": [{"survivor": ..., "absorbed": ...}, ...],
             "total_merged": int}
    """
    brands = session.query(BrandRegistry).all()
    brand_map: dict[int, BrandRegistry] = {b.id: b for b in brands}
    absorbed_ids: set[int] = set()
    merged_pairs: list[dict] = []

    brand_list = list(brand_map.values())
    for i in range(len(brand_list)):
        b_i = brand_list[i]
        if b_i.id in absorbed_ids:
            continue
        for j in range(i + 1, len(brand_list)):
            b_j = brand_list[j]
            if b_j.id in absorbed_ids:
                continue
            if _is_likely_same_brand(b_i.canonical_name, b_j.canonical_name, threshold):
                # Keep the brand with more ads
                count_i = b_i.total_ad_count or 0
                count_j = b_j.total_ad_count or 0
                if count_i >= count_j:
                    survivor, duplicate = b_i, b_j
                else:
                    survivor, duplicate = b_j, b_i

                # Reassign ads
                session.query(Ad).filter(Ad.brand_id == duplicate.id).update(
                    {"brand_id": survivor.id}
                )

                # Merge aliases
                survivor_aliases = set(survivor.aliases or [])
                duplicate_aliases = set(duplicate.aliases or [])
                survivor_aliases |= duplicate_aliases
                survivor_aliases.add(duplicate.canonical_name)
                survivor.aliases = list(survivor_aliases)

                # Recompute total_ad_count
                new_count = (
                    session.query(func.count(Ad.id))
                    .filter(Ad.brand_id == survivor.id)
                    .scalar()
                )
                survivor.total_ad_count = new_count or 0

                # Recompute date range
                date_stats = (
                    session.query(
                        func.min(Ad.first_seen_at),
                        func.max(Ad.last_seen_at),
                    )
                    .filter(Ad.brand_id == survivor.id)
                    .first()
                )
                if date_stats:
                    survivor.first_seen_at = date_stats[0]
                    survivor.last_seen_at = date_stats[1]

                survivor.updated_at = datetime.now(timezone.utc)

                # Delete duplicate
                session.delete(duplicate)
                absorbed_ids.add(duplicate.id)

                merged_pairs.append({
                    "survivor": survivor.canonical_name,
                    "absorbed": duplicate.canonical_name,
                })
                logger.info(
                    "brand_merged",
                    survivor=survivor.canonical_name,
                    absorbed=duplicate.canonical_name,
                )

    session.commit()
    logger.info("merge_duplicate_brands_complete", total_merged=len(merged_pairs))
    return {"merged_pairs": merged_pairs, "total_merged": len(merged_pairs)}
