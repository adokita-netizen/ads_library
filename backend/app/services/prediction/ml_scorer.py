"""ML-based hit scoring service with lightweight model/version management."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import structlog
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics, ProductRanking
from app.services.ranking.ranking_service import compute_hit_score

logger = structlog.get_logger()

try:
    from xgboost import XGBRegressor
except Exception:  # pragma: no cover - fallback when xgboost unavailable
    XGBRegressor = None


class MLHitScorer:
    """In-process ML scorer for hit score prediction."""

    _model: Any = None
    _model_version: str = "ml-hit-v0"
    _trained_at: datetime | None = None
    _feature_names: list[str] = [
        "days_running",
        "is_still_running",
        "has_video",
        "has_image",
        "has_thumbnail",
        "estimated_total_spend_jpy",
        "views_7d",
        "likes_7d",
        "comments_7d",
    ]

    def train_if_needed(self, session: Session, *, min_rows: int = 50) -> dict:
        now = datetime.now(timezone.utc)
        if self._model is not None and self._trained_at and (now - self._trained_at) < timedelta(hours=24):
            return {
                "trained": False,
                "reason": "fresh_model_exists",
                "model_version": self._model_version,
            }

        rows = (
            session.query(ProductRanking, Ad)
            .join(Ad, Ad.id == ProductRanking.ad_id)
            .filter(ProductRanking.hit_score.isnot(None))
            .order_by(ProductRanking.updated_at.desc())
            .limit(5000)
            .all()
        )
        if len(rows) < min_rows:
            return {
                "trained": False,
                "reason": "insufficient_rows",
                "row_count": len(rows),
                "model_version": self._model_version,
            }

        x, y = [], []
        for ranking, ad in rows:
            x.append(self._extract_features(session=session, ad=ad))
            y.append(float(ranking.hit_score or 0.0))

        x_arr = np.array(x, dtype=np.float32)
        y_arr = np.array(y, dtype=np.float32)

        if XGBRegressor is not None:
            model = XGBRegressor(
                n_estimators=150,
                max_depth=4,
                learning_rate=0.08,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="reg:squarederror",
                random_state=42,
            )
        else:
            from sklearn.ensemble import GradientBoostingRegressor

            model = GradientBoostingRegressor(random_state=42)

        model.fit(x_arr, y_arr)
        self._model = model
        self._trained_at = now
        self._model_version = f"ml-hit-{now.strftime('%Y%m%d%H%M%S')}"
        logger.info("ml_hit_scorer_trained", version=self._model_version, rows=len(rows))
        return {
            "trained": True,
            "row_count": len(rows),
            "model_version": self._model_version,
        }

    def score_ad(
        self,
        session: Session,
        *,
        ad_id: int,
        user_id: int | None,
        ab_mode: str = "auto",
    ) -> dict:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            raise ValueError("Ad not found")

        metrics = (
            session.query(AdDailyMetrics)
            .filter(AdDailyMetrics.ad_id == ad_id)
            .order_by(AdDailyMetrics.metric_date.asc())
            .all()
        )
        rule_score, rule_hit, rule_level, _ = compute_hit_score(ad=ad, metrics=metrics, genre_stats={})

        train_result = self.train_if_needed(session)
        ml_score = None
        ml_ready = self._model is not None
        if ml_ready:
            feats = np.array([self._extract_features(session=session, ad=ad)], dtype=np.float32)
            ml_score = float(np.clip(self._model.predict(feats)[0], 0.0, 100.0))

        arm = self._select_arm(ad_id=ad_id, user_id=user_id, ab_mode=ab_mode, ml_ready=ml_ready)
        selected_score = ml_score if arm == "ml" and ml_score is not None else float(rule_score)
        selected_score = round(float(selected_score), 1)

        return {
            "ad_id": ad_id,
            "ab_mode": ab_mode,
            "ab_arm": arm,
            "model_version": self._model_version if ml_ready else "rule-only",
            "rule_score": round(float(rule_score), 1),
            "ml_score": round(float(ml_score), 1) if ml_score is not None else None,
            "selected_score": selected_score,
            "rule_hit": bool(rule_hit),
            "rule_level": rule_level,
            "trained_now": bool(train_result.get("trained", False)),
            "train_info": train_result,
        }

    def _extract_features(self, *, session: Session, ad: Ad) -> list[float]:
        meta = ad.ad_metadata or {}
        days_running = float(meta.get("days_running") or 0.0)
        is_still_running = 1.0 if bool(meta.get("is_still_running", ad.last_seen_at is None)) else 0.0
        has_video = 1.0 if bool(ad.video_url) else 0.0
        has_image = 1.0 if bool(ad.image_url) else 0.0
        has_thumb = 1.0 if bool(ad.thumbnail_url) else 0.0
        spend = float(meta.get("estimated_total_spend_jpy") or ad.spend or 0.0)

        recent = (
            session.query(AdDailyMetrics)
            .filter(AdDailyMetrics.ad_id == ad.id)
            .order_by(AdDailyMetrics.metric_date.desc())
            .limit(7)
            .all()
        )
        views_7d = float(sum(float(getattr(r, "view_count_increase", 0) or 0) for r in recent))
        likes_7d = float(sum(float(getattr(r, "like_count", 0) or 0) for r in recent))
        comments_7d = float(sum(float(getattr(r, "comment_count", 0) or 0) for r in recent))

        return [
            days_running,
            is_still_running,
            has_video,
            has_image,
            has_thumb,
            spend,
            views_7d,
            likes_7d,
            comments_7d,
        ]

    @staticmethod
    def _select_arm(*, ad_id: int, user_id: int | None, ab_mode: str, ml_ready: bool) -> str:
        mode = (ab_mode or "auto").lower()
        if mode == "rule":
            return "rule"
        if mode == "ml" and ml_ready:
            return "ml"
        if mode == "ml" and not ml_ready:
            return "rule"

        key = f"{user_id or 0}:{ad_id}"
        bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100
        if ml_ready and bucket < 50:
            return "ml"
        return "rule"
