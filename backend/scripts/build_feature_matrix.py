#!/usr/bin/env python3
"""Build feature matrix from all ads for hit prediction.

Extracts numerical features from each ad (title metrics, one-hot encoded
categorical fields, advertiser stats, temporal features, emotion scores)
and exports them as a JSON feature matrix ready for prediction.

Output: backend/exports/feature_matrix.json
Format: {"feature_names": [...], "data": [{"ad_id": 1, "features": {...}, "target": 93.0}, ...]}

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/build_feature_matrix.py
"""

import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── Constants ────────────────────────────────────────────────────────────

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)

# Positive / negative sentiment keywords for title analysis
POSITIVE_KEYWORDS = [
    "amazing", "beautiful", "love", "perfect", "great", "excellent",
    "wonderful", "fantastic", "incredible", "superb", "brilliant",
    # Japanese positive
    "\u7d20\u6674\u3089\u3057\u3044", "\u6700\u9ad8", "\u5b89\u5fc3",
    "\u4fbf\u5229", "\u5feb\u9069", "\u7406\u60f3", "\u6539\u5584",
    "\u52b9\u679c", "\u7d50\u679c", "\u304a\u5f97", "\u7c21\u5358",
    "\u5e78\u305b", "\u7f8e\u3057\u3044",
]

NEGATIVE_KEYWORDS = [
    "warning", "danger", "risk", "problem", "trouble", "pain",
    "struggle", "worry", "fear", "ugly", "bad", "worst",
    # Japanese negative
    "\u5371\u967a", "\u640d", "\u5f8c\u6094", "\u8001\u5316",
    "\u653e\u7f6e", "\u624b\u9045\u308c", "\u30ea\u30b9\u30af",
    "\u5931\u6557", "\u4e0d\u5b89", "\u8b66\u544a", "\u8981\u6ce8\u610f",
]

# Known hook types used in creative_analysis
HOOK_TYPES = [
    "none", "urgency", "social_proof", "pain_point", "statistic",
    "benefit", "question", "curiosity", "shocking", "story",
    "testimonial", "authority", "emotional", "comparison",
    "challenge", "how_to", "list", "news", "problem",
]

# Known CTA types
CTA_TYPES = [
    "none", "line_add", "purchase", "signup", "free_trial",
    "consultation", "download", "learn_more", "urgency",
    "discount", "buy_now", "limited_time", "get_started",
    "apply_now", "book_now", "claim", "subscribe", "contact",
    "shop_now", "sign_up",
]

# Known genre (category) values
GENRE_TYPES = [
    "ec_d2c", "app", "finance", "education", "beauty", "food",
    "gaming", "health", "technology", "real_estate", "travel", "other",
]

# Emotion categories used in emotion_analysis
EMOTION_TYPES = [
    "anxiety", "hope", "urgency", "curiosity", "trust", "fear",
]


# ── Helpers ──────────────────────────────────────────────────────────────


