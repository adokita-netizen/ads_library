#!/usr/bin/env python3
"""NLP analysis of ad text using AWS Comprehend.

For each ad's title + description (+ transcript if available):
  - detect_sentiment()         -> positive/negative/neutral/mixed
  - detect_key_phrases()       -> important phrases
  - detect_entities()          -> brands, products, quantities
  - detect_dominant_language()  -> confirm language

Results stored in ad_metadata["nlp"].

Usage:
    python -m scripts.comprehend_analysis                  # all unprocessed
    python -m scripts.comprehend_analysis --ad-id 123      # specific ad
    python -m scripts.comprehend_analysis --limit 100      # limit batch
    python -m scripts.comprehend_analysis --cost-estimate   # cost preview
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("APP_ENV", "development")

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# Comprehend pricing (per 100 chars, min 300 chars = 3 units)
PRICE_PER_UNIT = 0.0001  # $0.0001 per unit (100 chars)
ANALYSES_PER_AD = 4  # sentiment + key_phrases + entities + language


def _get_comprehend_client():
    """Get boto3 Comprehend client."""
    import boto3
    from app.core.config import get_settings
    settings = get_settings()
    return boto3.client("comprehend", region_name=settings.aws_region)


def _build_text(ad, meta: dict) -> str:
    """Build combined text for NLP analysis."""
    parts = []
    if ad.title:
        parts.append(ad.title)
    if ad.description:
        parts.append(ad.description)
    # Include transcript if available
    transcript = meta.get("transcript", {})
    if transcript.get("full_text"):
        parts.append(transcript["full_text"])
    return "\n".join(parts)


def _analyze_text(client, text: str) -> dict:
    """Run all Comprehend analyses on text."""
    # Comprehend requires min 1 char, but meaningful analysis needs more
    if len(text.strip()) < 10:
        return {"error": "text_too_short"}

    # Truncate to 5000 chars (Comprehend limit for single-doc APIs)
    text = text[:5000]

    result = {}

    # 1. Detect dominant language
    lang_code = "ja"
    try:
        resp = client.detect_dominant_language(Text=text)
        languages = resp.get("Languages", [])
        if languages:
            lang_code = languages[0]["LanguageCode"]
            result["language"] = lang_code
            result["language_confidence"] = round(languages[0]["Score"], 3)
    except Exception as e:
        result["language_error"] = str(e)

    # 2. Detect sentiment
    try:
        resp = client.detect_sentiment(Text=text, LanguageCode=lang_code)
        result["sentiment"] = resp.get("Sentiment", "UNKNOWN")
        scores = resp.get("SentimentScore", {})
        result["sentiment_score"] = {
            k.lower(): round(v, 3) for k, v in scores.items()
        }
    except Exception as e:
        result["sentiment_error"] = str(e)

    # 3. Detect key phrases
    try:
        resp = client.detect_key_phrases(Text=text, LanguageCode=lang_code)
        phrases = resp.get("KeyPhrases", [])
        result["key_phrases"] = [
            p["Text"] for p in phrases
            if p["Score"] > 0.7
        ][:20]  # top 20
    except Exception as e:
        result["key_phrases_error"] = str(e)

    # 4. Detect entities
    try:
        resp = client.detect_entities(Text=text, LanguageCode=lang_code)
        entities = resp.get("Entities", [])
        result["entities"] = [
            {"text": e["Text"], "type": e["Type"]}
            for e in entities
            if e["Score"] > 0.7
        ][:20]
    except Exception as e:
        result["entities_error"] = str(e)

    return result


def analyze_ads(ad_id: int | None = None, limit: int = 0, cost_only: bool = False) -> dict:
    """Run NLP analysis on ads."""
    session = SyncSessionLocal()
    try:
        if ad_id:
            ads = [session.query(Ad).filter(Ad.id == ad_id).first()]
            ads = [a for a in ads if a]
        else:
            all_ads = session.query(Ad).all()
            ads = []
            for ad in all_ads:
                meta = ad.ad_metadata or {}
                if "nlp" in meta:
                    continue
                text = _build_text(ad, meta)
                if len(text.strip()) >= 10:
                    ads.append(ad)

        if limit > 0:
            ads = ads[:limit]

        # Cost estimate
        avg_chars = 500  # average text length
        units_per_ad = max(3, avg_chars // 100)  # min 3 units
        est_cost = len(ads) * units_per_ad * PRICE_PER_UNIT * ANALYSES_PER_AD
        print(f"Ads to analyze: {len(ads)}")
        print(f"Estimated cost: ${est_cost:.2f}")

        if cost_only or len(ads) == 0:
            return {"total": len(ads), "estimated_cost": est_cost}

        client = _get_comprehend_client()
        processed = 0
        errors = 0

        for i, ad in enumerate(ads, 1):
            try:
                meta = ad.ad_metadata or {}
                text = _build_text(ad, meta)

                analysis = _analyze_text(client, text)

                if "error" in analysis:
                    if i % 20 == 0:
                        print(f"  [{i}/{len(ads)}] Ad {ad.id}: {analysis['error']}")
                    continue

                meta["nlp"] = analysis
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                session.commit()
                processed += 1

                if i % 20 == 0 or i == len(ads):
                    sentiment = analysis.get("sentiment", "?")
                    phrases = len(analysis.get("key_phrases", []))
                    entities = len(analysis.get("entities", []))
                    print(f"  [{i}/{len(ads)}] Ad {ad.id}: {sentiment}, "
                          f"{phrases} phrases, {entities} entities")
                    sys.stdout.flush()

                # Rate limit: Comprehend allows 25 TPS
                if i % 20 == 0:
                    time.sleep(1)

            except Exception as e:
                print(f"  [{i}/{len(ads)}] Ad {ad.id}: ERROR - {e}")
                session.rollback()
                errors += 1
                time.sleep(1)

        summary = {"processed": processed, "errors": errors, "total": len(ads)}
        print(f"\n=== Summary ===")
        print(f"  Processed: {processed}")
        print(f"  Errors:    {errors}")
        return summary

    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="NLP analysis with AWS Comprehend")
    parser.add_argument("--ad-id", type=int, help="Analyze specific ad")
    parser.add_argument("--limit", type=int, default=0, help="Max ads to process")
    parser.add_argument("--cost-estimate", action="store_true", help="Show cost estimate only")
    args = parser.parse_args()

    print("=== AWS Comprehend NLP Analysis ===")
    sys.stdout.flush()
    analyze_ads(ad_id=args.ad_id, limit=args.limit, cost_only=args.cost_estimate)


if __name__ == "__main__":
    main()
