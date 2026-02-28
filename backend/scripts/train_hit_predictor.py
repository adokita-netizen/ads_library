#!/usr/bin/env python3
"""Train a hit predictor model from feature vectors.

Uses scikit-learn if available; otherwise falls back to a rule-based predictor
using feature weights derived from hit rate correlation.

Outputs:
  - Model file:        backend/models/hit_predictor.pkl
  - Feature importance: backend/exports/feature_importance.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/train_hit_predictor.py
"""

import csv
import json
import math
import os
import pickle
import sys
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)
MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
)


# ── sklearn availability check ──────────────────────────────────────────

_HAS_SKLEARN = False
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score, train_test_split
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score,
        f1_score, confusion_matrix,
    )
    from sklearn.preprocessing import StandardScaler
    _HAS_SKLEARN = True
except ImportError:
    pass


# ── Rule-based predictor (fallback) ─────────────────────────────────────


class RuleBasedPredictor:
    """Simple weighted-sum predictor using per-feature hit-rate correlation.

    For each binary/numeric feature, computes:
        weight = (hit_rate_when_present - baseline_hit_rate)
    At prediction time, computes:
        score = sum(feature_value * weight) + intercept
        probability = sigmoid(score)
    """

    def __init__(self):
        self.weights: dict[str, float] = {}
        self.intercept: float = 0.0
        self.feature_names: list[str] = []
        self.baseline_hit_rate: float = 0.0

    def fit(self, X: list[list[float]], y: list[int], feature_names: list[str]):
        """Train the model by computing correlation-based weights."""
        self.feature_names = list(feature_names)
        n = len(y)
        if n == 0:
            return

        total_hits = sum(y)
        self.baseline_hit_rate = total_hits / n if n > 0 else 0.0

        # Compute per-feature weights
        for j, fname in enumerate(feature_names):
            present_hits = 0
            present_total = 0
            absent_hits = 0
            absent_total = 0

            for i in range(n):
                val = X[i][j]
                if val > 0:
                    present_total += 1
                    if y[i] == 1:
                        present_hits += 1
                else:
                    absent_total += 1
                    if y[i] == 1:
                        absent_hits += 1

            # Weight = difference in hit rate (present vs absent)
            present_rate = present_hits / present_total if present_total > 0 else 0
            absent_rate = absent_hits / absent_total if absent_total > 0 else self.baseline_hit_rate

            # Only use weight if we have enough samples
            if present_total >= 2:
                weight = present_rate - absent_rate
            else:
                weight = 0.0

            self.weights[fname] = weight

        # Intercept is baseline log-odds
        if 0 < self.baseline_hit_rate < 1:
            self.intercept = math.log(self.baseline_hit_rate / (1 - self.baseline_hit_rate))
        else:
            self.intercept = 0.0

    def predict_proba(self, X: list[list[float]]) -> list[float]:
        """Predict hit probability for each sample."""
        probabilities = []
        for row in X:
            score = self.intercept
            for j, val in enumerate(row):
                fname = self.feature_names[j] if j < len(self.feature_names) else ""
                w = self.weights.get(fname, 0.0)
                score += val * w * 2.0  # Scale factor for better separation
            # Sigmoid
            prob = 1.0 / (1.0 + math.exp(-max(-20, min(20, score))))
            probabilities.append(prob)
        return probabilities

    def predict(self, X: list[list[float]], threshold: float = 0.5) -> list[int]:
        """Predict binary labels."""
        probs = self.predict_proba(X)
        return [1 if p >= threshold else 0 for p in probs]

    def get_feature_importance(self) -> list[tuple[str, float]]:
        """Return features sorted by absolute weight."""
        return sorted(
            self.weights.items(),
            key=lambda x: abs(x[1]),
            reverse=True,
        )


def _compute_metrics(y_true: list[int], y_pred: list[int]) -> dict:
    """Compute accuracy, precision, recall, F1 without sklearn."""
    tp = sum(1 for a, b in zip(y_true, y_pred) if a == 1 and b == 1)
    fp = sum(1 for a, b in zip(y_true, y_pred) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(y_true, y_pred) if a == 1 and b == 0)
    tn = sum(1 for a, b in zip(y_true, y_pred) if a == 0 and b == 0)

    total = len(y_true)
    accuracy = (tp + tn) / total if total > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "confusion_matrix": [[tn, fp], [fn, tp]],
    }


def _simple_train_test_split(
    X: list[list[float]], y: list[int], test_ratio: float = 0.2, seed: int = 42
) -> tuple:
    """Simple deterministic train/test split."""
    import random
    rng = random.Random(seed)
    indices = list(range(len(y)))
    rng.shuffle(indices)
    split_idx = int(len(indices) * (1 - test_ratio))

    train_idx = indices[:split_idx]
    test_idx = indices[split_idx:]

    X_train = [X[i] for i in train_idx]
    X_test = [X[i] for i in test_idx]
    y_train = [y[i] for i in train_idx]
    y_test = [y[i] for i in test_idx]

    return X_train, X_test, y_train, y_test


