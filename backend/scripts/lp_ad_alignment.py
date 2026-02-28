#!/usr/bin/env python3
"""LP-Ad Alignment Analysis.

Compares ad creative with its landing page to assess message consistency:
  - Headline matching (ad title vs LP headline)
  - Offer matching (ad offer vs LP offer)
  - CTA consistency (ad CTA vs LP CTA)
  - Overall alignment score (0-100)

Stores result in ad_metadata["lp_alignment"].

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/lp_ad_alignment.py
"""

import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.landing_page import LandingPage


# ── Text Similarity Helpers ─────────────────────────────────────────────


def _tokenize(text: str) -> set[str]:
    """Simple tokenizer: split into words and character n-grams for Japanese."""
    if not text:
        return set()
    text_lower = text.lower().strip()
    # ASCII words
    ascii_words = set(re.findall(r'[a-zA-Z]{2,}', text_lower))
    # Japanese character bigrams (for overlap detection)
    jp_chars = re.findall(r'[\u3000-\u9fff\uff00-\uffef]', text_lower)
    jp_bigrams = set()
    for i in range(len(jp_chars) - 1):
        jp_bigrams.add(jp_chars[i] + jp_chars[i + 1])
    # Number patterns
    numbers = set(re.findall(r'\d+[%\u5186\u4e07]?', text_lower))
    return ascii_words | jp_bigrams | numbers


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def _substring_overlap(text_a: str, text_b: str, min_len: int = 4) -> float:
    """Compute overlap ratio based on shared substrings."""
    if not text_a or not text_b:
        return 0.0
    a = text_a.lower()
    b = text_b.lower()

    # Check for direct substring containment
    if a in b or b in a:
        return 1.0

    # Count shared substrings of length >= min_len
    shorter = a if len(a) <= len(b) else b
    longer = b if len(a) <= len(b) else a

    matches = 0
    total = 0
    for i in range(0, len(shorter) - min_len + 1, min_len):
        substr = shorter[i:i + min_len]
        total += 1
        if substr in longer:
            matches += 1

    return matches / total if total > 0 else 0.0


# ── Alignment Scoring Functions ─────────────────────────────────────────


def _score_headline_alignment(
    ad_title: str | None,
    lp_headline: str | None,
    lp_title: str | None,
) -> tuple[int, str]:
    """Score headline alignment between ad and LP (0-30 points).

    Returns (score, detail_string).
    """
    if not ad_title:
        return 0, "no ad title"

    # Use LP headline or LP title
    lp_text = lp_headline or lp_title or ""
    if not lp_text:
        return 15, "no LP headline data"  # Neutral score if no LP data

    # Token-based similarity
    ad_tokens = _tokenize(ad_title)
    lp_tokens = _tokenize(lp_text)
    jaccard = _jaccard_similarity(ad_tokens, lp_tokens)

    # Substring overlap
    overlap = _substring_overlap(ad_title, lp_text)

    # Combined score (weight: 60% jaccard, 40% overlap)
    similarity = jaccard * 0.6 + overlap * 0.4

    if similarity >= 0.5:
        return 30, f"strong headline match ({similarity:.0%})"
    elif similarity >= 0.25:
        return 20, f"partial headline match ({similarity:.0%})"
    elif similarity >= 0.10:
        return 10, f"weak headline match ({similarity:.0%})"
    else:
        return 0, f"headline mismatch ({similarity:.0%})"


def _score_offer_alignment(
    ad_meta: dict,
    lp_data: dict,
) -> tuple[int, str]:
    """Score offer alignment between ad and LP (0-25 points)."""
    ca = ad_meta.get("creative_analysis", {})
    ad_offer = ca.get("offer_type", "none")
    ad_offer_detail = ca.get("offer_detail")

    lp_has_price = bool(
        lp_data.get("has_pricing")
        or lp_data.get("has_price")
        or lp_data.get("price_text")
        or lp_data.get("discount_text")
    )
    lp_has_offer = bool(
        lp_data.get("has_offer")
        or lp_data.get("has_discount")
        or lp_data.get("discount_text")
    )

    if ad_offer == "none":
        # No offer in ad -> no alignment needed
        return 15, "no offer in ad (neutral)"

    if ad_offer in ("discount", "free", "trial", "limited_time"):
        # Ad has a specific offer -> LP should reflect it
        if lp_has_price or lp_has_offer:
            # Check if offer details match
            lp_price_text = (lp_data.get("price_text") or "") + " " + (lp_data.get("discount_text") or "")
            if ad_offer_detail and ad_offer_detail.lower() in lp_price_text.lower():
                return 25, f"exact offer match: {ad_offer}"
            else:
                return 20, f"LP has pricing but different detail: {ad_offer}"
        else:
            return 5, f"ad has '{ad_offer}' offer but LP lacks pricing"
    else:
        if lp_has_price:
            return 20, f"LP has pricing, ad offer={ad_offer}"
        return 15, f"ad offer={ad_offer}, LP neutral"


