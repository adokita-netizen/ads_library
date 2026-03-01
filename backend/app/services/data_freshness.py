"""A-R2-6: Data freshness scoring and auto-recrawl scheduling."""

import math
from datetime import datetime, timezone

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.ad import Ad

logger = structlog.get_logger()


class DataFreshnessService:
    """Computes freshness scores and schedules auto-recrawl for stale ads."""

    # Freshness decay curve: score = 100 * e^(-days/half_life)
    HALF_LIFE_DAYS = 7.0  # score halves every 7 days

    def __init__(self, session: Session):
        self.session = session

    def compute_freshness_scores(self) -> dict:
        """Compute freshness score for each ad based on last_seen_at.

        Returns summary stats.
        """
        now = datetime.now(timezone.utc)
        ads = self.session.query(Ad).all()
        updated = 0
        scores = []

        for ad in ads:
            last_seen = ad.last_seen_at
            if not last_seen:
                score = 0.0
            else:
                if not last_seen.tzinfo:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                days_since = max(0, (now - last_seen).total_seconds() / 86400)
                score = round(100 * math.exp(-days_since / self.HALF_LIFE_DAYS), 1)

            meta = dict(ad.ad_metadata or {})
            if meta.get("freshness_score") != score:
                meta["freshness_score"] = score
                meta["freshness_updated_at"] = now.isoformat()
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                updated += 1

            scores.append(score)

        if updated > 0:
            self.session.flush()

        avg_score = sum(scores) / len(scores) if scores else 0
        return {
            "total_ads": len(ads),
            "updated": updated,
            "avg_freshness": round(avg_score, 1),
            "stale_count": sum(1 for s in scores if s < 30),
            "fresh_count": sum(1 for s in scores if s >= 70),
        }

    def generate_daily_report(self) -> dict:
        """Generate a daily data quality/freshness report."""
        total = self.session.execute(text("SELECT COUNT(*) FROM ads")).scalar()
        if total == 0:
            return {"total": 0}

        # Field fill rates
        fields = ["title", "category", "destination_url", "platform", "advertiser_name", "creative_type"]
        fill_rates = {}
        for f in fields:
            null_count = self.session.execute(
                text(f"SELECT COUNT(*) FROM ads WHERE {f} IS NULL")
            ).scalar()
            fill_rates[f] = round((total - null_count) / total * 100, 1)

        # Freshness distribution
        freshness = self.session.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE (ad_metadata->>'freshness_score')::float >= 70) as fresh,
                COUNT(*) FILTER (WHERE (ad_metadata->>'freshness_score')::float >= 30
                                  AND (ad_metadata->>'freshness_score')::float < 70) as moderate,
                COUNT(*) FILTER (WHERE (ad_metadata->>'freshness_score')::float < 30) as stale,
                COUNT(*) FILTER (WHERE ad_metadata->>'freshness_score' IS NULL) as unknown
            FROM ads
        """)).fetchone()

        return {
            "total": total,
            "fill_rates": fill_rates,
            "freshness": {
                "fresh": freshness[0],
                "moderate": freshness[1],
                "stale": freshness[2],
                "unknown": freshness[3],
            },
        }

    def schedule_auto_recrawl(self, threshold: float = 30.0) -> int:
        """Mark stale ads for automatic re-crawl by Agent D.

        Sets ad_metadata["auto_recrawl_scheduled"] = True for ads
        with freshness_score below threshold.
        """
        ads = self.session.query(Ad).all()
        scheduled = 0

        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            score = meta.get("freshness_score", 100)

            if score < threshold and not meta.get("auto_recrawl_scheduled"):
                meta["auto_recrawl_scheduled"] = True
                meta["auto_recrawl_reason"] = f"freshness_score={score}"
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                scheduled += 1

        if scheduled > 0:
            self.session.flush()

        logger.info("auto_recrawl_scheduled", count=scheduled, threshold=threshold)
        return scheduled