def _cross_validate_rule_based(
    X: list[list[float]], y: list[int], feature_names: list[str], n_folds: int = 5
) -> list[float]:
    """Simple k-fold cross-validation for rule-based model."""
    import random
    rng = random.Random(42)
    indices = list(range(len(y)))
    rng.shuffle(indices)

    fold_size = len(indices) // n_folds
    fold_scores = []

    for fold in range(n_folds):
        start = fold * fold_size
        end = start + fold_size if fold < n_folds - 1 else len(indices)
        test_idx = set(indices[start:end])
        train_idx = [i for i in indices if i not in test_idx]

        X_train = [X[i] for i in train_idx]
        y_train = [y[i] for i in train_idx]
        X_test = [X[i] for i in test_idx]
        y_test = [y[i] for i in test_idx]

        model = RuleBasedPredictor()
        model.fit(X_train, y_train, feature_names)
        y_pred = model.predict(X_test)

        # Accuracy for this fold
        correct = sum(1 for a, b in zip(y_test, y_pred) if a == b)
        fold_scores.append(correct / len(y_test) if y_test else 0)

    return fold_scores


# ── Main ─────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("Train Hit Predictor Script")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print(f"sklearn available: {_HAS_SKLEARN}")
    print("=" * 60)

    # Load feature matrix
    csv_path = os.path.join(EXPORTS_DIR, "feature_matrix.csv")
    if not os.path.exists(csv_path):
        print(f"ERROR: Feature matrix not found at {csv_path}")
        print("Run build_prediction_features.py first.")
        return

    # Read CSV
    rows: list[dict] = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    total = len(rows)
    print(f"\nLoaded {total} rows from feature_matrix.csv")

    if total < 10:
        print("ERROR: Need at least 10 ads to train a model.")
        return

    # Extract feature names (exclude ad_id, is_hit, hit_score)
    exclude_cols = {"ad_id", "is_hit", "hit_score"}
    feature_names = [k for k in rows[0].keys() if k not in exclude_cols]
    print(f"Features: {len(feature_names)}")

    # Build X, y matrices
    X: list[list[float]] = []
    y: list[int] = []
    for row in rows:
        feature_vec = []
        for fname in feature_names:
            try:
                feature_vec.append(float(row.get(fname, 0) or 0))
            except (ValueError, TypeError):
                feature_vec.append(0.0)
        X.append(feature_vec)
        y.append(int(float(row.get("is_hit", 0) or 0)))

    hit_count = sum(y)
    non_hit_count = total - hit_count
    print(f"Target distribution: {hit_count} hits, {non_hit_count} non-hits")

    if hit_count == 0 or non_hit_count == 0:
        print("WARNING: All ads are the same class. Model will not be useful.")

    # ── Train model ──────────────────────────────────────────────────

    model_info = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_samples": total,
        "hit_count": hit_count,
        "non_hit_count": non_hit_count,
        "feature_count": len(feature_names),
        "model_type": "",
    }

    if _HAS_SKLEARN:
        print("\nUsing scikit-learn LogisticRegression...")
        model_info["model_type"] = "sklearn_logistic_regression"

        import numpy as np

        X_np = np.array(X, dtype=np.float64)
        y_np = np.array(y, dtype=np.int64)

        # Standardize features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_np)

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y_np, test_size=0.2, random_state=42, stratify=y_np
        )

        # Train model
        model = LogisticRegression(
            max_iter=1000,
            random_state=42,
            class_weight="balanced",
        )
        model.fit(X_train, y_train)

        # Evaluate
        y_pred = model.predict(X_test)
        y_pred_train = model.predict(X_train)

        train_acc = accuracy_score(y_train, y_pred_train)
        test_acc = accuracy_score(y_test, y_pred)
        test_prec = precision_score(y_test, y_pred, zero_division=0)
        test_rec = recall_score(y_test, y_pred, zero_division=0)
        test_f1 = f1_score(y_test, y_pred, zero_division=0)
        cm = confusion_matrix(y_test, y_pred).tolist()

        # Cross-validation
        cv_scores = cross_val_score(model, X_scaled, y_np, cv=5, scoring="accuracy")

        model_info["train_accuracy"] = round(float(train_acc), 4)
        model_info["test_accuracy"] = round(float(test_acc), 4)
        model_info["precision"] = round(float(test_prec), 4)
        model_info["recall"] = round(float(test_rec), 4)
        model_info["f1"] = round(float(test_f1), 4)
        model_info["confusion_matrix"] = cm
        model_info["cv_scores"] = [round(float(s), 4) for s in cv_scores]
        model_info["cv_mean"] = round(float(cv_scores.mean()), 4)
        model_info["cv_std"] = round(float(cv_scores.std()), 4)

        # Feature importance
        coefs = model.coef_[0]
        importance_pairs = [
            (feature_names[i], round(float(coefs[i]), 4))
            for i in range(len(feature_names))
        ]
        importance_pairs.sort(key=lambda x: abs(x[1]), reverse=True)

        # Save model (sklearn model + scaler + feature_names)
        model_package = {
            "model": model,
            "scaler": scaler,
            "feature_names": feature_names,
            "model_type": "sklearn",
        }

        print(f"\n--- Model Performance ---")
        print(f"  Train accuracy: {train_acc:.4f}")
        print(f"  Test accuracy:  {test_acc:.4f}")
        print(f"  Precision:      {test_prec:.4f}")
        print(f"  Recall:         {test_rec:.4f}")
        print(f"  F1 Score:       {test_f1:.4f}")
        print(f"  CV Mean:        {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
        print(f"\n--- Confusion Matrix ---")
        print(f"  TN={cm[0][0]:>4d}  FP={cm[0][1]:>4d}")
        print(f"  FN={cm[1][0]:>4d}  TP={cm[1][1]:>4d}")

    else:
        print("\nsklearn not available. Using rule-based predictor (feature weight correlation)...")
        model_info["model_type"] = "rule_based_correlation"

        # Train/test split
        X_train, X_test, y_train, y_test = _simple_train_test_split(X, y, test_ratio=0.2)

        # Train model
        model_rb = RuleBasedPredictor()
        model_rb.fit(X_train, y_train, feature_names)

        # Evaluate on test set
        y_pred = model_rb.predict(X_test)
        y_pred_train = model_rb.predict(X_train)

        test_metrics = _compute_metrics(y_test, y_pred)
        train_metrics = _compute_metrics(y_train, y_pred_train)

        # Cross-validation
        cv_scores = _cross_validate_rule_based(X, y, feature_names, n_folds=5)

        model_info["train_accuracy"] = train_metrics["accuracy"]
        model_info["test_accuracy"] = test_metrics["accuracy"]
        model_info["precision"] = test_metrics["precision"]
        model_info["recall"] = test_metrics["recall"]
        model_info["f1"] = test_metrics["f1"]
        model_info["confusion_matrix"] = test_metrics["confusion_matrix"]
        model_info["cv_scores"] = [round(s, 4) for s in cv_scores]
        model_info["cv_mean"] = round(mean(cv_scores), 4) if cv_scores else 0
        model_info["cv_std"] = round(
            (sum((s - mean(cv_scores)) ** 2 for s in cv_scores) / len(cv_scores)) ** 0.5, 4
        ) if cv_scores else 0

        # Feature importance
        importance_pairs = [
            (name, round(weight, 4))
            for name, weight in model_rb.get_feature_importance()
        ]

        # Save model
        model_package = {
            "model": model_rb,
            "feature_names": feature_names,
            "model_type": "rule_based",
        }

        print(f"\n--- Model Performance (Rule-Based) ---")
        print(f"  Train accuracy:  {train_metrics['accuracy']:.4f}")
        print(f"  Test accuracy:   {test_metrics['accuracy']:.4f}")
        print(f"  Precision:       {test_metrics['precision']:.4f}")
        print(f"  Recall:          {test_metrics['recall']:.4f}")
        print(f"  F1 Score:        {test_metrics['f1']:.4f}")
        print(f"  CV Mean:         {model_info['cv_mean']:.4f} (+/- {model_info['cv_std']:.4f})")
        cm = test_metrics["confusion_matrix"]
        print(f"\n--- Confusion Matrix ---")
        print(f"  TN={cm[0][0]:>4d}  FP={cm[0][1]:>4d}")
        print(f"  FN={cm[1][0]:>4d}  TP={cm[1][1]:>4d}")

    # ── Print feature importance ─────────────────────────────────────

    print(f"\n--- Top 20 Feature Importance ---")
    print(f"  {'Rank':>4s} {'Feature':<35s} {'Weight':>8s}")
    print(f"  {'-' * 50}")
    for i, (fname, weight) in enumerate(importance_pairs[:20], 1):
        direction = "+" if weight > 0 else "-" if weight < 0 else " "
        print(f"  {i:>4d} {fname:<35s} {direction}{abs(weight):>7.4f}")

    # ── Save model ───────────────────────────────────────────────────

    os.makedirs(MODELS_DIR, exist_ok=True)
    model_path = os.path.join(MODELS_DIR, "hit_predictor.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model_package, f)
    print(f"\nModel saved to: {model_path}")

    # ── Save feature importance JSON ─────────────────────────────────

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    importance_export = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_info": model_info,
        "feature_importance": [
            {"rank": i + 1, "feature": fname, "weight": weight}
            for i, (fname, weight) in enumerate(importance_pairs)
        ],
    }
    importance_path = os.path.join(EXPORTS_DIR, "feature_importance.json")
    with open(importance_path, "w", encoding="utf-8") as f:
        json.dump(importance_export, f, ensure_ascii=False, indent=2)
    print(f"Feature importance saved to: {importance_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
