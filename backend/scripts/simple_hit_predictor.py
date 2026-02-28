#!/usr/bin/env python3
"""Simple rule-based hit predictor using correlation-weighted features.

Loads the pre-built feature matrix from exports/feature_matrix.json,
learns per-feature weights via Pearson correlation with hit_score,
predicts hit probability, and evaluates prediction accuracy.

No external ML libraries required (no sklearn, numpy, scipy).

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/simple_hit_predictor.py
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
FEATURE_MATRIX_PATH = os.path.join(EXPORTS_DIR, "feature_matrix.json")
WEIGHTS_OUTPUT_PATH = os.path.join(EXPORTS_DIR, "predictor_weights.json")

HIT_THRESHOLD = 45  # predicted_score >= 45 => predicted hit


# ---------------------------------------------------------------------------
# Pure-Python math helpers
# ---------------------------------------------------------------------------

def _mean(xs):
    """Arithmetic mean."""
    if not xs:
        return 0.0
    return sum(xs) / len(xs)


def pearson_correlation(xs, ys):
    """Compute Pearson correlation coefficient between two lists.

    Returns 0 when inputs are constant or too short.
    """
    n = len(xs)
    if n < 2:
        return 0.0
    mx = _mean(xs)
    my = _mean(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denom_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denom_x == 0.0 or denom_y == 0.0:
        return 0.0
    return numerator / (denom_x * denom_y)


def min_max_normalize(values):
    """Min-max normalize a list of numbers to [0, 1].

    Returns 0.5 for all entries when min == max.
    """
    mn = min(values)
    mx = max(values)
    if mx == mn:
        return [0.5] * len(values)
    rng = mx - mn
    return [(v - mn) / rng for v in values]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Simple Hit Predictor (Correlation-Weighted)")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load feature matrix from exports/feature_matrix.json
    # ------------------------------------------------------------------
    if not os.path.exists(FEATURE_MATRIX_PATH):
        print(f"\nERROR: Feature matrix not found at {FEATURE_MATRIX_PATH}")
        print("Run  python scripts/build_feature_matrix.py  first.")
        sys.exit(1)

    with open(FEATURE_MATRIX_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    matrix = data.get("data", data.get("matrix", []))
    feature_names = data.get("feature_names", [])
    total = len(matrix)

    print(f"\nLoaded {total} ads from {FEATURE_MATRIX_PATH}")
    print(f"Features ({len(feature_names)}): {', '.join(feature_names)}")

    if total == 0:
        print("No ads in feature matrix. Exiting.")
        return

    if not feature_names:
        # Derive feature names from first record if not stored at top level
        feature_names = list(matrix[0].get("features", {}).keys())

    # Extract target (hit_score / target) for every row
    scores = [float(row.get("target", row.get("hit_score", 0))) for row in matrix]

    # ------------------------------------------------------------------
    # 2. Compute Pearson correlation of each feature with hit_score
    # ------------------------------------------------------------------
    weights = {}
    for fname in feature_names:
        fvals = [float(row["features"].get(fname, 0)) for row in matrix]
        corr = pearson_correlation(fvals, scores)
        weights[fname] = round(corr, 6)

    print(f"\n--- Learned Weights (Pearson correlation with hit_score) ---")
    for fname, w in sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True):
        bar = "#" * int(abs(w) * 40)
        print(f"  {fname:<30s} {w:+.6f}  {bar}")

    # ------------------------------------------------------------------
    # 3. Predict: weighted sum of normalised features
    # ------------------------------------------------------------------
    # Normalise each feature column to [0, 1]
    normalized = {}
    for fname in feature_names:
        raw = [float(row["features"].get(fname, 0)) for row in matrix]
        normalized[fname] = min_max_normalize(raw)

    # Weighted sum per ad, then normalise to 0-100
    raw_predictions = []
    abs_weight_sum = sum(abs(weights[fn]) for fn in feature_names)

    for i in range(total):
        wsum = sum(weights[fn] * normalized[fn][i] for fn in feature_names)
        raw_predictions.append(wsum)

    # Normalise raw predictions to 0-100
    if abs_weight_sum > 0:
        predictions = []
        pred_min = min(raw_predictions)
        pred_max = max(raw_predictions)
        if pred_max == pred_min:
            predictions = [50.0] * total
        else:
            for rp in raw_predictions:
                norm = (rp - pred_min) / (pred_max - pred_min) * 100.0
                predictions.append(max(0.0, min(100.0, norm)))
    else:
        predictions = [50.0] * total

    # ------------------------------------------------------------------
    # 4. Classify and build confusion matrix
    # ------------------------------------------------------------------
    tp = fp = tn = fn_ = 0
    for i in range(total):
        actual_hit = scores[i] >= HIT_THRESHOLD
        predicted_hit = predictions[i] >= HIT_THRESHOLD
        if actual_hit and predicted_hit:
            tp += 1
        elif actual_hit and not predicted_hit:
            fn_ += 1
        elif not actual_hit and predicted_hit:
            fp += 1
        else:
            tn += 1

    # ------------------------------------------------------------------
    # 5. Compute evaluation metrics
    # ------------------------------------------------------------------
    accuracy = (tp + tn) / total * 100.0 if total > 0 else 0.0
    precision = tp / (tp + fp) * 100.0 if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn_) * 100.0 if (tp + fn_) > 0 else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    # ------------------------------------------------------------------
    # 6. Print confusion matrix
    # ------------------------------------------------------------------
    print(f"\n--- Confusion Matrix (threshold = {HIT_THRESHOLD}) ---")
    print(f"                    Predicted HIT   Predicted NOT-HIT")
    print(f"  Actual HIT           {tp:>6d}            {fn_:>6d}")
    print(f"  Actual NOT-HIT       {fp:>6d}            {tn:>6d}")
    print()
    print(f"  Accuracy:   {accuracy:.2f}%")
    print(f"  Precision:  {precision:.2f}%")
    print(f"  Recall:     {recall:.2f}%")
    print(f"  F1 Score:   {f1:.2f}%")
    print()

    # Score distribution summary
    actual_hits = sum(1 for s in scores if s >= HIT_THRESHOLD)
    predicted_hits = sum(1 for p in predictions if p >= HIT_THRESHOLD)
    print(f"  Actual hits:    {actual_hits}/{total} ({actual_hits/total*100:.1f}%)")
    print(f"  Predicted hits: {predicted_hits}/{total} ({predicted_hits/total*100:.1f}%)")

    # ------------------------------------------------------------------
    # 7. Store weights in exports/predictor_weights.json
    # ------------------------------------------------------------------
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "correlation-weighted rule-based predictor",
        "total_ads": total,
        "hit_threshold": HIT_THRESHOLD,
        "feature_count": len(feature_names),
        "weights": weights,
        "evaluation": {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "confusion_matrix": {
                "true_positive": tp,
                "false_positive": fp,
                "true_negative": tn,
                "false_negative": fn_,
            },
        },
        "predictions": [
            {
                "ad_id": matrix[i].get("ad_id"),
                "actual_score": round(scores[i], 2),
                "predicted_score": round(predictions[i], 2),
                "actual_hit": scores[i] >= HIT_THRESHOLD,
                "predicted_hit": predictions[i] >= HIT_THRESHOLD,
            }
            for i in range(total)
        ],
    }

    with open(WEIGHTS_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nWeights exported to: {WEIGHTS_OUTPUT_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
