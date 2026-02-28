#!/usr/bin/env python3
"""Score landing pages for conversion optimization.

For each ad with lp_data in ad_metadata, computes an LP score (0-100) based
on load speed, CTA presence, form, testimonials, video, price, urgency,
social proof, and mobile responsiveness.

Stores result in ad_metadata["lp_score"].

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/score_landing_pages.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.landing_page import LandingPage


# ── Scoring Functions ────────────────────────────────────────────────────


def compute_lp_score(lp_data: dict) -> dict:
    """Compute an LP score (0-100) and component breakdown from lp_data.

    Scoring rubric:
      - Load speed: < 3s = 20pts, 3-5s = 10pts, > 5s = 0pts
      - Has CTA button: +15pts
      - Has form: +10pts
      - Has testimonials: +10pts
      - Has video: +10pts
      - Has price/offer: +10pts
      - Has countdown/urgency: +10pts
      - Has social proof: +10pts
      - Mobile responsive (page_size < 5MB): +5pts
    """
    breakdown = {}
    total_score = 0

    # 1. Load speed
    load_time = lp_data.get("load_time_seconds") or lp_data.get("load_time")
    if load_time is not None:
        try:
            lt = float(load_time)
            if lt < 3.0:
                pts = 20
            elif lt <= 5.0:
                pts = 10
            else:
                pts = 0
        except (ValueError, TypeError):
            pts = 10  # Default: medium if unparseable
    else:
        pts = 10  # Default: assume medium speed
    breakdown["load_speed"] = pts
    total_score += pts

    # 2. Has CTA button
    has_cta = bool(
        lp_data.get("has_cta")
        or lp_data.get("cta_count", 0)
        or lp_data.get("primary_cta_text")
        or lp_data.get("cta_text")
    )
    pts = 15 if has_cta else 0
    breakdown["has_cta"] = pts
    total_score += pts

    # 3. Has form
    has_form = bool(
        lp_data.get("has_form")
        or (lp_data.get("form_count") or 0) > 0
    )
    pts = 10 if has_form else 0
    breakdown["has_form"] = pts
    total_score += pts

    # 4. Has testimonials
    has_testimonials = bool(
        lp_data.get("has_testimonials")
        or lp_data.get("has_testimonial")
        or (lp_data.get("testimonial_count") or 0) > 0
    )
    pts = 10 if has_testimonials else 0
    breakdown["has_testimonials"] = pts
    total_score += pts

    # 5. Has video
    has_video = bool(
        lp_data.get("has_video")
        or (lp_data.get("video_embed_count") or 0) > 0
    )
    pts = 10 if has_video else 0
    breakdown["has_video"] = pts
    total_score += pts

    # 6. Has price/offer
    has_price = bool(
        lp_data.get("has_price")
        or lp_data.get("has_pricing")
        or lp_data.get("price_text")
        or lp_data.get("discount_text")
        or lp_data.get("has_offer")
    )
    pts = 10 if has_price else 0
    breakdown["has_price_offer"] = pts
    total_score += pts

    # 7. Has countdown/urgency
    has_urgency = bool(
        lp_data.get("has_countdown")
        or lp_data.get("has_urgency")
        or lp_data.get("has_timer")
    )
    pts = 10 if has_urgency else 0
    breakdown["has_urgency"] = pts
    total_score += pts

    # 8. Has social proof
    has_social_proof = bool(
        lp_data.get("has_social_proof")
        or lp_data.get("has_reviews")
        or lp_data.get("has_ratings")
        or lp_data.get("has_trust_badges")
    )
    pts = 10 if has_social_proof else 0
    breakdown["has_social_proof"] = pts
    total_score += pts

    # 9. Mobile responsive (page_size < 5MB)
    page_size = lp_data.get("page_size_bytes") or lp_data.get("page_size")
    if page_size is not None:
        try:
            size_bytes = float(page_size)
            is_responsive = size_bytes < 5 * 1024 * 1024
        except (ValueError, TypeError):
            is_responsive = True  # Default: assume responsive
    else:
        is_responsive = True  # No data -> assume OK
    pts = 5 if is_responsive else 0
    breakdown["mobile_responsive"] = pts
    total_score += pts

    return {
        "score": min(total_score, 100),
        "breakdown": breakdown,
        "max_possible": 100,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_lp_score_from_model(lp: LandingPage) -> dict:
    """Compute LP score from the LandingPage model fields."""
    lp_data = {
        "has_cta": bool(lp.cta_count and lp.cta_count > 0) or bool(lp.primary_cta_text),
        "cta_count": lp.cta_count or 0,
        "primary_cta_text": lp.primary_cta_text,
        "has_form": bool(lp.form_count and lp.form_count > 0),
        "form_count": lp.form_count or 0,
        "has_testimonial": bool(lp.testimonial_count and lp.testimonial_count > 0),
        "testimonial_count": lp.testimonial_count or 0,
        "has_video": bool(lp.video_embed_count and lp.video_embed_count > 0),
        "video_embed_count": lp.video_embed_count or 0,
        "has_pricing": lp.has_pricing,
        "price_text": lp.price_text,
        "discount_text": lp.discount_text,
    }

    # Add metadata fields if available
    lp_meta = lp.lp_metadata or {}
    for key in ["load_time_seconds", "has_countdown", "has_urgency",
                "has_social_proof", "has_reviews", "page_size_bytes"]:
        if key in lp_meta:
            lp_data[key] = lp_meta[key]

    return compute_lp_score(lp_data)


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Landing Page Scoring Script")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Score ads with lp_data in ad_metadata
        scored_from_meta = 0
        scored_from_model = 0
        score_sum = 0.0
        score_distribution: dict[str, int] = {
            "excellent (80-100)": 0,
            "good (60-79)": 0,
            "average (40-59)": 0,
            "poor (20-39)": 0,
            "very_poor (0-19)": 0,
        }

        # First: score from ad_metadata lp_data
        for ad in ads:
            meta = ad.ad_metadata or {}
            lp_data = meta.get("lp_data")
            if not lp_data or not isinstance(lp_data, dict):
                continue

            result = compute_lp_score(lp_data)
            score = result["score"]

            # Store in ad_metadata
            meta_new = dict(meta)
            meta_new["lp_score"] = result
            ad.ad_metadata = meta_new
            flag_modified(ad, "ad_metadata")
            scored_from_meta += 1
            score_sum += score
            _classify_score(score, score_distribution)

        # Second: score from LandingPage model (if ads have linked LPs)
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
                if "lp_score" in meta:
                    continue  # Already scored from lp_data

                lp = lp_by_ad_id.get(ad.id)
                if not lp:
                    continue

                result = compute_lp_score_from_model(lp)
                score = result["score"]

                meta_new = dict(meta)
                meta_new["lp_score"] = result
                ad.ad_metadata = meta_new
                flag_modified(ad, "ad_metadata")
                scored_from_model += 1
                score_sum += score
                _classify_score(score, score_distribution)

        except Exception as e:
            print(f"  Note: Could not query LandingPage table: {e}")

        session.commit()

        total_scored = scored_from_meta + scored_from_model
        avg_score = score_sum / total_scored if total_scored > 0 else 0

        print(f"\n--- Scoring Results ---")
        print(f"  Scored from ad_metadata lp_data: {scored_from_meta}")
        print(f"  Scored from LandingPage model:   {scored_from_model}")
        print(f"  Total scored:                    {total_scored}/{total}")
        print(f"  Not scored (no LP data):         {total - total_scored}")

        if total_scored > 0:
            print(f"\n--- Score Statistics ---")
            print(f"  Average LP score: {avg_score:.1f}")
            print(f"\n--- Score Distribution ---")
            for label, count in score_distribution.items():
                pct = count / total_scored * 100
                bar = "#" * int(pct / 2)
                print(f"  {label:<20s} {count:>4d} ({pct:>5.1f}%) {bar}")

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


def _classify_score(score: float, distribution: dict[str, int]) -> None:
    """Classify a score into the distribution buckets."""
    if score >= 80:
        distribution["excellent (80-100)"] += 1
    elif score >= 60:
        distribution["good (60-79)"] += 1
    elif score >= 40:
        distribution["average (40-59)"] += 1
    elif score >= 20:
        distribution["poor (20-39)"] += 1
    else:
        distribution["very_poor (0-19)"] += 1


if __name__ == "__main__":
    main()
