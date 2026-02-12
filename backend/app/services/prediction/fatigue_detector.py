"""Ad fatigue detection and lifecycle management."""

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class FatigueAssessment:
    """Ad fatigue assessment result."""

    fatigue_score: float  # 0-100 (100 = completely fatigued)
    days_active: int
    performance_trend: str  # declining, stable, improving
    estimated_remaining_days: int
    recommendation: str
    replacement_urgency: str  # immediate, soon, monitor
    metrics_trend: dict


class FatigueDetector:
    """Detect ad fatigue and predict creative lifecycle."""

    # Typical fatigue thresholds
    FATIGUE_THRESHOLDS = {
        "healthy": (0, 30),
        "early_warning": (30, 60),
        "fatigued": (60, 80),
        "severely_fatigued": (80, 100),
    }

    # Platform-specific average lifecycles (days)
    PLATFORM_LIFECYCLE = {
        "youtube": 30,
        "tiktok": 14,
        "instagram": 21,
        "facebook": 21,
    }

    def assess_fatigue(
        self,
        daily_metrics: list[dict],
        platform: str = "youtube",
    ) -> FatigueAssessment:
        """Assess ad fatigue based on daily performance metrics.

        daily_metrics should be a list of dicts with:
        - date: str
        - impressions: int
        - clicks: int
        - conversions: int
        - ctr: float
        - cvr: float
        - cpa: float (optional)
        """
        if not daily_metrics or len(daily_metrics) < 3:
            return FatigueAssessment(
                fatigue_score=0,
                days_active=len(daily_metrics),
                performance_trend="insufficient_data",
                estimated_remaining_days=self.PLATFORM_LIFECYCLE.get(platform, 21),
                recommendation="データ不足のため、さらに3日以上のデータ収集を推奨",
                replacement_urgency="monitor",
                metrics_trend={},
            )

        days_active = len(daily_metrics)
        platform_lifecycle = self.PLATFORM_LIFECYCLE.get(platform, 21)

        # Calculate trends
        ctr_values = [m.get("ctr", 0) for m in daily_metrics]
        cvr_values = [m.get("cvr", 0) for m in daily_metrics]
        impression_values = [m.get("impressions", 0) for m in daily_metrics]

        ctr_trend = self._calculate_trend(ctr_values)
        cvr_trend = self._calculate_trend(cvr_values)
        impression_trend = self._calculate_trend(impression_values)

        # Calculate fatigue score
        fatigue_score = self._calculate_fatigue_score(
            ctr_trend=ctr_trend,
            cvr_trend=cvr_trend,
            impression_trend=impression_trend,
            days_active=days_active,
            platform_lifecycle=platform_lifecycle,
        )

        # Determine performance trend
        performance_trend = self._determine_trend(ctr_trend, cvr_trend)

        # Estimate remaining days
        estimated_remaining = self._estimate_remaining_days(
            fatigue_score, ctr_trend, platform_lifecycle
        )

        # Generate recommendation
        recommendation, urgency = self._generate_recommendation(
            fatigue_score, performance_trend, estimated_remaining
        )

        # Metrics trend details
        metrics_trend = {
            "ctr_trend_slope": round(ctr_trend, 6),
            "cvr_trend_slope": round(cvr_trend, 6),
            "impression_trend_slope": round(impression_trend, 2),
            "ctr_7d_avg": round(float(np.mean(ctr_values[-7:])), 4) if len(ctr_values) >= 7 else round(float(np.mean(ctr_values)), 4),
            "ctr_first_3d_avg": round(float(np.mean(ctr_values[:3])), 4),
            "ctr_change_pct": round(self._percentage_change(ctr_values[:3], ctr_values[-3:]), 1),
            "cvr_change_pct": round(self._percentage_change(cvr_values[:3], cvr_values[-3:]), 1),
        }

        return FatigueAssessment(
            fatigue_score=round(fatigue_score, 1),
            days_active=days_active,
            performance_trend=performance_trend,
            estimated_remaining_days=estimated_remaining,
            recommendation=recommendation,
            replacement_urgency=urgency,
            metrics_trend=metrics_trend,
        )

    def _calculate_trend(self, values: list[float]) -> float:
        """Calculate linear trend slope using least squares."""
        if len(values) < 2:
            return 0.0

        x = np.arange(len(values), dtype=np.float64)
        y = np.array(values, dtype=np.float64)

        # Remove zeros
        mask = y > 0
        if np.sum(mask) < 2:
            return 0.0

        x_clean = x[mask]
        y_clean = y[mask]

        # Linear regression
        n = len(x_clean)
        sum_x = np.sum(x_clean)
        sum_y = np.sum(y_clean)
        sum_xy = np.sum(x_clean * y_clean)
        sum_x2 = np.sum(x_clean ** 2)

        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return float(slope)

    def _calculate_fatigue_score(
        self,
        ctr_trend: float,
        cvr_trend: float,
        impression_trend: float,
        days_active: int,
        platform_lifecycle: int,
    ) -> float:
        """Calculate composite fatigue score (0-100)."""
        score = 0.0

        # Age factor (0-40 points)
        age_ratio = days_active / platform_lifecycle
        age_score = min(age_ratio * 40, 40)
        score += age_score

        # CTR decline factor (0-30 points)
        if ctr_trend < 0:
            ctr_decline_score = min(abs(ctr_trend) * 10000, 30)
            score += ctr_decline_score

        # CVR decline factor (0-20 points)
        if cvr_trend < 0:
            cvr_decline_score = min(abs(cvr_trend) * 8000, 20)
            score += cvr_decline_score

        # Impression decline factor (0-10 points)
        if impression_trend < 0:
            score += min(abs(impression_trend) / 100, 10)

        return min(score, 100)

    def _determine_trend(self, ctr_trend: float, cvr_trend: float) -> str:
        """Determine overall performance trend."""
        if ctr_trend < -0.0001 and cvr_trend < -0.0001:
            return "declining"
        elif ctr_trend > 0.0001 and cvr_trend > 0.0001:
            return "improving"
        elif ctr_trend < -0.0005:
            return "declining"
        else:
            return "stable"

    def _estimate_remaining_days(
        self,
        fatigue_score: float,
        ctr_trend: float,
        platform_lifecycle: int,
    ) -> int:
        """Estimate remaining effective days."""
        if fatigue_score >= 80:
            return 0
        if fatigue_score >= 60:
            return max(1, int(platform_lifecycle * 0.1))
        if fatigue_score >= 30:
            return max(3, int(platform_lifecycle * 0.3))

        remaining_ratio = 1.0 - (fatigue_score / 100)
        return max(1, int(platform_lifecycle * remaining_ratio))

    def _percentage_change(self, early: list[float], recent: list[float]) -> float:
        """Calculate percentage change between two periods."""
        early_avg = np.mean(early) if early else 0
        recent_avg = np.mean(recent) if recent else 0

        if early_avg == 0:
            return 0.0

        return float((recent_avg - early_avg) / early_avg * 100)

    def _generate_recommendation(
        self,
        fatigue_score: float,
        trend: str,
        remaining_days: int,
    ) -> tuple[str, str]:
        """Generate actionable recommendation."""
        if fatigue_score >= 80:
            return (
                "クリエイティブの疲労が深刻です。即座に新しいクリエイティブへの差し替えを推奨します。"
                "現在のクリエイティブの勝ちパターンを分析し、新バリエーションを制作してください。",
                "immediate",
            )
        elif fatigue_score >= 60:
            return (
                f"クリエイティブの効果が低下しています。残り約{remaining_days}日以内に"
                "新しいクリエイティブの準備を開始してください。"
                "A/Bテスト用のバリエーションを3-5案用意することを推奨します。",
                "soon",
            )
        elif fatigue_score >= 30:
            return (
                "軽微な効果低下の兆候があります。パフォーマンスを継続的にモニタリングし、"
                "次のクリエイティブの企画を並行して進めてください。",
                "monitor",
            )
        else:
            if trend == "improving":
                return "パフォーマンスは良好で改善傾向にあります。現状のクリエイティブを維持してください。", "monitor"
            return "パフォーマンスは安定しています。定期的なモニタリングを継続してください。", "monitor"

    def batch_assess(
        self,
        ads_metrics: list[dict],
        platform: str = "youtube",
    ) -> list[dict]:
        """Assess fatigue for multiple ads at once."""
        results = []
        for ad_data in ads_metrics:
            ad_id = ad_data.get("ad_id")
            daily_metrics = ad_data.get("daily_metrics", [])
            assessment = self.assess_fatigue(daily_metrics, platform)

            results.append({
                "ad_id": ad_id,
                "fatigue_score": assessment.fatigue_score,
                "days_active": assessment.days_active,
                "performance_trend": assessment.performance_trend,
                "estimated_remaining_days": assessment.estimated_remaining_days,
                "replacement_urgency": assessment.replacement_urgency,
                "recommendation": assessment.recommendation,
            })

        # Sort by fatigue score (most fatigued first)
        results.sort(key=lambda x: -x["fatigue_score"])
        return results
