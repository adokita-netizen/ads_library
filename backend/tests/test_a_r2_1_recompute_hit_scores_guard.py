from datetime import date, datetime, timezone

from app.models.ad import Ad, AdCategoryEnum, AdPlatformEnum, AdStatusEnum
from app.models.ad_metrics import AdDailyMetrics
from app.services.ranking.ranking_service import compute_genre_stats


def test_compute_genre_stats_coerces_string_audience_values(session):
    ad = Ad(
        external_id="r2-audience-string",
        title="test ad",
        platform=AdPlatformEnum.FACEBOOK,
        category=AdCategoryEnum.BEAUTY,
        status=AdStatusEnum.PENDING,
        advertiser_name="tester",
        ad_metadata={"estimated_audience_max": "12000"},
        updated_at=datetime.now(timezone.utc),
    )
    session.add(ad)
    session.flush()
    session.add(
        AdDailyMetrics(
            ad_id=ad.id,
            metric_date=date(2026, 3, 7),
            genre="beauty",
            estimated_spend_increase=1500,
        )
    )
    session.commit()

    stats = compute_genre_stats(session, date(2026, 3, 1), date(2026, 3, 8))

    assert stats["beauty"]["ad_count"] == 1
    assert stats["beauty"]["max_audience"] == 12000.0
