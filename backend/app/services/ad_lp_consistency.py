"""Compute ad-to-LP text consistency score.

Measures how well ad copy aligns with LP content using token-level
Jaccard similarity, handling Japanese text without requiring MeCab.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.brand_registry import AdCard, AngleFact, LPSnapshot
from app.models.landing_page import LandingPage

logger = logging.getLogger(__name__)

# Characters to split Japanese text into quasi-tokens (bigrams for CJK, words for latin)
_CJK_RANGE = r"\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uFF00-\uFFEF"
_STOP_PATTERN = re.compile(r"[、。！？!?\s\u3000,.\-/]+")


def _tokenize_japanese(text: str) -> set[str]:
    """Tokenize mixed Japanese/English text into a set of tokens.

    Uses character bigrams for CJK characters and whitespace-split for Latin.
    This provides a reasonable approximation without requiring MeCab.
    """
    if not text:
        return set()

    text = text.lower().strip()
    # Remove punctuation/symbols but keep CJK and alphanumeric
    text = re.sub(r"[^\w" + _CJK_RANGE + r"]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    tokens: set[str] = set()

    # Split into segments: CJK runs vs Latin runs
    parts = re.split(r"(\s+)", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Check if mostly CJK
        cjk_chars = re.findall(r"[" + _CJK_RANGE + r"]", part)
        if len(cjk_chars) > len(part) * 0.3:
            # Use character bigrams for CJK-heavy text
            cleaned = re.sub(r"[^" + _CJK_RANGE + r"\w]", "", part)
            for i in range(len(cleaned) - 1):
                bigram = cleaned[i : i + 2]
                if len(bigram) == 2:
                    tokens.add(bigram)
            # Also add individual CJK chars for short strings
            if len(cleaned) <= 4:
                for ch in cleaned:
                    tokens.add(ch)
        else:
            # Latin text: use the word itself (min 2 chars)
            if len(part) >= 2:
                tokens.add(part)

    return tokens


def _clean_text(text: str | None) -> str:
    """Normalize whitespace."""
    if not text:
        return ""
    return re.sub(r"[\s\u3000]+", " ", text).strip()


def compute_consistency_score(ad_text: str, lp_text: str) -> float:
    """Compute text overlap between ad copy and LP hero.

    Uses token-level Jaccard similarity on cleaned Japanese text.
    Returns 0.0 to 1.0 score.
    """
    ad_tokens = _tokenize_japanese(ad_text)
    lp_tokens = _tokenize_japanese(lp_text)

    if not ad_tokens or not lp_tokens:
        return 0.0

    intersection = ad_tokens & lp_tokens
    union = ad_tokens | lp_tokens

    if not union:
        return 0.0

    return len(intersection) / len(union)


def _get_ad_text(ad: Ad, cards: list[AdCard]) -> str:
    """Build ad-side text from title, description, and card text."""
    parts: list[str] = []
    for text in (ad.title, ad.description):
        val = _clean_text(text)
        if val:
            parts.append(val)
    for card in cards:
        for text in (card.body_text, card.ocr_text, card.link_title):
            val = _clean_text(text)
            if val:
                parts.append(val)
    return " ".join(parts)


def _get_lp_text_for_ad(
    ad: Ad,
    cards: list[AdCard],
    lp_snapshots_by_card: dict[int, list[LPSnapshot]],
    landing_pages_by_ad: dict[int, LandingPage | None],
) -> str:
    """Get LP text from multiple sources in priority order.

    1. LPSnapshot.dom_text (first 500 chars) if available
    2. LandingPage.hero_headline + primary_cta_text if available
    3. ad_metadata.lp_info.title + description
    """
    # Source 1: LPSnapshot.dom_text from cards
    for card in cards:
        snapshots = lp_snapshots_by_card.get(card.id, [])
        for snap in snapshots:
            if snap.dom_text:
                return _clean_text(snap.dom_text[:500])

    # Source 2: LandingPage linked to ad
    lp = landing_pages_by_ad.get(ad.id)
    if lp:
        parts = []
        if lp.hero_headline:
            parts.append(_clean_text(lp.hero_headline))
        if lp.primary_cta_text:
            parts.append(_clean_text(lp.primary_cta_text))
        if lp.meta_description:
            parts.append(_clean_text(lp.meta_description))
        if parts:
            return " ".join(parts)

    # Source 3: ad_metadata.lp_info
    meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
    lp_info = meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}
    parts = []
    for key in ("title", "description"):
        val = _clean_text(lp_info.get(key))
        if val:
            parts.append(val)
    return " ".join(parts)


def batch_compute_consistency(session: Session, limit: int = 500) -> dict:
    """Compute ad_to_lp_consistency for ads with both ad text and LP text.

    Stores result in ad_metadata["ad_to_lp_consistency"].

    Gets LP text from:
    1. LPSnapshot.dom_text (first 500 chars) if available
    2. LandingPage.hero_headline + primary_cta_text if available
    3. ad_metadata.lp_info.title + description

    Returns {"computed": int, "avg_score": float}
    """
    from sqlalchemy import or_

    # Find ads that don't have consistency score yet
    # We check for ads that have at least some text content
    stmt = (
        select(Ad)
        .where(
            or_(
                Ad.title.isnot(None),
                Ad.description.isnot(None),
            )
        )
        .order_by(Ad.id)
        .limit(limit * 2)  # Fetch extra since some won't have LP text
    )
    ads = session.scalars(stmt).all()

    if not ads:
        return {"computed": 0, "avg_score": 0.0}

    # Filter to ads without existing consistency score
    candidate_ads = []
    for ad in ads:
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        if "ad_to_lp_consistency" not in meta:
            candidate_ads.append(ad)
        if len(candidate_ads) >= limit:
            break

    if not candidate_ads:
        return {"computed": 0, "avg_score": 0.0}

    ad_ids = [ad.id for ad in candidate_ads]

    # Batch-load cards
    card_stmt = select(AdCard).where(AdCard.ad_id.in_(ad_ids))
    cards_by_ad: dict[int, list[AdCard]] = {}
    card_ids: list[int] = []
    for card in session.scalars(card_stmt).all():
        cards_by_ad.setdefault(card.ad_id, []).append(card)
        card_ids.append(card.id)

    # Batch-load LP snapshots for cards
    lp_snapshots_by_card: dict[int, list[LPSnapshot]] = {}
    if card_ids:
        snap_stmt = select(LPSnapshot).where(LPSnapshot.card_id.in_(card_ids))
        for snap in session.scalars(snap_stmt).all():
            lp_snapshots_by_card.setdefault(snap.card_id, []).append(snap)

    # Batch-load landing pages linked to ads
    lp_stmt = select(LandingPage).where(LandingPage.ad_id.in_(ad_ids))
    landing_pages_by_ad: dict[int, LandingPage | None] = {}
    for lp in session.scalars(lp_stmt).all():
        if lp.ad_id is not None:
            landing_pages_by_ad[lp.ad_id] = lp

    computed = 0
    total_score = 0.0

    for ad in candidate_ads:
        cards = cards_by_ad.get(ad.id, [])
        ad_text = _get_ad_text(ad, cards)
        lp_text = _get_lp_text_for_ad(ad, cards, lp_snapshots_by_card, landing_pages_by_ad)

        if not ad_text or not lp_text:
            continue

        score = compute_consistency_score(ad_text, lp_text)

        # Store in ad_metadata
        meta = dict(ad.ad_metadata) if isinstance(ad.ad_metadata, dict) else {}
        meta["ad_to_lp_consistency"] = round(score, 4)
        ad.ad_metadata = meta

        total_score += score
        computed += 1

    session.flush()

    avg_score = round(total_score / computed, 4) if computed > 0 else 0.0
    logger.info("Computed ad-to-LP consistency for %d ads (avg=%.4f).", computed, avg_score)
    return {"computed": computed, "avg_score": avg_score}
