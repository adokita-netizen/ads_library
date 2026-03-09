from datetime import date

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.tasks import metrics_tasks


def _mk_ad(external_id: str, title: str, advertiser_name: str = "広告主", metadata: dict | None = None) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        advertiser_name=advertiser_name,
        platform=AdPlatformEnum.FACEBOOK,
        status=AdStatusEnum.PENDING,
        ad_metadata=metadata or {},
    )


def test_a44_build_false_negative_hunt_report_tracks_daily_diff_and_weekly_recovery(session, monkeypatch, tmp_path):
    monkeypatch.setattr(metrics_tasks, "_FALSE_NEGATIVE_HUNT_REPORTS_FILE", tmp_path / "false_negative_hunt_reports.json")

    missed = _mk_ad(
        "a44_1",
        "新NISAで資産運用を始める",
        advertiser_name="Fin Corp",
        metadata={"topic_label": "education"},
    )
    same_adv_ok = _mk_ad(
        "a44_2",
        "NISA無料セミナー",
        advertiser_name="Fin Corp",
        metadata={"topic_label": "finance"},
    )
    session.add_all([missed, same_adv_ok])
    session.commit()

    monkeypatch.setattr(
        metrics_tasks,
        "queue_false_negative_recrawls",
        lambda report, max_queries=8: {"queued_queries": ["新NISA", "finance"], "queued_count": 2, "status": "queued"},
    )

    first = metrics_tasks.build_false_negative_hunt_report(
        session,
        target_date=date(2026, 3, 8),
        false_negative_limit=10,
        queue_recrawls=True,
    )
    assert first["summary"]["candidate_count"] >= 1
    assert first["summary"]["newly_detected_count"] >= 1
    assert first["queue_result"]["queued_count"] == 2
    assert "previous_day_diff" in first["daily_candidates"][0]["rule_hits"]
    assert "competitor_compare" in first["daily_candidates"][0]["rule_hits"]
    assert first["weekly_recovery"]["detected_candidates"] >= 1

    missed.ad_metadata = {"topic_label": "finance"}
    session.commit()

    second = metrics_tasks.build_false_negative_hunt_report(
        session,
        target_date=date(2026, 3, 9),
        false_negative_limit=10,
        queue_recrawls=False,
    )
    assert second["summary"]["candidate_count"] == 0
    assert missed.id in second["resolved_ad_ids"]
    assert second["weekly_recovery"]["resolved_candidates"] >= 1