def _score_cta_alignment(
    ad_meta: dict,
    lp_data: dict,
) -> tuple[int, str]:
    """Score CTA alignment between ad and LP (0-25 points)."""
    ca = ad_meta.get("creative_analysis", {})
    ad_cta = ca.get("cta_type", "none")

    lp_cta_text = (
        lp_data.get("primary_cta_text")
        or lp_data.get("cta_text")
        or ""
    )
    lp_has_cta = bool(
        lp_data.get("has_cta")
        or (lp_data.get("cta_count") or 0) > 0
        or lp_cta_text
    )

    if not lp_has_cta:
        if ad_cta == "none":
            return 15, "no CTA in either (neutral)"
        return 5, f"ad has '{ad_cta}' CTA but LP has no CTA"

    if ad_cta == "none":
        return 15, "LP has CTA, ad CTA not explicit (neutral)"

    # Check CTA type match
    cta_keywords = {
        "line_add": ["LINE", "line", "friend", "add"],
        "purchase": ["purchase", "buy", "order", "cart"],
        "signup": ["signup", "register", "apply", "join"],
        "free_trial": ["free", "trial", "try"],
        "consultation": ["consult", "counsel", "estimate"],
        "download": ["download", "install", "DL"],
        "learn_more": ["detail", "check", "more", "see"],
    }

    if ad_cta in cta_keywords and lp_cta_text:
        lp_cta_lower = lp_cta_text.lower()
        matched = any(kw.lower() in lp_cta_lower for kw in cta_keywords[ad_cta])
        if matched:
            return 25, f"CTA match: ad={ad_cta}, LP CTA matches"
        else:
            return 15, f"CTA mismatch: ad={ad_cta}, LP CTA differs"

    return 15, f"ad_cta={ad_cta}, LP has CTA"


def _score_content_consistency(
    ad: Ad,
    lp_data: dict,
) -> tuple[int, str]:
    """Score overall content consistency (0-20 points)."""
    ad_text = " ".join(filter(None, [ad.title, ad.description]))
    lp_text = " ".join(filter(None, [
        lp_data.get("hero_headline", ""),
        lp_data.get("hero_subheadline", ""),
        lp_data.get("meta_description", ""),
    ]))

    if not ad_text or not lp_text:
        return 10, "insufficient text data (neutral)"

    ad_tokens = _tokenize(ad_text)
    lp_tokens = _tokenize(lp_text)
    similarity = _jaccard_similarity(ad_tokens, lp_tokens)

    if similarity >= 0.3:
        return 20, f"strong content consistency ({similarity:.0%})"
    elif similarity >= 0.15:
        return 15, f"moderate content consistency ({similarity:.0%})"
    elif similarity >= 0.05:
        return 10, f"weak content consistency ({similarity:.0%})"
    else:
        return 5, f"low content consistency ({similarity:.0%})"


