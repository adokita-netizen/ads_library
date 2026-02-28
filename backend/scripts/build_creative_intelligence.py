#!/usr/bin/env python3
"""Merge all analysis data into a unified creative intelligence object.

Combines:
  - Rekognition image analysis (labels, text, faces)
  - Rekognition video analysis (labels, text, face moments)
  - AWS Transcribe transcript
  - AWS Comprehend NLP (sentiment, key phrases, entities)
  - Existing creative_analysis (hook type, CTA, etc.)

Result stored in ad_metadata["creative_intelligence"].

Usage:
    python -m scripts.build_creative_intelligence             # all ads with any analysis
    python -m scripts.build_creative_intelligence --ad-id 123  # specific ad
    python -m scripts.build_creative_intelligence --force       # rebuild all
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("APP_ENV", "development")

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad


def _compute_score(ci: dict) -> int:
    """Compute overall creative intelligence score (0-100)."""
    score = 0

    # Visual elements (up to 25 points)
    visual = ci.get("visual_elements", [])
    if visual:
        score += min(len(visual), 10) * 2  # up to 20 for variety
        # Bonus for having people/faces
        if any(v.get("name") in ("Person", "Human", "Face") for v in visual):
            score += 5

    # Text overlay (up to 15 points)
    text = ci.get("text_overlay", [])
    if text:
        score += min(len(text), 5) * 3  # up to 15 for text presence

    # Audio/transcript (up to 15 points)
    if ci.get("audio_script"):
        score += 10
        if len(ci["audio_script"]) > 50:
            score += 5

    # Sentiment (up to 10 points)
    sentiment = ci.get("sentiment", "")
    if sentiment == "POSITIVE":
        score += 10
    elif sentiment == "MIXED":
        score += 7
    elif sentiment == "NEUTRAL":
        score += 5

    # Key phrases (up to 10 points)
    phrases = ci.get("key_phrases", [])
    score += min(len(phrases), 5) * 2

    # Hook type (up to 10 points)
    if ci.get("hook_type"):
        score += 10

    # Emotional engagement (up to 15 points)
    faces = ci.get("face_emotions", [])
    if faces:
        score += 5
        # Bonus for positive emotions
        for face in faces:
            emotions = face if isinstance(face, dict) else {}
            if emotions.get("happy", 0) > 70 or emotions.get("surprised", 0) > 70:
                score += 5
                break

    return min(score, 100)


def _identify_strengths_weaknesses(ci: dict) -> tuple[list, list]:
    """Identify creative strengths and weaknesses."""
    strengths = []
    weaknesses = []

    # Visual
    visual = ci.get("visual_elements", [])
    if len(visual) >= 5:
        strengths.append("rich visual content")
    elif not visual:
        weaknesses.append("no visual elements detected")

    has_person = any(v.get("name") in ("Person", "Human", "Face") for v in visual)
    if has_person:
        strengths.append("human presence")
    else:
        weaknesses.append("no human presence")

    # Text
    text = ci.get("text_overlay", [])
    if text:
        strengths.append("text overlay present")
        # Check for CTA-like text
        cta_words = ["free", "now", "limited", "click", "buy", "try", "get",
                      "today", "offer", "discount", "sale"]
        text_lower = " ".join(text).lower()
        if any(w in text_lower for w in cta_words):
            strengths.append("strong CTA text")
    else:
        weaknesses.append("no text overlay")

    # Sentiment
    sentiment = ci.get("sentiment", "")
    if sentiment == "POSITIVE":
        strengths.append("positive messaging")
    elif sentiment == "NEGATIVE":
        weaknesses.append("negative messaging tone")

    # Audio
    if ci.get("audio_script"):
        strengths.append("audio narration")
    elif ci.get("is_video"):
        weaknesses.append("video without narration")

    # Hook
    hook = ci.get("hook_type", "")
    if hook:
        strengths.append(f"{hook} hook")

    # Emotional
    if ci.get("face_emotions"):
        strengths.append("emotional engagement")

    return strengths[:6], weaknesses[:6]


def build_intelligence(ad_id: int | None = None, force: bool = False) -> dict:
    """Build creative intelligence for ads."""
    session = SyncSessionLocal()
    try:
        if ad_id:
            ads = [session.query(Ad).filter(Ad.id == ad_id).first()]
            ads = [a for a in ads if a]
        else:
            ads = session.query(Ad).all()

        processed = 0
        skipped = 0

        for i, ad in enumerate(ads, 1):
            meta = ad.ad_metadata or {}

            # Check if already built and not forcing rebuild
            if "creative_intelligence" in meta and not force:
                skipped += 1
                continue

            # Check if there's any analysis data to merge
            has_rek = "rekognition" in meta
            has_rek_video = "rekognition_video" in meta
            has_transcript = "transcript" in meta
            has_nlp = "nlp" in meta
            has_ca = "creative_analysis" in meta

            if not any([has_rek, has_rek_video, has_transcript, has_nlp, has_ca]):
                skipped += 1
                continue

            # Build unified intelligence object
            ci = {}

            # Visual elements (from Rekognition)
            rek = meta.get("rekognition", {})
            ci["visual_elements"] = rek.get("labels", [])
            ci["text_overlay"] = rek.get("text_detections", [])
            ci["face_emotions"] = [
                f.get("emotions", {}) for f in rek.get("faces", [])
            ]
            ci["moderation_flags"] = rek.get("moderation", [])

            # Video-specific (from Rekognition Video)
            rek_video = meta.get("rekognition_video", {})
            if rek_video:
                ci["is_video"] = True
                ci["video_labels"] = rek_video.get("labels", [])
                ci["video_text_timeline"] = rek_video.get("text_detections", [])
                ci["video_face_moments"] = rek_video.get("face_moments", [])

            # Audio script (from Transcribe)
            transcript = meta.get("transcript", {})
            ci["audio_script"] = transcript.get("full_text", "")
            ci["audio_segments"] = transcript.get("segments", [])
            ci["audio_confidence"] = transcript.get("confidence", 0)

            # NLP analysis (from Comprehend)
            nlp = meta.get("nlp", {})
            ci["sentiment"] = nlp.get("sentiment", "")
            ci["sentiment_score"] = nlp.get("sentiment_score", {})
            ci["key_phrases"] = nlp.get("key_phrases", [])
            ci["entities"] = nlp.get("entities", [])

            # Creative analysis (existing)
            ca = meta.get("creative_analysis", {})
            ci["hook_type"] = ca.get("hook_type", "")
            ci["cta_text"] = ca.get("cta_text", "")
            ci["creative_style"] = ca.get("creative_style", "")

            # Compute overall score
            ci["overall_score"] = _compute_score(ci)

            # Identify strengths and weaknesses
            strengths, weaknesses = _identify_strengths_weaknesses(ci)
            ci["strengths"] = strengths
            ci["weaknesses"] = weaknesses

            # Store
            meta["creative_intelligence"] = ci
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            session.commit()
            processed += 1

            if i % 50 == 0 or (ad_id and i == 1):
                print(f"  [{i}/{len(ads)}] Ad {ad.id}: score={ci['overall_score']}, "
                      f"strengths={len(strengths)}, weaknesses={len(weaknesses)}")
                sys.stdout.flush()

        print(f"\n=== Summary ===")
        print(f"  Built:   {processed}")
        print(f"  Skipped: {skipped}")
        return {"processed": processed, "skipped": skipped}

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Build creative intelligence objects")
    parser.add_argument("--ad-id", type=int, help="Build for specific ad")
    parser.add_argument("--force", action="store_true", help="Rebuild all (overwrite existing)")
    args = parser.parse_args()

    print("=== Build Creative Intelligence ===")
    sys.stdout.flush()
    build_intelligence(ad_id=args.ad_id, force=args.force)


if __name__ == "__main__":
    main()
