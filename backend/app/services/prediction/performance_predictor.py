"""Performance prediction models for CTR, CVR, and winning probability."""

import json
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import structlog

from app.services.prediction.feature_engineering import AdFeatures, FeatureEngineer

logger = structlog.get_logger()


class PerformancePredictor:
    """Predict ad performance metrics (CTR, CVR, winning probability)."""

    def __init__(
        self,
        model_dir: str = "ml_models",
        feature_engineer: Optional[FeatureEngineer] = None,
    ):
        self.model_dir = Path(model_dir)
        self.feature_engineer = feature_engineer or FeatureEngineer()
        self._ctr_model = None
        self._cvr_model = None
        self._winning_model = None

    def _load_model(self, model_name: str):
        """Load a trained model from disk."""
        model_path = self.model_dir / f"{model_name}.pkl"
        if model_path.exists():
            with open(model_path, "rb") as f:
                return pickle.load(f)
        return None

    def predict_performance(
        self,
        video_analysis: dict,
        audio_analysis: dict,
        platform: str = "youtube",
    ) -> dict:
        """Predict performance metrics for an ad."""
        features = self.feature_engineer.extract_features(
            video_analysis, audio_analysis, platform
        )

        feature_array = features.to_array().reshape(1, -1)

        # Try to use trained models, fall back to heuristic
        ctr_prediction = self._predict_ctr(features, feature_array)
        cvr_prediction = self._predict_cvr(features, feature_array)
        winning_prediction = self._predict_winning_probability(features)
        optimal_duration = self._predict_optimal_duration(features, platform)

        # Feature importance (from heuristic weights)
        feature_importance = self._get_feature_importance(features)

        # Improvement suggestions
        suggestions = self._generate_suggestions(features, ctr_prediction, cvr_prediction)

        return {
            "predicted_ctr": round(ctr_prediction["value"], 4),
            "ctr_confidence": {
                "low": round(ctr_prediction["low"], 4),
                "high": round(ctr_prediction["high"], 4),
            },
            "predicted_cvr": round(cvr_prediction["value"], 4),
            "cvr_confidence": {
                "low": round(cvr_prediction["low"], 4),
                "high": round(cvr_prediction["high"], 4),
            },
            "winning_probability": round(winning_prediction, 2),
            "optimal_duration_seconds": optimal_duration,
            "feature_importance": feature_importance,
            "improvement_suggestions": suggestions,
            "model_version": "heuristic_v1",
        }

    def _predict_ctr(self, features: AdFeatures, feature_array: np.ndarray) -> dict:
        """Predict Click-Through Rate."""
        if self._ctr_model is None:
            self._ctr_model = self._load_model("ctr_model")

        if self._ctr_model is not None:
            prediction = float(self._ctr_model.predict(feature_array)[0])
            return {"value": prediction, "low": prediction * 0.8, "high": prediction * 1.2}

        # Heuristic prediction based on known patterns
        base_ctr = 0.015  # 1.5% base

        # Hook quality
        if features.hook_has_text and features.hook_has_person:
            base_ctr *= 1.3
        elif features.hook_has_text or features.hook_has_person:
            base_ctr *= 1.15
        if features.hook_has_question:
            base_ctr *= 1.1

        # Visual quality
        if 0.3 < features.face_closeup_ratio < 0.7:
            base_ctr *= 1.1
        if features.text_overlay_ratio > 0.05:
            base_ctr *= 1.05

        # Content
        if features.has_cta:
            base_ctr *= 1.15
        if features.has_subtitles:
            base_ctr *= 1.05

        # Pacing
        if features.pacing_score > 60:
            base_ctr *= 1.1

        # Duration penalty
        if features.duration_seconds > 60:
            base_ctr *= 0.9
        elif features.duration_seconds < 15:
            base_ctr *= 1.1

        # Sentiment
        if features.sentiment_score > 0.3:
            base_ctr *= 1.05

        return {
            "value": min(base_ctr, 0.10),
            "low": min(base_ctr * 0.7, 0.10),
            "high": min(base_ctr * 1.3, 0.10),
        }

    def _predict_cvr(self, features: AdFeatures, feature_array: np.ndarray) -> dict:
        """Predict Conversion Rate."""
        if self._cvr_model is None:
            self._cvr_model = self._load_model("cvr_model")

        if self._cvr_model is not None:
            prediction = float(self._cvr_model.predict(feature_array)[0])
            return {"value": prediction, "low": prediction * 0.7, "high": prediction * 1.3}

        # Heuristic
        base_cvr = 0.02  # 2% base

        if features.has_cta:
            base_cvr *= 1.3
        if features.cta_keyword_count > 2:
            base_cvr *= 1.1
        if features.product_display_ratio > 0.3:
            base_cvr *= 1.2
        if features.appeal_axis_count >= 2:
            base_cvr *= 1.1
        if features.sentiment_score > 0.3:
            base_cvr *= 1.05

        return {
            "value": min(base_cvr, 0.15),
            "low": min(base_cvr * 0.6, 0.15),
            "high": min(base_cvr * 1.4, 0.15),
        }

    def _predict_winning_probability(self, features: AdFeatures) -> float:
        """Predict probability of being a winning creative (0-100)."""
        score = 50.0  # Base

        # Strong hook
        if features.hook_has_text and features.hook_has_person:
            score += 10
        if features.hook_has_question:
            score += 5

        # Good pacing
        if features.pacing_score > 50:
            score += 5

        # CTA presence
        if features.has_cta:
            score += 10

        # Product visibility
        if features.product_display_ratio > 0.2:
            score += 5

        # Subtitles
        if features.has_subtitles:
            score += 5

        # Narration
        if features.has_narration:
            score += 5

        # Visual quality
        if features.visual_complexity > 0.4:
            score += 3

        # Sentiment
        if features.sentiment_score > 0.2:
            score += 3

        # Duration sweet spot
        if 15 <= features.duration_seconds <= 30:
            score += 5
        elif features.duration_seconds > 90:
            score -= 10

        return min(max(score, 0), 100)

    def _predict_optimal_duration(self, features: AdFeatures, platform: str) -> float:
        """Predict optimal video duration."""
        platform_optimal = {
            "tiktok": 15,
            "instagram": 15,
            "youtube": 30,
            "facebook": 20,
        }

        base = platform_optimal.get(platform.lower(), 25)

        # Adjust based on content complexity
        if features.word_count > 100:
            base = max(base, 30)
        if features.total_scenes > 10:
            base = max(base, 25)

        return float(base)

    def _get_feature_importance(self, features: AdFeatures) -> list[dict]:
        """Get feature importance ranking."""
        importance = [
            {"feature": "hook_quality", "importance": 0.20, "value": "Strong" if features.hook_has_text else "Weak"},
            {"feature": "cta_presence", "importance": 0.15, "value": "Yes" if features.has_cta else "No"},
            {"feature": "pacing_score", "importance": 0.12, "value": f"{features.pacing_score:.0f}/100"},
            {"feature": "face_closeup_ratio", "importance": 0.10, "value": f"{features.face_closeup_ratio:.1%}"},
            {"feature": "product_display", "importance": 0.10, "value": f"{features.product_display_ratio:.1%}"},
            {"feature": "subtitles", "importance": 0.08, "value": "Yes" if features.has_subtitles else "No"},
            {"feature": "sentiment", "importance": 0.08, "value": f"{features.sentiment_score:.2f}"},
            {"feature": "duration", "importance": 0.07, "value": f"{features.duration_seconds:.0f}s"},
            {"feature": "visual_complexity", "importance": 0.05, "value": f"{features.visual_complexity:.2f}"},
            {"feature": "appeal_axes", "importance": 0.05, "value": f"{features.appeal_axis_count}"},
        ]
        return sorted(importance, key=lambda x: -x["importance"])

    def _generate_suggestions(
        self,
        features: AdFeatures,
        ctr_pred: dict,
        cvr_pred: dict,
    ) -> list[dict]:
        """Generate improvement suggestions."""
        suggestions: list[dict] = []

        if not features.hook_has_text:
            suggestions.append({
                "category": "hook",
                "suggestion": "冒頭3秒にインパクトのあるテキストオーバーレイを追加",
                "priority": "high",
                "expected_ctr_lift": "+15-20%",
            })

        if not features.has_cta:
            suggestions.append({
                "category": "cta",
                "suggestion": "明確なCTA（行動喚起）を動画の最後に追加",
                "priority": "high",
                "expected_cvr_lift": "+20-30%",
            })

        if not features.has_subtitles:
            suggestions.append({
                "category": "accessibility",
                "suggestion": "字幕を追加して音声OFFでも内容が伝わるようにする",
                "priority": "medium",
                "expected_ctr_lift": "+5-10%",
            })

        if features.pacing_score < 30:
            suggestions.append({
                "category": "pacing",
                "suggestion": "カット数を増やしてテンポを上げる（目安: 2-3秒/カット）",
                "priority": "medium",
                "expected_ctr_lift": "+10-15%",
            })

        if features.face_closeup_ratio < 0.1:
            suggestions.append({
                "category": "visual",
                "suggestion": "人物の顔が見えるシーンを増やし、共感性を高める",
                "priority": "medium",
                "expected_ctr_lift": "+5-10%",
            })

        if features.duration_seconds > 60:
            suggestions.append({
                "category": "duration",
                "suggestion": f"動画が{features.duration_seconds:.0f}秒と長め。15-30秒版も検討",
                "priority": "low",
                "expected_ctr_lift": "+10-20%",
            })

        return suggestions

    def train_models(self, training_data: list[dict]):
        """Train prediction models on historical data."""
        if not training_data:
            logger.warning("no_training_data")
            return

        try:
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.model_selection import train_test_split

            features_list = []
            ctr_labels = []
            cvr_labels = []

            for data in training_data:
                features = self.feature_engineer.extract_features(
                    data.get("video_analysis", {}),
                    data.get("audio_analysis", {}),
                    data.get("platform", "youtube"),
                )
                features_list.append(features.to_array())
                ctr_labels.append(data.get("actual_ctr", 0))
                cvr_labels.append(data.get("actual_cvr", 0))

            X = np.array(features_list)
            y_ctr = np.array(ctr_labels)
            y_cvr = np.array(cvr_labels)

            # Train CTR model
            X_train, X_test, y_train, y_test = train_test_split(X, y_ctr, test_size=0.2)
            self._ctr_model = GradientBoostingRegressor(n_estimators=100, max_depth=5)
            self._ctr_model.fit(X_train, y_train)
            ctr_score = self._ctr_model.score(X_test, y_test)

            # Train CVR model
            X_train, X_test, y_train, y_test = train_test_split(X, y_cvr, test_size=0.2)
            self._cvr_model = GradientBoostingRegressor(n_estimators=100, max_depth=5)
            self._cvr_model.fit(X_train, y_train)
            cvr_score = self._cvr_model.score(X_test, y_test)

            # Save models
            self.model_dir.mkdir(parents=True, exist_ok=True)
            with open(self.model_dir / "ctr_model.pkl", "wb") as f:
                pickle.dump(self._ctr_model, f)
            with open(self.model_dir / "cvr_model.pkl", "wb") as f:
                pickle.dump(self._cvr_model, f)

            logger.info("models_trained", ctr_r2=ctr_score, cvr_r2=cvr_score)

        except Exception as e:
            logger.error("model_training_failed", error=str(e))
            raise