def _get_score(ad: Ad) -> float:
    """Get hit score from ad_metadata, default 0."""
    meta = ad.ad_metadata or {}
    try:
        return float(meta.get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _one_hot(value: str, categories: list[str], prefix: str) -> dict[str, int]:
    """Create one-hot encoding dict with a prefix.

    Returns e.g. {"hook_none": 1, "hook_benefit": 0, ...}
    """
    value_clean = (value or "").lower().strip()
    if value_clean not in categories:
        value_clean = categories[0]  # default to first (typically "none" / "other")
    result = {}
    for cat in categories:
        result[f"{prefix}_{cat}"] = 1 if value_clean == cat else 0
    return result


def _count_power_words_from_keywords(ad: Ad) -> int:
    """Count power words from ad_metadata['keywords'].

    Keywords is typically a list of strings extracted by extract_keywords.py.
    """
    meta = ad.ad_metadata or {}
    keywords = meta.get("keywords", [])
    if isinstance(keywords, list):
        return len(keywords)
    return 0


def _word_count(text: str) -> int:
    """Count words in text (space-separated for ASCII, char-based for JP)."""
    if not text:
        return 0
    ascii_words = len(re.findall(r'[a-zA-Z]+', text))
    jp_chars = len(re.findall(r'[\u3000-\u9fff\uff00-\uffef]', text))
    return ascii_words + jp_chars


def _count_keyword_matches(text: str, keywords: list[str]) -> int:
    """Count how many keywords appear in text."""
    if not text:
        return 0
    text_lower = text.lower()
    return sum(1 for w in keywords if w.lower() in text_lower)


def _pearson_correlation(xs: list[float], ys: list[float]) -> float:
    """Compute Pearson correlation coefficient (stdlib only)."""
    n = len(xs)
    if n == 0:
        return 0.0
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    numerator = 0.0
    denom_x = 0.0
    denom_y = 0.0
    for i in range(n):
        dx = xs[i] - x_mean
        dy = ys[i] - y_mean
        numerator += dx * dy
        denom_x += dx * dx
        denom_y += dy * dy
    denom = math.sqrt(denom_x * denom_y)
    if denom == 0:
        return 0.0
    return numerator / denom


# ── Feature Extraction ──────────────────────────────────────────────────


def extract_features(ad: Ad, advertiser_stats: dict) -> dict:
    """Extract feature vector from a single ad.

    Returns a flat dict of feature_name -> numeric_value.
    """
    title = ad.title or ""
    title_lower = title.lower()
    meta = ad.ad_metadata or {}
    ca = meta.get("creative_analysis", {}) or {}

    features: dict[str, float] = {}

    # ---- Title text features ----
    features["title_length"] = len(title)
    features["word_count"] = _word_count(title)

    # Power word count from ad_metadata["keywords"]
    features["power_word_count"] = _count_power_words_from_keywords(ad)

    # Positive / negative keyword counts from title
    features["positive_keyword_count"] = _count_keyword_matches(title, POSITIVE_KEYWORDS)
    features["negative_keyword_count"] = _count_keyword_matches(title, NEGATIVE_KEYWORDS)

    # ---- Hook type one-hot ----
    hook_type = ca.get("hook_type") or "none"
    # Also check AdAnalysis relationship
    if hook_type == "none" and ad.analysis and ad.analysis.hook_type:
        hook_type = ad.analysis.hook_type
    hook_oh = _one_hot(hook_type, HOOK_TYPES, "hook")
    features.update(hook_oh)

    # ---- CTA type one-hot ----
    cta_type = ca.get("cta_type") or "none"
    if cta_type == "none" and ad.analysis and ad.analysis.cta_type:
        cta_type = ad.analysis.cta_type
    cta_oh = _one_hot(cta_type, CTA_TYPES, "cta")
    features.update(cta_oh)

    # ---- Genre one-hot ----
    genre = "other"
    if ad.category:
        genre = str(ad.category.value)
    genre_oh = _one_hot(genre, GENRE_TYPES, "genre")
    features.update(genre_oh)

    # ---- Media features ----
    features["has_video"] = 1 if (ad.creative_type or "").lower() == "video" else 0
    features["has_lp"] = 1 if ad.destination_url else 0

    # ---- Advertiser features ----
    adv_name = ad.advertiser_name or "unknown"
    adv_stats = advertiser_stats.get(adv_name, {"count": 0, "avg_score": 0.0})
    features["advertiser_ad_count"] = adv_stats["count"]
    features["advertiser_avg_score"] = round(adv_stats["avg_score"], 2)

    # ---- Temporal features ----
    first_seen = ad.first_seen_at or ad.created_at
    features["day_of_week_first_seen"] = first_seen.weekday() if first_seen else 0
    features["month_first_seen"] = first_seen.month if first_seen else 1

    # ---- Emotion scores from ad_metadata["emotion_analysis"] ----
    emotion_data = meta.get("emotion_analysis", {}) or {}
    emotion_scores = emotion_data.get("scores", {}) or {}
    for emo in EMOTION_TYPES:
        val = 0.0
        try:
            val = float(emotion_scores.get(emo, 0) or 0)
        except (ValueError, TypeError):
            pass
        features[f"emotion_{emo}"] = val

    return features


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Build Feature Matrix for Hit Prediction")
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

        # Pre-compute advertiser stats
        print("Computing advertiser statistics...")
        advertiser_ads: dict[str, list[float]] = defaultdict(list)
        for ad in ads:
            name = ad.advertiser_name or "unknown"
            advertiser_ads[name].append(_get_score(ad))

        advertiser_stats: dict[str, dict] = {}
        for name, scores in advertiser_ads.items():
            advertiser_stats[name] = {
                "count": len(scores),
                "avg_score": sum(scores) / len(scores) if scores else 0.0,
            }
        print(f"  {len(advertiser_stats)} unique advertisers")

        # Extract features for all ads
        print("Extracting features...")
        feature_names: list[str] | None = None
        data: list[dict] = []

        for ad in ads:
            features = extract_features(ad, advertiser_stats)
            score = _get_score(ad)

            if feature_names is None:
                feature_names = list(features.keys())

            data.append({
                "ad_id": ad.id,
                "features": features,
                "target": round(score, 2),
            })

        print(f"  Extracted {len(data)} feature vectors")
        print(f"  Feature count: {len(feature_names)}")

        # ---- Feature importance: Pearson correlation with hit_score ----
        print(f"\n{'=' * 60}")
        print("Feature Importance (Pearson correlation with hit_score)")
        print(f"{'=' * 60}")

        targets = [d["target"] for d in data]
        importance: dict[str, float] = {}

        for fname in feature_names:
            fvals = [d["features"][fname] for d in data]
            corr = _pearson_correlation(fvals, targets)
            importance[fname] = round(corr, 4)

        # Sort by absolute correlation descending
        sorted_imp = sorted(importance.items(), key=lambda x: abs(x[1]), reverse=True)
        for fname, corr in sorted_imp:
            direction = "+" if corr >= 0 else "-"
            bar_len = int(abs(corr) * 40)
            bar = "#" * bar_len
            print(f"  {fname:<35s} {direction}{abs(corr):.4f} {bar}")

        # ---- Feature distribution summary ----
        print(f"\n{'=' * 60}")
        print("Feature Distribution Summary (top 10 by variance)")
        print(f"{'=' * 60}")

        variances = {}
        for fname in feature_names:
            fvals = [d["features"][fname] for d in data]
            fmean = sum(fvals) / len(fvals) if fvals else 0
            var = sum((v - fmean) ** 2 for v in fvals) / len(fvals) if fvals else 0
            variances[fname] = var

        sorted_var = sorted(variances.items(), key=lambda x: x[1], reverse=True)
        for fname, var in sorted_var[:10]:
            fvals = [d["features"][fname] for d in data]
            fmin = min(fvals) if fvals else 0
            fmax = max(fvals) if fvals else 0
            fmean = sum(fvals) / len(fvals) if fvals else 0
            non_zero = sum(1 for v in fvals if v != 0)
            print(
                f"  {fname:<35s} "
                f"mean={fmean:>8.2f}  min={fmin:>6.1f}  max={fmax:>8.1f}  "
                f"non-zero={non_zero:>4d}/{len(fvals)}"
            )

        # ---- Target distribution ----
        print(f"\n{'=' * 60}")
        print("Target (hit_score) Distribution")
        print(f"{'=' * 60}")
        if targets:
            avg_target = sum(targets) / len(targets)
            print(f"  Count:   {len(targets)}")
            print(f"  Mean:    {avg_target:.2f}")
            print(f"  Min:     {min(targets):.2f}")
            print(f"  Max:     {max(targets):.2f}")

            ranges = {"0-19": 0, "20-39": 0, "40-59": 0, "60-79": 0, "80-100": 0}
            for t in targets:
                if t < 20:
                    ranges["0-19"] += 1
                elif t < 40:
                    ranges["20-39"] += 1
                elif t < 60:
                    ranges["40-59"] += 1
                elif t < 80:
                    ranges["60-79"] += 1
                else:
                    ranges["80-100"] += 1

            for label, count in ranges.items():
                bar = "#" * (count // 2 + (1 if count % 2 else 0))
                print(f"  {label:>7s}: {count:>4d} {bar}")

        # ---- Export ----
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        output = {
            "feature_names": feature_names,
            "data": data,
        }

        out_path = os.path.join(EXPORTS_DIR, "feature_matrix.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)

        print(f"\nExported: {out_path}")
        print(f"  Feature names: {len(feature_names)}")
        print(f"  Data rows:     {len(data)}")
        print("Done!")

    except Exception as e:
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
