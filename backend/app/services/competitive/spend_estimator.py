"""Spend estimation service with P50/P90 confidence ranges and CPM calibration."""

import math
from datetime import date, timedelta
from typing import Optional

import structlog
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ad_metrics import AdDailyMetrics
from app.models.competitive_intel import SpendEstimate, CPMCalibration

logger = structlog.get_logger()

# Platform average CPMs (JPY per 1000 impressions) - industry research baseline
PLATFORM_CPM_DEFAULTS = {
    "youtube": {"avg": 400, "min": 200, "max": 800, "std": 150},
    "tiktok": {"avg": 300, "min": 100, "max": 600, "std": 120},
    "instagram": {"avg": 500, "min": 250, "max": 1000, "std": 180},
    "facebook": {"avg": 450, "min": 200, "max": 900, "std": 170},
    "x_twitter": {"avg": 350, "min": 150, "max": 700, "std": 140},
    "line": {"avg": 380, "min": 180, "max": 750, "std": 150},
    "yahoo": {"avg": 420, "min": 200, "max": 850, "std": 160},
    "pinterest": {"avg": 320, "min": 150, "max": 650, "std": 130},
    "smartnews": {"avg": 350, "min": 150, "max": 700, "std": 140},
    "google_ads": {"avg": 450, "min": 200, "max": 1000, "std": 180},
    "gunosy": {"avg": 300, "min": 120, "max": 600, "std": 120},
}

# Genre-specific CPM multipliers (relative to platform average)
GENRE_CPM_MULTIPLIERS = {
    "美容・コスメ": 1.3,
    "健康食品": 1.2,
    "ヘアケア": 1.15,
    "ダイエット": 1.25,
    "スキンケア": 1.3,
    "サプリ": 1.1,
    "金融": 1.5,
    "教育": 0.9,
    "ゲーム": 0.8,
    "不動産": 1.4,
}

# Seasonal factors (month → multiplier)
SEASONAL_FACTORS = {
    1: 0.85, 2: 0.90, 3: 1.05, 4: 1.00, 5: 0.95, 6: 1.00,
    7: 0.95, 8: 0.90, 9: 1.05, 10: 1.10, 11: 1.20, 12: 1.30,
}


class SpendEstimator:
    """Estimate ad spend with confidence ranges using CPM model."""

    def estimate_spend(
        self,
        session: Session,
        ad_id: int,
        view_count_increase: int,
        platform: str,
        genre: Optional[str] = None,
        target_date: Optional[date] = None,
        user_id: Optional[int] = None,
    ) -> SpendEstimate:
        """Estimate spend with P10-P90 confidence intervals."""
        target_date = target_date or date.today()

        # 1. Get platform CPM distribution
        platform_key = platform.lower().replace(" ", "_")
        cpm_dist = PLATFORM_CPM_DEFAULTS.get(platform_key, PLATFORM_CPM_DEFAULTS["youtube"])

        cpm_avg = cpm_dist["avg"]
        cpm_std = cpm_dist["std"]

        # 2. Apply genre multiplier
        genre_mult = GENRE_CPM_MULTIPLIERS.get(genre, 1.0) if genre else 1.0
        cpm_avg *= genre_mult
        cpm_std *= genre_mult

        # 3. Apply seasonal factor
        seasonal = SEASONAL_FACTORS.get(target_date.month, 1.0)
        cpm_avg *= seasonal

        # 4. Check user calibration data
        cpm_user = None
        if user_id:
            calib = session.query(CPMCalibration).filter(
                CPMCalibration.user_id == user_id,
                CPMCalibration.platform == platform_key,
            )
            if genre:
                calib = calib.filter(CPMCalibration.genre == genre)
            calib = calib.order_by(CPMCalibration.created_at.desc()).first()

            if calib and calib.actual_cpm:
                cpm_user = calib.actual_cpm
                # Blend: 70% user data, 30% market avg
                cpm_avg = cpm_user * 0.7 + cpm_avg * 0.3
                cpm_std *= 0.6  # Tighter confidence with calibration

        # 5. Calculate view-based impressions estimate
        # Assumption: view_count ≈ impressions for video platforms
        impressions = view_count_increase

        # 6. Calculate spend at various percentiles
        spend_point = (impressions / 1000) * cpm_avg

        # Log-normal distribution for spend (always positive, right-skewed)
        if spend_point > 0:
            log_mean = math.log(max(spend_point, 1))
            log_std = cpm_std / cpm_avg * 0.8  # Convert CPM variance to log-space

            spend_p10 = math.exp(log_mean - 1.28 * log_std)
            spend_p25 = math.exp(log_mean - 0.67 * log_std)
            spend_p50 = math.exp(log_mean)
            spend_p75 = math.exp(log_mean + 0.67 * log_std)
            spend_p90 = math.exp(log_mean + 1.28 * log_std)
        else:
            spend_p10 = spend_p25 = spend_p50 = spend_p75 = spend_p90 = 0

        # 7. Confidence level (higher with calibration, lower without)
        confidence = 0.7 if cpm_user else 0.45
        method = "calibrated" if cpm_user else "cpm_model"

        estimate = SpendEstimate(
            ad_id=ad_id,
            estimate_date=target_date,
            view_count=0,
            view_count_increase=view_count_increase,
            platform=platform_key,
            genre=genre,
            cpm_platform_avg=cpm_dist["avg"],
            cpm_genre_avg=cpm_avg / seasonal,  # pre-seasonal
            cpm_seasonal_factor=seasonal,
            cpm_user_calibrated=cpm_user,
            estimated_spend=round(spend_point, 2),
            spend_p10=round(spend_p10, 2),
            spend_p25=round(spend_p25, 2),
            spend_p50=round(spend_p50, 2),
            spend_p75=round(spend_p75, 2),
            spend_p90=round(spend_p90, 2),
            estimation_method=method,
            confidence_level=confidence,
        )

        return estimate

    def batch_estimate(
        self,
        session: Session,
        period_start: date,
        period_end: date,
        user_id: Optional[int] = None,
    ) -> list[SpendEstimate]:
        """Batch estimate spend for all ads with metrics in period."""
        metrics = (
            session.query(
                AdDailyMetrics.ad_id,
                func.sum(AdDailyMetrics.view_count_increase).label("total_views"),
                func.max(AdDailyMetrics.platform).label("platform"),
                func.max(AdDailyMetrics.genre).label("genre"),
            )
            .filter(
                AdDailyMetrics.metric_date >= period_start,
                AdDailyMetrics.metric_date <= period_end,
            )
            .group_by(AdDailyMetrics.ad_id)
            .all()
        )

        estimates = []
        for m in metrics:
            est = self.estimate_spend(
                session,
                ad_id=m.ad_id,
                view_count_increase=m.total_views or 0,
                platform=m.platform or "youtube",
                genre=m.genre,
                target_date=period_end,
                user_id=user_id,
            )
            estimates.append(est)

        return estimates

    def save_calibration(
        self,
        session: Session,
        user_id: int,
        platform: str,
        actual_cpm: float,
        genre: Optional[str] = None,
        actual_cpv: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> CPMCalibration:
        """Save user CPM calibration data."""
        calib = CPMCalibration(
            user_id=user_id,
            platform=platform.lower(),
            genre=genre,
            actual_cpm=actual_cpm,
            actual_cpv=actual_cpv,
            notes=notes,
        )
        session.add(calib)
        session.commit()
        session.refresh(calib)
        return calib