def compute_alignment(ad: Ad, lp_data: dict) -> dict:
    """Compute full alignment analysis for an ad + LP pair.

    Returns alignment dict with score (0-100) and component breakdown.
    """
    meta = ad.ad_metadata or {}

    # Component scores (total max = 100)
    headline_score, headline_detail = _score_headline_alignment(
        ad.title,
        lp_data.get("hero_headline"),
        lp_data.get("title"),
    )
    offer_score, offer_detail = _score_offer_alignment(meta, lp_data)
    cta_score, cta_detail = _score_cta_alignment(meta, lp_data)
    content_score, content_detail = _score_content_consistency(ad, lp_data)

    total_score = headline_score + offer_score + cta_score + content_score

    # Grade
    if total_score >= 80:
        grade = "A"
    elif total_score >= 60:
        grade = "B"
    elif total_score >= 40:
        grade = "C"
    elif total_score >= 20:
        grade = "D"
    else:
        grade = "F"

    return {
        "alignment_score": min(total_score, 100),
        "grade": grade,
        "breakdown": {
            "headline": {"score": headline_score, "max": 30, "detail": headline_detail},
            "offer": {"score": offer_score, "max": 25, "detail": offer_detail},
            "cta": {"score": cta_score, "max": 25, "detail": cta_detail},
            "content": {"score": content_score, "max": 20, "detail": content_detail},
        },
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("LP-Ad Alignment Analysis Script")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        scored = 0
        score_sum = 0.0
        grade_counts: dict[str, int] = {}

        # Score from ad_metadata lp_data
        for ad in ads:
            meta = ad.ad_metadata or {}
            lp_data = meta.get("lp_data")
            if not lp_data or not isinstance(lp_data, dict):
                continue

            alignment = compute_alignment(ad, lp_data)

            # Store result
            meta_new = dict(meta)
            meta_new["lp_alignment"] = alignment
            ad.ad_metadata = meta_new
            flag_modified(ad, "ad_metadata")

            scored += 1
            score_sum += alignment["alignment_score"]
            grade = alignment["grade"]
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

        # Also score from LandingPage model
        try:
            landing_pages = session.query(LandingPage).filter(
                LandingPage.ad_id.isnot(None)
            ).all()

            lp_by_ad_id: dict[int, LandingPage] = {}
            for lp in landing_pages:
                if lp.ad_id:
                    lp_by_ad_id[lp.ad_id] = lp

            for ad in ads:
                meta = ad.ad_metadata or {}
                if "lp_alignment" in meta:
                    continue  # Already scored

                lp = lp_by_ad_id.get(ad.id)
                if not lp:
                    continue

                # Build lp_data from model fields
                lp_data_from_model = {
                    "title": lp.title,
                    "hero_headline": lp.hero_headline,
                    "hero_subheadline": lp.hero_subheadline,
                    "meta_description": lp.meta_description,
                    "primary_cta_text": lp.primary_cta_text,
                    "has_cta": bool(lp.cta_count and lp.cta_count > 0),
                    "cta_count": lp.cta_count or 0,
                    "has_pricing": lp.has_pricing,
                    "price_text": lp.price_text,
                    "discount_text": lp.discount_text,
                    "has_form": bool(lp.form_count and lp.form_count > 0),
                    "form_count": lp.form_count or 0,
                    "has_testimonial": bool(lp.testimonial_count and lp.testimonial_count > 0),
                }

                alignment = compute_alignment(ad, lp_data_from_model)

                meta_new = dict(meta)
                meta_new["lp_alignment"] = alignment
                ad.ad_metadata = meta_new
                flag_modified(ad, "ad_metadata")

                scored += 1
                score_sum += alignment["alignment_score"]
                grade = alignment["grade"]
                grade_counts[grade] = grade_counts.get(grade, 0) + 1

        except Exception as e:
            print(f"  Note: Could not query LandingPage table: {e}")

        session.commit()

        avg_score = score_sum / scored if scored > 0 else 0

        print(f"\n--- Alignment Results ---")
        print(f"  Ads scored:     {scored}/{total}")
        print(f"  Not scored:     {total - scored} (no LP data)")

        if scored > 0:
            print(f"  Average score:  {avg_score:.1f}")
            print(f"\n--- Grade Distribution ---")
            for grade in ["A", "B", "C", "D", "F"]:
                count = grade_counts.get(grade, 0)
                pct = count / scored * 100
                bar = "#" * int(pct / 2)
                print(f"  {grade}: {count:>4d} ({pct:>5.1f}%) {bar}")

        # Show samples
        print(f"\n--- Sample Alignments (first 5 scored) ---")
        sample_count = 0
        for ad in ads:
            if sample_count >= 5:
                break
            alignment = (ad.ad_metadata or {}).get("lp_alignment")
            if not alignment:
                continue
            title_safe = (ad.title or "")[:40].encode("ascii", "replace").decode("ascii")
            print(f"  ID={ad.id} title={title_safe!r}")
            print(f"    alignment_score={alignment['alignment_score']}  grade={alignment['grade']}")
            bd = alignment.get("breakdown", {})
            for comp in ["headline", "offer", "cta", "content"]:
                info = bd.get(comp, {})
                print(f"      {comp}: {info.get('score', '?')}/{info.get('max', '?')} - {info.get('detail', '?')}")
            sample_count += 1

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
