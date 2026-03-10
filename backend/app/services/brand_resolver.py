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
