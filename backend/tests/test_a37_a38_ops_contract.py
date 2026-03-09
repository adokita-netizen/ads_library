from datetime import datetime, timedelta, timezone

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule
from app.services.alert_engine import AlertEngine, seed_default_rules
from app.services.data_freshness import DataFreshnessService


def _mk_ad(external_id: str, *, metadata: dict | None = None, last_seen_at: datetime | None = None) -> Ad:
    return Ad(
        external_id=external_id,
        title=external_id,
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        advertiser_name="tester",
        ad_metadata=metadata or {},
        last_seen_at=last_seen_at,
    )


def test_a37_seed_default_rules_adds_score_change_rule(session):
    count = seed_default_rules(session)
    assert count == 4
    rules = session.query(AlertRule).order_by(AlertRule.id.asc()).all()
    assert {rule.condition_type for rule in rules} >= {
        "score_threshold",
        "new_hit",
        "data_quality",
        "score_change",
    }


def test_a37_alert_engine_emits_score_change_alert(session):
    AlertRule.__table__.create(bind=session.bind, checkfirst=True)
    AlertHistory.__table__.create(bind=session.bind, checkfirst=True)
    session.add(
        AlertRule(
            name="score shift",
            condition_type="score_change",
            operator="change_gt",
            threshold=10.0,
            cooldown_minutes=0,
            notification_channel="in_app",
        )
    )
    session.add(
        _mk_ad(
            "score-change",
            metadata={
                "latest_hit_score": 82.4,
                "previous_hit_score": 60.0,
                "score_delta": 22.4,
                "score_updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    )
    session.commit()

    created = AlertEngine(session).evaluate_all_rules()
    session.commit()

    assert created == 1
    alert = session.query(AlertHistory).one()
    assert alert.alert_type == "score_change"
    assert alert.new_value == 82.4
    assert alert.old_value == 60.0


def test_a38_data_freshness_scores_and_flags_stale_ads(session):
    fresh_seen = datetime.now(timezone.utc) - timedelta(hours=12)
    stale_seen = datetime.now(timezone.utc) - timedelta(days=21)
    session.add_all(
        [
            _mk_ad("fresh", metadata={}, last_seen_at=fresh_seen),
            _mk_ad("stale", metadata={}, last_seen_at=stale_seen),
        ]
    )
    session.commit()

    service = DataFreshnessService(session)
    summary = service.compute_freshness_scores()
    scheduled = service.schedule_auto_recrawl()
    session.commit()

    fresh = session.query(Ad).filter(Ad.external_id == "fresh").one()
    stale = session.query(Ad).filter(Ad.external_id == "stale").one()

    assert summary["total_ads"] == 2
    assert fresh.ad_metadata["freshness_score"] > stale.ad_metadata["freshness_score"]
    assert scheduled == 1
    assert stale.ad_metadata["auto_recrawl_scheduled"] is True

