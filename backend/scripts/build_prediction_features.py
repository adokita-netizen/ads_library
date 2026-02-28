#!/usr/bin/env python3
"""Build prediction feature vectors for all ads.

For each ad, compiles a feature vector from creative_analysis, text features,
LP data, and Rekognition data. Stores in ad_metadata["prediction_features"]
and exports to backend/exports/feature_matrix.csv.

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/build_prediction_features.py
"""

import csv
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Constants ────────────────────────────────────────────────────────────

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)

# Categories for one-hot encoding
HOOK_TYPES = [
    "urgency", "social_proof", "pain_point", "statistic",
    "benefit", "question", "curiosity", "none",
]
CTA_TYPES = [
    "line_add", "purchase", "signup", "free_trial",
    "consultation", "download", "learn_more", "none",
]
OFFER_TYPES = [
    "discount", "free", "trial", "limited_time",
    "bundle", "comparison", "none",
]
EMOTION_TYPES = [
    "fear", "desire", "trust", "excitement",
    "relief", "curiosity", "neutral",
]

# Power word categories from A11
POWER_WORD_CATEGORIES: dict[str, list[str]] = {
    "urgency": [
        "\u4eca\u3060\u3051", "\u9650\u5b9a", "\u6b8b\u308a\u308f\u305a\u304b",
        "\u6025\u3044\u3067", "\u672c\u65e5\u9650\u308a", "\u671f\u9593\u9650\u5b9a",
        "\u5148\u7740", "\u7de0\u5207", "\u30e9\u30b9\u30c8", "\u304a\u6025\u304e",
        "\u6700\u7d42", "\u3042\u3068\u308f\u305a\u304b",
    ],
    "social_proof": [
        "\u4eba\u6c17", "\u8a71\u984c", "\u58f2\u4e0aNo.1", "\u6e80\u8db3\u5ea6",
        "\u30ec\u30d3\u30e5\u30fc", "\u53e3\u30b3\u30df", "\u30e9\u30f3\u30ad\u30f3\u30b0",
        "\u7d2f\u8a08", "\u7a81\u7834", "\u5b9f\u7e3e", "\u6bbf\u5802\u5165\u308a",
        "\u30d9\u30b9\u30c8\u30bb\u30e9\u30fc", "\u30ea\u30d4\u30fc\u30c8", "\u7b2c1\u4f4d",
    ],
    "benefit": [
        "\u7c21\u5358", "\u305f\u3063\u305f", "\u3060\u3051\u3067",
        "\u9a5a\u304d\u306e", "\u5b9f\u611f", "\u624b\u8efd", "\u304a\u5f97",
        "\u5b89\u5fc3", "\u4fbf\u5229", "\u5feb\u9069", "\u30b9\u30c3\u30ad\u30ea",
        "\u7406\u60f3", "\u6539\u5584", "\u52b9\u679c", "\u7d50\u679c",
    ],
    "fear": [
        "\u5371\u967a", "\u77e5\u3089\u306a\u3044\u3068", "\u640d",
        "\u5f8c\u6094", "\u8001\u5316", "\u653e\u7f6e", "\u624b\u9045\u308c",
        "\u30ea\u30b9\u30af", "\u5931\u6557", "\u4e0d\u5b89", "\u8b66\u544a",
        "\u8981\u6ce8\u610f",
    ],
    "free": [
        "\u7121\u6599", "0\u5186", "\u30bf\u30c0", "\u30d7\u30ec\u30bc\u30f3\u30c8",
        "\u7279\u5178", "\u9001\u6599\u7121\u6599", "\u624b\u6570\u6599\u7121\u6599",
        "\u304a\u8a66\u3057", "\u30c8\u30e9\u30a4\u30a2\u30eb", "\u30b5\u30f3\u30d7\u30eb",
        "\u30e2\u30cb\u30bf\u30fc",
    ],
}


# ── Feature extraction helpers ──────────────────────────────────────────


def _one_hot(value: str, categories: list[str]) -> dict[str, int]:
    """Create one-hot encoding for a value against category list."""
    result = {}
    for cat in categories:
        result[cat] = 1 if value == cat else 0
    return result


def _normalize_text_length(text: str | None, max_len: int = 500) -> float:
    """Normalize text length to 0-1 range."""
    if not text:
        return 0.0
    return min(len(text) / max_len, 1.0)


def _count_power_words(text: str) -> int:
    """Count total power words in text."""
    if not text:
        return 0
    text_lower = text.lower()
    count = 0
    for words in POWER_WORD_CATEGORIES.values():
        for w in words:
            if w.lower() in text_lower:
                count += 1
    return count


def _word_count(text: str | None) -> int:
    """Approximate word count (Japanese: char-based, ASCII: space-separated)."""
    if not text:
        return 0
    # Count ASCII words by spaces + estimate Japanese chars as words
    ascii_words = len(re.findall(r'[a-zA-Z]+', text))
    jp_chars = len(re.findall(r'[\u3000-\u9fff\uff00-\uffef]', text))
    return ascii_words + jp_chars


