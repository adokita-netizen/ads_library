"""Enhanced alert detection - spend surge, LP swap, appeal change, new competitor ads."""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

import structlog
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics
from app.models.landing_page import LandingPage, AppealAxisAnalysis
from app.models.competitive_intel import AlertLog

logger = structlog.get_logger()


class AlertDetector:
    """Detect significant market events and generate alerts."""

    def detect_spend_surges(
        self,
        session: Session,
        threshold_multiplier: float = 3.0,
        min_spend_increase: float = 50000,
    ) -> list[AlertLog]:
        """Detect ads with sudden spend increases (spend surge).

        Triggers when: current period spend > threshold_multiplier * previous period spend
        """
        today = date.today()
        current_start = today - timedelta(days=3)
        previous_start = today - timedelta(days=6)

        # Current period spend per ad
        current = dict(
            session.query(
                AdDailyMetrics.ad_id,
                func.sum(AdDailyMetrics.estimated_spend_increase),
            )
            .filter(AdDailyMetrics.metric_date >= current_start)
            .group_by(AdDailyMetrics.ad_id)
            .all()
        )

        # Previous period spend per ad
        previous = dict(
            session.query(
                AdDailyMetrics.ad_id,
                func.sum(AdDailyMetrics.estimated_spend_increase),
            )
            .filter(
                AdDailyMetrics.metric_date >= previous_start,
                AdDailyMetrics.metric_date < current_start,
            )
            .group_by(AdDailyMetrics.ad_id)
            .all()
        )

        alerts = []
        for ad_id, current_spend in current.items():
            if not current_spend or current_spend < min_spend_increase:
                continue

            prev_spend = previous.get(ad_id, 0) or 0

            # Check surge condition
            if prev_spend > 0:
                multiplier = current_spend / prev_spend
                if multiplier >= threshold_multiplier:
                    # Get ad info
                    ad_info = session.query(
                        AdDailyMetrics.product_name,
                        AdDailyMetrics.advertiser_name,
                        AdDailyMetrics.genre,
                    ).filter(AdDailyMetrics.ad_id == ad_id).first()

                    name = ad_info.product_name or ad_info.advertiser_name or f"Ad #{ad_id}" if ad_info else f"Ad #{ad_id}"
                    change_pct = round((multiplier - 1) * 100, 1)

                    alert = AlertLog(
                        alert_type="spend_surge",
                        severity="high" if multiplier >= 5 else "medium",
                        entity_type="ad",
                        entity_id=ad_id,
                        entity_name=name,
                        title=f"消化額急増: {name} ({change_pct}%増)",
                        description=f"直近3日間の予想消化額が前期間比{multiplier:.1f}倍に急増。¥{round(prev_spend):,} → ¥{round(current_spend):,}",
                        metric_before=round(prev_spend),
                        metric_after=round(current_spend),
                        change_percent=change_pct,
                        context_data={
                            "genre": ad_info.genre if ad_info else None,
                            "period_days": 3,
                            "multiplier": round(multiplier, 2),
                        },
                    )
                    alerts.append(alert)
            elif current_spend >= min_spend_increase * 2:
                # New ad with high spend (no previous data)
                ad_info = session.query(
                    AdDailyMetrics.product_name,
                    AdDailyMetrics.advertiser_name,
                ).filter(AdDailyMetrics.ad_id == ad_id).first()
                name = ad_info.product_name or ad_info.advertiser_name or f"Ad #{ad_id}" if ad_info else f"Ad #{ad_id}"

                alert = AlertLog(
                    alert_type="spend_surge",
                    severity="medium",
                    entity_type="ad",
                    entity_id=ad_id,
                    entity_name=name,
                    title=f"新規高消化: {name} (¥{round(current_spend):,})",
                    description=f"新規出稿で3日間の予想消化額が¥{round(current_spend):,}に到達",
                    metric_before=0,
                    metric_after=round(current_spend),
                    change_percent=100,
                )
                alerts.append(alert)

        return alerts

    def detect_lp_swaps(
        self,
        session: Session,
        days_lookback: int = 7,
    ) -> list[AlertLog]:
        """Detect when an advertiser swaps their LP (遷移先変更).

        Checks if an ad's associated LP URL has changed.
        """
        today = date.today()
        recent_cutoff = today - timedelta(days=days_lookback)

        # Find LPs that were recently updated (URL changed)
        recent_lps = (
            session.query(LandingPage)
            .filter(
                LandingPage.updated_at >= datetime(recent_cutoff.year, recent_cutoff.month, recent_cutoff.day, tzinfo=timezone.utc),
                LandingPage.final_url.isnot(None),
                LandingPage.url != LandingPage.final_url,
            )
            .all()
        )

        alerts = []
        for lp in recent_lps:
            alert = AlertLog(
                alert_type="lp_swap",
                severity="medium",
                entity_type="lp",
                entity_id=lp.id,
                entity_name=lp.advertiser_name or lp.domain,
                title=f"LP変更検出: {lp.advertiser_name or lp.domain}",
                description=f"遷移先LPが変更されました: {lp.domain}",
                context_data={
                    "original_url": lp.url,
                    "new_url": lp.final_url,
                    "genre": lp.genre,
                    "product_name": lp.product_name,
                },
            )
            alerts.append(alert)

        return alerts

    def detect_new_competitor_ads(
        self,
        session: Session,
        watched_advertisers: list[str],
        days_lookback: int = 3,
    ) -> list[AlertLog]:
        """Detect new ads from watched competitors."""
        today = date.today()
        cutoff = today - timedelta(days=days_lookback)

        alerts = []
        for advertiser in watched_advertisers:
            new_ads = (
                session.query(Ad)
                .filter(
                    Ad.advertiser_name.ilike(f"%{advertiser}%"),
                    Ad.created_at >= datetime(cutoff.year, cutoff.month, cutoff.day, tzinfo=timezone.utc),
                )
                .all()
            )

            if new_ads:
                platforms = list(set(str(a.platform) for a in new_ads))
                alert = AlertLog(
                    alert_type="new_competitor_ad",
                    severity="medium",
                    entity_type="advertiser",
                    entity_name=advertiser,
                    title=f"競合新規出稿: {advertiser} ({len(new_ads)}件)",
                    description=f"{advertiser}が{len(new_ads)}件の新しい広告を出稿。媒体: {', '.join(platforms)}",
                    context_data={
                        "new_ads_count": len(new_ads),
                        "platforms": platforms,
                        "ad_ids": [a.id for a in new_ads[:10]],
                    },
                )
                alerts.append(alert)

        return alerts

    def detect_category_trends(
        self,
        session: Session,
        threshold_percent: float = 30,
    ) -> list[AlertLog]:
        """Detect genres with significant spend/volume changes."""
        today = date.today()
        current_start = today - timedelta(days=7)
        previous_start = today - timedelta(days=14)

        # Current period by genre
        current = dict(
            session.query(
                AdDailyMetrics.genre,
                func.sum(AdDailyMetrics.estimated_spend_increase),
            )
            .filter(
                AdDailyMetrics.metric_date >= current_start,
                AdDailyMetrics.genre.isnot(None),
            )
            .group_by(AdDailyMetrics.genre)
            .all()
        )

        # Previous period by genre
        previous = dict(
            session.query(
                AdDailyMetrics.genre,
                func.sum(AdDailyMetrics.estimated_spend_increase),
            )
            .filter(
                AdDailyMetrics.metric_date >= previous_start,
                AdDailyMetrics.metric_date < current_start,
                AdDailyMetrics.genre.isnot(None),
            )
            .group_by(AdDailyMetrics.genre)
            .all()
        )

        alerts = []
        for genre, current_spend in current.items():
            if not genre or not current_spend:
                continue
            prev_spend = previous.get(genre, 0) or 0
            if prev_spend <= 0:
                continue

            change_pct = ((current_spend - prev_spend) / prev_spend) * 100
            if abs(change_pct) >= threshold_percent:
                direction = "急伸" if change_pct > 0 else "縮小"
                alert = AlertLog(
                    alert_type="category_trend",
                    severity="high" if abs(change_pct) >= 50 else "medium",
                    entity_type="genre",
                    entity_name=genre,
                    title=f"ジャンル{direction}: {genre} ({change_pct:+.0f}%)",
                    description=f"{genre}の週間予想消化額が{abs(change_pct):.0f}%{'増加' if change_pct > 0 else '減少'}",
                    metric_before=round(prev_spend),
                    metric_after=round(current_spend),
                    change_percent=round(change_pct, 1),
                    context_data={"period_days": 7},
                )
                alerts.append(alert)

        return alerts

    def run_all_detections(
        self,
        session: Session,
        watched_advertisers: Optional[list[str]] = None,
    ) -> list[AlertLog]:
        """Run all detection algorithms and save alerts."""
        all_alerts = []

        try:
            all_alerts.extend(self.detect_spend_surges(session))
        except Exception as e:
            logger.error("spend_surge_detection_failed", error=str(e))

        try:
            all_alerts.extend(self.detect_lp_swaps(session))
        except Exception as e:
            logger.error("lp_swap_detection_failed", error=str(e))

        if watched_advertisers:
            try:
                all_alerts.extend(self.detect_new_competitor_ads(session, watched_advertisers))
            except Exception as e:
                logger.error("competitor_detection_failed", error=str(e))

        try:
            all_alerts.extend(self.detect_category_trends(session))
        except Exception as e:
            logger.error("category_trend_detection_failed", error=str(e))

        # Save all alerts
        for alert in all_alerts:
            session.add(alert)

        if all_alerts:
            session.commit()
            logger.info("alerts_detected", count=len(all_alerts))

        return all_alerts
