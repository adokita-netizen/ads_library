"""Ad card builder — creates AdCard entities from existing ad data.

Converts the current flat ad structure (image_s3_keys JSON array, single
body text) into first-class AdCard entities with per-card metadata.
Also parses Meta carousel data from ad_metadata.
"""

from datetime import datetime, timezone
from urllib.parse import urlparse

import structlog
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.brand_registry import AdCard

logger = structlog.get_logger()


def _guess_media_type(url: str | None) -> str | None:
    """Guess media type from URL extension."""
    if not url:
        return None
    lower = url.lower().split("?")[0]
    if any(lower.endswith(ext) for ext in [".mp4", ".webm", ".mov", ".avi"]):
        return "video"
    if any(lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
        return "image"
    return None


def _extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).hostname or ""
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return None


def build_cards_for_ad(session: Session, ad: Ad) -> list[AdCard]:
    """Create AdCard entities from an existing Ad record.

    Handles three cases:
    1. Carousel ads with image_s3_keys (JSON array)
    2. Single-image ads
    3. Video ads
    """
    # Check if cards already exist
    existing = session.query(AdCard).filter(AdCard.ad_id == ad.id).count()
    if existing > 0:
        return []

    cards = []
    meta = ad.ad_metadata or {}

    # Case 1: Carousel — multiple images
    image_keys = ad.image_s3_keys if hasattr(ad, "image_s3_keys") and ad.image_s3_keys else None
    if isinstance(image_keys, list) and len(image_keys) > 1:
        for idx, key in enumerate(image_keys):
            card = AdCard(
                ad_id=ad.id,
                brand_id=ad.brand_id,
                card_index=idx,
                body_text=ad.description if idx == 0 else None,
                link_title=ad.title if idx == 0 else None,
                media_type="image",
                image_s3_key=key if isinstance(key, str) else None,
                image_url=key if isinstance(key, str) and key.startswith("http") else None,
                destination_url_initial=ad.destination_url,
                destination_domain=_extract_domain(ad.destination_url),
                card_metadata={"source": "carousel_migration"},
            )
            cards.append(card)

    # Case 2: Single image or video — create one card
    elif not cards:
        media_type = None
        if ad.creative_type:
            media_type = ad.creative_type if ad.creative_type in ("image", "video") else None
        if not media_type:
            media_type = _guess_media_type(ad.video_url) or _guess_media_type(ad.image_url) or "image"

        card = AdCard(
            ad_id=ad.id,
            brand_id=ad.brand_id,
            card_index=0,
            body_text=ad.description,
            link_title=ad.title,
            media_type=media_type,
            image_url=ad.image_url,
            image_s3_key=getattr(ad, "image_s3_key", None),
            video_url=ad.video_url,
            video_s3_key=getattr(ad, "video_s3_key", None),
            destination_url_initial=ad.destination_url,
            destination_url_final=meta.get("lp_info", {}).get("final_url") if isinstance(meta, dict) else None,
            destination_domain=_extract_domain(ad.destination_url),
            card_metadata={"source": "single_migration"},
        )
        cards.append(card)

    for card in cards:
        session.add(card)

    return cards


def batch_build_cards(session: Session, limit: int = 1000) -> dict:
    """Build AdCard entities for all ads that don't have cards yet.

    Returns summary dict.
    """
    # Find ads without cards
    from sqlalchemy import func

    ads_with_cards = session.query(AdCard.ad_id).distinct().subquery()
    ads = (
        session.query(Ad)
        .filter(~Ad.id.in_(session.query(ads_with_cards.c.ad_id)))
        .limit(limit)
        .all()
    )

    total_cards = 0
    processed = 0

    for ad in ads:
        new_cards = build_cards_for_ad(session, ad)
        total_cards += len(new_cards)
        processed += 1

    session.commit()
    logger.info("card_build_complete", processed=processed, total_cards=total_cards)
    return {"processed": processed, "total_cards": total_cards}