def build_feature_vector(ad: Ad) -> dict:
    """Build a feature vector for a single ad.

    Returns a flat dict of feature_name -> numeric_value (0/1 or float).
    """
    meta = ad.ad_metadata or {}
    ca = meta.get("creative_analysis", {})
    lp_data = meta.get("lp_data", {})
    rekognition = meta.get("rekognition", {})

    features = {}

    # 1. Creative analysis one-hot features
    hook_type = ca.get("hook_type", "none") or "none"
    for k, v in _one_hot(hook_type, HOOK_TYPES).items():
        features[f"hook_{k}"] = v

    cta_type = ca.get("cta_type", "none") or "none"
    for k, v in _one_hot(cta_type, CTA_TYPES).items():
        features[f"cta_{k}"] = v

    offer_type = ca.get("offer_type", "none") or "none"
    for k, v in _one_hot(offer_type, OFFER_TYPES).items():
        features[f"offer_{k}"] = v

    emotion = ca.get("emotion", "neutral") or "neutral"
    for k, v in _one_hot(emotion, EMOTION_TYPES).items():
        features[f"emotion_{k}"] = v

    # 2. Text length (normalized)
    desc = ad.description or ""
    title = ad.title or ""
    features["text_length_normalized"] = _normalize_text_length(desc)

    # 3. Binary text features
    features["has_emoji"] = 1 if ca.get("has_emoji") else 0
    features["has_numbers"] = 1 if ca.get("has_numbers") else 0
    features["has_testimonial"] = 1 if ca.get("has_testimonial") else 0
    features["has_before_after"] = 1 if ca.get("has_before_after") else 0

    # 4. Creative type (video=1, image=0)
    features["is_video"] = 1 if (ad.creative_type or "").lower() == "video" else 0

    # 5. Word counts
    features["title_word_count"] = _word_count(title)
    features["description_word_count"] = _word_count(desc)

    # 6. Power word count
    full_text = " ".join(filter(None, [title, desc]))
    features["power_word_count"] = _count_power_words(full_text)

    # 7. LP features (if available from D12 or lp_data)
    features["lp_has_form"] = 1 if lp_data.get("has_form") else 0
    features["lp_has_video"] = 1 if lp_data.get("has_video") else 0
    features["lp_has_testimonial"] = 1 if lp_data.get("has_testimonial") else 0
    features["lp_has_price"] = 1 if lp_data.get("has_price") else 0
    features["lp_has_countdown"] = 1 if lp_data.get("has_countdown") else 0

    # 8. Rekognition features (if available)
    features["face_count"] = int(rekognition.get("face_count", 0) or 0)
    features["text_count"] = int(rekognition.get("text_count", 0) or 0)
    features["label_count"] = int(rekognition.get("label_count", 0) or 0)

    # 9. Additional useful features
    features["has_destination_url"] = 1 if ad.destination_url else 0
    features["line_count"] = int(ca.get("line_count", 0) or 0)

    # Longevity features
    days_running = 0
    try:
        days_running = int(meta.get("days_running", 0) or 0)
    except (ValueError, TypeError):
        pass
    features["days_running"] = days_running

    return features


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Build Prediction Features Script")
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

        # Build feature vectors
        feature_rows: list[dict] = []
        updated = 0

        for ad in ads:
            features = build_feature_vector(ad)

            # Store in ad_metadata
            meta = dict(ad.ad_metadata or {})
            meta["prediction_features"] = features
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")
            updated += 1

            # Prepare row for CSV export
            row = {"ad_id": ad.id}
            row.update(features)

            # Add target variable (is_hit)
            hit_level = (ad.ad_metadata or {}).get("hit_level", "none")
            row["is_hit"] = 1 if hit_level in ("hit", "mega_hit") else 0
            row["hit_score"] = float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)

            feature_rows.append(row)

        session.commit()
        print(f"Updated prediction_features for {updated}/{total} ads.")

        # Export feature matrix to CSV
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        csv_path = os.path.join(EXPORTS_DIR, "feature_matrix.csv")

        if feature_rows:
            fieldnames = list(feature_rows[0].keys())
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in feature_rows:
                    writer.writerow(row)
            print(f"Feature matrix exported to: {csv_path}")
            print(f"  Rows: {len(feature_rows)}, Columns: {len(fieldnames)}")

        # Print feature summary
        if feature_rows:
            feature_names = [k for k in feature_rows[0].keys() if k not in ("ad_id", "is_hit", "hit_score")]
            print(f"\n--- Feature Summary ({len(feature_names)} features) ---")

            # Count non-zero values for each feature
            for fname in feature_names[:15]:
                non_zero = sum(1 for r in feature_rows if r.get(fname, 0) != 0)
                pct = non_zero / len(feature_rows) * 100
                print(f"  {fname:<35s} non-zero: {non_zero:>4d} ({pct:>5.1f}%)")
            if len(feature_names) > 15:
                print(f"  ... and {len(feature_names) - 15} more features")

            # Hit distribution
            hits = sum(1 for r in feature_rows if r["is_hit"] == 1)
            print(f"\n--- Target Distribution ---")
            print(f"  Hit ads:     {hits:>4d} ({hits / len(feature_rows) * 100:.1f}%)")
            print(f"  Non-hit ads: {len(feature_rows) - hits:>4d} ({(len(feature_rows) - hits) / len(feature_rows) * 100:.1f}%)")

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
