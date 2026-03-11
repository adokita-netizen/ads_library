"""Ad card builder — creates AdCard entities from existing ad data.

Converts the current flat ad structure (image_s3_keys JSON array, single
body text) into first-class AdCard entities with per-card metadata.
Also parses Meta carousel data from ad_metadata, using the 4 parallel
Meta API arrays: bodies, link_titles, link_descriptions, link_captions.
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


def _looks_like_domain_or_url(text: str | None) -> bool:
    """Return True if the text looks like a domain name or URL rather than a CTA label."""
    if not text:
        return False
    t = text.strip().lower()
    # Contains a dot with no spaces → likely a domain/URL
    if "." in t and " " not in t:
        return True
    if t.startswith("http://") or t.startswith("https://"):
        return True
    return False


def _safe_list(meta: dict, *keys) -> list:
    """Extract a list from metadata, trying multiple key names.

    Returns the first non-empty list found, or [].
    """
    for key in keys:
        val = meta.get(key)
        if isinstance(val, list) and len(val) > 0:
            return val
    return []


def _safe_index(arr: list, idx: int):
    """Return arr[idx] if in range, else None."""
    if idx < len(arr):
        val = arr[idx]
        # Treat empty strings as None for cleanliness
        if isinstance(val, str) and val.strip() == "":
            return None
        return val
    return None


def build_cards_for_ad(session: Session, ad: Ad) -> list[AdCard]:
    """Create AdCard entities from an existing Ad record.

    Uses the 4 parallel Meta API arrays stored in ad_metadata to populate
    per-card copy fields.  Card count is determined by:

        card_count = max(len(bodies), len(titles), len(captions),
                        len(descriptions), len(image_s3_keys))

    For single-card ads (card_count <= 1), falls back to the flat Ad fields
    (ad.title, ad.description) when metadata arrays are absent.
    """
    # Check if cards already exist
    existing = session.query(AdCard).filter(AdCard.ad_id == ad.id).count()
    if existing > 0:
        return []

    meta = ad.ad_metadata or {}

    # ── Extract the 4 parallel Meta API arrays ──────────────────────────
    bodies = _safe_list(meta, "ad_creative_bodies")
    titles = _safe_list(meta, "ad_creative_link_titles")
    descriptions = _safe_list(
        meta, "ad_creative_link_descriptions", "link_descriptions"
    )
    captions = _safe_list(meta, "ad_creative_link_captions", "link_captions")

    # ── Image / media keys ──────────────────────────────────────────────
    image_keys: list = []
    raw_keys = ad.image_s3_keys if hasattr(ad, "image_s3_keys") and ad.image_s3_keys else None
    if isinstance(raw_keys, list):
        image_keys = raw_keys

    # ── Compute card count ──────────────────────────────────────────────
    card_count = max(
        len(bodies),
        len(titles),
        len(captions),
        len(descriptions),
        len(image_keys),
        1,  # At least 1 card always
    )

    # ── Determine base media type ───────────────────────────────────────
    base_media_type: str | None = None
    if ad.creative_type and ad.creative_type in ("image", "video"):
        base_media_type = ad.creative_type
    if not base_media_type:
        base_media_type = (
            _guess_media_type(ad.video_url)
            or _guess_media_type(ad.image_url)
            or "image"
        )

    cards: list[AdCard] = []

    for idx in range(card_count):
        # ── Per-card copy from Meta arrays (None if index out of range) ─
        body = _safe_index(bodies, idx)
        title = _safe_index(titles, idx)
        description = _safe_index(descriptions, idx)
        caption = _safe_index(captions, idx)

        # For single-card ads, fall back to flat Ad fields when arrays empty
        if card_count == 1:
            if body is None:
                body = ad.description
            if title is None:
                title = ad.title

        # ── CTA / display_url from caption ──────────────────────────────
        cta: str | None = None
        card_meta: dict = {"source": "meta_api_normalized"}
        if caption is not None:
            card_meta["link_caption"] = caption
            if _looks_like_domain_or_url(caption):
                card_meta["display_url"] = caption
            else:
                # Treat non-URL caption as a CTA label
                cta = caption

        # ── Media assignment ────────────────────────────────────────────
        img_key = _safe_index(image_keys, idx)
        img_url: str | None = None
        img_s3: str | None = None
        vid_url: str | None = None
        vid_s3: str | None = None
        media_type = base_media_type

        if img_key and isinstance(img_key, str):
            if img_key.startswith("http"):
                img_url = img_key
            else:
                img_s3 = img_key
            media_type = "image"
        elif idx == 0:
            # First card inherits the Ad-level media
            img_url = ad.image_url
            img_s3 = getattr(ad, "image_s3_key", None)
            vid_url = ad.video_url
            vid_s3 = getattr(ad, "video_s3_key", None)

        # ── Destination ─────────────────────────────────────────────────
        lp_final = None
        if isinstance(meta.get("lp_info"), dict):
            lp_final = meta["lp_info"].get("final_url")

        card = AdCard(
            ad_id=ad.id,
            brand_id=ad.brand_id,
            card_index=idx,
            body_text=body,
            link_title=title,
            link_description=description,
            call_to_action=cta,
            media_type=media_type,
            image_url=img_url,
            image_s3_key=img_s3,
            video_url=vid_url,
            video_s3_key=vid_s3,
            destination_url_initial=ad.destination_url,
            destination_url_final=lp_final if idx == 0 else None,
            destination_domain=_extract_domain(ad.destination_url),
            card_metadata=card_meta,
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
