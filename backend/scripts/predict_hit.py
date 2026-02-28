#!/usr/bin/env python3
"""Predict hit probability for new/unscored ads.

Loads the saved hit predictor model (sklearn or rule-based) and predicts
hit probability for each ad. Stores results in ad_metadata["hit_prediction"].

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/predict_hit.py
"""

import os
import pickle
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from scripts.build_prediction_features import build_feature_vector
from scripts.train_hit_predictor import RuleBasedPredictor  # needed for pickle

MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
)


# ── Prediction helpers ──────────────────────────────────────────────────


def _confidence_label(probability: float) -> str:
    """Convert probability to a confidence label."""
    if probability >= 0.75:
        return "high"
    elif probability >= 0.50:
        return "medium"
    elif probability >= 0.30:
        return "low"
    else:
        return "very_low"


def _identify_factors(
    features: dict, feature_importance: list[tuple[str, float]], top_n: int = 3
) -> tuple[list[str], list[str]]:
    """Identify top positive and negative factors for this ad.

    Returns (top_positive_factors, top_negative_factors).
    """
    # For each feature, compute contribution = feature_value * weight
    contributions = []
    for fname, weight in feature_importance:
        val = features.get(fname, 0)
        if val == 0:
            continue
        contribution = val * weight
        contributions.append((fname, contribution, weight))

    # Sort by contribution
    contributions.sort(key=lambda x: x[1], reverse=True)

    # Top positive: high contribution (feature present AND positive weight)
    positive = []
    for fname, contrib, weight in contributions:
        if contrib > 0 and len(positive) < top_n:
            # Make human-readable label
            label = _feature_to_label(fname)
            positive.append(label)

    # Top negative: features that are absent but would help (or present and hurt)
    negative = []
    # First: present features with negative weight
    for fname, contrib, weight in reversed(contributions):
        if contrib < 0 and len(negative) < top_n:
            label = _feature_to_label(fname)
            negative.append(label)

    # If we need more negatives, check absent features with positive weight
    if len(negative) < top_n:
        for fname, weight in feature_importance:
            if len(negative) >= top_n:
                break
            val = features.get(fname, 0)
            if val == 0 and weight > 0.05:
                label = "no " + _feature_to_label(fname)
                if label not in negative:
                    negative.append(label)

    return positive, negative


def _feature_to_label(fname: str) -> str:
    """Convert a feature name to a human-readable label."""
    # Remove prefixes and clean up
    replacements = {
        "hook_": " hook",
        "cta_": " CTA",
        "offer_": " offer",
        "emotion_": " emotion",
        "lp_has_": "LP has ",
        "lp_": "LP ",
        "has_": "has ",
        "is_": "",
        "_": " ",
    }
    label = fname
    for old, new in replacements.items():
        label = label.replace(old, new)
    return label.strip()


def _generate_recommendation(
    probability: float, positive_factors: list[str], negative_factors: list[str]
) -> str:
    """Generate a brief recommendation based on prediction results."""
    if probability >= 0.75:
        return "Strong creative pattern. Maintain current approach."
    elif probability >= 0.50:
        if negative_factors:
            return f"Good potential. Consider adding: {negative_factors[0]}."
        return "Good potential. Fine-tune elements for higher impact."
    elif probability >= 0.30:
        if negative_factors:
            fixes = ", ".join(negative_factors[:2])
            return f"Moderate potential. Key improvements needed: {fixes}."
        return "Moderate potential. Revise creative elements for better performance."
    else:
        if positive_factors:
            return f"Low hit potential. Strengths: {positive_factors[0]}. Rebuild creative strategy."
        return "Low hit potential. Consider rebuilding creative with proven patterns."


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Hit Prediction Script")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # Load model
    model_path = os.path.join(MODELS_DIR, "hit_predictor.pkl")
    if not os.path.exists(model_path):
        print(f"ERROR: Model not found at {model_path}")
        print("Run train_hit_predictor.py first.")
        return

    with open(model_path, "rb") as f:
        model_package = pickle.load(f)

    model = model_package["model"]
    feature_names = model_package["feature_names"]
    model_type = model_package.get("model_type", "unknown")
    scaler = model_package.get("scaler")  # Only for sklearn

    print(f"Model type: {model_type}")
    print(f"Features: {len(feature_names)}")

    # Get feature importance for factor analysis
    if model_type == "sklearn":
        coefs = model.coef_[0]
        feature_importance = [
            (feature_names[i], float(coefs[i]))
            for i in range(len(feature_names))
        ]
    else:
        # Rule-based model
        feature_importance = model.get_feature_importance()

    # Sort by absolute weight for factor identification
    feature_importance_sorted = sorted(
        feature_importance, key=lambda x: abs(x[1]), reverse=True
    )

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"\nTotal ads: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        predicted = 0
        prob_sum = 0.0
        confidence_counts: dict[str, int] = {}

        for ad in ads:
            # Build feature vector
            features = build_feature_vector(ad)

            # Build ordered feature list matching model's expected order
            feature_vec = []
            for fname in feature_names:
                feature_vec.append(float(features.get(fname, 0)))

            # Predict
            if model_type == "sklearn" and scaler is not None:
                import numpy as np
                X = scaler.transform(np.array([feature_vec]))
                prob = float(model.predict_proba(X)[0][1])
            else:
                probs = model.predict_proba([feature_vec])
                prob = probs[0]

            confidence = _confidence_label(prob)
            positive_factors, negative_factors = _identify_factors(
                features, feature_importance_sorted
            )
            recommendation = _generate_recommendation(
                prob, positive_factors, negative_factors
            )

            # Build prediction result
            prediction = {
                "probability": round(prob, 4),
                "confidence": confidence,
                "top_positive_factors": positive_factors,
                "top_negative_factors": negative_factors,
                "recommendation": recommendation,
                "model_type": model_type,
                "predicted_at": datetime.now(timezone.utc).isoformat(),
            }

            # Store in ad_metadata
            meta = dict(ad.ad_metadata or {})
            meta["hit_prediction"] = prediction
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            predicted += 1
            prob_sum += prob
            confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1

        session.commit()
        print(f"\nPredictions stored for {predicted}/{total} ads.")

        # Summary statistics
        avg_prob = prob_sum / predicted if predicted > 0 else 0
        print(f"\n--- Prediction Summary ---")
        print(f"  Average probability: {avg_prob:.4f}")
        print(f"  Confidence distribution:")
        for conf, count in sorted(confidence_counts.items()):
            pct = count / predicted * 100 if predicted > 0 else 0
            print(f"    {conf:<10s}: {count:>4d} ({pct:>5.1f}%)")

        # Show sample predictions
        print(f"\n--- Sample Predictions (first 5) ---")
        sample_ads = session.query(Ad).limit(5).all()
        for ad in sample_ads:
            pred = (ad.ad_metadata or {}).get("hit_prediction", {})
            title_safe = (ad.title or "")[:40].encode("ascii", "replace").decode("ascii")
            print(f"  ID={ad.id} title={title_safe!r}")
            print(f"    prob={pred.get('probability', '?'):.4f}  "
                  f"confidence={pred.get('confidence', '?')}")
            pos = pred.get("top_positive_factors", [])
            neg = pred.get("top_negative_factors", [])
            if pos:
                print(f"    positive: {', '.join(pos[:3])}")
            if neg:
                print(f"    negative: {', '.join(neg[:3])}")
            rec = pred.get("recommendation", "")
            if rec:
                print(f"    recommendation: {rec}")

        print("\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
