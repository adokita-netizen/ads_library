"""Build unified searchable_text from multiple sources and store on Ad.searchable_text.

Combines ad copy, OCR/ASR text, LP metadata, and angle fact data into a single
searchable text column for full-text search and similarity matching.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.ad import Ad
from app.models.brand_registry import AdCard, AngleFact

logger = logging.getLogger(__name__)


def _clean_text(text: str | None) -> str:
    """Normalize whitespace and strip empty values."""
    if not text:
        return ""
    # Collapse whitespace (including full-width spaces)
    cleaned = re.sub(r"[\s\u3000]+", " ", text).strip()
    return cleaned


def _flatten_jsonb_list(value: Any) -> list[str]:
    """Safely extract strings from a JSONB list field.

    Handles: None, list of strings, list of dicts, nested structures.
    """
    if not value:
        return []
    if not isinstance(value, list):
        return [str(value)] if value else []
    result = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif isinstance(item, dict):
            # Extract values from dict items (e.g., {"type": "xxx", "text": "yyy"})
            for v in item.values():
                if isinstance(v, str) and v.strip():
                    result.append(v.strip())
        elif item is not None:
            s = str(item).strip()
            if s:
                result.append(s)
    return result


def _extract_lp_text(ad: Ad) -> str:
    """Extract LP text from ad_metadata.lp_info."""
    meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
    lp_info = meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}
    parts = []
    for key in ("title", "description"):
        val = _clean_text(lp_info.get(key))
        if val:
            parts.append(val)
    return " ".join(parts)


def _extract_card_text(cards: list[AdCard]) -> str:
    """Combine OCR, ASR, and body text from all cards."""
    parts = []
    for card in cards:
        for text in (card.ocr_text, card.asr_text, card.body_text, card.link_title, card.link_description):
            val = _clean_text(text)
            if val:
                parts.append(val)
    return " ".join(parts)


def _extract_angle_text(angle_facts: list[AngleFact]) -> str:
    """Extract searchable text from angle fact JSONB array fields."""
    parts = []
    for fact in angle_facts:
        if fact.hook_type:
            parts.append(fact.hook_type)
        for field in (
            fact.pain_points,
            fact.promises,
            fact.offer_types,
            fact.proof_types,
            fact.urgency_types,
            fact.audience_hints,
            fact.creative_styles,
        ):
            parts.extend(_flatten_jsonb_list(field))
        if fact.lp_pattern:
            parts.append(fact.lp_pattern)
    return " ".join(parts)


def _build_text_for_ad(ad: Ad, cards: list[AdCard], angle_facts: list[AngleFact]) -> str:
    """Assemble the final searchable text from all sources."""
    segments = []

    # 1. Ad title + description
    for text in (ad.title, ad.description):
        val = _clean_text(text)
        if val:
            segments.append(val)

    # 2. Card-level text (OCR, ASR, body)
    card_text = _extract_card_text(cards)
    if card_text:
        segments.append(card_text)

    # 3. LP info from ad_metadata
    lp_text = _extract_lp_text(ad)
    if lp_text:
        segments.append(lp_text)

    # 4. Angle fact data (hook types, pain points, offers, proofs)
    angle_text = _extract_angle_text(angle_facts)
    if angle_text:
        segments.append(angle_text)

    combined = " ".join(segments)
    # Deduplicate repeated tokens while preserving order
    seen: set[str] = set()
    tokens = []
    for token in combined.split():
        lower = token.lower()
        if lower not in seen:
            seen.add(lower)
            tokens.append(token)
    return " ".join(tokens)


def build_searchable_text(session: Session, limit: int = 1000) -> dict:
    """Build searchable_text for ads that don't have it yet.

    Combines: title + description + OCR text + ASR text + LP title + LP hero +
    angle fact data (hook_type, pain_points, offers, proofs)

    Sources:
    - Ad.title, Ad.description
    - AdCard.ocr_text, AdCard.asr_text, AdCard.body_text
    - ad_metadata.lp_info.title, ad_metadata.lp_info.description
    - AngleFact.pain_points, AngleFact.promises, AngleFact.offer_types, AngleFact.proof_types

    Returns {"updated": int}
    """
    # Find ads without searchable_text
    stmt = (
        select(Ad)
        .where(Ad.searchable_text.is_(None))
        .order_by(Ad.id)
        .limit(limit)
    )
    ads = session.scalars(stmt).all()

    if not ads:
        logger.info("No ads need searchable_text update.")
        return {"updated": 0}

    ad_ids = [ad.id for ad in ads]

    # Batch-load cards for these ads
    card_stmt = (
        select(AdCard)
        .where(AdCard.ad_id.in_(ad_ids))
        .options(joinedload(AdCard.angle_facts))
    )
    cards_by_ad: dict[int, list[AdCard]] = {}
    for card in session.scalars(card_stmt).unique().all():
        cards_by_ad.setdefault(card.ad_id, []).append(card)

    # Batch-load angle facts linked directly to ads (not via cards)
    direct_angle_stmt = (
        select(AngleFact)
        .where(AngleFact.ad_id.in_(ad_ids))
        .where(AngleFact.card_id.is_(None))
    )
    direct_angles_by_ad: dict[int, list[AngleFact]] = {}
    for fact in session.scalars(direct_angle_stmt).all():
        direct_angles_by_ad.setdefault(fact.ad_id, []).append(fact)

    updated = 0
    for ad in ads:
        cards = cards_by_ad.get(ad.id, [])
        # Collect angle facts from cards + direct ad-level facts
        angle_facts: list[AngleFact] = []
        for card in cards:
            angle_facts.extend(card.angle_facts)
        angle_facts.extend(direct_angles_by_ad.get(ad.id, []))

        text = _build_text_for_ad(ad, cards, angle_facts)
        if text:
            ad.searchable_text = text
            updated += 1

    session.flush()
    logger.info("Built searchable_text for %d ads.", updated)
    return {"updated": updated}
