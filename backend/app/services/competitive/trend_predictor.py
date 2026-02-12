"""Advanced trend/hit detection with velocity curves, genre-specific thresholds, and S-curve modeling."""

import math
from datetime import date, timedelta
from typing import Optional

import structlog
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics
from app.models.competitive_intel import TrendPrediction

logger = structlog.get_logger()


class TrendPredictor:
    """Predict trending/hit ads with velocity analysis and genre-aware thresholds."""

    def compute_velocity_metrics(
        self,
        session: Session,
        ad_id: int,
        as_of_date: Optional[date] = None,
    ) -> Optional[dict]:
        """Compute velocity and acceleration metrics for an ad."""
        as_of = as_of_date or date.today()

        # Get metrics for last 7+ days
        metrics = (
            session.query(AdDailyMetrics)
            .filter(
                AdDailyMetrics.ad_id == ad_id,
                AdDailyMetrics.metric_date <= as_of,
                AdDailyMetrics.metric_date >= as_of - timedelta(days=14),
            )
            .order_by(AdDailyMetrics.metric_date.desc())
            .all()
        )

        if not metrics:
            return None

        # Calculate velocities for different windows
        def avg_daily(data, days):
            subset = [m for m in data if m.metric_date >= as_of - timedelta(days=days)]
            if not subset:
                return 0
            return sum(m.view_count_increase for m in subset) / max(len(subset), 1)

        def avg_spend_daily(data, days):
            subset = [m for m in data if m.metric_date >= as_of - timedelta(days=days)]
            if not subset:
                return 0
            return sum(m.estimated_spend_increase for m in subset) / max(len(subset), 1)

        view_vel_1d = avg_daily(metrics, 1)
        view_vel_3d = avg_daily(metrics, 3)
        view_vel_7d = avg_daily(metrics, 7)

        spend_vel_1d = avg_spend_daily(metrics, 1)
        spend_vel_3d = avg_spend_daily(metrics, 3)
        spend_vel_7d = avg_spend_daily(metrics, 7)

        # Acceleration: rate of change of velocity
        view_acceleration = (view_vel_1d - view_vel_7d) / max(view_vel_7d, 1)
        spend_acceleration = (spend_vel_1d - spend_vel_7d) / max(spend_vel_7d, 1)

        # Days since first seen
        first_metric = metrics[-1] if metrics else None
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        first_seen = ad.first_seen_at.date() if ad and ad.first_seen_at else (first_metric.metric_date if first_metric else as_of)
        days_active = (as_of - first_seen).days

        # Growth phase detection (S-curve)
        growth_phase = self._detect_growth_phase(view_vel_1d, view_vel_3d, view_vel_7d, view_acceleration, days_active)

        return {
            "ad_id": ad_id,
            "view_velocity_1d": round(view_vel_1d, 1),
            "view_velocity_3d": round(view_vel_3d, 1),
            "view_velocity_7d": round(view_vel_7d, 1),
            "view_acceleration": round(view_acceleration, 4),
            "spend_velocity_1d": round(spend_vel_1d, 2),
            "spend_velocity_3d": round(spend_vel_3d, 2),
            "spend_velocity_7d": round(spend_vel_7d, 2),
            "spend_acceleration": round(spend_acceleration, 4),
            "days_since_first_seen": days_active,
            "growth_phase": growth_phase,
            "genre": metrics[0].genre if metrics else None,
            "platform": metrics[0].platform if metrics else None,
        }

    def _detect_growth_phase(
        self,
        vel_1d: float,
        vel_3d: float,
        vel_7d: float,
        acceleration: float,
        days_active: int,
    ) -> str:
        """Detect which phase of the S-curve an ad is in."""
        if days_active <= 3:
            return "launch"
        elif acceleration > 0.3 and vel_1d > vel_7d:
            return "growth"
        elif -0.1 <= acceleration <= 0.1 and vel_1d > 0:
            return "peak"
        elif acceleration < -0.1 and vel_1d > vel_7d * 0.5:
            return "plateau"
        else:
            return "decline"

    def predict_hits(
        self,
        session: Session,
        as_of_date: Optional[date] = None,
        limit: int = 50,
    ) -> list[TrendPrediction]:
        """Predict which ads will become hits using velocity and genre-aware analysis."""
        as_of = as_of_date or date.today()

        # Get recently active ads (last 7 days)
        active_ads = (
            session.query(AdDailyMetrics.ad_id)
            .filter(AdDailyMetrics.metric_date >= as_of - timedelta(days=7))
            .group_by(AdDailyMetrics.ad_id)
            .all()
        )

        # Compute genre averages for relative scoring
        genre_avgs = dict(
            session.query(
                AdDailyMetrics.genre,
                func.avg(AdDailyMetrics.view_count_increase),
            )
            .filter(
                AdDailyMetrics.metric_date >= as_of - timedelta(days=7),
                AdDailyMetrics.genre.isnot(None),
            )
            .group_by(AdDailyMetrics.genre)
            .all()
        )

        predictions = []
        for (ad_id,) in active_ads:
            velocity = self.compute_velocity_metrics(session, ad_id, as_of)
            if not velocity:
                continue

            genre = velocity.get("genre")
            genre_avg = genre_avgs.get(genre, 0) or 1

            # Genre-relative percentile
            genre_percentile = min(100, (velocity["view_velocity_7d"] / max(genre_avg, 1)) * 50)

            # Hit probability calculation
            hit_prob = self._calculate_hit_probability(velocity, genre_percentile)

            # Momentum score (comprehensive)
            momentum = self._calculate_momentum_score(velocity, genre_percentile)

            # Predicted peak spend (rough estimate)
            predicted_peak = velocity["spend_velocity_1d"] * 30 if velocity["growth_phase"] in ("launch", "growth") else None

            prediction = TrendPrediction(
                ad_id=ad_id,
                prediction_date=as_of,
                view_velocity_1d=velocity["view_velocity_1d"],
                view_velocity_3d=velocity["view_velocity_3d"],
                view_velocity_7d=velocity["view_velocity_7d"],
                view_acceleration=velocity["view_acceleration"],
                spend_velocity_1d=velocity["spend_velocity_1d"],
                spend_velocity_3d=velocity["spend_velocity_3d"],
                spend_velocity_7d=velocity["spend_velocity_7d"],
                spend_acceleration=velocity["spend_acceleration"],
                growth_phase=velocity["growth_phase"],
                days_since_first_seen=velocity["days_since_first_seen"],
                genre=genre,
                genre_avg_velocity=round(genre_avg, 1) if genre_avg else None,
                genre_percentile=round(genre_percentile, 1),
                predicted_hit=hit_prob >= 0.6,
                hit_probability=round(hit_prob, 3),
                predicted_peak_spend=round(predicted_peak) if predicted_peak else None,
                momentum_score=round(momentum, 1),
            )
            predictions.append(prediction)

        # Sort by momentum score
        predictions.sort(key=lambda p: -(p.momentum_score or 0))
        return predictions[:limit]

    def _calculate_hit_probability(self, velocity: dict, genre_percentile: float) -> float:
        """Calculate probability of an ad becoming a hit."""
        score = 0.0

        # Velocity signals (40% weight)
        if velocity["view_velocity_1d"] > 10000:
            score += 0.15
        elif velocity["view_velocity_1d"] > 5000:
            score += 0.10
        elif velocity["view_velocity_1d"] > 1000:
            score += 0.05

        if velocity["spend_velocity_1d"] > 100000:
            score += 0.15
        elif velocity["spend_velocity_1d"] > 50000:
            score += 0.10

        # Acceleration signals (25% weight)
        if velocity["view_acceleration"] > 0.5:
            score += 0.15
        elif velocity["view_acceleration"] > 0.2:
            score += 0.10

        if velocity["spend_acceleration"] > 0.3:
            score += 0.10

        # Growth phase (15% weight)
        phase_scores = {"launch": 0.05, "growth": 0.15, "peak": 0.10, "plateau": 0.03, "decline": 0.00}
        score += phase_scores.get(velocity["growth_phase"], 0)

        # Genre-relative performance (20% weight)
        if genre_percentile >= 90:
            score += 0.20
        elif genre_percentile >= 75:
            score += 0.15
        elif genre_percentile >= 50:
            score += 0.08

        return min(score, 1.0)

    def _calculate_momentum_score(self, velocity: dict, genre_percentile: float) -> float:
        """Calculate comprehensive momentum score (0-100)."""
        score = 0.0

        # View velocity component (30 points max)
        vel_7d = velocity["view_velocity_7d"]
        if vel_7d > 50000:
            score += 30
        elif vel_7d > 10000:
            score += 20
        elif vel_7d > 5000:
            score += 15
        elif vel_7d > 1000:
            score += 8

        # Spend velocity component (25 points max)
        spend_7d = velocity["spend_velocity_7d"]
        if spend_7d > 200000:
            score += 25
        elif spend_7d > 100000:
            score += 18
        elif spend_7d > 50000:
            score += 12
        elif spend_7d > 10000:
            score += 5

        # Acceleration component (20 points max)
        acc = velocity["view_acceleration"]
        if acc > 0.5:
            score += 20
        elif acc > 0.2:
            score += 14
        elif acc > 0:
            score += 7
        elif acc < -0.3:
            score -= 5

        # Genre-relative performance (15 points max)
        score += min(15, genre_percentile * 0.15)

        # Growth phase bonus (10 points max)
        phase_bonus = {"launch": 3, "growth": 10, "peak": 7, "plateau": 2, "decline": 0}
        score += phase_bonus.get(velocity["growth_phase"], 0)

        return max(0, min(100, score))

    def get_early_hit_candidates(
        self,
        session: Session,
        max_days_active: int = 7,
        min_momentum: float = 40,
    ) -> list[dict]:
        """Find ads in their first week that show hit potential (early detection)."""
        as_of = date.today()

        predictions = self.predict_hits(session, as_of, limit=200)

        candidates = []
        for p in predictions:
            if (p.days_since_first_seen or 99) <= max_days_active and (p.momentum_score or 0) >= min_momentum:
                candidates.append({
                    "ad_id": p.ad_id,
                    "days_active": p.days_since_first_seen,
                    "growth_phase": p.growth_phase,
                    "momentum_score": p.momentum_score,
                    "hit_probability": p.hit_probability,
                    "view_velocity_1d": p.view_velocity_1d,
                    "spend_velocity_1d": p.spend_velocity_1d,
                    "genre": p.genre,
                    "genre_percentile": p.genre_percentile,
                })

        return candidates
